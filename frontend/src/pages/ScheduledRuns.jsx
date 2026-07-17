import { useEffect, useState } from 'react';
import {
  Calendar,
  Clock,
  Play,
  Plus,
  Trash2,
  Pencil,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { buildAuthHeaders, handleUnauthorized } from '../services/authHeaders';
import Breadcrumbs from '../components/Breadcrumbs';

import { API_BASE } from '../services/apiBase';

const STATUS_ICON = {
  success: CheckCircle2,
  error: XCircle,
  timeout: AlertTriangle,
  running: Loader2,
  skipped: AlertTriangle,
};

const STATUS_COLOR = {
  success: 'text-emerald-400',
  error: 'text-rose-400',
  timeout: 'text-orange-400',
  running: 'text-sky-400',
  skipped: 'text-slate-400',
};

function fmtTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: buildAuthHeaders({
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    }),
  });
  if (res.status === 401) handleUnauthorized();
  if (res.status === 204) return null;
  const text = await res.text();
  let data = {};
  if (text) {
    try { data = JSON.parse(text); }
    catch {
      // Non-JSON response — most often the SPA index.html when the request
      // accidentally fell off the API path. Don't crash the page.
      const ct = res.headers.get('content-type') || '';
      throw new Error(
        `Non-JSON response from ${path} (status ${res.status}, content-type ${ct})`
      );
    }
  }
  if (!res.ok) {
    const msg = data?.detail?.message || data?.detail || res.statusText;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

const EMPTY_FORM = {
  name: '',
  agentId: '',
  prompt: '',
  cron: '0 13 * * *',
  timezone: 'UTC',
  ownerUserId: '',
  enabled: true,
  maxRuntimeSeconds: 300,
};

function EditModal({ open, initial, agents, onClose, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(initial ? { ...EMPTY_FORM, ...initial } : EMPTY_FORM);
    }
  }, [open, initial]);

  if (!open) return null;

  const submit = async () => {
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      toast.error(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-2xl w-full p-6 space-y-4">
        <h2 className="text-xl font-semibold text-white">
          {initial?.id ? 'Edit scheduled run' : 'New scheduled run'}
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <label className="block col-span-2">
            <span className="text-sm text-slate-400">Name</span>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>

          <label className="block">
            <span className="text-sm text-slate-400">Agent</span>
            <select
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
              value={form.agentId}
              onChange={(e) => setForm({ ...form, agentId: e.target.value })}
            >
              <option value="">— pick an agent —</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.displayName || a.name} ({a.id})
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-slate-400">Owner user id (optional)</span>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white font-mono text-xs"
              value={form.ownerUserId || ''}
              placeholder="UUID — used for per-user JWT propagation"
              onChange={(e) => setForm({ ...form, ownerUserId: e.target.value })}
            />
          </label>

          <label className="block col-span-2">
            <span className="text-sm text-slate-400">Prompt</span>
            <textarea
              rows={4}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
              value={form.prompt}
              onChange={(e) => setForm({ ...form, prompt: e.target.value })}
            />
          </label>

          <label className="block">
            <span className="text-sm text-slate-400">Cron (5 fields)</span>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white font-mono"
              value={form.cron}
              onChange={(e) => setForm({ ...form, cron: e.target.value })}
              placeholder="m h dom mon dow"
            />
          </label>

          <label className="block">
            <span className="text-sm text-slate-400">Timezone</span>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
              value={form.timezone}
              onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            />
          </label>

          <label className="block">
            <span className="text-sm text-slate-400">Max runtime (seconds)</span>
            <input
              type="number"
              min={5}
              max={3600}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
              value={form.maxRuntimeSeconds}
              onChange={(e) =>
                setForm({ ...form, maxRuntimeSeconds: Number(e.target.value) })
              }
            />
          </label>

          <label className="flex items-center gap-2 mt-6">
            <input
              type="checkbox"
              checked={!!form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            <span className="text-sm text-slate-300">Enabled</span>
          </label>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-slate-700 text-slate-300 rounded hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving || !form.name || !form.agentId || !form.cron || !form.prompt}
            className="px-4 py-2 bg-unicorn-600 hover:bg-unicorn-500 text-white rounded disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScheduledRuns() {
  const [items, setItems] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [history, setHistory] = useState({});

  const reload = async () => {
    setLoading(true);
    try {
      const [list, agentList] = await Promise.all([
        api('/scheduled-runs'),
        api('/agents'),
      ]);
      setItems(list.items || []);
      const ag = Array.isArray(agentList)
        ? agentList
        : agentList.agents || agentList.items || [];
      setAgents(ag);
    } catch (err) {
      toast.error(err.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    const t = setInterval(reload, 30000);
    return () => clearInterval(t);
  }, []);

  const create = () => {
    setEditing(null);
    setEditOpen(true);
  };
  const edit = (row) => {
    setEditing(row);
    setEditOpen(true);
  };
  const save = async (form) => {
    const body = { ...form };
    if (!body.ownerUserId) delete body.ownerUserId;
    if (editing?.id) {
      await api(`/scheduled-runs/${editing.id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      toast.success('Updated');
    } else {
      await api('/scheduled-runs', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      toast.success('Created');
    }
    await reload();
  };
  const toggle = async (row) => {
    try {
      await api(`/scheduled-runs/${row.id}`, {
        method: 'PUT',
        body: JSON.stringify({ enabled: !row.enabled }),
      });
      reload();
    } catch (err) {
      toast.error(err.message);
    }
  };
  const remove = async (row) => {
    if (!confirm(`Delete scheduled run "${row.name}"?`)) return;
    try {
      await api(`/scheduled-runs/${row.id}`, { method: 'DELETE' });
      toast.success('Deleted');
      reload();
    } catch (err) {
      toast.error(err.message);
    }
  };
  const runNow = async (row) => {
    try {
      const res = await api(`/scheduled-runs/${row.id}/run-now`, { method: 'POST' });
      toast.success(`Run started (${res.status})`);
      reload();
      if (expandedId === row.id) loadHistory(row.id);
    } catch (err) {
      toast.error(err.message);
    }
  };
  const loadHistory = async (id) => {
    try {
      const res = await api(`/scheduled-runs/${id}/history?limit=50`);
      setHistory((h) => ({ ...h, [id]: res.items || [] }));
    } catch (err) {
      toast.error(err.message);
    }
  };
  const expand = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    loadHistory(id);
  };

  return (
    <div className="p-6 space-y-6">
      <Breadcrumbs items={[{ label: 'Scheduled Runs' }]} />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar className="text-unicorn-400" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-white">Scheduled Runs</h1>
            <p className="text-sm text-slate-400">
              Cron-based agent invocations. Survives container restarts.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={reload}
            className="flex items-center gap-2 px-3 py-2 border border-slate-700 text-slate-300 rounded hover:bg-slate-800"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={create}
            className="flex items-center gap-2 px-3 py-2 bg-unicorn-600 hover:bg-unicorn-500 text-white rounded"
          >
            <Plus size={16} /> New
          </button>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-950 text-slate-400 text-left text-xs uppercase">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Cron</th>
              <th className="px-4 py-3">Enabled</th>
              <th className="px-4 py-3">Last run</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No scheduled runs yet.
                </td>
              </tr>
            )}
            {items.map((row) => {
              const Icon = STATUS_ICON[row.lastStatus] || Clock;
              const color = STATUS_COLOR[row.lastStatus] || 'text-slate-400';
              const open = expandedId === row.id;
              return (
                <>
                  <tr
                    key={row.id}
                    className="border-t border-slate-800 hover:bg-slate-800/40"
                  >
                    <td className="px-4 py-3 text-white">
                      <button
                        onClick={() => expand(row.id)}
                        className="hover:underline text-left"
                      >
                        {row.name}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                      {row.agentId}
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                      {row.cron}{' '}
                      <span className="text-slate-400">({row.timezone})</span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggle(row)}
                        className={`px-2 py-1 rounded text-xs ${
                          row.enabled
                            ? 'bg-emerald-900/40 text-emerald-300'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {row.enabled ? 'on' : 'off'}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {fmtTime(row.lastRunAt)}
                    </td>
                    <td className={`px-4 py-3 ${color}`}>
                      <div className="flex items-center gap-2">
                        <Icon size={16} />
                        {row.lastStatus || '—'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => runNow(row)}
                          title="Run now"
                          className="p-1 text-emerald-400 hover:bg-slate-800 rounded"
                        >
                          <Play size={16} />
                        </button>
                        <button
                          onClick={() => edit(row)}
                          title="Edit"
                          className="p-1 text-sky-400 hover:bg-slate-800 rounded"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => remove(row)}
                          title="Delete"
                          className="p-1 text-rose-400 hover:bg-slate-800 rounded"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {open && (
                    <tr>
                      <td colSpan={7} className="bg-slate-950/60 px-4 py-3">
                        <div className="text-xs text-slate-400 mb-2">
                          Recent history (most recent first):
                        </div>
                        <div className="space-y-1">
                          {(history[row.id] || []).length === 0 && (
                            <div className="text-slate-400 text-xs">
                              No runs yet.
                            </div>
                          )}
                          {(history[row.id] || []).map((h) => {
                            const HIcon = STATUS_ICON[h.status] || Clock;
                            const hColor = STATUS_COLOR[h.status] || 'text-slate-400';
                            return (
                              <div
                                key={h.id}
                                className="flex items-start gap-3 text-xs border-l-2 border-slate-800 pl-2"
                              >
                                <HIcon size={14} className={`${hColor} mt-0.5`} />
                                <div className="text-slate-400 w-44 shrink-0">
                                  {fmtTime(h.startedAt)}
                                </div>
                                <div className={`${hColor} w-20 shrink-0`}>
                                  {h.status}
                                </div>
                                <div className="text-slate-300 truncate">
                                  {h.error
                                    ? `error: ${h.error}`
                                    : h.outputSummary || '(no output)'}
                                  {h.toolCallsCount
                                    ? ` · ${h.toolCallsCount} tool call${
                                        h.toolCallsCount === 1 ? '' : 's'
                                      }`
                                    : ''}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>

      <EditModal
        open={editOpen}
        initial={editing}
        agents={agents}
        onClose={() => setEditOpen(false)}
        onSave={save}
      />
    </div>
  );
}
