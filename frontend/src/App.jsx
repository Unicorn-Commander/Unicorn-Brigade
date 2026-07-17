import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster, toast } from 'react-hot-toast';
import { useEffect, useState, lazy, Suspense } from 'react';
// Shell stays eager (rendered on every authenticated view); everything routable
// is lazy so the initial bundle is just the app frame, not all ~25 pages.
import Navigation from './components/Navigation';
import CommandPalette from './components/CommandPalette';
import useAuth from './hooks/useAuth';
import { Loader2 } from 'lucide-react';
import GettingStartedWizard from './components/GettingStartedWizard';
import ErrorBoundary from './components/ErrorBoundary';

// .catch() provides a fallback if WebGL module evaluation crashes.
const WebGLFallbackPage = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-900">
    <div className="text-center p-8">
      <p className="text-xl text-slate-300 font-medium mb-2">3D Visualization Unavailable</p>
      <p className="text-slate-500">This page requires WebGL support in your browser.</p>
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
const Settings = lazy(() => import('./pages/Settings'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const NotFound = lazy(() => import('./pages/NotFound'));
const ServerError = lazy(() => import('./pages/ServerError'));
// WebGL / Three.js-heavy pages (extra crash fallback).
const Orchestration = lazy(() => import('./pages/Orchestration').catch(() => ({ default: WebGLFallbackPage })));
const OrchestrationDemo = lazy(() => import('./pages/OrchestrationDemo').catch(() => ({ default: WebGLFallbackPage })));
const KnowledgeGraph = lazy(() => import('./pages/KnowledgeGraph').catch(() => ({ default: WebGLFallbackPage })));
const CommandCenter = lazy(() => import('./pages/CommandCenter'));

const queryClient = new QueryClient();

const LazyFallback = () => (
  <div className="min-h-screen flex items-center justify-center bg-slate-900">
    <div className="text-center">
      <Loader2 className="w-12 h-12 text-unicorn-400 animate-spin mx-auto mb-4" />
      <p className="text-slate-400">Loading...</p>
    </div>
  </div>
);

/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-unicorn-400 animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Loading Brigade...</p>
        </div>
      </div>
    );
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
  return (
    <div className="min-h-screen flex">
      <Navigation />
      <main className="flex-1 pt-16 lg:pt-0 lg:ml-64">
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

  useEffect(() => {
    const handleOffline = () => {
      toast.error('You are offline. Please check your internet connection.', {
        id: 'offline',
        duration: Infinity,
      });
    };

    const handleOnline = () => {
      toast.dismiss('offline');
      toast.success('You are back online!', { id: 'online' });
    };

    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);

    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <ErrorBoundary>
          <Suspense fallback={<LazyFallback />}>
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

            <Route path="/orchestration" element={
              <ProtectedRoute>
                <AppLayout>
                  <Suspense fallback={<LazyFallback />}>
                    <Orchestration />
                  </Suspense>
                </AppLayout>
              </ProtectedRoute>
            } />

            <Route path="/orchestration/demo" element={
              <ProtectedRoute>
                <AppLayout>
                  <Suspense fallback={<LazyFallback />}>
                    <OrchestrationDemo />
                  </Suspense>
                </AppLayout>
              </ProtectedRoute>
            } />

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

            <Route path="/settings" element={
              <ProtectedRoute>
                <AppLayout>
                  <Settings />
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

        <Toaster
          position="top-right"
          toastOptions={{
            className: 'glass',
            style: {
              background: 'rgba(15, 23, 42, 0.9)',
              color: '#e2e8f0',
              border: '1px solid rgba(100, 116, 139, 0.3)',
            },
          }}
        />
      </Router>
    </QueryClientProvider>
  );
}

export default App
