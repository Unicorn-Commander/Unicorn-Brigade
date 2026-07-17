import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, Bot, User, Loader, RefreshCw, BookOpen, ChevronRight, ChevronLeft, ChevronDown, Settings, RotateCcw, Rocket, X, CheckCircle, Cpu, Wrench, Shield } from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import { apiJson } from '../services/http';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import AgentPreview from '../components/AgentPreview';
import Modal from '../components/ui/Modal';
import ModelSelector from '../components/ModelSelector';
import ParameterSlider from '../components/ParameterSlider';
import { GunnyAvatar } from '../components/UnicornBrigadeLogo';
import useAuth from '../hooks/useAuth';

const AgentBuilderChat = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [gunnyInfo, setGunnyInfo] = useState(null);
  const [showPreview, setShowPreview] = useState(true);
  const messagesEndRef = useRef(null);

  // Agent Preferences State
  const [showPreferences, setShowPreferences] = useState(false);
  const [preferences, setPreferences] = useState({
    model: 'ai-choice', // null or 'ai-choice' = let AI decide
    domain: null,
    temperature: 0.7,
    maxTokens: 4096
  });

  // Agent Preview State
  const [agentPreview, setAgentPreview] = useState({
    name: null,
    displayName: null,
    domain: null,
    model: null,
    temperature: 0.7,
    maxTokens: 4096,
    tools: [],
    capabilities: [],
    systemPrompt: null,
    status: 'building' // 'building', 'ready', 'created'
  });

  // Confirmation Flow State
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [parsedAgentConfig, setParsedAgentConfig] = useState(null);
  const [isDeploying, setIsDeploying] = useState(false);

  useEffect(() => {
    // Generate session ID
    setSessionId(`session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);

    // Load Gunny info
    loadGunnyInfo();

    // Welcome message
    setMessages([
      {
        role: 'assistant',
        content: `Howdy! I'm **Gunny**, your Agent Builder.

I'm here to help you build and deploy new AI agents through conversation. Whether you need a financial analyst, a legal researcher, a cybersecurity specialist, or any other type of agent, I'll guide you through the process.

**How can I assist you today?**

- Tell me about the agent you want to create
- Ask about available tools and capabilities
- Explore different agent domains
- Get recommendations for your use case

What would you like to build?`
      }
    ]);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadGunnyInfo = async () => {
    try {
      const data = await apiJson('/agent-builder/info');
      setGunnyInfo(data);
    } catch (error) {
      console.error('Failed to load Gunny info:', error);
    }
  };

  // Parse agent details from The General's messages
  const parseAgentDetails = (message, currentPreview) => {
    const updates = { ...currentPreview };

    // Extract agent name
    const namePatterns = [
      /(?:call it|name it|agent called|agent named)\s+["']?([^"'\n.]+)["']?/i,
      /(?:create|build)\s+(?:an?\s+)?["']?([^"'\n.]+)["']?\s+agent/i,
      /agent\s+name[:\s]+["']?([^"'\n.]+)["']?/i
    ];

    for (const pattern of namePatterns) {
      const match = message.match(pattern);
      if (match && match[1]) {
        const name = match[1].trim();
        if (name.length > 2 && name.length < 50 && !name.match(/the|this|that|your/i)) {
          updates.name = name;
          updates.displayName = name;
          break;
        }
      }
    }

    // Extract model
    const modelPatterns = [
      /(gpt-4[^\s,]*)/i,
      /(claude[^\s,]*)/i,
      /(gemini[^\s,]*)/i
    ];

    for (const pattern of modelPatterns) {
      const match = message.match(pattern);
      if (match && match[1] && match[1].match(/gpt|claude|gemini/i)) {
        updates.model = match[1].trim();
        break;
      }
    }

    // Extract domain
    const domains = ['financial', 'legal', 'medical', 'technology', 'investigation', 'cybersecurity',
                    'data-analysis', 'customer-service', 'content-creation', 'education'];
    for (const domain of domains) {
      if (message.toLowerCase().includes(domain)) {
        updates.domain = domain;
        break;
      }
    }

    // Extract temperature
    const tempMatch = message.match(/temperature[:\s]+([0-9.]+)/i);
    if (tempMatch) {
      const temp = parseFloat(tempMatch[1]);
      if (temp >= 0 && temp <= 2) updates.temperature = temp;
    }

    // Extract max tokens
    const tokensMatch = message.match(/(?:max tokens|token limit)[:\s]+([0-9,]+)/i);
    if (tokensMatch) {
      const tokens = parseInt(tokensMatch[1].replace(/,/g, ''));
      if (tokens > 0) updates.maxTokens = tokens;
    }

    // Extract tools
    const toolsSection = message.match(/(?:tools?|capabilities)[:\s]+([^\n]+(?:\n[-•*]\s*[^\n]+)*)/i);
    if (toolsSection) {
      const toolsList = toolsSection[1]
        .split(/\n|,/)
        .map(t => t.replace(/^[-•*]\s*/, '').trim())
        .filter(t => t.length > 2 && t.length < 50);
      if (toolsList.length > 0) {
        updates.tools = [...new Set([...updates.tools, ...toolsList])];
      }
    }

    // Extract inline tool mentions
    const commonTools = ['web search', 'calculator', 'code execution', 'database', 'api',
                        'data analysis', 'visualization', 'file system'];
    for (const tool of commonTools) {
      if (message.toLowerCase().includes(tool) && !updates.tools.some(t => t.toLowerCase().includes(tool))) {
        updates.tools.push(tool.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '));
      }
    }

    // Extract capabilities
    const capMatch = message.match(/(?:capabilities|can)[:\s]+([^\n]+(?:\n[-•*]\s*[^\n]+)*)/i);
    if (capMatch) {
      const capsList = capMatch[1]
        .split(/\n|,/)
        .map(c => c.replace(/^[-•*]\s*/, '').trim())
        .filter(c => c.length > 2 && c.length < 50);
      if (capsList.length > 0) {
        updates.capabilities = [...new Set([...updates.capabilities, ...capsList])];
      }
    }

    // Check if ready to create
    if (message.match(/ready to create|shall I create|proceed with creation|create this agent|deploy.*agent/i)) {
      updates.status = 'ready';
    }

    return updates;
  };

  // Parse JSON config block from Gunny's message
  const parseJsonConfigFromMessage = (messageContent) => {
    try {
      // Look for ```json ... ``` blocks
      const jsonBlockMatch = messageContent.match(/```json\s*([\s\S]*?)```/);
      if (jsonBlockMatch && jsonBlockMatch[1]) {
        const parsed = JSON.parse(jsonBlockMatch[1].trim());
        return parsed;
      }

      // Fallback: look for any JSON object in the message
      const jsonObjectMatch = messageContent.match(/\{[\s\S]*"name"[\s\S]*\}/);
      if (jsonObjectMatch) {
        const parsed = JSON.parse(jsonObjectMatch[0]);
        if (parsed.name) return parsed;
      }
    } catch (err) {
      console.error('Failed to parse JSON config from message:', err);
    }
    return null;
  };

  // Handle deploy agent from confirmation panel
  const handleDeployAgent = async () => {
    if (!parsedAgentConfig) return;

    setIsDeploying(true);
    try {
      const deployPayload = {
        name: parsedAgentConfig.name,
        displayName: parsedAgentConfig.displayName || parsedAgentConfig.name,
        domain: parsedAgentConfig.domain || agentPreview.domain,
        model: parsedAgentConfig.model || agentPreview.model || 'gpt-4-turbo',
        temperature: parsedAgentConfig.temperature ?? agentPreview.temperature ?? 0.7,
        maxTokens: parsedAgentConfig.maxTokens || agentPreview.maxTokens || 4096,
        tools: parsedAgentConfig.tools || agentPreview.tools || [],
        capabilities: parsedAgentConfig.capabilities || agentPreview.capabilities || [],
        systemPrompt: parsedAgentConfig.systemPrompt || agentPreview.systemPrompt,
        avatar: parsedAgentConfig.avatar,
        title: parsedAgentConfig.title,
        bio: parsedAgentConfig.bio,
        createdBy: user?.id || 'guest-user',
        createdByAgent: 'the-general-001'
      };

      const created = await apiJson('/agents', {
        method: 'POST',
        body: JSON.stringify(deployPayload)
      });

      notify.success('Agent deployed successfully!');
      setShowConfirmation(false);
      setParsedAgentConfig(null);
      setAgentPreview(prev => ({ ...prev, status: 'created' }));

      // Navigate to agent detail page after a short delay
      setTimeout(() => {
        navigate(`/agent/${created.id}`);
      }, 1000);
    } catch (error) {
      console.error('Failed to deploy agent:', error);
      const errorMsg = error.data?.error || error.message || 'Unknown error';
      toast.error(`Failed to deploy agent: ${errorMsg}`);
    } finally {
      setIsDeploying(false);
    }
  };

  // Handle continue editing from confirmation panel
  const handleContinueEditing = () => {
    setShowConfirmation(false);
    toast('Continue refining your agent. Tell Gunny what you want to change.', {
      icon: '🎯',
      duration: 3000
    });
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      // Include preferences in the request if they're set
      const requestData = {
        message: userMessage,
        sessionId: sessionId,
        userId: user?.id || 'guest-user',
        preferences: preferences.model === 'ai-choice' ? {} : preferences
      };

      const data = await apiJson('/agent-builder/chat', {
        method: 'POST',
        body: JSON.stringify(requestData)
      });

      // Add assistant response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message,
        usage: data.usage,
        agentCreationIntent: data.agentCreationIntent
      }]);

      // Parse agent details from response and update preview
      const updatedPreview = parseAgentDetails(data.message, agentPreview);
      setAgentPreview(updatedPreview);

      // Show confirmation flow when creation intent is detected
      if (data.agentCreationIntent) {
        const jsonConfig = parseJsonConfigFromMessage(data.message);
        if (jsonConfig) {
          setParsedAgentConfig(jsonConfig);
          setShowConfirmation(true);
          toast('Agent configuration ready! Review and deploy.', {
            icon: '🎖️',
            duration: 4000
          });
        } else {
          // Fallback: use the agentPreview state as config
          const fallbackConfig = {
            name: updatedPreview.name,
            displayName: updatedPreview.displayName,
            domain: updatedPreview.domain,
            model: updatedPreview.model,
            temperature: updatedPreview.temperature,
            maxTokens: updatedPreview.maxTokens,
            tools: updatedPreview.tools,
            capabilities: updatedPreview.capabilities,
            systemPrompt: updatedPreview.systemPrompt
          };
          if (fallbackConfig.name) {
            setParsedAgentConfig(fallbackConfig);
            setShowConfirmation(true);
            toast('Agent creation detected! Review the configuration.', {
              icon: '🎖️',
              duration: 4000
            });
          } else {
            toast('Agent creation detected, but no configuration found. Ask Gunny to provide the JSON config.', {
              icon: '🎖️',
              duration: 4000
            });
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Failed to send message. Please try again.');

      // Add error message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'I apologize, but I encountered an error. Please try your message again.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetConversation = () => {
    if (confirm('Are you sure you want to start a new conversation? Your current conversation will be lost.')) {
      const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      setSessionId(newSessionId);
      setMessages([
        {
          role: 'assistant',
          content: `New conversation started. I'm ready to help you build a new agent!

What would you like to create today?`
        }
      ]);
      // Reset preview
      setAgentPreview({
        name: null,
        displayName: null,
        domain: null,
        model: null,
        temperature: 0.7,
        maxTokens: 4096,
        tools: [],
        capabilities: [],
        systemPrompt: null,
        status: 'building'
      });
    }
  };

  const handleCreateAgent = async () => {
    try {
      // Call backend to create agent with current preview
      const created = await apiJson('/agents', {
        method: 'POST',
        body: JSON.stringify({
          name: agentPreview.name,
          displayName: agentPreview.displayName || agentPreview.name,
          domain: agentPreview.domain,
          model: agentPreview.model || 'gpt-4-turbo',
          temperature: agentPreview.temperature,
          maxTokens: agentPreview.maxTokens,
          tools: agentPreview.tools,
          capabilities: agentPreview.capabilities,
          systemPrompt: agentPreview.systemPrompt,
          createdBy: user?.id || 'guest-user',
          createdByAgent: 'the-general-001'
        })
      });

      notify.success('Agent created successfully!');

      // Update preview status
      setAgentPreview({ ...agentPreview, status: 'created' });

      // Navigate to agent detail page after a short delay
      setTimeout(() => {
        navigate(`/agent/${created.id}`);
      }, 1000);
    } catch (error) {
      console.error('Failed to create agent:', error);
      toast.error('Failed to create agent. Please try again.');
    }
  };

  const handleResetPreview = () => {
    setAgentPreview({
      name: null,
      displayName: null,
      domain: null,
      model: null,
      temperature: 0.7,
      maxTokens: 4096,
      tools: [],
      capabilities: [],
      systemPrompt: null,
      status: 'building'
    });
    notify.success('Preview reset. Start fresh!');
  };

  const resetPreferences = () => {
    setPreferences({
      model: 'ai-choice',
      domain: null,
      temperature: 0.7,
      maxTokens: 4096
    });
    notify.success('Preferences reset to defaults');
  };

  const applyPreferences = () => {
    notify.success('Preferences will be applied to Gunny\'s recommendations');
    setShowPreferences(false);
  };

  const domains = [
    { value: null, label: 'Any domain' },
    { value: 'financial', label: 'Financial' },
    { value: 'legal', label: 'Legal' },
    { value: 'medical', label: 'Medical' },
    { value: 'cybersecurity', label: 'Cybersecurity' },
    { value: 'analytics', label: 'Analytics' },
    { value: 'customer-service', label: 'Customer Service' },
    { value: 'education', label: 'Education' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'research', label: 'Research' }
  ];

  const maxTokensPresets = [2048, 4096, 8192, 16384, 32768];

  return (
    <div className="h-screen flex bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex-shrink-0 border-b border-slate-700 bg-slate-900/50 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
              <GunnyAvatar size={56} />
              <div>
                <h1 className="text-xl font-bold text-gradient">Gunny</h1>
                <p className="text-sm text-slate-400">Agent Builder</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              {gunnyInfo && (
                <div className="text-xs text-slate-400">
                  <div className="flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    <span>{gunnyInfo.theGeneral?.status || 'ready'}</span>
                  </div>
                </div>
              )}

              <button
                onClick={resetConversation}
                className="btn-secondary flex items-center space-x-2"
                title="Start New Conversation"
              >
                <RefreshCw className="w-4 h-4" />
                <span>New Chat</span>
              </button>

              <a
                href="/library"
                className="btn-secondary flex items-center space-x-2"
                title="View Agent Library"
              >
                <BookOpen className="w-4 h-4" />
                <span>Library</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Preferences Panel */}
      <div className="flex-shrink-0 border-b border-slate-700 bg-slate-900/30">
        <div className="max-w-6xl mx-auto p-4">
          <button
            onClick={() => setShowPreferences(!showPreferences)}
            className="flex items-center space-x-2 text-slate-300 hover:text-unicorn-400 transition-colors w-full"
          >
            <Settings className="w-4 h-4" />
            <span className="font-medium">Agent Preferences (Optional)</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${showPreferences ? 'rotate-180' : ''}`} />
          </button>

          {showPreferences && (
            <div className="mt-4 p-6 bg-slate-800/30 border border-slate-700 rounded-xl space-y-6 animate-fade-in">
              <p className="text-sm text-slate-400 leading-relaxed">
                These preferences guide Gunny's recommendations. Leave blank or use default values for AI to decide best options.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Preferred Model */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Preferred Model
                  </label>
                  <ModelSelector
                    value={preferences.model}
                    onChange={(value) => setPreferences({ ...preferences, model: value })}
                    allowAIChoice={true}
                  />
                </div>

                {/* Target Domain */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Target Domain
                  </label>
                  <select
                    aria-label="Agent domain"
                    value={preferences.domain || ''}
                    onChange={(e) => setPreferences({ ...preferences, domain: e.target.value || null })}
                    className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                  >
                    {domains.map(domain => (
                      <option key={domain.value || 'any'} value={domain.value || ''}>
                        {domain.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Temperature Slider */}
              <div>
                <ParameterSlider
                  label="Temperature"
                  value={preferences.temperature}
                  onChange={(value) => setPreferences({ ...preferences, temperature: value })}
                  min={0}
                  max={2}
                  step={0.1}
                  description="Controls creativity and randomness in responses"
                  leftLabel="Focused"
                  rightLabel="Creative"
                />
              </div>

              {/* Max Tokens */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Max Tokens
                </label>
                <div className="flex items-center space-x-2 mb-2">
                  {maxTokensPresets.map(preset => (
                    <button
                      key={preset}
                      onClick={() => setPreferences({ ...preferences, maxTokens: preset })}
                      className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                        preferences.maxTokens === preset
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
                  value={preferences.maxTokens}
                  onChange={(e) => setPreferences({ ...preferences, maxTokens: parseInt(e.target.value) || 4096 })}
                  className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                  placeholder="Or enter custom value..."
                  min={256}
                  max={128000}
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-3 pt-4 border-t border-slate-700">
                <button
                  onClick={applyPreferences}
                  className="btn-primary flex items-center space-x-2"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Apply Preferences</span>
                </button>
                <button
                  onClick={resetPreferences}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Reset to Defaults</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-6 space-y-6">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
            >
              <div
                className={`flex items-start space-x-3 max-w-3xl ${
                  message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                }`}
              >
                {/* Avatar */}
                <div
                  className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center overflow-hidden ${
                    message.role === 'user'
                      ? 'bg-gradient-to-br from-cyan-500 to-blue-600'
                      : 'border-2 border-amber-500/30'
                  }`}
                >
                  {message.role === 'user' ? (
                    <User className="w-5 h-5 text-white" />
                  ) : (
                    <span className="text-lg" role="img" aria-label="Gunny">🎯</span>
                  )}
                </div>

                {/* Message Content */}
                <div
                  className={`flex-1 rounded-2xl p-4 ${
                    message.role === 'user'
                      ? 'bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30'
                      : 'bg-gradient-to-br from-slate-800/80 to-slate-700/80 border border-slate-600/30'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-slate-100 whitespace-pre-wrap">{message.content}</p>
                  )}

                  {/* Usage Stats */}
                  {message.usage && (
                    <div className="mt-3 pt-3 border-t border-slate-600/30 flex items-center space-x-4 text-xs text-slate-400">
                      <span>Tokens: {message.usage.total_tokens || 0}</span>
                      <span>Model: {message.usage.model || 'gpt-4-turbo'}</span>
                    </div>
                  )}

                  {/* Agent Creation Intent Badge */}
                  {message.agentCreationIntent && (
                    <div className="mt-3 flex items-center space-x-2 text-xs">
                      <div className="px-2 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center space-x-1">
                        <Sparkles className="w-3 h-3" />
                        <span>Ready to create agent</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Loading Indicator */}
          {loading && (
            <div className="flex justify-start animate-fade-in">
              <div className="flex items-start space-x-3 max-w-3xl">
                <GunnyAvatar size={40} />
                <div className="flex-1 rounded-2xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-700/80 border border-slate-600/30">
                  <div className="flex items-center space-x-2 text-slate-400">
                    <Loader className="w-4 h-4 animate-spin" />
                    <span>Gunny is thinking...</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-slate-700 bg-slate-900/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto p-4">
          <div className="flex items-end space-x-3">
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Describe the agent you want to build..."
                className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-xl focus:ring-2 focus:ring-unicorn-500 focus:border-transparent resize-none"
                rows={3}
                disabled={loading}
              />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                <span>Press Enter to send, Shift+Enter for new line</span>
                <span>{input.length} characters</span>
              </div>
            </div>

            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="btn-primary flex items-center space-x-2 px-6 py-3 h-12 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <Loader className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              <span>Send</span>
            </button>
          </div>
        </div>
      </div>
      </div>

      {/* Agent Preview Panel */}
      {showPreview && !showConfirmation && (
        <AgentPreview
          preview={agentPreview}
          onConfirm={handleCreateAgent}
          onReset={handleResetPreview}
        />
      )}

      {/* Toggle Preview Button */}
      {!showConfirmation && (
        <button
          onClick={() => setShowPreview(!showPreview)}
          className={`fixed right-4 top-24 z-50 btn-secondary p-2 transition-all ${
            showPreview ? 'translate-x-0' : 'translate-x-0'
          }`}
          title={showPreview ? 'Hide Preview' : 'Show Preview'}
          aria-label={showPreview ? 'Hide preview' : 'Show preview'}
          aria-pressed={showPreview}
        >
          {showPreview ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      )}

      {/* Deploy Confirmation Panel */}
      {showConfirmation && parsedAgentConfig && (
        <Modal
          onClose={handleContinueEditing}
          ariaLabel="Deploy agent confirmation"
          showClose={false}
          closeOnBackdrop={false}
          panelClassName="w-full max-w-lg mx-4 rounded-2xl border border-slate-700/50 bg-slate-900/95 backdrop-blur-xl shadow-2xl shadow-unicorn-500/10 overflow-hidden focus:outline-none"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-gradient-to-r from-unicorn-500/10 to-unicorn-500/10">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-unicorn-600 to-unicorn-500 flex items-center justify-center">
                  <Rocket className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Deploy Agent</h2>
                  <p className="text-xs text-slate-400">Review configuration before deploying</p>
                </div>
              </div>
              <button
                onClick={handleContinueEditing}
                aria-label="Close dialog"
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Config Details */}
            <div className="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">
              {/* Name & Display Name */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Agent Name</label>
                <p className="text-white font-medium text-lg">
                  {parsedAgentConfig.avatar && <span className="mr-2">{parsedAgentConfig.avatar}</span>}
                  {parsedAgentConfig.displayName || parsedAgentConfig.name || 'Unnamed Agent'}
                </p>
                {parsedAgentConfig.title && (
                  <p className="text-sm text-slate-400">{parsedAgentConfig.title}</p>
                )}
              </div>

              {/* Domain & Model */}
              <div className="grid grid-cols-2 gap-4">
                {parsedAgentConfig.domain && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Domain</label>
                    <div className="flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-unicorn-400" />
                      <span className="text-sm text-slate-200 capitalize">{parsedAgentConfig.domain}</span>
                    </div>
                  </div>
                )}
                {(parsedAgentConfig.model || agentPreview.model) && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Model</label>
                    <div className="flex items-center space-x-2">
                      <Cpu className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm text-slate-200">{(parsedAgentConfig.model || agentPreview.model || 'gpt-4-turbo').split('/').pop()}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Capabilities */}
              {parsedAgentConfig.capabilities && parsedAgentConfig.capabilities.length > 0 && (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Capabilities</label>
                  <div className="flex flex-wrap gap-1.5">
                    {parsedAgentConfig.capabilities.map((cap, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg bg-unicorn-500/10 text-unicorn-300 text-xs border border-unicorn-500/20"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tools */}
              {parsedAgentConfig.tools && parsedAgentConfig.tools.length > 0 && (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Tools</label>
                  <div className="space-y-1.5">
                    {parsedAgentConfig.tools.map((tool, idx) => (
                      <div key={idx} className="flex items-center space-x-2 px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700/30">
                        <Wrench className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                        <span className="text-sm text-slate-200">{typeof tool === 'string' ? tool : tool.name || tool}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Parameters */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Temperature</label>
                  <p className="text-sm text-slate-200">{parsedAgentConfig.temperature ?? agentPreview.temperature ?? 0.7}</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Max Tokens</label>
                  <p className="text-sm text-slate-200">{(parsedAgentConfig.maxTokens || agentPreview.maxTokens || 4096).toLocaleString()}</p>
                </div>
              </div>

              {/* System Prompt Preview */}
              {parsedAgentConfig.systemPrompt && (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">System Prompt</label>
                  <div className="px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700/30 max-h-24 overflow-y-auto">
                    <p className="text-xs text-slate-400 leading-relaxed">{parsedAgentConfig.systemPrompt}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="px-6 py-4 border-t border-slate-700/50 flex items-center justify-end space-x-3">
              <button
                onClick={handleContinueEditing}
                disabled={isDeploying}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-slate-300 bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:text-white disabled:opacity-50 transition-all"
              >
                Continue Editing
              </button>
              <button
                onClick={handleDeployAgent}
                disabled={isDeploying}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-unicorn-600 to-unicorn-500 hover:from-unicorn-500 hover:to-unicorn-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-unicorn-500/20"
              >
                {isDeploying ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    <span>Deploying...</span>
                  </>
                ) : (
                  <>
                    <Rocket className="w-4 h-4" />
                    <span>Deploy Agent</span>
                  </>
                )}
              </button>
            </div>
        </Modal>
      )}
    </div>
  );
};

export default AgentBuilderChat;
