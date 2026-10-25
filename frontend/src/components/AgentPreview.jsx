import { Check, Cpu, FileText, RefreshCw, Sparkles, Wrench } from 'lucide-react';
import { prettyDomain } from '../utils/agentClass';
import { Button, Chip } from './ui';

// Weighted completeness: name, domain and model matter most; temperature
// always has a default so it counts as done.
export function previewProgress(p = {}) {
  let done = 20; // temperature default
  if (p.name || p.displayName) done += 20;
  if (p.domain) done += 20;
  if (p.model) done += 20;
  if (p.tools?.length) done += 10;
  if (p.capabilities?.length) done += 10;
  return done;
}

const statusLine = (p, progress) => {
  if (p.status === 'created') return 'Deployed. Opening the agent…';
  if (p.status === 'ready') return 'Spec complete — ready to deploy.';
  if (progress <= 20) return 'Tell Gunny what the agent is for.';
  if (progress < 60) return 'Learning the requirements…';
  if (progress < 100) return 'Filling in the spec card…';
  return 'Spec complete.';
};

function Slot({ label, value }) {
  const done = Boolean(value);
  return (
    <div className="flex items-center justify-between gap-3 rounded-control border border-border bg-surface/60 px-3 py-2">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="min-w-0 text-right">
        {done ? (
          <span className="inline-flex max-w-full items-center gap-1.5 text-body-sm font-medium text-fg-strong">
            <Check aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-ok" />
            <span className="truncate">{value}</span>
          </span>
        ) : (
          <Chip size="xs">Pending</Chip>
        )}
      </dd>
    </div>
  );
}

/**
 * AgentPreview — the spec card Gunny fills in as the conversation goes:
 * progress, the fields as they land, tools and capabilities as chips, and
 * the Create / Start over actions once the spec is complete. The caller
 * decides where it lives (a side panel on desktop, a Sheet on phones).
 */
export default function AgentPreview({ preview = {}, onConfirm, onReset }) {
  const progress = previewProgress(preview);
  const tools = Array.isArray(preview.tools) ? preview.tools : [];
  const caps = Array.isArray(preview.capabilities) ? preview.capabilities : [];
  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <h3 className="inline-flex items-center gap-2 text-lead font-semibold text-fg-strong">
            <Sparkles aria-hidden="true" className="h-4 w-4 text-accent" />
            Building agent
          </h3>
          <span className="text-caption tabular-nums text-muted">{progress}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-elevated" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Spec completeness">
          <div className="h-full rounded-full bg-accent-fill transition-[width] duration-slow ease-standard" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-1.5 text-caption text-muted">{statusLine(preview, progress)}</p>
      </div>

      <dl className="space-y-2">
        <Slot label="Name" value={preview.displayName || preview.name} />
        <Slot label="Domain" value={preview.domain ? prettyDomain(preview.domain) : null} />
        <Slot label="Model" value={preview.model} />
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-control border border-border bg-surface/60 px-3 py-2">
            <dt className="text-caption text-muted">Temperature</dt>
            <dd className="text-body-sm font-medium text-fg-strong tabular-nums">{Number(preview.temperature ?? 0.7).toFixed(1)}</dd>
          </div>
          <div className="rounded-control border border-border bg-surface/60 px-3 py-2">
            <dt className="text-caption text-muted">Max tokens</dt>
            <dd className="text-body-sm font-medium text-fg-strong tabular-nums">{Number(preview.maxTokens || 4096).toLocaleString()}</dd>
          </div>
        </div>
      </dl>

      <div className="rounded-control border border-border bg-surface/60 p-3">
        <p className="mb-1.5 inline-flex items-center gap-1.5 text-caption text-muted">
          <Wrench aria-hidden="true" className="h-3.5 w-3.5" />
          Tools
        </p>
        {tools.length ? (
          <ul className="flex flex-wrap gap-1" aria-label="Tools">
            {tools.map((t) => (
              <li key={typeof t === 'string' ? t : t?.name}>
                <Chip size="xs" tone="live">
                  {typeof t === 'string' ? t : t?.name}
                </Chip>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body-sm text-subtle">None yet</p>
        )}
      </div>

      <div className="rounded-control border border-border bg-surface/60 p-3">
        <p className="mb-1.5 inline-flex items-center gap-1.5 text-caption text-muted">
          <Cpu aria-hidden="true" className="h-3.5 w-3.5" />
          Capabilities
        </p>
        {caps.length ? (
          <ul className="flex flex-wrap gap-1" aria-label="Capabilities">
            {caps.map((c) => (
              <li key={c}>
                <Chip size="xs" tone="accent">
                  {c}
                </Chip>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body-sm text-subtle">None yet</p>
        )}
      </div>

      {preview.systemPrompt && (
        <div className="rounded-control border border-border bg-surface/60 p-3">
          <p className="mb-1.5 inline-flex items-center gap-1.5 text-caption text-muted">
            <FileText aria-hidden="true" className="h-3.5 w-3.5" />
            System prompt
          </p>
          <p className="line-clamp-3 text-body-sm text-fg">{preview.systemPrompt}</p>
        </div>
      )}

      {preview.status === 'ready' && (
        <div className="space-y-2 border-t border-border pt-4">
          <Button icon={Sparkles} className="w-full" onClick={onConfirm}>
            Create agent
          </Button>
          <Button variant="ghost" icon={RefreshCw} className="w-full" onClick={onReset}>
            Start over
          </Button>
        </div>
      )}
    </div>
  );
}
