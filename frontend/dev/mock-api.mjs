#!/usr/bin/env node
/**
 * Unicorn Brigade — deterministic MOCK of the backend API for frontend UI lanes.
 *
 *   node frontend/dev/mock-api.mjs --port 8100 --scenario normal
 *
 * Serves everything the React app calls under /api/v1/* (and the un-versioned
 * /api/* aliases), including the orchestration SSE stream and per-agent chat
 * streaming, from the JSON fixtures in ./fixtures. No Docker, no Keycloak, no
 * credentials, no npm dependencies — node:http, node:fs, node:crypto only.
 *
 * Scenarios (CLI default; per-request override via header `X-Mock-Scenario`,
 * cookie `mock_scenario`, or query `?mock_scenario=`):
 *   normal  17 seed agents + healthy platform + a few of everything
 *   large   same, 57 agents (wide org chart like dogfood)
 *   empty   first run: zero agents / conversations / tools / workflows, no plan
 *   busy    normal + continuous orchestration SSE storylines (delegations,
 *           tool calls, one tool failure) + one workflow running
 *   error   data endpoints 500, /health 503, SSE + ticket 401
 *   slow    every response delayed 2500 ms (skeletons / loading states)
 *
 * The autonomy catalogue (GET /autonomy, PUT/DELETE /autonomy/jobs/:key,
 * POST/GET /autonomy/jobs/:key/runs) follows lane-reports/2026-10-24-brigade-uiux/
 * autonomy/CONTRACT.md: health and nextRunAt are computed per request from the
 * contract's rules with a standard 5-field cron engine (0/7 = Sunday).
 *
 * Field names follow the FastAPI handlers / SQLAlchemy to_dict() bodies under
 * app/ (camelCase vs snake_case exactly as the real API serves them). See
 * ./README.md for the endpoint coverage table and the known gaps.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
const SCENARIOS = ['normal', 'large', 'empty', 'busy', 'error', 'slow'];
const argv = process.argv.slice(2);
const opts = { port: 8100, host: '127.0.0.1', scenario: 'normal', seed: 42, slowMs: 2500, chatFirstByteMs: 450, quiet: false };
for (let i = 0; i < argv.length; i += 1) {
  const a = argv[i];
  const next = () => argv[++i];
  if (a === '--port' || a === '-p') opts.port = Number(next());
  else if (a === '--host') opts.host = next();
  else if (a === '--scenario' || a === '-s') opts.scenario = String(next() || '').toLowerCase();
  else if (a === '--seed') opts.seed = Number(next());
  else if (a === '--slow-ms') opts.slowMs = Number(next());
  else if (a === '--chat-first-byte-ms') opts.chatFirstByteMs = Number(next());
  else if (a === '--quiet' || a === '-q') opts.quiet = true;
  else if (a === '--help' || a === '-h') {
    console.log(`usage: node frontend/dev/mock-api.mjs [--port 8100] [--host 127.0.0.1] [--scenario ${SCENARIOS.join('|')}] [--seed 42] [--slow-ms 2500] [--chat-first-byte-ms 450] [--quiet]`);
    process.exit(0);
  } else {
    console.error(`[mock] unknown argument: ${a}`);
    process.exit(2);
  }
}
if (!SCENARIOS.includes(opts.scenario)) {
  console.error(`[mock] unknown scenario "${opts.scenario}" — expected one of ${SCENARIOS.join(', ')}`);
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Determinism: one NOW, one seeded PRNG
// ---------------------------------------------------------------------------
const STARTED = Date.now();
const NOW = STARTED;
function mulberry32(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(opts.seed);
const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
const randInt = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const hex = (n) => Array.from({ length: n }, () => '0123456789abcdef'[Math.floor(rnd() * 16)]).join('');
const uuid = () => `${hex(8)}-${hex(4)}-4${hex(3)}-a${hex(3)}-${hex(12)}`;
const iso = (ms = Date.now()) => new Date(ms).toISOString();
const clone = (v) => (v === undefined ? v : JSON.parse(JSON.stringify(v)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// "$now", "$now-2h30m", "$now+3d" → ISO timestamps relative to startup.
const UNIT = { s: 1e3, m: 6e4, h: 36e5, d: 864e5 };
const TIME_TOKEN = /^\$now(?:([+-])((?:\d+[smhd])+))?$/;
function resolveTimeToken(str) {
  const m = TIME_TOKEN.exec(str);
  if (!m) return str;
  let ms = 0;
  if (m[2]) for (const [, n, u] of m[2].matchAll(/(\d+)([smhd])/g)) ms += Number(n) * UNIT[u];
  return iso(NOW + (m[1] === '-' ? -ms : ms));
}
function resolveDeep(v) {
  if (typeof v === 'string') return v.startsWith('$now') ? resolveTimeToken(v) : v;
  if (Array.isArray(v)) return v.map(resolveDeep);
  if (v && typeof v === 'object') {
    const out = {};
    for (const [k, val] of Object.entries(v)) out[k] = resolveDeep(val);
    return out;
  }
  return v;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = path.join(HERE, 'fixtures');
const FX = {};
for (const f of fs.readdirSync(FIXTURES_DIR).filter((n) => n.endsWith('.json')).sort()) {
  FX[f.replace(/\.json$/, '')] = resolveDeep(JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, f), 'utf8')));
}
const need = ['agents', 'agents-large', 'tools', 'conversations', 'mcp-servers', 'workflows', 'scheduled-runs', 'monitoring', 'organization', 'billing', 'api-keys', 'attribution', 'knowledge', 'platform', 'chat-replies', 'orchestration', 'autonomy'];
for (const n of need) if (!FX[n]) throw new Error(`missing fixture ${n}.json in ${FIXTURES_DIR}`);
// The autonomy fixture keeps its "$now-…" tokens and is resolved per request
// (resolveDeepAt), so "last run 2 minutes ago" stays true however long the mock
// has been up — an ok five-minute job must not drift into "stale".
const AUTONOMY_RAW = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, 'autonomy.json'), 'utf8'));
function resolveDeepAt(v, at) {
  if (typeof v === 'string') {
    const m = TIME_TOKEN.exec(v);
    if (!m) return v;
    let ms = 0;
    if (m[2]) for (const [, n, u] of m[2].matchAll(/(\d+)([smhd])/g)) ms += Number(n) * UNIT[u];
    return iso(at + (m[1] === '-' ? -ms : ms));
  }
  if (Array.isArray(v)) return v.map((x) => resolveDeepAt(x, at));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolveDeepAt(x, at)]));
  return v;
}

const ORG_ID = FX.organization.orgId;
const PERSONAL_ORG_ID = FX.organization.personalOrgId;
const CALLER = FX.platform.auth_me;
const CATALOG = Object.fromEntries(FX.tools.catalog.map((t) => [t.name, t]));

// Mutable in-memory state (resets on restart or POST /__mock/reset). Objects
// created through the API are remembered in CREATED so the `empty` scenario
// can still show what a lane just made.
let STATE;
const CREATED = new WeakSet();
function resetState() {
  STATE = {
    agents: clone(FX.agents.agents),
    agentsLarge: clone(FX['agents-large'].agents),
    conversations: clone(FX.conversations.conversations),
    messages: clone(FX.conversations.messages),
    scheduledRuns: clone(FX['scheduled-runs'].items),
    history: clone(FX['scheduled-runs'].history),
    executions: clone(FX.workflows.executions),
    mcpRunning: new Set(FX['mcp-servers'].servers.filter((s) => s.running).map((s) => s.name).concat(FX['mcp-servers'].serversLarge.filter((s) => s.running).map((s) => s.name))),
    orgs: clone(FX.organization.orgs),
    members: clone(FX.organization.members),
    invitations: clone(FX.organization.invitations),
    userKeys: clone(FX['api-keys'].userKeys),
    agentKeys: clone(FX['api-keys'].agentKeys),
    missions: clone(FX.orchestration.missions),
    autonomyJobs: clone(AUTONOMY_RAW.jobs),
    autonomyRuns: clone(AUTONOMY_RAW.runs),
    statsCalls: 0,
    unknownPaths: new Map(),
  };
}
resetState();

// ---------------------------------------------------------------------------
// Scenario-aware data views
// ---------------------------------------------------------------------------
const isEmpty = (sc) => sc === 'empty';
const onlyCreated = (list) => list.filter((x) => CREATED.has(x));

function enrichAgent(agent) {
  // Mirrors app/api/agent_routes.py::_enrich_agent_tools + list_agents defaults.
  const a = clone(agent);
  const details = [];
  let paid = 0;
  let external = 0;
  let maxPerm = 0;
  for (const t of a.tools || []) {
    const meta = CATALOG[t] || { name: t, displayName: null, costTier: 'free', permissionLevel: 1, provider: null, external: false };
    details.push(meta);
    if (meta.costTier !== 'free') paid += 1;
    if (meta.external) external += 1;
    if ((meta.permissionLevel || 0) > maxPerm) maxPerm = meta.permissionLevel || 0;
  }
  a._count ??= { messages: 0, tasks: 0, apiKeys: 0 };
  a.agentTools ??= [];
  a.toolDetails = details;
  a.toolCostSummary = { total: details.length, paid, external, maxPermissionLevel: maxPerm };
  return a;
}
function roster(sc) {
  if (isEmpty(sc)) return onlyCreated(STATE.agents);
  return sc === 'large' ? [...STATE.agents, ...STATE.agentsLarge] : STATE.agents;
}
function findAgent(sc, id) {
  return roster(sc).find((a) => a.id === id) || STATE.agents.find((a) => a.id === id) || STATE.agentsLarge.find((a) => a.id === id) || null;
}
function domainsFor(agents) {
  const m = new Map();
  for (const a of agents) m.set(a.domain || 'general', (m.get(a.domain || 'general') || 0) + 1);
  return [...m.entries()].map(([name, count]) => ({ name, count })).sort((x, y) => y.count - x.count || x.name.localeCompare(y.name));
}
function conversations(sc) {
  const list = isEmpty(sc) ? onlyCreated(STATE.conversations) : STATE.conversations;
  return [...list].sort((a, b) => Date.parse(b.updated_at || 0) - Date.parse(a.updated_at || 0));
}
function mcpServers(sc) {
  if (isEmpty(sc)) return [];
  const base = sc === 'large' ? [...FX['mcp-servers'].servers, ...FX['mcp-servers'].serversLarge] : FX['mcp-servers'].servers;
  return base.map((s) => ({ ...s, running: STATE.mcpRunning.has(s.name) }));
}
function mcpDetail(name) {
  const d = FX['mcp-servers'].details[name] || FX['mcp-servers'].detailsLarge[name];
  return d ? { ...d, running: STATE.mcpRunning.has(name) } : null;
}
function scheduledRuns(sc) {
  return isEmpty(sc) ? onlyCreated(STATE.scheduledRuns) : STATE.scheduledRuns;
}
function executions(sc) {
  return isEmpty(sc) ? onlyCreated(STATE.executions) : STATE.executions;
}
function templates(sc) {
  return isEmpty(sc) ? [] : FX.workflows.templates;
}
function orgsFor(sc) {
  return isEmpty(sc) ? STATE.orgs.filter((o) => o.id === PERSONAL_ORG_ID) : STATE.orgs;
}
function activeOrgId(req, sc) {
  const h = req.headers['x-org-id'];
  const list = orgsFor(sc);
  if (h && list.some((o) => o.id === h)) return h;
  return (list.find((o) => !o.metadata?.personal) || list[0])?.id || null;
}
function membersFor(sc, orgId) {
  if (isEmpty(sc)) return (STATE.members[orgId] || []).filter((m) => m.userId === CALLER.id);
  return STATE.members[orgId] || [];
}
function detail(message) {
  return { detail: message };
}

// ---------------------------------------------------------------------------
// HTTP plumbing
// ---------------------------------------------------------------------------
const stamp = () => new Date().toISOString().slice(11, 23);
const log = (...a) => { if (!opts.quiet) console.log(`[mock ${stamp()}]`, ...a); };
const warn = (...a) => console.warn(`[mock ${stamp()}]`, ...a);

function parseCookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}
function corsHeaders(req) {
  const origin = req.headers.origin;
  const h = { 'Cache-Control': 'no-store', 'X-Mock-Server': 'brigade-mock' };
  if (origin) {
    h['Access-Control-Allow-Origin'] = origin;
    h['Access-Control-Allow-Credentials'] = 'true';
    h['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, X-API-Key, X-Org-Id, X-Mock-Scenario';
    h['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS';
    h.Vary = 'Origin';
  }
  return h;
}
function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); } catch { resolve({ _raw: raw }); }
    });
    req.on('error', () => resolve({}));
  });
}

// Route table. kind: data (500 in error scenario) | auth | health (503) | sse | ticket | passive
const ROUTES = [];
function route(method, pattern, handler, kind = 'data') {
  const keys = [];
  const re = new RegExp('^' + pattern
    .replace(/\/\*$/, '/(?<rest>.*)')
    .replace(/:([a-zA-Z_]+)/g, (_, k) => { keys.push(k); return `(?<${k}>[^/]+)`; }) + '/?$');
  ROUTES.push({ method, re, handler, kind, pattern });
}
const GET = (p, h, k) => route('GET', p, h, k);
const POST = (p, h, k) => route('POST', p, h, k);
const PUT = (p, h, k) => route('PUT', p, h, k);
const PATCH = (p, h, k) => route('PATCH', p, h, k);
const DELETE = (p, h, k) => route('DELETE', p, h, k);

function sendJson(ctx, status, body, extraHeaders = {}) {
  const payload = body === undefined ? '' : JSON.stringify(body);
  ctx.res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
    ...corsHeaders(ctx.req),
    ...extraHeaders,
  });
  ctx.res.end(ctx.req.method === 'HEAD' ? undefined : payload);
  ctx.status = status;
}
const ok = (ctx, body, headers) => sendJson(ctx, 200, body, headers);
const created = (ctx, body) => sendJson(ctx, 201, body);
const notFound = (ctx, msg) => sendJson(ctx, 404, detail(msg));
function noContent(ctx) {
  ctx.res.writeHead(204, corsHeaders(ctx.req));
  ctx.res.end();
  ctx.status = 204;
}
function mark(obj) {
  CREATED.add(obj);
  return obj;
}

// ---------------------------------------------------------------------------
// Orchestration SSE hub + busy storyline engine
// ---------------------------------------------------------------------------
const SSE_COOKIE = 'brigade_sse_ticket';
const TICKET_TTL_S = 60;
const tickets = new Map(); // ticket -> expiresAt (ms)
const sseClients = new Set(); // { res, scenario, missionId, id }
const recentEvents = []; // ring buffer for /orchestration/state
const liveAgentStates = new Map(); // agentId -> { status, task, name, ts }
let busyTimers = new Set();
let busyLoop = null;
let storyCount = 0;
let warnedNoTicket = false;

function sseWrite(client, obj) {
  if (client.res.destroyed || client.res.writableEnded) return false;
  client.res.write(`data: ${JSON.stringify(obj)}\n\n`);
  return true;
}
function mkEvent(type, agent, data = {}, message = '', missionId = null) {
  return {
    id: hex(8),
    type,
    timestamp: iso(),
    agentId: agent?.id || '',
    agentName: agent?.displayName || agent?.name || '',
    missionId,
    orgId: ORG_ID,
    data,
    message,
  };
}
const STATUS_BY_EVENT = {
  agent_started: 'thinking', agent_thinking: 'thinking', tool_call: 'executing', tool_result: 'thinking',
  agent_responding: 'executing', agent_completed: 'idle', agent_error: 'error',
};
function publish(evt, filter) {
  recentEvents.push(evt);
  if (recentEvents.length > 100) recentEvents.shift();
  const st = STATUS_BY_EVENT[evt.type];
  if (evt.agentId && st) {
    if (st === 'idle') liveAgentStates.delete(evt.agentId);
    else liveAgentStates.set(evt.agentId, { agentId: evt.agentId, agentName: evt.agentName, status: st, currentTask: evt.data?.task || evt.data?.tool || evt.data?.purpose || evt.message || null, currentMission: evt.missionId, lastActivity: evt.timestamp, orgId: ORG_ID });
  }
  for (const c of sseClients) {
    if (c.scenario === 'error') continue;
    if (filter && !filter(c)) continue;
    if (c.missionId && evt.missionId && c.missionId !== evt.missionId) continue;
    sseWrite(c, evt);
  }
}

function pickActors(agents) {
  const byId = new Map(agents.map((a) => [a.id, a]));
  const root = agents.find((a) => a.reportsTo == null && a.type === 'orchestrator') || agents.find((a) => a.reportsTo == null) || agents[0];
  if (!root) return null;
  const kids = (id) => agents.filter((a) => a.reportsTo === id && byId.has(a.id));
  const leads = kids(root.id).filter((l) => kids(l.id).length > 0);
  const lead = leads.length ? pick(leads) : pick(kids(root.id).length ? kids(root.id) : agents.filter((a) => a.id !== root.id));
  if (!lead) return null;
  const specs = kids(lead.id);
  const specialist = specs.length ? pick(specs) : pick(agents.filter((a) => a.id !== root.id && a.id !== lead.id)) || lead;
  return { general: root, lead, specialist };
}
function fill(str, vars) {
  return typeof str === 'string' ? str.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] ?? `{{${k}}}`)) : str;
}
function fillDeep(v, vars) {
  if (typeof v === 'string') return fill(v, vars);
  if (Array.isArray(v)) return v.map((x) => fillDeep(x, vars));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, fillDeep(x, vars)]));
  return v;
}
function runStoryline(tpl, agents, filter) {
  const actors = pickActors(agents);
  if (!actors) return;
  const vars = {
    task: pick(FX.orchestration.tasks),
    protocol: pick(['a2a', 'paid', 'internal', 'a2a']),
    specialistTool: pick(FX.orchestration.specialistTools),
  };
  const missionId = STATE.missions.find((m) => m.status === 'active')?.id || null;
  for (const step of tpl.steps) {
    const t = setTimeout(() => {
      busyTimers.delete(t);
      const actor = actors[step.actor];
      if (!actor) return;
      const name = actor.displayName || actor.name;
      let evt;
      switch (step.type) {
        case 'agent_invocation': {
          const target = actors[step.to];
          const protocol = fill(step.protocol, vars);
          const purpose = fill(step.purpose, vars);
          evt = mkEvent('agent_invocation', actor, { toAgent: target.id, toAgentName: target.displayName || target.name, purpose, protocol }, `${name} invoking ${target.displayName || target.name}: ${purpose}`, missionId);
          break;
        }
        case 'tool_call': {
          const tool = fill(step.tool, vars);
          evt = mkEvent('tool_call', actor, { tool, arguments: fillDeep(step.arguments || {}, vars) }, `Calling ${tool}`, missionId);
          break;
        }
        case 'tool_result': {
          const tool = fill(step.tool, vars);
          evt = mkEvent('tool_result', actor, { tool, result: fillDeep(step.result || {}, vars) }, `${tool} completed`, missionId);
          break;
        }
        case 'agent_error': {
          const tool = fill(step.tool, vars);
          evt = mkEvent('agent_error', actor, { tool, error: fill(step.error, vars) }, fill(step.message || step.error, vars), missionId);
          break;
        }
        case 'agent_started':
          evt = mkEvent('agent_started', actor, fillDeep(step.data || {}, vars), fill(step.message, vars) || `${name} started working`, missionId);
          break;
        case 'agent_thinking':
          evt = mkEvent('agent_thinking', actor, fillDeep(step.data || {}, vars), fill(step.message, vars) || fill(step.data?.thought, vars) || `${name} is thinking`, missionId);
          break;
        case 'agent_responding':
          evt = mkEvent('agent_responding', actor, fillDeep(step.data || {}, vars), `${name} is responding`, missionId);
          break;
        case 'agent_completed':
          evt = mkEvent('agent_completed', actor, fillDeep(step.data || {}, vars), `${name} completed task`, missionId);
          break;
        default:
          evt = mkEvent(step.type, actor, fillDeep(step.data || {}, vars), fill(step.message, vars) || '', missionId);
      }
      publish(evt, filter);
    }, step.at);
    busyTimers.add(t);
  }
}
const busyFilter = (c) => c.scenario === 'busy';
function busyClientCount() {
  let n = 0;
  for (const c of sseClients) if (c.scenario === 'busy') n += 1;
  return n;
}
function startBusyEngine() {
  if (busyLoop) return;
  const agents = roster('busy');
  if (agents.length < 3) return;
  const tpls = FX.orchestration.storylines;
  const kick = () => {
    storyCount += 1;
    // Every 4th storyline is the tool-error variant.
    const tpl = storyCount % 4 === 0 ? tpls.find((t) => t.id === 'delegation-with-tool-error') || tpls[0] : tpls[0];
    runStoryline(tpl, agents, busyFilter);
  };
  kick();
  const second = setTimeout(() => { busyTimers.delete(second); kick(); }, 1500);
  busyTimers.add(second);
  busyLoop = setInterval(kick, 4500);
  log('busy engine started (storylines every 4.5s)');
}
function stopBusyEngine() {
  if (!busyLoop) return;
  clearInterval(busyLoop);
  busyLoop = null;
  for (const t of busyTimers) clearTimeout(t);
  busyTimers = new Set();
  log('busy engine stopped (no busy clients)');
}

// ---------------------------------------------------------------------------
// Per-agent chat streaming (POST /agents/:id/chat)
// ---------------------------------------------------------------------------
function chooseReply(agent, message) {
  const replies = FX['chat-replies'].replies;
  let h = 0;
  for (const ch of `${agent.id}|${message.length}`) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const tpl = replies[h % replies.length];
  const vars = {
    agentName: agent.displayName || agent.name,
    question: message.replace(/\s+/g, ' ').trim().slice(0, 160) || '(no message)',
    domain: agent.domain || 'general',
  };
  return { tool: fillDeep(tpl.tool, vars), markdown: fill(tpl.markdown, vars) };
}
function chunkMarkdown(md) {
  // Word-ish chunks of 1–4 tokens, whitespace preserved, so markdown renders progressively.
  const tokens = md.match(/\s+|[^\s]+/g) || [md];
  const chunks = [];
  let i = 0;
  while (i < tokens.length) {
    const n = randInt(1, 4) * 2; // tokens alternate word/space
    chunks.push(tokens.slice(i, i + n).join(''));
    i += n;
  }
  return chunks;
}
async function streamChat(ctx, agent, body) {
  const { req, res } = ctx;
  const message = String(body.message || '');
  const model = body.model || agent.model;
  const { tool, markdown } = chooseReply(agent, message);
  const toolCallId = `call_${hex(12)}`;
  const chunks = chunkMarkdown(markdown);
  const perChunk = Math.max(25, Math.floor(3000 / Math.max(chunks.length, 1)));
  const timers = new Set();
  let closed = false;
  const after = (ms, fn) => { const t = setTimeout(() => { timers.delete(t); if (!closed) fn(); }, ms); timers.add(t); };
  const write = (obj) => { if (!closed && !res.destroyed) res.write(`data: ${JSON.stringify(obj)}\n\n`); };
  const stop = () => { closed = true; for (const t of timers) clearTimeout(t); };
  const t0 = Date.now();
  req.on('close', () => {
    if (!res.writableEnded) {
      stop();
      log(`chat stream ${agent.id}: aborted by client after ${Date.now() - t0}ms`);
      publish(mkEvent('agent_completed', agent, { result: '(client aborted)' }, `${agent.displayName || agent.name} stopped (aborted)`));
    }
  });

  // A model never answers in 0 ms. The pause before the first byte keeps the
  // request ordering the UI was built against (AgentChat re-loads the
  // conversation it just created; that GET must land before the stream opens).
  if (opts.chatFirstByteMs > 0) await sleep(opts.chatFirstByteMs);
  if (closed || res.destroyed) return;

  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
    ...corsHeaders(req),
  });
  res.flushHeaders?.();
  ctx.status = 200;

  log(`chat stream ${agent.id}: start (${chunks.length} chunks over ~${Math.round(chunks.length * perChunk)}ms, tool=${tool.name})`);
  write({ type: 'start', agent: agent.displayName || agent.name, model, tools: agent.tools || [] });
  publish(mkEvent('agent_started', agent, { task: message.slice(0, 200) }, `${agent.displayName || agent.name} started working`));

  let t = 300;
  after(t, () => {
    write({ type: 'tool_call', id: toolCallId, name: tool.name, arguments: tool.arguments });
    publish(mkEvent('tool_call', agent, { tool: tool.name, arguments: tool.arguments }, `Calling ${tool.name}`));
  });
  t += 800;
  after(t, () => {
    write({ type: 'tool_result', id: toolCallId, name: tool.name, result: tool.result, error: null, success: true });
    publish(mkEvent('tool_result', agent, { tool: tool.name, result: tool.result }, `${tool.name} completed`));
  });
  t += 250;
  chunks.forEach((chunk, i) => {
    after(t + i * perChunk, () => {
      if (i === 0) publish(mkEvent('agent_responding', agent, {}, `${agent.displayName || agent.name} is responding`));
      write({ type: 'token', content: chunk });
    });
  });
  t += chunks.length * perChunk + 60;
  after(t, () => {
    write({
      type: 'complete',
      content: markdown,
      model,
      toolCalls: [{ id: toolCallId, name: tool.name, arguments: tool.arguments, result: tool.result, error: null }],
    });
    res.write('data: [DONE]\n\n');
    res.end();
    stop();
    log(`chat stream ${agent.id}: complete after ${Date.now() - t0}ms (${chunks.length} chunks, tool=${tool.name})`);
    publish(mkEvent('agent_completed', agent, { result: markdown.slice(0, 500) }, `${agent.displayName || agent.name} completed task`));
  });
}

// ---------------------------------------------------------------------------
// Routes — auth / users
// ---------------------------------------------------------------------------
const AUTH_ME_UI = () => ({ ...CALLER, tier: 'founders', roles: CALLER.permissions, username: 'devuser', avatar: null });
GET('/auth/config', (ctx) => ok(ctx, FX.platform.auth_config), 'auth');
GET('/auth/me', (ctx) => ok(ctx, clone(CALLER)), 'auth');
GET('/auth/oidc/user', (ctx) => ok(ctx, AUTH_ME_UI()), 'auth');
POST('/auth/oidc/refresh', (ctx) => ok(ctx, { ok: true, expires_in: 3600, token_type: 'cookie' }), 'auth');
GET('/auth/oidc/login', (ctx) => {
  // A browser landing here (handleUnauthorized) is bounced straight back into
  // the app as a signed-in user; a JSON client gets the same URL as authUrl.
  const target = '/auth/callback?login=success';
  if (String(ctx.req.headers.accept || '').includes('application/json')) return ok(ctx, { authUrl: target });
  ctx.res.writeHead(302, { Location: target, 'Set-Cookie': 'brigade_session=mock-session; Path=/; HttpOnly; SameSite=Lax', ...corsHeaders(ctx.req) });
  ctx.res.end();
  ctx.status = 302;
}, 'auth');
const logout = (ctx) => {
  ctx.res.writeHead(302, { Location: '/login', 'Set-Cookie': 'brigade_session=; Path=/; Max-Age=0', ...corsHeaders(ctx.req) });
  ctx.res.end();
  ctx.status = 302;
};
GET('/auth/oidc/logout', logout, 'auth');
POST('/auth/oidc/logout', logout, 'auth');
GET('/auth/oidc/callback', (ctx) => { ctx.res.writeHead(302, { Location: '/auth/callback?login=success', ...corsHeaders(ctx.req) }); ctx.res.end(); ctx.status = 302; }, 'auth');
GET('/auth/oidc/permissions', (ctx) => ok(ctx, { permissions: CALLER.permissions, role: CALLER.role }), 'auth');
POST('/auth/oidc/check-permission', (ctx) => ok(ctx, { allowed: true, permission: ctx.body.permission }), 'auth');
GET('/auth/oidc/tool-access', (ctx) => ok(ctx, { allowed: true, tool: ctx.url.searchParams.get('tool') }), 'auth');
GET('/auth/oidc/upgrade-info', (ctx) => ok(ctx, FX.billing.upgrade_plan), 'auth');
GET('/users/me', (ctx) => ok(ctx, AUTH_ME_UI()), 'auth');
POST('/users/login', (ctx) => ok(ctx, { apiKey: 'brg_mock_dev_key_not_a_secret', user: AUTH_ME_UI() }), 'auth');
POST('/users/register', (ctx) => created(ctx, { apiKey: 'brg_mock_dev_key_not_a_secret', user: { ...AUTH_ME_UI(), name: ctx.body.name || 'New User', email: ctx.body.email || CALLER.email } }), 'auth');
GET('/users/me/api-keys', (ctx) => ok(ctx, { keys: isEmpty(ctx.scenario) ? onlyCreated(STATE.userKeys) : STATE.userKeys }));
POST('/users/me/api-keys', (ctx) => {
  const key = mark({
    id: uuid(), userId: CALLER.id, name: ctx.body.name || 'New key', keyPrefix: `brg_${hex(4)}`, permissions: ctx.body.permissions || ['chat', 'read'],
    rateLimit: ctx.body.rateLimit || 100, expiresAt: iso(Date.now() + (ctx.body.expiresInDays || 90) * UNIT.d), lastUsedAt: null, usageCount: 0, isActive: true, createdAt: iso(), createdVia: 'ui',
  });
  STATE.userKeys.unshift(key);
  created(ctx, { ...key, key: `${key.keyPrefix}_${hex(32)}` }); // full value shown once, mock-only
});
DELETE('/users/me/api-keys/:id', (ctx) => { STATE.userKeys = STATE.userKeys.filter((k) => k.id !== ctx.params.id); ok(ctx, { message: 'API key revoked', id: ctx.params.id }); });

// ---------------------------------------------------------------------------
// Routes — platform health / stats / models / providers
// ---------------------------------------------------------------------------
GET('/health', (ctx) => {
  if (ctx.scenario === 'error') return sendJson(ctx, 503, { ...FX.platform.health_degraded, timestamp: iso() });
  ok(ctx, { ...FX.platform.health, timestamp: iso() });
}, 'health');
GET('/system/status', (ctx) => ok(ctx, { status: 'operational', agents: roster(ctx.scenario).length, memory: { status: 'ok' }, workflows: { status: 'ok' }, timestamp: iso() }));
GET('/stats', (ctx) => {
  const agents = roster(ctx.scenario);
  const convs = conversations(ctx.scenario);
  const series = FX.monitoring.resources_series;
  const sample = series[STATE.statsCalls % series.length];
  STATE.statsCalls += 1;
  ok(ctx, {
    totalAgents: agents.length,
    activeAgents: agents.filter((a) => a.status === 'active').length,
    totalModels: isEmpty(ctx.scenario) ? 0 : FX.platform.models.length,
    totalTools: isEmpty(ctx.scenario) ? 0 : FX.tools.tools.length,
    totalConversations: convs.length,
    totalMessages: convs.reduce((n, c) => n + (c.message_count || 0), 0),
    uptime_seconds: Math.round((FX.monitoring.stats.uptime_seconds_base + (Date.now() - STARTED) / 1000) * 10) / 10,
    status: 'operational',
    version: FX.monitoring.stats.version,
    resources: { ...sample },
  });
});
GET('/monitoring/services', (ctx) => ok(ctx, { services: clone(FX.monitoring.services), checked_at: iso(), count: FX.monitoring.services.length }));
GET('/monitoring/health', (ctx) => ok(ctx, { status: 'healthy', services: clone(FX.monitoring.services), checked_at: iso() }), 'health');
POST('/monitoring/check', (ctx) => ok(ctx, { message: 'checks triggered', services: clone(FX.monitoring.services), checked_at: iso() }));
GET('/chat/models', (ctx) => {
  const models = isEmpty(ctx.scenario) ? [] : clone(FX.platform.models);
  const categories = {};
  for (const m of models) (categories[m.category || 'unknown'] ||= []).push(m);
  ok(ctx, { models, count: models.length, categories });
});
GET('/llm/models', (ctx) => ok(ctx, { models: clone(FX.platform.models), count: FX.platform.models.length, source: 'mock' }));
GET('/models/local', (ctx) => ok(ctx, { models: FX.platform.models.filter((m) => m.category === 'local'), count: FX.platform.models.filter((m) => m.category === 'local').length }));
GET('/providers', (ctx) => ok(ctx, { providers: isEmpty(ctx.scenario) ? [] : clone(FX.platform.providers), count: isEmpty(ctx.scenario) ? 0 : FX.platform.providers.length }));
GET('/providers/:id', (ctx) => { const p = FX.platform.providers.find((x) => x.id === ctx.params.id); p ? ok(ctx, p) : notFound(ctx, `Provider not found: ${ctx.params.id}`); });
POST('/providers/:id/test', (ctx) => ok(ctx, { success: true, latency_ms: 120, provider: ctx.params.id }));
POST('/chat/completions', (ctx) => {
  const content = `Mock completion for: ${(ctx.body.messages || []).at(-1)?.content || ''}`.slice(0, 500);
  ok(ctx, { id: `chatcmpl-${hex(10)}`, object: 'chat.completion', created: Math.floor(Date.now() / 1000), model: ctx.body.model || 'claude-sonnet-4', choices: [{ index: 0, message: { role: 'assistant', content }, finish_reason: 'stop' }], usage: { prompt_tokens: 42, completion_tokens: 18, total_tokens: 60 } });
});

// ---------------------------------------------------------------------------
// Routes — agents
// ---------------------------------------------------------------------------
GET('/agents', (ctx) => ok(ctx, { agents: roster(ctx.scenario).map(enrichAgent) }));
GET('/agents/domains', (ctx) => ok(ctx, { domains: domainsFor(roster(ctx.scenario)) }));
GET('/agents/hierarchy', (ctx) => {
  const edges = roster(ctx.scenario).filter((a) => a.reportsTo).map((a) => ({ agent: a.id, reportsTo: a.reportsTo }));
  ok(ctx, { edges, count: edges.length });
});
PUT('/agents/hierarchy', (ctx) => {
  const applied = [];
  for (const edit of ctx.body.edits || []) {
    const a = findAgent(ctx.scenario, edit.id);
    if (a) { a.reportsTo = edit.reportsTo ?? null; applied.push({ agent: a.id, reportsTo: a.reportsTo }); }
  }
  ok(ctx, { applied, count: applied.length });
});
GET('/agents/export/json', (ctx) => ok(ctx, roster(ctx.scenario).map(enrichAgent)));
POST('/agents/import/json', (ctx) => ok(ctx, { imported: Array.isArray(ctx.body) ? ctx.body.length : (ctx.body.agents || []).length, skipped: 0 }));
GET('/tool-catalog', (ctx) => ok(ctx, { tools: [...FX.tools.catalog].sort((a, b) => a.name.localeCompare(b.name)) }));
GET('/agents/research/sessions', (ctx) => ok(ctx, { sessions: [], count: 0 }));
GET('/agents/sql/schema', (ctx) => ok(ctx, { tables: [], count: 0 }));
GET('/agents/:id', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a || (isEmpty(ctx.scenario) && !CREATED.has(a))) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  const out = enrichAgent(a);
  out.apiKeys = STATE.agentKeys[a.id] || [];
  ok(ctx, out);
});
POST('/agents', (ctx) => {
  const b = ctx.body || {};
  const id = (b.id || b.name || `agent-${hex(6)}`).toString().toLowerCase().replace(/[^a-z0-9-]+/g, '-');
  const a = mark({
    id, name: b.name || id, displayName: b.displayName || b.name || id, title: b.title || null, rank: b.rank || null, avatar: b.avatar || '🦄', avatarUrl: b.avatarUrl || null,
    bio: b.bio || null, persona: b.persona || null, systemPrompt: b.systemPrompt || null, domain: b.domain || 'general', subdomain: b.subdomain || null, reportsTo: b.reportsTo || null,
    status: b.status || 'active', type: b.type || 'individual', agentType: b.agentType || 'analysis', capabilities: b.capabilities || [], model: b.model || 'openai/gpt-4o-mini',
    temperature: b.temperature ?? 0.7, maxTokens: b.maxTokens ?? 2000, tools: b.tools || [], orgId: b.shared ? null : ORG_ID, billingTier: b.billingTier || 'standard', rateMultiplier: b.rateMultiplier ?? 1.0,
    basePricePerCall: b.basePricePerCall ?? null, affiliation: b.affiliation || null, accessPolicy: null, createdAt: iso(), updatedAt: iso(), _count: { messages: 0, tasks: 0, apiKeys: 0 }, agentTools: [],
  });
  STATE.agents.push(a);
  created(ctx, enrichAgent(a));
});
PUT('/agents/:id', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  for (const [k, v] of Object.entries(ctx.body || {})) if (k !== 'id' && k !== '_count' && k !== 'toolDetails' && k !== 'toolCostSummary') a[k] = v;
  a.updatedAt = iso();
  ok(ctx, { ...enrichAgent(a), apiKeys: STATE.agentKeys[a.id] || [] });
});
PUT('/agents/:id/reports-to', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  a.reportsTo = ctx.body.reportsTo ?? null;
  ok(ctx, enrichAgent(a));
});
DELETE('/agents/:id', (ctx) => {
  const before = STATE.agents.length + STATE.agentsLarge.length;
  STATE.agents = STATE.agents.filter((a) => a.id !== ctx.params.id);
  STATE.agentsLarge = STATE.agentsLarge.filter((a) => a.id !== ctx.params.id);
  if (before === STATE.agents.length + STATE.agentsLarge.length) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  ok(ctx, { message: 'Agent deleted', id: ctx.params.id });
});
GET('/agents/:id/tools', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  ok(ctx, { tools: a.agentTools || [], toolNames: a.tools || [] });
});
POST('/agents/:id/tools', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  const name = ctx.body.toolId || ctx.body.tool_id || ctx.body.name || ctx.body.tool;
  if (name && !(a.tools || []).includes(name)) a.tools = [...(a.tools || []), name];
  created(ctx, { message: 'Tool attached', tools: a.tools });
});
DELETE('/agents/:id/tools/:toolId', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  a.tools = (a.tools || []).filter((t) => t !== ctx.params.toolId);
  ok(ctx, { message: 'Tool detached', tools: a.tools });
});
PATCH('/agents/:id/tools/:toolId', (ctx) => ok(ctx, { message: 'Tool configured', toolId: ctx.params.toolId, config: ctx.body }));
GET('/agents/:id/api-keys', (ctx) => ok(ctx, { keys: STATE.agentKeys[ctx.params.id] || [] }));
POST('/agents/:id/api-keys', (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  const key = mark({
    id: uuid(), agentId: a.id, orgId: ORG_ID, name: ctx.body.name || 'New key', keyPrefix: `brg_${hex(4)}`, permissions: ctx.body.permissions || ['chat', 'read'],
    rateLimit: ctx.body.rateLimit || 60, expiresAt: iso(Date.now() + (ctx.body.expiresInDays || 90) * UNIT.d), lastUsedAt: null, usageCount: 0, isActive: true, createdAt: iso(),
  });
  (STATE.agentKeys[a.id] ||= []).unshift(key);
  a._count = { ...(a._count || {}), apiKeys: STATE.agentKeys[a.id].length };
  created(ctx, { ...key, key: `${key.keyPrefix}_${hex(32)}` });
});
GET('/agents/:id/api-keys/:keyId', (ctx) => { const k = (STATE.agentKeys[ctx.params.id] || []).find((x) => x.id === ctx.params.keyId); k ? ok(ctx, k) : notFound(ctx, 'API key not found'); });
DELETE('/agents/:id/api-keys/:keyId', (ctx) => {
  STATE.agentKeys[ctx.params.id] = (STATE.agentKeys[ctx.params.id] || []).filter((k) => k.id !== ctx.params.keyId);
  ok(ctx, { message: 'API key revoked', id: ctx.params.keyId });
});
POST('/agents/:id/chat', async (ctx) => {
  const a = findAgent(ctx.scenario, ctx.params.id);
  if (!a) return notFound(ctx, `Agent not found: ${ctx.params.id}`);
  if (ctx.body.stream === false) {
    const { tool, markdown } = chooseReply(a, String(ctx.body.message || ''));
    return ok(ctx, { response: markdown, model: ctx.body.model || a.model, toolCalls: [{ id: `call_${hex(12)}`, name: tool.name, arguments: tool.arguments, result: tool.result, error: null }], usage: { prompt_tokens: 120, completion_tokens: 380, total_tokens: 500 } });
  }
  await streamChat(ctx, a, ctx.body || {});
});
POST('/agents/:id/chat/local', (ctx) => ok(ctx, { response: 'Local lane reply (mock).', model: 'uc/chat-local-p40' }));
POST('/agents/execute', (ctx) => ok(ctx, { task_id: uuid(), status: 'completed', result: 'Mock task result', tokens: 120 }));
POST('/agents/sql', (ctx) => ok(ctx, { sql: 'SELECT 1;', explanation: 'Mock SQL', confidence: 0.9 }));
POST('/agents/research', (ctx) => ok(ctx, { session_id: uuid(), status: 'completed', summary: 'Mock research summary', sources: [] }));

// ---------------------------------------------------------------------------
// Routes — conversations
// ---------------------------------------------------------------------------
GET('/conversations', (ctx) => {
  const limit = Number(ctx.url.searchParams.get('limit') || 50);
  ok(ctx, { conversations: conversations(ctx.scenario).slice(0, limit) });
});
GET('/conversations/:id', (ctx) => {
  const c = STATE.conversations.find((x) => x.id === ctx.params.id);
  if (!c || (isEmpty(ctx.scenario) && !CREATED.has(c))) return notFound(ctx, 'Conversation not found');
  ok(ctx, { ...c, messages: STATE.messages[c.id] || [] });
});
POST('/conversations', (ctx) => {
  const agent = ctx.body.agent_id ? findAgent(ctx.scenario, ctx.body.agent_id) : null;
  const c = mark({
    id: uuid(), agent_id: ctx.body.agent_id || null, user_id: CALLER.id, org_id: ORG_ID, title: ctx.body.title || null, model: ctx.body.model || agent?.model || null,
    status: 'active', message_count: 0, total_tokens: 0, created_at: iso(), updated_at: iso(),
    agent: agent ? { id: agent.id, name: agent.name, displayName: agent.displayName, avatar: agent.avatar } : null,
  });
  STATE.conversations.unshift(c);
  STATE.messages[c.id] = [];
  created(ctx, c);
});
PATCH('/conversations/:id', (ctx) => {
  const c = STATE.conversations.find((x) => x.id === ctx.params.id);
  if (!c) return notFound(ctx, 'Conversation not found');
  for (const k of ['title', 'status', 'model']) if (ctx.body[k] !== undefined) c[k] = ctx.body[k];
  c.updated_at = iso();
  ok(ctx, c);
});
DELETE('/conversations/:id', (ctx) => {
  const before = STATE.conversations.length;
  STATE.conversations = STATE.conversations.filter((x) => x.id !== ctx.params.id);
  delete STATE.messages[ctx.params.id];
  if (before === STATE.conversations.length) return notFound(ctx, 'Conversation not found');
  ok(ctx, { message: 'Conversation deleted', id: ctx.params.id });
});
POST('/conversations/:id/messages', (ctx) => {
  const c = STATE.conversations.find((x) => x.id === ctx.params.id);
  if (!c) return notFound(ctx, 'Conversation not found');
  const tokens = ctx.body.tokens_used || 0;
  const m = { id: uuid(), conversation_id: c.id, org_id: ORG_ID, role: ctx.body.role || 'user', content: ctx.body.content || '', model: ctx.body.model || null, tokens_used: tokens, tool_calls: ctx.body.tool_calls || null, tool_results: ctx.body.tool_results || null, metadata: ctx.body.metadata || null, created_at: iso() };
  (STATE.messages[c.id] ||= []).push(m);
  c.message_count = STATE.messages[c.id].length;
  c.total_tokens = (c.total_tokens || 0) + tokens;
  c.updated_at = iso();
  if (!c.title && m.role === 'user') c.title = m.content.slice(0, 60);
  created(ctx, m);
});

// ---------------------------------------------------------------------------
// Routes — tools / MCP registry
// ---------------------------------------------------------------------------
GET('/tools', (ctx) => { const tools = isEmpty(ctx.scenario) ? [] : clone(FX.tools.tools); ok(ctx, { tools, count: tools.length }); });
GET('/tools/available', (ctx) => { const tools = isEmpty(ctx.scenario) ? [] : clone(FX.tools.tools); ok(ctx, { tools, count: tools.length, permission_level: 3 }); });
POST('/tools/:id/execute', (ctx) => ok(ctx, { success: true, tool: ctx.params.id, result: { value: `mock result from ${ctx.params.id}` }, duration_ms: 42 }));
GET('/mcp/registry/servers', (ctx) => ok(ctx, { servers: mcpServers(ctx.scenario) }));
GET('/mcp/registry/servers/running', (ctx) => ok(ctx, {
  servers: mcpServers(ctx.scenario).filter((s) => s.running).map((s) => ({ name: s.name, display_name: s.display_name, pid: FX['mcp-servers'].pids[s.name] || 48000 + s.name.length, capabilities: s.capabilities })),
}));
GET('/mcp/registry/servers/:name', (ctx) => { const d = mcpDetail(ctx.params.name); d ? ok(ctx, d) : notFound(ctx, `Server not found: ${ctx.params.name}`); });
POST('/mcp/registry/servers', (ctx) => created(ctx, { status: 'registered', server: ctx.body.name || 'new-server' }));
DELETE('/mcp/registry/servers/:name', (ctx) => ok(ctx, { status: 'unregistered', server: ctx.params.name }));
POST('/mcp/registry/servers/:name/start', (ctx) => {
  if (!mcpDetail(ctx.params.name)) return notFound(ctx, `Server not found: ${ctx.params.name}`);
  const already = STATE.mcpRunning.has(ctx.params.name);
  STATE.mcpRunning.add(ctx.params.name);
  ok(ctx, { status: already ? 'already_running' : 'started', server: ctx.params.name });
});
POST('/mcp/registry/servers/:name/stop', (ctx) => {
  if (!mcpDetail(ctx.params.name)) return notFound(ctx, `Server not found: ${ctx.params.name}`);
  const was = STATE.mcpRunning.delete(ctx.params.name);
  ok(ctx, { status: was ? 'stopped' : 'not_running', server: ctx.params.name });
});
POST('/mcp/registry/servers/:name/restart', (ctx) => {
  if (!mcpDetail(ctx.params.name)) return notFound(ctx, `Server not found: ${ctx.params.name}`);
  STATE.mcpRunning.add(ctx.params.name);
  ok(ctx, { status: 'restarted', server: ctx.params.name });
});
POST('/mcp/registry/tools/call', (ctx) => ok(ctx, { success: true, server: ctx.body.server_name, tool: ctx.body.tool_name, result: { content: [{ type: 'text', text: `mock result from ${ctx.body.server_name}/${ctx.body.tool_name}` }] } }));
GET('/mcp/registry/health', (ctx) => ok(ctx, { status: 'healthy', docker_available: false, e2b_available: true, registered_servers: mcpServers(ctx.scenario).length, running_servers: mcpServers(ctx.scenario).filter((s) => s.running).length }), 'health');
GET('/mcp/registry/sandbox/status', (ctx) => ok(ctx, { docker_available: false, e2b_available: true, default: 'e2b' }));
POST('/mcp/registry/sandbox/execute', (ctx) => ok(ctx, { success: true, output: 'mock sandbox output\n', exit_code: 0, duration_ms: 310 }));
POST('/mcp/registry/sandbox/execute/fallback', (ctx) => ok(ctx, { success: true, output: 'mock sandbox output (fallback)\n', exit_code: 0, duration_ms: 290 }));
GET('/mcp/tools/list', (ctx) => ok(ctx, { tools: mcpServers(ctx.scenario).flatMap((s) => s.capabilities.map((c) => ({ server: s.name, name: c }))) }));

// ---------------------------------------------------------------------------
// Routes — hierarchical workflows / ralph
// ---------------------------------------------------------------------------
const executionTimers = new Map();
function advanceExecution(id) {
  const e = STATE.executions.find((x) => x.id === id);
  if (!e || e.state !== 'running') return;
  const order = Object.keys(e.stepExecutions);
  const running = order.find((k) => e.stepExecutions[k].state === 'running');
  if (running) {
    const s = e.stepExecutions[running];
    s.state = 'completed'; s.completedAt = iso(); s.tokensUsed = randInt(800, 4200); s.estimatedCost = Number((rnd() * 0.05).toFixed(4)); s.outputs = { result: `mock output for ${running}` };
    e.totalTokens += s.tokensUsed; e.totalCost = Number((e.totalCost + s.estimatedCost).toFixed(4));
  }
  const nextKey = order.find((k) => e.stepExecutions[k].state === 'pending');
  if (nextKey) {
    e.stepExecutions[nextKey].state = 'running'; e.stepExecutions[nextKey].startedAt = iso(); e.currentStep = nextKey;
    executionTimers.set(id, setTimeout(() => advanceExecution(id), 2500));
  } else {
    e.state = 'completed'; e.completedAt = iso(); e.currentStep = null; e.outputs = { result: 'Workflow completed (mock)' };
    executionTimers.delete(id);
  }
}
GET('/hierarchical/templates', (ctx) => {
  const tag = ctx.url.searchParams.get('tag');
  const list = templates(ctx.scenario);
  if (tag) {
    const filtered = list.filter((w) => (w.tags || []).includes(tag)).map((w) => ({ id: w.id, name: w.name, description: w.description, tags: w.tags, requiredInputs: w.required_inputs, stepCount: w.step_count, checkpointCount: w.checkpoint_count }));
    return ok(ctx, { workflows: filtered, count: filtered.length, filter: { tag } });
  }
  ok(ctx, { workflows: clone(list), count: list.length });
});
GET('/hierarchical/templates/:id', (ctx) => {
  const w = isEmpty(ctx.scenario) ? null : FX.workflows.details[ctx.params.id];
  w ? ok(ctx, { workflow: clone(w) }) : notFound(ctx, `Workflow not found: ${ctx.params.id}`);
});
GET('/hierarchical/executions', (ctx) => {
  const state = ctx.url.searchParams.get('state');
  const wf = ctx.url.searchParams.get('workflow_id');
  let list = executions(ctx.scenario);
  if (state) list = list.filter((e) => e.state === state);
  if (wf) list = list.filter((e) => e.workflowId === wf);
  list = [...list].sort((a, b) => Date.parse(b.startedAt || 0) - Date.parse(a.startedAt || 0));
  ok(ctx, { executions: clone(list), count: list.length });
});
GET('/hierarchical/executions/:id', (ctx) => {
  const e = STATE.executions.find((x) => x.id === ctx.params.id);
  e ? ok(ctx, { execution: clone(e) }) : notFound(ctx, `Execution not found: ${ctx.params.id}`);
});
POST('/hierarchical/execute', (ctx) => {
  const w = FX.workflows.details[ctx.body.workflow_id];
  if (!w) return notFound(ctx, `Workflow not found: ${ctx.body.workflow_id}`);
  const id = `exec-${hex(6)}`;
  const stepExecutions = {};
  w.steps.forEach((s, i) => {
    stepExecutions[s.id] = { stepId: s.id, state: i === 0 ? 'running' : 'pending', startedAt: i === 0 ? iso() : null, completedAt: null, executorId: s.executor, modelUsed: null, inputsReceived: {}, outputs: {}, workerCalls: 0, error: null, retries: 0, tokensUsed: 0, estimatedCost: 0 };
  });
  const e = mark({ id, workflowId: w.id, workflowName: w.name, state: 'running', currentStep: w.steps[0]?.id || null, startedAt: iso(), completedAt: null, inputs: ctx.body.inputs || {}, outputs: {}, stepExecutions, pendingCheckpoint: null, checkpointResponses: {}, error: null, totalTokens: 0, totalCost: 0, missionId: null, modelConfigUsed: ctx.body.model_config || { preset: 'balanced' } });
  STATE.executions.unshift(e);
  executionTimers.set(id, setTimeout(() => advanceExecution(id), 2500));
  ok(ctx, { execution_id: id, status: 'running', message: `Workflow '${w.name}' started`, async: ctx.body.async_execution !== false, execution: clone(e) });
});
POST('/hierarchical/executions/:id/cancel', (ctx) => {
  const e = STATE.executions.find((x) => x.id === ctx.params.id);
  if (!e) return notFound(ctx, `Execution not found: ${ctx.params.id}`);
  clearTimeout(executionTimers.get(e.id)); executionTimers.delete(e.id);
  e.state = 'cancelled'; e.completedAt = iso();
  for (const s of Object.values(e.stepExecutions)) if (s.state === 'running' || s.state === 'pending') s.state = 'cancelled';
  ok(ctx, { message: 'Execution cancelled', execution: clone(e) });
});
POST('/hierarchical/executions/:id/checkpoint', (ctx) => {
  const e = STATE.executions.find((x) => x.id === ctx.params.id);
  if (!e) return notFound(ctx, `Execution not found: ${ctx.params.id}`);
  if (e.pendingCheckpoint) e.checkpointResponses[e.pendingCheckpoint.id] = ctx.body.response || ctx.body.option || 'approve';
  e.pendingCheckpoint = null; e.state = 'running';
  const nextKey = Object.keys(e.stepExecutions).find((k) => e.stepExecutions[k].state === 'pending');
  if (nextKey) { e.stepExecutions[nextKey].state = 'running'; e.stepExecutions[nextKey].startedAt = iso(); e.currentStep = nextKey; executionTimers.set(e.id, setTimeout(() => advanceExecution(e.id), 2500)); } else { e.state = 'completed'; e.completedAt = iso(); }
  ok(ctx, { message: 'Checkpoint resolved', execution: clone(e) });
});
GET('/hierarchical/health', (ctx) => ok(ctx, {
  status: 'healthy', engine_initialized: true, template_count: templates(ctx.scenario).length, domain_count: 5, worker_count: 11,
  active_executions: executions(ctx.scenario).filter((e) => e.state === 'running').length,
  architecture: { orchestrator: 'The General (Claude Opus 4.5)', teamLeads: '5 domains', workers: '11 narrow-scope executors' },
}), 'health');
GET('/hierarchical/domains', (ctx) => {
  const leads = new Map();
  for (const w of Object.values(FX.workflows.details)) for (const tl of w.teamLeads) leads.set(tl.id, tl);
  const domains = [...leads.values()].map((tl) => ({ id: tl.id, name: tl.name, domain: tl.domain, description: tl.description, model: tl.model, workers: tl.workers.map((w) => ({ id: w.id, name: w.name, description: w.description, model: w.model })) }));
  ok(ctx, { domains, count: domains.length });
});
GET('/hierarchical/workers', (ctx) => {
  const workers = new Map();
  for (const w of Object.values(FX.workflows.details)) for (const tl of w.teamLeads) for (const wk of tl.workers) workers.set(wk.id, { ...wk, teamLead: tl.id });
  ok(ctx, { workers: [...workers.values()], count: workers.size });
});
GET('/hierarchical/models', (ctx) => ok(ctx, { models: FX.platform.models.map((m) => ({ id: m.id, name: m.display_name, tier: m.category === 'local' ? 'local' : 'frontier', provider: m.provider })), count: FX.platform.models.length }));
GET('/hierarchical/config/presets', (ctx) => ok(ctx, { presets: { cost_optimized: { description: 'Local models everywhere' }, balanced: { description: 'Frontier leads, local workers' }, quality: { description: 'Frontier everywhere' } }, count: 3 }));
POST('/hierarchical/config/estimate-cost', (ctx) => ok(ctx, { estimated_cost: 0.1842, currency: 'USD', breakdown: { orchestrator: 0.09, team_leads: 0.07, workers: 0.0242 } }));
GET('/ralph/executions', (ctx) => ok(ctx, { executions: [], count: 0 }));
GET('/ralph/executions/:id', (ctx) => notFound(ctx, `Execution not found: ${ctx.params.id}`));
POST('/ralph/execute', (ctx) => ok(ctx, { execution_id: `ralph-${hex(6)}`, status: 'running', message: 'Ralph execution started (mock)' }));

// ---------------------------------------------------------------------------
// Routes — scheduled runs
// ---------------------------------------------------------------------------
GET('/scheduled-runs', (ctx) => { const items = scheduledRuns(ctx.scenario); ok(ctx, { items: clone(items), total: items.length }); });
POST('/scheduled-runs', (ctx) => {
  const b = ctx.body || {};
  if (b.description != null && String(b.description).length > 2000) return sendJson(ctx, 422, { detail: [{ type: 'string_too_long', loc: ['body', 'description'], msg: 'String should have at most 2000 characters', input: '…' }] });
  const r = mark({ id: uuid(), name: b.name || 'New scheduled run', description: b.description || null, orgId: ORG_ID, agentId: b.agentId || null, prompt: b.prompt || '', cron: b.cron || '0 9 * * *', timezone: b.timezone || 'America/New_York', ownerUserId: b.ownerUserId || CALLER.id, enabled: b.enabled !== false, maxRuntimeSeconds: b.maxRuntimeSeconds || 300, lastRunAt: null, lastStatus: null, lastResultSummary: null, createdAt: iso(), updatedAt: iso() });
  STATE.scheduledRuns.push(r);
  STATE.history[r.id] = [];
  created(ctx, r);
});
GET('/scheduled-runs/:id', (ctx) => {
  const r = STATE.scheduledRuns.find((x) => x.id === ctx.params.id);
  if (!r) return notFound(ctx, 'scheduled run not found');
  ok(ctx, { ...r, history: (STATE.history[r.id] || []).slice(0, Number(ctx.url.searchParams.get('history_limit') || 20)) });
});
PUT('/scheduled-runs/:id', (ctx) => {
  const r = STATE.scheduledRuns.find((x) => x.id === ctx.params.id);
  if (!r) return notFound(ctx, 'scheduled run not found');
  if (ctx.body.description != null && String(ctx.body.description).length > 2000) return sendJson(ctx, 422, { detail: [{ type: 'string_too_long', loc: ['body', 'description'], msg: 'String should have at most 2000 characters', input: '…' }] });
  for (const k of ['name', 'description', 'agentId', 'prompt', 'cron', 'timezone', 'ownerUserId', 'enabled', 'maxRuntimeSeconds']) if (ctx.body[k] !== undefined) r[k] = ctx.body[k];
  r.updatedAt = iso();
  ok(ctx, r);
});
DELETE('/scheduled-runs/:id', (ctx) => {
  const before = STATE.scheduledRuns.length;
  STATE.scheduledRuns = STATE.scheduledRuns.filter((x) => x.id !== ctx.params.id);
  if (before === STATE.scheduledRuns.length) return notFound(ctx, 'scheduled run not found');
  noContent(ctx);
});
POST('/scheduled-runs/:id/run-now', (ctx) => {
  const r = STATE.scheduledRuns.find((x) => x.id === ctx.params.id);
  if (!r) return notFound(ctx, 'scheduled run not found');
  if (!r.enabled && !ctx.body.allowDisabled) return sendJson(ctx, 409, detail('scheduled run is disabled; set allowDisabled=true to run it manually'));
  const h = { id: uuid(), scheduledRunId: r.id, orgId: ORG_ID, startedAt: iso(), finishedAt: null, status: 'running', trigger: 'manual', actor: CALLER.id, outputSummary: null, error: null, toolCallsCount: 0 };
  (STATE.history[r.id] ||= []).unshift(h);
  r.lastRunAt = h.startedAt; r.lastStatus = 'running'; r.lastResultSummary = null; r.updatedAt = iso();
  setTimeout(() => {
    h.status = 'success'; h.finishedAt = iso(); h.outputSummary = 'Manual run completed (mock).'; h.toolCallsCount = randInt(1, 6);
    r.lastStatus = 'success'; r.lastResultSummary = h.outputSummary; r.updatedAt = iso();
  }, 6000).unref?.();
  ok(ctx, h);
});
GET('/scheduled-runs/:id/history', (ctx) => {
  const limit = Number(ctx.url.searchParams.get('limit') || 50);
  const offset = Number(ctx.url.searchParams.get('offset') || 0);
  const all = STATE.history[ctx.params.id] || [];
  ok(ctx, { items: clone(all.slice(offset, offset + limit)), total: all.length, limit, offset });
});
POST('/scheduled-runs/admin/reload', (ctx) => ok(ctx, { reloaded: STATE.scheduledRuns.length }));

// ---------------------------------------------------------------------------
// Cron engine (standard 5-field cron, 0/7 = Sunday; minute resolution, any
// IANA zone via Intl). Used only to compute nextRunAt and staleness below.
// NOTE: the real backend's _parse_cron hands day_of_week straight to
// APScheduler 3.10, where 0 = MONDAY — see README "Known gaps" 11.
// ---------------------------------------------------------------------------
const CRON_FIELDS = [
  { label: 'minute', min: 0, max: 59 },
  { label: 'hour', min: 0, max: 23 },
  { label: 'day', min: 1, max: 31 },
  { label: 'month', min: 1, max: 12, names: { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 } },
  { label: 'day_of_week', min: 0, max: 7, names: { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 } },
];
function parseCronExpr(expr) {
  const parts = String(expr || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length !== 5) throw new Error(`cron must be 5 fields (minute hour day month day_of_week), got: '${expr}'`);
  const sets = parts.map((spec, i) => {
    const f = CRON_FIELDS[i];
    const out = new Set();
    for (const piece of spec.split(',')) {
      const m = /^(\*|([a-z0-9]+)(?:-([a-z0-9]+))?)(?:\/(\d+))?$/i.exec(piece);
      if (!m) throw new Error(`Error validating expression '${piece}' in the ${f.label} field`);
      const step = m[4] ? Number(m[4]) : 1;
      const val = (t) => (/^\d+$/.test(t) ? Number(t) : f.names?.[t.toLowerCase()]);
      let a = f.min;
      let b = f.max;
      if (m[1] !== '*') {
        a = val(m[2]);
        b = m[3] !== undefined ? val(m[3]) : m[4] ? f.max : a;
      }
      if (step < 1 || !Number.isInteger(a) || !Number.isInteger(b) || a < f.min || b > f.max || a > b) {
        throw new Error(`the ${f.label} field value '${piece}' is outside ${f.min}-${f.max}`);
      }
      for (let v = a; v <= b; v += step) out.add(i === 4 ? v % 7 : v);
    }
    return out;
  });
  return { minute: sets[0], hour: sets[1], dom: sets[2], month: sets[3], dow: sets[4], domAny: parts[2] === '*', dowAny: parts[4] === '*' };
}
const ZONE_FMT = new Map();
const WEEKDAY = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
function zonedParts(ms, tz) {
  let fmt = ZONE_FMT.get(tz);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', weekday: 'short' });
    ZONE_FMT.set(tz, fmt);
  }
  const p = {};
  for (const { type, value } of fmt.formatToParts(new Date(ms))) p[type] = value;
  return { month: Number(p.month), day: Number(p.day), hour: Number(p.hour) % 24, minute: Number(p.minute), dow: WEEKDAY[p.weekday] };
}
/** The first fire time strictly after fromMs (ms), or null within ~1 year. */
function cronNext(expr, tz, fromMs) {
  const c = typeof expr === 'string' ? parseCronExpr(expr) : expr;
  let t = Math.floor(fromMs / 60000) * 60000 + 60000;
  for (let i = 0; i < 250000; i += 1) {
    const p = zonedParts(t, tz);
    const domOk = c.dom.has(p.day);
    const dowOk = c.dow.has(p.dow);
    // Vixie semantics: when both day fields are restricted, either may match.
    const dayOk = c.month.has(p.month) && (c.domAny && c.dowAny ? true : c.domAny ? dowOk : c.dowAny ? domOk : domOk || dowOk);
    if (!dayOk) {
      let next = t + (24 * 60 - (p.hour * 60 + p.minute)) * 60000;
      const q = zonedParts(next, tz);
      if (q.day !== p.day && (q.hour || q.minute)) next -= (q.hour * 60 + q.minute) * 60000; // DST: don't skip past midnight
      t = next > t ? next : t + 60000;
      continue;
    }
    if (!c.hour.has(p.hour)) { t += (60 - p.minute) * 60000; continue; }
    if (!c.minute.has(p.minute)) { t += 60000; continue; }
    return t;
  }
  return null;
}
/** The latest fire time at or before `now` (ms), or null — searched in widening windows. */
function cronPrev(expr, tz, now) {
  const c = typeof expr === 'string' ? parseCronExpr(expr) : expr;
  for (const back of [2 * UNIT.h, UNIT.d + UNIT.h, 8 * UNIT.d, 32 * UNIT.d, 370 * UNIT.d]) {
    let t = cronNext(c, tz, now - back);
    let last = null;
    for (let guard = 0; t != null && t <= now && guard < 3000; guard += 1) {
      last = t;
      t = cronNext(c, tz, t);
    }
    if (last != null) return last;
  }
  return null;
}
// "$lastFire", "$lastFire+94s", "$lastFire-1d": relative to the job's most recent
// scheduled fire, so a healthy fixture job reads as on schedule at any hour.
const FIRE_TOKEN = /^\$lastFire(?:([+-])((?:\d+[smhd])+))?$/;
function resolveFireTokens(v, fire) {
  if (typeof v === 'string') {
    const m = FIRE_TOKEN.exec(v);
    if (!m || fire == null) return v;
    let ms = 0;
    if (m[2]) for (const [, n, u] of m[2].matchAll(/(\d+)([smhd])/g)) ms += Number(n) * UNIT[u];
    return iso(fire + (m[1] === '-' ? -ms : ms));
  }
  if (Array.isArray(v)) return v.map((x) => resolveFireTokens(x, fire));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolveFireTokens(x, fire)]));
  return v;
}
function lastFireOf(job, now) {
  if (!job.schedule) return null;
  try { return cronPrev(job.schedule, job.timezone || 'UTC', now); } catch { return null; }
}
function validTimezone(tz) {
  try { new Intl.DateTimeFormat('en-US', { timeZone: tz }); return true; } catch { return false; }
}

