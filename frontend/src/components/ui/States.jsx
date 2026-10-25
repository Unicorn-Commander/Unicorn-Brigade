import { AlertTriangle, WifiOff, RefreshCw } from 'lucide-react';
import Button from './Button';

/**
 * The four states every surface must design: EMPTY, LOADING, ERROR, OFFLINE.
 * A screen is not done until all four exist. These are the shared renderers;
 * copy their copy style: say what is missing, then the next step.
 */

// ── Empty ────────────────────────────────────────────────────────────────────
/**
 *   <EmptyState
 *     icon={Bot}
 *     title="No agents yet"
 *     description="Build your first agent with Gunny, or import one from the library."
 *     action={<Button icon={Sparkles} onClick={…}>Build an agent</Button>}
 *     secondary={<Button variant="ghost">Read the guide</Button>}
 *   />
 * Use `compact` inside cards and panels.
 */
export function EmptyState({ icon: Icon, title, description, action, secondary, compact = false, className = '' }) {
  return (
    <div
      role="status"
      className={`flex flex-col items-center justify-center text-center ${
        compact ? 'gap-2 px-4 py-8' : 'gap-3 px-6 py-16'
      } ${className}`}
    >
      {Icon && (
        <span
          aria-hidden="true"
          className={`flex items-center justify-center rounded-pane border border-border bg-elevated/60 text-muted ${
            compact ? 'h-10 w-10' : 'h-14 w-14'
          }`}
        >
          <Icon className={compact ? 'h-5 w-5' : 'h-7 w-7'} />
        </span>
      )}
      <div className="max-w-md">
        <p className={`${compact ? 'text-body' : 'text-heading'} font-semibold text-fg-strong`}>{title}</p>
        {description && <p className={`mt-1 ${compact ? 'text-body-sm' : 'text-body'} text-muted`}>{description}</p>}
      </div>
      {(action || secondary) && (
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondary}
        </div>
      )}
    </div>
  );
}

// ── Error ────────────────────────────────────────────────────────────────────
/**
 *   <ErrorState title="Couldn’t load the roster" detail={humanize(err)} onRetry={reload} />
 * Human words only — never a raw exception. utils/errors.js humanize() turns an
 * ApiError into a sentence with a next step.
 */
export function ErrorState({ title = 'Something went wrong', detail, onRetry, retryLabel = 'Try again', compact = false, className = '' }) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center text-center ${
        compact ? 'gap-2 px-4 py-8' : 'gap-3 px-6 py-16'
      } ${className}`}
    >
      <span
        aria-hidden="true"
        className={`flex items-center justify-center rounded-pane border border-danger/30 bg-danger/10 text-danger ${
          compact ? 'h-10 w-10' : 'h-14 w-14'
        }`}
      >
        <AlertTriangle className={compact ? 'h-5 w-5' : 'h-7 w-7'} />
      </span>
      <div className="max-w-md">
        <p className={`${compact ? 'text-body' : 'text-heading'} font-semibold text-fg-strong`}>{title}</p>
        {detail && <p className={`mt-1 ${compact ? 'text-body-sm' : 'text-body'} text-muted`}>{detail}</p>}
      </div>
      {onRetry && (
        <Button variant="secondary" size={compact ? 'sm' : 'md'} icon={RefreshCw} onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}

// ── Offline ──────────────────────────────────────────────────────────────────
export function OfflineState({ onRetry, compact = false, className = '' }) {
  return (
    <div role="status" className={`flex flex-col items-center justify-center text-center ${compact ? 'gap-2 px-4 py-8' : 'gap-3 px-6 py-16'} ${className}`}>
      <span aria-hidden="true" className="flex h-12 w-12 items-center justify-center rounded-pane border border-border bg-elevated/60 text-muted">
        <WifiOff className="h-6 w-6" />
      </span>
      <div className="max-w-md">
        <p className="text-heading font-semibold text-fg-strong">You’re offline</p>
        <p className="mt-1 text-body text-muted">This view will refresh when the connection comes back.</p>
      </div>
      {onRetry && (
        <Button variant="secondary" icon={RefreshCw} onClick={onRetry}>
          Retry now
        </Button>
      )}
    </div>
  );
}

// ── Loading (skeletons) ──────────────────────────────────────────────────────
const Bone = ({ className = '' }) => <div className={`rounded-chip bg-elevated/80 ${className}`} />;

/**
 * Skeletons that match the shape of what is coming, so content lands with no
 * layout shift. Pick the variant that matches the surface:
 *   cards (grid of cards) · list (rows with an avatar) · table (rows/cols) ·
 *   stats (a KPI strip) · text (paragraph) · chart (a plot area)
 */
export function LoadingState({ variant = 'list', count, label = 'Loading', className = '' }) {
  const n = count ?? { cards: 6, list: 5, table: 6, stats: 4, text: 4, chart: 1 }[variant] ?? 4;
  const items = Array.from({ length: n });
  let body;
  if (variant === 'cards') {
    body = (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((_, i) => (
          <div key={i} className="rounded-card border border-border bg-card p-5">
            <div className="flex items-start gap-3">
              <Bone className="h-11 w-11 rounded-control" />
              <div className="flex-1 space-y-2 pt-0.5">
                <Bone className="h-4 w-2/3" />
                <Bone className="h-3 w-1/3" />
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <Bone className="h-3 w-full" />
              <Bone className="h-3 w-5/6" />
            </div>
          </div>
        ))}
      </div>
    );
  } else if (variant === 'table') {
    body = (
      <div className="overflow-hidden rounded-card border border-border bg-card">
        <div className="flex gap-6 border-b border-border px-4 py-3">
          {[1, 2, 3, 4].map((c) => (
            <Bone key={c} className="h-3 w-24" />
          ))}
        </div>
        {items.map((_, i) => (
          <div key={i} className="flex items-center gap-6 border-b border-border/60 px-4 py-3.5 last:border-b-0">
            <Bone className="h-3.5 w-40" />
            <Bone className="h-3.5 w-28" />
            <Bone className="h-3.5 w-20" />
            <Bone className="ml-auto h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    );
  } else if (variant === 'stats') {
    body = (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {items.map((_, i) => (
          <div key={i} className="rounded-card border border-border bg-card p-5">
            <Bone className="mb-5 h-8 w-8 rounded-control" />
            <Bone className="mb-2 h-7 w-20" />
            <Bone className="h-3 w-24" />
          </div>
        ))}
      </div>
    );
  } else if (variant === 'text') {
    body = (
      <div className="space-y-2">
        {items.map((_, i) => (
          <Bone key={i} className={`h-3.5 ${i === n - 1 ? 'w-2/3' : 'w-full'}`} />
        ))}
      </div>
    );
  } else if (variant === 'chart') {
    body = (
      <div className="rounded-card border border-border bg-card p-5">
        <Bone className="mb-4 h-4 w-40" />
        <div className="flex h-48 items-end gap-2">
          {[40, 65, 50, 80, 55, 70, 45, 90, 60, 75, 50, 85].map((h, i) => (
            <Bone key={i} className="flex-1" style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    );
  } else {
    body = (
      <div className="space-y-2">
        {items.map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-card border border-border bg-card px-4 py-3">
            <Bone className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Bone className="h-3.5 w-1/3" />
              <Bone className="h-3 w-1/2" />
            </div>
            <Bone className="h-7 w-20" />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div role="status" aria-busy="true" aria-label={label} className={`animate-pulse ${className}`}>
      {body}
      <span className="sr-only">{label}…</span>
    </div>
  );
}
