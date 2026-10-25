import { Plus, Wrench, X } from 'lucide-react';
import { Button, Chip, IconButton } from './ui';

// Same tone-per-type rule as the Tool Library.
const TYPE_TONE = { MCP: 'accent', Python: 'info' };

/**
 * ToolCard — one tool row inside a picker: name, type, description and a
 * single action (add or remove). Used by ToolSelector.
 */
export default function ToolCard({ tool, action = 'add', onAction, busy = false }) {
  const add = action === 'add';
  const name = tool.name || tool.displayName || tool.id;
  return (
    <div className="flex items-start gap-3 rounded-control border border-border bg-surface/60 p-3 transition-colors duration-fast hover:border-border-strong">
      <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-elevated text-lead">
        {tool.icon || <Wrench className="h-4 w-4 text-muted" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <h4 className="truncate text-body font-medium text-fg-strong">{name}</h4>
          {tool.type && (
            <Chip size="xs" tone={TYPE_TONE[tool.type] || 'neutral'} uppercase>
              {tool.type}
            </Chip>
          )}
        </div>
        {tool.description && <p className="mt-0.5 line-clamp-2 text-body-sm text-muted">{tool.description}</p>}
      </div>
      {add ? (
        <Button size="sm" variant="secondary" icon={Plus} loading={busy} onClick={onAction} aria-label={`Add ${name}`}>
          Add
        </Button>
      ) : (
        <IconButton icon={X} label={`Remove ${name}`} size="sm" disabled={busy} onClick={onAction} />
      )}
    </div>
  );
}