// ---------------------------------------------------------------------------
// Routes — autonomy catalogue (every agent job that runs on its own)
// ---------------------------------------------------------------------------
const AUTONOMY_RUNNERS = ['cron', 'systemd', 'launchd', 'claude-routine', 'continuous', 'other'];
const AUTONOMY_STATUSES = ['running', 'success', 'error', 'timeout', 'skipped'];
const AUTONOMY_KEY_RE = /^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$/;
// The secret check, as the backend lane implements it (app/services/autonomy.py):
// key shapes anchored at a token boundary with a minimum length, so
// "disk-guard.sh" or "kiosk-chromium-refresh" (which contain "sk-") pass.
const AUTONOMY_SECRET_RES = [
  /(password|passwd|secret|token|api[_-]?key)\s*[=:]/i,
  /:\/\/[^/\s:]+:[^@\s]+@/,
  /(?<![A-Za-z0-9])(?:(?:sk|ubk|sbk)-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abposr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})/,
];
const AUTONOMY_SECRET_FIELDS = { command: 'command', runbookUrl: 'runbook URL', notes: 'notes' };
const HEALTH_RANK = { failing: 0, stale: 1, never: 2, ok: 3, paused: 4 };
// Real Brigade rows carry statuses outside the contract's enum ("degraded"); the
// backend maps those to failing (coordinator, 2026-10-24) and so does the mock.
const KNOWN_STATUSES = ['running', 'success', 'error', 'timeout', 'skipped'];
const failedStatus = (s) => s === 'error' || s === 'timeout' || (Boolean(s) && !KNOWN_STATUSES.includes(s));

