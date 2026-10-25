import { useEffect, useState, useCallback, useRef } from 'react';
import api from '../services/api';

// The roster refreshes itself in the background so an agent built or imported
// elsewhere appears on the board without a reload. Silent: no skeleton flash,
// no error flip, no re-render unless something actually changed.
const DEFAULT_REFRESH_MS = 30000;

/**
 * Fetch the agent roster. Shared by Library / Orchestration / Command Center so
 * the agent list isn't refetched ad-hoc in each page. Tolerates both the
 * `{ agents: [...] }` and bare-array response shapes.
 *
 *   const { agents, loading, error, reload } = useAgents();
 *   useAgents({ refreshMs: 0 })   // one-shot, no background refresh
 */
export function useAgents({ refreshMs = DEFAULT_REFRESH_MS } = {}) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const signature = useRef('');

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.getAgents();
      const list = Array.isArray(data) ? data : data?.agents || [];
      const sig = JSON.stringify(list);
      if (sig !== signature.current) {
        signature.current = sig;
        setAgents(list);
      }
      setError(null);
    } catch (e) {
      if (!silent) setError(e);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const reload = useCallback(() => load(), [load]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!refreshMs) return undefined;
    const t = setInterval(() => {
      if (typeof document === 'undefined' || !document.hidden) load({ silent: true });
    }, refreshMs);
    return () => clearInterval(t);
  }, [refreshMs, load]);

  return { agents, loading, error, reload };
}

export default useAgents;
