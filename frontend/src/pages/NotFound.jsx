import { Link } from 'react-router-dom';
import { ArrowLeft, Bot, Home, Server, Workflow } from 'lucide-react';
import { Button, Card } from '../components/ui';

const SUGGESTIONS = [
  { to: '/dashboard', icon: Home, title: 'Dashboard', text: 'The overview' },
  { to: '/library', icon: Bot, title: 'Agent Library', text: 'Browse and build agents' },
  { to: '/workflows', icon: Workflow, title: 'Workflows', text: 'Run multi-agent workflows' },
  { to: '/mcp-servers', icon: Server, title: 'MCP Servers', text: 'Tools your agents can use' },
];

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl text-center">
        <p aria-hidden="true" className="text-hero text-gradient">
          404
        </p>
        <h1 className="mt-2 text-title text-fg-strong">Page not found</h1>
        <p className="mx-auto mt-2 max-w-md text-body text-muted">That address doesn’t exist or has moved. The pages below are the usual places to start.</p>

        <Card className="mt-8 text-left">
          <p className="mb-3 text-micro font-semibold uppercase tracking-wider text-muted">Try these instead</p>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <li key={s.to}>
                <Card as={Link} to={s.to} variant="elevated" padding="sm" interactive className="flex h-full items-center gap-3">
                  <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-accent/10 text-accent">
                    <s.icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-body font-medium text-fg-strong">{s.title}</span>
                    <span className="block text-caption text-muted">{s.text}</span>
                  </span>
                </Card>
              </li>
            ))}
          </ul>
        </Card>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button variant="secondary" icon={ArrowLeft} onClick={() => window.history.back()}>
            Go back
          </Button>
          <Button as={Link} to="/dashboard" icon={Home}>
            Go to Dashboard
          </Button>
        </div>
      </div>
    </main>
  );
}
