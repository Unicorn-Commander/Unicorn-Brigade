/**
 * Settings — preferences for this browser, the LLM providers behind the
 * platform, and the caller's personal API keys.
 *
 * Preferences are real and consumed (src/utils/preferences.js): theme →
 * src/utils/theme.js, defaultModel + streamResponses → the chat request path,
 * notifications → src/utils/notify.js. Keys: GET/POST/DELETE /users/me/api-keys;
 * the full key value is shown once, by KeyRevealModal, at creation.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Cpu, Key, Keyboard, LogIn, Monitor, Moon, Palette, Plus, RefreshCw, Sun, Trash2, Zap, Info } from 'lucide-react';
import KeyRevealModal from '../components/KeyRevealModal';
import Breadcrumbs from '../components/Breadcrumbs';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { getPreferences, savePreferences } from '../utils/preferences';
import { THEME_FAMILIES, applyTheme, applyThemeFamily, normalizeFamily, resolveTheme } from '../utils/theme';
import { apiJson } from '../services/http';
import {
  Button,
  Card,
  CardHeader,
  Chip,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  Kbd,
  LoadingState,
  Modal,
  Page,
  PageHeader,
  Select,
  Tabs,
  Toggle,
  Tooltip,
} from '../components/ui';

const THEME_TABS = [
  { id: 'system', label: 'System', icon: Monitor },
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
];

// Static swatches per family × mode — page, panel, accent fill, ok, warn,
// danger — copied from src/styles/tokens.css. The picker shows every family
// while only the chosen one is applied to the document, so these cannot be
// read from the live tokens. Keep in step with tokens.css.
const SWATCH_NAMES = ['page', 'panel', 'accent', 'ok', 'warning', 'danger'];
const FAMILY_SWATCHES = {
  brigade: {
    dark: ['232 30% 5%', '230 26% 9%', '332 78% 47%', '158 64% 52%', '40 95% 58%', '0 90% 70%'],
    light: ['220 30% 97%', '0 0% 100%', '332 76% 44%', '158 72% 24%', '32 92% 29%', '0 70% 42%'],
  },
  business: {
    dark: ['220 14% 6%', '220 12% 9%', '221 75% 54%', '158 64% 52%', '40 95% 58%', '0 90% 70%'],
    light: ['220 20% 97%', '0 0% 100%', '221 72% 46%', '158 72% 24%', '32 92% 29%', '0 70% 42%'],
  },
  graphite: {
    dark: ['0 0% 4%', '0 0% 7%', '0 0% 96%', '150 55% 56%', '40 90% 60%', '0 85% 70%'],
    light: ['0 0% 98%', '0 0% 100%', '0 0% 10%', '150 60% 26%', '32 90% 30%', '0 70% 42%'],
  },
};

/** Three selectable cards, one per theme family: a radio group with arrow keys. */
function FamilyPicker({ value, mode, onChange }) {
  const refs = useRef([]);
  const select = (i) => {
    const f = THEME_FAMILIES[i];
    if (!f) return;
    onChange(f.id);
    refs.current[i]?.focus();
  };
  const onKeyDown = (e, i) => {
    const n = THEME_FAMILIES.length;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') select((i + 1) % n);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') select((i - 1 + n) % n);
    else if (e.key === 'Home') select(0);
    else if (e.key === 'End') select(n - 1);
    else return;
    e.preventDefault();
  };
  return (
    <div role="radiogroup" aria-label="Theme family" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {THEME_FAMILIES.map((f, i) => {
        const selected = f.id === value;
        const swatches = (FAMILY_SWATCHES[f.id] || FAMILY_SWATCHES.brigade)[mode] || FAMILY_SWATCHES.brigade.dark;
        return (
          <button
            key={f.id}
            ref={(el) => (refs.current[i] = el)}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(f.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`rounded-card border p-3 text-left transition-[border-color,background-color,box-shadow] duration-fast ease-standard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card ${
              selected ? 'border-accent bg-accent/5 shadow-e1' : 'border-border bg-surface/50 hover:border-border-strong'
            }`}
          >
            <svg role="img" aria-label={`${f.label} palette, ${mode}: ${SWATCH_NAMES.join(', ')}`} viewBox="0 0 60 10" preserveAspectRatio="none" className="block h-3 w-full overflow-hidden rounded-chip border border-border">
              {swatches.map((hsl, k) => (
                <rect key={SWATCH_NAMES[k]} x={k * 10} y={0} width={10} height={10} fill={`hsl(${hsl})`} />
              ))}
            </svg>
            <span className="mt-2.5 flex items-center justify-between gap-2">
              <span className="text-body font-medium text-fg-strong">{f.label}</span>
              {selected && (
                <Chip tone="accent" size="xs" dot>
                  Active
                </Chip>
              )}
            </span>
            <span className="mt-0.5 block text-caption text-muted">{f.blurb}</span>
          </button>
        );
      })}
    </div>
  );
}

