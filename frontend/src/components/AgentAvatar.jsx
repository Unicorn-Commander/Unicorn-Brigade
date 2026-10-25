import { useState, useEffect } from 'react';
import { Bot } from 'lucide-react';
import AVATARS from 'virtual:avatar-manifest';

// Live status -> avatar expression-variant suffix. Agents whose variants exist
// visibly react as they work; anything without a variant falls back to primary.
const STATE_SUFFIX = {
  thinking: '-thinking',
  tool: '-thinking',
  responding: '-success',
  streaming: '-success',
  done: '-success',
  error: '-alert',
};

/**
 * Single source of truth for rendering an agent's face.
 *
 * Precedence: an explicit `agent.avatarUrl` (image URL set via the API) wins
 * and shows the same single image for every state. Otherwise prefers the real
 * portrait at /avatars/<id>.webp; when `status` is an active state and an
 * expression variant exists (/avatars/<id>-<state>.webp), shows that so the
 * face reacts live. Broken images fall through the chain: avatarUrl ->
 * variant -> primary -> seed emoji -> the Bot mark. seed_agents.json stores an
 * EMOJI in `avatar`, not a path.
 *
 * `size` accepts a number (px) or a Tailwind size class string (e.g. "w-16 h-16").
 * `rounded` is a radius class: rounded-card (default) | rounded-control | rounded-full.
 */
export default function AgentAvatar({ agent, size = 40, rounded = 'rounded-card', status = 'idle', className = '' }) {
  // stage = index into the ordered image-source chain; past the end = emoji
  const [stage, setStage] = useState(0);

  const id = agent?.id;
  const avatarUrl = (typeof agent?.avatarUrl === 'string' && agent.avatarUrl.trim()) || null;
  const suffix = STATE_SUFFIX[status] || '';
  const sources = [];
  if (avatarUrl) sources.push(avatarUrl);
  // Conventional files only when they ship (build-time manifest), so an agent
  // with no portrait or no expression variant never requests a missing file.
  // The manifest is keyed by the raw id; the URL carries it encoded (ids can hold dots, spaces, '#').
  if (id && suffix && AVATARS.has(`${id}${suffix}`)) sources.push(`/avatars/${encodeURIComponent(`${id}${suffix}`)}.webp`);
  if (id && AVATARS.has(id)) sources.push(`/avatars/${encodeURIComponent(id)}.webp`);
  const chainKey = sources.join('|');

  // Re-try from the top whenever the source chain changes (new agent/state).
  useEffect(() => {
    setStage(0);
  }, [chainKey]);

  const emoji = (typeof agent?.avatar === 'string' && agent.avatar.trim()) || null;
  const label = agent?.displayName || agent?.name || 'agent';
  const numeric = typeof size === 'number';
  const dim = numeric ? { width: size, height: size } : undefined;
  const sizeClass = numeric ? '' : size;

  if (stage < sources.length) {
    return (
      <img
        src={sources[stage]}
        alt={label}
        onError={() => setStage((s) => s + 1)}
        style={dim}
        draggable={false}
        className={`${sizeClass} ${rounded} shrink-0 bg-surface object-cover ${className}`}
      />
    );
  }

  return (
    <div
      style={dim}
      role="img"
      aria-label={label}
      className={`${sizeClass} ${rounded} flex shrink-0 select-none items-center justify-center bg-surface ${className}`}
    >
      {emoji ? (
        <span style={{ fontSize: numeric ? Math.round(size * 0.55) : undefined }} className="leading-none">
          {emoji}
        </span>
      ) : (
        <Bot
          aria-hidden="true"
          className="text-accent"
          style={numeric ? { width: Math.round(size * 0.5), height: Math.round(size * 0.5) } : undefined}
        />
      )}
    </div>
  );
}
