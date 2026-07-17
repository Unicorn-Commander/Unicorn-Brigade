# Self-Host SSO (Keycloak / OIDC)

Brigade can authenticate users against your own Keycloak realm (or any
OIDC-compliant identity provider) instead of, or alongside, static API keys.
Two surfaces use it:

1. **Bearer JWT validation** — API clients present a Keycloak-issued access
   token as `Authorization: Bearer <jwt>`; Brigade validates it against the
   realm's JWKS. (`app/auth/keycloak.py`)
2. **Browser login flow** — the OIDC authorization-code + PKCE flow that sets a
   session cookie for the web UI. (`app/api/oidc_routes.py`)

Both are **off by default**. With `BRIGADE_USE_KEYCLOAK` unset/false, Brigade
uses only `X-API-Key` / `BRIGADE_ADMIN_KEY`.

## Enable it

Set these in `.env`:

```bash
# Turn on Keycloak/OIDC bearer validation
BRIGADE_USE_KEYCLOAK=true

# Your realm issuer (the base the .well-known lives under)
OIDC_ISSUER=https://auth.example.com/realms/uchub

# The client Brigade authenticates as
KEYCLOAK_CLIENT_ID=brigade

# Optional: audience to enforce. If unset, aud is not checked and azp is used.
# OIDC_AUDIENCE=brigade

# Optional: JWKS URL override (defaults to <issuer>/protocol/openid-connect/certs)
# KEYCLOAK_JWKS_URL=https://auth.example.com/realms/uchub/protocol/openid-connect/certs

# Optional: JWKS cache TTL in seconds (default 3600)
# OIDC_JWKS_TTL=3600
```

For the **browser login flow** (web UI), also set:

```bash
# Confidential client secret for the authorization-code exchange
KEYCLOAK_CLIENT_SECRET=<from Keycloak client credentials>

# Where Keycloak redirects back after login (must be a registered redirect URI)
BRIGADE_CALLBACK_URL=https://brigade.example.com/api/auth/oidc/callback

# Where to send the browser after login completes
BRIGADE_FRONTEND_URL=https://brigade.example.com

# Set false only for local http development
COOKIE_SECURE=true
```

The login endpoints are:

- `GET /api/auth/oidc/login` → returns `{authUrl}` for the frontend to redirect to
- `GET /api/auth/oidc/callback` → exchanges the code, sets the session cookie
- `GET /api/auth/oidc/logout` → clears the session

The authorization request uses scope `openid profile email`. An open-redirect
guard restricts the post-login landing to same-app relative paths.

## Role mapping

Brigade maps Keycloak **realm roles** to its three internal roles. The first
match (highest privilege) wins; unmatched users default to Viewer
(`app/auth/roles.py`):

| Keycloak realm role | Brigade role |
| ------------------- | ------------ |
| `admin`             | Admin        |
| `investigator`      | Operator     |
| `operator`          | Operator     |
| `client`            | Viewer       |
| `viewer`            | Viewer       |
| *(none matched)*    | Viewer       |

Admin-gated routes (MCP `tools/call`, MCP registry, raw MCP `request`) require a
token that maps to Brigade **Admin**.

## Email allowlist (`BRIGADE_ALLOWED_EMAILS`)

On top of OIDC you can restrict early-access paths to a named set of users. This
is an allowlist checked against the authenticated user's email:

```bash
# Comma-separated, case-insensitive. Empty = no allowlist restriction.
BRIGADE_ALLOWED_EMAILS=alice@example.com,bob@example.com
```

When set, any request to an early-access path from an email **not** in the list
is rejected even if the token is otherwise valid. Leave it empty to allow any
authenticated user through. (`app/auth/middleware.py`)

## Keycloak client setup checklist

1. Create a client (e.g. `brigade`) in your realm.
2. For the **web login flow**, make it a *confidential* client, enable the
   *Standard flow* (authorization code), and copy the client secret into
   `KEYCLOAK_CLIENT_SECRET`.
3. Add your `BRIGADE_CALLBACK_URL` to the client's **Valid redirect URIs**.
4. Assign realm roles (`admin`, `operator`, …) to users per the table above.
5. Confirm the realm's JWKS is reachable from Brigade at
   `<issuer>/protocol/openid-connect/certs`.

## Verifying

With Keycloak enabled, call an admin route with a realm-issued admin token:

```bash
curl https://brigade.example.com/api/v1/mcp/tools/list \
  -H "Authorization: Bearer $KEYCLOAK_ACCESS_TOKEN"
```

A `401` means the token failed validation (issuer/JWKS/audience mismatch or
expiry); a `403` means it validated but the mapped role lacks permission.
