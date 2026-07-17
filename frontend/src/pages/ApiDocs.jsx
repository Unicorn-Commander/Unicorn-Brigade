import { useState } from 'react';
import { Code, Copy, CheckCircle, Book, Key, Server, Zap, Shield, MessageSquare, Clock } from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';
import { bareHost } from '../services/apiBase';

// Bare host (no /api/v1) — documented paths below carry the full /api/v1 prefix
const API_HOST = bareHost();

const ApiDocs = () => {
  const [selectedEndpoint, setSelectedEndpoint] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState('curl');

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const endpoints = [
    {
      id: 'list-agents',
      method: 'GET',
      path: '/api/v1/agents',
      title: 'List All Agents',
      description: 'Retrieve all agents visible to the caller (per-agent access policy enforced)',
      params: [],
      response: {
        agents: [
          {
            id: 'string',
            name: 'string',
            displayName: 'string',
            domain: 'string',
            status: 'active|draft|inactive',
            avatar: 'string',
            model: 'string',
            tools: ['array']
          }
        ]
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/agents" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/agents', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const data = await response.json();
console.log(data.agents);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/agents',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
agents = response.json()['agents']
print(agents)`
      }
    },
    {
      id: 'get-domains',
      method: 'GET',
      path: '/api/v1/agents/domains',
      title: 'Get Domains',
      description: 'Get list of agent domains with agent counts',
      params: [],
      response: {
        domains: [
          {
            name: 'string',
            count: 'number'
          }
        ]
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/agents/domains" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/agents/domains', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const data = await response.json();
console.log(data.domains);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/agents/domains',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
domains = response.json()['domains']
print(domains)`
      }
    },
    {
      id: 'create-agent',
      method: 'POST',
      path: '/api/v1/agents',
      title: 'Create Agent',
      description: 'Create a new agent with the specified configuration (requires operator role)',
      params: [],
      body: {
        name: { type: 'string', required: true, description: 'Agent name' },
        displayName: { type: 'string', required: false, description: 'Display name' },
        domain: { type: 'string', required: false, description: 'Agent domain (default: general)' },
        systemPrompt: { type: 'string', required: false, description: 'System prompt' },
        persona: { type: 'string', required: false, description: 'Personality / persona text' },
        model: { type: 'string', required: false, description: 'LLM model (default: openai/gpt-4o-mini)' },
        temperature: { type: 'number', required: false, description: 'Sampling temperature (default: 0.7)' },
        tools: { type: 'array', required: false, description: 'Tool names to attach (e.g. web_search, calculator)' },
        capabilities: { type: 'array', required: false, description: 'List of capabilities' }
      },
      response: {
        id: 'string',
        name: 'string',
        displayName: 'string',
        domain: 'string',
        status: 'active',
        model: 'string',
        tools: ['array']
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/agents" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "my-agent",
    "displayName": "My Agent",
    "domain": "technology",
    "systemPrompt": "You are a helpful assistant",
    "model": "openai/gpt-4o-mini",
    "tools": ["web_search", "calculator"]
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/agents', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'my-agent',
    displayName: 'My Agent',
    domain: 'technology',
    systemPrompt: 'You are a helpful assistant',
    model: 'openai/gpt-4o-mini',
    tools: ['web_search', 'calculator']
  })
});
const agent = await response.json();
console.log(agent.id);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/agents',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'name': 'my-agent',
        'displayName': 'My Agent',
        'domain': 'technology',
        'systemPrompt': 'You are a helpful assistant',
        'model': 'openai/gpt-4o-mini',
        'tools': ['web_search', 'calculator']
    }
)
agent = response.json()
print(agent['id'])`
      }
    },
    {
      id: 'chat-agent',
      method: 'POST',
      path: '/api/v1/agents/{id}/chat',
      title: 'Chat with Agent',
      description: 'Send a message to an agent and get a response. Tools attached to the agent are invoked automatically (function calling).',
      params: [
        { name: 'id', type: 'string', description: 'Agent ID', required: true }
      ],
      body: {
        message: { type: 'string', required: true, description: 'Message to send' },
        stream: { type: 'boolean', required: false, description: 'Stream the response via SSE (default: false)' },
        model: { type: 'string', required: false, description: 'Override the agent model for this call' },
        temperature: { type: 'number', required: false, description: 'Override sampling temperature' },
        maxTokens: { type: 'number', required: false, description: 'Override max tokens' },
        history: { type: 'array', required: false, description: 'Prior turns: [{"role", "content"}]' }
      },
      response: {
        content: 'string',
        model: 'string',
        provider: 'string',
        usage: {
          prompt_tokens: 'number',
          completion_tokens: 'number',
          total_tokens: 'number'
        },
        agent: {
          id: 'string',
          name: 'string',
          avatar: 'string'
        }
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/agents/AGENT_ID/chat" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Search for AI market trends"
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/agents/AGENT_ID/chat', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: 'Search for AI market trends'
  })
});
const data = await response.json();
console.log(data.content);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/agents/AGENT_ID/chat',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={'message': 'Search for AI market trends'}
)
data = response.json()
print(data['content'])`
      }
    },
    {
      id: 'builder-chat',
      method: 'POST',
      path: '/api/v1/agent-builder/chat',
      title: 'Agent Builder Chat (Gunny)',
      description: 'Chat with Gunny, the agent builder, to design and create new agents through conversation',
      params: [],
      body: {
        message: { type: 'string', required: true, description: 'Message to Gunny' },
        sessionId: { type: 'string', required: false, description: 'Builder session ID (continues a conversation)' },
        userId: { type: 'string', required: false, description: 'Caller user ID' }
      },
      response: {
        message: 'string',
        sessionId: 'string',
        usage: {
          total_tokens: 'number',
          model: 'string'
        },
        agentCreationIntent: 'boolean'
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/agent-builder/chat" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Create a financial analysis agent"
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/agent-builder/chat', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: 'Create a financial analysis agent'
  })
});
const data = await response.json();
console.log(data.message);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/agent-builder/chat',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={'message': 'Create a financial analysis agent'}
)
data = response.json()
print(data['message'])`
      }
    },
    {
      id: 'a2a-list-agents',
      method: 'GET',
      path: '/api/v1/a2a/agents',
      title: 'List Agent Cards (A2A)',
      description: 'List all agents as A2A agent cards for discovery',
      params: [],
      queryParams: [
        { name: 'domain', type: 'string', description: 'Filter by domain', required: false },
        { name: 'status', type: 'string', description: 'Filter by status (default: active)', required: false }
      ],
      response: {
        agents: ['array of agent cards'],
        count: 'number',
        protocol: 'a2a/1.0'
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/a2a/agents" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/a2a/agents', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const data = await response.json();
console.log(data.agents);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/a2a/agents',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
print(response.json()['agents'])`
      }
    },
    {
      id: 'a2a-agent-card',
      method: 'GET',
      path: '/api/v1/a2a/agents/{id}/card',
      title: 'Get Agent Card (A2A)',
      description: 'Retrieve one agent’s A2A card: capabilities, endpoints, auth, and rate limits',
      params: [
        { name: 'id', type: 'string', description: 'Agent ID', required: true }
      ],
      response: {
        id: 'string',
        name: 'string',
        description: 'string',
        version: 'string',
        endpoints: {
          invoke_url: 'string',
          stream_url: 'string',
          card_url: 'string'
        },
        capabilities: ['array'],
        domain: 'string',
        status: 'active|inactive'
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/a2a/agents/AGENT_ID/card" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/a2a/agents/AGENT_ID/card', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const card = await response.json();
console.log(card);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/a2a/agents/AGENT_ID/card',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
card = response.json()
print(card)`
      }
    },
    {
      id: 'a2a-invoke',
      method: 'POST',
      path: '/api/v1/a2a/agents/{id}/invoke',
      title: 'Invoke Agent (A2A)',
      description: 'Invoke an agent via the A2A protocol — the entry point for agent-to-agent communication',
      params: [
        { name: 'id', type: 'string', description: 'Agent ID', required: true }
      ],
      body: {
        task: { type: 'string', required: true, description: 'Task for the agent to perform' },
        capability: { type: 'string', required: false, description: 'Specific capability to use' },
        context: { type: 'object', required: false, description: 'Additional context' },
        session_id: { type: 'string', required: false, description: 'Session ID for continuity' },
        conversation_history: { type: 'array', required: false, description: 'Prior turns: [{"role", "content"}]' },
        timeout_seconds: { type: 'number', required: false, description: 'Timeout (default: 120)' },
        stream: { type: 'boolean', required: false, description: 'Stream the response (default: false)' }
      },
      response: {
        status: 'completed|failed',
        result: 'string',
        task_id: 'string',
        agent_id: 'string',
        model_used: 'string',
        tokens_used: {
          input: 'number',
          output: 'number'
        },
        duration_seconds: 'number'
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/a2a/agents/AGENT_ID/invoke" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "task": "Summarize Q4 tech sector trends"
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/a2a/agents/AGENT_ID/invoke', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    task: 'Summarize Q4 tech sector trends'
  })
});
const data = await response.json();
console.log(data.result);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/a2a/agents/AGENT_ID/invoke',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={'task': 'Summarize Q4 tech sector trends'}
)
data = response.json()
print(data['result'])`
      }
    },
    {
      id: 'mcp-tools-list',
      method: 'GET',
      path: '/api/v1/mcp/tools/list',
      title: 'List Tools (MCP)',
      description: 'List all tools registered with the MCP server, with parameter schemas',
      params: [],
      response: {
        tools: [
          {
            name: 'string',
            description: 'string',
            parameters: ['array'],
            requires_approval: 'boolean'
          }
        ],
        count: 'number'
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/mcp/tools/list" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/mcp/tools/list', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const data = await response.json();
console.log(data.tools);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/mcp/tools/list',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
print(response.json()['tools'])`
      }
    },
    {
      id: 'mcp-tools-call',
      method: 'POST',
      path: '/api/v1/mcp/tools/call',
      title: 'Call Tool (MCP)',
      description: 'Invoke an MCP tool directly by name with arguments',
      params: [],
      body: {
        name: { type: 'string', required: true, description: 'Tool name (e.g. calculator, web_search)' },
        arguments: { type: 'object', required: false, description: 'Tool arguments' }
      },
      response: {
        tool: 'string',
        result: 'any',
        success: 'boolean'
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/mcp/tools/call" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "calculator",
    "arguments": {"expression": "2 + 2"}
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/mcp/tools/call', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'calculator',
    arguments: { expression: '2 + 2' }
  })
});
const data = await response.json();
console.log(data.result);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/mcp/tools/call',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={'name': 'calculator', 'arguments': {'expression': '2 + 2'}}
)
data = response.json()
print(data['result'])`
      }
    },
    {
      id: 'scheduled-runs-list',
      method: 'GET',
      path: '/api/v1/scheduled-runs',
      title: 'List Scheduled Runs',
      description: 'List scheduled agent runs. Non-admins see only their own runs.',
      params: [],
      response: {
        items: [
          {
            id: 'string',
            name: 'string',
            agentId: 'string',
            prompt: 'string',
            cron: 'string',
            timezone: 'string',
            enabled: 'boolean'
          }
        ],
        total: 'number'
      },
      examples: {
        curl: `curl -X GET "${API_HOST}/api/v1/scheduled-runs" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/scheduled-runs', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const data = await response.json();
console.log(data.items);`,
        python: `import requests

response = requests.get(
    '${API_HOST}/api/v1/scheduled-runs',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
print(response.json()['items'])`
      }
    },
    {
      id: 'scheduled-runs-create',
      method: 'POST',
      path: '/api/v1/scheduled-runs',
      title: 'Create Scheduled Run',
      description: 'Schedule an agent to run a prompt on a cron cadence (requires operator role)',
      params: [],
      body: {
        name: { type: 'string', required: true, description: 'Run name' },
        agentId: { type: 'string', required: true, description: 'Agent to run' },
        prompt: { type: 'string', required: true, description: 'Prompt sent to the agent on each run' },
        cron: { type: 'string', required: true, description: 'Cron expression (e.g. "0 9 * * 1-5")' },
        timezone: { type: 'string', required: false, description: 'IANA timezone (default: UTC)' },
        enabled: { type: 'boolean', required: false, description: 'Start enabled (default: true)' },
        maxRuntimeSeconds: { type: 'number', required: false, description: 'Per-run timeout, 5-3600 (default: 300)' }
      },
      response: {
        id: 'string',
        name: 'string',
        agentId: 'string',
        cron: 'string',
        timezone: 'string',
        enabled: 'boolean'
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/scheduled-runs" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Morning briefing",
    "agentId": "AGENT_ID",
    "prompt": "Summarize overnight developments in AI",
    "cron": "0 9 * * 1-5",
    "timezone": "America/New_York"
  }'`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/scheduled-runs', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Morning briefing',
    agentId: 'AGENT_ID',
    prompt: 'Summarize overnight developments in AI',
    cron: '0 9 * * 1-5',
    timezone: 'America/New_York'
  })
});
const run = await response.json();
console.log(run.id);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/scheduled-runs',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'name': 'Morning briefing',
        'agentId': 'AGENT_ID',
        'prompt': 'Summarize overnight developments in AI',
        'cron': '0 9 * * 1-5',
        'timezone': 'America/New_York'
    }
)
run = response.json()
print(run['id'])`
      }
    },
    {
      id: 'scheduled-runs-run-now',
      method: 'POST',
      path: '/api/v1/scheduled-runs/{id}/run-now',
      title: 'Trigger Scheduled Run Now',
      description: 'Execute a scheduled run immediately, outside its cron cadence. History is available at GET /api/v1/scheduled-runs/{id}/history.',
      params: [
        { name: 'id', type: 'string', description: 'Scheduled run ID', required: true }
      ],
      response: {
        id: 'string',
        scheduledRunId: 'string',
        status: 'string',
        startedAt: 'string'
      },
      examples: {
        curl: `curl -X POST "${API_HOST}/api/v1/scheduled-runs/RUN_ID/run-now" \\
  -H "X-API-Key: YOUR_API_KEY"`,
        javascript: `const response = await fetch('${API_HOST}/api/v1/scheduled-runs/RUN_ID/run-now', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY'
  }
});
const history = await response.json();
console.log(history);`,
        python: `import requests

