// BR-3.7 — usage / billing service. Talks to the /api/v1/billing/* surface
// (usage summary + real upgrade-requirements). Auth-aware via the shared client.
import { buildAuthHeaders } from './authHeaders';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

async function get(endpoint) {
  const res = await fetch(`${BASE}${endpoint}`, {
    credentials: 'include',
    headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
  });
  if (!res.ok) {
    const err = new Error(`billing request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * One shape for a metered event, whichever casing the server used.
 *
 * The real API serialises rows with UsageEvent.to_dict() — camelCase
 * (createdAt, eventType, agentId). The page used to read created_at /
 * event_type and rendered "—" for every When and Type cell (the 2026-10-24
 * audit, "When — Type —"). Normalising here keeps every consumer on one shape.
 */
export function normalizeUsageEvent(row) {
  if (!row || typeof row !== 'object') return row;
  return {
    ...row,
    created_at: row.createdAt ?? row.created_at ?? null,
    event_type: row.eventType ?? row.event_type ?? null,
    agent_id: row.agentId ?? row.agent_id ?? null,
    rate_tier: row.rateTier ?? row.rate_tier ?? null,
    source: row.source ?? null,
    model: row.model ?? null,
    tokens: Number(row.tokens ?? 0),
    cost: Number(row.cost ?? 0),
  };
}

export const billingService = {
  // This org's current-period spend + caps + recent events.
  getUsage: async (limit = 50) => {
    const usage = await get(`/billing/usage?limit=${limit}`);
    return usage && typeof usage === 'object'
      ? { ...usage, recent: Array.isArray(usage.recent) ? usage.recent.map(normalizeUsageEvent) : [] }
      : usage;
  },
  // Real upgrade info for the UpgradePrompt / 402 interceptor.
  getUpgradeRequirements: (feature) =>
    get(`/billing/upgrade-requirements${feature ? `?feature=${encodeURIComponent(feature)}` : ''}`),
};

export default billingService;
