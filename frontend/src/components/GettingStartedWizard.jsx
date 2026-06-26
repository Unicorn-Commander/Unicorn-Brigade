import React, { useState } from 'react';
import {
  X,
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  MessageSquare,
  Bot,
  Workflow,
  Sparkles
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const WIZARD_STEPS = [
  {
    title: 'Welcome to Unicorn Brigade',
    icon: Sparkles,
    description: 'Your AI Agent Factory for building, deploying, and orchestrating intelligent agents.',
    content: (
      <div className="space-y-4">
        <p className="text-slate-300">
          Unicorn Brigade is a production-ready platform with:
        </p>
        <ul className="space-y-2 text-sm text-slate-400">
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-white">Production-ready agents</strong> across multiple domains</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-white">Hierarchical multi-agent workflows</strong> with real-time tracking</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-white">MCP server integrations</strong> with a growing tool catalog</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-white">Built-in working tools</strong> (search, email, memory, browser, and more)</span>
          </li>
        </ul>
      </div>
    ),
    action: null,
  },
  {
    title: 'Chat with an Agent',
    icon: MessageSquare,
    description: 'Start a conversation with any of your agents.',
    content: (
      <div className="space-y-4">
        <p className="text-slate-300">
          Try chatting with one of our specialized agents:
        </p>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="text-sm font-medium text-white">LtCol Sterling</div>
            <div className="text-xs text-slate-400 mt-1">Financial Analysis</div>
          </div>
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="text-sm font-medium text-white">Maj CodeCraft</div>
            <div className="text-xs text-slate-400 mt-1">Software Engineering</div>
          </div>
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="text-sm font-medium text-white">Cpl Scout</div>
            <div className="text-xs text-slate-400 mt-1">Research & Intelligence</div>
          </div>
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="text-sm font-medium text-white">Sgt Scribe</div>
            <div className="text-xs text-slate-400 mt-1">Meeting Notes & Summaries</div>
          </div>
        </div>
      </div>
    ),
    action: { label: 'Go to Agent Library', path: '/library' },
  },
  {
    title: 'Build Custom Agents',
    icon: Bot,
    description: 'Create your own agents with custom personalities and tools.',
    content: (
      <div className="space-y-4">
        <p className="text-slate-300">
          Build agents tailored to your needs:
        </p>
        <ul className="space-y-2 text-sm text-slate-400">
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-purple-400">1.</div>
            <span>Define personality and behavior</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-purple-400">2.</div>
            <span>Select from 23 available tools</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-purple-400">3.</div>
            <span>Configure model and parameters</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-purple-400">4.</div>
            <span>Deploy and start chatting</span>
          </li>
        </ul>
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3 mt-4">
          <p className="text-sm text-purple-300">
            💡 Tip: Use the Agent Library to edit existing agents or create new ones from scratch.
          </p>
        </div>
      </div>
    ),
    action: { label: 'Create an Agent', path: '/library' },
  },
  {
    title: 'Execute Workflows',
    icon: Workflow,
    description: 'Run automated multi-agent workflows with real-time tracking.',
    content: (
      <div className="space-y-4">
        <p className="text-slate-300">
          Choose from 25 pre-built workflow templates:
        </p>
        <div className="space-y-2 text-sm">
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="font-medium text-white">Investment Due Diligence</div>
            <div className="text-xs text-slate-400 mt-1">Finance, Research, Investment</div>
          </div>
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="font-medium text-white">Content Production Factory</div>
            <div className="text-xs text-slate-400 mt-1">Research, Content, SEO</div>
          </div>
          <div className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-3">
            <div className="font-medium text-white">Incident Response & Resolution</div>
            <div className="text-xs text-slate-400 mt-1">DevOps, Monitoring, Investigation</div>
          </div>
        </div>
        <p className="text-sm text-slate-400 mt-4">
          Each workflow coordinates multiple specialized agents working together.
        </p>
      </div>
    ),
    action: { label: 'Browse Workflows', path: '/workflows' },
  },
];

export default function GettingStartedWizard({ onClose }) {
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();

  const step = WIZARD_STEPS[currentStep];
  const Icon = step.icon;

  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      handleFinish();
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleFinish = () => {
    localStorage.setItem('wizard-completed', 'true');
    onClose();
  };

  const handleAction = () => {
    if (step.action) {
      localStorage.setItem('wizard-completed', 'true');
      navigate(step.action.path);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800/95 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl max-w-2xl w-full">
        <div className="flex justify-between items-center p-6 border-b border-slate-700/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Icon className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{step.title}</h2>
              <p className="text-sm text-slate-400 mt-0.5">{step.description}</p>
            </div>
          </div>
          <button
            onClick={handleFinish}
            className="p-3 min-h-[44px] min-w-[44px] hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <div className="p-6 min-h-[300px]">
          {step.content}
        </div>

        <div className="flex justify-between items-center p-6 border-t border-slate-700/50 bg-slate-800/50">
          <div className="flex space-x-2">
            {WIZARD_STEPS.map((_, index) => (
              <div
                key={index}
                className={`w-2 h-2 rounded-full transition-colors ${
                  index === currentStep
                    ? 'bg-purple-500'
                    : index < currentStep
                    ? 'bg-purple-500/50'
                    : 'bg-slate-600'
                }`}
              />
            ))}
          </div>

          <div className="flex gap-3">
            {currentStep > 0 && (
              <button
                onClick={handleBack}
                className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors flex items-center space-x-2"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
            )}

            {step.action && (
              <button
                onClick={handleAction}
                className="px-4 py-2 bg-purple-600/20 text-purple-400 rounded-lg hover:bg-purple-600/30 transition-colors"
              >
                {step.action.label}
              </button>
            )}

            <button
              onClick={handleNext}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:from-purple-700 hover:to-pink-700 transition-colors flex items-center space-x-2"
            >
              <span>{currentStep === WIZARD_STEPS.length - 1 ? 'Get Started' : 'Next'}</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
