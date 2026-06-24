// Canonical agent-classification helpers — kept in sync with the Stable product.
// Three signals surfaced on an agent node:
//   1. affiliation  → a colored left border (employee/contractor/third_party/frontier)
//   2. model tier   → Local vs Frontier, derived from the model id prefix
//   3. paid tools   → an amber money badge when any tool costs > free

// EXACT canonical color map (must match Stable).
const AFFILIATION_BORDER = {
  employee: 'border-l-emerald-400',
  contractor: 'border-l-amber-400',
  third_party: 'border-l-rose-400',
  frontier: 'border-l-violet-400',
};

export function affiliationBorder(affiliation) {
  return AFFILIATION_BORDER[affiliation] || 'border-l-slate-500';
}

// Derive a coarse model tier from the model id.
export function modelTier(model) {
  const m = (model || '').toLowerCase();
  if (m.startsWith('local/') || m.startsWith('uc/')) return 'Local';
  if (
    m.startsWith('anthropic/') ||
    m.includes('claude') ||
    m.startsWith('openai/') ||
    m.includes('gpt') ||
    m.startsWith('google/') ||
    m.includes('gemini')
  ) {
    return 'Frontier';
  }
  return 'Local';
}

// Subtle pill classes for the model tier chip.
export function modelTierChip(tier) {
  return tier === 'Frontier'
    ? 'bg-violet-500/15 text-violet-200'
    : 'bg-emerald-500/15 text-emerald-200';
}

// Paid-tool rollup. Reads toolCostSummary first, falls back to toolDetails.
export function paidToolInfo(agent) {
  const details = Array.isArray(agent?.toolDetails) ? agent.toolDetails : [];
  const paidNames = details
    .filter((t) => t && t.costTier && t.costTier !== 'free')
    .map((t) => t.displayName || t.name);
  const count = agent?.toolCostSummary?.paid ?? paidNames.length;
  return { count: count || 0, names: paidNames };
}
