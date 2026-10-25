import { useEffect, useMemo, useState } from 'react';
import { Save, Search } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import ModelSelector from './ModelSelector';
import ParameterSlider from './ParameterSlider';
import { Button, Chip, Field, Input, Modal, Select, Textarea } from './ui';

const RANKS = ['Field Marshal', 'General', 'Colonel', 'Lieutenant Colonel', 'Commander', 'Major', 'Professor', 'Captain', 'Chief Warrant Officer', 'Lieutenant', 'Gunnery Sergeant', 'Sergeant First Class', 'Sergeant', 'Corporal', 'Specialist', 'Private'];
const STATUSES = [
  { id: 'active', label: 'Active' },
  { id: 'draft', label: 'Draft' },
  { id: 'inactive', label: 'Inactive' },
  { id: 'archived', label: 'Archived' },
];

const prettyName = (id) => String(id).replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const toolNames = (tools = []) => tools.map((t) => (typeof t === 'string' ? t : t?.tool?.name || t?.name || t?.id)).filter(Boolean);

/**
 * AgentEditModal — the agent's record in one dialog: identity, persona,
 * model settings and tools. Saves with PUT /agents/:id and reports through
 * onSave(agent, { optimistic }) so the caller can update its list first and
 * roll back if the save fails (the returned function undoes the optimistic
 * update).
 */
