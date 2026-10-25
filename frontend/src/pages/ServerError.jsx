import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, Home, RefreshCw } from 'lucide-react';
import { Button, Card } from '../components/ui';

const STEPS = ['Wait a moment and reload the page.', 'Check Monitoring for a service that is down.', 'If it keeps happening, tell an owner of your organization what you were doing.'];

export default function ServerError() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl text-center">
        <span aria-hidden="true" className="mx-auto flex h-14 w-14 items-center justify-center rounded-pane border border-danger/30 bg-danger/10 text-danger">
          <AlertTriangle className="h-7 w-7" />
        </span>
        <p aria-hidden="true" className="mt-4 text-hero text-fg-strong">
          500
        </p>
        <h1 className="mt-2 text-title text-fg-strong">Something went wrong on our side</h1>
        <p className="mx-auto mt-2 max-w-md text-body text-muted">The server hit a problem it couldn’t recover from. Nothing you did caused it, and nothing you had saved is lost.</p>

        <Card className="mt-8 text-left">
          <p className="mb-3 text-micro font-semibold uppercase tracking-wider text-muted">What you can do</p>
          <ol className="space-y-2">
            {STEPS.map((s, i) => (
              <li key={s} className="flex items-start gap-3 text-body-sm text-fg">
                <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-elevated font-mono text-caption text-muted">
                  {i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
        </Card>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button variant="secondary" icon={RefreshCw} onClick={() => window.location.reload()}>
            Reload page
          </Button>
          <Button as={Link} to="/monitoring" variant="secondary" icon={Activity}>
            Check Monitoring
          </Button>
          <Button as={Link} to="/dashboard" icon={Home}>
            Go to Dashboard
          </Button>
        </div>
      </div>
    </main>
  );
}
