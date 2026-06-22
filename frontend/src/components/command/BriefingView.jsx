import { useMemo, useState } from 'react';
import { Megaphone, Send } from 'lucide-react';
import { byRankDesc } from '../../utils/rank';
import BriefingCard from './BriefingCard';

/**
 * Staff Briefing — the one-to-many move. Put a single prompt to a whole group of
 * agents at once and watch every answer stream in side by side. The complement to
 * the dock (which is one-to-one across many windows). Each recipient runs its own
 * independent chat via BriefingCard.
 */
export default function BriefingView({ tree, onPromote }) {
  const agents = tree.agents;
  const root = tree.root;
  const [prompt, setPrompt] = useState('');
  const [scope, setScope] = useState('all');
  const [round, setRound] = useState(0);
  const [sentPrompt, setSentPrompt] = useState('');

  const leadIds = useMemo(
    () => new Set((tree.childrenById.get(root?.id) || []).map((a) => a.id)),
    [tree, root]
  );
  const domains = useMemo(
    () => [...new Set(agents.map((a) => a.domain).filter(Boolean))].sort(),
    [agents]
  );

  const recipients = useMemo(() => {
    let list = agents;
    if (scope === 'leads') list = agents.filter((a) => leadIds.has(a.id));
    else if (scope === 'specialists') list = agents.filter((a) => !leadIds.has(a.id) && a.id !== root?.id);
    else if (scope.startsWith('domain:')) {
      const d = scope.slice(7);
      list = agents.filter((a) => a.domain === d);
    }
    return [...list].sort(byRankDesc);
  }, [scope, agents, leadIds, root]);

  const presets = [
    { id: 'all', label: `All ${agents.length}` },
    { id: 'leads', label: 'Domain leads' },
    { id: 'specialists', label: 'Specialists' },
  ];

  const send = () => {
    const t = prompt.trim();
    if (!t || recipients.length === 0) return;
    setSentPrompt(t);
    setRound((r) => r + 1);
  };

  const chip = (id, text, key) => (
    <button
      key={key || id}
      onClick={() => setScope(id)}
      className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
        scope === id
          ? 'bg-unicorn-500/25 text-unicorn-100 ring-1 ring-unicorn-500/50'
          : 'bg-slate-800/60 text-slate-300 hover:bg-slate-800'
      }`}
    >
      {text}
    </button>
  );

  return (
    <div className="flex h-full flex-col">
      {/* Composer */}
      <div className="border-b border-slate-800 bg-slate-900/40 p-3">
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 flex items-center gap-1 text-xs font-semibold text-unicorn-200">
            <Megaphone className="h-3.5 w-3.5" /> Brief
          </span>
          {presets.map((p) => chip(p.id, p.label))}
          <span className="mx-1 h-4 w-px bg-slate-700" />
          {domains.map((d) => chip(`domain:${d}`, d, d))}
        </div>
        <div className="flex items-end gap-2">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            placeholder={`Brief ${recipients.length} agent${recipients.length === 1 ? '' : 's'}…  (⌘↵ to send)`}
            className="max-h-32 flex-1 resize-none rounded-lg bg-slate-800/70 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-unicorn-500/50"
          />
          <button
            onClick={send}
            disabled={!prompt.trim() || recipients.length === 0}
            className="flex items-center gap-1.5 rounded-lg bg-unicorn-500/80 px-3 py-2 text-sm font-medium text-white hover:bg-unicorn-500 disabled:opacity-40"
          >
            <Send className="h-4 w-4" /> Brief {recipients.length}
          </button>
        </div>
      </div>

      {/* Response grid */}
      <div className="flex-1 overflow-y-auto p-3">
        {round === 0 ? (
          <div className="mt-10 text-center text-sm text-slate-500">
            Pick a group, write one prompt, and brief them all at once — every answer streams in below.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {recipients.map((a) => (
              <BriefingCard key={a.id} agent={a} prompt={sentPrompt} round={round} onPromote={onPromote} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
