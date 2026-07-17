import { useState } from 'react';
import { CheckCircle, Circle, Clock, MessageSquare, Settings, UserCheck, ChevronDown, ChevronUp } from 'lucide-react';

const AgentTimeline = ({ session, agentName }) => {
  const [expandedSteps, setExpandedSteps] = useState({});

  // If no session data provided, show placeholder
  if (!session || !session.messages || session.messages.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 rounded-full bg-slate-800/50 border border-slate-700 flex items-center justify-center mx-auto mb-4">
          <Clock className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-300 mb-2">No Build History Available</h3>
        <p className="text-slate-400">This agent was created manually or the build session is not available.</p>
      </div>
    );
  }

  // Parse the session messages into timeline phases
  const phases = parseSessionIntoPhases(session);

  const toggleStep = (index) => {
    setExpandedSteps(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-slate-700 pb-4">
        <h2 className="text-2xl font-bold text-white mb-2">
          Build Process for "{agentName || 'Agent'}"
        </h2>
        <p className="text-slate-400">
          Interactive conversation with The General
        </p>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gradient-to-b from-unicorn-500 via-cyan-500 to-emerald-500"></div>

        {/* Timeline Steps */}
        <div className="space-y-8">
          {phases.map((phase, index) => (
            <TimelineStep
              key={index}
              phase={phase}
              index={index}
              isExpanded={expandedSteps[index]}
              onToggle={() => toggleStep(index)}
              isLast={index === phases.length - 1}
            />
          ))}
        </div>
      </div>

      {/* Summary Footer */}
      {session.createdAt && (
        <div className="mt-8 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
            <div>
              <p className="font-medium text-emerald-300">Agent Successfully Created</p>
              <p className="text-sm text-slate-400">
                {new Date(session.createdAt).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const TimelineStep = ({ phase, index, isExpanded, onToggle, isLast }) => {
  const Icon = phase.icon;
  const isCompleted = phase.status === 'completed';

  return (
    <div className="relative pl-16">
      {/* Timeline dot */}
      <div className={`absolute left-4 w-4 h-4 rounded-full flex items-center justify-center ${
        isCompleted
          ? 'bg-emerald-500 ring-4 ring-emerald-500/20'
          : 'bg-unicorn-500 ring-4 ring-unicorn-500/20'
      }`}>
        {isCompleted && <div className="w-2 h-2 rounded-full bg-white"></div>}
      </div>

      {/* Step content card */}
      <div className={`rounded-lg border transition-all ${
        isExpanded
          ? 'bg-slate-800/50 border-unicorn-500/50'
          : 'bg-slate-900/30 border-slate-700/50 hover:bg-slate-800/30'
      }`}>
        {/* Header - Always visible */}
        <button
          onClick={onToggle}
          className="w-full p-4 flex items-center justify-between text-left"
        >
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              isCompleted
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-unicorn-500/20 text-unicorn-400'
            }`}>
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white">
                Step {index + 1}: {phase.title}
              </h3>
              <p className="text-sm text-slate-400">
                {phase.messages.length} message{phase.messages.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {phase.timestamp && (
              <span className="text-xs text-slate-400">
                {new Date(phase.timestamp).toLocaleTimeString()}
              </span>
            )}
            {isExpanded ? (
              <ChevronUp className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            )}
          </div>
        </button>

        {/* Expanded content */}
        {isExpanded && (
          <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-4">
            {phase.messages.map((msg, msgIndex) => (
              <MessageBubble key={msgIndex} message={msg} />
            ))}

            {/* Key decisions */}
            {phase.keyDecisions && phase.keyDecisions.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-unicorn-500/10 border border-unicorn-500/20">
                <h4 className="text-sm font-semibold text-unicorn-300 mb-2">Key Decisions:</h4>
                <ul className="space-y-1">
                  {phase.keyDecisions.map((decision, idx) => (
                    <li key={idx} className="text-sm text-slate-300 flex items-start space-x-2">
                      <span className="text-unicorn-400 mt-0.5">•</span>
                      <span>{decision}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl rounded-lg p-3 ${
        isUser
          ? 'bg-unicorn-500/20 border border-unicorn-500/30'
          : isSystem
          ? 'bg-slate-700/30 border border-slate-600/30'
          : 'bg-cyan-500/20 border border-cyan-500/30'
      }`}>
        <div className="flex items-center space-x-2 mb-1">
          <span className="text-xs font-semibold text-slate-400 uppercase">
            {isUser ? 'You' : isSystem ? 'System' : 'The General'}
          </span>
          {message.timestamp && (
            <span className="text-xs text-slate-400">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-200 whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
};

// Parse session messages into timeline phases
function parseSessionIntoPhases(session) {
  const messages = session.messages || [];
  const phases = [];

  // Simple heuristic-based parsing
  // In a real implementation, you might use AI or better parsing logic

  let currentPhase = {
    title: 'Discovery Phase',
    icon: MessageSquare,
    status: 'completed',
    messages: [],
    keyDecisions: []
  };

  let phaseIndex = 0;
  const phaseTypes = [
    { title: 'Discovery Phase', icon: MessageSquare, keywords: ['need', 'want', 'looking for', 'help'] },
    { title: 'Design Phase', icon: Settings, keywords: ['model', 'tools', 'capabilities', 'configuration'] },
    { title: 'Review Phase', icon: UserCheck, keywords: ['looks', 'perfect', 'good', 'approve', 'create'] },
    { title: 'Created', icon: CheckCircle, keywords: ['created', 'success', 'done'] }
  ];

  messages.forEach((msg, index) => {
    currentPhase.messages.push(msg);

    // Check if we should move to next phase
    const content = msg.content?.toLowerCase() || '';

    // Extract key decisions from assistant messages
    if (msg.role === 'assistant' && content.includes('propose')) {
      // Extract proposals as key decisions
      const lines = content.split('\n').filter(line =>
        line.trim().startsWith('•') ||
        line.trim().startsWith('-') ||
        line.includes(':')
      );
      currentPhase.keyDecisions.push(...lines.map(l => l.trim()));
    }

    // Detect phase transitions
    if (phaseIndex < phaseTypes.length - 1) {
      const nextPhase = phaseTypes[phaseIndex + 1];
      const hasKeyword = nextPhase.keywords.some(kw => content.includes(kw));

      if (hasKeyword && currentPhase.messages.length >= 2) {
        // Add timestamp from first message in phase
        if (currentPhase.messages.length > 0) {
          currentPhase.timestamp = currentPhase.messages[0].timestamp || currentPhase.messages[0].createdAt;
        }

        phases.push(currentPhase);
        phaseIndex++;

        currentPhase = {
          title: nextPhase.title,
          icon: nextPhase.icon,
          status: 'completed',
          messages: [msg],
          keyDecisions: []
        };
      }
    }
  });

  // Add final phase
  if (currentPhase.messages.length > 0) {
    if (currentPhase.messages.length > 0) {
      currentPhase.timestamp = currentPhase.messages[0].timestamp || currentPhase.messages[0].createdAt;
    }
    phases.push(currentPhase);
  }

  return phases;
}

export default AgentTimeline;