function autonomyJobs(sc) {
  return isEmpty(sc) ? onlyCreated(STATE.autonomyJobs) : STATE.autonomyJobs;
}
function findJob(sc, key) {
  return autonomyJobs(sc).find((j) => j.key === key) || null;
}
function agentBrief(sc, id) {
  if (!id) return null;
  const a = roster(sc).find((x) => x.id === id);
  return a ? { id: a.id, name: a.name, displayName: a.displayName || a.name, title: a.title || null, domain: a.domain || null, avatarUrl: a.avatarUrl || null } : null;
}
/**
 * nextRunAt, and when a job that last ran at lastRunAt turns stale: the first
 * fire time after that run, plus half the gap to the fire after it, plus 15 min
 * — the contract's "1.5 × interval + 15 min" anchored on the schedule, as the
 * backend lane computes it (no weekend false alarms for weekday jobs).
 */
function cronFacts(schedule, tz, enabled, now, lastRunAt) {
  if (!schedule) return { nextRunAt: null, staleAt: null };
  try {
    const c = parseCronExpr(schedule);
    const zone = tz || 'UTC';
    const n1 = cronNext(c, zone, now);
    let staleAt = null;
    if (lastRunAt) {
      const expected = cronNext(c, zone, Date.parse(lastRunAt));
      const after = expected == null ? null : cronNext(c, zone, expected);
      if (expected != null) staleAt = expected + (after != null ? (after - expected) / 2 : 0) + 15 * 60000;
    }
    return { nextRunAt: enabled && n1 != null ? iso(n1) : null, staleAt };
  } catch {
    return { nextRunAt: null, staleAt: null };
  }
}
/** The contract's order: paused → failing (incl. statuses outside the enum) → never → stale → ok. */
function healthOf(it, staleAt, now) {
  if (!it.enabled) return 'paused';
  if (failedStatus(it.lastStatus)) return 'failing';
  if (!it.lastRunAt) return 'never';
  if (staleAt != null && now > staleAt) return 'stale';
  return 'ok';
}
function brigadeItem(sc, run, now) {
  const summary = run.lastResultSummary ? String(run.lastResultSummary).slice(0, 280) : null;
  const { nextRunAt, staleAt } = cronFacts(run.cron, run.timezone, run.enabled, now, run.lastRunAt);
  const it = {
    id: `brigade:${run.id}`, source: 'brigade', key: run.id, name: run.name, responsibility: run.description || null,
    agentId: run.agentId || null, agent: agentBrief(sc, run.agentId), host: 'brigade', runner: 'brigade-scheduler',
    schedule: run.cron || null, timezone: run.timezone || 'America/New_York', scheduleNote: null, nextRunAt, enabled: Boolean(run.enabled),
    lastRunAt: run.lastRunAt || null, lastStatus: run.lastStatus || null, lastSummary: summary,
    lastError: failedStatus(run.lastStatus) ? summary : null, lastDurationMs: null,
    command: null, runbookUrl: null, owner: null, notes: null, scheduledRunId: run.id, updatedAt: run.updatedAt || null,
  };
  it.health = healthOf(it, staleAt, now);
  return it;
}
/** A job as the API would read it right now: tokens resolved; in `busy` the Build Log refresh is mid-run. */
function jobNow(sc, job, now) {
  const j = resolveFireTokens(resolveDeepAt(job, now), lastFireOf(job, now));
  if (sc === 'busy' && j.key === 'build-log-refresh') Object.assign(j, { lastStatus: 'running', lastRunAt: iso(now - 40000), lastSummary: null, lastError: null, lastDurationMs: null });
  return j;
}
function externalItem(sc, job, now) {
  const j = jobNow(sc, job, now);
  const { nextRunAt, staleAt } = cronFacts(j.schedule, j.timezone, j.enabled !== false, now, j.lastRunAt);
  const it = {
    id: `external:${j.key}`, source: 'external', key: j.key, name: j.name, responsibility: j.responsibility,
    agentId: j.agentId || null, agent: agentBrief(sc, j.agentId), host: j.host, runner: j.runner,
    schedule: j.schedule || null, timezone: j.timezone || 'UTC', scheduleNote: j.scheduleNote || null, nextRunAt, enabled: j.enabled !== false,
    lastRunAt: j.lastRunAt || null, lastStatus: j.lastStatus || null, lastSummary: j.lastSummary || null, lastError: j.lastError || null,
    lastDurationMs: j.lastDurationMs ?? null, command: j.command || null, runbookUrl: j.runbookUrl || null, owner: j.owner || null,
    notes: j.notes || null, scheduledRunId: null, updatedAt: j.updatedAt || null,
  };
  it.health = healthOf(it, staleAt, now);
  return it;
}
function catalogue(sc) {
  const now = Date.now();
  const items = [...scheduledRuns(sc).map((r) => brigadeItem(sc, r, now)), ...autonomyJobs(sc).map((j) => externalItem(sc, j, now))];
  const agentName = (it) => String(it.agent?.displayName || it.agent?.name || '').toLowerCase();
  items.sort((a, b) => HEALTH_RANK[a.health] - HEALTH_RANK[b.health] || agentName(a).localeCompare(agentName(b)) || a.name.localeCompare(b.name));
  const counts = { total: items.length, brigade: 0, external: 0, failing: 0, stale: 0, paused: 0, never: 0 };
  for (const it of items) {
    counts[it.source] += 1;
    if (counts[it.health] !== undefined) counts[it.health] += 1;
  }
  return { items, counts, generatedAt: iso(now) };
}
const publicRun = (r) => ({ id: r.id, runId: r.runId ?? null, status: r.status, startedAt: r.startedAt, finishedAt: r.finishedAt ?? null, durationMs: r.durationMs ?? null, summary: r.summary ?? null, error: r.error ?? null });
/** FastAPI/pydantic-v2-shaped 422 for schema problems (missing, too long, wrong type, not in the enum). */
function schemaErrors(body, spec) {
  const errs = [];
  for (const [name, rule] of Object.entries(spec)) {
    const v = body[name];
    const missing = v === undefined || v === null || (typeof v === 'string' && !v.trim());
    if (rule.required && missing) { errs.push({ type: 'missing', loc: ['body', name], msg: 'Field required', input: v ?? null }); continue; }
    if (missing) continue;
    if (rule.type === 'string' && typeof v !== 'string') errs.push({ type: 'string_type', loc: ['body', name], msg: 'Input should be a valid string', input: v });
    else if (rule.type === 'bool' && typeof v !== 'boolean') errs.push({ type: 'bool_type', loc: ['body', name], msg: 'Input should be a valid boolean', input: v });
    else if (rule.type === 'int' && (!Number.isInteger(v) || v < 0)) errs.push({ type: 'greater_than_equal', loc: ['body', name], msg: 'Input should be greater than or equal to 0', input: v });
    else if (rule.max && String(v).length > rule.max) errs.push({ type: 'string_too_long', loc: ['body', name], msg: `String should have at most ${rule.max} characters`, input: '…' });
    else if (rule.oneOf && !rule.oneOf.includes(v)) errs.push({ type: 'literal_error', loc: ['body', name], msg: `Input should be ${rule.oneOf.map((x) => `'${x}'`).join(', ')}`, input: v });
  }
  return errs;
}

