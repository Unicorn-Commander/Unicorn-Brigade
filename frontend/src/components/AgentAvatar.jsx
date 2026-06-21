import { useState } from 'react';

/**
 * Single source of truth for rendering an agent's face.
 *
 * Prefers the real portrait at /avatars/<id>.webp (all 17 seed agents have one),
 * falls back to the seed `avatar` emoji, then to the unicorn. Replaces the
 * scattered `{agent.avatar || '🦄'}` usages — note seed_agents.json stores an
 * EMOJI in `avatar`, not the webp path, so those sites never showed the portrait.
 *
 * `size` accepts a number (px) or a Tailwind size class string (e.g. "w-16 h-16").
 */
export default function AgentAvatar({
  agent,
  size = 40,
  rounded = 'rounded-xl',
  className = '',
}) {
  const [failed, setFailed] = useState(false);

  const id = agent?.id;
  const webp = id ? `/avatars/${id}.webp` : null;
  const emoji = (typeof agent?.avatar === 'string' && agent.avatar.trim()) || '🦄';
  const label = agent?.displayName || agent?.name || 'agent';

  const numeric = typeof size === 'number';
  const dim = numeric ? { width: size, height: size } : undefined;
  const sizeClass = numeric ? '' : size;

  if (webp && !failed) {
    return (
      <img
        src={webp}
        alt={label}
        title={label}
        onError={() => setFailed(true)}
        style={dim}
        draggable={false}
        className={`${sizeClass} ${rounded} object-cover bg-slate-900 shrink-0 ${className}`}
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
