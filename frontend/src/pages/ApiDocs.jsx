import { useState } from 'react';
import { Code, Copy, CheckCircle, Book, Key, Server, Zap, Shield, MessageSquare } from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1').replace(/\/api\/v1$/, '').replace(/\/api$/, '');

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
      path: '/api/agents',
      title: 'List All Agents',
      description: 'Retrieve a list of all agents in the system',
      params: [],
      queryParams: [
        { name: 'domain', type: 'string', description: 'Filter by domain', required: false },
        { name: 'status', type: 'string', description: 'Filter by status', required: false }
      ],
      response: {
        agents: [
          {
            id: 'string',
            name: 'string',
            displayName: 'string',
            domain: 'string',
            status: 'active|draft|inactive',
            avatar: 'string',
            model: 'string'
          }
        ]
      },
      examples: {
        curl: `curl -X GET "${API_BASE}/api/agents" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json"`,
        javascript: `const response = await fetch('${API_BASE}/api/agents', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
console.log(data.agents);`,
        python: `import requests

response = requests.get(
    '${API_BASE}/api/agents',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    }
)
agents = response.json()['agents']
print(agents)`
      }
    },
    {
      id: 'create-agent',
      method: 'POST',
      path: '/api/agents',
      title: 'Create Agent',
      description: 'Create a new agent with specified configuration',
      params: [],
      body: {
        name: { type: 'string', required: true, description: 'Agent name' },
        displayName: { type: 'string', required: false, description: 'Display name' },
        domain: { type: 'string', required: true, description: 'Agent domain' },
        prompt: { type: 'string', required: true, description: 'System prompt' },
        model: { type: 'string', required: false, description: 'LLM model to use' },
        capabilities: { type: 'array', required: false, description: 'List of capabilities' }
      },
      response: {
        agent: {
          id: 'string',
          name: 'string',
          domain: 'string',
          status: 'draft'
        }
      },
      examples: {
        curl: `curl -X POST "${API_BASE}/api/agents" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "my-agent",
    "displayName": "My Agent",
    "domain": "technology",
    "prompt": "You are a helpful assistant",
    "model": "gpt-4-turbo"
  }'`,
        javascript: `const response = await fetch('${API_BASE}/api/agents', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'my-agent',
    displayName: 'My Agent',
    domain: 'technology',
    prompt: 'You are a helpful assistant',
    model: 'gpt-4-turbo'
  })
});
const data = await response.json();
console.log(data.agent);`,
        python: `import requests

response = requests.post(
    '${API_BASE}/api/agents',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'name': 'my-agent',
        'displayName': 'My Agent',
        'domain': 'technology',
        'prompt': 'You are a helpful assistant',
        'model': 'gpt-4-turbo'
    }
)
agent = response.json()['agent']
print(agent)`
      }
    },
    {
      id: 'get-agent-card',
      method: 'GET',
      path: '/api/agents/:id/card',
      title: 'Get Agent Card (A2A)',
      description: 'Retrieve Agent Card for Agent-to-Agent (A2A) protocol',
      params: [
        { name: 'id', type: 'string', description: 'Agent ID', required: true }
      ],
      response: {
        type: 'agent-card',
        agent: {
          id: 'string',
          name: 'string',
          capabilities: ['array'],
          endpoints: {
            invoke: 'string'
          }
        }
      },
      examples: {
        curl: `curl -X GET "${API_BASE}/api/agents/AGENT_ID/card" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json"`,
        javascript: `const response = await fetch('${API_BASE}/api/agents/AGENT_ID/card', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  }
});
const card = await response.json();
console.log(card);`,
        python: `import requests

response = requests.get(
    '${API_BASE}/api/agents/AGENT_ID/card',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    }
)
card = response.json()
print(card)`
      }
    },
    {
      id: 'invoke-agent',
      method: 'POST',
      path: '/api/agents/:id/invoke',
      title: 'Invoke Agent',
      description: 'Send a message to an agent and get a response',
      params: [
        { name: 'id', type: 'string', description: 'Agent ID', required: true }
      ],
      body: {
        message: { type: 'string', required: true, description: 'Message to send' },
        conversationId: { type: 'string', required: false, description: 'Conversation ID' },
        context: { type: 'object', required: false, description: 'Additional context' }
      },
      response: {
        response: 'string',
        conversationId: 'string',
        metadata: {
          model: 'string',
          tokensUsed: 'number'
        }
      },
      examples: {
        curl: `curl -X POST "${API_BASE}/api/agents/AGENT_ID/invoke" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Hello, agent!",
    "conversationId": "conv-123"
  }'`,
        javascript: `const response = await fetch('${API_BASE}/api/agents/AGENT_ID/invoke', {
  method: 'POST',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: 'Hello, agent!',
    conversationId: 'conv-123'
  })
});
const data = await response.json();
console.log(data.response);`,
        python: `import requests

response = requests.post(
    '${API_BASE}/api/agents/AGENT_ID/invoke',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'message': 'Hello, agent!',
        'conversationId': 'conv-123'
    }
)
data = response.json()
print(data['response'])`
      }
    },
    {
      id: 'builder-chat',
      method: 'POST',
      path: '/api/agent-builder/chat',
      title: 'Chat with The General',
      description: 'Chat with The General to build or modify agents',
      params: [],
      body: {
        message: { type: 'string', required: true, description: 'Message to The General' },
        conversationId: { type: 'string', required: false, description: 'Conversation ID' }
      },
      response: {
        response: 'string',
        conversationId: 'string',
        actions: ['array']
      },
      examples: {
        curl: `curl -X POST "${API_BASE}/api/agent-builder/chat" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "message": "Create a financial analysis agent"
  }'`,
        javascript: `const response = await fetch('${API_BASE}/api/agent-builder/chat', {
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
console.log(data.response);`,
        python: `import requests

response = requests.post(
    '${API_BASE}/api/agent-builder/chat',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'message': 'Create a financial analysis agent'
    }
)
data = response.json()
print(data['response'])`
      }
    },
    {
      id: 'get-domains',
      method: 'GET',
      path: '/api/agents/domains',
      title: 'Get Domains',
      description: 'Get list of agent domains with counts',
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
        curl: `curl -X GET "${API_BASE}/api/agents/domains" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json"`,
        javascript: `const response = await fetch('${API_BASE}/api/agents/domains', {
  method: 'GET',
  headers: {
    'X-API-Key': 'YOUR_API_KEY',
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
console.log(data.domains);`,
        python: `import requests

response = requests.get(
    '${API_BASE}/api/agents/domains',
    headers={
        'X-API-Key': 'YOUR_API_KEY',
        'Content-Type': 'application/json'
    }
)
domains = response.json()['domains']
print(domains)`
      }
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-6 lg:p-8">
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
              <span className="text-sm text-purple-400 font-mono">{API_BASE}</span>
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
            Agents can discover each other via Agent Cards and communicate through standardized endpoints.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Agent Discovery</h3>
              <p className="text-sm text-slate-400">
                Use the <code className="text-purple-400">/card</code> endpoint to retrieve an agent's capabilities and endpoints
              </p>
            </div>
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <h3 className="font-semibold text-white mb-2">Agent Invocation</h3>
              <p className="text-sm text-slate-400">
                Use the <code className="text-purple-400">/invoke</code> endpoint to send messages and get responses
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApiDocs;
