import { useEffect, useState } from 'react';
import { Pencil, Save, X } from 'lucide-react';
import { humanize } from '../utils/errors';
import ModelSelector from './ModelSelector';
import ParameterSlider from './ParameterSlider';
import TagInput from './TagInput';
import { Button, Chip, Field, Input, SectionHeader, Toggle } from './ui';

const TOKEN_PRESETS = [2048, 4096, 8192, 16384, 32768];

// Every runtime parameter with the default the model provider would use when
// the agent does not state one. Read mode shows the effective value; edit
// mode edits a draft and saves the whole set at once.
const pick = (a = {}) => ({
  model: a.model || '',
  temperature: a.temperature ?? 0.7,
  maxTokens: a.maxTokens ?? 4096,
  topP: a.topP ?? 1.0,
  frequencyPenalty: a.frequencyPenalty ?? 0.0,
  presencePenalty: a.presencePenalty ?? 0.0,
  stop: Array.isArray(a.stop) ? a.stop : [],
  streaming: a.streaming ?? true,
  safeMode: a.safeMode ?? false,
  maxRetries: a.maxRetries ?? 3,
  timeout: a.timeout ?? 120,
});

function Row({ label, help, editing, value, children }) {
  if (editing) {
    return (
      <Field label={label} help={help}>
        {children}
      </Field>
    );
  }
  return (
    <div>
      <dt className="text-caption text-muted">{label}</dt>
      <dd className="mt-0.5 text-body text-fg">{value}</dd>
    </div>
  );
}

/**
 * AgentConfigurationTab — model and runtime parameters, read by default,
 * edited as one draft with Save/Cancel. `onSave(patch)` returns a promise;
 * the tab stays in edit mode and shows the reason if it rejects.
 */
