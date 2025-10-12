import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import ModelSelector from './ModelSelector';
import ParameterSlider from './ParameterSlider';
import TagInput from './TagInput';

const AgentConfigurationTab = ({ agent, editMode, onUpdate }) => {
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    advanced: false,
    behavior: false
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const updateField = (field, value) => {
    onUpdate({ ...agent, [field]: value });
  };

  // Initialize advanced parameters with defaults if they don't exist
  const topP = agent.topP !== undefined ? agent.topP : 1.0;
  const frequencyPenalty = agent.frequencyPenalty !== undefined ? agent.frequencyPenalty : 0.0;
  const presencePenalty = agent.presencePenalty !== undefined ? agent.presencePenalty : 0.0;
  const stop = agent.stop || [];
  const streaming = agent.streaming !== undefined ? agent.streaming : true;
  const safeMode = agent.safeMode !== undefined ? agent.safeMode : false;
  const maxRetries = agent.maxRetries !== undefined ? agent.maxRetries : 3;
  const timeout = agent.timeout !== undefined ? agent.timeout : 120;

  const maxTokensPresets = [2048, 4096, 8192, 16384, 32768];

  const SectionHeader = ({ title, section, description }) => (
    <button
      onClick={() => toggleSection(section)}
      className="flex items-center justify-between w-full py-3 px-4 bg-slate-800/30 hover:bg-slate-800/50 rounded-lg transition-colors mb-4"
    >
      <div className="flex items-center space-x-3">
        {expandedSections[section] ? (
          <ChevronDown className="w-5 h-5 text-unicorn-400" />
        ) : (
          <ChevronRight className="w-5 h-5 text-slate-400" />
        )}
        <div className="text-left">
          <h3 className="text-lg font-semibold text-slate-200">{title}</h3>
          {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
        </div>
      </div>
    </button>
  );

  return (
    <div className="space-y-6">
      {/* Basic Settings */}
      <div>
        <SectionHeader
          title="Basic Settings"
          section="basic"
          description="Core LLM configuration parameters"
        />

        {expandedSections.basic && (
          <div className="space-y-6 p-4 bg-slate-800/20 rounded-lg border border-slate-700/50">
            {/* Model */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Model
              </label>
              {editMode ? (
                <ModelSelector
                  value={agent.model}
                  onChange={(value) => updateField('model', value)}
                />
              ) : (
                <div className="space-y-2">
                  <p className="text-slate-200 font-mono">{agent.model}</p>
                  <p className="text-xs text-slate-400">Provider: OpenRouter (auto-selected)</p>
                </div>
              )}
            </div>

            {/* Temperature */}
            <div>
              {editMode ? (
                <ParameterSlider
                  label="Temperature"
                  value={agent.temperature}
                  onChange={(value) => updateField('temperature', value)}
                  min={0}
                  max={2}
                  step={0.1}
                  description="Lower = Focused & Consistent, Higher = Creative & Variable"
                  leftLabel="Focused"
                  rightLabel="Creative"
                />
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Temperature</label>
                  <p className="text-slate-200">{agent.temperature}</p>
                  <p className="text-xs text-slate-400 mt-1">Lower = Focused, Higher = Creative</p>
                </div>
              )}
            </div>

            {/* Max Tokens */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Max Tokens
              </label>
              {editMode ? (
                <>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {maxTokensPresets.map(preset => (
                      <button
                        key={preset}
                        onClick={() => updateField('maxTokens', preset)}
                        className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                          agent.maxTokens === preset
                            ? 'bg-unicorn-500 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                      >
                        {preset >= 1024 ? `${preset / 1024}K` : preset}
                      </button>
                    ))}
                  </div>
                  <input
                    type="number"
                    value={agent.maxTokens}
                    onChange={(e) => updateField('maxTokens', parseInt(e.target.value) || 4096)}
                    className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                    placeholder="Or enter custom value..."
                    min={256}
                    max={128000}
                  />
                </>
              ) : (
                <p className="text-slate-200">{agent.maxTokens}</p>
              )}
            </div>

            {/* Version (Read-only) */}
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Version</label>
              <p className="text-slate-200">{agent.version}</p>
            </div>
          </div>
        )}
      </div>

      {/* Advanced Settings */}
      <div>
        <SectionHeader
          title="Advanced Settings"
          section="advanced"
          description="Fine-tune model behavior and output quality"
        />

        {expandedSections.advanced && (
          <div className="space-y-6 p-4 bg-slate-800/20 rounded-lg border border-slate-700/50">
            {/* Top-P */}
            <div>
              {editMode ? (
                <ParameterSlider
                  label="Top-P (Nucleus Sampling)"
                  value={topP}
                  onChange={(value) => updateField('topP', value)}
                  min={0}
                  max={1}
                  step={0.05}
                  description="Controls diversity of word choice. Lower values = more focused, higher = more diverse"
                  leftLabel="Focused"
                  rightLabel="Diverse"
                />
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Top-P (Nucleus Sampling)</label>
                  <p className="text-slate-200">{topP}</p>
                  <p className="text-xs text-slate-400 mt-1">Controls diversity of word choice</p>
                </div>
              )}
            </div>

            {/* Frequency Penalty */}
            <div>
              {editMode ? (
                <ParameterSlider
                  label="Frequency Penalty"
                  value={frequencyPenalty}
                  onChange={(value) => updateField('frequencyPenalty', value)}
                  min={-2}
                  max={2}
                  step={0.1}
                  description="Reduces repetition of common phrases. Positive values discourage repetition"
                  leftLabel="Allow Repetition"
                  rightLabel="Discourage"
                />
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Frequency Penalty</label>
                  <p className="text-slate-200">{frequencyPenalty}</p>
                  <p className="text-xs text-slate-400 mt-1">Reduces repetition of common phrases</p>
                </div>
              )}
            </div>

            {/* Presence Penalty */}
            <div>
              {editMode ? (
                <ParameterSlider
                  label="Presence Penalty"
                  value={presencePenalty}
                  onChange={(value) => updateField('presencePenalty', value)}
                  min={-2}
                  max={2}
                  step={0.1}
                  description="Encourages new topics. Positive values encourage discussing new subjects"
                  leftLabel="Stay on Topic"
                  rightLabel="Explore Topics"
                />
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Presence Penalty</label>
                  <p className="text-slate-200">{presencePenalty}</p>
                  <p className="text-xs text-slate-400 mt-1">Encourages new topics</p>
                </div>
              )}
            </div>

            {/* Stop Sequences */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Stop Sequences
              </label>
              <p className="text-xs text-slate-400 mb-3">
                Strings that will cause the model to stop generating. Useful for controlling output format.
              </p>
              {editMode ? (
                <TagInput
                  tags={stop}
                  onAdd={(tag) => updateField('stop', [...stop, tag])}
                  onRemove={(tag) => updateField('stop', stop.filter(t => t !== tag))}
                  placeholder="Enter stop sequence (e.g., END, STOP)"
                  maxTags={10}
                />
              ) : (
                <div className="flex flex-wrap gap-2">
                  {stop.length > 0 ? (
                    stop.map((seq, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1.5 bg-unicorn-500/20 border border-unicorn-500/30 rounded-lg text-sm text-unicorn-300 font-mono"
                      >
                        {seq}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-slate-500 italic">No stop sequences defined</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Behavior Settings */}
      <div>
        <SectionHeader
          title="Behavior Settings"
          section="behavior"
          description="Control runtime behavior and error handling"
        />

        {expandedSections.behavior && (
          <div className="space-y-6 p-4 bg-slate-800/20 rounded-lg border border-slate-700/50">
            {/* Streaming */}
            <div className="flex items-start space-x-3">
              {editMode ? (
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={streaming}
                    onChange={(e) => updateField('streaming', e.target.checked)}
                    className="w-5 h-5 rounded border-slate-600 text-unicorn-500 focus:ring-2 focus:ring-unicorn-500 focus:ring-offset-0 bg-slate-700"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-300">Enable Streaming</span>
                    <p className="text-xs text-slate-400">Real-time response streaming for better UX</p>
                  </div>
                </label>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Streaming</label>
                  <p className="text-slate-200">{streaming ? 'Enabled' : 'Disabled'}</p>
                  <p className="text-xs text-slate-400 mt-1">Real-time response streaming</p>
                </div>
              )}
            </div>

            {/* Safe Mode */}
            <div className="flex items-start space-x-3">
              {editMode ? (
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={safeMode}
                    onChange={(e) => updateField('safeMode', e.target.checked)}
                    className="w-5 h-5 rounded border-slate-600 text-unicorn-500 focus:ring-2 focus:ring-unicorn-500 focus:ring-offset-0 bg-slate-700"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-300">Safe Mode</span>
                    <p className="text-xs text-slate-400">Enable content filtering and safety checks</p>
                  </div>
                </label>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Safe Mode</label>
                  <p className="text-slate-200">{safeMode ? 'Enabled' : 'Disabled'}</p>
                  <p className="text-xs text-slate-400 mt-1">Content filtering enabled</p>
                </div>
              )}
            </div>

            {/* Max Retries */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Max Retries
              </label>
              <p className="text-xs text-slate-400 mb-3">
                Number of automatic retry attempts on API failure
              </p>
              {editMode ? (
                <input
                  type="number"
                  value={maxRetries}
                  onChange={(e) => updateField('maxRetries', parseInt(e.target.value) || 3)}
                  className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                  min={0}
                  max={10}
                />
              ) : (
                <p className="text-slate-200">{maxRetries}</p>
              )}
            </div>

            {/* Timeout */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Timeout (seconds)
              </label>
              <p className="text-xs text-slate-400 mb-3">
                Maximum time to wait for a response before timing out
              </p>
              {editMode ? (
                <input
                  type="number"
                  value={timeout}
                  onChange={(e) => updateField('timeout', parseInt(e.target.value) || 120)}
                  className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                  min={10}
                  max={600}
                />
              ) : (
                <p className="text-slate-200">{timeout}s</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
        <p className="text-sm text-cyan-300 leading-relaxed">
          <strong>Note:</strong> Advanced parameters are optional. If not set, the model will use provider defaults.
          Changes to these settings will take effect on the next agent invocation.
        </p>
      </div>
    </div>
  );
};

export default AgentConfigurationTab;
