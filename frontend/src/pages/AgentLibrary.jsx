/**
 * Agent Library — every agent in the brigade, grouped by domain.
 *
 * Shape follows the Tool Library exemplar: one PageHeader, a toolbar Card,
 * all four states where the content goes, keyboard-reachable cards, dialogs
 * from components/ui. Counts in the header are the roster's own numbers.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Award,
  BookOpen,
  Bot,
  Briefcase,
  ChevronDown,
  Code2,
  Cpu,
  Database,
  DollarSign,
  Eye,
  LayoutGrid,
  Layers,
  LifeBuoy,
  List,
  ListChecks,
  Scale,
  Search,
  Sparkles,
  Stethoscope,
  Target,
  X,
} from "lucide-react";
import { apiJson } from "../services/http";
import { humanize } from "../utils/errors";
import { prettyDomain } from "../utils/agentClass";
import AgentCard, { agentToolNames } from "../components/AgentCard";
import AgentEditModal from "../components/AgentEditModal";
import AgentDeleteConfirmModal from "../components/AgentDeleteConfirmModal";
import Breadcrumbs from "../components/Breadcrumbs";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  IconButton,
  Input,
  LoadingState,
  OfflineState,
  Page,
  PageHeader,
  Select,
} from "../components/ui";

const VIEW_KEY = "brigade.library.view";
const GROUP_KEY = "brigade.library.group";
const COLLAPSED_KEY = "brigade.library.collapsed";
const readStored = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
};
const store = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — the choice just doesn't persist */
  }
};

const TYPES = [
  { id: "", label: "All types" },
  { id: "individual", label: "Individual" },
  { id: "team_lead", label: "Team lead" },
  { id: "orchestrator", label: "Orchestrator" },
];
const STATUSES = ["active", "draft", "inactive", "archived"];
const DOMAIN_ICON = {
  financial: DollarSign,
  legal: Scale,
  medical: Stethoscope,
  technology: Code2,
  engineering: Cpu,
  investigation: Search,
  orchestration: Target,
  meta: Award,
  intelligence: Eye,
  data: Database,
  support: LifeBuoy,
  sales: Briefcase,
  knowledge: BookOpen,
  productivity: ListChecks,
};

const text = (v) => String(v || "").toLowerCase();

