import { useState, useEffect } from 'react';

// Live status -> avatar expression-variant suffix. Agents whose variants exist
// visibly react as they work; anything without a variant falls back to primary.
const STATE_SUFFIX = {
  thinking: '-thinking',
  tool: '-thinking',
  responding: '-success',
  streaming: '-success',
  error: '-alert',
};

/**
 * Single source of truth for rendering an agent's face.
 *
 * Prefers the real portrait at /avatars/<id>.webp (all 17 seed agents have one).
 * When `status` is an active state and an expression variant exists
 * (/avatars/<id>-<state>.webp), shows that so the face reacts live; it falls
 * back variant -> primary -> seed emoji -> unicorn. seed_agents.json stores an
 * EMOJI in `avatar`, not the webp path.
 *
 * `size` accepts a number (px) or a Tailwind size class string (e.g. "w-16 h-16").
 */
export default function AgentAvatar({
  agent,
  size = 40,
  rounded = 'rounded-xl',
  status = 'idle',
  className = '',
}) {
  // stage 0 = try expression variant, 1 = primary, 2 = emoji
  const [stage, setStage] = useState(0);

  const id = agent?.id;
  const suffix = STATE_SUFFIX[status] || '';
  const primary = id ? `/avatars/${id}.webp` : null;
  const variant = id && suffix ? `/avatars/${id}${suffix}.webp` : primary;

  // Re-try the (possibly new) variant whenever the target src changes.
  useEffect(() => {
    setStage(0);
  }, [variant]);

  const emoji = (typeof agent?.avatar === 'string' && agent.avatar.trim()) || '🦄';
  const label = agent?.displayName || agent?.name || 'agent';

  const numeric = typeof size === 'number';
  const dim = numeric ? { width: size, height: size } : undefined;
  const sizeClass = numeric ? '' : size;

  const src = stage === 0 ? variant : primary;

  if (primary && stage < 2) {
    return (
      <img
        src={src}
        alt={label}
        title={label}
        onError={() => setStage((s) => (s === 0 && suffix ? 1 : 2))}
        style={dim}
        draggable={false}
        className={`${sizeClass} ${rounded} object-cover bg-slate-900 shrink-0 transition-opacity ${className}`}
      />
    );
  }

  return (
    <div
      style={dim}
      aria-label={label}
      title={label}
      className={`${sizeClass} ${rounded} bg-slate-900 flex items-center justify-center select-none shrink-0 ${className}`}
    >
      <span style={{ fontSize: numeric ? Math.round(size * 0.55) : undefined }} className="leading-none">
        {emoji}
      </span>
    </div>
  );
}
