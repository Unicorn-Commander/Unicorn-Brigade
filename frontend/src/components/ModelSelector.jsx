import { useEffect, useState } from 'react';
import { apiJson } from '../services/http';
import { Chip, Select } from './ui';

// Used only when /agent-builder/info cannot be reached, so the control is
// never empty. The live list from the API replaces it on load.
const FALLBACK_MODELS = [
  {
    provider: 'Anthropic',
    models: [
      { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', contextWindow: '200K' },
      { id: 'anthropic/claude-opus-4-5', name: 'Claude Opus 4.5', contextWindow: '200K' },
    ],
  },
  {
    provider: 'OpenAI',
    models: [
      { id: 'openai/gpt-4o', name: 'GPT-4o', contextWindow: '128K' },
      { id: 'openai/gpt-4o-mini', name: 'GPT-4o mini', contextWindow: '128K' },
    ],
  },
  {
    provider: 'Local',
    models: [{ id: 'qwen3.6-35b-a3b', name: 'Qwen 3.6 35B A3B', contextWindow: '128K' }],
  },
];

const groupByProvider = (models) => {
  const groups = new Map();
  models.forEach((m) => {
    const provider = m.provider || 'Other';
    if (!groups.has(provider)) groups.set(provider, []);
    groups.get(provider).push(m);
  });
  return [...groups.entries()].map(([provider, list]) => ({ provider, models: list }));
};

/**
 * ModelSelector — the one model picker: a grouped <Select> fed by
 * /agent-builder/info, with the chosen model's provider / context / price as
 * chips underneath. Works inside <Field> (id and aria-describedby pass through).
 */
export default function ModelSelector({
  value,
  onChange,
  disabled = false,
  allowAIChoice = false,
  className = '',
  id,
  invalid,
  'aria-label': ariaLabel = 'Model',
  'aria-describedby': describedBy,
}) {
  const [groups, setGroups] = useState(FALLBACK_MODELS);
  const [source, setSource] = useState('loading'); // loading | api | fallback

  useEffect(() => {
    let alive = true;
    apiJson('/agent-builder/info')
      .then((data) => {
        if (!alive) return;
        const list = data?.capabilities?.availableModels;
        const grouped = Array.isArray(list) && list.length ? groupByProvider(list) : [];
        if (grouped.length) {
          setGroups(grouped);
          setSource('api');
        } else {
          setSource('fallback');
        }
      })
      .catch(() => alive && setSource('fallback'));
    return () => {
      alive = false;
    };
  }, []);

  const selected =
    value && value !== 'ai-choice' ? groups.flatMap((g) => g.models.map((m) => ({ ...m, provider: m.provider || g.provider }))).find((m) => m.id === value) : null;
  // A model the roster uses but the list doesn't know stays selectable.
  const unknown = value && value !== 'ai-choice' && !selected ? value : null;

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <Select
        id={id}
        aria-label={ariaLabel}
        aria-describedby={describedBy}
        invalid={invalid}
        value={value || ''}
        onChange={(e) => onChange?.(e.target.value)}
        disabled={disabled}
      >
        {allowAIChoice && <option value="ai-choice">Let Gunny choose</option>}
        {!allowAIChoice && !value && <option value="">Choose a model…</option>}
        {unknown && <option value={unknown}>{unknown}</option>}
        {groups.map((group) => (
          <optgroup key={group.provider} label={group.provider}>
            {group.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name || m.id}
                {m.pricing ? ` · ${m.pricing}/1M` : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>
      {selected && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip size="xs">{selected.provider}</Chip>
          {selected.contextWindow && <Chip size="xs">{selected.contextWindow} context</Chip>}
          {selected.pricing && (
            <Chip size="xs" tone="ok">
              {selected.pricing}/1M tokens
            </Chip>
          )}
          <span className="font-mono text-micro text-subtle">{selected.id}</span>
        </div>
      )}
      {source === 'fallback' && <p className="text-caption text-muted">Live model list unavailable; showing the built-in list.</p>}
    </div>
  );
}
