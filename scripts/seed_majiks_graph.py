"""
One-time seed: bootstrap the Majiks Ecosystem Research FalkorDB graph
from the existing markdown catalog so Maj. Recon's first monthly run
starts with full state instead of an empty graph.

Spec: Research/Majiks-Ecosystem-Research/10-pitch-deck-assets/brigade-monitor-agent-spec.md

What it does:
  - Mechanically parses the source bibliography (00-index/sources.md) into (:Source) nodes
  - Mechanically parses the papers manifest (09-papers/MANIFEST.md) into (:AcademicPaper) nodes
  - Emits structured (:Company), (:FundingRound), (:Investor), (:Lawsuit), (:Regulation) nodes
    extracted from comparable-rounds.md / litigation-tracker.md / regulatory-landscape.md
  - Wires (Company)-[:RAISED]->(FundingRound), (FundingRound)-[:LED_BY|PARTICIPANT]->(Investor),
    (Lawsuit)-[:AGAINST]->(Company), and (Source)-[:CITES]->(*) edges
  - Creates one (:MonitorRun {version: "v0-bootstrap"}) provenance node with
    (MonitorRun)-[:UPDATED]->(*) edges to every node touched

Idempotent: every write is a MERGE, so re-running is safe.

Usage:
  python scripts/seed_majiks_graph.py --dry-run                  # print stats, no writes
  python scripts/seed_majiks_graph.py                            # write to majiks_research graph
  python scripts/seed_majiks_graph.py --graph-name majiks_test   # write to a sandbox graph
  CATALOG_PATH=/data/majiks-research python scripts/seed_majiks_graph.py
                                                                  # override catalog mount path
  FALKORDB_HOST=brigade-falkordb FALKORDB_PORT=6380 ... python scripts/seed_majiks_graph.py
                                                                  # standard Brigade env vars

Reads FALKORDB_HOST / FALKORDB_PORT / FALKORDB_PASSWORD / FALKORDB_ENABLED from env (same
contract as KnowledgeGraphManager). Set FALKORDB_ENABLED=true on bigboy to actually connect.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Make Brigade's app/ importable when run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge.graph_manager import KnowledgeGraphManager  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_majiks_graph")

DEFAULT_CATALOG = "/Volumes/Studio Storage/Development/Research/Majiks-Ecosystem-Research"
DEFAULT_GRAPH = "majiks_research"
SEED_VERSION = "v0-bootstrap"


# ---------------------------------------------------------------------------
# Mechanical parsers (catalog → typed records)
# ---------------------------------------------------------------------------

@dataclass
class SourceRecord:
    source_n: str
    title: str = ""
    author_org: str = ""
    published: str = ""
    accessed: str = ""
    url: str = ""
    type: str = ""
    notes: str = ""


@dataclass
class PaperRecord:
    file: str
    source_n: str
    citation: str
    folder: str
    paywalled: bool = False
    paywall_reason: str = ""


def parse_sources_md(path: Path) -> list[SourceRecord]:
    """Parse 00-index/sources.md. Each entry is a `## [source-N]` block followed by
    bullets like `- **Title:** ...`. Stops at the next `## ` heading."""
    if not path.exists():
        log.warning("sources file not found: %s", path)
        return []

    text = path.read_text(encoding="utf-8")
    records: list[SourceRecord] = []
    block_re = re.compile(r"^## \[source-(\d+)\]\s*$", re.MULTILINE)
    matches = list(block_re.finditer(text))
    for i, m in enumerate(matches):
        n = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        rec = SourceRecord(source_n=n)
        for field_name, label in [
            ("title", "Title"),
            ("author_org", "Author/Org"),
            ("published", "Published"),
            ("accessed", "Accessed"),
            ("url", "URL"),
            ("type", "Type"),
            ("notes", "Notes"),
        ]:
            fm = re.search(rf"-\s+\*\*{re.escape(label)}:\*\*\s*(.+?)(?:\n|$)", body)
            if fm:
                setattr(rec, field_name, fm.group(1).strip().strip("[]"))
        records.append(rec)
    return records


def parse_papers_manifest(path: Path) -> list[PaperRecord]:
    """Parse 09-papers/MANIFEST.md. Two parts:
      1. Successfully downloaded — folder-grouped tables `| File | Source | Citation | Size |`
      2. Paywalled / failed — table `| Source | Paper | Reason | Alt checked |`
    """
    if not path.exists():
        log.warning("MANIFEST not found: %s", path)
        return []

    text = path.read_text(encoding="utf-8")
    records: list[PaperRecord] = []
    current_folder = ""
    in_paywalled = False
    folder_re = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
    paywall_marker = re.compile(r"^##\s+Paywalled\s*/\s*failed", re.MULTILINE)

    paywall_start = paywall_marker.search(text)
    paywall_offset = paywall_start.start() if paywall_start else len(text)

    for line in text.splitlines(keepends=False):
        # Track section
        fm = folder_re.match(line)
        if fm:
            current_folder = fm.group(1).strip()
            continue
        if line.startswith("## Paywalled"):
            in_paywalled = True
            continue

        if not line.startswith("|"):
            continue
        if "----" in line:
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # Skip table header rows by exact first-cell match
        if cells and cells[0].lower() in ("file", "source"):
            continue

        if not in_paywalled and len(cells) >= 3:
            file_name = cells[0]
            source_n = cells[1]
            citation = cells[2]
            if file_name and source_n.isdigit():
                records.append(PaperRecord(
                    file=file_name,
                    source_n=source_n,
                    citation=citation,
                    folder=current_folder,
                ))
        elif in_paywalled and len(cells) >= 3:
            source_n = cells[0]
            paper = cells[1]
            reason = cells[2]
            if source_n.isdigit():
                records.append(PaperRecord(
                    file="",
                    source_n=source_n,
                    citation=paper,
                    folder="paywalled",
                    paywalled=True,
                    paywall_reason=reason,
                ))
    return records


# ---------------------------------------------------------------------------
# Structured catalog facts
# ---------------------------------------------------------------------------
# Hand-extracted from comparable-rounds.md, litigation-tracker.md, and
# regulatory-landscape.md. Each entry references the source-N(s) used in the
# original markdown. Treat this as the bootstrap snapshot (2026-04-29). The
# monthly Maj. Recon runs are responsible for keeping the graph current after
# this seed lands.

COMPANIES: list[dict[str, Any]] = [
    # comparable-rounds.md §1
    {"name": "Suno", "type": "ai-music", "hq": "Cambridge, MA", "status": "active",
     "arr_usd": 300_000_000, "arr_date": "2026-02-27",
     "valuation_usd": 2_450_000_000, "valuation_date": "2025-11-19",
     "sources": ["100", "101", "102", "200", "203", "204", "205"]},
    {"name": "Udio", "type": "ai-music", "hq": "New York, NY", "status": "active",
     "sources": ["206", "207", "218"]},
    {"name": "ElevenLabs", "type": "voice-audio-ai", "hq": "London/NY", "status": "active",
     "valuation_usd": 11_000_000_000, "valuation_date": "2026-02-04",
     "arr_usd": 200_000_000, "arr_date": "2025-12-31",
     "sources": ["208", "209", "210", "211"]},
    {"name": "ProducerAI", "type": "ai-music", "hq": "San Francisco", "status": "acquired",
     "notes": "Riffusion → ProducerAI; acquired by Google Feb 24, 2026",
     "sources": ["212", "213"]},
    # comparable-rounds.md §2
    {"name": "DistroKid", "type": "distribution", "hq": "New York", "status": "private",
     "valuation_usd": 1_300_000_000, "valuation_date": "2021-08-31",
     "arr_usd": 97_200_000, "arr_date": "2024-10-31",
     "sources": ["214", "215"]},
    {"name": "CD Baby", "type": "distribution", "status": "subsidiary",
     "notes": "Acquired into UMG Virgin via Downtown Music Holdings Dec 2024 deal, closed Feb 2026",
     "sources": ["216", "217"]},
    {"name": "Downtown Music Holdings", "type": "rights-services", "status": "acquired",
     "notes": "$775M cash to UMG Virgin Music Group Dec 16 2024; closed Feb 2026",
     "sources": ["216", "217", "219"]},
    {"name": "Songtrust", "type": "publisher-admin", "status": "subsidiary",
     "notes": "Subsidiary of Downtown Music Holdings; 4M+ songs, 445K+ songwriters",
     "sources": ["219"]},
    # litigation-tracker plaintiffs/defendants
    {"name": "Universal Music Group", "type": "label", "status": "active", "sources": ["327"]},
    {"name": "Sony Music Entertainment", "type": "label", "status": "active", "sources": ["327"]},
    {"name": "Warner Records", "type": "label", "status": "active", "sources": ["327"]},
    {"name": "Anthropic", "type": "ai-foundation", "status": "active", "sources": ["310", "331", "333"]},
    # MLC reference entity (regulatory)
    {"name": "Mechanical Licensing Collective", "type": "rights-collective", "status": "active",
     "sources": ["338", "339"]},
]

INVESTORS: list[dict[str, Any]] = [
    {"name": "Lightspeed Venture Partners", "type": "vc"},
    {"name": "Menlo Ventures", "type": "vc"},
    {"name": "Matrix Partners", "type": "vc"},
    {"name": "NVIDIA NVentures", "type": "strategic"},
    {"name": "Hallwood Media", "type": "strategic"},
    {"name": "Founder Collective", "type": "vc"},
    {"name": "Andreessen Horowitz (a16z)", "type": "vc"},
    {"name": "ICONIQ Growth", "type": "vc"},
    {"name": "Sequoia Capital", "type": "vc"},
    {"name": "NEA", "type": "vc"},
    {"name": "Greycroft", "type": "vc"},
    {"name": "South Park Commons", "type": "vc"},
    {"name": "Sky9", "type": "vc"},
    {"name": "Insight Partners", "type": "vc"},
    {"name": "Smash Capital", "type": "vc"},
    {"name": "Nat Friedman", "type": "angel"},
    {"name": "Daniel Gross", "type": "angel"},
]

# Each round: company, stage, amount, post-money, date, lead, participants, sources
FUNDING_ROUNDS: list[dict[str, Any]] = [
    {"company": "Suno", "stage": "Series B", "amount_usd": 125_000_000,
     "valuation_post_usd": 500_000_000, "date": "2024-05-01",
     "lead": "Lightspeed Venture Partners",
     "participants": ["Nat Friedman", "Daniel Gross", "Matrix Partners", "Founder Collective"],
     "sources": ["200", "202"]},
    {"company": "Suno", "stage": "Series C", "amount_usd": 250_000_000,
     "valuation_post_usd": 2_450_000_000, "date": "2025-11-19",
     "lead": "Menlo Ventures",
     "participants": ["NVIDIA NVentures", "Hallwood Media", "Lightspeed Venture Partners", "Matrix Partners"],
     "sources": ["203", "204", "205"]},
    {"company": "Udio", "stage": "Seed", "amount_usd": 10_000_000, "date": "2024-04-10",
     "lead": "Andreessen Horowitz (a16z)",
     "participants": [],
     "sources": ["206", "207"]},
    {"company": "ElevenLabs", "stage": "Series B", "amount_usd": 80_000_000,
     "valuation_post_usd": 1_100_000_000, "date": "2024-01-22",
     "lead": "Andreessen Horowitz (a16z)",
     "participants": ["Sequoia Capital", "Smash Capital", "Nat Friedman", "Daniel Gross"],
     "sources": ["208"]},
    {"company": "ElevenLabs", "stage": "Series C", "amount_usd": 180_000_000,
     "valuation_post_usd": 3_300_000_000, "date": "2025-01-30",
     "lead": "Andreessen Horowitz (a16z)",
     "participants": ["ICONIQ Growth", "NEA", "Sequoia Capital"],
     "sources": ["209"]},
    {"company": "ElevenLabs", "stage": "Series D", "amount_usd": 500_000_000,
     "valuation_post_usd": 11_000_000_000, "date": "2026-02-04",
     "lead": "Sequoia Capital",
     "participants": ["NVIDIA NVentures"],
     "sources": ["210", "211"]},
    {"company": "ProducerAI", "stage": "Seed", "amount_usd": 4_000_000, "date": "2023-10-01",
     "lead": "Greycroft",
     "participants": ["South Park Commons", "Sky9"],
     "sources": ["212"]},
    {"company": "DistroKid", "stage": "Minority Investment", "amount_usd": 0,
     "valuation_post_usd": 1_300_000_000, "date": "2021-08-01",
     "lead": "Insight Partners",
     "participants": [],
     "sources": ["214"]},
]

LAWSUITS: list[dict[str, Any]] = [
    {"plaintiff": "Universal Music Group + Sony Music Entertainment + Warner Records",
     "defendants": ["Suno"],
     "court": "D. Mass.", "case_no": "1:24-cv-11611", "filed_date": "2024-06-24",
     "judge": "Chief Judge F. Dennis Saylor IV",
     "status": "Sony continues litigating; UMG and Warner settled Nov 2025",
     "last_update_date": "2026-04-29",
     "name": "RIAA v. Suno",
     "key_dates": "Summary judgment motions due 2027-01-08",
     "sources": ["327", "328", "397", "316", "318"]},
    {"plaintiff": "Universal Music Group + Sony Music Entertainment + Warner Records",
     "defendants": ["Udio"],
     "court": "S.D.N.Y.", "case_no": "1:24-cv-04777", "filed_date": "2024-06-24",
     "status": "Sony continues litigating; UMG settled Oct 30 2025; Warner settled late 2025",
     "last_update_date": "2026-04-29",
     "name": "RIAA v. Udio",
     "sources": ["327", "306", "307", "308", "317", "324", "315"]},
    {"plaintiff": "Concord Music Group + Universal Music Publishing + ABKCO et al.",
     "defendants": ["Anthropic"],
     "court": "N.D. Cal.", "case_no": "5:24-cv-03811", "filed_date": "2023-10-01",
     "status": "Pending; new piracy complaint filed 2026-01-29 alleging 20,000+ torrented works, $3B+ damages estimate",
     "last_update_date": "2026-01-29",
     "name": "Music Publishers v. Anthropic",
     "sources": ["310", "331", "332", "333"]},
    {"plaintiff": "Independent musicians (proposed class)",
     "defendants": ["Suno"],
     "court": "TBD", "case_no": "TBD", "filed_date": "2025-11-01",
     "status": "Early stage; class certification pending",
     "last_update_date": "2026-04-29",
     "name": "Nguyen v. Suno",
     "sources": ["314"]},
]

REGULATIONS: list[dict[str, Any]] = [
    {"name": "Music Modernization Act (MMA)", "jurisdiction": "US-Federal",
     "status": "enacted", "effective_date": "2018-10-11",
     "scope": "Established MLC blanket mechanical license for digital audio",
     "sources": ["337", "338", "339"]},
    {"name": "NO FAKES Act", "jurisdiction": "US-Federal", "status": "pending",
     "effective_date": "",
     "scope": "Federal civil right against unauthorized AI replicas of voice/likeness",
     "sources": ["347", "348", "349", "350", "351", "352"]},
    {"name": "Take It Down Act", "jurisdiction": "US-Federal", "status": "enacted",
     "effective_date": "2025-05-19",
     "scope": "Non-consensual intimate deepfakes; notice-and-takedown",
     "sources": ["353"]},
    {"name": "Tennessee ELVIS Act", "jurisdiction": "US-TN", "status": "enacted",
     "effective_date": "2024-07-01",
     "scope": "First state law specifically protecting against AI voice cloning",
     "sources": ["354", "355"]},
    {"name": "U.S. Copyright Office AI Report Part 2 (Copyrightability)",
     "jurisdiction": "US-Federal", "status": "issued", "effective_date": "2025-01-29",
     "scope": "Prompts alone do not establish authorship; human contribution required",
     "sources": ["345", "346"]},
]


# ---------------------------------------------------------------------------
# Cypher emitters (idempotent MERGE)
# ---------------------------------------------------------------------------

def _props_set_clause(alias: str, props: dict[str, Any]) -> str:
    return ", ".join(f"{alias}.{k} = ${k}" for k in props.keys())


async def _exec(kg: KnowledgeGraphManager, graph_name: str, query: str,
                params: dict[str, Any], dry_run: bool, stats: dict[str, int]) -> None:
    if dry_run:
        # Track intent for stats; don't write
        return
    graph = kg._get_graph(graph_name)
    if graph is None:
        raise RuntimeError(f"Could not select FalkorDB graph '{graph_name}'. "
                           "Set FALKORDB_ENABLED=true and ensure the server is reachable.")
    result = graph.query(query, params)
    stats["nodes_created"] += int(getattr(result, "nodes_created", 0) or 0)
    stats["relationships_created"] += int(getattr(result, "relationships_created", 0) or 0)


async def merge_source(kg, graph_name, rec: SourceRecord, dry_run, stats):
    props = {
        "source_n": rec.source_n,
        "title": rec.title,
        "author_org": rec.author_org,
        "published": rec.published,
        "accessed_date": rec.accessed,
        "url": rec.url,
        "type": rec.type,
        "notes": rec.notes,
    }
    query = (
        "MERGE (s:Source {source_n: $source_n}) "
        "ON CREATE SET " + _props_set_clause("s", {k: v for k, v in props.items() if k != "source_n"}) + " "
        "ON MATCH SET " + _props_set_clause("s", {k: v for k, v in props.items() if k != "source_n"})
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)


async def merge_paper(kg, graph_name, rec: PaperRecord, dry_run, stats):
    props = {
        "source_n": rec.source_n,
        "citation": rec.citation,
        "file": rec.file,
        "folder": rec.folder,
        "paywalled": rec.paywalled,
        "paywall_reason": rec.paywall_reason,
    }
    query = (
        "MERGE (p:AcademicPaper {source_n: $source_n}) "
        "ON CREATE SET " + _props_set_clause("p", {k: v for k, v in props.items() if k != "source_n"}) + " "
        "ON MATCH SET " + _props_set_clause("p", {k: v for k, v in props.items() if k != "source_n"}) + " "
        "WITH p "
        "MATCH (s:Source {source_n: $source_n}) "
        "MERGE (s)-[:CITES]->(p)"
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)


async def merge_company(kg, graph_name, rec: dict, dry_run, stats):
    sources = rec.get("sources", [])
    props = {k: v for k, v in rec.items() if k != "sources"}
    set_clause = _props_set_clause("c", {k: v for k, v in props.items() if k != "name"})
    query = (
        "MERGE (c:Company {name: $name}) "
        f"ON CREATE SET {set_clause} "
        f"ON MATCH SET {set_clause}"
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)
    for source_n in sources:
        await _exec(kg, graph_name,
                    "MATCH (s:Source {source_n: $source_n}), (c:Company {name: $name}) "
                    "MERGE (s)-[:CITES]->(c)",
                    {"source_n": source_n, "name": rec["name"]}, dry_run, stats)


async def merge_investor(kg, graph_name, rec: dict, dry_run, stats):
    set_clause = _props_set_clause("i", {k: v for k, v in rec.items() if k != "name"})
    query = (
        "MERGE (i:Investor {name: $name}) "
        f"ON CREATE SET {set_clause} "
        f"ON MATCH SET {set_clause}"
    )
    await _exec(kg, graph_name, query, rec, dry_run, stats)


async def merge_funding_round(kg, graph_name, rec: dict, dry_run, stats):
    company = rec["company"]
    stage = rec["stage"]
    fr_id = f"{company}|{stage}|{rec.get('date', '')}"
    props = {
        "round_id": fr_id,
        "company": company,
        "stage": stage,
        "amount_usd": rec.get("amount_usd"),
        "valuation_post_usd": rec.get("valuation_post_usd"),
        "date": rec.get("date"),
        "lead_investor": rec.get("lead"),
    }
    set_clause = _props_set_clause("fr", {k: v for k, v in props.items() if k != "round_id"})
    query = (
        "MERGE (fr:FundingRound {round_id: $round_id}) "
        f"ON CREATE SET {set_clause} "
        f"ON MATCH SET {set_clause} "
        "WITH fr "
        "MATCH (c:Company {name: $company}) "
        "MERGE (c)-[:RAISED]->(fr)"
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)
    if rec.get("lead"):
        await _exec(kg, graph_name,
                    "MATCH (fr:FundingRound {round_id: $round_id}), (i:Investor {name: $name}) "
                    "MERGE (fr)-[:LED_BY]->(i)",
                    {"round_id": fr_id, "name": rec["lead"]}, dry_run, stats)
    for participant in rec.get("participants", []) or []:
        await _exec(kg, graph_name,
                    "MATCH (fr:FundingRound {round_id: $round_id}), (i:Investor {name: $name}) "
                    "MERGE (fr)-[:PARTICIPANT]->(i)",
                    {"round_id": fr_id, "name": participant}, dry_run, stats)
    for source_n in rec.get("sources", []) or []:
        await _exec(kg, graph_name,
                    "MATCH (s:Source {source_n: $source_n}), (fr:FundingRound {round_id: $round_id}) "
                    "MERGE (s)-[:CITES]->(fr)",
                    {"source_n": source_n, "round_id": fr_id}, dry_run, stats)


async def merge_lawsuit(kg, graph_name, rec: dict, dry_run, stats):
    case_id = rec.get("case_no", "") + "|" + rec.get("name", "")
    props = {
        "case_id": case_id,
        "name": rec["name"],
        "plaintiff": rec.get("plaintiff", ""),
        "court": rec.get("court", ""),
        "case_no": rec.get("case_no", ""),
        "filed_date": rec.get("filed_date", ""),
        "status": rec.get("status", ""),
        "last_update_date": rec.get("last_update_date", ""),
        "judge": rec.get("judge", ""),
        "key_dates": rec.get("key_dates", ""),
    }
    set_clause = _props_set_clause("l", {k: v for k, v in props.items() if k != "case_id"})
    query = (
        "MERGE (l:Lawsuit {case_id: $case_id}) "
        f"ON CREATE SET {set_clause} "
        f"ON MATCH SET {set_clause}"
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)
    for defendant in rec.get("defendants", []) or []:
        await _exec(kg, graph_name,
                    "MATCH (l:Lawsuit {case_id: $case_id}), (c:Company {name: $name}) "
                    "MERGE (l)-[:AGAINST]->(c)",
                    {"case_id": case_id, "name": defendant}, dry_run, stats)
    for source_n in rec.get("sources", []) or []:
        await _exec(kg, graph_name,
                    "MATCH (s:Source {source_n: $source_n}), (l:Lawsuit {case_id: $case_id}) "
                    "MERGE (s)-[:CITES]->(l)",
                    {"source_n": source_n, "case_id": case_id}, dry_run, stats)


async def merge_regulation(kg, graph_name, rec: dict, dry_run, stats):
    props = {
        "name": rec["name"],
        "jurisdiction": rec.get("jurisdiction", ""),
        "status": rec.get("status", ""),
        "effective_date": rec.get("effective_date", ""),
        "scope": rec.get("scope", ""),
    }
    set_clause = _props_set_clause("r", {k: v for k, v in props.items() if k != "name"})
    query = (
        "MERGE (r:Regulation {name: $name}) "
        f"ON CREATE SET {set_clause} "
        f"ON MATCH SET {set_clause}"
    )
    await _exec(kg, graph_name, query, props, dry_run, stats)
    for source_n in rec.get("sources", []) or []:
        await _exec(kg, graph_name,
                    "MATCH (s:Source {source_n: $source_n}), (r:Regulation {name: $name}) "
                    "MERGE (s)-[:CITES]->(r)",
                    {"source_n": source_n, "name": rec["name"]}, dry_run, stats)


async def merge_monitor_run_provenance(kg, graph_name, run_id: str, dry_run, stats):
    """Create one MonitorRun node and (MonitorRun)-[:UPDATED]->(*) for every node we touched."""
    await _exec(kg, graph_name,
                "MERGE (mr:MonitorRun {run_id: $run_id}) "
                "ON CREATE SET mr.date = $date, mr.version = $version, "
                "              mr.agent_version = $agent_version, mr.materials_count = $materials_count "
                "ON MATCH SET mr.date = $date, mr.version = $version, "
                "             mr.agent_version = $agent_version, mr.materials_count = $materials_count",
                {"run_id": run_id,
                 "date": datetime.utcnow().date().isoformat(),
                 "version": SEED_VERSION,
                 "agent_version": "maj-recon@bootstrap",
                 "materials_count": 0},
                dry_run, stats)
    # Wire UPDATED edges to every typed node
    for label in ("Source", "AcademicPaper", "Company", "Investor", "FundingRound", "Lawsuit", "Regulation"):
        await _exec(kg, graph_name,
                    f"MATCH (mr:MonitorRun {{run_id: $run_id}}), (n:{label}) "
                    "MERGE (mr)-[:UPDATED]->(n)",
                    {"run_id": run_id}, dry_run, stats)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

async def main(catalog_root: Path, graph_name: str, dry_run: bool) -> int:
    log.info("seed start: catalog=%s graph=%s dry_run=%s", catalog_root, graph_name, dry_run)

    # Parse the catalog up-front; even a dry run reports counts.
    sources_path = catalog_root / "00-index" / "sources.md"
    papers_path = catalog_root / "09-papers" / "MANIFEST.md"

    sources = parse_sources_md(sources_path)
    papers = parse_papers_manifest(papers_path)

    log.info("parsed: %d sources, %d papers (downloaded+paywalled)", len(sources), len(papers))
    log.info("structured records: %d companies, %d investors, %d rounds, %d lawsuits, %d regulations",
             len(COMPANIES), len(INVESTORS), len(FUNDING_ROUNDS), len(LAWSUITS), len(REGULATIONS))

    kg = KnowledgeGraphManager()
    if not dry_run and not kg.db:
        log.error("FalkorDB not connected. Set FALKORDB_ENABLED=true and ensure the server is reachable.")
        log.error("(connection params: host=%s port=%s)", kg.host, kg.port)
        return 2

    if not dry_run:
        kg._ensure_graph_schema(graph_name)

    stats = {"nodes_created": 0, "relationships_created": 0}

    # Sources first so other entities can attach :CITES edges to them.
    for s in sources:
        await merge_source(kg, graph_name, s, dry_run, stats)
    for p in papers:
        await merge_paper(kg, graph_name, p, dry_run, stats)
    for c in COMPANIES:
        await merge_company(kg, graph_name, c, dry_run, stats)
    for i in INVESTORS:
        await merge_investor(kg, graph_name, i, dry_run, stats)
    for fr in FUNDING_ROUNDS:
        await merge_funding_round(kg, graph_name, fr, dry_run, stats)
    for l in LAWSUITS:
        await merge_lawsuit(kg, graph_name, l, dry_run, stats)
    for r in REGULATIONS:
        await merge_regulation(kg, graph_name, r, dry_run, stats)

    run_id = f"bootstrap-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
    await merge_monitor_run_provenance(kg, graph_name, run_id, dry_run, stats)

    log.info("seed done. nodes_created=%d relationships_created=%d run_id=%s%s",
             stats["nodes_created"], stats["relationships_created"], run_id,
             " (dry-run, nothing written)" if dry_run else "")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bootstrap the Majiks research FalkorDB graph from the markdown catalog")
    ap.add_argument("--catalog-path", default=os.environ.get("CATALOG_PATH", DEFAULT_CATALOG))
    ap.add_argument("--graph-name", default=DEFAULT_GRAPH)
    ap.add_argument("--dry-run", action="store_true", help="parse and print stats; do not write")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    catalog_root = Path(args.catalog_path)
    if not catalog_root.exists():
        log.error("catalog path does not exist: %s", catalog_root)
        sys.exit(1)
    rc = asyncio.run(main(catalog_root, args.graph_name, args.dry_run))
    sys.exit(rc)
