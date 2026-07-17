import React, { useState } from 'react';
import {
  X,
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  Lightbulb,
  MessageSquare,
  Bot,
  Workflow,
  Sparkles
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Modal from './ui/Modal';

const WIZARD_STEPS = [
  {
    title: 'Welcome to Unicorn Brigade',
    icon: Sparkles,
    description: 'Your AI Agent Factory for building, deploying, and orchestrating intelligent agents.',
    content: (
      <div className="space-y-4">
        <p className="text-muted">
          Unicorn Brigade is a production-ready platform with:
        </p>
        <ul className="space-y-2 text-sm text-muted">
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-fg">Production-ready agents</strong> across multiple domains</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-fg">Hierarchical multi-agent workflows</strong> with real-time tracking</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-fg">MCP server integrations</strong> with a growing tool catalog</span>
          </li>
          <li className="flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span><strong className="text-fg">Built-in working tools</strong> (search, email, memory, browser, and more)</span>
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
        <p className="text-muted">
          Try chatting with one of our specialized agents:
        </p>
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="text-sm font-medium text-fg">LtCol Sterling</div>
            <div className="text-xs text-muted mt-1">Financial Analysis</div>
          </div>
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="text-sm font-medium text-fg">Maj CodeCraft</div>
            <div className="text-xs text-muted mt-1">Software Engineering</div>
          </div>
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="text-sm font-medium text-fg">Cpl Scout</div>
            <div className="text-xs text-muted mt-1">Research & Intelligence</div>
          </div>
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="text-sm font-medium text-fg">Sgt Scribe</div>
            <div className="text-xs text-muted mt-1">Meeting Notes & Summaries</div>
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
        <p className="text-muted">
          Build agents tailored to your needs:
        </p>
        <ul className="space-y-2 text-sm text-muted">
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-unicorn-400">1.</div>
            <span>Define personality and behavior</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-unicorn-400">2.</div>
            <span>Select tools from the Tool Library</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-unicorn-400">3.</div>
            <span>Configure model and parameters</span>
          </li>
          <li className="flex items-start space-x-2">
            <div className="w-5 h-5 flex-shrink-0 mt-0.5 text-unicorn-400">4.</div>
            <span>Deploy and start chatting</span>
          </li>
        </ul>
        <div className="bg-unicorn-500/10 border border-unicorn-500/30 rounded-lg p-3 mt-4">
          <p className="text-sm text-unicorn-300 flex items-start gap-2">
            <Lightbulb className="w-4 h-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span>Tip: Use the Agent Library to edit existing agents or create new ones from scratch.</span>
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
        <p className="text-muted">
          Choose from a library of ready-made workflow templates:
        </p>
        <div className="space-y-2 text-sm">
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="font-medium text-fg">Investment Due Diligence</div>
            <div className="text-xs text-muted mt-1">Finance, Research, Investment</div>
          </div>
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="font-medium text-fg">Content Production Factory</div>
            <div className="text-xs text-muted mt-1">Research, Content, SEO</div>
          </div>
          <div className="bg-elevated/30 border border-border/50 rounded-lg p-3">
            <div className="font-medium text-fg">Incident Response & Resolution</div>
            <div className="text-xs text-muted mt-1">DevOps, Monitoring, Investigation</div>
          </div>
        </div>
        <p className="text-sm text-muted mt-4">
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
    <Modal
      onClose={handleFinish}
      ariaLabel={`Getting started: ${step.title}`}
      showClose={false}
      panelClassName="bg-elevated/95 backdrop-blur-xl border border-border/50 rounded-xl shadow-2xl max-w-2xl w-full"
    >
        <div className="flex justify-between items-center p-6 border-b border-border/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-unicorn-500/20 rounded-lg">
              <Icon className="w-6 h-6 text-unicorn-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-fg">{step.title}</h2>
              <p className="text-sm text-muted mt-0.5">{step.description}</p>
            </div>
          </div>
          <button
            onClick={handleFinish}
            aria-label="Close getting started"
            className="p-3 min-h-[44px] min-w-[44px] hover:bg-elevated/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-muted" />
          </button>
        </div>

        <div className="p-6 min-h-[300px]">
          {step.content}
        </div>

        <div className="flex justify-between items-center p-6 border-t border-border/50 bg-elevated/50">
          <div className="flex space-x-2">
            {WIZARD_STEPS.map((_, index) => (
              <div
                key={index}
                className={`w-2 h-2 rounded-full transition-colors ${
                  index === currentStep
                    ? 'bg-unicorn-500'
                    : index < currentStep
                    ? 'bg-unicorn-500/50'
                    : 'bg-border'
                }`}
              />
            ))}
          </div>

          <div className="flex gap-3">
            {currentStep > 0 && (
              <button
                onClick={handleBack}
                className="px-4 py-2 bg-elevated text-fg rounded-lg hover:bg-elevated transition-colors flex items-center space-x-2"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
            )}

            {step.action && (
              <button
                onClick={handleAction}
                className="px-4 py-2 bg-unicorn-600/20 text-unicorn-400 rounded-lg hover:bg-unicorn-600/30 transition-colors"
              >
                {step.action.label}
              </button>
            )}

            <button
              onClick={handleNext}
              className="px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-700 hover:to-unicorn-600 transition-colors flex items-center space-x-2"
            >
              <span>{currentStep === WIZARD_STEPS.length - 1 ? 'Get Started' : 'Next'}</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
    </Modal>
  );
}
