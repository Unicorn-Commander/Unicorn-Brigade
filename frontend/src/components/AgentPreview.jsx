import {
  CheckCircle,
  Cpu,
  Wrench,
  Sparkles,
  RefreshCw,
  ChevronRight,
  Briefcase,
  Scale,
  Heart,
  Code,
  Shield,
  DollarSign,
  Search,
  AlertCircle,
  Loader,
  BarChart,
  MessageSquare,
  FileText,
  BookOpen
} from 'lucide-react';

const AgentPreview = ({ preview, onConfirm, onReset }) => {
  const progress = calculateProgress(preview);

  return (
    <div className="w-96 bg-slate-900/50 backdrop-blur-xl border-l border-slate-700 p-6 space-y-4 overflow-y-auto animate-slide-in-right scrollbar-thin">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg flex items-center space-x-2">
          <Sparkles className="w-5 h-5 text-amber-400" />
          <span>Building Agent</span>
        </h3>
        <div className="text-sm text-slate-400 font-medium">{progress}%</div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
        <div
          className="bg-gradient-to-r from-purple-500 via-pink-500 to-amber-500 h-2.5 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Status Message */}
      <div className="text-xs text-slate-400 italic">
        {getStatusMessage(preview)}
      </div>

      {/* Agent Name */}
      <PreviewField
        label="Agent Name"
        value={preview.name || preview.displayName}
        status={preview.name || preview.displayName ? 'complete' : 'pending'}
        icon={<Cpu className="w-4 h-4" />}
      />

      {/* Domain */}
      <PreviewField
        label="Domain"
        value={preview.domain ? formatDomain(preview.domain) : null}
        status={preview.domain ? 'complete' : 'pending'}
        icon={getDomainIcon(preview.domain)}
      />

      {/* Model */}
      <PreviewField
        label="AI Model"
        value={preview.model}
        status={preview.model ? 'complete' : 'pending'}
        icon={<Code className="w-4 h-4" />}
      />

      {/* Temperature Slider */}
      <div className="space-y-2 p-3 rounded-lg border border-slate-700 bg-slate-800/30">
        <label className="text-xs text-slate-400 font-medium">Temperature</label>
        <div className="flex items-center space-x-3">
          <div className="flex-1 h-2 bg-slate-700 rounded-full relative overflow-hidden">
            <div
              className="absolute h-2 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full transition-all duration-500"
              style={{ width: `${(preview.temperature / 2) * 100}%` }}
            />
            <div
              className="absolute h-3 w-3 bg-white rounded-full border-2 border-purple-500 -top-0.5 transform -translate-x-1/2 shadow-lg transition-all duration-500"
              style={{ left: `${(preview.temperature / 2) * 100}%` }}
            />
          </div>
          <span className="text-sm font-medium text-white w-8">{preview.temperature.toFixed(1)}</span>
        </div>
        <div className="flex justify-between text-xs text-slate-500">
          <span>Precise</span>
          <span>Creative</span>
        </div>
      </div>

      {/* Max Tokens */}
      {preview.maxTokens && (
        <div className="space-y-1 p-3 rounded-lg border border-slate-700 bg-slate-800/30">
          <label className="text-xs text-slate-400 font-medium">Max Tokens</label>
          <div className="text-sm font-medium text-white">{preview.maxTokens.toLocaleString()}</div>
        </div>
      )}

      {/* Tools */}
      <div className="space-y-2 p-3 rounded-lg border border-slate-700 bg-slate-800/30">
        <label className="text-xs text-slate-400 font-medium flex items-center space-x-2">
          <Wrench className="w-3.5 h-3.5" />
          <span>Tools & Capabilities</span>
        </label>
        {preview.tools && preview.tools.length > 0 ? (
          <div className="space-y-1.5">
            {preview.tools.map((tool, idx) => (
              <div
                key={idx}
                className="text-sm flex items-center space-x-2 animate-fade-in"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
                <span className="text-slate-200">{tool}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-500 italic">No tools specified yet</div>
        )}
      </div>

      {/* Capabilities */}
      {preview.capabilities && preview.capabilities.length > 0 && (
        <div className="space-y-2 p-3 rounded-lg border border-slate-700 bg-slate-800/30">
          <label className="text-xs text-slate-400 font-medium">Special Capabilities</label>
          <div className="flex flex-wrap gap-2">
            {preview.capabilities.map((cap, idx) => (
              <span
                key={idx}
                className="text-xs px-2.5 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 animate-fade-in"
                style={{ animationDelay: `${idx * 50}ms` }}
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* System Prompt Preview */}
      {preview.systemPrompt && (
        <div className="space-y-2 p-3 rounded-lg border border-slate-700 bg-slate-800/30">
          <label className="text-xs text-slate-400 font-medium">System Prompt</label>
          <div className="text-xs text-slate-300 line-clamp-3 italic">
            "{preview.systemPrompt}"
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {preview.status === 'ready' && (
        <div className="space-y-2 pt-4 border-t border-slate-700">
          <button
            onClick={onConfirm}
            className="w-full btn-primary flex items-center justify-center space-x-2 py-3 hover:scale-105 transition-transform"
          >
            <Sparkles className="w-5 h-5" />
            <span className="font-semibold">Create Agent</span>
          </button>
          <button
            onClick={onReset}
            className="w-full btn-secondary flex items-center justify-center space-x-2 py-2"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Start Over</span>
          </button>
        </div>
      )}

      {/* Building Status */}
      {preview.status === 'building' && progress < 100 && (
        <div className="flex items-center justify-center space-x-2 text-sm text-slate-400 pt-2">
          <Loader className="w-4 h-4 animate-spin" />
          <span>Gathering information...</span>
        </div>
      )}
    </div>
  );
};

const PreviewField = ({ label, value, status, icon }) => (
  <div className="space-y-1.5">
    <label className="text-xs text-slate-400 font-medium">{label}</label>
    <div className={`p-3 rounded-lg border transition-all duration-300 ${
      status === 'complete'
        ? 'bg-emerald-500/10 border-emerald-500/30 animate-pulse-soft'
        : 'bg-slate-800/50 border-slate-700'
    }`}>
      <div className="flex items-center space-x-2">
        <div className={status === 'complete' ? 'text-emerald-400' : 'text-slate-500'}>
          {icon}
        </div>
        <span className={`text-sm flex-1 ${status === 'complete' ? 'text-white font-medium' : 'text-slate-500'}`}>
          {value || <span className="italic">Pending...</span>}
        </span>
        {status === 'complete' && (
          <CheckCircle className="w-4 h-4 text-emerald-400 animate-fade-in" />
        )}
      </div>
    </div>
  </div>
);

// Helper Functions
const calculateProgress = (preview) => {
  let total = 0;
  let completed = 0;

  // Essential fields
  const essentialFields = [
    { key: 'name', weight: 20 },
    { key: 'domain', weight: 20 },
    { key: 'model', weight: 20 }
  ];

  essentialFields.forEach(field => {
    total += field.weight;
    if (preview[field.key] || (field.key === 'name' && preview.displayName)) {
      completed += field.weight;
    }
  });

  // Optional fields
  total += 20; // Temperature (always has default)
  completed += 20;

  // Tools
  total += 10;
  if (preview.tools && preview.tools.length > 0) {
    completed += 10;
  }

  // Capabilities
  total += 10;
  if (preview.capabilities && preview.capabilities.length > 0) {
    completed += 10;
  }

  return Math.round((completed / total) * 100);
};

const getStatusMessage = (preview) => {
  const progress = calculateProgress(preview);

  if (preview.status === 'ready') {
    return 'Agent configuration complete! Ready to deploy.';
  }

  if (progress === 0) {
    return 'Tell The General what kind of agent you need...';
  }

  if (progress < 50) {
    return 'Learning about your requirements...';
  }

  if (progress < 80) {
    return 'Configuring agent specifications...';
  }

  if (progress < 100) {
    return 'Almost ready to deploy...';
  }

  return 'Configuration complete!';
};

const formatDomain = (domain) => {
  if (!domain) return null;

  const domainMap = {
    'financial': 'Financial Analysis',
    'legal': 'Legal Research',
    'medical': 'Medical & Healthcare',
    'technology': 'Technology & Engineering',
    'investigation': 'Investigation & Research',
    'cybersecurity': 'Cybersecurity',
    'data-analysis': 'Data Analysis',
    'customer-service': 'Customer Service',
    'content-creation': 'Content Creation',
    'education': 'Education & Training'
  };

  return domainMap[domain.toLowerCase()] || domain.charAt(0).toUpperCase() + domain.slice(1);
};

const getDomainIcon = (domain) => {
  if (!domain) return <AlertCircle className="w-4 h-4" />;

  const iconMap = {
    'financial': <DollarSign className="w-4 h-4" />,
    'legal': <Scale className="w-4 h-4" />,
    'medical': <Heart className="w-4 h-4" />,
    'technology': <Code className="w-4 h-4" />,
    'investigation': <Search className="w-4 h-4" />,
    'cybersecurity': <Shield className="w-4 h-4" />,
    'data-analysis': <BarChart className="w-4 h-4" />,
    'customer-service': <MessageSquare className="w-4 h-4" />,
    'content-creation': <FileText className="w-4 h-4" />,
    'education': <BookOpen className="w-4 h-4" />
  };

  const Icon = iconMap[domain.toLowerCase()] || Briefcase;
  return typeof Icon === 'function' ? <Icon className="w-4 h-4" /> : Icon;
};

export default AgentPreview;
