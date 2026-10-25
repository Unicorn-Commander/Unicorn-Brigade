import { useState } from 'react';
import { CheckCircle, ChevronDown, Clock, MessageSquare, Settings, UserCheck } from 'lucide-react';
import { Chip, EmptyState, SectionHeader } from './ui';

const PHASES = [
  { title: 'Discovery', icon: MessageSquare, keywords: ['need', 'want', 'looking for', 'help'] },
  { title: 'Design', icon: Settings, keywords: ['model', 'tools', 'capabilities', 'configuration'] },
  { title: 'Review', icon: UserCheck, keywords: ['looks', 'perfect', 'good', 'approve', 'create'] },
  { title: 'Created', icon: CheckCircle, keywords: ['created', 'success', 'done'] },
];

// Split the build conversation into phases on simple keyword cues.
function toPhases(messages) {
  const phases = [];
  let i = 0;
  let current = { ...PHASES[0], messages: [], decisions: [] };
  messages.forEach((msg) => {
    current.messages.push(msg);
    const content = String(msg.content || '').toLowerCase();
    if (msg.role === 'assistant' && content.includes('propose')) {
      current.decisions.push(
        ...content
          .split('\n')
          .map((l) => l.trim())
          .filter((l) => l.startsWith('•') || l.startsWith('-'))
      );
    }
    const next = PHASES[i + 1];
    if (next && current.messages.length >= 2 && next.keywords.some((k) => content.includes(k))) {
      phases.push(current);
      i += 1;
      current = { ...next, messages: [msg], decisions: [] };
    }
  });
  if (current.messages.length) phases.push(current);
  return phases.map((p) => ({ ...p, at: p.messages[0]?.timestamp || p.messages[0]?.createdAt }));
}

const time = (s) => (s ? new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null);

/**
 * AgentTimeline — the conversation that built this agent, as phases.
 * Without a session it says so plainly instead of pretending.
 */
export default function AgentTimeline({ session, agentName }) {
  const [open, setOpen] = useState({});
  const messages = Array.isArray(session?.messages) ? session.messages : [];

  if (!messages.length) {
    return (
      <EmptyState
        compact
        icon={Clock}
        title="No build history"
        description={`${agentName || 'This agent'} was created directly or its build conversation wasn’t kept. Agents built with Gunny show the conversation here.`}
      />
    );
  }

  const phases = toPhases(messages);

  return (
    <div className="space-y-5">
      <SectionHeader title="Build history" description={`How ${agentName || 'this agent'} was specified with Gunny`} />
      <ol className="relative space-y-3 border-l border-border pl-6">
        {phases.map((phase, idx) => {
          const Icon = phase.icon;
          const expanded = Boolean(open[idx]);
          const id = `phase-${idx}`;
          return (
            <li key={idx} className="relative">
              <span aria-hidden="true" className="absolute -left-[31px] top-3 h-2.5 w-2.5 rounded-full bg-ok ring-4 ring-ok/20" />
              <div className="rounded-card border border-border bg-card">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={id}
                  onClick={() => setOpen((o) => ({ ...o, [idx]: !o[idx] }))}
                  className="flex min-h-touch w-full items-center gap-3 rounded-card p-3 text-left transition-colors duration-fast hover:bg-elevated/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-body font-semibold text-fg-strong">
                      Step {idx + 1}: {phase.title}
                    </span>
                    <span className="block text-caption text-muted">
                      {phase.messages.length} message{phase.messages.length === 1 ? '' : 's'}
                      {time(phase.at) ? ` · ${time(phase.at)}` : ''}
                    </span>
                  </span>
                  <ChevronDown aria-hidden="true" className={`h-4 w-4 shrink-0 text-muted transition-transform duration-base ${expanded ? 'rotate-180' : ''}`} />
                </button>
                {expanded && (
                  <div id={id} className="space-y-2 border-t border-border p-3">
                    {phase.messages.map((msg, m) => {
                      const user = msg.role === 'user';
                      return (
                        <div key={m} className={`flex ${user ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-2xl rounded-card border px-3 py-2 ${user ? 'border-accent/25 bg-accent/10' : 'border-border bg-surface/70'}`}>
                            <p className="mb-0.5 text-micro font-semibold uppercase tracking-wider text-muted">
                              {user ? 'You' : msg.role === 'system' ? 'System' : 'Gunny'}
                              {time(msg.timestamp || msg.createdAt) ? ` · ${time(msg.timestamp || msg.createdAt)}` : ''}
                            </p>
                            <p className="whitespace-pre-wrap text-body-sm text-fg">{msg.content}</p>
                          </div>
                        </div>
                      );
                    })}
                    {phase.decisions.length > 0 && (
                      <div className="rounded-control border border-accent/25 bg-accent/10 p-3">
                        <p className="mb-1 text-caption font-semibold text-accent">Decisions</p>
                        <ul className="list-disc space-y-0.5 pl-5 text-body-sm text-fg">
                          {phase.decisions.map((d, k) => (
                            <li key={k}>{d.replace(/^[•-]\s*/, '')}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {session?.createdAt && (
        <p className="flex items-center gap-2 text-body-sm text-muted">
          <Chip tone="ok" size="xs" dot>
            Created
          </Chip>
          {new Date(session.createdAt).toLocaleString()}
        </p>
      )}
    </div>
  );
}
