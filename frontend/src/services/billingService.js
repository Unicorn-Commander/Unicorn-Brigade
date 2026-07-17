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

export const billingService = {
  // This org's current-period spend + caps + recent events.
  getUsage: (limit = 50) => get(`/billing/usage?limit=${limit}`),
  // Real upgrade info for the UpgradePrompt / 402 interceptor.
  getUpgradeRequirements: (feature) =>
    get(`/billing/upgrade-requirements${feature ? `?feature=${encodeURIComponent(feature)}` : ''}`),
};

export default billingService;
