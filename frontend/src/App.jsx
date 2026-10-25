import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { useEffect, useState, lazy, Suspense } from 'react';
// Shell stays eager (rendered on every authenticated view); everything routable
// is lazy so the initial bundle is just the app frame, not all ~25 pages.
import Navigation from './components/Navigation';
import CommandPalette from './components/CommandPalette';
import PaymentRequiredModal from './components/billing/PaymentRequiredModal';
import useAuth from './hooks/useAuth';
import GettingStartedWizard from './components/GettingStartedWizard';
import ErrorBoundary from './components/ErrorBoundary';
import { TooltipHost } from './components/ui/Tooltip';
import { LoadingState, OfflineState, Page } from './components/ui';
import notify from './utils/notify';

// .catch() provides a fallback if WebGL module evaluation crashes.
const WebGLFallbackPage = () => (
  <div className="flex min-h-screen items-center justify-center bg-bg">
    <div className="p-8 text-center">
      <p className="mb-2 text-heading text-fg-strong">3D visualization unavailable</p>
      <p className="text-body text-muted">This page needs WebGL, which your browser has turned off.</p>
    </div>
  </div>
);

// Route-level code splitting — each page is its own chunk, fetched on demand.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AgentChat = lazy(() => import('./pages/AgentChat'));
const AgentBuilderChat = lazy(() => import('./pages/AgentBuilderChat'));
const AgentLibrary = lazy(() => import('./pages/AgentLibrary'));
const AgentDetail = lazy(() => import('./pages/AgentDetail'));
const Conversations = lazy(() => import('./pages/Conversations'));
const ToolLibrary = lazy(() => import('./pages/ToolLibrary'));
const MCPServers = lazy(() => import('./pages/MCPServers'));
const LangflowFlows = lazy(() => import('./pages/LangflowFlows'));
const Workflows = lazy(() => import('./pages/Workflows'));
const ApiDocs = lazy(() => import('./pages/ApiDocs'));
const MCPDocs = lazy(() => import('./pages/MCPDocs'));
const CodeAttribution = lazy(() => import('./pages/CodeAttribution'));
const Monitoring = lazy(() => import('./pages/Monitoring'));
const RalphMonitor = lazy(() => import('./pages/RalphMonitor'));
const ScheduledRuns = lazy(() => import('./pages/ScheduledRuns'));
const Organization = lazy(() => import('./pages/Organization'));
const Settings = lazy(() => import('./pages/Settings'));
const Billing = lazy(() => import('./pages/Billing'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const NotFound = lazy(() => import('./pages/NotFound'));
const ServerError = lazy(() => import('./pages/ServerError'));
// WebGL / Three.js-heavy pages (extra crash fallback).
const KnowledgeGraph = lazy(() => import('./pages/KnowledgeGraph').catch(() => ({ default: WebGLFallbackPage })));
const CommandCenter = lazy(() => import('./pages/CommandCenter'));

const queryClient = new QueryClient();

/**
 * Shell skeleton — what a lazy page (or the auth check) shows while it loads:
 * the sidebar and header blocks at their final sizes, then a stats strip and
 * cards. The real page lands in the same frame, so nothing jumps.
 */
const LazyFallback = ({ shell = false }) => {
  const page = (
    <Page>
      <div className="mb-5 flex items-end justify-between gap-3">
        <LoadingState variant="text" count={2} label="Loading page" className="w-full max-w-sm" />
        <div aria-hidden="true" className="h-9 w-28 shrink-0 animate-pulse rounded-control bg-elevated/80" />
      </div>
      <LoadingState variant="stats" label="Loading page" />
      <div className="mt-5">
        <LoadingState variant="cards" count={3} label="Loading page" />
      </div>
    </Page>
  );
  if (!shell) return page;
  return (
    <div className="flex min-h-screen">
      <div aria-hidden="true" className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-surface/80 lg:block" />
      <div aria-hidden="true" className="fixed inset-x-0 top-0 h-14 border-b border-border bg-surface/90 lg:hidden" />
      <main className="min-w-0 flex-1 pt-14 lg:ml-64 lg:pt-0">{page}</main>
    </div>
  );
};

/** Online/offline as a state of the shell, not a toast. */
function useOffline() {
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  useEffect(() => {
    const off = () => setOffline(true);
    const on = () => {
      setOffline(false);
      notify.success('Back online');
    };
    window.addEventListener('offline', off);
    window.addEventListener('online', on);
    return () => {
      window.removeEventListener('offline', off);
      window.removeEventListener('online', on);
    };
  }, []);
  return offline;
}

/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LazyFallback shell />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

/**
 * App Layout with Navigation
 * Only shown for authenticated routes
 */
function AppLayout({ children }) {
  const offline = useOffline();
  return (
    <div className="flex min-h-screen">
      <Navigation />
      <main id="main" className="min-w-0 flex-1 pt-14 lg:ml-64 lg:pt-0">
        {offline && (
          <div className="border-b border-warn/30 bg-warn/10">
            <OfflineState compact />
          </div>
        )}
        {children}
      </main>
    </div>
  );
}

function App() {
  const [showWizard, setShowWizard] = useState(false);
  // Gate onboarding on auth so the wizard never fires over /login or /register.
  const { isAuthenticated } = useAuth();

  // AuthProvider (in main.jsx) handles the initial session check via loadUser().

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    const hasCompletedWizard = localStorage.getItem('wizard-completed');
    if (!hasCompletedWizard) {
      const timer = setTimeout(() => setShowWizard(true), 500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [isAuthenticated]);

  // The sidebar's "Getting started" button (and the palette) re-open the tour
  // in place — no localStorage reset, no reload.
  useEffect(() => {
    const reopen = () => setShowWizard(true);
    window.addEventListener('brigade:getting-started', reopen);
    return () => window.removeEventListener('brigade:getting-started', reopen);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <ErrorBoundary>
          <Suspense fallback={<LazyFallback shell />}>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            {/* Protected Routes */}
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <AppLayout>
                  <Dashboard />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/chat" element={
              <ProtectedRoute>
                <AppLayout>
                  <AgentChat />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/conversations" element={
              <ProtectedRoute>
                <AppLayout>
                  <Conversations />
                </AppLayout>
              </ProtectedRoute>
            } />

            {/* Orchestration folded into the Command Center (Missions view), 2026-10-24. */}
            <Route path="/orchestration" element={<Navigate to="/command?view=missions" replace />} />

            <Route path="/command" element={
              <ProtectedRoute>
                <AppLayout>
                  <Suspense fallback={<LazyFallback />}>
                    <CommandCenter />
                  </Suspense>
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/knowledge" element={
              <ProtectedRoute>
                <AppLayout>
                  <Suspense fallback={<LazyFallback />}>
                    <KnowledgeGraph />
                  </Suspense>
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/library" element={
              <ProtectedRoute>
                <AppLayout>
                  <AgentLibrary />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/builder-chat" element={
              <ProtectedRoute>
                <AppLayout>
                  <AgentBuilderChat />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/agent/:id" element={
              <ProtectedRoute>
                <AppLayout>
                  <AgentDetail />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/tools" element={
              <ProtectedRoute>
                <AppLayout>
                  <ToolLibrary />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/mcp-servers" element={
              <ProtectedRoute>
                <AppLayout>
                  <MCPServers />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/langflow" element={
              <ProtectedRoute>
                <AppLayout>
                  <LangflowFlows />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/workflows" element={
              <ProtectedRoute>
                <AppLayout>
                  <Workflows />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/ralph-monitor" element={
              <ProtectedRoute>
                <AppLayout>
                  <RalphMonitor />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/docs" element={
              <ProtectedRoute>
                <AppLayout>
                  <ApiDocs />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/mcp-docs" element={
              <ProtectedRoute>
                <AppLayout>
                  <MCPDocs />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/code-attribution" element={
              <ProtectedRoute>
                <AppLayout>
                  <CodeAttribution />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/monitoring" element={
              <ProtectedRoute>
                <AppLayout>
                  <Monitoring />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/scheduled-runs" element={
              <ProtectedRoute>
                <AppLayout>
                  <ScheduledRuns />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/organization" element={
              <ProtectedRoute>
                <AppLayout>
                  <Organization />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/settings" element={
              <ProtectedRoute>
                <AppLayout>
                  <Settings />
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/billing" element={
              <ProtectedRoute>
                <AppLayout>
                  <Billing />
                </AppLayout>
              </ProtectedRoute>
            } />

            {/* Root redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />

            {/* Error routes */}
            <Route path="/500" element={<ServerError />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
          </Suspense>
        </ErrorBoundary>

        {isAuthenticated && showWizard && (
          <GettingStartedWizard onClose={() => setShowWizard(false)} />
        )}

        <CommandPalette />

        {/* BR-3.7: root-level 402 → upgrade-path modal (listens for brigade:payment-required) */}
        <PaymentRequiredModal />

        {/* One toaster, one tooltip host — both themed by the token layer (index.css). */}
        <Toaster
          position="bottom-right"
          gutter={8}
          containerClassName="ub-toaster"
          toastOptions={{
            className: 'ub-toast',
            duration: 4000,
            success: { className: 'ub-toast ub-toast-ok', iconTheme: { primary: 'hsl(var(--ok))', secondary: 'hsl(var(--overlay))' } },
            error: { className: 'ub-toast ub-toast-danger', duration: 6000, iconTheme: { primary: 'hsl(var(--danger))', secondary: 'hsl(var(--overlay))' } },
            loading: { className: 'ub-toast' },
          }}
        />
        <TooltipHost />
      </Router>
    </QueryClientProvider>
  );
}

export default App
