// Canonical agent-classification vocabulary — the SAME two axes Stable renders,
// so one agent reads identically in both products.
//
//   Axis 1  AFFILIATION — who operates the agent (Employee / Contractor /
//           3rd-party / Frontier). Shown as a colored LEFT BORDER plus a chip.
//   Axis 2  MODEL TIER  — what powers it (Local / Frontier / Flexible).
//           Shown as a chip.
//
// Plus a paid-tool rollup, which is a COUNT of tools that cost money — never a
// dollar amount. See PaidToolsBadge for why the label matters.
//
// Ported from Stable's web/src/components/Agents/agentClass.ts. The colors are
// canonical: changing one side without the other reintroduces exactly the drift
// this shared vocabulary exists to prevent.

// ── Axis 1: AFFILIATION ────────────────────────────────────────────────────
// `chip` carries border+background only (same split Stable uses) so `text` can
// be applied independently on surfaces that want the label tinted.
export const AFFIL_META = {
  employee: {
    label: 'Employee',
    border: 'border-l-emerald-400',
    bar: 'bg-emerald-400',
    text: 'text-emerald-300',
    chip: 'border-emerald-400/30 bg-emerald-400/10',
  },
  contractor: {
    label: 'Contractor',
    border: 'border-l-amber-400',
    bar: 'bg-amber-400',
    text: 'text-amber-300',
    chip: 'border-amber-400/30 bg-amber-400/10',
  },
  third_party: {
    label: '3rd-party',
    border: 'border-l-rose-400',
    bar: 'bg-rose-400',
    text: 'text-rose-300',
    chip: 'border-rose-400/30 bg-rose-400/10',
  },
  frontier: {
    label: 'Frontier',
    border: 'border-l-violet-400',
    bar: 'bg-violet-400',
    text: 'text-violet-300',
    chip: 'border-violet-400/30 bg-violet-400/10',
  },
};

export const AFFILIATIONS = ['employee', 'contractor', 'third_party', 'frontier'];

/** Normalize whatever the roster carries into one of the four canonical values. */
export function affiliationOf(agent) {
  const a = String(agent?.affiliation || '')
    .trim()
    .toLowerCase();
  if (a === 'contractor') return 'contractor';
  if (a === 'third_party' || a === 'third-party' || a === '3rd_party' || a === '3rd-party') {
    return 'third_party';
  }
  if (a === 'frontier') return 'frontier';
  if (a === 'employee') return 'employee';
  // The roster also records the operating COMPANY as an affiliation
  // ("magic-unicorn"). That is an employee — we run them. Without this the two
  // agents carrying it fell through to the unstated branch below and were
  // classified by their model instead of by who operates them.
  if (a === 'magic-unicorn' || a === 'magic_unicorn' || a === 'magicunicorn') {
    return 'employee';
  }
  // Unstated: fall back to the model tier so the border still means something —
  // an agent on a frontier model reads as frontier, everything else as employee
  // (we run it).
  return tierOf(agent) === 'frontier' ? 'frontier' : 'employee';
}

/** Left-border class for an agent's affiliation. */
export function affiliationBorder(agent) {
  return AFFIL_META[affiliationOf(agent)].border;
}

// ── Axis 2: MODEL TIER ─────────────────────────────────────────────────────
export const TIER_META = {
  local: {
    label: 'Local',
    chip: 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30',
    dot: 'bg-emerald-400',
  },
  frontier: {
    label: 'Frontier',
    chip: 'bg-violet-500/10 text-violet-300 ring-1 ring-violet-500/30',
    dot: 'bg-violet-400',
  },
  flexible: {
    label: 'Flexible',
    chip: 'bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/30',
    dot: 'bg-cyan-400',
  },
};

export const TIERS = ['local', 'frontier', 'flexible'];

/**
 * Which lane runs this agent.
 *
 * Reads the model id, which for this roster is mostly an Ops-Center gateway
 * alias (`uc/chat-local-p40`) rather than a bare model name — so the test is on
 * the word "local" in the alias, not on a `local/` prefix. Family names are
 * matched with a LEADING boundary only: `\bqwen\b` fails on "qwen3.6-35b"
 * because a digit follows, which silently graded a local 35B as Frontier.
 */
export function tierOf(agent) {
  const m = String(agent?.model || '').toLowerCase();
  const name = String(agent?.displayName || agent?.name || '').toLowerCase();
  // A router/switch alias picks its lane per request — neither Local nor
  // Frontier is true of it, so it gets its own value rather than a wrong one.
  if (
    name === 'majik' ||
    agent?.id === 'majik' ||
    m.includes('switch') ||
    m.includes('auto') ||
    m.includes('router')
  ) {
    return 'flexible';
  }
  if (
    m.startsWith('local/') ||
    m.startsWith('ollama') ||
    /\blocal\b/.test(m) ||
    /\b(qwen|llama|gemma|mistral|phi|deepseek)/.test(m)
  ) {
    return 'local';
  }
  return 'frontier';
}

/** Chip classes for an agent's model tier. */
export function modelTierChip(agent) {
  return TIER_META[tierOf(agent)].chip;
}

/** Human label for an agent's model tier. */
export function modelTierLabel(agent) {
  return TIER_META[tierOf(agent)].label;
}

// ── Paid tools ─────────────────────────────────────────────────────────────
/**
 * How many of this agent's tools cost money, and which.
 *
 * `count` is a COUNT OF TOOLS, not an amount of money. Reads the server's
 * rollup first (`toolCostSummary.paid`), falling back to counting the
 * per-tool details whose costTier is anything but "free".
 */
export function paidToolInfo(agent) {
  const details = Array.isArray(agent?.toolDetails) ? agent.toolDetails : [];
  const paidNames = details
    .filter((t) => t && t.costTier && t.costTier !== 'free')
    .map((t) => t.displayName || t.name);
  const count = agent?.toolCostSummary?.paid ?? paidNames.length;
  return { count: count || 0, names: paidNames };
}

/**
 * The sentence the paid-tool badge means, spelled out. Used for the badge's
 * accessible name and tooltip so "4" can never be read as "$4.00".
 */
export function paidToolSummary(agent) {
  const { count, names } = paidToolInfo(agent);
  if (count <= 0) return '';
  const head = `${count} paid tool${count === 1 ? '' : 's'} (cost money to run)`;
  return names.length ? `${head}: ${names.join(', ')}` : head;
}

// ── Misc ───────────────────────────────────────────────────────────────────
export function prettyDomain(domain) {
  if (!domain) return 'General';
  return String(domain)
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** The line under an agent's name: their job, however the roster states it. */
export function roleLine(agent) {
  return agent?.title || agent?.rank || prettyDomain(agent?.domain);
}
