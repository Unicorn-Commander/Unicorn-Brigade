/**
 * Unicorn Brigade marks — the real logo images from /public.
 * Agent faces live in components/AgentAvatar (portraits + live expressions);
 * these two are the brand mark and the two founding characters.
 */

/** Brigade mark — The General's logo used as the platform brand. */
export function BrigadeLogo({ size = 48, className = '' }) {
  return (
    <img
      src="/The_General_Logo.png"
      alt="Unicorn Brigade"
      width={size}
      height={size}
      className={`shrink-0 rounded-control ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/** The General — commanding meta-orchestrator. */
export function GeneralAvatar({ size = 64, className = '' }) {
  return (
    <img
      src="/The_General_Logo.png"
      alt="The General"
      width={size}
      height={size}
      className={`shrink-0 rounded-card shadow-e2 ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

/** Gunny — the agent builder. */
export function GunnyAvatar({ size = 64, className = '' }) {
  return (
    <img
      src="/Gunny_Logo.png"
      alt="Gunny"
      width={size}
      height={size}
      className={`shrink-0 rounded-card shadow-e2 ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

export default BrigadeLogo;
