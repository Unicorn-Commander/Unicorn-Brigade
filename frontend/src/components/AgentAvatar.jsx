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
 * Precedence: an explicit `agent.avatarUrl` (image URL set via the API) wins
 * and shows the same single image for every state. Otherwise prefers the real
 * portrait at /avatars/<id>.webp (all 17 seed agents have one); when `status`
 * is an active state and an expression variant exists
 * (/avatars/<id>-<state>.webp), shows that so the face reacts live. Broken
 * images fall through the chain: avatarUrl -> variant -> primary -> seed
 * emoji -> unicorn. seed_agents.json stores an EMOJI in `avatar`, not a path.
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
  // stage = index into the ordered image-source chain; past the end = emoji
  const [stage, setStage] = useState(0);

  const id = agent?.id;
  const avatarUrl =
    (typeof agent?.avatarUrl === 'string' && agent.avatarUrl.trim()) || null;
  const suffix = STATE_SUFFIX[status] || '';
  const primary = id ? `/avatars/${id}.webp` : null;
  const variant = id && suffix ? `/avatars/${id}${suffix}.webp` : null;

  // Ordered image sources: explicit URL first, then the convention chain.
  const sources = [];
  if (avatarUrl) sources.push(avatarUrl);
  if (variant) sources.push(variant);
  if (primary) sources.push(primary);

  const chainKey = sources.join('|');

  // Re-try from the top whenever the source chain changes (new agent/state).
  useEffect(() => {
    setStage(0);
  }, [chainKey]);

  const emoji = (typeof agent?.avatar === 'string' && agent.avatar.trim()) || '🦄';
  const label = agent?.displayName || agent?.name || 'agent';

  const numeric = typeof size === 'number';
  const dim = numeric ? { width: size, height: size } : undefined;
  const sizeClass = numeric ? '' : size;

  if (stage < sources.length) {
    return (
      <img
        src={sources[stage]}
        alt={label}
        title={label}
        onError={() => setStage((s) => s + 1)}
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
