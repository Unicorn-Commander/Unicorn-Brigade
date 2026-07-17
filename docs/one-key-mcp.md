# One-Key MCP: Wiring the `/mcp` Endpoint

Brigade exposes its built-in tools over the [Model Context Protocol
(MCP)](https://modelcontextprotocol.io) so that MCP-aware clients — Claude
Desktop, Claude Code, other assistants — can discover and call Brigade tools
with a single API key.

The implementation lives in `app/api/mcp_routes.py` and is mounted under
`/api/v1`.

## Endpoints

| Method & Path                       | Auth        | Purpose                                    |
| ----------------------------------- | ----------- | ------------------------------------------ |
| `GET  /api/v1/mcp/info`             | public      | Server info + capabilities                 |
| `GET  /api/v1/mcp/tools/list`       | public      | List available tools (MCP format)          |
| `GET  /api/v1/mcp/tools/openai`     | public      | Same, OpenAI function-calling format       |
| `GET  /api/v1/mcp/tools/anthropic`  | public      | Same, Anthropic tool format                |
| `POST /api/v1/mcp/tools/call`       | **admin**   | Invoke a tool by name                      |
| `GET  /api/v1/mcp/resources/list`   | public      | List MCP resources                         |
| `POST /api/v1/mcp/request`          | **admin**   | Raw MCP protocol request (JSON-RPC style)  |
| `GET  /api/v1/mcp/config`           | public      | Client config snippet                      |

Brigade's built-in tools (from the tool registry) are registered with the MCP
server on first request. Listing endpoints are open so a client can discover
capabilities; **anything that executes a tool (`tools/call`, raw `request`) is
admin-gated** by the `require_admin` dependency.

## Permissions

Tool execution requires an admin credential. Provide it as either header:

```
X-API-Key: <BRIGADE_ADMIN_KEY>
```
or
```
Authorization: Bearer <BRIGADE_ADMIN_KEY-or-user-JWT>
```

The bootstrap admin key is `BRIGADE_ADMIN_KEY` (see `.env.example`). When
Keycloak is enabled (`BRIGADE_USE_KEYCLOAK=true`) an admin-role JWT also
satisfies `require_admin` — see [self-host-sso.md](self-host-sso.md).

## Public alias

Behind the reverse proxy, the hosted deployment publishes a short alias so
clients can point at `https://<host>/mcp` instead of the full
`/api/v1/mcp/...` path. If you self-host and want the same convenience, add a
proxy rewrite from `/mcp` to `/api/v1/mcp` in your Traefik/nginx config. The
canonical application routes are always the `/api/v1/mcp/*` paths above.

## Example: list tools

```bash
curl https://<host>/api/v1/mcp/tools/list
```

## Example: call a tool

```bash
curl -X POST https://<host>/api/v1/mcp/tools/call \
  -H "X-API-Key: $BRIGADE_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "web_search",
        "arguments": {"query": "unicorn commander"}
      }'
```

## Example: Claude Desktop config

Fetch a ready-made client snippet from the server:

```bash
curl https://<host>/api/v1/mcp/config
```

Then wire it into your MCP client's server list, supplying your admin key as the
credential. Only the tools your key is authorized for will execute.
