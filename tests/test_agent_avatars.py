"""Contract tests for Brigade-owned agent portraits and coverage workflow."""

import hashlib
import json
from pathlib import Path

from app.agent_avatars import (
    CORE_AGENT_AVATAR_IDS,
    MASTERED_AGENT_AVATAR_IDS,
    VERIFIED_AGENT_AVATAR_IDS,
    VERIFIED_AGENT_AVATAR_SHA256,
    build_avatar_coverage,
    canonical_avatar_path,
    plan_verified_avatar_updates,
)
from app.db.migrations import MIGRATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_AVATARS = REPO_ROOT / "frontend" / "public" / "avatars"


def test_every_core_agent_has_a_primary_webp() -> None:
    assert len(CORE_AGENT_AVATAR_IDS) == 17
    missing = [
        agent_id
        for agent_id in CORE_AGENT_AVATAR_IDS
        if not (PUBLIC_AVATARS / f"{agent_id}.webp").is_file()
    ]
    assert missing == []


def test_every_mastered_agent_has_primary_and_iris_has_existing_variants() -> None:
    missing = [
        agent_id
        for agent_id in MASTERED_AGENT_AVATAR_IDS
        if not (PUBLIC_AVATARS / f"{agent_id}.webp").is_file()
    ]
    assert missing == []
    for state in ("thinking", "success", "alert"):
        assert (PUBLIC_AVATARS / f"iris-{state}.webp").is_file()


def test_every_verified_asset_matches_reviewed_sha256() -> None:
    assert set(VERIFIED_AGENT_AVATAR_IDS) == set(VERIFIED_AGENT_AVATAR_SHA256)
    for agent_id, expected_sha256 in VERIFIED_AGENT_AVATAR_SHA256.items():
        asset = PUBLIC_AVATARS / f"{agent_id}.webp"
        assert asset.is_file()
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == expected_sha256


def test_core_avatar_paths_are_same_origin_and_stable() -> None:
    assert canonical_avatar_path("the-general") == "/avatars/the-general.webp"
    assert canonical_avatar_path("not-a-core-agent") is None
    for agent_id in CORE_AGENT_AVATAR_IDS:
        path = canonical_avatar_path(agent_id)
        assert path == f"/avatars/{agent_id}.webp"
        assert ".." not in path
    assert canonical_avatar_path("iris") == "/avatars/iris.webp"
    assert canonical_avatar_path("perry") == "/avatars/perry.webp"
    assert canonical_avatar_path("prudence") == "/avatars/prudence.webp"
    assert canonical_avatar_path("cpl.-colophon") == "/avatars/cpl.-colophon.webp"
    assert canonical_avatar_path("rating-raider") == "/avatars/rating-raider.webp"


def test_avatar_migration_split_statements_begin_with_sql() -> None:
    sql = next(
        migration_sql
        for version, _description, migration_sql in MIGRATIONS
        if version == "20260729_01_core_agent_avatar_urls"
    )
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    assert statements
    assert all(not statement.startswith("--") for statement in statements)


def test_rating_raider_migration_is_null_only_and_appended() -> None:
    version, _description, sql = MIGRATIONS[-1]
    assert version == "20260729_02_rating_raider_avatar_url"
    assert "id = 'rating-raider'" in sql
    assert "avatar_url IS NULL OR btrim(avatar_url) = ''" in sql


def test_production_roster_coverage_is_explicit_and_complete() -> None:
    snapshot = json.loads(
        (
            REPO_ROOT
            / "docs"
            / "agent-avatar-production-roster-2026-07-29.json"
        ).read_text()
    )
    report = build_avatar_coverage(snapshot["agents"])
    assert report["total"] == 49
    assert report["verified"] == 6
    assert report["custom"] == 0
    assert report["available"] == 0
    assert report["unmapped"] == 43
    assert report["boundPercent"] == 12.2
    assert [
        item["agentId"]
        for item in report["entries"]
        if item["status"] == "unmapped"
    ] == sorted(
        [
            item["id"]
            for item in snapshot["agents"]
            if item["avatarUrl"] is None
        ]
    )


def test_safe_apply_planner_never_replaces_custom_or_guesses() -> None:
    roster = [
        {"id": "iris", "avatarUrl": None},
        {"id": "rating-raider", "avatarUrl": "https://example.test/custom.webp"},
        {"id": "meeting-ops-dev", "avatarUrl": None},
    ]
    assert plan_verified_avatar_updates(roster) == [
        {"agentId": "iris", "avatarUrl": "/avatars/iris.webp"}
    ]
    try:
        plan_verified_avatar_updates(roster, ["meeting-ops-dev"])
    except ValueError as exc:
        assert str(exc) == "No reviewed avatar mapping for: meeting-ops-dev"
    else:
        raise AssertionError("unverified ID must be rejected")