export default function AgentConfigurationTab({ agent, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => pick(agent));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (!editing) setDraft(pick(agent));
  }, [agent, editing]);

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const cancel = () => {
    setDraft(pick(agent));
    setSaveError(null);
    setEditing(false);
  };
  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await onSave?.(draft);
      setEditing(false);
    } catch (err) {
      setSaveError(humanize(err, { what: 'saving the configuration' }));
    } finally {
      setSaving(false);
    }
  };

  const v = editing ? draft : pick(agent);
  const Wrap = editing ? 'div' : 'dl';

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Configuration"
        description="Model and runtime parameters. Changes apply on the agent’s next invocation."
        actions={
          editing ? (
            <>
              <Button variant="ghost" size="sm" icon={X} onClick={cancel} disabled={saving}>
                Cancel
              </Button>
              <Button size="sm" icon={Save} loading={saving} onClick={save}>
                Save
              </Button>
            </>
          ) : (
            <Button variant="secondary" size="sm" icon={Pencil} onClick={() => setEditing(true)}>
              Edit configuration
            </Button>
          )
        }
      />

      <section>
        <h3 className="mb-3 text-body-sm font-semibold uppercase tracking-wider text-muted">Model</h3>
        <Wrap className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <Row label="Model" editing={editing} value={<span className="font-mono text-body-sm">{v.model || 'Not set'}</span>}>
            <ModelSelector value={draft.model} onChange={(model) => set({ model })} disabled={saving} />
          </Row>
          <Row label="Max tokens" help="Longest reply the agent may write" editing={editing} value={v.maxTokens.toLocaleString()}>
            <Input type="number" min={256} max={128000} step={256} value={draft.maxTokens} onChange={(e) => set({ maxTokens: parseInt(e.target.value, 10) || 0 })} disabled={saving} />
          </Row>
          {editing && (
            <div className="flex flex-wrap gap-1.5 md:col-start-2" role="group" aria-label="Max token presets">
              {TOKEN_PRESETS.map((p) => (
                <Chip key={p} size="md" tone="accent" selected={draft.maxTokens === p} onClick={() => set({ maxTokens: p })} disabled={saving}>
                  {p / 1024}K
                </Chip>
              ))}
            </div>
          )}
          <div className="md:col-span-2">
            {editing ? (
              <ParameterSlider label="Temperature" value={draft.temperature} onChange={(temperature) => set({ temperature })} min={0} max={2} step={0.1} leftLabel="Focused" rightLabel="Creative" description="How much the agent varies its wording; 0 is deterministic." disabled={saving} />
            ) : (
              <Row label="Temperature" editing={false} value={v.temperature} />
            )}
          </div>
          {!editing && agent?.version != null && <Row label="Version" editing={false} value={agent.version} />}
        </Wrap>
      </section>

      <section>
        <h3 className="mb-3 text-body-sm font-semibold uppercase tracking-wider text-muted">Sampling</h3>
        <Wrap className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {editing ? (
            <>
              <ParameterSlider label="Top-P" value={draft.topP} onChange={(topP) => set({ topP })} min={0} max={1} step={0.05} leftLabel="Focused" rightLabel="Diverse" description="Nucleus sampling: the share of likely words the model may pick from." disabled={saving} />
              <ParameterSlider label="Frequency penalty" value={draft.frequencyPenalty} onChange={(frequencyPenalty) => set({ frequencyPenalty })} min={-2} max={2} step={0.1} leftLabel="Allow repetition" rightLabel="Discourage" disabled={saving} />
              <ParameterSlider label="Presence penalty" value={draft.presencePenalty} onChange={(presencePenalty) => set({ presencePenalty })} min={-2} max={2} step={0.1} leftLabel="Stay on topic" rightLabel="Explore" disabled={saving} />
              <Field label="Stop sequences" help="Strings that end a reply when the model writes them">
                <TagInput tags={draft.stop} onAdd={(t) => set({ stop: [...draft.stop, t] })} onRemove={(t) => set({ stop: draft.stop.filter((x) => x !== t) })} placeholder="END" maxTags={10} disabled={saving} />
              </Field>
            </>
          ) : (
            <>
              <Row label="Top-P" editing={false} value={v.topP} />
              <Row label="Frequency penalty" editing={false} value={v.frequencyPenalty} />
              <Row label="Presence penalty" editing={false} value={v.presencePenalty} />
              <Row
                label="Stop sequences"
                editing={false}
                value={
                  v.stop.length ? (
                    <span className="flex flex-wrap gap-1">
                      {v.stop.map((s) => (
                        <Chip key={s} size="xs" className="font-mono">
                          {s}
                        </Chip>
                      ))}
                    </span>
                  ) : (
                    'None'
                  )
                }
              />
            </>
          )}
        </Wrap>
      </section>

      <section>
        <h3 className="mb-3 text-body-sm font-semibold uppercase tracking-wider text-muted">Runtime</h3>
        <Wrap className="grid grid-cols-1 gap-5 md:grid-cols-2">
          {editing ? (
            <>
              <div className="flex items-center justify-between gap-3 rounded-control border border-border bg-surface/60 p-3">
                <label htmlFor="cfg-streaming" className="text-body text-fg">
                  Stream responses
                  <span className="block text-caption text-muted">Show the reply as it is written</span>
                </label>
                <Toggle id="cfg-streaming" checked={draft.streaming} onChange={(streaming) => set({ streaming })} disabled={saving} label="Stream responses" />
              </div>
              <div className="flex items-center justify-between gap-3 rounded-control border border-border bg-surface/60 p-3">
                <label htmlFor="cfg-safe" className="text-body text-fg">
                  Safe mode
                  <span className="block text-caption text-muted">Content filtering and safety checks</span>
                </label>
                <Toggle id="cfg-safe" checked={draft.safeMode} onChange={(safeMode) => set({ safeMode })} disabled={saving} label="Safe mode" />
              </div>
              <Field label="Max retries" help="Automatic retries after a provider failure">
                <Input type="number" min={0} max={10} value={draft.maxRetries} onChange={(e) => set({ maxRetries: parseInt(e.target.value, 10) || 0 })} disabled={saving} />
              </Field>
              <Field label="Timeout" help="Seconds to wait for a reply">
                <Input type="number" min={10} max={600} value={draft.timeout} onChange={(e) => set({ timeout: parseInt(e.target.value, 10) || 0 })} disabled={saving} />
              </Field>
            </>
          ) : (
            <>
              <Row label="Stream responses" editing={false} value={v.streaming ? 'On' : 'Off'} />
              <Row label="Safe mode" editing={false} value={v.safeMode ? 'On' : 'Off'} />
              <Row label="Max retries" editing={false} value={v.maxRetries} />
              <Row label="Timeout" editing={false} value={`${v.timeout} s`} />
            </>
          )}
        </Wrap>
      </section>

      {saveError && (
        <p role="alert" className="text-body-sm text-danger">
          {saveError}
        </p>
      )}
    </div>
  );
}
