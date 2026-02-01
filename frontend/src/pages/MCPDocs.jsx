import { useState } from 'react';
import {
  Book,
  Code,
  Copy,
  Server,
  Zap,
  Package,
  GitBranch,
  Terminal,
  CheckCircle,
  ExternalLink,
  FileCode,
  Layers,
  Search,
  ChevronDown,
  ChevronRight,
  HelpCircle
} from 'lucide-react';
import { toast } from 'react-hot-toast';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1').replace(/\/api\/v1$/, '').replace(/\/api$/, '');

const MCPDocs = () => {
  const [expandedSection, setExpandedSection] = useState('what-is-mcp');
  const [selectedPhase, setSelectedPhase] = useState('baseline');

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  // MCP Server phases data
  const serverPhases = {
    baseline: {
      name: 'Baseline Servers',
      count: 10,
      servers: [
        { name: 'GitHub', tools: 17, capabilities: 'Repository management, PRs, issues, code search' },
        { name: 'Playwright', tools: 12, capabilities: 'Browser automation via accessibility tree' },
        { name: 'Slack', tools: 6, capabilities: 'Channel/message management, search' },
        { name: 'PostgreSQL', tools: 4, capabilities: 'Database queries, schema inspection' },
        { name: 'Filesystem', tools: 6, capabilities: 'File operations, read/write/search' },
        { name: 'Memory', tools: 4, capabilities: 'Persistent key-value storage' },
        { name: 'HTTP Fetch', tools: 1, capabilities: 'External API calls (GET, POST, PUT, DELETE)' },
        { name: 'Brave Search', tools: 2, capabilities: 'Web and local search' },
        { name: 'Google Drive', tools: 4, capabilities: 'Document access and search' },
        { name: 'Puppeteer', tools: 5, capabilities: 'Browser control (alternative to Playwright)' }
      ]
    },
    phase1: {
      name: 'Phase 1 - Business Operations',
      count: 4,
      servers: [
        { name: 'Stripe', tools: 29, capabilities: 'Payments, subscriptions, customers, invoices, refunds' },
        { name: 'Linear', tools: 24, capabilities: 'Issue tracking, projects, teams, workflows, sprints' },
        { name: 'Git', tools: 20, capabilities: 'Local repository operations, commits, branches, history' },
        { name: 'Notion', tools: 15, capabilities: 'Workspace, pages, databases, tasks, wiki' }
      ]
    },
    phase2: {
      name: 'Phase 2 - Cloud Infrastructure',
      count: 4,
      servers: [
        { name: 'Airtable', tools: 16, capabilities: 'Flexible database/spreadsheet hybrid' },
        { name: 'Vercel', tools: 22, capabilities: 'Deployment automation, serverless functions' },
        { name: 'Cloudflare', tools: 25, capabilities: 'Edge computing, Workers, KV, R2, DNS' },
        { name: 'Supabase', tools: 20, capabilities: 'PostgreSQL, auth, storage, real-time' }
      ]
    },
    phase3: {
      name: 'Phase 3 - Data & Communications',
      count: 4,
      servers: [
        { name: 'MongoDB', tools: 18, capabilities: 'NoSQL database, document operations' },
        { name: 'Twilio', tools: 21, capabilities: 'SMS, voice, WhatsApp, email, verification' },
        { name: 'Sentry', tools: 14, capabilities: 'Error tracking, performance monitoring' },
        { name: 'HubSpot', tools: 28, capabilities: 'CRM, marketing automation, sales pipeline' }
      ]
    }
  };

  // Calculate totals
  const totalServers = Object.values(serverPhases).reduce((sum, phase) => sum + phase.count, 0);
  const totalTools = Object.values(serverPhases).reduce((sum, phase) =>
    sum + phase.servers.reduce((toolSum, server) => toolSum + server.tools, 0), 0
  );

  const categories = [
    'Developer Tools', 'Data & Databases', 'Communication', 'Cloud Infrastructure',
    'Payments & Commerce', 'Project Management', 'Monitoring & Observability',
    'AI & ML Platforms', 'Enterprise & Productivity', 'Emerging & Specialized'
  ];

  const apiEndpoints = [
    {
      method: 'GET',
      path: '/api/v1/mcp/registry/servers',
      description: 'List all registered MCP servers',
      params: []
    },
    {
      method: 'GET',
      path: '/api/v1/mcp/registry/servers/running',
      description: 'List currently running servers',
      params: []
    },
    {
      method: 'GET',
      path: '/api/v1/mcp/registry/servers/{name}',
      description: 'Get server details',
      params: [{ name: 'name', type: 'string', description: 'Server name' }]
    },
    {
      method: 'POST',
      path: '/api/v1/mcp/registry/servers/{name}/start',
      description: 'Start an MCP server',
      params: [{ name: 'name', type: 'string', description: 'Server name' }]
    },
    {
      method: 'POST',
      path: '/api/v1/mcp/registry/servers/{name}/stop',
      description: 'Stop a running server',
      params: [{ name: 'name', type: 'string', description: 'Server name' }]
    },
    {
      method: 'POST',
      path: '/api/v1/mcp/registry/tools/call',
      description: 'Invoke a tool on an MCP server',
      params: [],
      body: {
        server: { type: 'string', required: true, description: 'Server name' },
        tool: { type: 'string', required: true, description: 'Tool name' },
        arguments: { type: 'object', required: false, description: 'Tool arguments' }
      }
    }
  ];

  const faqs = [
    {
      question: "What's the difference between built-in tools and MCP tools?",
      answer: "Built-in tools are directly integrated into the platform and always available. MCP tools are provided by external servers that can be started/stopped as needed. MCP tools offer more flexibility and can be updated independently."
    },
    {
      question: "How do I know which MCP server to use?",
      answer: "Browse the server phases above to see capabilities. For example, use Stripe for payments, Linear for project management, or GitHub for repository operations. Each server's description lists its primary use cases."
    },
    {
      question: "Can I run multiple servers at once?",
      answer: "Yes! The registry supports running as many servers as needed simultaneously. Servers are independent and can run concurrently without conflicts."
    },
    {
      question: "What happens if a server fails?",
      answer: "Failed servers can be restarted via the API. The registry tracks server state and logs errors. Agents will receive error responses if they attempt to use tools from a stopped server."
    },
    {
      question: "How do I update MCP servers?",
      answer: "Servers are npm packages (e.g., @stripe/agent-toolkit). Update by restarting the server - npx automatically uses the latest version unless pinned."
    },
    {
      question: "Can I create private MCP servers?",
      answer: "Yes! You can build custom servers using the MCP SDK and register them in the registry. See the 'Building Custom Servers' section below."
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Hero Section */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-8">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center space-x-3 mb-4">
              <Server className="w-12 h-12 text-purple-400" />
              <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                MCP Server Ecosystem
              </h1>
            </div>
            <p className="text-xl text-slate-300 mb-2">
              {totalServers} pre-configured servers, ~{totalTools} tools across {Object.keys(serverPhases).length} phases
            </p>
            <p className="text-slate-400">
              Model Context Protocol enables seamless agent tool integration
            </p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-6 bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/30 rounded-lg text-center">
              <div className="text-3xl font-bold text-purple-400 mb-1">{totalServers}</div>
              <div className="text-sm text-slate-400">Total Servers</div>
            </div>
            <div className="p-6 bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30 rounded-lg text-center">
              <div className="text-3xl font-bold text-blue-400 mb-1">~{totalTools}</div>
              <div className="text-sm text-slate-400">Available Tools</div>
            </div>
            <div className="p-6 bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border border-emerald-500/30 rounded-lg text-center">
              <div className="text-3xl font-bold text-emerald-400 mb-1">{categories.length}</div>
              <div className="text-sm text-slate-400">Categories</div>
            </div>
            <div className="p-6 bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/30 rounded-lg text-center">
              <div className="text-3xl font-bold text-orange-400 mb-1">{Object.keys(serverPhases).length}</div>
              <div className="text-sm text-slate-400">Integration Phases</div>
            </div>
          </div>
        </div>

        {/* What is MCP? */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <button
            onClick={() => toggleSection('what-is-mcp')}
            className="w-full flex items-center justify-between mb-4"
          >
            <div className="flex items-center space-x-3">
              <Book className="w-6 h-6 text-purple-400" />
              <h2 className="text-2xl font-bold text-white">What is MCP?</h2>
            </div>
            {expandedSection === 'what-is-mcp' ? (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-slate-400" />
            )}
          </button>

          {expandedSection === 'what-is-mcp' && (
            <div className="space-y-4 text-slate-300">
              <p className="leading-relaxed">
                <strong className="text-purple-400">Model Context Protocol (MCP)</strong> is an open standard that enables AI agents to securely connect with external tools and data sources. Think of it as a universal plug-and-play system for AI capabilities.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                <div className="p-4 bg-slate-800/50 rounded-lg">
                  <Zap className="w-8 h-8 text-emerald-400 mb-3" />
                  <h3 className="font-semibold text-white mb-2">Standardized Protocol</h3>
                  <p className="text-sm text-slate-400">
                    One protocol for all integrations. No custom code for each service.
                  </p>
                </div>
                <div className="p-4 bg-slate-800/50 rounded-lg">
                  <Package className="w-8 h-8 text-blue-400 mb-3" />
                  <h3 className="font-semibold text-white mb-2">Plug-and-Play Servers</h3>
                  <p className="text-sm text-slate-400">
                    Install servers with npm, configure with API keys, and start using tools.
                  </p>
                </div>
                <div className="p-4 bg-slate-800/50 rounded-lg">
                  <Layers className="w-8 h-8 text-purple-400 mb-3" />
                  <h3 className="font-semibold text-white mb-2">Community Ecosystem</h3>
                  <p className="text-sm text-slate-400">
                    600+ community servers available. Build custom servers with the SDK.
                  </p>
                </div>
              </div>

              <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <p className="text-sm text-blue-300">
                  <strong>How it works:</strong> MCP servers run as separate processes and communicate with agents via JSON-RPC. Agents discover available tools and invoke them as needed during conversation.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Available Servers */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <Server className="w-6 h-6 text-purple-400" />
              <h2 className="text-2xl font-bold text-white">Available Servers</h2>
            </div>
            <a
              href="/mcp-servers"
              className="flex items-center space-x-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 rounded-lg text-white text-sm font-medium transition-colors"
            >
              <span>Browse All Servers</span>
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>

          {/* Phase Tabs */}
          <div className="flex space-x-2 mb-6 overflow-x-auto">
            {Object.entries(serverPhases).map(([key, phase]) => (
              <button
                key={key}
                onClick={() => setSelectedPhase(key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                  selectedPhase === key
                    ? 'bg-purple-500 text-white'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {phase.name} ({phase.count})
              </button>
            ))}
          </div>

          {/* Server List */}
          <div className="space-y-3">
            {serverPhases[selectedPhase].servers.map((server, idx) => (
              <div key={idx} className="p-4 bg-slate-800/50 rounded-lg hover:bg-slate-800 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-lg font-semibold text-white">{server.name}</h3>
                      <span className="px-2 py-0.5 bg-purple-500/20 border border-purple-500/30 rounded text-xs text-purple-400">
                        {server.tools} tools
                      </span>
                    </div>
                    <p className="text-sm text-slate-400">{server.capabilities}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 p-4 bg-slate-800/50 rounded-lg">
            <p className="text-sm text-slate-400">
              <strong className="text-white">Total in this phase:</strong> {serverPhases[selectedPhase].count} servers, {serverPhases[selectedPhase].servers.reduce((sum, s) => sum + s.tools, 0)} tools
            </p>
          </div>
        </div>

        {/* How to Use MCP Servers */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-6">
            <Terminal className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-bold text-white">How to Use MCP Servers</h2>
          </div>

          <div className="space-y-6">
            {/* Step 1 */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-purple-500/20 border border-purple-500/30 rounded-full">
                  <span className="text-sm font-bold text-purple-400">1</span>
                </div>
                <h3 className="text-lg font-semibold text-white">Discover Servers</h3>
              </div>
              <p className="text-slate-400 mb-3">List all available MCP servers in the registry:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`curl -X GET "${API_BASE}/api/v1/mcp/registry/servers" \\
  -H "X-API-Key: YOUR_API_KEY"`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`curl -X GET "${API_BASE}/api/v1/mcp/registry/servers" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                </pre>
              </div>
            </div>

            {/* Step 2 */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-purple-500/20 border border-purple-500/30 rounded-full">
                  <span className="text-sm font-bold text-purple-400">2</span>
                </div>
                <h3 className="text-lg font-semibold text-white">Configure Environment</h3>
              </div>
              <p className="text-slate-400 mb-3">Add required API keys to your .env file:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`# Stripe (Phase 1)
STRIPE_API_KEY=sk_test_000000000000000000000000

# Linear (Phase 1)
LINEAR_API_KEY=lin_api_...

# Notion (Phase 1)
NOTION_API_KEY=secret_...`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`# Stripe (Phase 1)
STRIPE_API_KEY=sk_test_000000000000000000000000

# Linear (Phase 1)
LINEAR_API_KEY=lin_api_...

# Notion (Phase 1)
NOTION_API_KEY=secret_...`}
                </pre>
              </div>
            </div>

            {/* Step 3 */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-purple-500/20 border border-purple-500/30 rounded-full">
                  <span className="text-sm font-bold text-purple-400">3</span>
                </div>
                <h3 className="text-lg font-semibold text-white">Start Server</h3>
              </div>
              <p className="text-slate-400 mb-3">Start an MCP server:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`curl -X POST "${API_BASE}/api/v1/mcp/registry/servers/stripe/start" \\
  -H "X-API-Key: YOUR_API_KEY"`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`curl -X POST "${API_BASE}/api/v1/mcp/registry/servers/stripe/start" \\
  -H "X-API-Key: YOUR_API_KEY"`}
                </pre>
              </div>
            </div>

            {/* Step 4 */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-purple-500/20 border border-purple-500/30 rounded-full">
                  <span className="text-sm font-bold text-purple-400">4</span>
                </div>
                <h3 className="text-lg font-semibold text-white">Assign Tools to Agents</h3>
              </div>
              <p className="text-slate-400 mb-3">Update agent configuration to include MCP tools:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`{
  "name": "payment-agent",
  "tools": [
    "mcp:stripe:create_payment_intent",
    "mcp:stripe:create_customer",
    "mcp:stripe:list_invoices"
  ]
}`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`{
  "name": "payment-agent",
  "tools": [
    "mcp:stripe:create_payment_intent",
    "mcp:stripe:create_customer",
    "mcp:stripe:list_invoices"
  ]
}`}
                </pre>
              </div>
            </div>

            {/* Step 5 */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <div className="flex items-center justify-center w-8 h-8 bg-purple-500/20 border border-purple-500/30 rounded-full">
                  <span className="text-sm font-bold text-purple-400">5</span>
                </div>
                <h3 className="text-lg font-semibold text-white">Invoke Tools</h3>
              </div>
              <p className="text-slate-400 mb-3">Agents automatically invoke tools during execution:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`curl -X POST "${API_BASE}/api/v1/mcp/registry/tools/call" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "server": "stripe",
    "tool": "create_payment_intent",
    "arguments": {
      "amount": 2000,
      "currency": "usd"
    }
  }'`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`curl -X POST "${API_BASE}/api/v1/mcp/registry/tools/call" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "server": "stripe",
    "tool": "create_payment_intent",
    "arguments": {
      "amount": 2000,
      "currency": "usd"
    }
  }'`}
                </pre>
              </div>
            </div>
          </div>
        </div>

        {/* Building Custom MCP Servers */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-6">
            <FileCode className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-bold text-white">Building Custom MCP Servers</h2>
          </div>

          <div className="space-y-6">
            {/* Option 1: NPM Package */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-3">
                <Package className="w-5 h-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-white">Option 1: NPM Package</h3>
              </div>
              <p className="text-slate-400 mb-3">Create a standalone MCP server using the official SDK:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`npm install @modelcontextprotocol/sdk

// server.js
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-custom-server",
  version: "1.0.0",
}, {
  capabilities: {
    tools: {}
  }
});

// Define tools
server.setRequestHandler("tools/list", async () => ({
  tools: [{
    name: "my_tool",
    description: "Does something cool",
    inputSchema: {
      type: "object",
      properties: {
        input: { type: "string" }
      }
    }
  }]
}));

server.setRequestHandler("tools/call", async (request) => {
  if (request.params.name === "my_tool") {
    return {
      content: [{
        type: "text",
        text: \`Result: \${request.params.arguments.input}\`
      }]
    };
  }
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`npm install @modelcontextprotocol/sdk

// server.js
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-custom-server",
  version: "1.0.0",
}, {
  capabilities: {
    tools: {}
  }
});

// Define tools
server.setRequestHandler("tools/list", async () => ({
  tools: [{
    name: "my_tool",
    description: "Does something cool",
    inputSchema: {
      type: "object",
      properties: {
        input: { type: "string" }
      }
    }
  }]
}));

server.setRequestHandler("tools/call", async (request) => {
  if (request.params.name === "my_tool") {
    return {
      content: [{
        type: "text",
        text: \`Result: \${request.params.arguments.input}\`
      }]
    };
  }
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);`}
                </pre>
              </div>
            </div>

            {/* Option 2: Local Server */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-3">
                <Server className="w-5 h-5 text-blue-400" />
                <h3 className="text-lg font-semibold text-white">Option 2: HTTP Server</h3>
              </div>
              <p className="text-slate-400 mb-3">Create an HTTP-based MCP server (Python example):</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ToolCall(BaseModel):
    name: str
    arguments: dict

@app.get("/mcp/tools")
async def list_tools():
    return {
        "tools": [{
            "name": "my_tool",
            "description": "Does something cool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        }]
    }

@app.post("/mcp/tools/call")
async def call_tool(request: ToolCall):
    if request.name == "my_tool":
        result = f"Result: {request.arguments['input']}"
        return {"content": [{"type": "text", "text": result}]}

    return {"error": "Unknown tool"}

# Run with: uvicorn server:app --port 8080`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ToolCall(BaseModel):
    name: str
    arguments: dict

@app.get("/mcp/tools")
async def list_tools():
    return {
        "tools": [{
            "name": "my_tool",
            "description": "Does something cool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                }
            }
        }]
    }

@app.post("/mcp/tools/call")
async def call_tool(request: ToolCall):
    if request.name == "my_tool":
        result = f"Result: {request.arguments['input']}"
        return {"content": [{"type": "text", "text": result}]}

    return {"error": "Unknown tool"}

# Run with: uvicorn server:app --port 8080`}
                </pre>
              </div>
            </div>

            {/* Option 3: Fork Existing */}
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-3">
                <GitBranch className="w-5 h-5 text-purple-400" />
                <h3 className="text-lg font-semibold text-white">Option 3: Fork Existing Server</h3>
              </div>
              <p className="text-slate-400 mb-3">Start from an existing MCP server and customize it:</p>
              <div className="bg-slate-900/50 rounded-lg p-4 font-mono text-sm relative">
                <button
                  onClick={() => copyToClipboard(`# Clone an official MCP server
git clone https://github.com/modelcontextprotocol/servers
cd servers/src/filesystem

# Modify to add your custom logic
# Update package.json with your name

# Publish or use locally
npm link
npx my-custom-server`)}
                  className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                >
                  <Copy className="w-4 h-4 text-slate-400" />
                </button>
                <pre className="text-slate-300 overflow-x-auto pr-12">
{`# Clone an official MCP server
git clone https://github.com/modelcontextprotocol/servers
cd servers/src/filesystem

# Modify to add your custom logic
# Update package.json with your name

# Publish or use locally
npm link
npx my-custom-server`}
                </pre>
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <p className="text-sm text-blue-300">
              <strong>Documentation:</strong> Visit <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-200">modelcontextprotocol.io</a> for complete SDK documentation and examples.
            </p>
          </div>
        </div>

        {/* Finding New MCP Servers */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-6">
            <Search className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-bold text-white">Finding New MCP Servers</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">NPM Search</h3>
              <p className="text-sm text-slate-400 mb-3">Search for MCP servers on npm:</p>
              <div className="bg-slate-900/50 rounded-lg p-3 font-mono text-sm">
                <code className="text-slate-300">npm search @modelcontextprotocol</code>
              </div>
            </div>

            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">GitHub Search</h3>
              <p className="text-sm text-slate-400 mb-3">Find community servers on GitHub:</p>
              <div className="bg-slate-900/50 rounded-lg p-3 font-mono text-sm">
                <code className="text-slate-300">topic:mcp-server</code>
              </div>
            </div>

            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Official Registry</h3>
              <p className="text-sm text-slate-400 mb-3">Browse the official MCP registry:</p>
              <a
                href="https://registry.modelcontextprotocol.io"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 text-purple-400 hover:text-purple-300 text-sm"
              >
                <span>registry.modelcontextprotocol.io</span>
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>

            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Community Resources</h3>
              <p className="text-sm text-slate-400 mb-3">MCP servers repository:</p>
              <a
                href="https://github.com/modelcontextprotocol/servers"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 text-purple-400 hover:text-purple-300 text-sm"
              >
                <span>modelcontextprotocol/servers</span>
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          </div>
        </div>

        {/* API Reference */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-6">
            <Code className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-bold text-white">API Reference</h2>
          </div>

          <div className="space-y-4">
            {apiEndpoints.map((endpoint, idx) => (
              <div key={idx} className="p-4 bg-slate-800/50 rounded-lg">
                <div className="flex items-center space-x-3 mb-2">
                  <span className={`px-3 py-1 rounded text-xs font-semibold ${
                    endpoint.method === 'GET' ? 'bg-blue-500/20 text-blue-400' : 'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {endpoint.method}
                  </span>
                  <code className="text-purple-400 font-mono text-sm">{endpoint.path}</code>
                </div>
                <p className="text-sm text-slate-400 mb-3">{endpoint.description}</p>

                {endpoint.params && endpoint.params.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-slate-500 mb-2">Path Parameters:</p>
                    <div className="space-y-1">
                      {endpoint.params.map((param, pidx) => (
                        <div key={pidx} className="text-xs">
                          <code className="text-purple-400">{param.name}</code>
                          <span className="text-slate-500"> - {param.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {endpoint.body && (
                  <div>
                    <p className="text-xs text-slate-500 mb-2">Request Body:</p>
                    <div className="bg-slate-900/50 rounded p-2 font-mono text-xs">
                      <pre className="text-slate-300">
{JSON.stringify(Object.fromEntries(
  Object.entries(endpoint.body).map(([k, v]) => [k, `<${v.type}>`])
), null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* FAQs */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-6">
            <HelpCircle className="w-6 h-6 text-purple-400" />
            <h2 className="text-2xl font-bold text-white">Frequently Asked Questions</h2>
          </div>

          <div className="space-y-4">
            {faqs.map((faq, idx) => (
              <div key={idx} className="p-4 bg-slate-800/50 rounded-lg">
                <h3 className="font-semibold text-white mb-2 flex items-start">
                  <CheckCircle className="w-5 h-5 text-emerald-400 mr-2 mt-0.5 flex-shrink-0" />
                  {faq.question}
                </h3>
                <p className="text-sm text-slate-400 ml-7">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Links */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/mcp-servers"
            className="p-6 bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/30 rounded-lg hover:scale-105 transition-transform"
          >
            <Server className="w-8 h-8 text-purple-400 mb-3" />
            <h3 className="font-semibold text-white mb-2">Browse All Servers</h3>
            <p className="text-sm text-slate-400">Explore all {totalServers} MCP servers</p>
          </a>

          <a
            href="/docs"
            className="p-6 bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30 rounded-lg hover:scale-105 transition-transform"
          >
            <Book className="w-8 h-8 text-blue-400 mb-3" />
            <h3 className="font-semibold text-white mb-2">API Documentation</h3>
            <p className="text-sm text-slate-400">Complete REST API reference</p>
          </a>

          <a
            href="https://modelcontextprotocol.io"
            target="_blank"
            rel="noopener noreferrer"
            className="p-6 bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border border-emerald-500/30 rounded-lg hover:scale-105 transition-transform"
          >
            <ExternalLink className="w-8 h-8 text-emerald-400 mb-3" />
            <h3 className="font-semibold text-white mb-2">MCP Documentation</h3>
            <p className="text-sm text-slate-400">Official protocol documentation</p>
          </a>
        </div>
      </div>
    </div>
  );
};

export default MCPDocs;
