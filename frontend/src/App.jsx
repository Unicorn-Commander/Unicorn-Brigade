import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import Dashboard from './pages/Dashboard';
import AgentBuilderChat from './pages/AgentBuilderChat';
import AgentLibrary from './pages/AgentLibrary';
import AgentDetail from './pages/AgentDetail';
import ToolLibrary from './pages/ToolLibrary';
import ApiDocs from './pages/ApiDocs';
import Monitoring from './pages/Monitoring';
import Settings from './pages/Settings';
import Navigation from './components/Navigation';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen flex">
          <Navigation />
          <main className="flex-1 ml-64">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/library" element={<AgentLibrary />} />
              <Route path="/builder-chat" element={<AgentBuilderChat />} />
              <Route path="/agent/:id" element={<AgentDetail />} />
              <Route path="/tools" element={<ToolLibrary />} />
              <Route path="/docs" element={<ApiDocs />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>

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
