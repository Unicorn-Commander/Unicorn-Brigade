"""Public marketing landing page — the front door to Unicorn Brigade.

Serves at brigade.magicunicorn.dev/landing (via Traefik rule). The
existing React admin UI still owns /, this page is brand + pitch +
"try it now" CTAs.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


LANDING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unicorn Brigade · agents you can talk to</title>
  <meta name="description" content="Self-hosted multi-agent AI platform with persistent memory, real delegation, and voice rooms.">
  <meta property="og:title" content="Unicorn Brigade — agents you can talk to">
  <meta property="og:description" content="Twenty specialist AI agents with persistent memory. Self-hosted. Open.">
  <meta property="og:image" content="https://brigade.magicunicorn.dev/welcome/icon.svg">
  <style>
    :root {
      --bg: #0a0818;
      --card: rgba(30, 27, 75, 0.5);
      --border: rgba(139, 92, 246, 0.3);
      --text: #f1f5f9;
      --muted: #94a3b8;
      --accent: #a78bfa;
      --accent-bright: #c4b5fd;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      background-image:
        radial-gradient(circle at 20% 20%, rgba(139, 92, 246, 0.15), transparent 40%),
        radial-gradient(circle at 80% 80%, rgba(236, 72, 153, 0.1), transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.08), transparent 50%);
      color: var(--text);
      line-height: 1.6;
      min-height: 100vh;
    }
    header {
      padding: 24px 32px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(20px);
      position: sticky;
      top: 0;
      background: rgba(10, 8, 24, 0.8);
      z-index: 10;
    }
    header img { width: 32px; height: 32px; }
    header .brand { font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
    header nav { margin-left: auto; display: flex; gap: 24px; align-items: center; }
    header nav a { color: var(--muted); text-decoration: none; font-size: 14px; transition: color .15s; }
    header nav a:hover { color: var(--text); }
    header nav .cta {
      padding: 8px 20px;
      background: var(--accent);
      color: #0a0818;
      border-radius: 8px;
      font-weight: 600;
    }
    header nav .cta:hover { background: var(--accent-bright); color: #0a0818; }

    .hero {
      max-width: 1000px;
      margin: 0 auto;
      padding: 96px 24px 64px;
      text-align: center;
    }
    .eyebrow {
      display: inline-block;
      padding: 4px 12px;
      background: rgba(139, 92, 246, 0.15);
      border: 1px solid var(--border);
      border-radius: 999px;
      font-size: 12px;
      color: var(--accent);
      margin-bottom: 24px;
      font-weight: 500;
    }
    h1 {
      font-size: clamp(40px, 6vw, 72px);
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.05;
      margin: 0 0 24px;
      background: linear-gradient(180deg, #f1f5f9 0%, #a78bfa 120%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .hero p.lede { font-size: 22px; color: var(--muted); max-width: 640px; margin: 0 auto 40px; }
    .hero-cta { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
    .btn {
      padding: 14px 28px;
      border-radius: 10px;
      font-weight: 600;
      text-decoration: none;
      font-size: 15px;
      transition: all .15s;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .btn-primary { background: var(--accent); color: #0a0818; }
    .btn-primary:hover { background: var(--accent-bright); transform: translateY(-1px); }
    .btn-ghost {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
    }
    .btn-ghost:hover { border-color: var(--accent); background: rgba(139, 92, 246, 0.08); }

    .section { max-width: 1100px; margin: 0 auto; padding: 64px 24px; }
    .section h2 { font-size: 36px; font-weight: 700; margin: 0 0 16px; letter-spacing: -0.02em; }
    .section .sub { font-size: 17px; color: var(--muted); margin-bottom: 48px; max-width: 640px; }

    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
    .feature {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px;
      backdrop-filter: blur(10px);
    }
    .feature .icon { font-size: 28px; margin-bottom: 16px; display: block; }
    .feature h3 { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
    .feature p { font-size: 14px; color: var(--muted); }

    .agents {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 32px;
    }
    .agent {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      font-size: 14px;
      backdrop-filter: blur(8px);
    }
    .agent .name { font-weight: 600; }
    .agent .role { font-size: 12px; color: var(--muted); margin-top: 4px; }

    .surfaces { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; }
    .surface-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px;
      text-decoration: none;
      color: inherit;
      backdrop-filter: blur(10px);
      transition: all .15s;
      display: block;
    }
    .surface-card:hover { border-color: var(--accent); transform: translateY(-2px); }
    .surface-card .title { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
    .surface-card .url { font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--accent); word-break: break-all; }
    .surface-card .desc { font-size: 13px; color: var(--muted); margin-top: 8px; }

    .cta-band {
      max-width: 900px;
      margin: 64px auto;
      padding: 48px 24px;
      text-align: center;
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(236, 72, 153, 0.1));
      border: 1px solid var(--border);
      border-radius: 20px;
      backdrop-filter: blur(10px);
    }
    .cta-band h2 { font-size: 32px; }

    footer {
      max-width: 1100px;
      margin: 48px auto 0;
      padding: 40px 24px;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 13px;
      flex-wrap: wrap;
      gap: 16px;
    }
    footer a { color: var(--accent); text-decoration: none; }
    footer a:hover { color: var(--accent-bright); }

    code {
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      background: rgba(15, 23, 42, 0.8);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <header>
    <img src="/welcome/icon.svg" alt="Unicorn Brigade">
    <div class="brand">Unicorn Brigade</div>
    <nav>
      <a href="#agents">Agents</a>
      <a href="#surfaces">Surfaces</a>
      <a href="#why">Why</a>
      <a class="cta" href="/welcome">Sign up →</a>
    </nav>
  </header>

  <section class="hero">
    <div class="eyebrow">Self-hosted · multi-agent · voice-capable</div>
    <h1>Agents you can talk to.</h1>
    <p class="lede">Twenty specialist AI agents with persistent memory, real delegation between agents, and tools that actually work. All running on your own hardware.</p>
    <div class="hero-cta">
      <a class="btn btn-primary" href="/welcome">Create account</a>
      <a class="btn btn-ghost" href="https://libre.magicunicorn.dev">Open chat ↗</a>
    </div>
  </section>

  <section id="why" class="section">
    <h2>What makes it different</h2>
    <p class="sub">Most AI tools are one-agent chatboxes. This is a platform of agents that talk to each other, remember you, and plug into whatever interface you prefer.</p>
    <div class="grid-3">
      <div class="feature">
        <span class="icon">🧠</span>
        <h3>Temporal graph memory</h3>
        <p>Agents actually remember you across conversations. Facts about you are stored as a time-aware knowledge graph (Graphiti + FalkorDB) — supersessions, contradictions, context all handled.</p>
      </div>
      <div class="feature">
        <span class="icon">🎖️</span>
        <h3>Real delegation</h3>
        <p>The General coordinates. Specialists do the work. Ask one question — watch it get routed to the right agent. See the tool-call chain in every response.</p>
      </div>
      <div class="feature">
        <span class="icon">🔒</span>
        <h3>Per-user isolation</h3>
        <p>Non-admin users cannot spoof identities. Memory is scoped to your authenticated account. GDPR deletion is one API call.</p>
      </div>
      <div class="feature">
        <span class="icon">🛠️</span>
        <h3>Dual-layer tools</h3>
        <p>Brigade's server-side tools (delegation, web search, memory) coexist with your client's tools (file read, shell, etc.) in one conversation. OpenCode works fully.</p>
      </div>
      <div class="feature">
        <span class="icon">📡</span>
        <h3>OpenAI-compatible API</h3>
        <p>Drop-in provider for any OpenAI SDK. Agents appear as models. Streaming, tool-calling, everything works. Point your existing code at us and pick an agent instead of a model.</p>
      </div>
      <div class="feature">
        <span class="icon">⚡</span>
        <h3>Fully self-hosted</h3>
        <p>Your data never leaves your infra. Models run locally (Qwen, Gemma 4, whatever). No vendor lock-in. Open source under your control.</p>
      </div>
    </div>
  </section>

  <section id="agents" class="section">
    <h2>The roster</h2>
    <p class="sub">Pick an agent by role. Each has their own persona, knowledge, tools, and memory of past conversations with you.</p>
    <div class="agents">
      <div class="agent"><div class="name">🎖️ The General</div><div class="role">Orchestration · delegates</div></div>
      <div class="agent"><div class="name">🔍 Detective Holmes</div><div class="role">Research, investigation</div></div>
      <div class="agent"><div class="name">⚖️ Judge Advocate</div><div class="role">Legal analysis</div></div>
      <div class="agent"><div class="name">💻 Cpt. Fullstack</div><div class="role">Full-stack development</div></div>
      <div class="agent"><div class="name">🔍 Code Reviewer</div><div class="role">Code review</div></div>
      <div class="agent"><div class="name">🚀 Maj. DevOps</div><div class="role">Infra, CI/CD</div></div>
      <div class="agent"><div class="name">🛡️ Sgt. Cipher</div><div class="role">Security</div></div>
      <div class="agent"><div class="name">📝 Sgt. Scribe</div><div class="role">Documentation</div></div>
      <div class="agent"><div class="name">🧬 Prof. DataSci</div><div class="role">Data science</div></div>
      <div class="agent"><div class="name">🗄️ SQL Analyst</div><div class="role">Database queries</div></div>
      <div class="agent"><div class="name">🔬 Doc MedResearch</div><div class="role">Medical research</div></div>
      <div class="agent"><div class="name">📊 Col. Finance</div><div class="role">Financial analysis</div></div>
      <div class="agent"><div class="name">🧾 Lt. TaxStrat</div><div class="role">Tax strategy</div></div>
      <div class="agent"><div class="name">📄 Lt. DocAnalyst</div><div class="role">Document analysis</div></div>
      <div class="agent"><div class="name">🎯 Maj. LeadGen</div><div class="role">Lead generation</div></div>
      <div class="agent"><div class="name">🎧 Support Specialist</div><div class="role">Customer support</div></div>
      <div class="agent"><div class="name">🔍 Evidence Correlator</div><div class="role">Legal evidence</div></div>
      <div class="agent"><div class="name">🧩 Gap Analyzer</div><div class="role">Legal gap analysis</div></div>
      <div class="agent"><div class="name">📅 Timeline Builder</div><div class="role">Legal timelines</div></div>
      <div class="agent"><div class="name">🎯 Gunny</div><div class="role">Agent builder</div></div>
    </div>
  </section>

  <section id="surfaces" class="section">
    <h2>Talk to them however you want</h2>
    <p class="sub">One backend, many front doors. Pick the surface that fits your workflow.</p>
    <div class="surfaces">
      <a class="surface-card" href="https://libre.magicunicorn.dev" target="_blank">
        <div class="title">💬 Chat in your browser</div>
        <div class="url">libre.magicunicorn.dev</div>
        <div class="desc">Web chat UI with streaming, markdown, tool traces. Keycloak SSO.</div>
      </a>
      <a class="surface-card" href="https://stable.magicunicorn.dev" target="_blank">
        <div class="title">🎙️ Voice rooms</div>
        <div class="url">stable.magicunicorn.dev</div>
        <div class="desc">LiveKit-based rooms — invite specific agents as participants. Text + voice.</div>
      </a>
      <a class="surface-card" href="/welcome#opencode">
        <div class="title">⌨️ In your code editor</div>
        <div class="url">opencode provider</div>
        <div class="desc">Pick an agent from OpenCode's model picker. Full tool access, persona, memory.</div>
      </a>
      <a class="surface-card" href="/welcome#api">
        <div class="title">🔌 Any OpenAI SDK</div>
        <div class="url">/api/v1/openai/v1/*</div>
        <div class="desc">Drop-in compatible. Streaming, tool calling, dual-layer tools. Python, Node, curl.</div>
      </a>
    </div>
  </section>

  <section class="cta-band">
    <h2>Try it. It's free for personal use.</h2>
    <p class="sub" style="margin: 16px auto 32px; text-align: center;">Sign up takes 30 seconds. Your API key appears instantly with a ready-to-paste OpenCode snippet.</p>
    <a class="btn btn-primary" href="/welcome">Get my API key →</a>
  </section>

  <footer>
    <div>© 2026 Magic Unicorn · Built on <a href="https://git.unicorncommander.ai" target="_blank">Unicorn Commander</a></div>
    <div><a href="https://git.unicorncommander.ai/UnicornCommander/Unicorn-Brigade" target="_blank">Source</a> · <a href="/welcome">Sign up</a> · <a href="https://langfuse.magicunicorn.dev" target="_blank">Observability</a></div>
  </footer>
</body>
</html>"""


@router.get("/landing", response_class=HTMLResponse, include_in_schema=False)
async def landing() -> HTMLResponse:
    return HTMLResponse(content=LANDING_HTML)
