import { useEffect, useState } from 'react';
import { currentTheme } from '../../utils/tokens';

/**
 * Small environment hooks for the Command Center. (Candidates for hooks/ —
 * kept here because this lane's file set is components/command/*.)
 */

/** True while the media query matches; re-evaluates on change. */
export function useMediaQuery(query) {
  const get = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches;
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    if (mq.addEventListener) mq.addEventListener('change', on);
    else mq.addListener(on);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', on);
      else mq.removeListener(on);
    };
  }, [query]);
  return matches;
}

/** Below Tailwind's `sm` breakpoint — the dock becomes a sheet, the minimap goes. */
export const usePhone = () => useMediaQuery('(max-width: 639px)');

/** The OS "reduce motion" setting: no particles, no spin, no pulse. */
export const useReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)');

/** Changes when the theme flips, so canvas/graph code can re-read its tokens. */
export function useThemeKey() {
  const [key, setKey] = useState(() => currentTheme());
  useEffect(() => {
    if (typeof MutationObserver === 'undefined') return undefined;
    const obs = new MutationObserver(() => setKey(currentTheme()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);
  return key;
}
