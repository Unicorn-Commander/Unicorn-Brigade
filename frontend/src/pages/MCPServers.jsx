/**
 * MCP Servers — the registry of Model Context Protocol servers agents can
 * draw tools from. Cards are drawn from what the list endpoint actually
 * returns (name, display_name, description, capabilities, transport, enabled,
 * running); command, args and env vars come from the detail endpoint inside
 * Manage. Start/Stop report their result and keep a failure's reason on the
 * card until the next attempt.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  BookOpen,
  Package,
  RefreshCw,
  Search,
  Server,
  X,
} from "lucide-react";
import { apiJson } from "../services/http";
import notify from "../utils/notify";
import { humanize } from "../utils/errors";
import MCPServerCard from "../components/MCPServerCard";
import MCPToolList from "../components/MCPToolList";
import MCPServerControlPanel from "../components/MCPServerControlPanel";
import Breadcrumbs from "../components/Breadcrumbs";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  OfflineState,
  Page,
  PageHeader,
  Select,
  StatCard,
} from "../components/ui";

const POLL_MS = 10000;
const text = (v) => String(v || "").toLowerCase();

export default function MCPServers() {
  const navigate = useNavigate();
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(
    typeof navigator !== "undefined" && navigator.onLine === false,
  );
  const [running, setRunning] = useState(null); // Set of names from /servers/running, null until polled
  const [pending, setPending] = useState({}); // name → 'start' | 'stop'
  const [failures, setFailures] = useState({}); // name → human reason
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [toolsFor, setToolsFor] = useState(null); // { server, state, list, error }
  const [controlServer, setControlServer] = useState(null);

  const pollRunning = useCallback(async () => {
    try {
      const data = await apiJson("/mcp/registry/servers/running");
      const list = data?.servers || data?.running_servers || [];
      setRunning(new Set(list.map((s) => s.name).filter(Boolean)));
    } catch {
      /* keep the last known set; the list endpoint's `running` flag still applies */
    }
  }, []);

  const load = useCallback(
    async ({ quiet = false } = {}) => {
      if (quiet) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const data = await apiJson("/mcp/registry/servers");
        setServers(Array.isArray(data) ? data : data?.servers || []);
        await pollRunning();
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [pollRunning],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const id = setInterval(pollRunning, POLL_MS);
    return () => clearInterval(id);
  }, [pollRunning]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, [load]);

  const statusOf = (s) =>
    failures[s.name]
      ? "error"
      : (running ? running.has(s.name) : s.running || s.status === "running")
        ? "running"
        : "stopped";

  const stats = useMemo(() => {
    const up = servers.filter((s) => statusOf(s) === "running").length;
    const declared = servers.reduce(
      (n, s) => n + (Array.isArray(s.capabilities) ? s.capabilities.length : 0),
      0,
    );
    return { up, total: servers.length, declared };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servers, running, failures]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return servers.filter((s) => {
      if (statusFilter && statusOf(s) !== statusFilter) return false;
      if (!q) return true;
      const caps = Array.isArray(s.capabilities) ? s.capabilities : [];
      return (
        text(s.name).includes(q) ||
        text(s.display_name).includes(q) ||
        text(s.description).includes(q) ||
        caps.some((c) => text(c).includes(q))
      );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [servers, query, statusFilter, running, failures]);

  const hasFilters = Boolean(query || statusFilter);
  const clearFilters = () => {
    setQuery("");
    setStatusFilter("");
  };

  const act = async (server, what) => {
    const title = server.display_name || server.name;
    setPending((p) => ({ ...p, [server.name]: what }));
    try {
      await apiJson(
        `/mcp/registry/servers/${encodeURIComponent(server.name)}/${what}`,
        { method: "POST" },
      );
      setFailures((f) => {
        const next = { ...f };
        delete next[server.name];
        return next;
      });
      setRunning((r) => {
        const next = new Set(
          r || servers.filter((s) => s.running).map((s) => s.name),
        );
        if (what === "start") next.add(server.name);
        else next.delete(server.name);
        return next;
      });
      notify.success(`${title} ${what === "start" ? "started" : "stopped"}`);
      pollRunning();
    } catch (err) {
      const reason = humanize(err, { what: `${what}ing ${title}` });
      setFailures((f) => ({ ...f, [server.name]: reason }));
      notify.error(`${title}: ${reason}`);
    } finally {
      setPending((p) => {
        const next = { ...p };
        delete next[server.name];
        return next;
      });
    }
  };

  const viewTools = async (server) => {
    setToolsFor({ server, state: "loading", list: [], error: null });
    try {
      const detail = await apiJson(
        `/mcp/registry/servers/${encodeURIComponent(server.name)}`,
      );
      const caps = Array.isArray(detail?.capabilities)
        ? detail.capabilities
        : Array.isArray(server.capabilities)
          ? server.capabilities
          : [];
      const list = caps.map((c) => (typeof c === "string" ? { name: c } : c));
      setToolsFor({ server, state: "ready", list, error: null });
    } catch (err) {
      setToolsFor({ server, state: "error", list: [], error: err });
    }
  };

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !servers.length) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = (
      <LoadingState variant="cards" count={6} label="Loading MCP servers" />
    );
  } else if (error) {
    body = (
      <ErrorState
        title="Couldn’t load the MCP registry"
        detail={humanize(error, { what: "loading MCP servers" })}
        onRetry={load}
      />
    );
  } else if (!servers.length) {
    body = (
      <EmptyState
        icon={Server}
        title="No MCP servers registered"
        description="An MCP server gives every agent a set of tools: GitHub, a filesystem, a database, a browser. Register one on the API host and it appears here."
        action={
          <Button icon={BookOpen} onClick={() => navigate("/mcp-docs")}>
            Read the MCP guide
          </Button>
        }
      />
    );
  } else if (!filtered.length) {
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No servers match"
        description="Try another word, or clear the status filter."
        action={
          <Button variant="secondary" size="sm" icon={X} onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else {
    body = (
      <ul
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
        aria-label="MCP servers"
      >
        {filtered.map((server) => (
          <li key={server.name}>
            <MCPServerCard
              server={server}
              status={statusOf(server)}
              reason={failures[server.name]}
              busy={Boolean(pending[server.name])}
              onStart={(s) => act(s, "start")}
              onStop={(s) => act(s, "stop")}
              onViewTools={viewTools}
              onManage={setControlServer}
            />
          </li>
        ))}
      </ul>
    );
  }

  const quiet = !loading && (error || !servers.length); // nothing to filter yet
  const description =
    loading || quiet
      ? "Tool servers agents can draw on"
      : `${stats.up} of ${stats.total} running · ${stats.declared} declared tool${stats.declared === 1 ? "" : "s"}`;

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Tools"
        title="MCP Servers"
        description={description}
        actions={
          <Button
            variant="secondary"
            icon={RefreshCw}
            loading={refreshing}
            onClick={() => load({ quiet: true })}
          >
            Refresh
          </Button>
        }
      />

      {!loading && !error && servers.length > 0 && (
        <div className="mb-5 hidden gap-4 sm:grid sm:grid-cols-3">
          <StatCard icon={Activity} label="Running now" value={stats.up} />
          <StatCard
            icon={Server}
            label="Registered servers"
            value={stats.total}
          />
          <StatCard
            icon={Package}
            label="Declared tools (registry)"
            value={stats.declared}
          />
        </div>
      )}

      {!quiet && (
        <Card padding="sm" className="mb-5">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto]">
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              />
              <Input
                type="search"
                aria-label="Search servers"
                placeholder="Search servers, tools…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              aria-label="Filter by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="md:w-44"
            >
              <option value="">Any status</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
              <option value="error">Error</option>
            </Select>
          </div>
          {hasFilters && !loading && (
            <div className="mt-2 flex items-center gap-2 text-caption text-muted">
              <span>
                {filtered.length} match{filtered.length === 1 ? "" : "es"}
              </span>
              <Button variant="link" size="xs" onClick={clearFilters}>
                Clear
              </Button>
            </div>
          )}
        </Card>
      )}

      {body}

      {toolsFor && (
        <MCPToolList
          server={toolsFor.server}
          tools={toolsFor.list}
          loading={toolsFor.state === "loading"}
          error={toolsFor.state === "error" ? toolsFor.error : null}
          onRetry={() => viewTools(toolsFor.server)}
          onClose={() => setToolsFor(null)}
        />
      )}
      {controlServer && (
        <MCPServerControlPanel
          server={controlServer}
          onClose={() => {
            setControlServer(null);
            pollRunning();
          }}
          onServerUpdated={(detail) => {
            if (!detail?.name) return;
            setServers((prev) =>
              prev.map((s) =>
                s.name === detail.name ? { ...s, ...detail } : s,
              ),
            );
            if (typeof detail.running === "boolean") {
              setRunning((r) => {
                const next = new Set(r || []);
                if (detail.running) next.add(detail.name);
                else next.delete(detail.name);
                return next;
              });
            }
          }}
        />
      )}
    </Page>
  );
}
