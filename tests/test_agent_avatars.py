"""Contract tests for Brigade-owned agent portraits and coverage workflow."""

import hashlib
import json
from pathlib import Path

import pytest

from app.agent_avatars import (
    CORE_AGENT_AVATAR_IDS,
    MASTERED_AGENT_AVATAR_IDS,
    VERIFIED_AGENT_AVATAR_IDS,
    VERIFIED_AGENT_AVATAR_SHA256,
    build_avatar_coverage,
    canonical_avatar_path,
    normalize_avatar_url,
    plan_verified_avatar_updates,
    validate_explicit_avatar_url,
)
from app.db.migrations import MIGRATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_AVATARS = REPO_ROOT / "frontend" / "public" / "avatars"

STABLE_RESIDENT_IDS = ("majik", "sidekick", "corporal-qwen")


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
    for agent_id in STABLE_RESIDENT_IDS:
        assert canonical_avatar_path(agent_id) == f"/avatars/{agent_id}.webp"


def test_stable_resident_cdn_bust_pngs_remain_available() -> None:
    """Runtime -v2.png bindings must keep resolving until migration + deploy."""

    for agent_id in STABLE_RESIDENT_IDS:
        primary = PUBLIC_AVATARS / f"{agent_id}.png"
        bust = PUBLIC_AVATARS / f"{agent_id}-v2.png"
        assert primary.is_file()
        assert bust.is_file()
        assert primary.read_bytes() == bust.read_bytes()


def test_avatar_migration_split_statements_begin_with_sql() -> None:
    sql = next(
        migration_sql
        for version, _description, migration_sql in MIGRATIONS
        if version == "20260729_01_core_agent_avatar_urls"
    )
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    assert statements
    assert all(not statement.startswith("--") for statement in statements)


def test_rating_raider_migration_is_null_only() -> None:
    version, _description, sql = next(
        row for row in MIGRATIONS if row[0] == "20260729_02_rating_raider_avatar_url"
    )
    assert version == "20260729_02_rating_raider_avatar_url"
    assert "id = 'rating-raider'" in sql
    assert "avatar_url IS NULL OR btrim(avatar_url) = ''" in sql


def test_stable_resident_migration_rewrites_known_runtime_urls() -> None:
    version, _description, sql = MIGRATIONS[-1]
    assert version == "20260731_01_stable_resident_avatar_urls"
    for agent_id in STABLE_RESIDENT_IDS:
        assert f"id = '{agent_id}'" in sql
        assert f"/avatars/{agent_id}.webp" in sql
        assert f"/avatars/{agent_id}-v2.png" in sql
    # Never a bare name-similarity bind for unrelated agents.
    assert "meeting-ops-dev" not in sql


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
    # Snapshot still has only the original six bound rows (rating-raider + core
    # aliases). majik/sidekick/corporal-qwen were null on 2026-07-29 and become
    # "available" once promoted into the verified manifest — never auto-bound.
    assert report["verified"] == 6
    assert report["custom"] == 0
    assert report["available"] == 3
    assert report["unmapped"] == 40
    assert report["boundPercent"] == 12.2
    available_ids = sorted(
        item["agentId"] for item in report["entries"] if item["status"] == "available"
    )
    assert available_ids == sorted(STABLE_RESIDENT_IDS)
    assert [
        item["agentId"]
        for item in report["entries"]
        if item["status"] == "unmapped"
    ] == sorted(
        [
            item["id"]
            for item in snapshot["agents"]
            if item["avatarUrl"] is None and item["id"] not in STABLE_RESIDENT_IDS
        ]
    )


def test_safe_apply_planner_never_replaces_custom_or_guesses() -> None:
    roster = [
        {"id": "iris", "avatarUrl": None},
        {"id": "rating-raider", "avatarUrl": "https://example.test/custom.webp"},
        {"id": "meeting-ops-dev", "avatarUrl": None},
        {"id": "majik", "avatarUrl": None},
    ]
    planned = plan_verified_avatar_updates(roster)
    assert {"agentId": "iris", "avatarUrl": "/avatars/iris.webp"} in planned
    assert {"agentId": "majik", "avatarUrl": "/avatars/majik.webp"} in planned
    assert all(item["agentId"] != "rating-raider" for item in planned)
    assert all(item["agentId"] != "meeting-ops-dev" for item in planned)
    try:
        plan_verified_avatar_updates(roster, ["meeting-ops-dev"])
    except ValueError as exc:
        assert str(exc) == "No reviewed avatar mapping for: meeting-ops-dev"
    else:
        raise AssertionError("unverified ID must be rejected")


def test_normalize_and_validate_explicit_avatar_url() -> None:
    assert normalize_avatar_url(None) is None
    assert normalize_avatar_url("  ") is None
    assert normalize_avatar_url(" /avatars/majik.webp ") == "/avatars/majik.webp"
    assert validate_explicit_avatar_url("/avatars/majik.webp") == "/avatars/majik.webp"
    assert (
        validate_explicit_avatar_url("https://brigade.magicunicorn.dev/avatars/majik.webp")
        == "https://brigade.magicunicorn.dev/avatars/majik.webp"
    )
    with pytest.raises(ValueError):
        validate_explicit_avatar_url("javascript:alert(1)")
    with pytest.raises(ValueError):
        validate_explicit_avatar_url("//evil.example/x")
    with pytest.raises(ValueError):
        validate_explicit_avatar_url("/avatars/../etc/passwd")
    with pytest.raises(ValueError):
        validate_explicit_avatar_url("http://insecure.example/x.png")
