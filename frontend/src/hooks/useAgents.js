import { useEffect, useState, useCallback } from 'react';
import api from '../services/api';

/**
 * Fetch the agent roster. Shared by Library / Orchestration / Command Center so
 * the agent list isn't refetched ad-hoc in each page. Tolerates both the
 * `{ agents: [...] }` and bare-array response shapes.
 */
export function useAgents() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getAgents();
      setAgents(Array.isArray(data) ? data : data?.agents || []);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { agents, loading, error, reload };
}

export default useAgents;
