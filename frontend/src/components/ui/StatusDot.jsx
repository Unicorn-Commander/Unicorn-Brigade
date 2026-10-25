/**
 * StatusDot + the shared AGENT STATUS vocabulary.
 *
 * One mapping from what an agent is doing to how it looks, used by the org
 * chart, the activity wall, the dock header, the chat page and the live feed —
 * so "thinking" is the same amber everywhere and the label a screen reader
 * hears is the same sentence everywhere.
 *
 *   idle · thinking · tool · responding · streaming · done · error · offline
 */
export const AGENT_STATUS = {
  idle: { tone: 'neutral', dot: 'bg-subtle', label: 'Idle', pulse: false },
  thinking: { tone: 'warn', dot: 'bg-warn', label: 'Thinking', pulse: true },
  tool: { tone: 'live', dot: 'bg-live', label: 'Running a tool', pulse: true },
  responding: { tone: 'ok', dot: 'bg-ok', label: 'Responding', pulse: true },
  streaming: { tone: 'ok', dot: 'bg-ok', label: 'Responding', pulse: true },
  done: { tone: 'ok', dot: 'bg-ok', label: 'Done', pulse: false },
  error: { tone: 'danger', dot: 'bg-danger', label: 'Needs attention', pulse: false },
  offline: { tone: 'neutral', dot: 'bg-subtle', label: 'Offline', pulse: false },
};

export function statusMeta(status) {
  return AGENT_STATUS[status] || AGENT_STATUS.idle;
}

const SIZES = { xs: 'h-1.5 w-1.5', sm: 'h-2 w-2', md: 'h-2.5 w-2.5', lg: 'h-3 w-3' };

/**
 * A coloured dot with the status as its accessible name. Put it where the
 * meaning is, next to the face or the name — never alone.
 *
 *   <StatusDot status="tool" size="md" />
 *   <StatusDot status="error" ring />   // adds a surface-coloured ring for
 *                                       // overlaying on an avatar corner
 */
export default function StatusDot({ status = 'idle', size = 'sm', ring = false, className = '', label }) {
  const m = statusMeta(status);
  return (
    <span
      role="img"
      aria-label={label || m.label}
      className={[
        'inline-block shrink-0 rounded-full',
        SIZES[size] || SIZES.sm,
        m.dot,
        m.pulse ? 'animate-pulse' : '',
        ring ? 'ring-2 ring-surface' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    />
  );
}
