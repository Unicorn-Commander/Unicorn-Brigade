import { useId } from 'react';

/**
 * ParameterSlider — a labelled range whose value is always visible.
 *
 * A native <input type="range"> so arrow keys, Home/End, Page Up/Down and
 * screen readers work without any custom code; the thumb and track take the
 * accent through `accent-color`. The value sits in an <output> bound to the
 * input so assistive tech announces it as it changes.
 *
 *   <ParameterSlider label="Temperature" value={0.7} onChange={…} min={0} max={2} step={0.1}
 *                    leftLabel="Focused" rightLabel="Creative" description="…" />
 */
export default function ParameterSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.1,
  description,
  leftLabel,
  rightLabel,
  disabled = false,
  id: idProp,
}) {
  const auto = useId();
  const id = idProp || auto;
  const safe = typeof value === 'number' && !Number.isNaN(value) ? value : min;
  const decimals = step < 1 ? (String(step).split('.')[1] || '').length || 1 : 0;
  const shown = safe.toFixed(decimals);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="text-body-sm font-medium text-fg">
          {label}
        </label>
        <output htmlFor={id} className="font-mono text-body-sm tabular-nums text-accent">
          {shown}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={safe}
        disabled={disabled}
        aria-valuetext={shown}
        onChange={(e) => onChange?.(parseFloat(e.target.value))}
        className="h-2 w-full cursor-pointer rounded-full accent-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50"
      />
      {(leftLabel || rightLabel) && (
        <div className="flex items-center justify-between text-caption text-muted">
          <span>{leftLabel}</span>
          <span>{rightLabel}</span>
        </div>
      )}
      {description && <p className="text-caption text-muted">{description}</p>}
    </div>
  );
}
