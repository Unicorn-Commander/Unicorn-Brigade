/**
 * MCP servers — what the Model Context Protocol is, which servers this
 * deployment registers (live from the registry), how to use them, how to build
 * one. Same docs layout as ApiDocs: sticky section list, one long document,
 * copyable code, honest numbers (declared tools ≠ discovered tools).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Book, ExternalLink, FileCode, GitBranch, HelpCircle, Layers, Package, Server, Zap } from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import { Button, Card, Chip, EmptyState, ErrorState, LoadingState, OfflineState, Page, PageHeader, StatCard } from '../components/ui';
import { CodeBlock, DocsJump, DocsNav, DocsSection, MethodChip, useActiveSection } from './ApiDocs';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1').replace(/\/api\/v1$/, '').replace(/\/api$/, '');

const NAV_GROUPS = [
  {
    title: 'Guide',
    items: [
      { id: 'overview', label: 'What is MCP?' },
      { id: 'servers', label: 'Registered servers' },
      { id: 'quick-start', label: 'Using a server' },
      { id: 'build', label: 'Build your own' },
      { id: 'find', label: 'Find more servers' },
      { id: 'faq', label: 'FAQ' },
    ],
  },
  {
    title: 'API',
    items: [
      { id: 'api-list', label: 'List servers', method: 'GET' },
      { id: 'api-running', label: 'Running servers', method: 'GET' },
      { id: 'api-get', label: 'Server details', method: 'GET' },
      { id: 'api-start', label: 'Start a server', method: 'POST' },
      { id: 'api-stop', label: 'Stop a server', method: 'POST' },
      { id: 'api-call', label: 'Call a tool', method: 'POST' },
    ],
  },
];

const API_ENDPOINTS = [
  { id: 'api-list', method: 'GET', path: '/api/v1/mcp/registry/servers', description: 'List all registered MCP servers.', params: [] },
  { id: 'api-running', method: 'GET', path: '/api/v1/mcp/registry/servers/running', description: 'List the servers running right now.', params: [] },
  { id: 'api-get', method: 'GET', path: '/api/v1/mcp/registry/servers/{name}', description: 'Get one server’s details.', params: [{ name: 'name', type: 'string', description: 'Server name' }] },
  { id: 'api-start', method: 'POST', path: '/api/v1/mcp/registry/servers/{name}/start', description: 'Start an MCP server.', params: [{ name: 'name', type: 'string', description: 'Server name' }] },
  { id: 'api-stop', method: 'POST', path: '/api/v1/mcp/registry/servers/{name}/stop', description: 'Stop a running server.', params: [{ name: 'name', type: 'string', description: 'Server name' }] },
  {
    id: 'api-call',
    method: 'POST',
    path: '/api/v1/mcp/registry/tools/call',
    description: 'Invoke a tool on an MCP server.',
    params: [],
    body: { server_name: '<string>', tool_name: '<string>', arguments: '<object>' },
  },
];

const FAQS = [
  { q: 'What’s the difference between built-in tools and MCP tools?', a: 'Built-in tools ship with the platform and are always available. MCP tools come from external servers that start and stop independently, so they can be added and updated without a platform release.' },
  { q: 'Which server should I use?', a: 'Browse the registered servers above. Stripe for payments, Notion for pages and databases, GitHub for repositories; each description lists its primary use.' },
  { q: 'Can I run several servers at once?', a: 'Yes. Servers are independent processes; the registry runs as many as you start.' },
  { q: 'What happens if a server fails?', a: 'The registry records the state and the error. An agent calling a tool on a stopped server gets an error response, and you can restart the server through the API or the MCP Servers page.' },
  { q: 'How do I update a server?', a: 'Most servers are npm packages (for example @modelcontextprotocol/server-github). Restart the server and npx picks up the latest version unless you pinned one.' },
  { q: 'Can I run a private server?', a: 'Yes. Build one with the MCP SDK and register it; see “Build your own” above.' },
];

const STEPS = [
  {
    title: 'Discover servers',
    text: 'List every server in the registry.',
    code: `curl -X GET "${API_BASE}/api/v1/mcp/registry/servers" \\
  -H "X-API-Key: YOUR_API_KEY"`,
  },
  {
    title: 'Configure credentials',
    text: 'Most servers need an API key in the platform’s .env before they can start.',
    code: `# GitHub
GITHUB_TOKEN=ghp_000000000000000000000000000000000000

# Stripe
STRIPE_API_KEY=sk_test_000000000000000000000000

# Notion
NOTION_API_KEY=secret_...`,
  },
  {
    title: 'Start a server',
    text: 'The server’s real tool list is discovered when it starts.',
    code: `curl -X POST "${API_BASE}/api/v1/mcp/registry/servers/stripe/start" \\
  -H "X-API-Key: YOUR_API_KEY"`,
  },
  {
    title: 'Give the tools to an agent',
    text: 'Reference MCP tools as mcp:<server>:<tool> in the agent’s tool list.',
    code: `{
  "name": "payment-agent",
  "tools": [
    "mcp:stripe:create_customer",
    "mcp:stripe:create_invoice",
    "mcp:stripe:create_payment_link"
  ]
}`,
  },
  {
    title: 'Call a tool',
    text: 'Agents call tools on their own during a conversation; you can also call one directly.',
    code: `curl -X POST "${API_BASE}/api/v1/mcp/registry/tools/call" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "server_name": "stripe",
    "tool_name": "list_customers",
    "arguments": {
      "limit": 3
    }
  }'`,
  },
];

const BUILD_OPTIONS = [
  {
    icon: Package,
    title: 'Option 1 · npm package with the official SDK',
    text: 'A standalone server over stdio.',
    label: 'server.js',
    code: `npm install @modelcontextprotocol/sdk

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
await server.connect(transport);`,
  },
  {
    icon: Server,
    title: 'Option 2 · HTTP server (Python)',
    text: 'A FastAPI server that answers tools/list and tools/call.',
    label: 'server.py',
    code: `from fastapi import FastAPI
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

# Run with: uvicorn server:app --port 8080`,
  },
  {
    icon: GitBranch,
    title: 'Option 3 · fork an existing server',
    text: 'Start from an official server and customise it.',
    label: 'shell',
    code: `# Clone an official MCP server
git clone https://github.com/modelcontextprotocol/servers
cd servers/src/filesystem

# Modify to add your custom logic
# Update package.json with your name

# Publish or use locally
npm link
npx my-custom-server`,
  },
];

const FIND = [
  { title: 'npm', text: 'Search the registry for published servers.', code: 'npm search @modelcontextprotocol' },
  { title: 'GitHub', text: 'Community servers tag themselves with a topic.', code: 'topic:mcp-server' },
  { title: 'Official registry', text: 'The protocol’s own catalogue.', href: 'https://registry.modelcontextprotocol.io', label: 'registry.modelcontextprotocol.io' },
  { title: 'Reference servers', text: 'The maintained set of example servers.', href: 'https://github.com/modelcontextprotocol/servers', label: 'modelcontextprotocol/servers' },
];

export default function MCPDocs() {
  const [servers, setServers] = useState(null); // null = loading
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);

  const load = useCallback(async () => {
    setServers(null);
    setError(null);
    try {
      const data = await apiJson('/mcp/registry/servers');
      setServers(data?.servers || []);
    } catch (err) {
      setError(err);
      setServers([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  const ids = useMemo(() => NAV_GROUPS.flatMap((g) => g.items.map((i) => i.id)), []);
  const [active, jumpTo] = useActiveSection(ids);

  const loading = servers === null;
  const list = servers || [];
  const declared = list.reduce((n, s) => n + (s.capabilities?.length || 0), 0);
  const running = list.filter((s) => s.running).length;

  const description = loading
    ? 'Loading the server registry…'
    : error
      ? 'The Model Context Protocol lets agents reach external tools. The registry couldn’t be read just now.'
      : `The Model Context Protocol lets agents reach external tools. ${list.length} registered server${list.length === 1 ? '' : 's'} · ${declared} declared tool${declared === 1 ? '' : 's'} · ${running} running.`;

  // ── servers section: the four states ───────────────────────────────────────
  let serversBody;
  if (offline && loading) {
    serversBody = <OfflineState compact onRetry={load} />;
  } else if (loading) {
    serversBody = <LoadingState variant="list" count={3} label="Loading servers" />;
  } else if (error) {
    serversBody = <ErrorState compact title="Couldn’t read the server registry" detail={humanize(error, { what: 'loading the registry' })} onRetry={load} />;
  } else if (list.length === 0) {
    serversBody = (
      <EmptyState
        compact
        icon={Server}
        title="No servers registered"
        description="Register a server on the MCP Servers page and it appears here with its declared tools."
        action={
          <Button as={Link} to="/mcp-servers" size="sm" icon={Server}>
            Open MCP servers
          </Button>
        }
      />
    );
  } else {
    serversBody = (
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-2" aria-label="Registered MCP servers">
        {list.map((s) => (
          <li key={s.name}>
            <Card className="h-full">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="text-body font-semibold text-fg-strong">{s.display_name || s.name}</h3>
                <Chip size="xs">{s.capabilities?.length || 0} declared tools</Chip>
                <Chip tone={s.running ? 'ok' : 'neutral'} size="xs" dot pulse={Boolean(s.running)}>
                  {s.running ? 'Running' : 'Stopped'}
                </Chip>
              </div>
              {s.description && <p className="text-body-sm text-muted">{s.description}</p>}
              {s.transport && <p className="mt-2 font-mono text-caption text-subtle">{s.transport}</p>}
            </Card>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Developers"
        title="MCP servers"
        description={description}
        actions={
          <Button as={Link} to="/mcp-servers" variant="secondary" icon={Server}>
            Manage servers
          </Button>
        }
      />

      {loading && !error ? (
        <div className="mb-8">
          <LoadingState variant="stats" count={3} label="Loading registry counts" />
        </div>
      ) : !error ? (
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard icon={Server} label="Registered servers" value={list.length} />
          <StatCard icon={Layers} label="Declared tools" value={declared} change="Declared by the registry; the real list is discovered at start" />
          <StatCard icon={Zap} label="Running now" value={running} tone={running ? 'ok' : 'neutral'} />
        </div>
      ) : null}

      <DocsJump groups={NAV_GROUPS} active={active} onSelect={jumpTo} />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[232px_minmax(0,1fr)]">
        <DocsNav groups={NAV_GROUPS} active={active} onSelect={jumpTo} />

        <div className="min-w-0 space-y-12">
          <DocsSection id="overview" title="What is MCP?" lead="The Model Context Protocol is an open standard that lets an AI agent connect to external tools and data sources through one interface: a universal plug for capabilities.">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {[
                { icon: Zap, title: 'One protocol', text: 'Every integration speaks the same JSON-RPC contract. No custom glue per service.' },
                { icon: Package, title: 'Plug-and-play servers', text: 'Install a server, give it credentials, start it. Its tools are ready for any agent.' },
                { icon: Layers, title: 'A large ecosystem', text: 'Hundreds of community servers exist, and the SDK makes a private one an afternoon’s work.' },
              ].map((c) => (
                <Card key={c.title}>
                  <c.icon aria-hidden="true" className="mb-3 h-5 w-5 text-accent" />
                  <h3 className="text-body font-semibold text-fg-strong">{c.title}</h3>
                  <p className="mt-1 text-body-sm text-muted">{c.text}</p>
                </Card>
              ))}
            </div>
            <p className="mt-4 rounded-control border border-info/25 bg-info/10 p-3 text-body-sm text-fg">
              <strong className="font-semibold">How it works:</strong> servers run as separate processes and talk to agents over JSON-RPC. An agent discovers the tools a server offers and calls them as it works through a conversation.
            </p>
          </DocsSection>

          <DocsSection id="servers" title="Registered servers" lead="Live from this deployment’s registry. Tool counts are what each server declares; the authoritative list is discovered from the server once it starts, and most servers need credentials first.">
            {serversBody}
          </DocsSection>

          <DocsSection id="quick-start" title="Using a server" lead="Five steps from a registered server to an agent that uses its tools.">
            <ol className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={s.title}>
                  <Card>
                    <div className="mb-3 flex items-center gap-3">
                      <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono text-body-sm font-semibold text-accent">
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-body font-semibold text-fg-strong">{s.title}</h3>
                        <p className="text-body-sm text-muted">{s.text}</p>
                      </div>
                    </div>
                    <CodeBlock code={s.code} />
                  </Card>
                </li>
              ))}
            </ol>
          </DocsSection>

          <DocsSection id="build" title="Build your own" lead="Three ways to a custom server, from a stdio package to a fork of an official one.">
            <div className="space-y-4">
              {BUILD_OPTIONS.map((o) => (
                <Card key={o.title}>
                  <div className="mb-3 flex items-center gap-2">
                    <o.icon aria-hidden="true" className="h-4 w-4 text-muted" />
                    <h3 className="text-body font-semibold text-fg-strong">{o.title}</h3>
                  </div>
                  <p className="mb-3 text-body-sm text-muted">{o.text}</p>
                  <CodeBlock label={o.label} code={o.code} />
                </Card>
              ))}
            </div>
            <p className="mt-4 text-body-sm text-muted">
              Full SDK documentation and examples:{' '}
              <Button as="a" href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer" variant="link" size="sm" iconRight={ExternalLink}>
                modelcontextprotocol.io
              </Button>
            </p>
          </DocsSection>

          <DocsSection id="find" title="Find more servers">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {FIND.map((f) => (
                <Card key={f.title}>
                  <h3 className="text-body font-semibold text-fg-strong">{f.title}</h3>
                  <p className="mt-1 text-body-sm text-muted">{f.text}</p>
                  <div className="mt-3">
                    {f.code ? (
                      <CodeBlock code={f.code} />
                    ) : (
                      <Button as="a" href={f.href} target="_blank" rel="noopener noreferrer" variant="link" size="sm" iconRight={ExternalLink}>
                        {f.label}
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </DocsSection>

          {/* API reference */}
          <div className="space-y-8 border-t border-border pt-10">
            <div>
              <h2 className="text-heading text-fg-strong">API reference</h2>
              <p className="mt-1 text-body text-muted">The registry endpoints. All take the X-API-Key header.</p>
            </div>
            {API_ENDPOINTS.map((e) => (
              <section key={e.id} id={e.id} className="scroll-mt-6" aria-labelledby={`${e.id}-title`}>
                <div className="flex flex-wrap items-center gap-2">
                  <MethodChip method={e.method} size="sm" />
                  <code className="min-w-0 break-all font-mono text-body text-fg-strong">{e.path}</code>
                </div>
                <h2 id={`${e.id}-title`} className="mt-2 text-body font-semibold text-fg-strong">
                  {e.description}
                </h2>
                {e.params.length > 0 && (
                  <dl className="mt-2 space-y-1 text-body-sm">
                    {e.params.map((p) => (
                      <div key={p.name} className="flex gap-2">
                        <dt>
                          <code className="font-mono text-accent">{p.name}</code> <span className="text-caption text-muted">{p.type}</span>
                        </dt>
                        <dd className="text-muted">{p.description}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                {e.body && (
                  <div className="mt-3">
                    <CodeBlock label="Request body" code={JSON.stringify(e.body, null, 2)} />
                  </div>
                )}
              </section>
            ))}
          </div>

          <DocsSection id="faq" title="Frequently asked questions">
            <ul className="space-y-3">
              {FAQS.map((f) => (
                <li key={f.q}>
                  <Card padding="sm">
                    <h3 className="flex items-start gap-2 text-body font-semibold text-fg-strong">
                      <HelpCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                      {f.q}
                    </h3>
                    <p className="mt-1 pl-6 text-body-sm text-muted">{f.a}</p>
                  </Card>
                </li>
              ))}
            </ul>
          </DocsSection>

          {/* Quick links */}
          <div className="grid grid-cols-1 gap-3 border-t border-border pt-8 md:grid-cols-3">
            <Card as={Link} to="/mcp-servers" interactive className="block">
              <Server aria-hidden="true" className="mb-3 h-5 w-5 text-accent" />
              <h3 className="text-body font-semibold text-fg-strong">Manage servers</h3>
              <p className="mt-1 text-body-sm text-muted">{list.length ? `Start, stop and configure the ${list.length} registered servers.` : 'Start, stop and configure servers.'}</p>
            </Card>
            <Card as={Link} to="/docs" interactive className="block">
              <Book aria-hidden="true" className="mb-3 h-5 w-5 text-accent" />
              <h3 className="text-body font-semibold text-fg-strong">API reference</h3>
              <p className="mt-1 text-body-sm text-muted">The full REST API for agents, chat, A2A and scheduled runs.</p>
            </Card>
            <Card as="a" href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer" interactive className="block">
              <FileCode aria-hidden="true" className="mb-3 h-5 w-5 text-accent" />
              <h3 className="flex items-center gap-1.5 text-body font-semibold text-fg-strong">
                MCP documentation <ExternalLink aria-hidden="true" className="h-3.5 w-3.5 text-muted" />
              </h3>
              <p className="mt-1 text-body-sm text-muted">The protocol specification and SDKs.</p>
            </Card>
          </div>
        </div>
      </div>
    </Page>
  );
}
