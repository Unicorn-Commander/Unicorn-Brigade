/**
 * API reference — the REST surface, written to read like Stripe's docs:
 * a sticky section list on the left, one long document on the right, every
 * code block copyable, one language choice applied everywhere.
 *
 * The docs scaffolding (CodeBlock, MethodChip, CopyChip, DocsNav, DocsJump,
 * useActiveSection) is exported from here and shared with MCPDocs.jsx. It is a
 * candidate for components/ui once the integrator lifts it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Book, Check, Clock, Copy, Key, MessageSquare, Repeat, Server, Settings, Shield, Zap } from 'lucide-react';
import notify from '../utils/notify';
import Breadcrumbs from '../components/Breadcrumbs';
import { bareHost } from '../services/apiBase';
import { Button, Card, Chip, IconButton, Page, PageHeader, Select, Tabs } from '../components/ui';

// Bare host (no /api/v1) — documented paths below carry the full /api/v1 prefix.
// A same-origin build (VITE_API_URL=/api/v1) has no host, so show this origin:
// a curl example with a relative URL helps nobody.
const API_HOST = bareHost() || (typeof window !== 'undefined' ? window.location.origin : '');
const BASE_URL = `${API_HOST}/api/v1`;

// ── shared docs scaffolding ──────────────────────────────────────────────────

const METHOD_TONE = { GET: 'info', POST: 'accent', PUT: 'warn', PATCH: 'warn', DELETE: 'danger' };

export function MethodChip({ method, size = 'xs' }) {
  return (
    <Chip tone={METHOD_TONE[method] || 'neutral'} size={size} uppercase className="font-mono">
      {method}
    </Chip>
  );
}

export async function copyText(text, what = 'Copied') {
  try {
    await navigator.clipboard.writeText(text);
    notify.success(what);
  } catch {
    notify.error('Couldn’t copy — your browser blocked clipboard access.');
  }
}

/** A value you can click to copy (the base URL, a header name). */
export function CopyChip({ value, label, tone = 'neutral' }) {
  const [done, setDone] = useState(false);
  return (
    <Chip
      tone={tone}
      size="md"
      icon={done ? Check : Copy}
      className="font-mono"
      onClick={async () => {
        await copyText(value, `${label || 'Value'} copied`);
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
      aria-label={`Copy ${label || value}`}
    >
      {value}
    </Chip>
  );
}

/** A code sample in a mono card with a copy control and optional header actions (language tabs). */
export function CodeBlock({ code, label, copyLabel = 'Copy code', actions, className = '' }) {
  return (
    <Card padding="none" className={`overflow-hidden ${className}`}>
      <div className="flex items-center gap-2 border-b border-border bg-elevated/50 py-1.5 pl-3 pr-1.5">
        {label && <span className="min-w-0 flex-1 truncate font-mono text-caption text-muted">{label}</span>}
        {!label && <span className="flex-1" />}
        {actions}
        <IconButton icon={Copy} label={copyLabel} size="sm" onClick={() => copyText(code, 'Copied to clipboard')} />
      </div>
      <pre className="overflow-x-auto bg-surface/70 p-4 font-mono text-body-sm leading-5 text-fg">
        <code>{code}</code>
      </pre>
    </Card>
  );
}

/** Tracks which section is in view; returns [activeId, jumpTo]. */
export function useActiveSection(ids) {
  const [active, setActive] = useState(ids[0] || null);
  const key = ids.join('|');
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      let current = ids[0] || null;
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        if (el.getBoundingClientRect().top <= 140) current = id;
        else break;
      }
      setActive((a) => (a === current ? a : current));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    measure();
    // capture=true also catches inner scrollers (the app shell's main pane).
    document.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      document.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const jumpTo = useCallback((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ block: 'start' });
    setActive(id);
    // Move focus so keyboard users land in the section.
    const h = el.querySelector('h2');
    if (h) {
      h.setAttribute('tabindex', '-1');
      h.focus({ preventScroll: true });
    }
  }, []);
  return [active, jumpTo];
}