GET('/autonomy', (ctx) => ok(ctx, catalogue(ctx.scenario)));

PUT('/autonomy/jobs/:key', (ctx) => {
  const key = ctx.params.key;
  if (!AUTONOMY_KEY_RE.test(key)) return sendJson(ctx, 422, detail(`“${key}” isn't a valid job key: use 3–120 lowercase letters, digits and dashes, starting and ending with a letter or digit.`));
  const b = ctx.body && typeof ctx.body === 'object' && !ctx.body._raw ? ctx.body : {};
  const errs = schemaErrors(b, {
    name: { required: true, type: 'string', max: 255 },
    responsibility: { required: true, type: 'string', max: 2000 },
    agentId: { type: 'string', max: 255 },
    host: { required: true, type: 'string', max: 120 },
    runner: { required: true, type: 'string', oneOf: AUTONOMY_RUNNERS },
    schedule: { type: 'string', max: 120 },
    timezone: { type: 'string', max: 64 },
    scheduleNote: { type: 'string', max: 255 },
    command: { type: 'string', max: 500 },
    runbookUrl: { type: 'string', max: 500 },
    owner: { type: 'string', max: 255 },
    notes: { type: 'string', max: 2000 },
    enabled: { type: 'bool' },
  });
  if (errs.length) return sendJson(ctx, 422, { detail: errs });
  const tz = b.timezone || 'UTC';
  if (b.agentId && !roster(ctx.scenario).some((a) => a.id === b.agentId)) return sendJson(ctx, 422, detail(`No agent '${b.agentId}' in Brigade's roster.`));
  if (b.schedule) {
    try { parseCronExpr(b.schedule); } catch (e) { return sendJson(ctx, 422, detail(`That schedule isn't a valid cron: ${e.message}.`)); }
  }
  if (!validTimezone(tz)) return sendJson(ctx, 422, detail(`“${tz}” isn't a time zone the server knows. Use an IANA name like America/New_York or UTC.`));
  for (const [field, words] of Object.entries(AUTONOMY_SECRET_FIELDS)) {
    if (b[field] && AUTONOMY_SECRET_RES.some((re) => re.test(b[field]))) return sendJson(ctx, 422, detail(`Don't store secrets in the ${words}; reference them by name.`));
  }
  const fields = {
    name: b.name.trim(), responsibility: b.responsibility.trim(), agentId: b.agentId || null, host: b.host.trim(), runner: b.runner,
    schedule: b.schedule ? b.schedule.trim() : null, timezone: tz, scheduleNote: b.scheduleNote || null, command: b.command || null,
    runbookUrl: b.runbookUrl || null, owner: b.owner || null, notes: b.notes || null, enabled: b.enabled !== false,
  };
  let job = STATE.autonomyJobs.find((j) => j.key === key);
  const isNew = !job || (isEmpty(ctx.scenario) && !CREATED.has(job));
  if (!job) {
    job = mark({ key, ...fields, lastRunAt: null, lastStatus: null, lastSummary: null, lastError: null, lastDurationMs: null, createdAt: iso(), updatedAt: iso() });
    STATE.autonomyJobs.push(job);
    STATE.autonomyRuns[key] = [];
  } else {
    Object.assign(job, fields, { updatedAt: iso() });
    if (isNew) mark(job);
  }
  ok(ctx, { created: isNew, item: externalItem(ctx.scenario, job, Date.now()) });
});