export default function AgentLibrary() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(
    typeof navigator !== "undefined" && navigator.onLine === false,
  );

  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [tool, setTool] = useState("");
  const [sort, setSort] = useState("a-z");
  const [view, setView] = useState(() =>
    readStored(VIEW_KEY, "grid") === "list" ? "list" : "grid",
  );
  const [collapsed, setCollapsed] = useState(
    () => new Set(readStored(COLLAPSED_KEY, [])),
  );
  // Flat grid by default: with most domains holding one or two agents, a group
  // per domain spent a full row per card. "By domain" stays one click away.
  const [grouped, setGrouped] = useState(() => readStored(GROUP_KEY, false) === true);
  const toggleGrouped = () => {
    setGrouped((g) => {
      store(GROUP_KEY, !g);
      return !g;
    });
  };

  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson("/agents");
      setAgents(Array.isArray(data) ? data : data?.agents || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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

  const changeView = (next) => {
    setView(next);
    store(VIEW_KEY, next);
  };
  const toggleGroup = (name) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      store(COLLAPSED_KEY, [...next]);
      return next;
    });
  };

  // ── derived facets ───────────────────────────────────────────────────────
  const domains = useMemo(() => {
    const counts = new Map();
    agents.forEach((a) =>
      counts.set(
        a.domain || "other",
        (counts.get(a.domain || "other") || 0) + 1,
      ),
    );
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [agents]);
  const tools = useMemo(
    () => [...new Set(agents.flatMap(agentToolNames))].sort(),
    [agents],
  );
  const hasUsage = useMemo(
    () => agents.some((a) => Number(a?._count?.messages) > 0),
    [agents],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = agents.filter((a) => {
      if (domain && (a.domain || "other") !== domain) return false;
      if (status && a.status !== status) return false;
      if (type && a.type !== type) return false;
      if (tool && !agentToolNames(a).includes(tool)) return false;
      if (!q) return true;
      const caps = Array.isArray(a.capabilities) ? a.capabilities : [];
      return (
        text(a.name).includes(q) ||
        text(a.displayName).includes(q) ||
        text(a.title).includes(q) ||
        text(a.rank).includes(q) ||
        text(a.bio).includes(q) ||
        text(a.domain).includes(q) ||
        caps.some((c) => text(c).includes(q)) ||
        agentToolNames(a).some((t) => text(t).includes(q))
      );
    });
    const name = (a) => a.displayName || a.name || "";
    list.sort((a, b) => {
      if (sort === "newest")
        return new Date(b.createdAt || 0) - new Date(a.createdAt || 0);
      if (sort === "most-tools")
        return (
          agentToolNames(b).length - agentToolNames(a).length ||
          name(a).localeCompare(name(b))
        );
      if (sort === "most-used")
        return (
          (b._count?.messages || 0) - (a._count?.messages || 0) ||
          name(a).localeCompare(name(b))
        );
      return name(a).localeCompare(name(b));
    });
    return list;
  }, [agents, query, domain, status, type, tool, sort]);

  const groups = useMemo(() => {
    const map = new Map();
    filtered.forEach((a) => {
      const key = a.domain || "other";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(a);
    });
    return [...map.entries()].sort(
      (a, b) =>
        (a[0] === "other") - (b[0] === "other") || a[0].localeCompare(b[0]),
    );
  }, [filtered]);

  const hasFilters = Boolean(query || domain || status || type || tool);
  const clearFilters = () => {
    setQuery("");
    setDomain("");
    setStatus("");
    setType("");
    setTool("");
  };

  // ── optimistic edits (the dialogs call back twice: optimistic, then final) ──
  const onSaved = (updated, meta = {}) => {
    const snapshot = agents;
    setAgents((prev) =>
      prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a)),
    );
    if (!meta.optimistic) setEditing(null);
    return () => setAgents(snapshot);
  };
  const onDeleted = (target, meta = {}) => {
    const snapshot = agents;
    const id = typeof target === "string" ? target : target?.id;
    setAgents((prev) => prev.filter((a) => a.id !== id));
    if (!meta.optimistic) setDeleting(null);
    return () => setAgents(snapshot);
  };

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !agents.length) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = (
      <LoadingState
        variant={view === "list" ? "list" : "cards"}
        count={6}
        label="Loading agents"
      />
    );
  } else if (error) {
    body = (
      <ErrorState
        title="Couldn’t load the roster"
        detail={humanize(error, { what: "loading agents" })}
        onRetry={load}
      />
    );
  } else if (!agents.length) {
    body = (
      <EmptyState
        icon={Bot}
        title="No agents yet"
        description="Build your first agent with Gunny: describe the job, pick its tools, and it joins the brigade here."
        action={
          <Button icon={Sparkles} onClick={() => navigate("/builder-chat")}>
            Build an agent
          </Button>
        }
      />
    );
  } else if (!filtered.length) {
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No agents match"
        description="Try another word, or clear the filters."
        action={
          <Button variant="secondary" size="sm" icon={X} onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else {
    const renderCard = (agent) => (
      <li key={agent.id}>
        <AgentCard
          agent={agent}
          variant={view}
          onOpen={() => navigate(`/agent/${agent.id}`)}
          onChat={() => navigate(`/chat?agent=${encodeURIComponent(agent.id)}`)}
          onEdit={() => setEditing(agent)}
          onDelete={() => setDeleting(agent)}
        />
      </li>
    );
    const listClass =
      view === "grid" ? "grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" : "space-y-2";
    body = !grouped ? (
      <ul className={listClass} aria-label="Agents">
        {filtered.map(renderCard)}
      </ul>
    ) : (
      <div className="space-y-6">
        {groups.map(([name, list]) => {
          const Icon = DOMAIN_ICON[name] || Bot;
          const open = !collapsed.has(name);
          const panelId = `domain-${name}`;
          return (
            <section key={name} aria-labelledby={`${panelId}-title`}>
              <button
                type="button"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() => toggleGroup(name)}
                className="mb-3 flex min-h-touch w-full items-center gap-3 rounded-control px-1 text-left transition-colors duration-fast hover:bg-elevated/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span
                  aria-hidden="true"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-elevated text-muted"
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    id={`${panelId}-title`}
                    className="block text-heading text-fg-strong"
                  >
                    {prettyDomain(name)}
                  </span>
                </span>
                <Chip size="xs">
                  {list.length} agent{list.length === 1 ? "" : "s"}
                </Chip>
                <ChevronDown
                  aria-hidden="true"
                  className={`h-4 w-4 text-muted transition-transform duration-base ${open ? "" : "-rotate-90"}`}
                />
              </button>
              {open && (
                <ul
                  id={panelId}
                  className={
                    view === "grid"
                      ? "grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
                      : "space-y-2"
                  }
                  aria-label={`${prettyDomain(name)} agents`}
                >
                  {list.map((agent) => (
                    <li key={agent.id}>
                      <AgentCard
                        agent={agent}
                        variant={view}
                        onOpen={() => navigate(`/agent/${agent.id}`)}
                        onChat={() =>
                          navigate(
                            `/chat?agent=${encodeURIComponent(agent.id)}`,
                          )
                        }
                        onEdit={() => setEditing(agent)}
                        onDelete={() => setDeleting(agent)}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    );
  }

  const quiet = !loading && (error || !agents.length); // nothing to filter yet
  const description =
    loading || quiet
      ? "Every agent in the brigade"
      : hasFilters
        ? `${filtered.length} of ${agents.length} agents match`
        : `${agents.length} agent${agents.length === 1 ? "" : "s"} across ${domains.length} domain${domains.length === 1 ? "" : "s"}`;

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Agents"
        title="Agent Library"
        description={description}
        actions={
          <Button icon={Sparkles} onClick={() => navigate("/builder-chat")}>
            Build an agent
          </Button>
        }
      />

      {!quiet && (
        <Card padding="sm" className="mb-5">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto_auto]">
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
              />
              <Input
                type="search"
                aria-label="Search agents"
                placeholder="Search agents, tools, capabilities…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              aria-label="Filter by domain"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="md:w-44"
            >
              <option value="">All domains</option>
              {domains.map(([name, count]) => (
                <option key={name} value={name}>
                  {prettyDomain(name)} ({count})
                </option>
              ))}
            </Select>
            <Select
              aria-label="Filter by tool"
              value={tool}
              onChange={(e) => setTool(e.target.value)}
              className="md:w-44"
            >
              <option value="">All tools</option>
              {tools.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Filter by status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="md:w-36"
            >
              <option value="">Any status</option>
              {STATUSES.map((s) => (
                <option key={s} value={s} className="capitalize">
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </Select>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <div
              className="flex flex-wrap items-center gap-1.5"
              role="group"
              aria-label="Filter by type"
            >
              {TYPES.map((t) => (
                <Chip
                  key={t.id || "all"}
                  tone="accent"
                  size="md"
                  selected={type === t.id}
                  onClick={() => setType(t.id)}
                >
                  {t.label}
                </Chip>
              ))}
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Select
                aria-label="Sort agents"
                size="sm"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                className="w-40"
              >
                <option value="a-z">Name A–Z</option>
                <option value="newest">Newest first</option>
                <option value="most-tools">Most tools</option>
                {hasUsage && <option value="most-used">Most used</option>}
              </Select>
              <div
                className="flex items-center gap-0.5 rounded-control border border-border bg-surface/70 p-0.5"
                role="group"
                aria-label="Layout"
              >
                <IconButton
                  icon={LayoutGrid}
                  label="Grid view"
                  size="sm"
                  variant={view === "grid" ? "secondary" : "ghost"}
                  aria-pressed={view === "grid"}
                  onClick={() => changeView("grid")}
                />
                <IconButton
                  icon={List}
                  label="List view"
                  size="sm"
                  variant={view === "list" ? "secondary" : "ghost"}
                  aria-pressed={view === "list"}
                  onClick={() => changeView("list")}
                />
                <span aria-hidden="true" className="mx-0.5 h-5 w-px bg-border" />
                <IconButton
                  icon={Layers}
                  label={grouped ? "Show one grid" : "Group by domain"}
                  size="sm"
                  variant={grouped ? "secondary" : "ghost"}
                  aria-pressed={grouped}
                  onClick={toggleGrouped}
                />
              </div>
            </div>
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

      {editing && (
        <AgentEditModal
          agent={editing}
          onClose={() => setEditing(null)}
          onSave={onSaved}
        />
      )}
      {deleting && (
        <AgentDeleteConfirmModal
          agent={deleting}
          onClose={() => setDeleting(null)}
          onDelete={onDeleted}
        />
      )}
    </Page>
  );
}