/** The sticky left section list (lg and up). groups: [{ title, items: [{ id, label, method? }] }] */
export function DocsNav({ groups, active, onSelect, label = 'On this page' }) {
  return (
    <nav aria-label={label} className="hidden lg:block">
      <div className="sticky top-6 max-h-[calc(100vh-6rem)] space-y-5 overflow-y-auto pr-2">
        {groups.map((g) => (
          <div key={g.title}>
            <p className="mb-1.5 px-2 text-micro font-semibold uppercase tracking-wider text-muted">{g.title}</p>
            <ul className="space-y-0.5">
              {g.items.map((it) => {
                const selected = it.id === active;
                return (
                  <li key={it.id}>
                    <a
                      href={`#${it.id}`}
                      aria-current={selected ? 'location' : undefined}
                      onClick={(e) => {
                        e.preventDefault();
                        onSelect(it.id);
                      }}
                      className={`flex min-w-0 items-center gap-2 rounded-control px-2 py-1.5 text-body-sm transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        selected ? 'bg-elevated text-fg-strong' : 'text-muted hover:bg-elevated/60 hover:text-fg'
                      }`}
                    >
                      {it.method && <MethodChip method={it.method} />}
                      <span className="truncate">{it.label}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

/** The phone replacement for DocsNav: a "Jump to" select. */
export function DocsJump({ groups, active, onSelect }) {
  return (
    <div className="mb-4 lg:hidden">
      <Select aria-label="Jump to section" value={active || ''} onChange={(e) => onSelect(e.target.value)}>
        {groups.map((g) => (
          <optgroup key={g.title} label={g.title}>
            {g.items.map((it) => (
              <option key={it.id} value={it.id}>
                {it.method ? `${it.method} · ` : ''}
                {it.label}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
    </div>
  );
}

/** Section wrapper: anchored id, heading, consistent rhythm. */
export function DocsSection({ id, title, lead, children, className = '' }) {
  return (
    <section id={id} className={`scroll-mt-6 ${className}`} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="text-heading text-fg-strong">
        {title}
      </h2>
      {lead && <p className="mt-1 max-w-3xl text-body text-muted">{lead}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ParamTable({ title, rows }) {
  if (!rows?.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-body font-semibold text-fg-strong">{title}</h3>
      <div className="overflow-hidden rounded-card border border-border">
        <table className="w-full border-collapse text-body-sm">
          <thead className="sr-only">
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Type</th>
              <th scope="col">Description</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-b border-border/60 last:border-b-0">
                <td className="whitespace-nowrap px-3 py-2 align-top">
                  <code className="font-mono text-body-sm text-accent">{r.name}</code>
                  <span className="ml-2 text-caption text-muted">{r.type}</span>
                  {r.required && (
                    <Chip tone="danger" size="xs" className="ml-2">
                      required
                    </Chip>
                  )}
                </td>
                <td className="w-full px-3 py-2 align-top text-muted">{r.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── content ──────────────────────────────────────────────────────────────────

const LANGS = [
  { id: 'curl', label: 'cURL' },
  { id: 'javascript', label: 'JavaScript' },
  { id: 'python', label: 'Python' },
];

const ENDPOINTS = [
  {
    id: 'list-agents',
    method: 'GET',
    path: '/api/v1/agents',
    title: 'List all agents',
    description: 'Retrieve all agents visible to the caller (per-agent access policy enforced).',
    params: [],
    response: {
      agents: [{ id: 'string', name: 'string', displayName: 'string', domain: 'string', status: 'active|draft|inactive', avatar: 'string', model: 'string', tools: ['array'] }],
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
print(agents)`,
    },
  },
  {
    id: 'get-domains',
    method: 'GET',
    path: '/api/v1/agents/domains',
    title: 'Get domains',
    description: 'List agent domains with agent counts.',
    params: [],
    response: { domains: [{ name: 'string', count: 'number' }] },
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
print(domains)`,
    },
  },
  {
    id: 'create-agent',
    method: 'POST',
    path: '/api/v1/agents',
    title: 'Create an agent',
    description: 'Create a new agent with the specified configuration (requires the operator role).',
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
      capabilities: { type: 'array', required: false, description: 'List of capabilities' },
    },
    response: { id: 'string', name: 'string', displayName: 'string', domain: 'string', status: 'active', model: 'string', tools: ['array'] },
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
print(agent['id'])`,
    },
  },
  {
    id: 'chat-agent',
    method: 'POST',
    path: '/api/v1/agents/{id}/chat',
    title: 'Chat with an agent',
    description: 'Send a message to an agent and get a response. Tools attached to the agent are invoked automatically (function calling).',
    params: [{ name: 'id', type: 'string', description: 'Agent ID', required: true }],
    body: {
      message: { type: 'string', required: true, description: 'Message to send' },
      stream: { type: 'boolean', required: false, description: 'Stream the response via SSE (default: false)' },
      model: { type: 'string', required: false, description: 'Override the agent model for this call' },
      temperature: { type: 'number', required: false, description: 'Override sampling temperature' },
      maxTokens: { type: 'number', required: false, description: 'Override max tokens' },
      history: { type: 'array', required: false, description: 'Prior turns: [{"role", "content"}]' },
    },
    response: {
      content: 'string',
      model: 'string',
      provider: 'string',
      usage: { prompt_tokens: 'number', completion_tokens: 'number', total_tokens: 'number' },
      agent: { id: 'string', name: 'string', avatar: 'string' },
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
print(data['content'])`,
    },
  },
  {
    id: 'builder-chat',
    method: 'POST',
    path: '/api/v1/agent-builder/chat',
    title: 'Agent builder chat (Gunny)',
    description: 'Chat with Gunny, the agent builder, to design and create new agents through conversation.',
    params: [],
    body: {
      message: { type: 'string', required: true, description: 'Message to Gunny' },
      sessionId: { type: 'string', required: false, description: 'Builder session ID (continues a conversation)' },
      userId: { type: 'string', required: false, description: 'Caller user ID' },
    },
    response: { message: 'string', sessionId: 'string', usage: { total_tokens: 'number', model: 'string' }, agentCreationIntent: 'boolean' },
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
print(data['message'])`,
    },
  },
  {
    id: 'a2a-list-agents',
    method: 'GET',
    path: '/api/v1/a2a/agents',
    title: 'List agent cards (A2A)',
    description: 'List all agents as A2A agent cards for discovery.',
    params: [],
    queryParams: [
      { name: 'domain', type: 'string', description: 'Filter by domain', required: false },
      { name: 'status', type: 'string', description: 'Filter by status (default: active)', required: false },
    ],
    response: { agents: ['array of agent cards'], count: 'number', protocol: 'a2a/1.0' },
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
print(response.json()['agents'])`,
    },
  },
  {
    id: 'a2a-agent-card',
    method: 'GET',
    path: '/api/v1/a2a/agents/{id}/card',
    title: 'Get an agent card (A2A)',
    description: 'Retrieve one agent’s A2A card: capabilities, endpoints, auth, and rate limits.',
    params: [{ name: 'id', type: 'string', description: 'Agent ID', required: true }],
    response: {
      id: 'string',
      name: 'string',
      description: 'string',
      version: 'string',
      endpoints: { invoke_url: 'string', stream_url: 'string', card_url: 'string' },
      capabilities: ['array'],
      domain: 'string',
      status: 'active|inactive',
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
print(card)`,
    },
  },
  {
    id: 'a2a-invoke',
    method: 'POST',
    path: '/api/v1/a2a/agents/{id}/invoke',
    title: 'Invoke an agent (A2A)',
    description: 'Invoke an agent via the A2A protocol — the entry point for agent-to-agent communication.',
    params: [{ name: 'id', type: 'string', description: 'Agent ID', required: true }],
    body: {
      task: { type: 'string', required: true, description: 'Task for the agent to perform' },
      capability: { type: 'string', required: false, description: 'Specific capability to use' },
      context: { type: 'object', required: false, description: 'Additional context' },
      session_id: { type: 'string', required: false, description: 'Session ID for continuity' },
      conversation_history: { type: 'array', required: false, description: 'Prior turns: [{"role", "content"}]' },
      timeout_seconds: { type: 'number', required: false, description: 'Timeout (default: 120)' },
      stream: { type: 'boolean', required: false, description: 'Stream the response (default: false)' },
    },
    response: {
      status: 'completed|failed',
      result: 'string',
      task_id: 'string',
      agent_id: 'string',
      model_used: 'string',
      tokens_used: { input: 'number', output: 'number' },
      duration_seconds: 'number',
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
print(data['result'])`,
    },
  },
  {
    id: 'mcp-tools-list',
    method: 'GET',
    path: '/api/v1/mcp/tools/list',
    title: 'List tools (MCP)',
    description: 'List all tools registered with the MCP server, with parameter schemas.',
    params: [],
    response: { tools: [{ name: 'string', description: 'string', parameters: ['array'], requires_approval: 'boolean' }], count: 'number' },
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
print(response.json()['tools'])`,
    },
  },
  {
    id: 'mcp-tools-call',
    method: 'POST',
    path: '/api/v1/mcp/tools/call',
    title: 'Call a tool (MCP)',
    description: 'Invoke an MCP tool directly by name with arguments.',
    params: [],
    body: {
      name: { type: 'string', required: true, description: 'Tool name (e.g. calculator, web_search)' },
      arguments: { type: 'object', required: false, description: 'Tool arguments' },
    },
    response: { tool: 'string', result: 'any', success: 'boolean' },
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
print(data['result'])`,
    },
  },
  {
    id: 'scheduled-runs-list',
    method: 'GET',
    path: '/api/v1/scheduled-runs',
    title: 'List scheduled runs',
    description: 'List scheduled agent runs. Non-admins see only their own runs.',
    params: [],
    response: { items: [{ id: 'string', name: 'string', agentId: 'string', prompt: 'string', cron: 'string', timezone: 'string', enabled: 'boolean' }], total: 'number' },
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
print(response.json()['items'])`,
    },
  },
  {
    id: 'scheduled-runs-create',
    method: 'POST',
    path: '/api/v1/scheduled-runs',
    title: 'Create a scheduled run',
    description: 'Schedule an agent to run a prompt on a cron cadence (requires the operator role).',
    params: [],
    body: {
      name: { type: 'string', required: true, description: 'Run name' },
      agentId: { type: 'string', required: true, description: 'Agent to run' },
      prompt: { type: 'string', required: true, description: 'Prompt sent to the agent on each run' },
      cron: { type: 'string', required: true, description: 'Cron expression (e.g. "0 9 * * 1-5")' },
      timezone: { type: 'string', required: false, description: 'IANA timezone (default: UTC)' },
      enabled: { type: 'boolean', required: false, description: 'Start enabled (default: true)' },
      maxRuntimeSeconds: { type: 'number', required: false, description: 'Per-run timeout, 5-3600 (default: 300)' },
    },
    response: { id: 'string', name: 'string', agentId: 'string', cron: 'string', timezone: 'string', enabled: 'boolean' },
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
print(run['id'])`,
    },
  },
  {
    id: 'scheduled-runs-run-now',
    method: 'POST',
    path: '/api/v1/scheduled-runs/{id}/run-now',
    title: 'Trigger a scheduled run now',
    description: 'Execute a scheduled run immediately, outside its cron cadence. History is available at GET /api/v1/scheduled-runs/{id}/history.',
    params: [{ name: 'id', type: 'string', description: 'Scheduled run ID', required: true }],
    response: { id: 'string', scheduledRunId: 'string', status: 'string', startedAt: 'string' },
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
print(response.json())`,
    },
  },
  {
    id: 'autonomy-register',
    method: 'PUT',
    path: '/api/v1/autonomy/jobs/{key}',
    title: 'Register an outside job',
    description:
      'Add a job that runs outside Brigade to the autonomy catalogue, or update it. Idempotent: a script may send it on every run. Accepts an operator session or an API key with the autonomy:report permission.',
    params: [{ name: 'key', type: 'string', required: true, description: 'The job’s slug: 3–120 lowercase letters, digits and dashes, starting and ending with a letter or digit (build-log-refresh).' }],
    body: {
      name: { type: 'string', required: true, description: '1–255 characters.' },
      responsibility: { type: 'string', required: true, description: 'What the job is responsible for, in one or two plain sentences (1–2000).' },
      agentId: { type: 'string | null', required: false, description: 'The agent it works for; must exist when given.' },
      host: { type: 'string', required: true, description: 'Where it runs: a machine name, or cloud (1–120).' },
      runner: { type: 'string', required: true, description: 'cron · systemd · launchd · claude-routine · continuous · other' },
      schedule: { type: 'string | null', required: false, description: 'Five-field cron. Leave it out for a watcher or an event-driven job.' },
      timezone: { type: 'string', required: false, description: 'IANA zone of the host’s clock (default UTC).' },
      scheduleNote: { type: 'string', required: false, description: 'Human words when there is no cron: “continuous”, “on every push” (≤255).' },
      command: { type: 'string', required: false, description: 'Script path or entry point (≤500). Never a secret: anything that looks like one is refused with 422.' },
      runbookUrl: { type: 'string', required: false, description: 'Where to look when it fails (≤500).' },
      owner: { type: 'string', required: false, description: 'Who to ask when it breaks (≤255).' },
      notes: { type: 'string', required: false, description: 'An audit’s observations (≤2000): where it was found, what is wrong. Opening with BROKEN, FAILING or ORPHAN flags the job for attention in the Command Center.' },
      enabled: { type: 'boolean', required: false, description: 'Default true. A paused job is never flagged stale.' },
    },
    response: {
      created: 'boolean',
      item: { id: 'external:build-log-refresh', source: 'external', key: 'string', name: 'string', responsibility: 'string', agentId: 'string | null', host: 'string', runner: 'string', schedule: 'string | null', timezone: 'string', nextRunAt: 'ISO-8601 | null', lastRunAt: 'ISO-8601 | null', lastStatus: 'running | success | error | timeout | skipped | null', lastError: 'string | null', notes: 'string | null', health: 'ok | failing | stale | never | paused' },
    },
    examples: {
      curl: `curl -fsS -X PUT "${API_HOST}/api/v1/autonomy/jobs/build-log-refresh" \\
  -H "X-API-Key: YOUR_REPORTER_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Build Log refresh",
    "agentId": "<agent id from the Agent Library>",
    "responsibility": "Writes the day’s Build Log story from the commits.",
    "host": "build-server",
    "runner": "cron",
    "schedule": "0 6,14,22 * * *",
    "timezone": "UTC"
  }'`,
      javascript: `const response = await fetch('${API_HOST}/api/v1/autonomy/jobs/build-log-refresh', {
  method: 'PUT',
  headers: {
    'X-API-Key': process.env.BRIGADE_REPORTER_KEY,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Build Log refresh',
    agentId: '<agent id from the Agent Library>',
    responsibility: 'Writes the day’s Build Log story from the commits.',
    host: 'build-server',
    runner: 'cron',
    schedule: '0 6,14,22 * * *',
    timezone: 'UTC'
  })
});
const { created, item } = await response.json();
console.log(created, item.health);`,
      python: `import os, requests

response = requests.put(
    '${API_HOST}/api/v1/autonomy/jobs/build-log-refresh',
    headers={'X-API-Key': os.environ['BRIGADE_REPORTER_KEY']},
    json={
        'name': 'Build Log refresh',
        'agentId': '<agent id from the Agent Library>',
        'responsibility': 'Writes the day’s Build Log story from the commits.',
        'host': 'build-server',
        'runner': 'cron',
        'schedule': '0 6,14,22 * * *',
        'timezone': 'UTC'
    }
)
print(response.json()['item']['health'])`,
    },
  },
  {
    id: 'autonomy-report',
    method: 'POST',
    path: '/api/v1/autonomy/jobs/{key}/runs',
    status: 201,
    title: 'Report a run',
    description:
      'Report one run of an outside job. Send status “running” with a runId when it starts and the same runId with the outcome when it ends — or just the outcome at the end. A success clears the job’s last error. An unknown key is a 404 that says to register it first.',
    params: [{ name: 'key', type: 'string', required: true, description: 'The key the job was registered under.' }],
    body: {
      status: { type: 'string', required: true, description: 'running · success · error · timeout · skipped' },
      runId: { type: 'string', required: false, description: 'Your idempotency key (≤120); pairs a running report with its outcome.' },
      startedAt: { type: 'ISO-8601', required: false, description: 'When the run started (default: now).' },
      finishedAt: { type: 'ISO-8601', required: false, description: 'When it finished (default: now for an outcome).' },
      summary: { type: 'string', required: false, description: 'What it did, in words (≤2000): “3 new day stories”.' },
      error: { type: 'string', required: false, description: 'Why it failed, in words (≤4000). Shown in the catalogue in red.' },
      durationMs: { type: 'number', required: false, description: '≥ 0; computed from the timestamps when left out.' },
    },
    response: {
      run: { id: 'string', runId: 'string | null', status: 'string', startedAt: 'ISO-8601', finishedAt: 'ISO-8601 | null', durationMs: 'number | null', summary: 'string | null', error: 'string | null' },
      item: { id: 'external:build-log-refresh', health: 'ok | failing | stale | never | paused', lastRunAt: 'ISO-8601', lastStatus: 'string', lastError: 'string | null' },
    },
    examples: {
      curl: `curl -fsS -X POST "${API_HOST}/api/v1/autonomy/jobs/build-log-refresh/runs" \\
  -H "X-API-Key: YOUR_REPORTER_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"status": "success", "summary": "3 new day stories"}'

# when it fails, say why in words
curl -fsS -X POST "${API_HOST}/api/v1/autonomy/jobs/build-log-refresh/runs" \\
  -H "X-API-Key: YOUR_REPORTER_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"status": "error", "error": "git fetch failed: Forgejo answered 502"}'`,
      javascript: `const response = await fetch('${API_HOST}/api/v1/autonomy/jobs/build-log-refresh/runs', {
  method: 'POST',
  headers: {
    'X-API-Key': process.env.BRIGADE_REPORTER_KEY,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ status: 'success', summary: '3 new day stories' })
});
const { run, item } = await response.json();
console.log(run.status, item.health);`,
      python: `import os, requests

response = requests.post(
    '${API_HOST}/api/v1/autonomy/jobs/build-log-refresh/runs',
    headers={'X-API-Key': os.environ['BRIGADE_REPORTER_KEY']},
    json={'status': 'success', 'summary': '3 new day stories'}
)
print(response.json()['item']['health'])`,
    },
  },
];

const GUIDE = [
  { id: 'quick-start', label: 'Quick start' },
  { id: 'authentication', label: 'Authentication' },
  { id: 'a2a', label: 'Agent-to-agent (A2A)' },
  { id: 'scheduled-runs', label: 'Scheduled runs' },
  { id: 'autonomy', label: 'Autonomous jobs' },
];

// The contract's two lines, as an outside script runs them (P-00092, autonomy catalogue).
const AUTONOMY_SCRIPT = `# once, or on every run (idempotent)
curl -fsS -X PUT "$BRIGADE_URL/api/v1/autonomy/jobs/build-log-refresh" \\
  -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \\
  -d '{"name":"Build Log refresh","agentId":"<agent id from the Agent Library>","responsibility":"Writes the day’s Build Log story from the commits.","host":"build-server","runner":"cron","schedule":"0 6,14,22 * * *","timezone":"UTC"}'
# at the end of each run
curl -fsS -X POST "$BRIGADE_URL/api/v1/autonomy/jobs/build-log-refresh/runs" \\
  -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \\
  -d '{"status":"success","summary":"3 new day stories"}'`;

const HEALTH_RULES = [
  ['Paused', 'The job is turned off. Checked first; a paused job is never anything else.'],
  ['Failing', 'Its last run ended in error or timeout, or reported a status outside that set (such as “degraded”).'],
  ['Never ran', 'Registered, but no run has been reported yet.'],
  ['Stale', 'It has a cron and has not reported for longer than 1.5 × its interval + 15 minutes (the interval is the gap between its next two fire times). A continuous job with no cron is never stale.'],
  ['OK', 'Everything else: the last run went through and it reported on time.'],
];

const NAV_GROUPS = [
  { title: 'Guide', items: GUIDE },
  { title: 'Endpoints', items: ENDPOINTS.map((e) => ({ id: e.id, label: e.title, method: e.method })) },
];

const bodyRows = (body) => Object.entries(body || {}).map(([name, v]) => ({ name, type: v.type, required: v.required, description: v.description }));

function EndpointSection({ endpoint, lang, onLang }) {
  const e = endpoint;
  return (
    <section id={e.id} className="scroll-mt-6" aria-labelledby={`${e.id}-title`}>
      <div className="flex flex-wrap items-center gap-2">
        <MethodChip method={e.method} size="sm" />
        <code className="min-w-0 break-all font-mono text-body text-fg-strong">{e.path}</code>
        <IconButton icon={Copy} label={`Copy path ${e.path}`} size="xs" onClick={() => copyText(e.path, 'Path copied')} />
      </div>
      <h2 id={`${e.id}-title`} className="mt-2 text-heading text-fg-strong">
        {e.title}
      </h2>
      <p className="mt-1 max-w-3xl text-body text-muted">{e.description}</p>
      <div className="mt-4 space-y-4">
        <ParamTable title="Path parameters" rows={e.params} />
        <ParamTable title="Query parameters" rows={e.queryParams} />
        <ParamTable title="Request body" rows={bodyRows(e.body)} />
        <div>
          <h3 className="mb-2 text-body font-semibold text-fg-strong">Response</h3>
          <CodeBlock label={`${e.status || 200} · application/json`} code={JSON.stringify(e.response, null, 2)} copyLabel="Copy response shape" />
        </div>
        <div>
          <h3 className="mb-2 text-body font-semibold text-fg-strong">Example</h3>
          <CodeBlock
            code={e.examples[lang]}
            copyLabel={`Copy ${LANGS.find((l) => l.id === lang)?.label || ''} example`}
            actions={<Tabs variant="segmented" size="sm" label={`Example language for ${e.title}`} idBase={`${e.id}-lang`} tabs={LANGS} value={lang} onChange={onLang} />}
          />
        </div>
      </div>
    </section>
  );
}

export default function ApiDocs() {
  const [lang, setLang] = useState('curl');
  const ids = useMemo(() => NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id)), []);
  const [active, jumpTo] = useActiveSection(ids);
  const topRef = useRef(null);

  return (
    <Page width="wide">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Developers"
        title="API reference"
        description="Build on Unicorn Brigade with the REST API. Every request carries an X-API-Key header; responses are JSON."
        actions={
          <span className="inline-flex items-center gap-2">
            <span className="text-caption text-muted">Base URL</span>
            <CopyChip value={BASE_URL} label="Base URL" tone="accent" />
          </span>
        }
      />

      <DocsJump groups={NAV_GROUPS} active={active} onSelect={jumpTo} />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[232px_minmax(0,1fr)]" ref={topRef}>
        <DocsNav groups={NAV_GROUPS} active={active} onSelect={jumpTo} />

        <div className="min-w-0 space-y-12">
          {/* Quick start */}
          <DocsSection id="quick-start" title="Quick start" lead="Three steps from zero to a running agent.">
            <ol className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {[
                { n: 1, icon: Key, title: 'Create an API key', text: 'Keys live in Settings → API keys. The full value is shown once, at creation.', action: <Button as={Link} to="/settings" variant="link" size="sm" icon={Settings}>Open Settings</Button> },
                { n: 2, icon: Server, title: 'Make a request', text: 'Send HTTPS requests to the base URL with your key in the X-API-Key header.' },
                { n: 3, icon: Zap, title: 'Build', text: 'Create agents, chat with them, invoke them agent-to-agent, and schedule them on a cron.' },
              ].map((s) => (
                <li key={s.n}>
                  <Card className="h-full">
                    <div className="mb-3 flex items-center gap-3">
                      <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono text-body-sm font-semibold text-accent">
                        {s.n}
                      </span>
                      <s.icon aria-hidden="true" className="h-4 w-4 text-muted" />
                      <h3 className="text-body font-semibold text-fg-strong">{s.title}</h3>
                    </div>
                    <p className="text-body-sm text-muted">{s.text}</p>
                    {s.action && <div className="mt-2">{s.action}</div>}
                  </Card>
                </li>
              ))}
            </ol>
            <div className="mt-4">
              <CodeBlock
                label="First request"
                code={`curl "${BASE_URL}/agents" \\
  -H "X-API-Key: YOUR_API_KEY"`}
              />
            </div>
          </DocsSection>

          {/* Authentication */}
          <DocsSection id="authentication" title="Authentication" lead="Every request is authenticated with a personal API key. Keys are scoped to your account and organization; revoke one in Settings and it stops working immediately.">
            <div className="space-y-3">
              <CodeBlock label="Header" code="X-API-Key: YOUR_API_KEY" copyLabel="Copy header" />
              <p className="flex items-start gap-2 text-body-sm text-muted">
                <Shield aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
                Treat a key like a password: keep it in an environment variable or a secrets manager, never in a repository or a client-side bundle.
              </p>
            </div>
          </DocsSection>

          {/* A2A */}
          <DocsSection id="a2a" title="Agent-to-agent (A2A) protocol" lead="Unicorn Brigade speaks A2A for agent discovery and invocation. Everything lives under /api/v1/a2a — server info at /api/v1/a2a/info, capability search at POST /api/v1/a2a/discover.">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Card>
                <div className="mb-2 flex items-center gap-2">
                  <MessageSquare aria-hidden="true" className="h-4 w-4 text-muted" />
                  <h3 className="text-body font-semibold text-fg-strong">Discovery</h3>
                </div>
                <p className="text-body-sm text-muted">
                  List cards with <code className="font-mono text-fg">GET /api/v1/a2a/agents</code> or fetch one agent’s capabilities with{' '}
                  <code className="font-mono text-fg">GET /api/v1/a2a/agents/{'{id}'}/card</code>.
                </p>
              </Card>
              <Card>
                <div className="mb-2 flex items-center gap-2">
                  <Zap aria-hidden="true" className="h-4 w-4 text-muted" />
                  <h3 className="text-body font-semibold text-fg-strong">Invocation</h3>
                </div>
                <p className="text-body-sm text-muted">
                  Send tasks with <code className="font-mono text-fg">POST /api/v1/a2a/agents/{'{id}'}/invoke</code> and poll async tasks at{' '}
                  <code className="font-mono text-fg">GET /api/v1/a2a/tasks/{'{task_id}'}/status</code>.
                </p>
              </Card>
            </div>
          </DocsSection>

          {/* Scheduled runs */}
          <DocsSection id="scheduled-runs" title="Scheduled runs" lead="Run any agent on a cron schedule: a watcher, a daily report, a monitoring sweep. Endpoints live under /api/v1/scheduled-runs and are owner-scoped; non-admin callers only see and manage their own runs.">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {[
                { icon: Clock, title: 'Create and manage', text: <>POST with a name, agentId, prompt and cron expression. Update with <code className="font-mono text-fg">PUT /{'{id}'}</code>, remove with <code className="font-mono text-fg">DELETE /{'{id}'}</code>.</> },
                { icon: Zap, title: 'Trigger on demand', text: <><code className="font-mono text-fg">POST /{'{id}'}/run-now</code> executes immediately without waiting for the next cron tick.</> },
                { icon: Book, title: 'Inspect history', text: <><code className="font-mono text-fg">GET /{'{id}'}/history</code> returns past executions with status and output.</> },
              ].map((c) => (
                <Card key={c.title}>
                  <div className="mb-2 flex items-center gap-2">
                    <c.icon aria-hidden="true" className="h-4 w-4 text-muted" />
                    <h3 className="text-body font-semibold text-fg-strong">{c.title}</h3>
                  </div>
                  <p className="text-body-sm text-muted">{c.text}</p>
                </Card>
              ))}
            </div>
          </DocsSection>

          {/* Autonomous jobs */}
          <DocsSection
            id="autonomy"
            title="Autonomous jobs"
            lead="One catalogue of every agent job that runs on its own: Brigade’s scheduled runs and the loops outside Brigade — a cron, a systemd timer, a LaunchAgent, a Claude Code routine, a watcher. Read it with GET /api/v1/autonomy; an outside script registers itself and reports each run with the two calls below, and the Command Center’s Autonomous view shows whose job it is, what it is responsible for, when it runs next and how its last run went."
          >
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {[
                  { icon: Repeat, title: 'Register', text: <><code className="font-mono text-fg">PUT /autonomy/jobs/{'{key}'}</code> adds or updates the job. It is idempotent, so a script can send it on every run.</> },
                  { icon: Activity, title: 'Report each run', text: <><code className="font-mono text-fg">POST /autonomy/jobs/{'{key}'}/runs</code> with the outcome, and the reason in words when it failed.</> },
                  { icon: Key, title: 'The reporter key', text: <>An API key whose permissions include <code className="font-mono text-fg">autonomy:report</code> may make these two calls and nothing else. Minting one is a deliberate step for an admin; keep it in the host’s secret store.</> },
                ].map((c) => (
                  <Card key={c.title}>
                    <div className="mb-2 flex items-center gap-2">
                      <c.icon aria-hidden="true" className="h-4 w-4 text-muted" />
                      <h3 className="text-body font-semibold text-fg-strong">{c.title}</h3>
                    </div>
                    <p className="text-body-sm text-muted">{c.text}</p>
                  </Card>
                ))}
              </div>
              <CodeBlock label="From the script (BRIGADE_URL and BRIGADE_REPORTER_KEY come from the host’s environment)" code={AUTONOMY_SCRIPT} copyLabel="Copy the two calls" />
              <div>
                <h3 className="mb-2 text-body font-semibold text-fg-strong">Health — decided by the API, in this order</h3>
                <ol className="divide-y divide-border/60 overflow-hidden rounded-card border border-border">
                  {HEALTH_RULES.map(([name, rule], i) => (
                    <li key={name} className="flex items-start gap-3 px-3 py-2">
                      <span className="w-5 shrink-0 font-mono text-caption text-muted">{i + 1}</span>
                      <span className="w-20 shrink-0 text-body-sm font-semibold text-fg-strong">{name}</span>
                      <span className="text-body-sm text-muted">{rule}</span>
                    </li>
                  ))}
                </ol>
              </div>
              <p className="text-body-sm text-muted">
                The Command Center also lists a job under <span className="text-fg">Needs attention</span> when its <code className="font-mono text-fg">notes</code> open
                with BROKEN, FAILING or ORPHAN — the fleet audit’s findings — whatever its health says.
              </p>
              <p className="flex items-start gap-2 text-body-sm text-muted">
                <Shield aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
                The command is never a secret. A command that looks like it carries one — password= or token:, a URL with user:password@, a key prefix such as sk- or ghp_ — is refused with 422: reference secrets by name instead.
              </p>
            </div>
          </DocsSection>

          {/* Endpoints */}
          <div className="space-y-12 border-t border-border pt-10">
            {ENDPOINTS.map((e) => (
              <EndpointSection key={e.id} endpoint={e} lang={lang} onLang={setLang} />
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}