response = requests.post(
    '${API_HOST}/api/v1/scheduled-runs/RUN_ID/run-now',
    headers={'X-API-Key': 'YOUR_API_KEY'}
)
print(response.json())`
      }
    }
  ];

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              API Documentation
            </h1>
            <p className="text-slate-400 mt-1">
              Build on Unicorn Brigade with our REST API
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <div className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg">
              <span className="text-sm text-slate-400">Base URL: </span>
              <span className="text-sm text-purple-400 font-mono">{API_HOST}/api/v1</span>
            </div>
          </div>
        </div>

        {/* Quick Start Guide */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Book className="w-6 h-6 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Quick Start</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-2">
                <Key className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-white">1. Get API Key</h3>
              </div>
              <p className="text-sm text-slate-400">
                Generate an API key from Settings to authenticate your requests
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-2">
                <Server className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white">2. Make Request</h3>
              </div>
              <p className="text-sm text-slate-400">
                Send HTTP requests with your API key in the X-API-Key header
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-2 mb-2">
                <Zap className="w-5 h-5 text-orange-400" />
                <h3 className="font-semibold text-white">3. Build</h3>
              </div>
              <p className="text-sm text-slate-400">
                Create agents, invoke them, and build your AI infrastructure
              </p>
            </div>
          </div>
        </div>

        {/* Authentication */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Shield className="w-6 h-6 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Authentication</h2>
          </div>
          <p className="text-slate-400 mb-4">
            All API requests must include an API key in the X-API-Key header:
          </p>
          <div className="bg-slate-800/50 rounded-lg p-4 font-mono text-sm relative">
            <button
              onClick={() => copyToClipboard('X-API-Key: YOUR_API_KEY')}
              className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
            >
              <Copy className="w-4 h-4 text-slate-400" />
            </button>
            <code className="text-slate-300">
              <span className="text-purple-400">X-API-Key:</span> YOUR_API_KEY
            </code>
          </div>
        </div>

        {/* Endpoints */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Endpoint List */}
          <div className="lg:col-span-1">
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 sticky top-6">
              <h2 className="text-xl font-bold text-white mb-4">Endpoints</h2>
              <div className="space-y-2">
                {endpoints.map(endpoint => (
                  <button
                    key={endpoint.id}
                    onClick={() => setSelectedEndpoint(endpoint)}
                    className={`w-full text-left p-3 rounded-lg transition-all ${
                      selectedEndpoint?.id === endpoint.id
                        ? 'bg-purple-500/20 border border-purple-500/30'
                        : 'bg-slate-800/50 hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center space-x-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        endpoint.method === 'GET' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-emerald-500/20 text-emerald-400'
                      }`}>
                        {endpoint.method}
                      </span>
                      <span className="text-xs text-slate-400 font-mono truncate">{endpoint.path}</span>
                    </div>
                    <p className="text-sm font-medium text-white">{endpoint.title}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Endpoint Details */}
          <div className="lg:col-span-2">
            {selectedEndpoint ? (
              <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 space-y-6">
                {/* Header */}
                <div>
                  <div className="flex items-center space-x-3 mb-2">
                    <span className={`px-3 py-1 rounded font-semibold ${
                      selectedEndpoint.method === 'GET' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-emerald-500/20 text-emerald-400'
                    }`}>
                      {selectedEndpoint.method}
                    </span>
                    <code className="text-purple-400 font-mono">{selectedEndpoint.path}</code>
                  </div>
                  <h2 className="text-2xl font-bold text-white mb-2">{selectedEndpoint.title}</h2>
                  <p className="text-slate-400">{selectedEndpoint.description}</p>
                </div>

                {/* Path Parameters */}
                {selectedEndpoint.params.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-3">Path Parameters</h3>
                    <div className="space-y-2">
                      {selectedEndpoint.params.map((param, idx) => (
                        <div key={idx} className="p-3 bg-slate-800/50 rounded-lg">
                          <div className="flex items-center space-x-2 mb-1">
                            <code className="text-purple-400">{param.name}</code>
                            <span className="text-xs text-slate-500">{param.type}</span>
                            {param.required && (
                              <span className="text-xs text-red-400">required</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-400">{param.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Query Parameters */}
                {selectedEndpoint.queryParams && selectedEndpoint.queryParams.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-3">Query Parameters</h3>
                    <div className="space-y-2">
                      {selectedEndpoint.queryParams.map((param, idx) => (
                        <div key={idx} className="p-3 bg-slate-800/50 rounded-lg">
                          <div className="flex items-center space-x-2 mb-1">
                            <code className="text-purple-400">{param.name}</code>
                            <span className="text-xs text-slate-500">{param.type}</span>
                            {param.required && (
                              <span className="text-xs text-red-400">required</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-400">{param.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Request Body */}
                {selectedEndpoint.body && (
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-3">Request Body</h3>
                    <div className="space-y-2">
                      {Object.entries(selectedEndpoint.body).map(([key, value]) => (
                        <div key={key} className="p-3 bg-slate-800/50 rounded-lg">
                          <div className="flex items-center space-x-2 mb-1">
                            <code className="text-purple-400">{key}</code>
                            <span className="text-xs text-slate-500">{value.type}</span>
                            {value.required && (
                              <span className="text-xs text-red-400">required</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-400">{value.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Response */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-3">Response</h3>
                  <div className="bg-slate-800/50 rounded-lg p-4 font-mono text-sm overflow-x-auto">
                    <pre className="text-slate-300">
                      {JSON.stringify(selectedEndpoint.response, null, 2)}
                    </pre>
                  </div>
                </div>

                {/* Code Examples */}
                <div>
                  <h3 className="text-lg font-semibold text-white mb-3">Code Examples</h3>
                  <div className="flex space-x-2 mb-3">
                    {['curl', 'javascript', 'python'].map(lang => (
                      <button
                        key={lang}
                        onClick={() => setSelectedLanguage(lang)}
                        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                          selectedLanguage === lang
                            ? 'bg-purple-500 text-white'
                            : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                        }`}
                      >
                        {lang === 'curl' ? 'cURL' : lang.charAt(0).toUpperCase() + lang.slice(1)}
                      </button>
                    ))}
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-4 font-mono text-sm relative">
                    <button
                      onClick={() => copyToClipboard(selectedEndpoint.examples[selectedLanguage])}
                      className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded z-10"
                    >
                      <Copy className="w-4 h-4 text-slate-400" />
                    </button>
                    <pre className="text-slate-300 overflow-x-auto pr-12">
                      {selectedEndpoint.examples[selectedLanguage]}
                    </pre>
                  </div>
                </div>
              </div>
            ) : (
              <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-12 text-center">
                <Code className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-slate-300 mb-2">Select an Endpoint</h3>
                <p className="text-slate-400">Choose an endpoint from the list to view documentation</p>
              </div>
            )}
          </div>
        </div>

        {/* A2A Protocol Section */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-4">
            <MessageSquare className="w-6 h-6 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Agent-to-Agent (A2A) Protocol</h2>
          </div>
          <p className="text-slate-400 mb-4">
            Unicorn Brigade supports the A2A protocol for agent discovery and communication.
            All A2A endpoints live under <code className="text-purple-400">/api/v1/a2a</code> —
            server info at <code className="text-purple-400">/api/v1/a2a/info</code>, capability search
            at <code className="text-purple-400">POST /api/v1/a2a/discover</code>.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Agent Discovery</h3>
              <p className="text-sm text-slate-400">
                List cards via <code className="text-purple-400">GET /api/v1/a2a/agents</code> or fetch one
                agent’s capabilities via <code className="text-purple-400">GET /api/v1/a2a/agents/{'{id}'}/card</code>
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Agent Invocation</h3>
              <p className="text-sm text-slate-400">
                Send tasks via <code className="text-purple-400">POST /api/v1/a2a/agents/{'{id}'}/invoke</code> and
                poll async tasks at <code className="text-purple-400">GET /api/v1/a2a/tasks/{'{task_id}'}/status</code>
              </p>
            </div>
          </div>
        </div>

        {/* Scheduled Runs Section */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Clock className="w-6 h-6 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Scheduled Runs</h2>
          </div>
          <p className="text-slate-400 mb-4">
            Run any agent on a recurring cron schedule — register a watcher, a daily report, or a
            monitoring sweep once and Brigade executes it for you. All endpoints live under{' '}
            <code className="text-purple-400">/api/v1/scheduled-runs</code> and are owner-scoped:
            non-admin callers only see and manage their own runs.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Create &amp; Manage</h3>
              <p className="text-sm text-slate-400">
                <code className="text-purple-400">POST /api/v1/scheduled-runs</code> with a name, agentId,
                prompt, and cron expression. Update with <code className="text-purple-400">PUT /{'{id}'}</code>,
                remove with <code className="text-purple-400">DELETE /{'{id}'}</code>
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Trigger On Demand</h3>
              <p className="text-sm text-slate-400">
                <code className="text-purple-400">POST /api/v1/scheduled-runs/{'{id}'}/run-now</code> executes
                immediately without waiting for the next cron tick
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Inspect History</h3>
              <p className="text-sm text-slate-400">
                <code className="text-purple-400">GET /api/v1/scheduled-runs/{'{id}'}/history</code> returns
                past executions with status and output
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApiDocs;