DELETE('/autonomy/jobs/:key', (ctx) => {
  const key = ctx.params.key;
  const job = findJob(ctx.scenario, key);
  if (!job) return notFound(ctx, `No job '${key}'.`);
  STATE.autonomyJobs = STATE.autonomyJobs.filter((j) => j !== job);
  delete STATE.autonomyRuns[key];
  noContent(ctx);
});

POST('/autonomy/jobs/:key/runs', (ctx) => {
  const key = ctx.params.key;
  const job = findJob(ctx.scenario, key);
  if (!job) return notFound(ctx, `No job '${key}'. Register it with PUT /api/v1/autonomy/jobs/${key} first.`);
  const b = ctx.body && typeof ctx.body === 'object' && !ctx.body._raw ? ctx.body : {};
  const errs = schemaErrors(b, {
    status: { required: true, type: 'string', oneOf: AUTONOMY_STATUSES },
    runId: { type: 'string', max: 120 },
    startedAt: { type: 'string' },
    finishedAt: { type: 'string' },
    summary: { type: 'string', max: 2000 },
    error: { type: 'string', max: 4000 },
    durationMs: { type: 'int' },
  });
  for (const k of ['startedAt', 'finishedAt']) if (b[k] && Number.isNaN(Date.parse(b[k]))) errs.push({ type: 'datetime_parsing', loc: ['body', k], msg: 'Input should be a valid datetime', input: b[k] });
  if (errs.length) return sendJson(ctx, 422, { detail: errs });
  const now = iso();
  const runs = (STATE.autonomyRuns[key] ||= []);
  let run = null;
  if (b.status !== 'running' && b.runId) run = runs.find((r) => r.runId === b.runId && r.status === 'running') || null;
  if (run) {
    run.status = b.status;
    run.finishedAt = b.finishedAt || now;
    run.summary = b.summary ?? run.summary ?? null;
    run.error = b.error ?? null;
    run.durationMs = b.durationMs ?? Math.max(0, Date.parse(run.finishedAt) - Date.parse(resolveFireTokens(resolveDeepAt(run.startedAt, Date.now()), lastFireOf(job, Date.now()))));
  } else {
    const startedAt = b.startedAt || now;
    const finishedAt = b.status === 'running' ? null : b.finishedAt || now;
    run = { id: uuid(), runId: b.runId || null, status: b.status, startedAt, finishedAt, durationMs: b.durationMs ?? (b.startedAt && finishedAt ? Math.max(0, Date.parse(finishedAt) - Date.parse(b.startedAt)) : null), summary: b.summary ?? null, error: b.error ?? null, createdAt: now };
    runs.unshift(run);
    runs.splice(200); // keep at most 200 runs per job
  }
  Object.assign(job, {
    lastRunAt: b.finishedAt || b.startedAt || now,
    lastStatus: b.status,
    lastSummary: b.summary ?? null,
    lastError: b.status === 'success' ? null : b.error ?? (b.status === 'running' ? job.lastError : null),
    lastDurationMs: run.durationMs ?? null,
    updatedAt: now,
  });
  sendJson(ctx, 201, { run: publicRun(resolveFireTokens(resolveDeepAt(run, Date.now()), lastFireOf(job, Date.now()))), item: externalItem(ctx.scenario, job, Date.now()) });
});

