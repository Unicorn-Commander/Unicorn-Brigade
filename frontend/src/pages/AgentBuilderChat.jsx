/**
 * Agent Builder — a conversation with Gunny that fills in a spec card.
 *
 * Two panes: the chat (header, optional preferences, messages, a sticky
 * composer) and the draft panel (AgentPreview) — a side column from `lg`,
 * a bottom Sheet behind a "Draft" button on phones. Gunny unreachable is a
 * state of the page, a failed send is a retryable bubble, and deploying
 * goes through a Modal that shows the spec before it joins the brigade.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { BookOpen, ChevronDown, PanelRight, RefreshCw, Rocket, RotateCcw, Send, Settings2, Sparkles, User } from 'lucide-react';
import { apiJson } from '../services/http';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { prettyDomain } from '../utils/agentClass';
import useAuth from '../hooks/useAuth';
import AgentAvatar from '../components/AgentAvatar';
import AgentPreview from '../components/AgentPreview';
import ModelSelector from '../components/ModelSelector';
import ParameterSlider from '../components/ParameterSlider';
import { Button, Card, Chip, ErrorState, Field, IconButton, Input, Kbd, Modal, Select, Sheet, Spinner, Textarea } from '../components/ui';

const GUNNY = { id: 'gunny', name: 'gunny', displayName: 'Gunny' };
const WELCOME = `Howdy! I'm **Gunny**, your Agent Builder.

Tell me what the agent is for — a financial analyst, a legal researcher, a release sergeant — and I'll draft its spec card as we talk: name, domain, model, tools and capabilities. You can also ask what tools and domains are available.

What would you like to build?`;
const FALLBACK_DOMAINS = ['financial', 'legal', 'medical', 'cybersecurity', 'analytics', 'customer-service', 'education', 'healthcare', 'research'];
const TOKEN_PRESETS = [2048, 4096, 8192, 16384, 32768];
const MARKDOWN =
  'text-body text-fg [&_p]:mb-2 [&_p:last-child]:mb-0 [&_h1]:text-lead [&_h1]:font-semibold [&_h2]:text-body [&_h2]:font-semibold [&_h3]:font-semibold [&_strong]:text-fg-strong [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-0.5 [&_code]:rounded-chip [&_code]:bg-elevated [&_code]:px-1 [&_code]:font-mono [&_code]:text-body-sm [&_pre]:mb-2 [&_pre]:overflow-x-auto [&_pre]:rounded-control [&_pre]:border [&_pre]:border-border [&_pre]:bg-surface [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_a]:text-accent [&_a]:underline';

const emptyPreview = () => ({ name: null, displayName: null, domain: null, model: null, temperature: 0.7, maxTokens: 4096, tools: [], capabilities: [], systemPrompt: null, status: 'building' });
const newSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;

// Pull what Gunny states in prose into the spec card.
function parseAgentDetails(message, current) {
  const next = { ...current, tools: [...(current.tools || [])], capabilities: [...(current.capabilities || [])] };
  const text = String(message || '');
  for (const re of [/(?:call it|name it|agent called|agent named)\s+["']?([^"'\n.]+)["']?/i, /(?:create|build)\s+(?:an?\s+)?["']?([^"'\n.]+)["']?\s+agent/i, /agent\s+name[:\s]+["']?([^"'\n.]+)["']?/i]) {
    const m = text.match(re);
    if (m?.[1]) {
      const name = m[1].trim();
      if (name.length > 2 && name.length < 50 && !/^(the|this|that|your)\b/i.test(name)) {
        next.name = name;
        next.displayName = name;
        break;
      }
    }
  }
  const model = text.match(/\b(gpt-4[^\s,]*|claude[^\s,]*|gemini[^\s,]*|qwen[^\s,]*)/i);
  if (model) next.model = model[1].trim();
  const lower = text.toLowerCase();
  const domain = [...FALLBACK_DOMAINS, 'technology', 'investigation', 'data-analysis', 'content-creation'].find((d) => lower.includes(d));
  if (domain) next.domain = domain;
  const temp = text.match(/temperature[:\s]+([0-9.]+)/i);
  if (temp && parseFloat(temp[1]) >= 0 && parseFloat(temp[1]) <= 2) next.temperature = parseFloat(temp[1]);
  const tokens = text.match(/(?:max tokens|token limit)[:\s]+([0-9,]+)/i);
  if (tokens) next.maxTokens = parseInt(tokens[1].replace(/,/g, ''), 10) || next.maxTokens;
  const listAfter = (re) =>
    (text.match(re)?.[1] || '')
      .split(/\n|,/)
      .map((t) => t.replace(/^[-•*]\s*/, '').trim())
      .filter((t) => t.length > 2 && t.length < 50);
  const tools = listAfter(/(?:tools?)[:\s]+([^\n]+(?:\n[-•*]\s*[^\n]+)*)/i);
  if (tools.length) next.tools = [...new Set([...next.tools, ...tools])];
  ['web search', 'calculator', 'code execution', 'database', 'data analysis', 'file system'].forEach((t) => {
    if (lower.includes(t) && !next.tools.some((x) => String(x).toLowerCase().includes(t))) next.tools.push(t.replace(/\b\w/g, (c) => c.toUpperCase()));
  });
  const caps = listAfter(/(?:capabilities)[:\s]+([^\n]+(?:\n[-•*]\s*[^\n]+)*)/i);
  if (caps.length) next.capabilities = [...new Set([...next.capabilities, ...caps])];
  if (/ready to create|shall I create|proceed with creation|create this agent|deploy.*agent/i.test(text)) next.status = 'ready';
  return next;
}

