import { Coins, Cpu } from 'lucide-react';
import { Chip, Tooltip } from './ui';
import { AFFIL_META, affiliationOf, TIER_META, tierOf, paidToolInfo, paidToolSummary } from '../utils/agentClass';

// Chip geometry (mirrors ui/Chip) with the canonical classification hues from
// utils/agentClass — those hues are shared verbatim with Stable, so they stay
// the classes they are. 11px is the floor: xs is text-micro, never smaller.
const BASE = 'inline-flex shrink-0 items-center whitespace-nowrap rounded-chip border font-semibold leading-none';
const SIZE = {
  xs: 'h-[18px] gap-1 px-1.5 text-micro',
  sm: 'h-[22px] gap-1.5 px-2 text-caption',
};
const ICON = { xs: 'h-3 w-3', sm: 'h-3.5 w-3.5' };

/**
 * Badge that says how many of an agent's tools COST MONEY.
 *
 * It used to render a dollar glyph next to an integer — "$ 4" — which reads as
 * four dollars. It never was: it is a count of tools whose costTier is anything
 * but free. The word "paid" sits beside the number, the glyph is coins rather
 * than a currency sign, and the tooltip + screen-reader text spell it out.
 * Renders nothing when nothing costs money. `compact` shows just the count.
 */
export function PaidToolsBadge({ agent, size = 'sm', compact = false }) {
  const { count } = paidToolInfo(agent);
  if (count <= 0) return null;
  const summary = paidToolSummary(agent);
  return (
    <Tooltip content={summary}>
      <Chip tone="warn" size={size === 'xs' ? 'xs' : 'sm'} icon={Coins} className="tabular-nums">
        {count}
        {!compact && (size === 'xs' ? ' paid' : ` paid tool${count === 1 ? '' : 's'}`)}
        <span className="sr-only"> {compact ? summary : '(cost money to run)'}</span>
      </Chip>
    </Tooltip>
  );
}

/** Who operates this agent — Employee / Contractor / 3rd-party / Frontier. */
export function AffiliationChip({ agent, size = 'sm' }) {
  const meta = AFFIL_META[affiliationOf(agent)];
  return (
    <Tooltip content={`${meta.label} — who operates this agent`}>
      <span className={`${BASE} ${SIZE[size] || SIZE.sm} ${meta.chip} ${meta.text}`}>{meta.label}</span>
    </Tooltip>
  );
}

/**
 * What powers this agent — Local / Frontier / Flexible.
 *
 * Carries a chip glyph because "Frontier" is a value on BOTH axes: an agent
 * operated by a frontier lab and running a frontier model would otherwise read
 * "Frontier Frontier". The glyph says which one is the model.
 */
export function ModelTierChip({ agent, size = 'sm' }) {
  const meta = TIER_META[tierOf(agent)];
  return (
    <Tooltip content={`${meta.label} model — ${agent?.model || 'unknown model'}`}>
      <span className={`${BASE} ${SIZE[size] || SIZE.sm} border-transparent ${meta.chip}`}>
        <Cpu aria-hidden="true" className={ICON[size] || ICON.sm} />
        {meta.label}
      </span>
    </Tooltip>
  );
}

export default PaidToolsBadge;