const PROVIDER_STATUS = {
  connected: { tone: 'ok', label: 'Connected' },
  degraded: { tone: 'warn', label: 'Degraded' },
  disconnected: { tone: 'danger', label: 'Unreachable' },
  error: { tone: 'danger', label: 'Unreachable' },
};
const providerStatus = (s) => PROVIDER_STATUS[s] || { tone: 'danger', label: 'Unreachable' };

const DAY = 86400000;
const fmtDate = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};
function timeAgo(iso) {
  if (!iso) return 'Never';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return 'Never';
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 45) return 'Just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d} day${d === 1 ? '' : 's'} ago`;
  return fmtDate(iso);
}

/** One labelled row in a settings card: text on the left, the control on the right. */
function SettingRow({ id, label, description, children }) {
  return (
    <div className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <label htmlFor={id} className="text-body font-medium text-fg">
          {label}
        </label>
        {description && <p className="mt-0.5 text-body-sm text-muted">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export default function Settings() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState([]);
  const [providersError, setProvidersError] = useState(null);
  const [models, setModels] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const [apiKeys, setApiKeys] = useState([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [keysError, setKeysError] = useState(null);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyError, setNewKeyError] = useState(null);
  const [creatingKey, setCreatingKey] = useState(false);
  const [revealedKey, setRevealedKey] = useState(null);
  const [revoking, setRevoking] = useState(null); // key awaiting confirmation
  const [revokeBusy, setRevokeBusy] = useState(false);

  const [preferences, setPreferences] = useState(getPreferences);
  const updatePref = (key, value) => setPreferences((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    savePreferences(preferences);
  }, [preferences]);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    const [p, m, s] = await Promise.allSettled([apiJson('/providers'), apiJson('/chat/models'), apiJson('/stats')]);
    if (p.status === 'fulfilled') {
      setProviders(p.value?.providers || []);
      setProvidersError(null);
    } else {
      setProviders([]);
      setProvidersError(p.reason);
    }
    setModels(m.status === 'fulfilled' ? m.value?.models || [] : []);
    setStats(s.status === 'fulfilled' ? s.value : null);
    setLoading(false);
  }, []);

  const loadApiKeys = useCallback(async () => {
    setKeysLoading(true);
    try {
      const data = await apiJson('/users/me/api-keys', { redirectOn401: false });
      setApiKeys(data?.keys || []);
      setKeysError(null);
    } catch (err) {
      setApiKeys([]);
      setKeysError(err);
    } finally {
      setKeysLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
    loadApiKeys();
  }, [loadSettings, loadApiKeys]);

  const createKey = async (e) => {
    e?.preventDefault?.();
    const name = newKeyName.trim();
    if (!name) {
      setNewKeyError('Give the key a name so you can tell it apart later.');
      return;
    }
    if (creatingKey) return;
    setCreatingKey(true);
    setNewKeyError(null);
    try {
      const created = await apiJson('/users/me/api-keys', { method: 'POST', body: JSON.stringify({ name }) });
      setRevealedKey(created); // the full key value is only returned once
      setNewKeyName('');
      notify.success('API key created');
      await loadApiKeys();
    } catch (err) {
      setNewKeyError(humanize(err, { what: 'creating the key' }));
    } finally {
      setCreatingKey(false);
    }
  };

  const confirmRevoke = async () => {
    if (!revoking) return;
    setRevokeBusy(true);
    try {
      await apiJson(`/users/me/api-keys/${revoking.id}`, { method: 'DELETE' });
      setApiKeys((prev) => prev.filter((k) => k.id !== revoking.id));
      notify.success(`Revoked “${revoking.name}”`);
      setRevoking(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'revoking the key' }));
    } finally {
      setRevokeBusy(false);
    }
  };

  const modelGroups = useMemo(() => {
    const groups = {};
    for (const m of models) (groups[m.category || 'other'] ||= []).push(m);
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [models]);

  // ── API key columns ────────────────────────────────────────────────────────
  const keyColumns = [
    {
      key: 'name',
      label: 'Name',
      render: (k) => (
        <span className="flex flex-col">
          <span className="font-medium text-fg-strong">{k.name}</span>
          <span className="font-mono text-caption text-muted">{k.keyPrefix}…</span>
        </span>
      ),
    },
    {
      key: 'permissions',
      label: 'Permissions',
      render: (k) => (
        <span className="inline-flex flex-wrap gap-1">
          {(k.permissions || []).map((p) => (
            <Chip key={p} size="xs">
              {p}
            </Chip>
          ))}
        </span>
      ),
    },
    { key: 'lastUsedAt', label: 'Last used', render: (k) => <span className="text-muted">{timeAgo(k.lastUsedAt)}</span> },
    {
      key: 'expiresAt',
      label: 'Expires',
      render: (k) => {
        if (!k.expiresAt) return <span className="text-muted">Never</span>;
        const left = new Date(k.expiresAt).getTime() - Date.now();
        if (left < 0) return <Chip tone="danger" size="xs">Expired {fmtDate(k.expiresAt)}</Chip>;
        if (left < 14 * DAY) return <Chip tone="warn" size="xs">In {Math.max(1, Math.round(left / DAY))} days</Chip>;
        return <span className="text-muted">{fmtDate(k.expiresAt)}</span>;
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (k) => {
        const expired = k.expiresAt && new Date(k.expiresAt) < new Date();
        const active = (k.isActive ?? true) && !expired;
        return (
          <Chip tone={active ? 'ok' : 'neutral'} size="xs" dot>
            {active ? 'Active' : expired ? 'Expired' : 'Revoked'}
          </Chip>
        );
      },
    },
    {
      key: 'actions',
      label: '',
      align: 'right',
      hideOnMobile: false,
      render: (k) => (
        <IconButton icon={Trash2} label={`Revoke ${k.name}`} size="sm" className="text-danger hover:text-danger" onClick={() => setRevoking(k)} />
      ),
    },
  ];

  // ── keys section states ────────────────────────────────────────────────────
  let keysBody;
  if (keysError && (keysError.status === 401 || keysError.status === 403)) {
    keysBody = (
      <EmptyState
        compact
        icon={Key}
        title="Sign in to manage your API keys"
        description="Personal keys belong to your account. Sign in and they appear here."
        action={
          <Button size="sm" icon={LogIn} onClick={() => navigate('/login')}>
            Sign in
          </Button>
        }
      />
    );
  } else {
    keysBody = (
      <>
        <form onSubmit={createKey} className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start">
          <Field label="New key name" error={newKeyError} className="flex-1" htmlFor="new-key-name">
            <Input value={newKeyName} onChange={(e) => { setNewKeyName(e.target.value); if (newKeyError) setNewKeyError(null); }} placeholder="e.g. CLI, n8n, staging" autoComplete="off" />
          </Field>
          <Button type="submit" icon={Plus} loading={creatingKey} className="sm:mt-[26px]">
            Create key
          </Button>
        </form>
        <DataTable
          caption="Your API keys"
          columns={keyColumns}
          rows={apiKeys}
          rowKey="id"
          dense
          loading={keysLoading}
          error={keysError && { title: 'Couldn’t load your API keys', detail: humanize(keysError, { what: 'loading your keys' }), onRetry: loadApiKeys }}
          empty={{ icon: Key, title: 'No API keys yet', description: 'Create one above to call the Brigade API from scripts, n8n or another app.' }}
        />
      </>
    );
  }

  return (
    <Page className="max-w-5xl">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="System"
        title="Settings"
        description="Preferences for this browser, the model providers behind the platform, and your personal API keys."
        actions={
          <Button variant="secondary" icon={RefreshCw} loading={loading} onClick={loadSettings}>
            Refresh
          </Button>
        }
      />

      <div className="space-y-5">
        {/* Appearance */}
        <Card>
          <CardHeader icon={Palette} title="Appearance" description="Applies immediately and is remembered in this browser." />
          <div className="pb-4">
            <p id="pref-family-label" className="text-body font-medium text-fg">
              Theme family
            </p>
            <p className="mb-3 mt-0.5 text-body-sm text-muted">Each family has a light and a dark side; pick the family here and the mode below.</p>
            <FamilyPicker
              value={normalizeFamily(preferences.themeFamily)}
              mode={resolveTheme(preferences.theme)}
              onChange={(id) => {
                updatePref('themeFamily', id);
                applyThemeFamily(id);
              }}
            />
          </div>
          <SettingRow id="pref-theme" label="Mode" description="System follows your operating system’s light or dark setting.">
            <Tabs
              variant="segmented"
              label="Color mode"
              idBase="pref-theme"
              tabs={THEME_TABS}
              value={preferences.theme}
              onChange={(v) => {
                updatePref('theme', v);
                applyTheme(v, preferences.themeFamily);
              }}
            />
          </SettingRow>
          <div className="mt-3 rounded-control border border-border bg-surface p-3" aria-label="Theme preview">
            <div className="flex flex-wrap items-center gap-2">
              {[
                ['bg-bg', 'Page'],
                ['bg-surface', 'Panel'],
                ['bg-card', 'Card'],
                ['bg-elevated', 'Tile'],
                ['bg-accent-fill', 'Accent'],
              ].map(([cls, name]) => (
                <Tooltip key={cls} content={name}>
                  <span tabIndex={0} aria-label={`${name} colour`} className={`h-7 w-7 rounded-chip border border-border ${cls} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`} />
                </Tooltip>
              ))}
              <span className="ml-auto inline-flex items-center gap-2">
                <Chip tone="ok" size="xs" dot>
                  Ready
                </Chip>
                <Chip tone="accent" size="xs">
                  Accent
                </Chip>
                <Button size="xs" variant="secondary">
                  Sample
                </Button>
              </span>
            </div>
          </div>
        </Card>

        {/* Chat defaults */}
        <Card>
          <CardHeader icon={Cpu} title="Chat defaults" description="Used by new conversations unless a chat window overrides them." />
          <div className="divide-y divide-border">
            <SettingRow id="pref-default-model" label="Default model" description={models.length ? `${models.length} models available` : loading ? 'Loading models…' : 'No models reported by the platform'}>
              <Select
                id="pref-default-model"
                aria-label="Default model"
                value={preferences.defaultModel}
                disabled={loading && !models.length}
                onChange={(e) => {
                  updatePref('defaultModel', e.target.value);
                  notify.success('Default model updated');
                }}
                className="sm:w-72"
              >
                <option value="">Auto (server default)</option>
                {modelGroups.map(([category, list]) => (
                  <optgroup key={category} label={category.charAt(0).toUpperCase() + category.slice(1)}>
                    {list.map((m) => (
                      <option key={m.id || m.name} value={m.id || m.name}>
                        {m.display_name || m.name || m.id}
                        {m.provider ? ` · ${m.provider}` : ''}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </SettingRow>
            <SettingRow id="pref-stream" label="Stream responses" description="Show text as it is generated instead of all at once.">
              <Toggle id="pref-stream" label="Stream responses" checked={preferences.streamResponses} onChange={(v) => updatePref('streamResponses', v)} />
            </SettingRow>
            <SettingRow id="pref-notifications" label="Notifications" description="Show success and info toasts. Errors always show.">
              <Toggle id="pref-notifications" label="Notifications" checked={preferences.notifications} onChange={(v) => updatePref('notifications', v)} />
            </SettingRow>
          </div>
        </Card>

        {/* LLM providers */}
        <Card>
          <CardHeader icon={Zap} title="LLM providers" description="Where inference is routed. Checked when this page loads." />
          {loading ? (
            <LoadingState variant="list" count={2} label="Checking providers" />
          ) : providersError ? (
            <ErrorState compact title="Couldn’t check the providers" detail={humanize(providersError, { what: 'checking providers' })} onRetry={loadSettings} />
          ) : providers.length === 0 ? (
            <EmptyState compact icon={Zap} title="No providers configured" description="Point the platform at Ops-Center or a local router and it appears here with its status." />
          ) : (
            <ul className="divide-y divide-border">
              {providers.map((p) => {
                const st = providerStatus(p.status);
                return (
                  <li key={p.id || p.name} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-body font-medium text-fg-strong">
                        {p.name}
                        {p.isDefault && (
                          <Chip tone="accent" size="xs">
                            Default
                          </Chip>
                        )}
                      </p>
                      <p className="truncate font-mono text-caption text-muted">{p.endpoint || p.url}</p>
                      {p.description && <p className="mt-0.5 text-body-sm text-muted">{p.description}</p>}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <Chip tone={st.tone} dot pulse={st.tone === 'ok'}>
                        {st.label}
                      </Chip>
                      {typeof p.latency_ms === 'number' && (
                        <Chip size="sm" className="tabular-nums">
                          {p.latency_ms} ms
                        </Chip>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* API keys */}
        <Card>
          <CardHeader
            icon={Key}
            title="API keys"
            description={
              <>
                Personal keys for the Brigade API, sent as an <code className="font-mono text-fg">X-API-Key</code> header. The full value is shown once, at creation.
              </>
            }
          />
          {keysBody}
        </Card>

        {/* Keyboard shortcuts + platform */}
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <Card>
            <CardHeader icon={Keyboard} title="Keyboard shortcuts" />
            <ul className="divide-y divide-border">
              {[
                { keys: ['⌘', 'K'], action: 'Command palette' },
                { keys: ['Enter'], action: 'Send message (in chat)' },
                { keys: ['Shift', 'Enter'], action: 'New line (in chat)' },
                { keys: ['Esc'], action: 'Close dialogs' },
              ].map((s) => (
                <li key={s.action} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0 text-body-sm text-fg">
                  <span>{s.action}</span>
                  <span className="inline-flex items-center gap-0.5">
                    {s.keys.map((k) => (
                      <Kbd key={k}>{k}</Kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader icon={Info} title="Platform" />
            <dl className="grid grid-cols-2 gap-3">
              <div>
                <dt className="text-caption text-muted">Version</dt>
                <dd className="mt-0.5 text-body font-medium text-fg">{stats?.version ? `v${stats.version}` : loading ? '…' : 'Not reported'}</dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Agents</dt>
                <dd className="mt-0.5 text-body font-medium tabular-nums text-fg">{stats?.totalAgents ?? (loading ? '…' : 'Not reported')}</dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Status</dt>
                <dd className="mt-0.5">
                  {stats?.status ? (
                    <Chip tone={stats.status === 'operational' ? 'ok' : 'warn'} size="xs" dot className="capitalize">
                      {stats.status}
                    </Chip>
                  ) : (
                    <span className="text-body text-muted">{loading ? '…' : 'Not reported'}</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Notifications</dt>
                <dd className="mt-0.5 flex items-center gap-1.5 text-body text-fg">
                  <Bell aria-hidden="true" className="h-3.5 w-3.5 text-muted" />
                  {preferences.notifications ? 'On' : 'Errors only'}
                </dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>

      {/* One-time reveal of a freshly created key (Lane B component) */}
      {revealedKey && <KeyRevealModal apiKey={revealedKey} onClose={() => setRevealedKey(null)} />}

      {/* Revoke confirmation */}
      <Modal
        isOpen={Boolean(revoking)}
        onClose={() => (revokeBusy ? null : setRevoking(null))}
        tone="danger"
        size="sm"
        title={revoking ? `Revoke “${revoking.name}”?` : 'Revoke key'}
        description="Anything still using this key stops working immediately. This can’t be undone."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevoking(null)} disabled={revokeBusy}>
              Keep it
            </Button>
            <Button variant="danger" icon={Trash2} loading={revokeBusy} onClick={confirmRevoke}>
              Revoke key
            </Button>
          </>
        }
      >
        {revoking && (
          <p className="font-mono text-body-sm text-muted">
            {revoking.keyPrefix}… · {(revoking.permissions || []).join(', ') || 'no permissions'}
          </p>
        )}
      </Modal>
    </Page>
  );
}
