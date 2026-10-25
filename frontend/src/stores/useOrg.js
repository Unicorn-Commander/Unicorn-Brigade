/**
 * Active-organization store (BR-2.2) — the tenancy spine for the UI.
 *
 * Holds the orgs the user belongs to and which one they're acting under. The
 * active org id is mirrored into localStorage (ACTIVE_ORG_KEY) so the unified
 * API client attaches it as X-Org-Id on every request (services/authHeaders.js).
 *
 * Switching org reloads the app: the whole product is org-scoped via that
 * header, so a reload is the honest, race-free way to make every already-mounted
 * surface reflect the new tenant (rather than shipping a switcher that silently
 * leaves stale data on the current page). Switching to the already-active org is
 * a guarded no-op — no reload, no toast.
 */
import { create } from 'zustand';
import { ACTIVE_ORG_KEY } from '../services/authHeaders';
import * as orgApi from '../services/orgService';

function persistActiveOrg(id) {
  try {
    if (id) localStorage.setItem(ACTIVE_ORG_KEY, id);
    else localStorage.removeItem(ACTIVE_ORG_KEY);
  } catch {
    /* storage unavailable — header simply falls back to the home org */
  }
}

function readStoredOrgId() {
  try {
    return localStorage.getItem(ACTIVE_ORG_KEY);
  } catch {
    return null;
  }
}

/** Resolve the active org: the stored one if still valid, else the personal
 *  org (metadata.personal), else the first membership. */
function resolveActive(orgs, storedId) {
  if (storedId && orgs.some((o) => o.id === storedId)) return storedId;
  const personal = orgs.find((o) => o?.metadata?.personal);
  return (personal || orgs[0])?.id || null;
}

const useOrg = create((set, get) => ({
  orgs: [],
  activeOrgId: null,
  loading: true,
  loaded: false,
  error: null,

  /** Load the caller's orgs and reconcile the active org + persisted header. */
  loadOrgs: async () => {
    set({ loading: true, error: null });
    try {
      const orgs = await orgApi.listOrgs();
      const storedId = readStoredOrgId();
      const activeOrgId = resolveActive(orgs, storedId);
      // Keep localStorage in lockstep so X-Org-Id (read live from storage) always
      // matches the org the UI shows as active.
      if (activeOrgId !== storedId) persistActiveOrg(activeOrgId);
      set({ orgs, activeOrgId, loading: false, loaded: true, error: null });
      return orgs;
    } catch (err) {
      // Keep the thrown error itself (status, detail) so a page can humanize it;
      // OrgSwitcher only needs its truthiness.
      set({
        orgs: [],
        loading: false,
        loaded: true,
        error: err || new Error('Failed to load organizations'),
      });
      return [];
    }
  },

  /**
   * Switch the active org. Returns false (no-op) when already active. Otherwise
   * persists the choice and reloads so every org-scoped surface re-renders under
   * the new tenant.
   */
  setActiveOrg: (id) => {
    if (!id || id === get().activeOrgId) return false;
    persistActiveOrg(id);
    set({ activeOrgId: id });
    if (typeof window !== 'undefined') window.location.reload();
    return true;
  },

  /** Create a team org, switch into it, and land on its management page. */
  createOrg: async ({ name, slug } = {}) => {
    const org = await orgApi.createOrg({ name, slug });
    persistActiveOrg(org.id);
    if (typeof window !== 'undefined') window.location.assign('/organization');
    return org;
  },
}));

export default useOrg;

/** Reactive selector for the full active-org record (incl. the caller's role). */
export function useActiveOrg() {
  return useOrg((s) => s.orgs.find((o) => o.id === s.activeOrgId) || null);
}