function parseJsonConfig(content) {
  try {
    const block = content.match(/```json\s*([\s\S]*?)```/);
    if (block?.[1]) return JSON.parse(block[1].trim());
    const obj = content.match(/\{[\s\S]*"name"[\s\S]*\}/);
    if (obj) {
      const parsed = JSON.parse(obj[0]);
      if (parsed.name) return parsed;
    }
  } catch {
    /* not a config block */
  }
  return null;
}

function useIsNarrow() {
  const q = '(max-width: 1023px)';
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = (e) => setNarrow(e.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return narrow;
}

export default function AgentBuilderChat() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const narrow = useIsNarrow();
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const [gunny, setGunny] = useState({ state: 'loading', info: null, error: null });
  const [sessionId, setSessionId] = useState(newSessionId);
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME }]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [preview, setPreview] = useState(emptyPreview);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [prefs, setPrefs] = useState({ model: 'ai-choice', domain: '', temperature: 0.7, maxTokens: 4096 });
  const [draftOpen, setDraftOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [confirmNew, setConfirmNew] = useState(false);
  const [deploy, setDeploy] = useState(null); // parsed config awaiting confirmation
  const [deploying, setDeploying] = useState(false);

  const loadGunny = useCallback(async () => {
    setGunny({ state: 'loading', info: null, error: null });
    try {
      const info = await apiJson('/agent-builder/info');
      setGunny({ state: 'ready', info, error: null });
    } catch (err) {
      setGunny({ state: 'error', info: null, error: err });
    }
  }, []);

  useEffect(() => {
    loadGunny();
  }, [loadGunny]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  const domains = gunny.info?.capabilities?.availableDomains?.length ? gunny.info.capabilities.availableDomains : FALLBACK_DOMAINS;

  const send = async (textOverride) => {
    const text = (textOverride ?? input).trim();
    if (!text || sending) return;
    if (textOverride == null) setInput('');
    setMessages((m) => [...m.filter((x) => x.role !== 'error'), { role: 'user', content: text }]);
    setSending(true);
    try {
      const data = await apiJson('/agent-builder/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: text,
          sessionId,
          userId: user?.id || 'guest-user',
          preferences: prefs.model === 'ai-choice' ? {} : { ...prefs, domain: prefs.domain || null },
        }),
      });
      const reply = String(data?.message || '');
      setMessages((m) => [...m, { role: 'assistant', content: reply, usage: data?.usage, intent: Boolean(data?.agentCreationIntent) }]);
      const next = parseAgentDetails(reply, preview);
      setPreview(next);
      if (data?.agentCreationIntent) {
        const config = parseJsonConfig(reply) || (next.name ? { ...next } : null);
        if (config) setDeploy(config);
        else notify.info('Gunny wants to create the agent but sent no spec. Ask for the JSON config.');
      }
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', content: humanize(err, { what: 'sending your message' }), retry: text }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const startNew = () => {
    setSessionId(newSessionId());
    setMessages([{ role: 'assistant', content: 'New conversation. What would you like to build?' }]);
    setPreview(emptyPreview());
    setDeploy(null);
    setConfirmNew(false);
  };

  const createAgent = async (config) => {
    const payload = {
      name: config.name,
      displayName: config.displayName || config.name,
      domain: config.domain || preview.domain,
      model: config.model || preview.model || (prefs.model !== 'ai-choice' ? prefs.model : undefined),
      temperature: config.temperature ?? preview.temperature ?? 0.7,
      maxTokens: config.maxTokens || preview.maxTokens || 4096,
      tools: config.tools || preview.tools || [],
      capabilities: config.capabilities || preview.capabilities || [],
      systemPrompt: config.systemPrompt || preview.systemPrompt,
      avatar: config.avatar,
      title: config.title,
      bio: config.bio,
      createdBy: user?.id || 'guest-user',
      createdByAgent: 'gunny',
    };
    setDeploying(true);
    try {
      const created = await apiJson('/agents', { method: 'POST', body: JSON.stringify(payload) });
      notify.success(`${payload.displayName} joined the brigade`);
      setPreview((p) => ({ ...p, status: 'created' }));
      setDeploy(null);
      navigate(`/agent/${created?.id || payload.name}`);
    } catch (err) {
      notify.error(humanize(err, { what: 'deploying the agent' }));
    } finally {
      setDeploying(false);
    }
  };

  const gunnyStatus = gunny.state === 'ready' ? { tone: 'ok', label: gunny.info?.builder?.status === 'ready' || gunny.info?.theGeneral?.status === 'online' ? 'Online' : gunny.info?.builder?.status || 'Online' } : gunny.state === 'loading' ? { tone: 'neutral', label: 'Connecting…' } : { tone: 'danger', label: 'Unreachable' };
  const unreachable = gunny.state === 'error';

  const draft = <AgentPreview preview={preview} onConfirm={() => createAgent({ ...preview })} onReset={() => setPreview(emptyPreview())} />;

  return (
    // w-0 + min-w-full: the header's non-wrapping line must not widen the
    // layout's main column on phones (it has no min-w-0 of its own).
    <div className="flex h-[calc(100dvh-4rem)] w-0 min-h-0 min-w-full lg:h-dvh">
      {/* ── chat column ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3 sm:px-6">
          <AgentAvatar agent={GUNNY} size={40} rounded="rounded-control" status={sending ? 'thinking' : 'idle'} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-lead font-semibold text-fg-strong">Gunny</h1>
              <Chip size="xs" tone={gunnyStatus.tone} dot pulse={sending}>
                {sending ? 'Thinking' : gunnyStatus.label}
              </Chip>
            </div>
            <p className="truncate text-caption text-muted">Agent Builder{gunny.info?.theGeneral?.agentCount ? ` · ${gunny.info.theGeneral.agentCount} agents in the brigade` : ''}</p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => setConfirmNew(true)} className="hidden sm:inline-flex">
              New chat
            </Button>
            <IconButton icon={RefreshCw} label="New chat" size="sm" onClick={() => setConfirmNew(true)} className="sm:hidden" />
            <Button as={Link} to="/library" variant="secondary" size="sm" icon={BookOpen} className="hidden sm:inline-flex">
              Library
            </Button>
            {narrow ? (
              <Button variant="secondary" size="sm" icon={PanelRight} onClick={() => setDraftOpen(true)}>
                Draft
              </Button>
            ) : (
              <IconButton icon={PanelRight} label={panelOpen ? 'Hide draft panel' : 'Show draft panel'} size="sm" aria-pressed={panelOpen} onClick={() => setPanelOpen((o) => !o)} />
            )}
          </div>
        </header>

        <div className="px-4 pt-3 sm:px-6">
          <Card padding="none">
            <button
              type="button"
              aria-expanded={prefsOpen}
              aria-controls="builder-prefs"
              onClick={() => setPrefsOpen((o) => !o)}
              className="flex min-h-touch w-full items-center gap-2 rounded-card px-4 py-2 text-left text-body-sm font-medium text-fg transition-colors duration-fast hover:bg-elevated/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Settings2 aria-hidden="true" className="h-4 w-4 text-muted" />
              Preferences
              <span className="text-caption font-normal text-muted">
                {prefs.model === 'ai-choice' && !prefs.domain ? 'Gunny chooses the model and domain' : `${prefs.model === 'ai-choice' ? 'Gunny picks the model' : prefs.model}${prefs.domain ? ` · ${prettyDomain(prefs.domain)}` : ''}`}
              </span>
              <ChevronDown aria-hidden="true" className={`ml-auto h-4 w-4 text-muted transition-transform duration-base ${prefsOpen ? 'rotate-180' : ''}`} />
            </button>
            {prefsOpen && (
              <div id="builder-prefs" className="space-y-4 border-t border-border px-4 pb-4 pt-3">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Field label="Preferred model" help="Leave it to Gunny unless you need a specific lane">
                    <ModelSelector value={prefs.model} onChange={(model) => setPrefs((p) => ({ ...p, model }))} allowAIChoice />
                  </Field>
                  <Field label="Target domain">
                    <Select value={prefs.domain} onChange={(e) => setPrefs((p) => ({ ...p, domain: e.target.value }))}>
                      <option value="">Any domain</option>
                      {domains.map((d) => (
                        <option key={d} value={d}>
                          {prettyDomain(d)}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <ParameterSlider label="Temperature" value={prefs.temperature} onChange={(temperature) => setPrefs((p) => ({ ...p, temperature }))} min={0} max={2} step={0.1} leftLabel="Focused" rightLabel="Creative" />
                <Field label="Max tokens">
                  <Input type="number" min={256} max={128000} step={256} value={prefs.maxTokens} onChange={(e) => setPrefs((p) => ({ ...p, maxTokens: parseInt(e.target.value, 10) || 4096 }))} />
                </Field>
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Max token presets">
                  {TOKEN_PRESETS.map((t) => (
                    <Chip key={t} size="md" tone="accent" selected={prefs.maxTokens === t} onClick={() => setPrefs((p) => ({ ...p, maxTokens: t }))}>
                      {t / 1024}K
                    </Chip>
                  ))}
                </div>
                <div className="flex items-center gap-2 border-t border-border pt-3">
                  <Button size="sm" icon={Sparkles} onClick={() => { setPrefsOpen(false); notify.success('Preferences apply to your next message'); }}>
                    Apply
                  </Button>
                  <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => setPrefs({ model: 'ai-choice', domain: '', temperature: 0.7, maxTokens: 4096 })}>
                    Reset
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6" role="log" aria-live="polite" aria-label="Conversation with Gunny">
          {unreachable ? (
            <ErrorState title="Gunny is unreachable" detail={humanize(gunny.error, { what: 'reaching the agent builder' })} onRetry={loadGunny} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.map((m, i) => {
                if (m.role === 'error') {
                  return (
                    <div key={i} className="rounded-card border border-danger/30 bg-danger/10">
                      <ErrorState compact title="That didn’t reach Gunny" detail={m.content} retryLabel="Send again" onRetry={() => send(m.retry)} />
                    </div>
                  );
                }
                const mine = m.role === 'user';
                return (
                  <div key={i} className={`flex items-start gap-3 ${mine ? 'flex-row-reverse' : ''}`}>
                    {mine ? (
                      <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-elevated text-muted">
                        <User className="h-4 w-4" />
                      </span>
                    ) : (
                      <AgentAvatar agent={GUNNY} size={32} rounded="rounded-control" />
                    )}
                    <div className={`min-w-0 max-w-[85%] rounded-card border px-4 py-3 ${mine ? 'border-accent/25 bg-accent/10' : 'border-border bg-card'}`}>
                      {mine ? (
                        <p className="whitespace-pre-wrap text-body text-fg">{m.content}</p>
                      ) : (
                        <div className={MARKDOWN}>
                          <ReactMarkdown>{m.content}</ReactMarkdown>
                        </div>
                      )}
                      {(m.usage || m.intent) && (
                        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border/60 pt-2 text-micro text-subtle">
                          {m.usage?.total_tokens != null && <span>{Number(m.usage.total_tokens).toLocaleString()} tokens</span>}
                          {m.usage?.model && <span>{m.usage.model}</span>}
                          {m.intent && (
                            <Chip size="xs" tone="warn" icon={Sparkles}>
                              Ready to create
                            </Chip>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {sending && (
                <div className="flex items-start gap-3">
                  <AgentAvatar agent={GUNNY} size={32} rounded="rounded-control" status="thinking" />
                  <div className="inline-flex items-center gap-2 rounded-card border border-border bg-card px-4 py-3 text-body-sm text-muted">
                    <Spinner label="Gunny is thinking" />
                    Gunny is thinking…
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        <div className="sticky bottom-0 border-t border-border bg-surface/90 px-4 py-3 backdrop-blur sm:px-6">
          <form
            className="mx-auto flex max-w-3xl items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <Textarea
              ref={inputRef}
              aria-label="Message to Gunny"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={unreachable ? 'Gunny is unreachable right now' : 'Describe the agent you want to build…'}
              disabled={sending || unreachable}
              className="min-w-0 resize-none"
            />
            <Button type="submit" size="lg" icon={Send} loading={sending} disabled={!input.trim() || unreachable}>
              Send
            </Button>
          </form>
          <div className="mx-auto mt-1.5 flex max-w-3xl items-center justify-between text-micro text-subtle">
            <span className="inline-flex items-center gap-1">
              <Kbd>↵</Kbd> to send · <Kbd>⇧</Kbd>
              <Kbd>↵</Kbd> for a new line
            </span>
            <span className="tabular-nums">{input.length} characters</span>
          </div>
        </div>
      </div>

      {/* ── draft panel (desktop) ── */}
      {!narrow && panelOpen && (
        <aside className="hidden w-96 shrink-0 overflow-y-auto border-l border-border bg-surface/40 p-5 lg:block" aria-label="Agent draft">
          {draft}
        </aside>
      )}

      {/* ── draft panel (phones) ── */}
      <Sheet isOpen={narrow && draftOpen} onClose={() => setDraftOpen(false)} side="bottom" title="Draft agent">
        <div className="pb-2">{draft}</div>
      </Sheet>

      <Modal
        isOpen={confirmNew}
        onClose={() => setConfirmNew(false)}
        size="sm"
        title="Start a new conversation?"
        description="The current conversation and draft are discarded."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmNew(false)}>
              Keep going
            </Button>
            <Button icon={RefreshCw} onClick={startNew}>
              Start new
            </Button>
          </>
        }
      />

      <Modal
        isOpen={Boolean(deploy)}
        onClose={() => !deploying && setDeploy(null)}
        closeOnBackdrop={false}
        size="lg"
        title="Deploy agent"
        description="Review the spec card before it joins the brigade."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeploy(null)} disabled={deploying}>
              Keep editing
            </Button>
            <Button icon={Rocket} loading={deploying} onClick={() => createAgent(deploy)}>
              Deploy agent
            </Button>
          </>
        }
      >
        {deploy && (
          <dl className="space-y-4">
            <div>
              <dt className="text-caption text-muted">Name</dt>
              <dd className="text-lead font-semibold text-fg-strong">
                {deploy.avatar ? `${deploy.avatar} ` : ''}
                {deploy.displayName || deploy.name || 'Unnamed agent'}
              </dd>
              {deploy.title && <dd className="text-body-sm text-muted">{deploy.title}</dd>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-caption text-muted">Domain</dt>
                <dd className="text-body text-fg">{deploy.domain ? prettyDomain(deploy.domain) : 'Not set'}</dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Model</dt>
                <dd className="font-mono text-body-sm text-fg">{deploy.model || preview.model || 'Default'}</dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Temperature</dt>
                <dd className="text-body text-fg">{deploy.temperature ?? preview.temperature ?? 0.7}</dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Max tokens</dt>
                <dd className="text-body text-fg">{Number(deploy.maxTokens || preview.maxTokens || 4096).toLocaleString()}</dd>
              </div>
            </div>
            {Array.isArray(deploy.capabilities) && deploy.capabilities.length > 0 && (
              <div>
                <dt className="mb-1.5 text-caption text-muted">Capabilities</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {deploy.capabilities.map((c) => (
                    <Chip key={c} tone="accent" size="xs">
                      {c}
                    </Chip>
                  ))}
                </dd>
              </div>
            )}
            {Array.isArray(deploy.tools) && deploy.tools.length > 0 && (
              <div>
                <dt className="mb-1.5 text-caption text-muted">Tools</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {deploy.tools.map((t) => (
                    <Chip key={typeof t === 'string' ? t : t?.name} tone="live" size="xs">
                      {typeof t === 'string' ? t : t?.name}
                    </Chip>
                  ))}
                </dd>
              </div>
            )}
            {deploy.systemPrompt && (
              <div>
                <dt className="mb-1.5 text-caption text-muted">System prompt</dt>
                <dd className="max-h-32 overflow-y-auto rounded-control border border-border bg-surface p-3 text-body-sm text-fg">{deploy.systemPrompt}</dd>
              </div>
            )}
          </dl>
        )}
      </Modal>
    </div>
  );
}
