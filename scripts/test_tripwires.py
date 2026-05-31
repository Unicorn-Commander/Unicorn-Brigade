"""
Synthetic tripwire-bundle dispatcher — verifies Slack webhook + email plumbing
without running a full Maj. Recon workflow.

Usage (inside the unicorn-brigade container):
  python /app/scripts/test_tripwires.py --dry-run    # build payloads, no send
  python /app/scripts/test_tripwires.py              # actually fire to channels

Environment (graceful no-op if unset):
  MAJIKS_TRIPWIRE_SLACK_WEBHOOK=https://hooks.slack.com/services/T.../B.../...
  MAJIKS_TRIPWIRE_EMAIL_TO=aaron@magicunicorn.tech,shafen@majiks.studio

Recommended sequence after wiring a new Slack webhook:
  1. ssh magicunicorn 'docker exec -e MAJIKS_TRIPWIRE_SLACK_WEBHOOK=<url> \\
       unicorn-brigade python /app/scripts/test_tripwires.py'
  2. confirm message arrives in #majiks-research
  3. add the env var permanently to docker-compose.brigade.yml and restart
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations.majiks_tripwire import dispatch_tripwires  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


SAMPLE_BUNDLE = [
    {
        "rule": "riaa_docket_entry",
        "domain": "court",
        "headline": "RIAA v. Suno (D. Mass. 1:24-cv-11611) — new ECF entry filed",
        "detail": "Cpt. Court flagged a new docket entry on the Sony-track case. Confirm before next deck push.",
        "source_url": "https://www.courtlistener.com/docket/68722499/recording-industry-association-of-america-v-suno-inc/",
        "source_n": "397",
        "deck_impact": "Refresh slide on Sony hearing timeline if filing changes calendar.",
        "severity": "tripwire",
    },
    {
        "rule": "new_funding_round_gt_10M",
        "domain": "cap",
        "headline": "ElevenLabs Series D — $500M @ $11B post (synthetic test)",
        "detail": "Sequoia-led; NVIDIA participating. Materially raises ARR comp benchmarks.",
        "source_url": "https://example.invalid/elevenlabs-d",
        "source_n": "210",
        "deck_impact": "Update comparable-rounds slide.",
        "severity": "tripwire",
    },
    {
        "rule": "model_major_version_release",
        "domain": "stack",
        "headline": "ACE-Step XL — major version release detected (synthetic test)",
        "detail": "v2.0 dropped on HF; download count climbing fast.",
        "source_url": "https://huggingface.co/ACE-Step",
        "source_n": "123",
        "deck_impact": "Re-benchmark Majiks Studio's ACE-Step pipeline.",
        "severity": "tripwire",
    },
    {
        "rule": "new_paper_kids_music",
        "domain": "lab",
        "headline": "New peer-reviewed paper: kids+music intervention (synthetic test)",
        "detail": "Cpt. Lab nominates for the clinical evidence binder.",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/example/",
        "source_n": "405",
        "deck_impact": "Backs up the Majiks Academy positioning.",
        "severity": "tripwire",
    },
]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="render payloads but do not POST or send")
    ap.add_argument("--run-id", default=f"smoke-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
    args = ap.parse_args()

    result = await dispatch_tripwires(SAMPLE_BUNDLE, run_id=args.run_id, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))

    if args.dry_run:
        return 0

    failed = [c for c in result.get("channels", []) if not c.get("ok") and not c.get("skipped")]
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
