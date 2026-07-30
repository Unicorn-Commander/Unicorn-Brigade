"""Contract tests for Brigade-owned core-agent portraits."""

from pathlib import Path

from app.agent_avatars import (
    CORE_AGENT_AVATAR_IDS,
    MASTERED_AGENT_AVATAR_IDS,
    canonical_avatar_path,
)


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
