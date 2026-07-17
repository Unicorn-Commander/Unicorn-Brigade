# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in Unicorn Brigade,
please report it privately. **Do not open a public issue for security
reports.**

- **Email:** security@unicorncommander.ai
- Please include a description of the issue, the affected version or commit,
  reproduction steps, and any relevant logs or proof-of-concept.
- We aim to acknowledge reports within 3 business days and to provide a
  remediation timeline after triage.

Please give us a reasonable window to investigate and ship a fix before any
public disclosure.

## Supported Versions

Brigade ships from `main`; there is no long-term-support back-porting policy
yet. Security fixes land on `main` and in the most recent tagged release.

| Version           | Supported          |
| ----------------- | ------------------ |
| `main` (latest)   | :white_check_mark: |
| Latest tagged release | :white_check_mark: |
| Older tags        | :x:                |

## Security Posture (one-page summary)

This is an **honest** snapshot of where Brigade stands. It documents both the
controls that exist and the gaps that do not yet, so that operators can make an
informed self-host decision.

### Authentication & Authorization

- **API-key auth.** Every mutating and admin route requires a credential passed
  as `X-API-Key` or `Authorization: Bearer <token>`. The bootstrap credential is
  `BRIGADE_ADMIN_KEY` (generate with `openssl rand -hex 32`). User-scoped API
  keys are validated against the database.
- **Keycloak / OIDC (optional).** When `BRIGADE_USE_KEYCLOAK=true`, Brigade
  validates Bearer JWTs issued by the configured realm (`OIDC_ISSUER`), caching
  JWKS with a TTL. Keycloak realm roles are mapped to Brigade roles
  (`app/auth/roles.py`). See [docs/self-host-sso.md](docs/self-host-sso.md).
- **RBAC.** Three roles — Admin, Operator, Viewer. Admin-only routes (e.g. the
  MCP registry, MCP `tools/call`, raw MCP protocol requests) are gated by a
  `require_admin` dependency.
- **Email allowlist.** `BRIGADE_ALLOWED_EMAILS` restricts early-access paths to
  a named set of identities on top of OIDC.
- **`AUTH_BYPASS`.** A development-only switch that disables key validation.
  **Never enable it in production.**

### Multi-Tenancy (RLS — now landing)

Postgres **row-level security** for per-tenant isolation is being introduced.
Until an operator has confirmed the RLS migration is applied and enforced,
treat a Brigade deployment as **single-tenant** and do not co-mingle data from
mutually-untrusted tenants in one instance. Track the RLS rollout before
relying on database-level tenant isolation.

### Secrets Handling

- All secrets are supplied via environment variables (`.env`, never committed —
  `.env` is git-ignored; only `.env.example` ships with placeholders).
- Generate `BRIGADE_ADMIN_KEY`, `SECRET_KEY`, database and Redis passwords with
  a CSPRNG (`openssl rand`) and rotate the admin key regularly.
- Do not paste real keys into issues, PRs, logs, or documentation.

### Tool & Code-Execution Isolation

- Agents run only their explicitly-assigned tools (per-agent allowlists).
- The shell / code-sandbox tool executes inside a Docker sandbox with resource
  limits, timeouts, and network isolation — not on the host.
- Path-traversal and input validation live in `app/security/validation.py`.

### Known Gaps / Not Yet Implemented

- **RLS enforcement** is in progress (see above) — verify before multi-tenant use.
- **Rate limiting and CSRF** hardening are not yet complete.
- **Automated dependency / SCA scanning** is not yet wired into CI.
- Test coverage is still being expanded; do your own review before trusting
  Brigade with sensitive data.
- Optional integrations (Slack, MS365/Google email, LiveKit, browser automation)
  each pull in third-party credentials — scope those tokens minimally.

If a control you need is not listed here, assume it is not present and verify in
the source before deploying.
