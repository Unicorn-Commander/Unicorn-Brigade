import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import AgentChat from './pages/AgentChat';
import AgentBuilderChat from './pages/AgentBuilderChat';
import AgentLibrary from './pages/AgentLibrary';
import AgentDetail from './pages/AgentDetail';
import Conversations from './pages/Conversations';
import Orchestration from './pages/Orchestration';
import ToolLibrary from './pages/ToolLibrary';
import ApiDocs from './pages/ApiDocs';
import Monitoring from './pages/Monitoring';
import Settings from './pages/Settings';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Navigation from './components/Navigation';
import CommandPalette from './components/CommandPalette';
import useAuth from './hooks/useAuth';
import { Loader2 } from 'lucide-react';

const queryClient = new QueryClient();

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
          <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
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
      <main className="flex-1 ml-64">
        {children}
      </main>
    </div>
  );
}

function App() {
  const { loadUser } = useAuth();

  // Load user authentication state on app start
  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
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
                <Orchestration />
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

          <Route path="/docs" element={
            <ProtectedRoute>
              <AppLayout>
                <ApiDocs />
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

          <Route path="/settings" element={
            <ProtectedRoute>
              <AppLayout>
                <Settings />
              </AppLayout>
            </ProtectedRoute>
          } />

          {/* Root redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Catch all - redirect to dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>

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
