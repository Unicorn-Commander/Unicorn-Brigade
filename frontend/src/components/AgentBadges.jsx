import { Coins, Cpu } from 'lucide-react';
import {
  AFFIL_META,
  affiliationOf,
  TIER_META,
  tierOf,
  paidToolInfo,
  paidToolSummary,
} from '../utils/agentClass';

/**
 * Badge that says how many of an agent's tools COST MONEY.
 *
 * It used to render a dollar glyph next to an integer — "$ 4" — which reads as
 * four dollars, and got asked about as if it were a bill. It never was: it is a
 * count of tools whose costTier is anything but free, and the agent may run
 * them a thousand times or never. So the number now carries the word "paid"
 * beside it, the glyph is coins rather than a currency sign, and the accessible
 * name spells the whole thing out. Renders nothing when nothing costs money.
 */
export function PaidToolsBadge({ agent, size = 'sm' }) {
  const { count } = paidToolInfo(agent);
  if (count <= 0) return null;
  const summary = paidToolSummary(agent);
  const xs = size === 'xs';
  return (
    <span
      title={summary}
      aria-label={summary}
      className={`inline-flex shrink-0 items-center gap-0.5 rounded-md bg-amber-500/15 font-semibold tabular-nums text-amber-200 ring-1 ring-amber-500/30 ${
        xs ? 'px-1 py-0.5 text-[9px]' : 'px-1.5 py-0.5 text-[10px]'
      }`}
    >
      <Coins aria-hidden="true" className={xs ? 'h-2.5 w-2.5' : 'h-3 w-3'} />
      {count} paid{xs ? '' : ` tool${count === 1 ? '' : 's'}`}
    </span>
  );
}

/** Who operates this agent — Employee / Contractor / 3rd-party / Frontier. */
export function AffiliationChip({ agent, size = 'sm' }) {
  const meta = AFFIL_META[affiliationOf(agent)];
  const xs = size === 'xs';
  return (
    <span
      title={`${meta.label} — who operates this agent`}
      className={`inline-flex shrink-0 items-center rounded-md border font-semibold uppercase tracking-wide ${meta.chip} ${meta.text} ${
        xs ? 'px-1 py-px text-[8px]' : 'px-1.5 py-0.5 text-[10px]'
      }`}
    >
      {meta.label}
    </span>
  );
}

/**
 * What powers this agent — Local / Frontier / Flexible.
 *
 * Carries a chip glyph because "Frontier" is a value on BOTH axes: an agent
 * operated by a frontier lab and running a frontier model rendered as two
 * near-identical chips reading "FRONTIER FRONTIER", which looks like a
 * duplicate rather than two different facts. The glyph says which one is the
 * model without spending the width to write the word.
 */
export function ModelTierChip({ agent, size = 'sm' }) {
  const meta = TIER_META[tierOf(agent)];
  const xs = size === 'xs';
  return (
    <span
      title={`${meta.label} model — ${agent?.model || 'unknown model'}`}
      className={`inline-flex shrink-0 items-center gap-0.5 rounded-md font-semibold uppercase tracking-wide ${meta.chip} ${
        xs ? 'px-1 py-px text-[8px]' : 'px-1.5 py-0.5 text-[10px]'
      }`}
    >
      <Cpu aria-hidden="true" className={xs ? 'h-2 w-2' : 'h-2.5 w-2.5'} />
      {meta.label}
    </span>
  );
}

export default PaidToolsBadge;