export default function AgentEditModal({ agent, onClose, onSave }) {
  const [form, setForm] = useState(() => ({
    name: agent?.name || '',
    displayName: agent?.displayName || '',
    title: agent?.title || '',
    rank: agent?.rank || '',
    bio: agent?.bio || '',
    persona: agent?.persona || '',
    systemPrompt: agent?.systemPrompt || '',
    tools: toolNames(agent?.tools || agent?.agentTools || []),
    model: agent?.model || '',
    temperature: agent?.temperature ?? 0.7,
    maxTokens: agent?.maxTokens ?? 2000,
    status: agent?.status || 'active',
  }));
  const [catalog, setCatalog] = useState([]);
  const [toolQuery, setToolQuery] = useState('');
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    apiJson('/tools')
      .then((data) => {
        if (!alive) return;
        const list = Array.isArray(data) ? data : data?.tools || [];
        setCatalog(list.map((t) => ({ id: t.id || t.name, name: t.name || prettyName(t.id) })).filter((t) => t.id));
      })
      .catch(() => {
        /* the agent's own tools still render below; the library just can't be browsed */
      });
    return () => {
      alive = false;
    };
  }, []);

  const options = useMemo(() => {
    const known = new Set(catalog.map((t) => t.id));
    const extra = form.tools.filter((id) => !known.has(id)).map((id) => ({ id, name: prettyName(id) }));
    return [...extra, ...catalog];
  }, [catalog, form.tools]);
  const visible = useMemo(() => {
    const q = toolQuery.trim().toLowerCase();
    return q ? options.filter((t) => t.name.toLowerCase().includes(q) || t.id.toLowerCase().includes(q)) : options;
  }, [options, toolQuery]);

  const set = (patch) => {
    setForm((f) => ({ ...f, ...patch }));
    setErrors((e) => ({ ...e, ...Object.fromEntries(Object.keys(patch).map((k) => [k, undefined])) }));
  };
  const toggleTool = (id) => set({ tools: form.tools.includes(id) ? form.tools.filter((t) => t !== id) : [...form.tools, id] });

  const validate = () => {
    const next = {};
    if (!form.name.trim()) next.name = 'The id is required.';
    if (!form.displayName.trim()) next.displayName = 'A display name is required.';
    if (form.persona.trim().length < 10) next.persona = 'Describe the persona in at least a sentence.';
    if (form.temperature < 0 || form.temperature > 2) next.temperature = 'Between 0 and 2.';
    if (form.maxTokens < 100 || form.maxTokens > 128000) next.maxTokens = 'Between 100 and 128,000.';
    setErrors(next);
    return !Object.keys(next).length;
  };

  const submit = async (e) => {
    e?.preventDefault();
    if (!validate()) return;
    setSaving(true);
    setSubmitError(null);
    const rollback = onSave?.({ ...agent, ...form }, { optimistic: true });
    try {
      const updated = await apiJson(`/agents/${agent.id}`, { method: 'PUT', body: JSON.stringify(form) });
      notify.success(`${updated?.displayName || form.displayName} updated`);
      onSave?.({ ...agent, ...form, ...(updated || {}) }, { optimistic: false });
      onClose?.();
    } catch (err) {
      if (typeof rollback === 'function') rollback();
      setSubmitError(humanize(err, { what: 'saving the agent' }));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={saving ? undefined : onClose}
      closeOnBackdrop={false}
      size="2xl"
      title="Edit agent"
      description={agent?.displayName || agent?.name}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button icon={Save} loading={saving} onClick={submit}>
            Save changes
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-6">
        <section className="space-y-4">
          <h3 className="text-body-sm font-semibold uppercase tracking-wider text-muted">Identity</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Id" required error={errors.name} help="Lowercase, used in URLs and API calls">
              <Input value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="sgt-scribe" disabled={saving} className="font-mono" />
            </Field>
            <Field label="Display name" required error={errors.displayName}>
              <Input value={form.displayName} onChange={(e) => set({ displayName: e.target.value })} placeholder="Sgt. Scribe" disabled={saving} />
            </Field>
            <Field label="Title" help="The job, as it reads under the name">
              <Input value={form.title} onChange={(e) => set({ title: e.target.value })} placeholder="Meeting scribe" disabled={saving} />
            </Field>
            <Field label="Rank">
              <Select value={form.rank} onChange={(e) => set({ rank: e.target.value })} disabled={saving}>
                <option value="">No rank</option>
                {RANKS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select value={form.status} onChange={(e) => set({ status: e.target.value })} disabled={saving}>
                {STATUSES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Bio" help="One or two sentences shown on the card">
            <Textarea rows={2} value={form.bio} onChange={(e) => set({ bio: e.target.value })} disabled={saving} />
          </Field>
        </section>

        <section className="space-y-4">
          <h3 className="text-body-sm font-semibold uppercase tracking-wider text-muted">Persona and instructions</h3>
          <Field label="Persona" required error={errors.persona} help="Who the agent is and how it speaks">
            <Textarea rows={3} value={form.persona} onChange={(e) => set({ persona: e.target.value })} disabled={saving} />
          </Field>
          <Field label="System prompt" help="Detailed operating instructions; Markdown is fine">
            <Textarea rows={5} value={form.systemPrompt} onChange={(e) => set({ systemPrompt: e.target.value })} disabled={saving} className="font-mono text-body-sm" />
          </Field>
        </section>

        <section className="space-y-4">
          <h3 className="text-body-sm font-semibold uppercase tracking-wider text-muted">Model</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Model">
              <ModelSelector value={form.model} onChange={(value) => set({ model: value })} disabled={saving} />
            </Field>
            <Field label="Max tokens" error={errors.maxTokens} help="Longest reply the agent may write">
              <Input type="number" min={100} max={128000} step={256} value={form.maxTokens} onChange={(e) => set({ maxTokens: parseInt(e.target.value, 10) || 0 })} disabled={saving} />
            </Field>
          </div>
          <ParameterSlider
            label="Temperature"
            value={form.temperature}
            onChange={(value) => set({ temperature: value })}
            min={0}
            max={2}
            step={0.1}
            leftLabel="Focused"
            rightLabel="Creative"
            disabled={saving}
          />
          {errors.temperature && (
            <p role="alert" className="text-caption text-danger">
              {errors.temperature}
            </p>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-body-sm font-semibold uppercase tracking-wider text-muted">Tools</h3>
            <span className="text-caption text-muted">
              {form.tools.length} selected
            </span>
          </div>
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input type="search" size="sm" aria-label="Search tools" placeholder="Filter tools…" value={toolQuery} onChange={(e) => setToolQuery(e.target.value)} className="pl-9" disabled={saving} />
          </div>
          {visible.length ? (
            <ul className="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto" aria-label="Tools">
              {visible.map((tool) => (
                <li key={tool.id}>
                  <Chip tone="accent" size="md" selected={form.tools.includes(tool.id)} onClick={() => toggleTool(tool.id)} disabled={saving}>
                    {tool.name}
                  </Chip>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body-sm text-muted">{options.length ? 'No tools match.' : 'The tool library is not reachable right now; the agent keeps its current tools.'}</p>
          )}
        </section>

        {submitError && (
          <p role="alert" className="text-body-sm text-danger">
            {submitError}
          </p>
        )}
        <button type="submit" className="sr-only" tabIndex={-1} aria-hidden="true">
          Save
        </button>
      </form>
    </Modal>
  );
}
