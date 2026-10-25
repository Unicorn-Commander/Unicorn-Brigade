import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, ChevronLeft, CheckCircle, Lightbulb, MessageSquare, Bot, Workflow, Sparkles } from 'lucide-react';
import { Button, Card, Modal, LoadingState } from './ui';
import AgentAvatar from './AgentAvatar';
import { roleLine } from '../utils/agentClass';
import { apiJson } from '../services/http';

const WIZARD_KEY = 'wizard-completed';

const Check = ({ children }) => (
  <li className="flex items-start gap-2 text-body-sm text-muted">
    <CheckCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
    <span>{children}</span>
  </li>
);

const STEPS = [
  {
    id: 'welcome',
    title: 'Welcome to Unicorn Brigade',
    icon: Sparkles,
    description: 'The AI Agent Factory: build, deploy and orchestrate agents, then watch them work.',
    content: () => (
      <ul className="space-y-2">
        <Check>
          <strong className="text-fg">A roster of production agents</strong> across finance, legal, engineering and more
        </Check>
        <Check>
          <strong className="text-fg">Hierarchical multi-agent workflows</strong> with live tracking
        </Check>
        <Check>
          <strong className="text-fg">MCP server integrations</strong> and a growing tool catalog
        </Check>
        <Check>
          <strong className="text-fg">Built-in working tools</strong>: search, email, memory, browser and more
        </Check>
      </ul>
    ),
  },
  {
    id: 'chat',
    title: 'Chat with an agent',
    icon: MessageSquare,
    description: 'Every agent has a job. Pick one and start a conversation.',
    content: ({ agents }) => (
      <div className="space-y-3">
        {agents == null ? (
          <LoadingState variant="list" count={4} label="Loading agents" />
        ) : agents.length === 0 ? (
          <p className="text-body-sm text-muted">Your roster is empty for now. Build an agent in the next step and it appears here.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {agents.map((a) => (
              <li key={a.id}>
                <Card variant="elevated" padding="sm" className="flex items-center gap-3">
                  <AgentAvatar agent={a} size={36} rounded="rounded-control" />
                  <span className="min-w-0">
                    <span className="block truncate text-body-sm font-medium text-fg">{a.displayName || a.name}</span>
                    <span className="block truncate text-caption text-muted">{roleLine(a)}</span>
                  </span>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    ),
    action: { label: 'Open the Agent Library', path: '/library' },
  },
  {
    id: 'build',
    title: 'Build your own agents',
    icon: Bot,
    description: 'Gunny builds agents in conversation: personality, tools, model, deploy.',
    content: () => (
      <div className="space-y-4">
        <ol className="space-y-2 text-body-sm text-muted">
          {['Describe the job and the personality', 'Pick tools from the Tool Library', 'Choose the model and parameters', 'Deploy and start chatting'].map((s, i) => (
            <li key={s} className="flex items-start gap-2">
              <span aria-hidden="true" className="w-5 shrink-0 font-semibold text-accent">
                {i + 1}.
              </span>
              <span>{s}</span>
            </li>
          ))}
        </ol>
        <p className="flex items-start gap-2 rounded-control border border-accent/25 bg-accent/10 p-3 text-body-sm text-fg">
          <Lightbulb aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>Tip: existing agents can be edited in the Agent Library; Gunny is for new ones.</span>
        </p>
      </div>
    ),
    action: { label: 'Build an agent', path: '/builder-chat' },
  },
  {
    id: 'workflows',
    title: 'Run a workflow',
    icon: Workflow,
    description: 'Templates coordinate several agents on one job, with live progress.',
    content: () => (
      <div className="space-y-2">
        {[
          ['Investment Due Diligence', 'Finance · Research · Investment'],
          ['Content Production Factory', 'Research · Content · SEO'],
          ['Incident Response & Resolution', 'DevOps · Monitoring · Investigation'],
        ].map(([name, tags]) => (
          <Card key={name} variant="elevated" padding="sm">
            <p className="text-body-sm font-medium text-fg">{name}</p>
            <p className="text-caption text-muted">{tags}</p>
          </Card>
        ))}
      </div>
    ),
    action: { label: 'Browse workflows', path: '/workflows' },
  },
];

/**
 * GettingStartedWizard — the four-step tour on the ui Modal. Marks itself
 * complete in localStorage on finish or on jumping to a step's page; the
 * sidebar's "Getting started" button re-opens it any time.
 */
export default function GettingStartedWizard({ onClose }) {
  const [current, setCurrent] = useState(0);
  const [agents, setAgents] = useState(null);
  const navigate = useNavigate();
  const step = STEPS[current];
  const last = current === STEPS.length - 1;

  useEffect(() => {
    let cancelled = false;
    apiJson('/agents', { redirectOn401: false })
      .then((d) => {
        if (cancelled) return;
        const list = Array.isArray(d?.agents) ? d.agents : [];
        setAgents(list.filter((a) => a.id !== 'the-general').slice(0, 4));
      })
      .catch(() => !cancelled && setAgents([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const finish = () => {
    try {
      localStorage.setItem(WIZARD_KEY, 'true');
    } catch {
      /* storage unavailable */
    }
    onClose?.();
  };

  const go = (path) => {
    finish();
    navigate(path);
  };

  return (
    <Modal
      isOpen
      onClose={finish}
      size="xl"
      title={step.title}
      description={step.description}
      footer={
        <>
          {current > 0 && (
            <Button variant="ghost" icon={ChevronLeft} onClick={() => setCurrent((i) => i - 1)}>
              Back
            </Button>
          )}
          {step.action && (
            <Button variant="secondary" onClick={() => go(step.action.path)}>
              {step.action.label}
            </Button>
          )}
          <Button iconRight={ChevronRight} onClick={() => (last ? finish() : setCurrent((i) => i + 1))}>
            {last ? 'Get started' : 'Next'}
          </Button>
        </>
      }
    >
      <ol className="mb-4 flex items-center gap-1.5" aria-label={`Step ${current + 1} of ${STEPS.length}`}>
        {STEPS.map((s, i) => (
          <li
            key={s.id}
            aria-current={i === current ? 'step' : undefined}
            className={`h-1.5 rounded-full transition-[width,background-color] duration-base ${
              i === current ? 'w-6 bg-accent' : i < current ? 'w-1.5 bg-accent/50' : 'w-1.5 bg-border-strong'
            }`}
          >
            <span className="sr-only">
              {s.title}
              {i === current ? ' (current)' : ''}
            </span>
          </li>
        ))}
        <li className="ml-2 text-caption text-muted" aria-hidden="true">
          {current + 1} / {STEPS.length}
        </li>
      </ol>
      <div className="min-h-[200px]">{step.content({ agents })}</div>
    </Modal>
  );
}
