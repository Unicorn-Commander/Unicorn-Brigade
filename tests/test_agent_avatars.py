# Executed by Grok (headless lane)
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

# Historical migration 20260731_01 rewrites these three runtime URLs.
# e4d91bfc5d2569604b752d38a32d2ffbeef61829 withdrew majik + sidekick
# portraits; corporal-qwen remains the only approved resident.
STABLE_RESIDENT_IDS = ("majik", "sidekick", "corporal-qwen")
WITHDRAWN_RESIDENT_IDS = ("majik", "sidekick")
REQUIRED_RESIDENT_IDS = ("corporal-qwen",)

# Core roster introduced in 6244a3d8b7ca845c24f8ee3bfe4bd62440102b60
# ("feat: serve canonical agent avatars"). Do not derive this from
# CORE_AGENT_AVATAR_IDS — the registry is the code under test.
EXPECTED_CORE_AGENT_AVATAR_IDS = (
    "the-general",
    "gunny",
    "sgt-cipher",
    "cpt-fullstack",
    "maj-devops",
    "col-finance",
    "lt-taxstrat",
    "judge-advocate",
    "doc-medresearch",
    "detective-holmes",
    "prof-datasci",
    "support-agent",
    "code-reviewer",
    "sql-analyst",
    "sgt-scribe",
    "maj-leadgen",
    "lt-docanalyst",
)

# Brand-Ops masters added alongside the core set; corporal-qwen promoted in
# ded3244e9d0a293d2610362381380bf271932799 and retained by e4d91bf.
EXPECTED_MASTERED_EXTRA_IDS = (
    "iris",
    "perry",
    "prudence",
    "cpl.-colophon",
    "corporal-qwen",
)

# Production verified roster after e4d91bf withdrew majik + sidekick.
EXPECTED_VERIFIED_AGENT_AVATAR_IDS = (
    EXPECTED_CORE_AGENT_AVATAR_IDS
    + EXPECTED_MASTERED_EXTRA_IDS
    + ("rating-raider",)
)

EXPECTED_CORE_PORTRAIT_FILES = tuple(
    f"{agent_id}.webp" for agent_id in EXPECTED_CORE_AGENT_AVATAR_IDS
)
EXPECTED_VERIFIED_PORTRAIT_FILES = tuple(
    f"{agent_id}.webp" for agent_id in EXPECTED_VERIFIED_AGENT_AVATAR_IDS
)
EXPECTED_IRIS_VARIANT_FILES = (
    "iris-thinking.webp",
    "iris-success.webp",
    "iris-alert.webp",
)
EXPECTED_RESIDENT_PNG_FILES = (
    "corporal-qwen.png",
    "corporal-qwen-v2.png",
)

# 2026-07-29 production snapshot: 6 already-bound rows, only corporal-qwen
# of the later residents is verified after e4d91bf.
EXPECTED_SNAPSHOT_AVAILABLE_IDS = ["corporal-qwen"]


def test_verified_roster_matches_production_literals() -> None:
    assert CORE_AGENT_AVATAR_IDS == EXPECTED_CORE_AGENT_AVATAR_IDS
    assert MASTERED_AGENT_AVATAR_IDS == (
        EXPECTED_CORE_AGENT_AVATAR_IDS + EXPECTED_MASTERED_EXTRA_IDS
    )
    assert VERIFIED_AGENT_AVATAR_IDS == EXPECTED_VERIFIED_AGENT_AVATAR_IDS
    assert "majik" not in VERIFIED_AGENT_AVATAR_IDS
    assert "sidekick" not in VERIFIED_AGENT_AVATAR_IDS


def test_every_core_agent_has_a_primary_webp() -> None:
    assert len(EXPECTED_CORE_AGENT_AVATAR_IDS) == 17
    missing = [
        filename
        for filename in EXPECTED_CORE_PORTRAIT_FILES
        if not (PUBLIC_AVATARS / filename).is_file()
    ]
    assert missing == []
    assert CORE_AGENT_AVATAR_IDS == EXPECTED_CORE_AGENT_AVATAR_IDS