GET('/autonomy/jobs/:key/runs', (ctx) => {
  const key = ctx.params.key;
  const job = findJob(ctx.scenario, key);
  if (!job) return notFound(ctx, `No job '${key}'. Register it with PUT /api/v1/autonomy/jobs/${key} first.`);
  const limit = Math.min(100, Math.max(1, Number(ctx.url.searchParams.get('limit') || 20) || 20));
  const now = Date.now();
  let runs = resolveFireTokens(resolveDeepAt(STATE.autonomyRuns[key] || [], now), lastFireOf(job, now)).map(publicRun);
  if (STATE.autonomyRuns[key] === undefined && job.lastRunAt) {
    const j = jobNow(ctx.scenario, job, now);
    const finished = Date.parse(j.lastRunAt);
    runs = [{ id: `last-${key}`, runId: null, status: j.lastStatus || 'success', startedAt: iso(finished - (j.lastDurationMs || 0)), finishedAt: j.lastRunAt, durationMs: j.lastDurationMs ?? null, summary: j.lastSummary || null, error: j.lastError || null }];
  }
  if (ctx.scenario === 'busy' && key === 'build-log-refresh') runs = [{ id: 'busy-running-build-log', runId: 'blr-now', status: 'running', startedAt: iso(now - 40000), finishedAt: null, durationMs: null, summary: null, error: null }, ...runs];
  runs.sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
  ok(ctx, { runs: runs.slice(0, limit) });
});

