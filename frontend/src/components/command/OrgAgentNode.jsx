import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Star, ChevronDown, ChevronRight, Clock } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import { AffiliationChip, ModelTierChip, PaidToolsBadge } from '../AgentBadges';
import { StatusDot, statusMeta, Tooltip } from '../ui';
import { AFFIL_META, affiliationOf, TIER_META, tierOf, paidToolSummary, prettyDomain, roleLine } from '../../utils/agentClass';
import { ORG_NODE_W, ORG_NODE_H } from '../../hooks/useOrgLayout';
import { autonomyLine } from '../../utils/autonomy';

// Handles exist so xyflow can anchor edges; the chart draws no connectors.
const HANDLE = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0 };

const ARROW_TO_NAV = { ArrowLeft: 'prev', ArrowRight: 'next', ArrowUp: 'up', ArrowDown: 'down' };

/** Everything the node cannot fit, as one line for the tooltip and the accessible name. */
function detailLine(agent, { status, reason, subordinates, autonomy }) {
  const affil = AFFIL_META[affiliationOf(agent)];
  const tier = TIER_META[tierOf(agent)];
  const parts = [roleLine(agent)];
  if (agent.rank && agent.rank !== roleLine(agent)) parts.push(agent.rank);
  parts.push(prettyDomain(agent.domain));
  parts.push(`${affil.label} · ${tier.label} model${agent.model ? ` (${agent.model})` : ''}`);
  if (subordinates > 0) parts.push(`${subordinates} report${subordinates === 1 ? '' : 's'}`);
  const paid = paidToolSummary(agent);
  if (paid) parts.push(paid);
  if (autonomy?.total) parts.push(autonomyLine(autonomy));
  if (status === 'error') parts.push(`Needs attention: ${reason || 'the agent stopped without saying why'}`);
  else if (status !== 'idle') parts.push(statusMeta(status).label);
  return parts.filter(Boolean).join(' · ');
}

/**
 * One agent on the org chart: portrait, name, role, the two classification
 * chips, a live status dot — and, for a lead, the pill that folds its team.
 * Everything else (rank, domain, model, paid tools, the failure reason) lives
 * in the tooltip, which also doubles as the spoken description.
 *
 * data: { agent, isRoot, status, reason, subordinates, hiddenCount, collapsed,
 *         match, dim, autonomy: { total, failing, stale } | null,
 *         nav: { prev, next, up, down }, onOpen, onToggle, onAutonomy }
 *
 * An agent with jobs that run on its own wears a small clock badge on its
 * top edge (danger when one is failing, warn when one is stale); clicking it
 * opens the Command Center's Autonomous view on that agent's jobs.
 */
function OrgAgentNodeBase({ data }) {
  const { agent, isRoot, status = 'idle', reason, subordinates = 0, hiddenCount = 0, collapsed = false, match, dim, nav, autonomy } = data;
  const name = agent.displayName || agent.name;
  const affil = AFFIL_META[affiliationOf(agent)];
  const active = status !== 'idle';
  const detail = detailLine(agent, { status, reason, subordinates, autonomy });
  const autoTone = autonomy?.failing
    ? 'border-danger-fill bg-danger-fill text-white'
    : autonomy?.stale
      ? 'border-warn-fill bg-warn-fill text-on-warn'
      : 'border-border-strong bg-elevated text-muted hover:text-fg';

  const onKeyDown = (e) => {
    const dir = ARROW_TO_NAV[e.key];
    if (!dir || !nav?.[dir]) return;
    // Ids can hold dots, quotes or spaces (dogfood has `cpl.-colophon`): escape, never splice.
    const next = document.querySelector(`[data-org-node="${CSS.escape(nav[dir])}"] [data-org-open]`);
    if (next) {
      e.preventDefault();
      next.focus();
    }
  };

  return (
    <div
      data-org-node={agent.id}
      className={`relative transition-opacity duration-base ${dim ? 'opacity-40' : ''}`}
      style={{ width: ORG_NODE_W, height: ORG_NODE_H }}
    >
      <Handle type="target" position={Position.Top} id="top" style={HANDLE} />
      <Handle type="target" position={Position.Left} id="left" style={HANDLE} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={HANDLE} />

      <Tooltip content={detail} side="bottom">
        <button
          type="button"
          data-org-open
          onClick={() => data.onOpen?.(agent)}
          onKeyDown={onKeyDown}
          aria-label={`Open comms with ${name}. ${detail}`}
          className={[
            'flex h-full w-full items-center gap-2 rounded-card border border-l-4 px-2 text-left',
            'transition-[border-color,box-shadow] duration-fast ease-standard',
            'hover:border-border-strong hover:shadow-e2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
            affil.border,
            status === 'error'
              ? 'border-danger/60 bg-card shadow-e2'
              : active
                ? 'border-accent/60 bg-card shadow-e2'
                : isRoot
                  ? 'border-warn/50 bg-card'
                  : 'border-border bg-card/90',
            match ? 'ring-2 ring-accent' : '',
          ].join(' ')}
        >
          <span className="relative shrink-0">
            <AgentAvatar agent={agent} size={isRoot ? 44 : 40} rounded="rounded-full" status={status} />
            <StatusDot status={status} size="md" ring className="absolute -bottom-0.5 -right-0.5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1">
              <span className="truncate text-body font-semibold text-fg-strong">{name}</span>
              {isRoot && <Star aria-hidden="true" className="h-3 w-3 shrink-0 fill-current text-warn" />}
            </span>
            <span className={`block truncate text-caption ${status === 'error' ? 'font-medium text-danger' : 'text-muted'}`}>
              {status === 'error' ? 'Needs attention' : roleLine(agent)}
            </span>
            <span className="mt-1 flex items-center gap-1 overflow-hidden">
              <AffiliationChip agent={agent} size="xs" />
              <ModelTierChip agent={agent} size="xs" />
              <PaidToolsBadge agent={agent} size="xs" compact />
            </span>
          </span>
        </button>
      </Tooltip>

      {autonomy?.total > 0 && (
        <Tooltip content={autonomyLine(autonomy)}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              data.onAutonomy?.(agent.id);
            }}
            aria-label={`${name}: ${autonomyLine(autonomy).replace(/ · /g, ', ')}. Show them in Autonomous.`}
            className={`absolute -top-2.5 right-3 z-raised flex h-5 items-center gap-0.5 rounded-full border px-1.5 text-micro font-semibold tabular-nums shadow-e1 transition-[filter,color] duration-fast hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-3 [@media(pointer:coarse)]:after:content-[''] ${autoTone}`}
          >
            <Clock aria-hidden="true" className="h-3 w-3" />
            {autonomy.total}
          </button>
        </Tooltip>
      )}

      {subordinates > 0 && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            data.onToggle?.(agent.id);
          }}
          aria-expanded={!collapsed}
          aria-label={collapsed ? `Show the ${hiddenCount} agents under ${name}` : `Hide the agents under ${name}`}
          className="absolute -bottom-3 left-1/2 z-raised flex h-6 -translate-x-1/2 items-center gap-0.5 rounded-full border border-border bg-elevated px-1.5 text-micro font-semibold tabular-nums text-muted shadow-e1 transition-colors duration-fast hover:border-border-strong hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {collapsed ? <ChevronRight aria-hidden="true" className="h-3 w-3" /> : <ChevronDown aria-hidden="true" className="h-3 w-3" />}
          {collapsed ? hiddenCount : subordinates}
        </button>
      )}
    </div>
  );
}

export default memo(OrgAgentNodeBase);
