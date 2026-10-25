import { useCallback, useEffect, useRef, useState } from 'react';
import { apiJson } from '../services/http';

/**
 * The autonomy catalogue (GET /api/v1/autonomy): every agent job that runs on
 * its own, inside Brigade and outside it, with health computed by the API.
 *
 *   const autonomy = useAutonomy();                 // refreshes every 60 s
 *   const autonomy = useAutonomy({ refreshMs: 0 }); // one read (agent detail)
 *
 * The Command Center owns ONE instance and hands it to the Autonomous view
 * and to the org-chart badges, so the board never fetches the list twice.
 * A failed refresh keeps the last good list and sets `error`; the view says
 * "Refresh failed" instead of blanking what it already showed.
 */
export function useAutonomy({ refreshMs = 60000 } = {}) {
  const [data, setData] = useState(null); // { items, counts, generatedAt }
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const alive = useRef(true);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const res = await apiJson('/autonomy');
      if (!alive.current) return;
      setData({
        items: Array.isArray(res?.items) ? res.items : [],
        counts: res?.counts && typeof res.counts === 'object' ? res.counts : null,
        generatedAt: res?.generatedAt || null,
      });
      setUpdatedAt(Date.now());
      setError(null);
    } catch (err) {
      if (alive.current) setError(err);
    } finally {
      if (alive.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    load();
    if (!refreshMs) {
      return () => {
        alive.current = false;
      };
    }
    const t = setInterval(() => {
      if (typeof document === 'undefined' || !document.hidden) load({ silent: true });
    }, refreshMs);
    return () => {
      alive.current = false;
      clearInterval(t);
    };
  }, [load, refreshMs]);

  /** Drop one item locally (after a delete) without waiting for the next read. */
  const removeItem = useCallback((id) => {
    setData((d) => (d ? { ...d, items: d.items.filter((it) => it.id !== id) } : d));
  }, []);

  return { data, items: data?.items || [], counts: data?.counts || null, loading, refreshing, error, updatedAt, reload: load, removeItem };
}

export default useAutonomy;
