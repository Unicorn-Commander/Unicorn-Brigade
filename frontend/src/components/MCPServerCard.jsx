import { Eye, Play, Settings2, Square } from 'lucide-react';
import McpServerIcon from '../utils/mcpIcons';
import { RoleGate } from './auth';
import { Button, Card, Chip, Tooltip } from './ui';

const STATUS = {
  running: { tone: 'ok', label: 'Running', pulse: true },
  stopped: { tone: 'neutral', label: 'Stopped', pulse: false },
  error: { tone: 'danger', label: 'Error', pulse: false },
};

/**
 * MCPServerCard — one registered server as the list endpoint describes it
 * (name, display_name, description, capabilities, transport, enabled,
 * running). Command, args and env vars live on the detail endpoint and are
 * shown in the Manage panel. The page owns status, errors and busy state.
 *
 *   <MCPServerCard server={s} status="running" reason={…} busy={false}
 *                  onStart={…} onStop={…} onViewTools={…} onManage={…} />
 */
export default function MCPServerCard({ server, status = 'stopped', reason, busy = false, onStart, onStop, onViewTools, onManage }) {
  const s = STATUS[status] || STATUS.stopped;
  const running = status === 'running';
  const declared = Array.isArray(server.capabilities) ? server.capabilities.length : 0;
  const title = server.display_name || server.name;

  return (
    <Card className="flex h-full flex-col">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
          <McpServerIcon name={server.name} className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-body font-semibold text-fg-strong">{title}</h3>
          <p className="truncate font-mono text-caption text-muted">{server.name}</p>
        </div>
        <Tooltip content={status === 'error' && reason ? reason : undefined}>
          <Chip tone={s.tone} size="xs" dot pulse={s.pulse && !busy}>
            {busy ? 'Working…' : s.label}
          </Chip>
        </Tooltip>
      </div>

      {server.description && <p className="mt-3 line-clamp-2 text-body-sm text-muted">{server.description}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-caption text-muted">
        {server.transport && (
          <Chip size="xs" tone="info" uppercase>
            {server.transport}
          </Chip>
        )}
        <span>
          {declared} declared tool{declared === 1 ? '' : 's'}
        </span>
        {server.enabled === false && (
          <Chip size="xs" tone="warn">
            Disabled in registry
          </Chip>
        )}
      </div>

      {status === 'error' && reason && (
        <p role="alert" className="mt-2 text-caption text-danger">
          {reason}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-4">
        {/* Start/Stop and Manage hit admin-only routes (require_admin); hide
            them from everyone else so there are no dead controls. Viewing the
            tool list is read-only. */}
        <RoleGate role="admin" showUpgradePrompt={false}>
          {running ? (
            <Button variant="secondary" size="sm" icon={Square} loading={busy} onClick={() => onStop?.(server)} aria-label={`Stop ${title}`}>
              Stop
            </Button>
          ) : (
            <Button variant="secondary" size="sm" icon={Play} loading={busy} onClick={() => onStart?.(server)} aria-label={`Start ${title}`} disabled={server.enabled === false}>
              Start
            </Button>
          )}
        </RoleGate>
        <Button variant="ghost" size="sm" icon={Eye} onClick={() => onViewTools?.(server)} aria-label={`Tools of ${title}`}>
          Tools
        </Button>
        {onManage && (
          <RoleGate role="admin" showUpgradePrompt={false}>
            <Button variant="ghost" size="sm" icon={Settings2} onClick={() => onManage(server)} aria-label={`Manage ${title}`} className="ml-auto">
              Manage
            </Button>
          </RoleGate>
        )}
      </div>
    </Card>
  );
}
