import { Component } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AlertTriangle, RefreshCw, RotateCw, Home, Copy } from 'lucide-react';
import { Button, Card, IconButton } from './ui';
import notify from '../utils/notify';

/**
 * ErrorBoundary — when a page throws, say so in human words and give three ways
 * out (try again, reload, dashboard) plus "Copy details" for support. The raw
 * error and component stack are never shown on screen outside DEV; they are
 * logged and copied. Navigating to another route resets the boundary.
 */
class Boundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null, errorCount: 0 };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', { error, errorInfo, componentStack: errorInfo?.componentStack });
    this.setState((prev) => ({ errorInfo, errorCount: prev.errorCount + 1 }));
  }

  componentDidUpdate(prevProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) this.reset();
  }

  reset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  reload = () => {
    window.location.reload();
  };

  copyDetails = async () => {
    const { error, errorInfo } = this.state;
    const text = [
      'Unicorn Brigade — page error',
      `URL: ${window.location.href}`,
      `Time: ${new Date().toISOString()}`,
      '',
      String(error?.stack || error || 'Unknown error'),
      '',
      'Component stack:',
      errorInfo?.componentStack || '(none)',
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      notify.success('Details copied — paste them into a support message');
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    const { error, errorInfo, errorCount } = this.state;
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-4">
        <Card className="w-full max-w-lg">
          <div role="alert" className="flex items-start gap-4">
            <span aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-pane border border-danger/30 bg-danger/10 text-danger">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <div className="min-w-0 flex-1">
              <h1 className="text-heading text-fg-strong">Something broke on this page — not your data</h1>
              <p className="mt-1 text-body text-muted">
                The rest of Brigade is fine. Try again, reload, or go back to the dashboard. If it keeps happening,
                copy the details and send them to support.
              </p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button icon={RefreshCw} onClick={this.reset}>
              Try again
            </Button>
            <Button variant="secondary" icon={RotateCw} onClick={this.reload}>
              Reload
            </Button>
            <Button variant="outline" as={Link} to="/dashboard" icon={Home}>
              Dashboard
            </Button>
            <span className="ml-auto">
              <IconButton icon={Copy} label="Copy details for support" variant="secondary" onClick={this.copyDetails} />
            </span>
          </div>

          {errorCount > 2 && (
            <p className="mt-4 rounded-control border border-warn/30 bg-warn/10 p-3 text-body-sm text-warn">
              This page has failed {errorCount} times in a row. Reloading usually clears it; if not, copy the details.
            </p>
          )}

          {import.meta.env.DEV && error && (
            <details className="mt-4 rounded-control border border-border bg-surface p-3">
              <summary className="cursor-pointer text-body-sm font-medium text-muted hover:text-fg">Error details (development only)</summary>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-caption text-muted">{String(error.stack || error)}</pre>
              {errorInfo?.componentStack && (
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-caption text-muted">{errorInfo.componentStack}</pre>
              )}
            </details>
          )}
        </Card>
      </div>
    );
  }
}

/** Mount inside the Router: a route change resets a caught error. */
export default function ErrorBoundary({ children }) {
  const location = useLocation();
  return <Boundary resetKey={location.pathname}>{children}</Boundary>;
}
