import { Activity, MessageSquare, Pencil, Trash2, Wrench } from 'lucide-react';
import AgentAvatar from './AgentAvatar';
import { AffiliationChip, ModelTierChip, PaidToolsBadge } from './AgentBadges';
import { roleLine } from '../utils/agentClass';
import { Button, Card, Chip, IconButton, StatusDot } from './ui';

// Lifecycle status is a fact about the record, not what the agent is doing
// right now (that is `status` → StatusDot). Active is the default and stays
// silent; anything else is worth a chip.
const LIFECYCLE = {
  draft: { tone: 'warn', label: 'Draft' },
  inactive: { tone: 'neutral', label: 'Inactive' },
  archived: { tone: 'neutral', label: 'Archived' },
  busy: { tone: 'live', label: 'Busy' },
};

/** Tool names as the API states them: rich toolDetails first, then the id list. */
export function agentToolNames(agent) {
  const details = Array.isArray(agent?.toolDetails) ? agent.toolDetails : [];
  if (details.length) return details.map((t) => t.displayName || t.name).filter(Boolean);
  const tools = Array.isArray(agent?.tools) ? agent.tools : Array.isArray(agent?.agentTools) ? agent.agentTools : [];
  return tools.map((t) => (typeof t === 'string' ? t : t?.tool?.name || t?.name)).filter(Boolean);
}

/**
 * AgentCard — one agent in the library, as a grid tile or a list row.
 *
 * The portrait is the one face component (AgentAvatar); classification comes
 * from AgentBadges so the card reads the same as the org chart and Stable.
 * Counts are shown only when the API states them: tools always (it is the
 * agent's own list), invocations only when `_count.messages` is a real number.
 *
 *   <AgentCard agent={a} onOpen={…} onChat={…} onEdit={…} onDelete={…} variant="grid" />
 */
export default function AgentCard({ agent, variant = 'grid', status, onOpen, onClick, onChat, onEdit, onDelete }) {
  const open = onOpen || onClick;
  const name = agent.displayName || agent.name;
  const tools = agentToolNames(agent);
  const invocations = Number(agent?._count?.messages) > 0 ? Number(agent._count.messages) : null;
  const life = agent.status && agent.status !== 'active' ? LIFECYCLE[agent.status] || { tone: 'neutral', label: agent.status } : null;
  const actions = (
    <>
      {onChat && (
        <Button variant="ghost" size="sm" icon={MessageSquare} onClick={onChat} aria-label={`Open chat with ${name}`}>
          Chat
        </Button>
      )}
      {onEdit && <IconButton icon={Pencil} label={`Edit ${name}`} size="sm" onClick={onEdit} />}
      {onDelete && <IconButton icon={Trash2} label={`Delete ${name}`} size="sm" onClick={onDelete} />}
    </>
  );

  if (variant === 'list') {
    return (
      <Card padding="none" className="flex items-center gap-2 px-2 py-1.5 sm:px-3">
        <button
          type="button"
          onClick={open}
          className="flex min-h-touch min-w-0 flex-1 items-center gap-3 rounded-control px-1 text-left transition-colors duration-fast hover:bg-elevated/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="relative shrink-0">
            <AgentAvatar agent={agent} size={36} rounded="rounded-control" status={status} />
            {status && <StatusDot status={status} ring className="absolute -bottom-0.5 -right-0.5" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-body font-semibold text-fg-strong">{name}</span>
            <span className="block truncate text-caption text-muted">
              {agent.rank ? `${agent.rank} · ` : ''}
              {roleLine(agent)}
            </span>
          </span>
          <span className="hidden items-center gap-1 md:flex">
            <AffiliationChip agent={agent} size="xs" />
            <ModelTierChip agent={agent} size="xs" />
            <PaidToolsBadge agent={agent} size="xs" />
          </span>
          <span className="hidden shrink-0 items-center gap-1 text-caption text-muted lg:inline-flex">
            <Wrench aria-hidden="true" className="h-3 w-3" />
            {tools.length}
          </span>
          {life && (
            <Chip tone={life.tone} size="xs" dot>
              {life.label}
            </Chip>
          )}
        </button>
        <span className="flex shrink-0 items-center gap-0.5">{actions}</span>
      </Card>
    );
  }

  return (
    <Card padding="none" interactive className="flex h-full flex-col">
      <button
        type="button"
        onClick={open}
        className="flex-1 rounded-t-card p-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        <div className="flex items-start gap-4">
          <span className="relative shrink-0">
            <AgentAvatar agent={agent} size={48} rounded="rounded-control" status={status} />
            {status && <StatusDot status={status} ring className="absolute -bottom-0.5 -right-0.5" />}
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-lead font-semibold text-fg-strong">{name}</h3>
            <p className="truncate text-body-sm text-muted">{roleLine(agent)}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <AffiliationChip agent={agent} size="xs" />
          <ModelTierChip agent={agent} size="xs" />
          <PaidToolsBadge agent={agent} size="xs" />
          {life && (
            <Chip tone={life.tone} size="xs" dot>
              {life.label}
            </Chip>
          )}
        </div>
        <dl className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted">
          <div className="inline-flex items-center gap-1">
            <Wrench aria-hidden="true" className="h-3 w-3" />
            <dt className="sr-only">Tools</dt>
            <dd>
              {tools.length} tool{tools.length === 1 ? '' : 's'}
            </dd>
          </div>
          {invocations != null && (
            <div className="inline-flex items-center gap-1">
              <Activity aria-hidden="true" className="h-3 w-3" />
              <dt className="sr-only">Invocations</dt>
              <dd className="tabular-nums">{invocations.toLocaleString()} invocations</dd>
            </div>
          )}
          {agent.rank && (
            <div>
              <dt className="sr-only">Rank</dt>
              <dd>{agent.rank}</dd>
            </div>
          )}
        </dl>
      </button>
      {(onChat || onEdit || onDelete) && (
        <div className="flex items-center gap-0.5 border-t border-border px-3 py-2">
          {onChat ? actions : <span className="ml-auto flex items-center gap-0.5">{actions}</span>}
        </div>
      )}
    </Card>
  );
}
