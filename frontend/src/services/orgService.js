/**
 * Organization (tenancy) API client — BR-2.2.
 *
 * Thin wrappers over the BR-2.1 org-lifecycle routes (app/api/org_routes.py),
 * all mounted under /api/v1. Every call goes through the unified `apiJson`
 * client (services/http.js) so auth + the X-Org-Id active-org header
 * (services/authHeaders.js) are attached uniformly and 401s recover.
 *
 * Backend authz recap (enforced server-side, mirrored in the UI gates):
 *   - org CRUD reads: any member; rename (PATCH): owner/admin only.
 *   - invitation create/list/revoke: owner/admin AND the caller must be ACTING
 *     UNDER the target org (X-Org-Id == org_id) or the route 409s. The UI only
 *     ever manages the ACTIVE org, so the header always matches.
 *   - accept is cross-tenant (token-bearer) and needs no active-org header.
 */
import { apiJson } from './http';

/** Per-org role vocabulary (mirrors app/db/org_service.py). */
export const ORG_ROLES = { OWNER: 'owner', ADMIN: 'admin', MEMBER: 'member' };

/** Owner/admin may rename the org, invite, and revoke. Members are read-only. */
export function canManageOrg(role) {
  return role === ORG_ROLES.OWNER || role === ORG_ROLES.ADMIN;
}

/** GET /orgs — every org the caller belongs to, each with their per-org role. */
export async function listOrgs() {
  const data = await apiJson('/orgs');
  return data?.orgs || [];
}

/** GET /orgs/current — the org the caller is acting under (X-Org-Id / home). */
export async function getCurrentOrg() {
  return apiJson('/orgs/current');
}

/** POST /orgs — create a team org; the caller becomes its owner. */
export async function createOrg({ name, slug } = {}) {
  return apiJson('/orgs', {
    method: 'POST',
    body: JSON.stringify(slug ? { name, slug } : { name }),
  });
}

/** PATCH /orgs/{id} — rename / re-slug an org (owner/admin). */
export async function updateOrg(orgId, updates) {
  return apiJson(`/orgs/${orgId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

/** GET /orgs/{id}/members — members with email/name + per-org role. */
export async function listMembers(orgId) {
  const data = await apiJson(`/orgs/${orgId}/members`);
  return data?.members || [];
}

/**
 * GET /orgs/{id}/invitations — invitations for the org (owner/admin).
 * Tokens are never returned here. `status` filters (pending|accepted|…).
 */
export async function listInvitations(orgId, status) {
  const data = await apiJson(`/orgs/${orgId}/invitations`, {
    params: status ? { status_filter: status } : undefined,
  });
  return data?.invitations || [];
}

/**
 * POST /orgs/{id}/invitations — invite an email (owner/admin). Returns the
 * invite INCLUDING its one-time token so the manager can deliver the link
 * out-of-band (email delivery is a backend stub in BR-2.1).
 */
export async function createInvitation(orgId, { email, role = ORG_ROLES.MEMBER } = {}) {
  return apiJson(`/orgs/${orgId}/invitations`, {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  });
}

/** DELETE /orgs/{id}/invitations/{invId} — revoke a pending invite (owner/admin). */
export async function revokeInvitation(orgId, invitationId) {
  return apiJson(`/orgs/${orgId}/invitations/${invitationId}`, { method: 'DELETE' });
}

/** POST /orgs/invitations/accept — join an org by its invite token. */
export async function acceptInvitation(token) {
  return apiJson('/orgs/invitations/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}
