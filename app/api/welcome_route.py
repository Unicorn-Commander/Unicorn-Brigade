"""Public welcome / signup / key-management page for end users.

Single self-contained HTML+CSS+JS page served from Brigade's FastAPI
backend. Lets a new user sign up, log in, generate an API key, and
download a ready-to-use opencode.json snippet — without an admin
having to run curl commands.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unicorn Brigade — agents you can talk to</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --accent: #a78bfa;
      --accent-hover: #c4b5fd;
      --success: #34d399;
      --error: #f87171;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      color: var(--text);
      min-height: 100vh;
    }
    header {
      padding: 24px 32px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--border);
    }
    header img { width: 32px; height: 32px; }
    header h1 { font-size: 18px; font-weight: 600; margin: 0; }
    header .tag { font-size: 12px; color: var(--muted); margin-left: auto; }
    main {
      max-width: 720px;
      margin: 0 auto;
      padding: 48px 24px;
    }
    .hero {
      text-align: center;
      margin-bottom: 48px;
    }
    .hero h2 {
      font-size: 36px;
      font-weight: 700;
      margin: 0 0 16px;
      background: linear-gradient(90deg, #a78bfa, #f0abfc);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .hero p { font-size: 18px; color: var(--muted); margin: 0; }
    .card {
      background: rgba(30, 41, 59, 0.7);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 32px;
      margin-bottom: 24px;
    }
    .card h3 { margin: 0 0 16px; font-size: 20px; }
    .row { display: flex; gap: 12px; }
    .row > * { flex: 1; }
    label { display: block; font-size: 13px; color: var(--muted); margin: 12px 0 6px; }
    input {
      width: 100%;
      padding: 12px 14px;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 14px;
      font-family: inherit;
    }
    input:focus { outline: none; border-color: var(--accent); }
    button {
      padding: 12px 24px;
      background: var(--accent);
      color: #0f172a;
      border: none;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 120ms;
      width: 100%;
      margin-top: 16px;
    }
    button:hover { background: var(--accent-hover); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .button-secondary { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
    .button-secondary:hover { background: rgba(167, 139, 250, 0.1); color: var(--accent-hover); }
    .status { margin-top: 16px; padding: 12px; border-radius: 8px; font-size: 14px; display: none; }
    .status.success { background: rgba(52, 211, 153, 0.1); color: var(--success); border: 1px solid var(--success); display: block; }
    .status.error { background: rgba(248, 113, 113, 0.1); color: var(--error); border: 1px solid var(--error); display: block; }
    .key {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 12px;
      word-break: break-all;
      color: var(--accent);
    }
    .tabs { display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid var(--border); }
    .tab {
      padding: 12px 16px;
      background: transparent;
      border: none;
      color: var(--muted);
      cursor: pointer;
      width: auto;
      margin: 0;
      font-weight: 500;
      border-bottom: 2px solid transparent;
    }
    .tab.active { color: var(--text); border-bottom-color: var(--accent); }
    .tab:hover:not(.active) { color: var(--text); }
    .surfaces { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
    .surface {
      background: rgba(15, 23, 42, 0.5);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }
    .surface a { color: var(--accent); text-decoration: none; font-weight: 600; font-size: 14px; }
    .surface a:hover { color: var(--accent-hover); }
    .surface small { display: block; color: var(--muted); margin-top: 4px; font-size: 12px; }
    pre {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 12px;
      max-height: 300px;
    }
    .hint { color: var(--muted); font-size: 13px; margin-top: 12px; line-height: 1.5; }
    .copy-row { display: flex; gap: 8px; margin-top: 12px; }
    .copy-row button { width: auto; margin: 0; flex-shrink: 0; padding: 8px 14px; font-size: 12px; }
    a { color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <img src="/welcome/icon.svg" alt="Unicorn Brigade">
    <h1>Unicorn Brigade</h1>
    <span class="tag">Self-hosted multi-agent platform</span>
  </header>

  <main>
    <section class="hero">
      <h2>Agents you can talk to.</h2>
      <p>Twenty specialist AI agents with persistent memory, real delegation, and tools that actually work.</p>
    </section>

    <div class="card">
      <div class="tabs">
        <button class="tab active" data-tab="signup">Sign up</button>
        <button class="tab" data-tab="signin">Sign in</button>
      </div>

      <div id="tab-signup">
        <h3>Create your account</h3>
        <p class="hint">Free for personal use. Keycloak SSO available for organizations — contact us.</p>
        <label>Name</label>
        <input id="su-name" type="text" placeholder="Your name" autocomplete="name">
        <label>Email</label>
        <input id="su-email" type="email" placeholder="you@example.com" autocomplete="email">
        <label>Password</label>
        <input id="su-pass" type="password" placeholder="At least 8 chars, with a number" autocomplete="new-password">
        <button id="su-btn">Create account</button>
        <div id="su-status" class="status"></div>
      </div>

      <div id="tab-signin" style="display:none">
        <h3>Sign in</h3>
        <label>Email</label>
        <input id="si-email" type="email" placeholder="you@example.com" autocomplete="email">
        <label>Password</label>
        <input id="si-pass" type="password" placeholder="Password" autocomplete="current-password">
        <button id="si-btn">Sign in</button>
        <div id="si-status" class="status"></div>
      </div>
    </div>

    <div id="key-card" class="card" style="display:none">
      <h3>Your API key</h3>
      <p class="hint">This is the only time the full key is shown. Copy it now and store it securely.</p>
      <div id="key-display" class="key"></div>
      <div class="copy-row">
        <button class="button-secondary" id="copy-key-btn">Copy key</button>
        <button class="button-secondary" id="dl-opencode-btn">Download opencode.json snippet</button>
      </div>

      <h3 style="margin-top:32px">Use it now</h3>
      <div class="surfaces">
        <div class="surface">
          <a href="https://libre.magicunicorn.dev" target="_blank">Open chat ↗</a>
          <small>libre.magicunicorn.dev</small>
        </div>
        <div class="surface">
          <a href="https://stable.magicunicorn.dev" target="_blank">Voice rooms ↗</a>
          <small>stable.magicunicorn.dev</small>
        </div>
        <div class="surface">
          <a href="#opencode" id="show-opencode">OpenCode setup</a>
          <small>code editor</small>
        </div>
        <div class="surface">
          <a href="#api" id="show-api">Direct API</a>
          <small>any OpenAI SDK</small>
        </div>
      </div>

      <div id="opencode-panel" style="display:none; margin-top:24px">
        <h3>OpenCode setup</h3>
        <p class="hint">Add this to your <code>~/.config/opencode/opencode.json</code> under <code>provider</code>. Then <code>export BRIGADE_API_KEY='...'</code> in your shell with the key above.</p>
        <pre id="opencode-snippet"></pre>
      </div>

      <div id="api-panel" style="display:none; margin-top:24px">
        <h3>Direct API</h3>
        <p class="hint">Works with any OpenAI-compatible client.</p>
        <pre id="api-snippet"></pre>
      </div>
    </div>
  </main>

<script>
const API_BASE = window.location.origin;

function $(id) { return document.getElementById(id); }
function status(elId, msg, kind) {
  const el = $(elId);
  el.textContent = msg;
  el.className = 'status ' + (kind || 'success');
}
function clearStatus(elId) {
  $(elId).className = 'status';
  $(elId).textContent = '';
}

document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    $('tab-signup').style.display = t.dataset.tab === 'signup' ? '' : 'none';
    $('tab-signin').style.display = t.dataset.tab === 'signin' ? '' : 'none';
  });
});

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API_BASE + path, opts);
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = { detail: text }; }
  if (!r.ok) {
    const msg = (data.detail && (data.detail.message || data.detail)) || `HTTP ${r.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

async function generateKey(loginKey) {
  return api('POST', '/api/v1/users/me/api-keys', {
    name: 'Default key',
    permissions: ['chat', 'read', 'write'],
    rateLimit: 200,
    expiresInDays: 365,
  });
}

async function showKeyCard(apiKey) {
  $('key-card').style.display = '';
  $('key-display').textContent = apiKey;
  $('opencode-snippet').textContent = JSON.stringify({
    "brigade": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Unicorn Brigade · agents as people",
      "options": {
        "baseURL": "https://brigade.magicunicorn.dev/api/v1/openai/v1",
        "apiKey": "{env:BRIGADE_API_KEY}",
        "timeout": 300000
      },
      "models": {
        "the-general": { "name": "🎖️ The General · primary", "limit": { "context": 131072, "output": 8192 } },
        "judge-advocate": { "name": "⚖️ Judge Advocate · legal", "limit": { "context": 32768, "output": 8192 } },
        "detective-holmes": { "name": "🔍 Detective Holmes · research", "limit": { "context": 32768, "output": 8192 } },
        "doc-medresearch": { "name": "🔬 Doc MedResearch · medical", "limit": { "context": 32768, "output": 8192 } },
        "col-finance": { "name": "📊 Col. Finance · finance", "limit": { "context": 32768, "output": 8192 } },
        "cpt-fullstack": { "name": "💻 Cpt. Fullstack · dev", "limit": { "context": 32768, "output": 8192 } },
        "code-reviewer": { "name": "🔍 Code Reviewer", "limit": { "context": 32768, "output": 8192 } }
      }
    }
  }, null, 2);
  $('api-snippet').textContent = `# Python (any OpenAI SDK works)
from openai import OpenAI
c = OpenAI(
    base_url="https://brigade.magicunicorn.dev/api/v1/openai/v1",
    api_key="${apiKey}",
)
r = c.chat.completions.create(
    model="the-general",
    messages=[{"role":"user","content":"Hello!"}],
    user="your-username",  # for memory isolation
)
print(r.choices[0].message.content)

# curl
curl https://brigade.magicunicorn.dev/api/v1/openai/v1/chat/completions \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"the-general","messages":[{"role":"user","content":"Hi"}]}'`;
}

$('su-btn').addEventListener('click', async () => {
  clearStatus('su-status');
  const name = $('su-name').value.trim();
  const email = $('su-email').value.trim();
  const password = $('su-pass').value;
  if (!name || !email || !password) { status('su-status', 'Fill in all fields', 'error'); return; }
  $('su-btn').disabled = true;
  try {
    await api('POST', '/api/v1/users/register', { name, email, password });
    const login = await api('POST', '/api/v1/users/login', { email, password });
    const key = login.apiKey;
    status('su-status', 'Account created. Your API key is below — save it now.', 'success');
    showKeyCard(key);
    window.scrollTo({ top: $('key-card').offsetTop - 20, behavior: 'smooth' });
  } catch (e) {
    status('su-status', e.message, 'error');
  } finally {
    $('su-btn').disabled = false;
  }
});

$('si-btn').addEventListener('click', async () => {
  clearStatus('si-status');
  const email = $('si-email').value.trim();
  const password = $('si-pass').value;
  if (!email || !password) { status('si-status', 'Email and password required', 'error'); return; }
  $('si-btn').disabled = true;
  try {
    const login = await api('POST', '/api/v1/users/login', { email, password });
    status('si-status', 'Signed in. Generating a fresh API key…', 'success');
    showKeyCard(login.apiKey);
    window.scrollTo({ top: $('key-card').offsetTop - 20, behavior: 'smooth' });
  } catch (e) {
    status('si-status', e.message, 'error');
  } finally {
    $('si-btn').disabled = false;
  }
});

$('copy-key-btn').addEventListener('click', () => {
  navigator.clipboard.writeText($('key-display').textContent);
  $('copy-key-btn').textContent = 'Copied!';
  setTimeout(() => { $('copy-key-btn').textContent = 'Copy key'; }, 1500);
});

$('dl-opencode-btn').addEventListener('click', () => {
  const blob = new Blob([$('opencode-snippet').textContent], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'brigade-provider.json';
  a.click();
  URL.revokeObjectURL(url);
});

$('show-opencode').addEventListener('click', (e) => { e.preventDefault(); $('opencode-panel').style.display = ''; $('api-panel').style.display = 'none'; });
$('show-api').addEventListener('click', (e) => { e.preventDefault(); $('api-panel').style.display = ''; $('opencode-panel').style.display = 'none'; });
</script>
</body>
</html>"""


ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#a78bfa"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30" fill="url(#g)"/>
  <path d="M32 12 L36 20 L44 14 L40 24 L50 24 L42 30 L48 38 L38 36 L36 46 L32 38 L28 46 L26 36 L16 38 L22 30 L14 24 L24 24 L20 14 L28 20 Z"
        fill="#ffffff" opacity="0.95"/>
  <circle cx="32" cy="32" r="4" fill="#7c3aed"/>
</svg>"""


@router.get("/welcome", response_class=HTMLResponse, include_in_schema=False)
async def welcome_page() -> HTMLResponse:
    return HTMLResponse(content=HTML_PAGE)


@router.get("/welcome/icon.svg", include_in_schema=False)
async def welcome_icon():
    return HTMLResponse(content=ICON_SVG, media_type="image/svg+xml")
