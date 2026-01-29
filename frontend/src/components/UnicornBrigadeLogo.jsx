/**
 * Unicorn Brigade Logo Components
 * Uses actual logo images from /public for The General and Gunny.
 */

/**
 * Brigade mark — The General logo used as the platform brand.
 */
export function BrigadeLogo({ size = 48, className = '' }) {
  return (
    <img
      src="/The_General_Logo.png"
      alt="Unicorn Brigade"
      className={`rounded-lg ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/**
 * The General — commanding meta-orchestrator avatar.
 */
export function GeneralAvatar({ size = 64, className = '' }) {
  return (
    <img
      src="/The_General_Logo.png"
      alt="The General"
      className={`rounded-lg shadow-lg shadow-purple-500/20 ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/**
 * Gunny — the agent builder drill sergeant avatar.
 */
export function GunnyAvatar({ size = 64, className = '' }) {
  return (
    <img
      src="/Gunny_Logo.png"
      alt="Gunny"
      className={`rounded-lg shadow-lg shadow-amber-500/20 ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/**
 * Generic agent avatar — uses agent's emoji or fallback.
 */
export function AgentAvatar({ emoji = '🦄', size = 40, className = '' }) {
  return (
    <div
      className={`flex items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 ${className}`}
      style={{ width: size, height: size }}
    >
      <span style={{ fontSize: size * 0.55 }} role="img" aria-label="Agent">
        {emoji}
      </span>
    </div>
  );
}

export default BrigadeLogo;