def test_every_mastered_agent_has_primary_and_iris_has_existing_variants() -> None:
    expected_mastered = EXPECTED_CORE_AGENT_AVATAR_IDS + EXPECTED_MASTERED_EXTRA_IDS
    missing = [
        f"{agent_id}.webp"
        for agent_id in expected_mastered
        if not (PUBLIC_AVATARS / f"{agent_id}.webp").is_file()
    ]
    assert missing == []
    assert MASTERED_AGENT_AVATAR_IDS == expected_mastered
    for filename in EXPECTED_IRIS_VARIANT_FILES:
        assert (PUBLIC_AVATARS / filename).is_file(), f"missing {filename}"


def test_every_verified_asset_matches_reviewed_sha256() -> None:
    assert VERIFIED_AGENT_AVATAR_IDS == EXPECTED_VERIFIED_AGENT_AVATAR_IDS
    assert set(VERIFIED_AGENT_AVATAR_SHA256) == set(EXPECTED_VERIFIED_AGENT_AVATAR_IDS)
    for agent_id in EXPECTED_VERIFIED_AGENT_AVATAR_IDS:
        filename = f"{agent_id}.webp"
        asset = PUBLIC_AVATARS / filename
        assert asset.is_file(), f"missing required portrait {filename}"
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == VERIFIED_AGENT_AVATAR_SHA256[agent_id]


def test_core_avatar_paths_are_same_origin_and_stable() -> None:
    assert canonical_avatar_path("the-general") == "/avatars/the-general.webp"
    assert canonical_avatar_path("not-a-core-agent") is None
    for agent_id in EXPECTED_CORE_AGENT_AVATAR_IDS:
        path = canonical_avatar_path(agent_id)
        assert path == f"/avatars/{agent_id}.webp"
        assert ".." not in path
    assert canonical_avatar_path("iris") == "/avatars/iris.webp"
    assert canonical_avatar_path("perry") == "/avatars/perry.webp"
    assert canonical_avatar_path("prudence") == "/avatars/prudence.webp"
    assert canonical_avatar_path("cpl.-colophon") == "/avatars/cpl.-colophon.webp"
    assert canonical_avatar_path("rating-raider") == "/avatars/rating-raider.webp"
    # e4d91bf: withdrawn portraits must not resolve; corporal-qwen must.
    assert canonical_avatar_path("corporal-qwen") == "/avatars/corporal-qwen.webp"
    for agent_id in WITHDRAWN_RESIDENT_IDS:
        assert canonical_avatar_path(agent_id) is None


def test_stable_resident_cdn_bust_pngs_remain_available() -> None:
    """Runtime -v2.png bindings must keep resolving until migration + deploy.

    e4d91bf withdrew majik/sidekick assets. corporal-qwen PNGs are required;
    a missing file is a failure, not a skip.
    """

    for filename in EXPECTED_RESIDENT_PNG_FILES:
        assert (PUBLIC_AVATARS / filename).is_file(), f"missing required portrait {filename}"
    for agent_id in REQUIRED_RESIDENT_IDS:
        primary = PUBLIC_AVATARS / f"{agent_id}.png"
        bust = PUBLIC_AVATARS / f"{agent_id}-v2.png"
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
    version, _description, sql = next(
        row for row in MIGRATIONS if row[0] == "20260731_01_stable_resident_avatar_urls"
    )
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
    # aliases). After e4d91bf only corporal-qwen of the later residents is
    # verified; majik/sidekick stay unmapped. Counts are literals, not derived
    # from VERIFIED_AGENT_AVATAR_IDS.
    assert report["verified"] == 6
    assert report["custom"] == 0
    assert report["available"] == 1
    assert report["unmapped"] == 42
    assert report["boundPercent"] == 12.2
    available_ids = sorted(
        item["agentId"] for item in report["entries"] if item["status"] == "available"
    )
    assert available_ids == EXPECTED_SNAPSHOT_AVAILABLE_IDS
    assert [
        item["agentId"]
        for item in report["entries"]
        if item["status"] == "unmapped"
    ] == sorted(
        [
            item["id"]
            for item in snapshot["agents"]
            if item["avatarUrl"] is None
            and item["id"] not in EXPECTED_SNAPSHOT_AVAILABLE_IDS
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
    # e4d91bf withdrew majik; the planner must not invent a binding.
    assert all(item["agentId"] != "majik" for item in planned)
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