// ---------------------------------------------------------------------------
// Routes — orchestration (SSE ticket + stream, state, missions)
// ---------------------------------------------------------------------------
POST('/orchestration/events/ticket', (ctx) => {
  if (ctx.scenario === 'error') return sendJson(ctx, 401, detail('Not authenticated (mock error scenario refuses the live feed)'));
  const ticket = crypto.randomBytes(16).toString('hex');
  tickets.set(ticket, Date.now() + TICKET_TTL_S * 1000);
  ok(ctx, { ticket, expires_in: TICKET_TTL_S }, {
    'Set-Cookie': `${SSE_COOKIE}=${ticket}; Path=/api/v1/orchestration; HttpOnly; SameSite=Lax; Max-Age=${TICKET_TTL_S}`,
  });
}, 'ticket');
GET('/orchestration/events', (ctx) => {
  const { req, res } = ctx;
  if (ctx.scenario === 'error') return sendJson(ctx, 401, detail('Not authenticated (mock error scenario refuses the live feed)'));
  const presented = ctx.url.searchParams.get('ticket') || parseCookies(req)[SSE_COOKIE] || null;
  if (presented) {
    const exp = tickets.get(presented);
    tickets.delete(presented); // single use
    if (!exp || exp < Date.now()) log('SSE: ticket unknown/expired — accepting anyway (mock is lenient)');
  } else if (!warnedNoTicket) {
    warnedNoTicket = true;
    log('SSE: stream opened without a ticket — accepting (mock is lenient; the real API would 401)');
  }
  const missionId = ctx.url.searchParams.get('mission_id') || null;
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
    ...corsHeaders(req),
  });
  res.flushHeaders?.();
  req.socket.setTimeout(0);
  req.socket.setNoDelay(true);
  ctx.status = 200;
  const client = { res, scenario: ctx.scenario, missionId, id: hex(6) };
  sseClients.add(client);
  sseWrite(client, { type: 'connected', mission_id: missionId });
  const ping = setInterval(() => { if (!res.destroyed) res.write(': ping\n\n'); }, 15000);
  const cleanup = () => {
    clearInterval(ping);
    sseClients.delete(client);
    if (busyClientCount() === 0) stopBusyEngine();
    log(`SSE client ${client.id} closed (${sseClients.size} open)`);
  };
  req.on('close', cleanup);
  res.on('error', cleanup);
  log(`SSE client ${client.id} connected (${ctx.scenario}, ${sseClients.size} open)`);
  if (ctx.scenario === 'busy') startBusyEngine();
}, 'sse');
function stateSnapshot(sc) {
  const agents = roster(sc);
  const ids = new Set(agents.map((a) => a.id));
  const byId = new Map(agents.map((a) => [a.id, a]));
  const agentStates = [...liveAgentStates.values()].filter((s) => ids.has(s.agentId)).map((s) => ({ ...s, agent: enrichAgent(byId.get(s.agentId)) }));
  const missions = isEmpty(sc) ? [] : clone(STATE.missions);
  return {
    missions,
    agentStates,
    recentEvents: recentEvents.slice(-50).filter((e) => !e.agentId || ids.has(e.agentId)),
    activeAgentCount: agentStates.length,
    activeMissionCount: missions.filter((m) => m.status === 'active').length,
    totalAgents: agents.length,
  };
}
GET('/orchestration/state', (ctx) => ok(ctx, stateSnapshot(ctx.scenario)));
GET('/orchestration/agents/active', (ctx) => { const s = stateSnapshot(ctx.scenario); ok(ctx, { agents: s.agentStates, count: s.agentStates.length }); });
GET('/orchestration/missions', (ctx) => ok(ctx, { missions: isEmpty(ctx.scenario) ? [] : clone(STATE.missions) }));
GET('/orchestration/missions/:id', (ctx) => { const m = STATE.missions.find((x) => x.id === ctx.params.id); m ? ok(ctx, { mission: m, events: recentEvents.filter((e) => e.missionId === m.id).slice(-50) }) : notFound(ctx, `Mission not found: ${ctx.params.id}`); });
POST('/orchestration/missions', (ctx) => {
  const agents = roster(ctx.scenario);
  const root = agents.find((a) => a.reportsTo == null) || agents[0];
  const m = mark({ id: `mission-${hex(6)}`, name: ctx.body.name || 'New mission', description: ctx.body.task || ctx.body.description || '', status: 'active', progress: 0, agents: root ? [root.id] : [], leadAgent: root?.id || null, createdAt: iso(), updatedAt: iso(), completedAt: null, orgId: ORG_ID });
  STATE.missions.unshift(m);
  publish({ ...mkEvent('mission_created', root, { mission: m }, `Mission '${m.name}' created`, m.id) });
  created(ctx, { mission: m, message: `Mission '${m.name}' created` });
});
POST('/orchestration/command', (ctx) => ok(ctx, { status: 'accepted', commandId: `cmd-${hex(6)}`, message: `Command accepted: ${String(ctx.body.command || ctx.body.task || '').slice(0, 80)}` }));
POST('/orchestration/agents/create', (ctx) => created(ctx, { agent: { id: `agent-${hex(6)}`, ...ctx.body }, message: 'Agent created (mock)' }));

// ---------------------------------------------------------------------------
// Routes — organizations
// ---------------------------------------------------------------------------
GET('/orgs', (ctx) => ok(ctx, { orgs: clone(orgsFor(ctx.scenario)) }));
GET('/orgs/current', (ctx) => {
  const id = activeOrgId(ctx.req, ctx.scenario);
  const org = orgsFor(ctx.scenario).find((o) => o.id === id);
  org ? ok(ctx, clone(org)) : notFound(ctx, 'No active organization');
});
POST('/orgs', (ctx) => {
  const name = ctx.body.name || 'New org';
  const org = mark({ id: uuid(), name, slug: ctx.body.slug || name.toLowerCase().replace(/[^a-z0-9]+/g, '-'), planTier: 'free', apiCallsLimit: 5000, metadata: {}, createdAt: iso(), updatedAt: iso(), role: 'owner' });
  STATE.orgs.push(org);
  STATE.members[org.id] = [{ userId: CALLER.id, email: CALLER.email, name: CALLER.name, role: 'owner', joinedAt: iso() }];
  STATE.invitations[org.id] = [];
  created(ctx, org);
});
GET('/orgs/invitations/accept', (ctx) => ok(ctx, { status: 'pending', message: 'POST the token to accept' }));
POST('/orgs/invitations/accept', (ctx) => ok(ctx, { status: 'accepted', orgId: ORG_ID, role: 'member', userId: CALLER.id }));
GET('/orgs/:id', (ctx) => { const o = STATE.orgs.find((x) => x.id === ctx.params.id); o ? ok(ctx, clone(o)) : notFound(ctx, 'Organization not found'); });
PATCH('/orgs/:id', (ctx) => {
  const o = STATE.orgs.find((x) => x.id === ctx.params.id);
  if (!o) return notFound(ctx, 'Organization not found');
  for (const k of ['name', 'slug']) if (ctx.body[k] !== undefined) o[k] = ctx.body[k];
  o.updatedAt = iso();
  ok(ctx, clone(o));
});
GET('/orgs/:id/members', (ctx) => ok(ctx, { members: clone(membersFor(ctx.scenario, ctx.params.id)) }));
PATCH('/orgs/:id/members/:userId', (ctx) => {
  const member = (STATE.members[ctx.params.id] || []).find((m) => m.userId === ctx.params.userId);
  if (!member) return notFound(ctx, 'Member not found');
  member.role = ctx.body.role || member.role;
  ok(ctx, clone(member));
});
DELETE('/orgs/:id/members/:userId', (ctx) => {
  const list = STATE.members[ctx.params.id] || [];
  const index = list.findIndex((m) => m.userId === ctx.params.userId);
  if (index < 0) return notFound(ctx, 'Member not found');
  const [removed] = list.splice(index, 1);
  ok(ctx, { ...clone(removed), status: 'removed' });
});
GET('/orgs/:id/invitations', (ctx) => {
  const status = ctx.url.searchParams.get('status_filter');
  let list = isEmpty(ctx.scenario) ? onlyCreated(STATE.invitations[ctx.params.id] || []) : (STATE.invitations[ctx.params.id] || []);
  if (status) list = list.filter((i) => i.status === status);
  ok(ctx, { invitations: clone(list) });
});
POST('/orgs/:id/invitations', (ctx) => {
  const inv = mark({ id: uuid(), orgId: ctx.params.id, email: ctx.body.email || 'invitee@example.com', role: ctx.body.role || 'member', status: 'pending', invitedBy: CALLER.id, acceptedBy: null, expiresAt: iso(Date.now() + 28 * UNIT.d), acceptedAt: null, createdAt: iso(), token: `inv_mock_${hex(24)}` });
  (STATE.invitations[ctx.params.id] ||= []).unshift(inv);
  created(ctx, { ...inv, emailDelivery: 'stub' });
});
DELETE('/orgs/:id/invitations/:invId', (ctx) => {
  const inv = (STATE.invitations[ctx.params.id] || []).find((i) => i.id === ctx.params.invId);
  if (!inv) return notFound(ctx, 'Invitation not found');
  inv.status = 'revoked';
  ok(ctx, { status: 'revoked', id: inv.id });
});
POST('/orgs/:id/invitations/:invId/resend', (ctx) => {
  const inv = (STATE.invitations[ctx.params.id] || []).find((i) => i.id === ctx.params.invId);
  if (!inv) return notFound(ctx, 'Invitation not found');
  if (inv.status !== 'pending') return sendJson(ctx, 409, detail('Only pending invitations can be resent'));
  inv.token = `inv_mock_${hex(24)}`;
  inv.expiresAt = iso(Date.now() + 28 * UNIT.d);
  inv.invitedBy = CALLER.id;
  inv.updatedAt = iso();
  ok(ctx, { ...clone(inv), emailDelivery: 'stub' });
});

// ---------------------------------------------------------------------------
// Routes — billing, trace (code attribution), knowledge graph
// ---------------------------------------------------------------------------
GET('/billing/usage', (ctx) => {
  const limit = Number(ctx.url.searchParams.get('limit') || 50);
  const u = clone(isEmpty(ctx.scenario) ? FX.billing.usage_noplan : FX.billing.usage_plan);
  u.recent = (u.recent || []).slice(0, limit);
  ok(ctx, u);
});
GET('/billing/upgrade-requirements', (ctx) => ok(ctx, { ...clone(isEmpty(ctx.scenario) ? FX.billing.upgrade_noplan : FX.billing.upgrade_plan), feature: ctx.url.searchParams.get('feature') }));
const attributions = (sc) => (isEmpty(sc) ? [] : FX.attribution.recent);
GET('/trace/recent', (ctx) => {
  const days = Number(ctx.url.searchParams.get('days') || 7);
  const limit = Number(ctx.url.searchParams.get('limit') || 100);
  const offset = Number(ctx.url.searchParams.get('offset') || 0);
  const cutoff = Date.now() - days * UNIT.d;
  const list = attributions(ctx.scenario).filter((a) => Date.parse(a.createdAt) >= cutoff).slice(offset, offset + limit);
  ok(ctx, clone(list));
});
GET('/trace/stats', (ctx) => ok(ctx, isEmpty(ctx.scenario) ? { totalLines: 0, totalAttributions: 0, uniqueAgents: 0, uniqueFiles: 0, topAgents: [], topFiles: [] } : clone(FX.attribution.stats)));
GET('/trace/health', (ctx) => ok(ctx, { ...FX.attribution.health, timestamp: iso() }), 'health');
GET('/trace/agents/:id', (ctx) => ok(ctx, clone(attributions(ctx.scenario).filter((a) => a.agentId === ctx.params.id))));
GET('/trace/sessions/:id', (ctx) => ok(ctx, clone(attributions(ctx.scenario).filter((a) => a.sessionId === ctx.params.id))));
GET('/trace/files/*', (ctx) => {
  const filePath = decodeURIComponent(ctx.params.rest || '');
  const list = attributions(ctx.scenario).filter((a) => a.filePath === filePath || a.filePath.endsWith(filePath));
  if (!list.length) return notFound(ctx, `No attributions for ${filePath}`);
  ok(ctx, { filePath, totalLines: Math.max(...list.map((a) => a.endLine)) + 40, attributionCount: list.length, attributions: clone(list) });
});
POST('/trace/report', (ctx) => {
  const rows = attributions(ctx.scenario);
  const csv = ['id,agentName,filePath,startLine,endLine,changeType,createdAt', ...rows.map((a) => [a.id, a.agentName, a.filePath, a.startLine, a.endLine, a.changeType, a.createdAt].join(','))].join('\n');
  if ((ctx.body.format || 'csv') === 'json') return ok(ctx, { totalAttributions: rows.length, attributions: rows });
  ctx.res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="attribution-report.csv"', ...corsHeaders(ctx.req) });
  ctx.res.end(csv);
  ctx.status = 200;
});
GET('/knowledge/graph', (ctx) => {
  if (isEmpty(ctx.scenario)) return ok(ctx, { success: true, nodes: [], links: [], total_nodes: 0, total_links: 0 });
  const type = ctx.url.searchParams.get('entity_type');
  const pattern = (ctx.url.searchParams.get('name_pattern') || '').toLowerCase();
  const limit = Number(ctx.url.searchParams.get('limit') || 200);
  let nodes = FX.knowledge.nodes;
  if (type) nodes = nodes.filter((n) => n.type === type);
  if (pattern) nodes = nodes.filter((n) => n.name.toLowerCase().includes(pattern));
  nodes = nodes.slice(0, limit);
  const ids = new Set(nodes.map((n) => n.id));
  const links = FX.knowledge.links.filter((l) => ids.has(l.source) && ids.has(l.target));
  ok(ctx, { success: true, nodes: clone(nodes), links: clone(links), total_nodes: nodes.length, total_links: links.length });
});
GET('/knowledge/stats', (ctx) => ok(ctx, isEmpty(ctx.scenario) ? { ...clone(FX.knowledge.stats), graphs: {}, entity_types: [], relationship_types: [], total_entities: 0, total_relationships: 0 } : clone(FX.knowledge.stats)));
GET('/knowledge/entities', (ctx) => ok(ctx, { success: true, entities: isEmpty(ctx.scenario) ? [] : clone(FX.knowledge.nodes), count: isEmpty(ctx.scenario) ? 0 : FX.knowledge.nodes.length }));
GET('/knowledge/relationships', (ctx) => ok(ctx, { success: true, relationships: isEmpty(ctx.scenario) ? [] : clone(FX.knowledge.links), count: isEmpty(ctx.scenario) ? 0 : FX.knowledge.links.length }));
GET('/knowledge/entity/:name', (ctx) => {
  const e = FX.knowledge.entities[decodeURIComponent(ctx.params.name)];
  e && !isEmpty(ctx.scenario) ? ok(ctx, clone(e)) : sendJson(ctx, 404, { success: false, error: `Entity not found: ${ctx.params.name}` });
});
GET('/knowledge/search', (ctx) => {
  const q = (ctx.url.searchParams.get('q') || ctx.url.searchParams.get('query') || '').toLowerCase();
  ok(ctx, { success: true, query: q, results: FX.knowledge.nodes.filter((n) => n.name.toLowerCase().includes(q)).slice(0, 20) });
});
POST('/knowledge/query', (ctx) => ok(ctx, { success: true, results: [], query: ctx.body.query || '' }));
POST('/knowledge/rag', (ctx) => ok(ctx, { success: true, answer: 'Mock RAG answer.', context: { graph_relationships: [] } }));

