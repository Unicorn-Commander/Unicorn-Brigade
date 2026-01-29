import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { toast } from 'react-hot-toast';
import axios from 'axios';
import ToolCard from './ToolCard';
import ToolConfigModal from './ToolConfigModal';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

// Mock data for when API isn't ready
const mockTools = [
  {
    id: 'tool-1',
    name: 'Web Search',
    description: 'Search the web for information and retrieve results',
    type: 'search',
    schema: {
      rateLimit: { type: 'number', default: 100, label: 'Requests per minute' },
      timeout: { type: 'number', default: 30, label: 'Timeout (seconds)' }
    }
  },
  {
    id: 'tool-2',
    name: 'Database',
    description: 'Execute SQL queries against configured databases',
    type: 'data',
    schema: {
      connectionString: { type: 'string', default: '', label: 'Connection String' },
      readOnly: { type: 'boolean', default: true, label: 'Read Only' }
    }
  },
  {
    id: 'tool-3',
    name: 'Code Executor',
    description: 'Run Python code in a sandboxed environment',
    type: 'execution',
    schema: {
      maxRuntime: { type: 'number', default: 60, label: 'Max Runtime (seconds)' },
      allowNetworkAccess: { type: 'boolean', default: false, label: 'Allow Network Access' }
    }
  },
  {
    id: 'tool-4',
    name: 'File System',
    description: 'Read and write files in designated directories',
    type: 'storage',
    schema: {
      basePath: { type: 'string', default: '/data', label: 'Base Path' },
      readOnly: { type: 'boolean', default: false, label: 'Read Only' }
    }
  },
  {
    id: 'tool-5',
    name: 'API Client',
    description: 'Make HTTP requests to external APIs',
    type: 'integration',
    schema: {
      allowedDomains: { type: 'string', default: '*', label: 'Allowed Domains (comma-separated)' },
      rateLimit: { type: 'number', default: 100, label: 'Requests per minute' }
    }
  },
  {
    id: 'tool-6',
    name: 'Calculator',
    description: 'Perform mathematical calculations and expressions',
    type: 'utility',
    schema: {
      precision: { type: 'number', default: 10, label: 'Decimal Precision' }
    }
  },
  {
    id: 'tool-7',
    name: 'Email Sender',
    description: 'Send emails via configured SMTP server',
    type: 'integration',
    schema: {
      smtpHost: { type: 'string', default: '', label: 'SMTP Host' },
      smtpPort: { type: 'number', default: 587, label: 'SMTP Port' },
      fromAddress: { type: 'string', default: '', label: 'From Address' }
    }
  },
  {
    id: 'tool-8',
    name: 'Image Generator',
    description: 'Generate images using AI models',
    type: 'ai',
    schema: {
      model: { type: 'string', default: 'dall-e-3', label: 'AI Model' },
      maxImages: { type: 'number', default: 5, label: 'Max Images per Request' }
    }
  }
];

const ToolSelector = ({ agentId, assignedTools = [], onUpdate }) => {
  const [availableTools, setAvailableTools] = useState([]);
  const [assigned, setAssigned] = useState(assignedTools);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [configTool, setConfigTool] = useState(null);
  const [toolConfig, setToolConfig] = useState({});

  useEffect(() => {
    fetchAvailableTools();
  }, []);

  useEffect(() => {
    setAssigned(assignedTools);
  }, [assignedTools]);

  const fetchAvailableTools = async () => {
    setLoading(true);
    try {
      // Try to fetch from API, fall back to mock data
      const response = await axios.get(`${API_BASE}/tools`);
      const tools = Array.isArray(response.data) ? response.data : (response.data.tools || response.data);
      setAvailableTools(Array.isArray(tools) ? tools : mockTools);
    } catch (error) {
      console.log('API not ready, using mock data');
      setAvailableTools(mockTools);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (tool) => {
    try {
      // POST /agents/:agentId/tools
      await axios.post(`${API_BASE}/agents/${agentId}/tools`, {
        toolId: tool.id
      });

      setAssigned([...assigned, tool]);
      toast.success(`Added ${tool.name}`);
      if (onUpdate) onUpdate();
    } catch (error) {
      console.error('Failed to add tool:', error);
      toast.error('Failed to add tool');
    }
  };

  const handleRemove = async (tool) => {
    try {
      // DELETE /agents/:agentId/tools/:toolId
      await axios.delete(`${API_BASE}/agents/${agentId}/tools/${tool.id}`);

      setAssigned(assigned.filter(t => t.id !== tool.id));
      toast.success(`Removed ${tool.name}`);
      if (onUpdate) onUpdate();
    } catch (error) {
      console.error('Failed to remove tool:', error);
      toast.error('Failed to remove tool');
    }
  };

  const handleConfigure = (tool) => {
    // Load existing config if available
    const existingConfig = assigned.find(t => t.id === tool.id)?.config || {};
    setToolConfig(existingConfig);
    setConfigTool(tool);
  };

  const handleSaveConfig = async (config) => {
    try {
      // PATCH /agents/:agentId/tools/:toolId
      await axios.patch(`${API_BASE}/agents/${agentId}/tools/${configTool.id}`, {
        config
      });

      // Update local state
      setAssigned(assigned.map(t =>
        t.id === configTool.id ? { ...t, config } : t
      ));

      toast.success('Configuration saved');
      setConfigTool(null);
      setToolConfig({});
      if (onUpdate) onUpdate();
    } catch (error) {
      console.error('Failed to save config:', error);
      toast.error('Failed to save configuration');
    }
  };

  const filteredTools = availableTools.filter(t =>
    (t.name.toLowerCase().includes(search.toLowerCase()) ||
     t.description.toLowerCase().includes(search.toLowerCase())) &&
    !assigned.find(a => a.id === t.id)
  );

  return (
    <>
      <div className="grid grid-cols-2 gap-6">
        {/* Available Tools */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-lg">Available Tools</h3>
            <span className="text-sm text-slate-400">{filteredTools.length} tools</span>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="search"
              placeholder="Search tools..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
            />
          </div>

          {/* Tools List */}
          <div className="space-y-2 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
            {loading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
                <p className="text-slate-400 mt-2">Loading tools...</p>
              </div>
            ) : filteredTools.length > 0 ? (
              filteredTools.map(tool => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  action="add"
                  onAction={() => handleAdd(tool)}
                />
              ))
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-400">
                  {search ? 'No tools found matching your search' : 'All tools have been assigned'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Assigned Tools */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-lg">Assigned Tools</h3>
            <span className="text-sm text-slate-400">{assigned.length} assigned</span>
          </div>

          {/* Placeholder for search alignment */}
          <div className="h-10"></div>

          {/* Tools List */}
          <div className="space-y-2 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
            {assigned.length > 0 ? (
              assigned.map(tool => (
                <ToolCard
                  key={tool.id}
                  tool={tool}
                  action="remove"
                  onAction={() => handleRemove(tool)}
                  onConfigure={() => handleConfigure(tool)}
                />
              ))
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-400">No tools assigned yet</p>
                <p className="text-sm text-slate-500 mt-1">Add tools from the left panel</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Configuration Modal */}
      {configTool && (
        <ToolConfigModal
          tool={configTool}
          config={toolConfig}
          onSave={handleSaveConfig}
          onClose={() => {
            setConfigTool(null);
            setToolConfig({});
          }}
        />
      )}
    </>
  );
};

export default ToolSelector;
