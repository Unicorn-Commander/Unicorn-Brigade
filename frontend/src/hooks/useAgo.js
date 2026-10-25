import { useEffect, useState } from 'react';

/** "updated 12s ago" that keeps itself current (re-renders every 5 s). */
export function useAgo(since) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, []);
  if (!since) return 'updating…';
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  if (s < 5) return 'updated just now';
  if (s < 60) return `updated ${s}s ago`;
  return `updated ${Math.round(s / 60)}m ago`;
}

export default useAgo;