// ---------------------------------------------------------------------------
// Routes — agent builder, voice, livekit, langflow, memory, admin
// ---------------------------------------------------------------------------
GET('/agent-builder/info', (ctx) => { const info = clone(FX.platform.builder_info); info.theGeneral.agentCount = roster(ctx.scenario).length; info.capabilities.availableDomains = domainsFor(roster(ctx.scenario)).map((d) => d.name); ok(ctx, info); });
POST('/agent-builder/chat', (ctx) => ok(ctx, {
  sessionId: ctx.body.sessionId || ctx.body.session_id || `builder-${hex(8)}`,
  message: `Gunny here. You said: "${String(ctx.body.message || '').slice(0, 120)}". Tell me the agent's job in one sentence and which domain it belongs to, and I will draft the spec card.`,
  agentCreationIntent: null,
  usage: { prompt_tokens: 220, completion_tokens: 64, total_tokens: 284 },
}));
GET('/agent-builder/session/:id', (ctx) => notFound(ctx, `Session not found: ${ctx.params.id}`));
GET('/voice/health', (ctx) => ok(ctx, clone(FX.platform.voice_health)), 'health');
GET('/voice/config', (ctx) => ok(ctx, { livekit_url: 'ws://localhost:7880', enabled: false, stt: 'whisper', tts: 'kokoro' }));
GET('/voice/rooms', (ctx) => ok(ctx, { rooms: [], count: 0 }));
POST('/voice/rooms', (ctx) => created(ctx, { room_id: `room-${hex(6)}`, name: ctx.body.name || 'mock-room', agent_id: ctx.body.agent_id || null, status: 'active', created_at: iso() }));
GET('/voice/rooms/:id/token', (ctx) => ok(ctx, { token: 'mock-livekit-participant-token', url: 'ws://localhost:7880', room_id: ctx.params.id, identity: CALLER.id }));
POST('/voice/rooms/:id/token', (ctx) => ok(ctx, { token: 'mock-livekit-participant-token', url: 'ws://localhost:7880', room_id: ctx.params.id, identity: CALLER.id }));
POST('/voice/rooms/:id/agent/join', (ctx) => ok(ctx, { status: 'joined', room_id: ctx.params.id, agent_identity: 'agent-mock' }));
DELETE('/voice/rooms/:id', (ctx) => ok(ctx, { message: 'Room closed', room_id: ctx.params.id }));
GET('/livekit/health', (ctx) => ok(ctx, { status: 'ok', livekit: 'mock', url: 'ws://localhost:7880' }), 'health');
POST('/livekit/token', (ctx) => ok(ctx, { token: 'mock-livekit-participant-token', url: 'ws://localhost:7880', room: ctx.body.room || 'mock-room' }));
GET('/langflow/health', (ctx) => ok(ctx, { status: 'unavailable', enabled: false, detail: 'Langflow is not part of the mock' }), 'health');
GET('/langflow/flows', (ctx) => ok(ctx, { flows: [], count: 0 }));
POST('/memory/search', (ctx) => ok(ctx, { results: [], query: ctx.body.query || '', count: 0 }));
POST('/memory', (ctx) => created(ctx, { id: uuid(), stored: true }));
POST('/memory/query', (ctx) => ok(ctx, { results: [], count: 0 }));
GET('/memory/user/:id', (ctx) => ok(ctx, { user_id: ctx.params.id, memories: [], count: 0 }));
GET('/admin/rbac/denials', (ctx) => ok(ctx, { denials: [], count: 0 }));
GET('/admin/activity/conversations', (ctx) => ok(ctx, { conversations: conversations(ctx.scenario).slice(0, 20), count: conversations(ctx.scenario).length }));
POST('/medical-test/test-openrouter', (ctx) => ok(ctx, { success: true, message: 'OpenRouter reachable (mock)', model: ctx.body.model || 'openai/gpt-4o-mini' }));
POST('/medical-test/test-consultation', (ctx) => ok(ctx, { success: true, response: 'Mock consultation response.', model: ctx.body.model || 'openai/gpt-4o-mini' }));

// ---------------------------------------------------------------------------
// Unknown paths: GET → 200 empty shape + warning; writes → echo success
// ---------------------------------------------------------------------------
const ID_LIKE = /^(\d+|[0-9a-f-]{16,}|[a-z0-9]+-[0-9a-f]{6,})$/i;
function unknown(ctx) {
  const key = `${ctx.req.method} ${ctx.path}`;
  if (!STATE.unknownPaths.has(key)) {
    STATE.unknownPaths.set(key, iso());
    warn(`UNKNOWN ${key} — not in the mock; answering with a placeholder. Add a handler in frontend/dev/mock-api.mjs if the UI needs it.`);
  }
  if (ctx.req.method === 'GET') {
    const segs = ctx.path.split('/').filter(Boolean);
    const last = [...segs].reverse().find((s) => !ID_LIKE.test(s)) || 'items';
    const body = { items: [], count: 0, _mock: `unknown GET ${ctx.path}` };
    if (last !== 'items') body[last] = [];
    return ok(ctx, body);
  }
  if (ctx.req.method === 'DELETE') return ok(ctx, { ok: true, deleted: true, path: ctx.path, _mock: 'unknown DELETE' });
  const body = ctx.body && typeof ctx.body === 'object' && !ctx.body._raw ? ctx.body : {};
  return sendJson(ctx, ctx.req.method === 'POST' ? 201 : 200, { ok: true, id: body.id || uuid(), ...body, createdAt: iso(), _mock: `unknown ${ctx.req.method} ${ctx.path}` });
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------
function scenarioFor(req, url) {
  const raw = req.headers['x-mock-scenario'] || url.searchParams.get('mock_scenario') || parseCookies(req).mock_scenario || opts.scenario;
  const s = String(raw).toLowerCase();
  return SCENARIOS.includes(s) ? s : opts.scenario;
}
function normalizePath(pathname) {
  if (/^\/api\/v1(\/|$)/.test(pathname)) return pathname.replace(/^\/api\/v1/, '') || '/';
  if (/^\/api(\/|$)/.test(pathname)) return pathname.replace(/^\/api/, '') || '/';
  return null;
}
const server = http.createServer(async (req, res) => {
  const t0 = Date.now();
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const method = req.method === 'HEAD' ? 'GET' : req.method;
  const ctx = { req, res, url, params: {}, body: {}, scenario: opts.scenario, path: url.pathname, status: 0 };

  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders(req));
    return res.end();
  }
  // Control surface for lanes.
  if (url.pathname.startsWith('/__mock')) {
    ctx.body = await readBody(req);
    if (url.pathname === '/__mock/status') {
      return ok(ctx, { scenario: opts.scenario, scenarios: SCENARIOS, port: opts.port, startedAt: iso(STARTED), now: iso(), seed: opts.seed, sseClients: sseClients.size, busyEngine: Boolean(busyLoop), unknownPaths: [...STATE.unknownPaths.entries()].map(([p, at]) => ({ path: p, firstSeen: at })), fixtures: Object.keys(FX) });
    }
    if (url.pathname === '/__mock/scenario' && (method === 'POST' || method === 'PUT')) {
      const s = String(ctx.body.scenario || '').toLowerCase();
      if (!SCENARIOS.includes(s)) return sendJson(ctx, 400, detail(`scenario must be one of ${SCENARIOS.join(', ')}`));
      opts.scenario = s;
      log(`default scenario → ${s}`);
      return ok(ctx, { scenario: s });
    }
    if (url.pathname === '/__mock/reset' && method === 'POST') { resetState(); return ok(ctx, { reset: true }); }
    if (url.pathname === '/__mock/stream-test') {
      // Diagnostic: a short chunked stream with a chosen content type, to see how
      // a browser/devtools reports the end of a streamed fetch (see README, "Known gaps").
      const ct = url.searchParams.get('ct') || 'text/event-stream';
      const n = Number(url.searchParams.get('n') || 10);
      res.writeHead(200, { 'Content-Type': ct, 'Cache-Control': 'no-cache', ...corsHeaders(req) });
      let i = 0;
      const iv = setInterval(() => { res.write(`data: {"i":${i}}\n\n`); if (++i >= n) { clearInterval(iv); res.end(); } }, 40);
      ctx.status = 200;
      return;
    }
    return notFound(ctx, 'unknown /__mock endpoint (status, scenario, reset)');
  }

  const apiPath = normalizePath(url.pathname);
  if (apiPath && apiPath.startsWith('/__mock/stream-test')) {
    // Same diagnostic, reachable through the Vite proxy (/api/v1/__mock/stream-test).
    const ct = url.searchParams.get('ct') || 'text/event-stream';
    const n = Number(url.searchParams.get('n') || 10);
    const mode = url.searchParams.get('mode') || 'spaced';
    const body = Array.from({ length: n }, (_, i) => `data: {"i":${i}}\n\n`).join('');
    if (mode === 'buffered') { res.writeHead(200, { 'Content-Type': ct, 'Content-Length': Buffer.byteLength(body), ...corsHeaders(req) }); res.end(body); return; }
    if (mode === 'single') { res.writeHead(200, { 'Content-Type': ct, ...corsHeaders(req) }); res.end(body); return; }
    if (mode === 'close-raw') { res.useChunkedEncodingByDefault = false; res.sendDate = false; }
    res.writeHead(200, { 'Content-Type': ct, 'Cache-Control': 'no-cache', ...(mode.startsWith('close') ? { Connection: 'close' } : {}), ...corsHeaders(req) });
    let i = 0;
    const iv = setInterval(() => { res.write(`data: {"i":${i}}\n\n`); if (++i >= n) { clearInterval(iv); res.end(); } }, 40);
    return;
  }
  if (apiPath === null) {
    return sendJson(ctx, 404, { detail: 'Brigade mock API: paths live under /api/v1/*', try: ['/api/v1/health', '/api/v1/agents', '/__mock/status'] });
  }
  ctx.path = apiPath.length > 1 ? apiPath.replace(/\/+$/, '') : apiPath;
  ctx.scenario = scenarioFor(req, url);
  if (ctx.scenario === 'slow') await sleep(opts.slowMs);
  if (method !== 'GET') ctx.body = await readBody(req);

  let matched = null;
  for (const r of ROUTES) {
    if (r.method !== method) continue;
    const m = r.re.exec(ctx.path);
    if (m) {
      matched = r;
      // The UI encodes every id it puts in a path (ids can hold dots, spaces, '#'): decode once, here.
      ctx.params = Object.fromEntries(Object.entries(m.groups || {}).map(([k, v]) => {
        try { return [k, decodeURIComponent(v)]; } catch { return [k, v]; }
      }));
      break;
    }
  }
  try {
    if (!matched) {
      if (ctx.scenario === 'error' && method === 'GET') sendJson(ctx, 500, detail(`Mock error scenario: ${method} ${ctx.path} failed (simulated 500)`));
      else unknown(ctx);
    } else if (ctx.scenario === 'error' && matched.kind === 'data') {
      sendJson(ctx, 500, detail(`Mock error scenario: ${method} ${ctx.path} failed (simulated 500)`));
    } else {
      await matched.handler(ctx);
    }
  } catch (err) {
    console.error('[mock] handler crashed:', err);
    if (!res.headersSent) sendJson(ctx, 500, detail(`mock handler crashed: ${err.message}`));
  }
  const ms = Date.now() - t0;
  const tag = ctx.scenario === opts.scenario ? ctx.scenario : `${ctx.scenario}*`;
  log(`${req.method} ${url.pathname}${url.search} → ${ctx.status || res.statusCode} (${tag}) ${ms}ms`);
});
server.keepAliveTimeout = 65000;
server.listen(opts.port, opts.host, () => {
  const base = `http://${opts.host}:${opts.port}`;
  console.log(`[mock] Unicorn Brigade mock API listening on ${base}/api/v1  scenario=${opts.scenario}  seed=${opts.seed}`);
  console.log(`[mock] ${ROUTES.length} routes · fixtures: ${Object.keys(FX).length} files · roster: normal=${STATE.agents.length} large=${STATE.agents.length + STATE.agentsLarge.length} · conversations=${STATE.conversations.length} · templates=${FX.workflows.templates.length}`);
  console.log(`[mock] override per request: header X-Mock-Scenario, cookie mock_scenario, or ?mock_scenario=  ·  control: GET ${base}/__mock/status, POST ${base}/__mock/scenario {"scenario":"busy"}, POST ${base}/__mock/reset`);
});
process.on('SIGINT', () => { console.log('\n[mock] bye'); process.exit(0); });
process.on('SIGTERM', () => process.exit(0));
