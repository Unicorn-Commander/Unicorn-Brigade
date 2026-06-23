// Curated, known-good models for the per-window switcher. Kept deliberately
// small and safe (the agents' own models are drawn from this set) so the dock
// never offers a dead/EOL model. `''` = use the agent's own default.
export const MODEL_OPTIONS = [
  { id: '', label: 'Agent default' },
  { id: 'claude-sonnet-4', label: 'Claude Sonnet 4 · frontier' },
  { id: 'qwen3.6-35b-a3b', label: 'Qwen3.6 35B · local' },
];

// A friendly label for a model id (falls back to the raw id).
export function modelLabel(id) {
  if (!id) return 'Agent default';
  return MODEL_OPTIONS.find((m) => m.id === id)?.label || id;
}
