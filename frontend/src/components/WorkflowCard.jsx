/**
 * WorkflowCard — one workflow template, in the grid or as a list row.
 *
 * The preview draws the real steps when the template carries them; the list
 * endpoint usually does not, so the card shows the three tiers it runs through
 * instead of an empty box. Stats are a tidy <dl>, not four tiles.
 */
import { Play, Eye, FileText, DollarSign, Search, Briefcase, Settings, Scale, Stethoscope, Fingerprint, Workflow, ChevronRight, Crown, Users, Hammer, PauseCircle } from 'lucide-react';
import MiniWorkflowDiagram from './MiniWorkflowDiagram';
import { Button, Card, Chip, Tooltip } from './ui';

export const DOMAIN_TAGS = ['research', 'finance', 'content', 'sales', 'devops', 'legal', 'medical', 'investigation'];
const DOMAIN_ICON = { research: Search, finance: DollarSign, content: FileText, sales: Briefcase, devops: Settings, legal: Scale, medical: Stethoscope, investigation: Fingerprint };

// The default preset is cost-optimized (local models for leads and workers);
// a real per-workflow estimate comes from POST /hierarchical/config/estimate-cost.
const DEFAULT_ESTIMATE = { estimate: '$0.02–0.05', note: 'Estimate for the cost-optimized preset: local models for team leads and workers.' };

export const counts = (w) => ({
  steps: w.step_count ?? w.stepCount ?? w.steps?.length ?? 0,
  checkpoints: w.checkpoint_count ?? w.checkpointCount ?? w.checkpoints?.length ?? 0,
  inputs: (w.required_inputs || w.requiredInputs || []).length,
  teamLeads: w.team_leads?.length ?? w.teamLeads?.length ?? w.team_lead_count ?? w.teamLeadCount ?? null,
});

export function complexityOf(w) {
  const { steps, checkpoints } = counts(w);
  if (steps <= 3 && checkpoints === 0) return { label: 'Simple', tone: 'ok' };
  if (steps <= 5 && checkpoints <= 1) return { label: 'Moderate', tone: 'info' };
  return { label: 'Complex', tone: 'warn' };
}

function StageStrip({ w }) {
  const { steps, checkpoints, teamLeads } = counts(w);
  const Arrow = () => <ChevronRight aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-subtle" />;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-4" aria-label={`${steps} steps across three tiers`}>
      <div className="flex flex-wrap items-center justify-center gap-1">
        <Chip size="xs" tone="accent" icon={Crown}>
          Orchestrator
        </Chip>
        <Arrow />
        <Chip size="xs" tone="info" icon={Users}>
          {teamLeads ? `${teamLeads} team lead${teamLeads === 1 ? '' : 's'}` : 'Team leads'}
        </Chip>
        <Arrow />
        <Chip size="xs" tone="ok" icon={Hammer}>
          Workers
        </Chip>
        {checkpoints > 0 && (
          <>
            <Arrow />
            <Chip size="xs" tone="warn" icon={PauseCircle}>
              {checkpoints} checkpoint{checkpoints === 1 ? '' : 's'}
            </Chip>
          </>
        )}
      </div>
      <p className="text-micro text-subtle">
        {steps} step{steps === 1 ? '' : 's'} · steps load with the details
      </p>
    </div>
  );
}

function Stats({ w, className = '' }) {
  const c = counts(w);
  const cost = w.estimated_cost ?? w.estimatedCost;
  const rows = [
    ['Inputs', c.inputs],
    ['Checkpoints', c.checkpoints],
    ['Team leads', c.teamLeads == null ? '—' : c.teamLeads],
  ];
  return (
    <dl className={`grid grid-cols-4 gap-2 ${className}`}>
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="truncate text-micro text-subtle">{label}</dt>
          <dd className="text-body-sm font-semibold tabular-nums text-fg">{value}</dd>
        </div>
      ))}
      <div className="min-w-0">
        <Tooltip content={cost != null ? 'Estimated by the engine for this workflow' : DEFAULT_ESTIMATE.note}>
          <dt className="truncate text-micro text-subtle underline decoration-dotted underline-offset-2">Est. cost</dt>
        </Tooltip>
        <dd className="text-body-sm font-semibold tabular-nums text-fg">{cost != null ? `$${Number(cost).toFixed(2)}` : DEFAULT_ESTIMATE.estimate}</dd>
      </div>
    </dl>
  );
}

export default function WorkflowCard({ workflow, onViewDetails, onExecute, layout = 'grid', busy = false }) {
  if (!workflow) return null;
  const tags = workflow.tags || [];
  const primaryDomain = tags.find((t) => DOMAIN_TAGS.includes(t));
  const DomainIcon = (primaryDomain && DOMAIN_ICON[primaryDomain]) || Workflow;
  const complexity = complexityOf(workflow);
  const { steps } = counts(workflow);
  const otherTags = tags.filter((t) => t !== primaryDomain);
  const hasSteps = Array.isArray(workflow.steps) && workflow.steps.length > 0;

  const title = (
    <div className="flex min-w-0 items-start gap-3">
      <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
        <DomainIcon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-body font-semibold text-fg-strong">{workflow.name}</h3>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <Chip size="xs">
            {steps} step{steps === 1 ? '' : 's'}
          </Chip>
          <Chip size="xs" tone={complexity.tone}>
            {complexity.label}
          </Chip>
          {primaryDomain && (
            <Chip size="xs" tone="accent" className="capitalize">
              {primaryDomain}
            </Chip>
          )}
        </div>
      </div>
    </div>
  );

  const actions = (
    <div className="flex items-center gap-2">
      <Button variant="secondary" size="sm" icon={Eye} onClick={() => onViewDetails(workflow)} className="flex-1">
        Details
      </Button>
      <Button size="sm" icon={Play} loading={busy} onClick={() => onExecute(workflow)} className="flex-1">
        Run
      </Button>
    </div>
  );

  if (layout === 'list') {
    return (
      <Card padding="sm" className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          {title}
          <p className="mt-2 line-clamp-2 text-body-sm text-muted">{workflow.description}</p>
        </div>
        <Stats w={workflow} className="sm:w-72" />
        <div className="sm:w-52">{actions}</div>
      </Card>
    );
  }

  return (
    <Card padding="none" className="flex h-full flex-col overflow-hidden">
      <div className="h-28 border-b border-border bg-surface/60">
        {hasSteps ? <MiniWorkflowDiagram workflow={workflow} height={112} /> : <StageStrip w={workflow} />}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        {title}
        <p className="line-clamp-2 text-body-sm text-muted">{workflow.description}</p>
        {otherTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {otherTags.slice(0, 3).map((t) => (
              <Chip key={t} size="xs">
                {t}
              </Chip>
            ))}
            {otherTags.length > 3 && <Chip size="xs">+{otherTags.length - 3}</Chip>}
          </div>
        )}
        <Stats w={workflow} className="mt-auto border-t border-border pt-3" />
        {actions}
      </div>
    </Card>
  );
}
