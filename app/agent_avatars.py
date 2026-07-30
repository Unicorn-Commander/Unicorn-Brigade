"""Canonical portrait paths for Brigade's built-in shared roster.

Brigade owns agent identity.  The corresponding WebP files live in the
Brigade frontend's public ``/avatars`` directory and are served by the same
public Brigade origin as the API.  Keeping the registry here gives the seed
loader, migrations, tests, and downstream consumers one explicit contract.

Status variants (``-thinking``, ``-success``, ``-alert``) are presentation
assets.  ``avatarUrl`` always points at the stable primary portrait.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import urlparse

CORE_AGENT_AVATAR_IDS: tuple[str, ...] = (
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

# Approved external identity masters imported into Brigade's runtime catalog.
# Brand-Ops remains the artwork source; Brigade owns the binding and served URL.
MASTERED_AGENT_AVATAR_IDS: tuple[str, ...] = CORE_AGENT_AVATAR_IDS + (
    "iris",
    "perry",
    "prudence",
    "cpl.-colophon",
)

# This asset was already bound explicitly to the production ``rating-raider``
# row and served at the URL below before it was imported into source control.
# The binding is identity-owner evidence; no visual/name inference was used.
RUNTIME_BOUND_AGENT_AVATAR_IDS: tuple[str, ...] = ("rating-raider",)

VERIFIED_AGENT_AVATAR_IDS: tuple[str, ...] = (
    MASTERED_AGENT_AVATAR_IDS + RUNTIME_BOUND_AGENT_AVATAR_IDS
)

# Hashes cover the exact primary WebP bytes shipped by Brigade.  Tests compare
# this manifest with the frontend assets so an accidental replacement cannot
# silently change an agent's identity.
VERIFIED_AGENT_AVATAR_SHA256: dict[str, str] = {
    "the-general": "5fa092c146160ae24922735a9e924a0a9b7241616ddb5a25e9598a15d99ed57b",
    "gunny": "1a6b12f201fdfa1c23aebcd055bd3dd73002bf03d7690c22818045c9076b3f14",
    "sgt-cipher": "0e9a7cee4b65a5f0e7826248b00463874602b089c65f16e00cd04c55e9d18315",
    "cpt-fullstack": "c1f8046a8dea209c85088b57caf24ee28ed9fe02b331f1a612ae261c6cced222",
    "maj-devops": "d66c52325bdcc2166bc1a03e35ae72040ed10004fdcbdc0efd83f5ae1ae674bb",
    "col-finance": "54d13efe40213b84e08df4786979ff348789ca209e29d6689115cad6ab6ce4b8",
    "lt-taxstrat": "7127d7664578d4f437212d548c57790fdf08d7786aa6e83b4e15ee775f1eef70",
    "judge-advocate": "8ab21b3e09643f3bf00ea21045b3bf0f0d4a13f87dfe81dfe7c5c627dd17b957",
    "doc-medresearch": "a991dc1c0939dbc4f8fa6cb7589f5f6311852835aa326e85fc60ca6513d24145",
    "detective-holmes": "0d1c04ea4a42efadac88c9f42b48716b29e18663275faf482bd0bec455db039c",
    "prof-datasci": "d8f91846e427c77717d0929013364cb035af7b0ef7a94ec2bfc3fc8399ea9f2c",
    "support-agent": "1287a11d551857ac308b9f1b8fdc5899e05973880d2fcb7e46ebd2d26eac2238",
    "code-reviewer": "4e71bfaba9df9207ff1edea007f12ad65727f632c55613e2382940eb5467ef63",
    "sql-analyst": "b9cd77665614d021d516c900c4af6f002921c240ce7ace96aa86a7f41f33ac8a",
    "sgt-scribe": "da5d4693ea6d70af76a06aba364dcb1c61e932e4ecaa11049b69009e9e4345ca",
    "maj-leadgen": "44916ac310963cdc08a55588cbd06af31563bd704ecbab4c1efa1f6787b72e70",
    "lt-docanalyst": "16f5ebccdc73d609c8b5e3bd838a0ee8a47ba120ff958db0d628960728a78c43",
    "iris": "f1c88540050c6d9533eb0c5e6d91acde0aa5a9d1158881b03cc32a6f064841c3",
    "perry": "7a032fac11cfa1787d0351e87b1212f3f19ed4ee6e4549c1c58b818820e49994",
    "prudence": "e24106302346bdc8df320e505a62a5ecda58d19e2934f769cec3bab907be7f85",
    "cpl.-colophon": "ece30097615b715a9f5f95df93dbc4be6c7f3765f8ae70a409924d590ba59685",
    "rating-raider": "4f4691c2eaa2989c1e249999c75f3f6c528515d96018e18caf2e4b023bbd06a3",
}

VERIFIED_AGENT_AVATAR_EVIDENCE: dict[str, str] = {
    **dict.fromkeys(CORE_AGENT_AVATAR_IDS, "brigade-core-roster"),
    "iris": "brand-ops-approved-master:iris",
    "perry": "brand-ops-approved-master:perrywinkle-spector;existing-runtime-alias",
    "prudence": "brand-ops-approved-master:prudence-finch;existing-runtime-alias",
    "cpl.-colophon": "brand-ops-approved-master:cpl-colophon;existing-runtime-alias",
    "rating-raider": "existing-production-runtime-binding:2026-07-29",
}


def canonical_avatar_path(agent_id: str) -> str | None:
    """Return the same-origin primary portrait for a verified agent mapping."""

    if agent_id not in VERIFIED_AGENT_AVATAR_IDS:
        return None
    return f"/avatars/{agent_id}.webp"


def _is_verified_binding(agent_id: str, avatar_url: str) -> bool:
    """Return true only for the known same-origin path (or its live origin)."""

    expected = canonical_avatar_path(agent_id)
    if not expected:
        return False
    if avatar_url == expected:
        return True
    parsed = urlparse(avatar_url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "brigade.magicunicorn.dev"
        and parsed.path == expected
        and not parsed.query
        and not parsed.fragment
    )


def build_avatar_coverage(agents: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Build an admin-readable, machine-readable coverage report.

    The database roster is authoritative. A non-empty custom URL is reported
    but never overwritten. A missing URL is considered safely applicable only
    when the ID exists in the reviewed verified-asset manifest above.
    """

    entries: list[dict[str, object]] = []
    counts = {
        "verified": 0,
        "custom": 0,
        "available": 0,
        "unmapped": 0,
    }
    for agent in sorted(agents, key=lambda item: str(item["id"])):
        agent_id = str(agent["id"])
        raw_url = agent.get("avatarUrl", agent.get("avatar_url"))
        avatar_url = str(raw_url).strip() if raw_url else ""
        verified_path = canonical_avatar_path(agent_id)
        evidence = VERIFIED_AGENT_AVATAR_EVIDENCE.get(agent_id)

        if avatar_url and _is_verified_binding(agent_id, avatar_url):
            status = "verified"
            reason = "Database binding matches the reviewed Brigade asset."
        elif avatar_url:
            status = "custom"
            reason = "Existing custom URL is preserved; identity has not been inferred."
        elif verified_path:
            status = "available"
            reason = "Reviewed asset is available and can be applied idempotently."
        else:
            status = "unmapped"
            reason = "No explicit identity-owner mapping or exact reviewed asset."
        counts[status] += 1
        entries.append(
            {
                "agentId": agent_id,
                "avatarUrl": avatar_url or None,
                "status": status,
                "verifiedAvatarUrl": verified_path,
                "assetSha256": VERIFIED_AGENT_AVATAR_SHA256.get(agent_id),
                "evidence": evidence,
                "reason": reason,
            }
        )

    total = len(entries)
    bound = counts["verified"] + counts["custom"]
    return {
        "total": total,
        "bound": bound,
        "verified": counts["verified"],
        "custom": counts["custom"],
        "available": counts["available"],
        "unmapped": counts["unmapped"],
        "boundPercent": round((bound / total) * 100, 1) if total else 100.0,
        "entries": entries,
    }


def plan_verified_avatar_updates(
    agents: Iterable[Mapping[str, object]],
    requested_ids: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    """Plan null-only assignments from the reviewed manifest.

    Callers may select a subset. Unknown or unverified IDs are rejected instead
    of being guessed. Existing URLs, including custom URLs, are never planned.
    """

    requested = set(requested_ids) if requested_ids is not None else None
    if requested is not None:
        unverifiable = sorted(
            agent_id for agent_id in requested
            if canonical_avatar_path(agent_id) is None
        )
        if unverifiable:
            raise ValueError(
                "No reviewed avatar mapping for: " + ", ".join(unverifiable)
            )

    updates: list[dict[str, str]] = []
    for agent in sorted(agents, key=lambda item: str(item["id"])):
        agent_id = str(agent["id"])
        if requested is not None and agent_id not in requested:
            continue
        raw_url = agent.get("avatarUrl", agent.get("avatar_url"))
        if raw_url and str(raw_url).strip():
            continue
        path = canonical_avatar_path(agent_id)
        if path:
            updates.append({"agentId": agent_id, "avatarUrl": path})
    return updates
