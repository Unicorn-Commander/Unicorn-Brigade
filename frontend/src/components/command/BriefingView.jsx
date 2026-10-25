import { useCallback, useMemo, useState } from 'react';
import { Megaphone } from 'lucide-react';
import { byRankDesc } from '../../utils/rank';
import { prettyDomain } from '../../utils/agentClass';
import BriefingCard from './BriefingCard';
import { Button, Card, Chip, EmptyState, Kbd, Modal, StatusDot, Textarea } from '../ui';

// Above this many recipients a briefing asks first: one click is N requests.
const CONFIRM_ABOVE = 10;

/**
 * Staff Briefing — the one-to-many move. Put a single prompt to a whole group
 * of agents at once and watch every answer stream in side by side. The
 * complement to the dock (one-to-one across many windows). Each recipient runs
 * its own independent chat via BriefingCard.
 */
export default function BriefingView({ tree, onPromote }) {
  const agents = tree.agents;
  const root = tree.root;
  const [prompt, setPrompt] = useState('');
  const [scope, setScope] = useState('all');
  const [round, setRound] = useState(0);
  const [sentPrompt, setSentPrompt] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [statuses, setStatuses] = useState({}); // agentId -> status, for the progress line
  const onCardStatus = useCallback((id, st) => setStatuses((s) => (s[id] === st ? s : { ...s, [id]: st })), []);

  // childrenById maps a parent id -> array of child *id strings*.
  const leadIds = useMemo(() => new Set(tree.childrenById.get(root?.id) || []), [tree, root]);
  const domains = useMemo(() => [...new Set(agents.map((a) => a.domain).filter(Boolean))].sort(), [agents]);

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

  const fire = () => {
    setConfirming(false);
    setStatuses({});
    setSentPrompt(prompt.trim());
    setRound((r) => r + 1);
  };
  const send = () => {
    if (!prompt.trim() || recipients.length === 0) return;
    if (recipients.length > CONFIRM_ABOVE) setConfirming(true);
    else fire();
  };

  const progress = useMemo(() => {
    const p = { working: 0, done: 0, error: 0, total: recipients.length };
    for (const a of recipients) {
      const st = statuses[a.id];
      if (st === 'error') p.error += 1;
      else if (st === 'done') p.done += 1;
      else if (st === 'thinking' || st === 'tool' || st === 'responding') p.working += 1;
    }
    return p;
  }, [recipients, statuses]);

  // Changing the group ends the current round: a new recipient must never be
  // briefed silently just because a card mounted under an old round.
  const selectScope = (id) => {
    if (id === scope) return;
    setScope(id);
    setRound(0);
    setStatuses({});
  };
  const chip = (id, text) => (
    <Chip key={id} size="md" tone={scope === id ? 'accent' : 'neutral'} selected={scope === id} onClick={() => selectScope(id)}>
      {text}
    </Chip>
  );
  const n = recipients.length;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3 sm:p-4">
        <Card padding="sm">
          <div className="mb-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Recipients">
            <span className="mr-1 flex items-center gap-1 text-caption font-semibold text-fg">
              <Megaphone aria-hidden="true" className="h-3.5 w-3.5 text-accent" /> Brief
            </span>
            {presets.map((p) => chip(p.id, p.label))}
            {domains.length > 0 && <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />}
            {domains.map((d) => chip(`domain:${d}`, prettyDomain(d)))}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <Textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={2}
              aria-label="Briefing prompt"
              placeholder={`Brief ${n} agent${n === 1 ? '' : 's'}…`}
              className="max-h-32 resize-none"
            />
            <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-end">
              <span className="text-micro text-subtle">
                <Kbd keys="⌘↵" /> to send
              </span>
              <Button icon={Megaphone} onClick={send} disabled={!prompt.trim() || n === 0}>
                Brief {n}
              </Button>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex-1 overflow-y-auto p-3 sm:p-4">
        {n === 0 ? (
          <EmptyState compact icon={Megaphone} title="No agents in this group" description="Pick another group above." />
        ) : round === 0 ? (
          <EmptyState
            icon={Megaphone}
            title="Brief the room"
            description="Pick a group, write one prompt, and brief them all at once — every answer streams in here side by side."
          />
        ) : (
          <>
            <p className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-body-sm text-muted" aria-live="polite">
              <span>Briefed {progress.total}</span>
              {progress.working > 0 && (
                <span className="inline-flex items-center gap-1.5 text-fg">
                  <StatusDot status="responding" /> {progress.working} working
                </span>
              )}
              {progress.done > 0 && (
                <span className="inline-flex items-center gap-1.5">
                  <StatusDot status="done" /> {progress.done} done
                </span>
              )}
              {progress.error > 0 && (
                <span className="inline-flex items-center gap-1.5 text-danger">
                  <StatusDot status="error" /> {progress.error} need{progress.error === 1 ? 's' : ''} attention
                </span>
              )}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {recipients.map((a) => (
                <BriefingCard key={a.id} agent={a} prompt={sentPrompt} round={round} onPromote={onPromote} onStatus={onCardStatus} />
              ))}
            </div>
          </>
        )}
      </div>

      <Modal
        isOpen={confirming}
        onClose={() => setConfirming(false)}
        title={`Brief ${n} agents?`}
        description={`This sends ${n} requests at once, one per agent, each billed as its own chat turn.`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button icon={Megaphone} onClick={fire} data-autofocus>
              Brief {n}
            </Button>
          </>
        }
      >
        <p className="line-clamp-4 rounded-control border border-border bg-surface px-3 py-2 text-body-sm text-fg">{prompt.trim()}</p>
      </Modal>
    </div>
  );
}
