import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Bot,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Loader2,
  RotateCcw,
  Trash2,
  Cpu,
  Zap,
  Plus,
  Wrench,
  ChevronRight,
  Phone,
  AlertTriangle,
  RefreshCw,
  Info,
  Settings,
  X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { toast } from 'react-hot-toast';
import ToolCallCard, { getToolIcon } from '../components/ToolCallCard';
import VoiceCallButton from '../components/VoiceCallButton';
import VoiceCallModal from '../components/VoiceCallModal';
import ListSkeleton from '../components/skeletons/ListSkeleton';
import { apiJson } from '../services/http';
import api from '../services/api';

const AgentChat = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Conversation persistence state
  const [conversationId, setConversationId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState(null);
  const [loadingConversation, setLoadingConversation] = useState(false);

  // Voice call state
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [isInVoiceCall, setIsInVoiceCall] = useState(false);

  // UI state for new features
  const [showToolsPanel, setShowToolsPanel] = useState(false);
  const [isExecutingTool, setIsExecutingTool] = useState(false);
  const [currentToolName, setCurrentToolName] = useState(null);
  const [retryMessage, setRetryMessage] = useState(null);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const abortRef = useRef(null);

  // Load agents on mount
  useEffect(() => {
    loadAgents();
  }, []);

  // Check for conversation URL param on mount and when agents load
  useEffect(() => {
    const convId = searchParams.get('conversation');
    if (convId && agents.length > 0) {
      loadConversation(convId);
    }
  }, [searchParams, agents]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const loadAgents = async () => {
    try {
      setAgentsLoading(true);
      const data = await apiJson('/agents');
      setAgents(data.agents || []);
      // Pick the agent from ?agent=<id> if present, else the first active one —
      // but only when not loading a specific conversation. (Fixes click-to-chat
      // deep-links from Dashboard / AgentLibrary / the org chart, which pass
      // ?agent= but were previously ignored.)
      const convId = searchParams.get('conversation');
      if (!convId) {
        const agentId = searchParams.get('agent');
        const requested = agentId && (data.agents || []).find(a => a.id === agentId);
        const active = (data.agents || []).find(a => a.status === 'active');
        const pick = requested || active;
        if (pick && !selectedAgent) {
          setSelectedAgent(pick);
        }
      }
    } catch (err) {
      console.error('Failed to load agents:', err);
    } finally {
      setAgentsLoading(false);
    }
  };

  const loadConversation = async (convId) => {
    setLoadingConversation(true);
    try {
      const data = await apiJson(`/conversations/${convId}`);

      setConversationId(data.id);
      setConversationTitle(data.title);

      // Find and set the agent
      if (data.agent_id) {
        const agent = agents.find(a => a.id === data.agent_id);
        if (agent) {
          setSelectedAgent(agent);
        }
      }

      // Populate messages
      if (data.messages && data.messages.length > 0) {
        const loadedMessages = data.messages.map((msg, index) => ({
          id: msg.id || `loaded-${index}`,
          role: msg.role,
          content: msg.content,
          model: msg.model,
          tokens_used: msg.tokens_used,
          tool_calls: msg.tool_calls,
          tool_results: msg.tool_results,
          timestamp: msg.created_at,
          agent: msg.role === 'assistant' ? {
            id: data.agent_id,
            name: data.agent?.displayName || data.agent?.name || 'Agent',
            avatar: data.agent?.avatar || '🦄',
          } : undefined,
          isStreaming: false
        }));
        setMessages(loadedMessages);
      }

      toast.success('Conversation loaded');
    } catch (err) {
      console.error('Failed to load conversation:', err);
      toast.error('Failed to load conversation');
      // Clear the URL param if conversation can't be loaded
      setSearchParams({});
    } finally {
      setLoadingConversation(false);
    }
  };

  const createConversation = async (agentId, model) => {
    try {
      // No hardcoded user_id: the backend infers it from the authenticated
      // user (and defaults to "anonymous" otherwise).
      const data = await apiJson('/conversations', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: agentId,
          model: model
        })
      });
      setConversationId(data.id);
      // Update URL without full navigation
      setSearchParams({ conversation: data.id });
      return data.id;
    } catch (err) {
      console.error('Failed to create conversation:', err);
      // Non-blocking - chat still works without persistence
      return null;
    }
  };

  const saveMessage = async (convId, role, content, model, tokensUsed) => {
    if (!convId) return;
    try {
      await apiJson(`/conversations/${convId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          role,
          content,
          model: model || undefined,
          tokens_used: tokensUsed || undefined
        })
      });
    } catch (err) {
      console.error('Failed to save message:', err);
      // Non-blocking - don't interrupt the chat flow
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setConversationTitle(null);
    setSearchParams({});
    toast.success('New conversation started');
  };

  const sendMessage = useCallback(async () => {
    if (!input.trim() || !selectedAgent || isStreaming) return;

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString()
    };

    const history = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsThinking(true);
    setIsStreaming(true);
    setIsExecutingTool(false);
    setCurrentToolName(null);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Create conversation on first message if none exists
    let activeConvId = conversationId;
    if (!activeConvId && messages.length === 0) {
      activeConvId = await createConversation(selectedAgent.id, selectedAgent.model);
    }

    // Save user message
    saveMessage(activeConvId, 'user', userMsg.content);

    // Create placeholder for assistant message
    const assistantId = Date.now() + 1;
    const assistantMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      agent: {
        id: selectedAgent.id,
        name: selectedAgent.displayName || selectedAgent.name,
        avatar: selectedAgent.avatar || '🦄',
      },
      model: selectedAgent.model || 'unknown',
      timestamp: new Date().toISOString(),
      usage: null,
      isStreaming: true
    };

    try {
      const res = await api.streamAgentChat(selectedAgent.id, {
        message: userMsg.content,
        stream: true,
        history,
        model: selectedAgent.model,
        temperature: selectedAgent.temperature
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let gotFirstToken = false;
      let finalModel = selectedAgent.model;

      // Add the empty assistant message
      setMessages(prev => [...prev, assistantMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;

          try {
            const event = JSON.parse(payload);

            if (event.type === 'start') {
              // Stream started
              if (event.tools && event.tools.length > 0) {
                // Agent has tools — keep thinking indicator while tools execute
              } else {
                setIsThinking(false);
              }
            } else if (event.type === 'tool_call') {
              // Tool is being called - show it in the message
              setIsThinking(false);
              setIsExecutingTool(true);
              setCurrentToolName(event.name);
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [
                          ...(m.toolCalls || []),
                          { name: event.name, arguments: event.arguments }
                        ]
                      }
                    : m
                )
              );
            } else if (event.type === 'tool_result') {
              // Tool returned a result - update the matching tool call
              setIsExecutingTool(false);
              setCurrentToolName(null);
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m;
                  const updatedCalls = (m.toolCalls || []).map(tc =>
                    tc.name === event.name && tc.result === undefined
                      ? { ...tc, result: event.result, error: event.error }
                      : tc
                  );
                  return { ...m, toolCalls: updatedCalls };
                })
              );
            } else if (event.type === 'token') {
              if (!gotFirstToken) {
                gotFirstToken = true;
                setIsThinking(false);
                setIsExecutingTool(false);
              }
              accumulated += event.content;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: accumulated }
                    : m
                )
              );
            } else if (event.type === 'complete') {
              const finalContent = event.content || accumulated;
              finalModel = event.model || selectedAgent.model;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: finalContent,
                        model: finalModel,
                        toolCalls: event.toolCalls || m.toolCalls || [],
                        isStreaming: false
                      }
                    : m
                )
              );
              // Save assistant message to conversation
              saveMessage(activeConvId, 'assistant', finalContent, finalModel, event.usage?.total_tokens);
            } else if (event.type === 'error') {
              throw new Error(event.error);
            }
          } catch (parseErr) {
            // Skip unparseable lines
          }
        }
      }

      // Finalize
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );

      // If stream ended without a complete event, save accumulated content
      if (accumulated && !accumulated.includes('[DONE]')) {
        // Check if complete event already saved by verifying the message
        const msgs = messages;
        const assistantInMsgs = msgs.find(m => m.id === assistantId);
        if (!assistantInMsgs || assistantInMsgs.isStreaming) {
          saveMessage(activeConvId, 'assistant', accumulated, finalModel);
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
      setIsThinking(false);
      setIsExecutingTool(false);

      // If we already added an empty assistant message, update it with error
      setMessages(prev => {
        const hasAssistant = prev.some(m => m.id === assistantId);
        if (hasAssistant) {
          return prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `Sorry, I encountered an error: ${err.message}`,
                  isError: true,
                  isStreaming: false,
                  errorDetails: err.message
                }
              : m
          );
        }
        return [
          ...prev,
          {
            ...assistantMsg,
            content: `Sorry, I encountered an error: ${err.message}`,
            isError: true,
            isStreaming: false,
            errorDetails: err.message
          }
        ];
      });
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
      setIsExecutingTool(false);
    }
  }, [input, selectedAgent, isStreaming, messages, conversationId]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyToClipboard = async (text, id) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const clearChat = () => {
    setMessages([]);
    setConversationId(null);
    setConversationTitle(null);
    setSearchParams({});
    toast.success('Chat cleared');
  };

  // Retry the last failed message
  const retryLastMessage = useCallback(async (messageToRetry) => {
    if (!messageToRetry || isStreaming) return;

    // Find the user message before the failed message
    const messageIndex = messages.findIndex(m => m.id === messageToRetry.id);
    if (messageIndex <= 0) return;

    const userMessage = messages[messageIndex - 1];
    if (userMessage.role !== 'user') return;

    // Remove the failed message
    setMessages(prev => prev.filter(m => m.id !== messageToRetry.id));

    // Resend the user message
    setInput(userMessage.content);
    // Use setTimeout to allow state to update before sending
    setTimeout(() => {
      setInput('');
      // We need to manually trigger the send with the content
      sendMessageWithContent(userMessage.content);
    }, 0);
  }, [messages, isStreaming]);

  // Separate send function that takes content directly
  const sendMessageWithContent = useCallback(async (content) => {
    if (!content.trim() || !selectedAgent || isStreaming) return;

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString()
    };

    const history = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    setMessages(prev => [...prev, userMsg]);
    setIsThinking(true);
    setIsStreaming(true);
    setIsExecutingTool(false);
    setCurrentToolName(null);

    // Create conversation on first message if none exists
    let activeConvId = conversationId;
    if (!activeConvId && messages.length === 0) {
      activeConvId = await createConversation(selectedAgent.id, selectedAgent.model);
    }

    // Save user message
    saveMessage(activeConvId, 'user', userMsg.content);

    // Create placeholder for assistant message
    const assistantId = Date.now() + 1;
    const assistantMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      agent: {
        id: selectedAgent.id,
        name: selectedAgent.displayName || selectedAgent.name,
        avatar: selectedAgent.avatar || '🦄',
      },
      model: selectedAgent.model || 'unknown',
      timestamp: new Date().toISOString(),
      usage: null,
      isStreaming: true
    };

    try {
      const res = await api.streamAgentChat(selectedAgent.id, {
        message: userMsg.content,
        stream: true,
        history,
        model: selectedAgent.model,
        temperature: selectedAgent.temperature
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let gotFirstToken = false;
      let finalModel = selectedAgent.model;

      // Add the empty assistant message
      setMessages(prev => [...prev, assistantMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;

          try {
            const event = JSON.parse(payload);

            if (event.type === 'start') {
              if (event.tools && event.tools.length > 0) {
                // Agent has tools - keep thinking indicator while tools execute
              } else {
                setIsThinking(false);
              }
            } else if (event.type === 'tool_call') {
              setIsThinking(false);
              setIsExecutingTool(true);
              setCurrentToolName(event.name);
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [
                          ...(m.toolCalls || []),
                          { name: event.name, arguments: event.arguments }
                        ]
                      }
                    : m
                )
              );
            } else if (event.type === 'tool_result') {
              setIsExecutingTool(false);
              setCurrentToolName(null);
              setMessages(prev =>
                prev.map(m => {
                  if (m.id !== assistantId) return m;
                  const updatedCalls = (m.toolCalls || []).map(tc =>
                    tc.name === event.name && tc.result === undefined
                      ? { ...tc, result: event.result, error: event.error }
                      : tc
                  );
                  return { ...m, toolCalls: updatedCalls };
                })
              );
            } else if (event.type === 'token') {
              if (!gotFirstToken) {
                gotFirstToken = true;
                setIsThinking(false);
                setIsExecutingTool(false);
              }
              accumulated += event.content;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: accumulated }
                    : m
                )
              );
            } else if (event.type === 'complete') {
              const finalContent = event.content || accumulated;
              finalModel = event.model || selectedAgent.model;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: finalContent,
                        model: finalModel,
                        toolCalls: event.toolCalls || m.toolCalls || [],
                        isStreaming: false
                      }
                    : m
                )
              );
              saveMessage(activeConvId, 'assistant', finalContent, finalModel, event.usage?.total_tokens);
            } else if (event.type === 'error') {
              throw new Error(event.error);
            }
          } catch (parseErr) {
            // Skip unparseable lines
          }
        }
      }

      // Finalize
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );
    } catch (err) {
      console.error('Chat error:', err);
      setIsThinking(false);
      setIsExecutingTool(false);

      setMessages(prev => {
        const hasAssistant = prev.some(m => m.id === assistantId);
        if (hasAssistant) {
          return prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content: `Sorry, I encountered an error: ${err.message}`,
                  isError: true,
                  isStreaming: false,
                  errorDetails: err.message
                }
              : m
          );
        }
        return [
          ...prev,
          {
            ...assistantMsg,
            content: `Sorry, I encountered an error: ${err.message}`,
            isError: true,
            isStreaming: false,
            errorDetails: err.message
          }
        ];
      });
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
      setIsExecutingTool(false);
    }
  }, [selectedAgent, isStreaming, messages, conversationId]);

  // Group agents by domain for picker
  const agentsByDomain = agents.reduce((acc, agent) => {
    const domain = agent.domain || 'other';
    if (!acc[domain]) acc[domain] = [];
    acc[domain].push(agent);
    return acc;
  }, {});

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-slate-700/50 backdrop-blur-xl bg-slate-900/80 relative z-50">
        <div className="flex items-center justify-between px-6 py-3">
          {/* Left: Agent Selector + Conversation Title */}
          <div className="flex items-center space-x-4">
            {/* Agent Selector */}
            <div className="relative">
              <button
                onClick={() => setShowAgentPicker(!showAgentPicker)}
                className="flex items-center space-x-3 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-unicorn-500/40 transition-all"
                disabled={agentsLoading}
              >
                {agentsLoading ? (
                  <div className="flex items-center space-x-2 text-sm text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Loading agents...</span>
                  </div>
                ) : selectedAgent ? (
                  <>
                    <span className="text-2xl">{selectedAgent.avatar || '🦄'}</span>
                    <div className="text-left">
                      <p className="text-sm font-semibold text-white">
                        {selectedAgent.displayName || selectedAgent.name}
                      </p>
                      <p className="text-xs text-slate-400">{selectedAgent.domain}</p>
                    </div>
                  </>
                ) : (
                  <span className="text-sm text-slate-400">Select Agent...</span>
                )}
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>

              {/* Agent Picker Dropdown */}
              <AnimatePresence>
                {showAgentPicker && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.15 }}
                    className="absolute top-full left-0 mt-2 w-80 max-h-96 overflow-y-auto rounded-xl bg-slate-800 border border-slate-700/50 shadow-2xl shadow-black/50 z-50"
                  >
                    {agentsLoading ? (
                      <div className="p-4">
                        <ListSkeleton rows={4} />
                      </div>
                    ) : (
                      Object.entries(agentsByDomain).map(([domain, domainAgents]) => (
                        <div key={domain}>
                          <p className="px-4 pt-3 pb-1 text-[10px] font-semibold tracking-widest text-slate-400 uppercase">
                            {domain}
                          </p>
                          {domainAgents.map((agent) => (
                            <button
                              key={agent.id}
                              onClick={() => {
                                setSelectedAgent(agent);
                                setShowAgentPicker(false);
                              }}
                              className={`w-full flex items-center space-x-3 px-4 py-2.5 hover:bg-slate-700/50 transition-colors ${
                                selectedAgent?.id === agent.id ? 'bg-unicorn-500/10' : ''
                              }`}
                            >
                              <span className="text-xl">{agent.avatar || '🦄'}</span>
                              <div className="text-left flex-1 min-w-0">
                                <p className="text-sm font-medium text-white truncate">
                                  {agent.displayName || agent.name}
                                </p>
                                <p className="text-xs text-slate-400 truncate">{agent.title || agent.agentType}</p>
                              </div>
                              {selectedAgent?.id === agent.id && (
                                <div className="w-2 h-2 rounded-full bg-unicorn-500"></div>
                              )}
                            </button>
                          ))}
                        </div>
                      ))
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Conversation Title (shown when resuming) */}
            {conversationTitle && (
              <div className="hidden md:block px-3 py-1.5 rounded-lg bg-slate-800/40 border border-slate-700/30">
                <p className="text-xs text-slate-400 truncate max-w-[200px]" title={conversationTitle}>
                  {conversationTitle}
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center space-x-2">
            {selectedAgent && (
              <>
                <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/40">
                  <Cpu className="w-3 h-3 text-slate-400" />
                  <span className="text-xs text-slate-400">
                    {(selectedAgent.model || 'gpt-4o-mini').split('/').pop()}
                  </span>
                </div>
                {/* Tools toggle button */}
                {(selectedAgent.tools?.length > 0 || selectedAgent.agentTools?.length > 0) && (
                  <button
                    onClick={() => setShowToolsPanel(!showToolsPanel)}
                    className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-all ${
                      showToolsPanel
                        ? 'bg-unicorn-500/20 text-unicorn-400 border border-unicorn-500/40'
                        : 'bg-slate-800/60 text-slate-400 border border-slate-700/40 hover:text-white hover:border-unicorn-500/40'
                    }`}
                    title="View available tools"
                  >
                    <Wrench className="w-3 h-3" />
                    <span className="text-xs hidden sm:inline">
                      {selectedAgent.tools?.length || selectedAgent.agentTools?.length || 0} Tools
                    </span>
                  </button>
                )}
              </>
            )}
            <button
              onClick={startNewConversation}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 transition-all"
              title="New Conversation"
            >
              <Plus className="w-4 h-4" />
              <span className="text-xs hidden sm:inline">New Chat</span>
            </button>
            <button
              onClick={clearChat}
              disabled={messages.length === 0}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 disabled:opacity-30 transition-all"
              title="Clear chat"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            {/* Voice Call Button */}
            {selectedAgent && (
              <VoiceCallButton
                onClick={() => setShowVoiceModal(true)}
                isConnecting={false}
                isConnected={isInVoiceCall}
                disabled={!selectedAgent || isStreaming}
                size="md"
              />
            )}
          </div>
        </div>
      </div>

      {/* Tools Panel - Collapsible */}
      <AnimatePresence>
        {showToolsPanel && selectedAgent && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-b border-slate-700/50 bg-slate-900/60"
          >
            <div className="px-6 py-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <Wrench className="w-4 h-4 text-unicorn-400" />
                  <span className="text-sm font-medium text-white">Available Tools</span>
                  <span className="px-2 py-0.5 rounded-full bg-unicorn-500/20 text-unicorn-400 text-xs">
                    {selectedAgent.tools?.length || selectedAgent.agentTools?.length || 0}
                  </span>
                </div>
                <button
                  onClick={() => setShowToolsPanel(false)}
                  className="p-1 rounded hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {(selectedAgent.tools || selectedAgent.agentTools || []).map((tool, idx) => {
                  const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name || 'tool');
                  const ToolIcon = getToolIcon(toolName);
                  return (
                    <div
                      key={idx}
                      className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50"
                    >
                      <ToolIcon className="w-3.5 h-3.5 text-cyan-400" />
                      <span className="text-xs text-slate-300">{toolName}</span>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-slate-400">
                These tools will be automatically used when relevant to your questions.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Close dropdown on outside click */}
      {showAgentPicker && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowAgentPicker(false)}
        />
      )}

      {/* Loading Conversation Overlay */}
      {loadingConversation && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-10 h-10 text-unicorn-400 animate-spin mx-auto mb-3" />
            <p className="text-slate-400 text-sm">Loading conversation...</p>
          </div>
        </div>
      )}

      {/* Messages */}
      {!loadingConversation && (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-unicorn-500/20 to-unicorn-500/20 flex items-center justify-center mb-6">
                  {selectedAgent ? (
                    <span className="text-4xl">{selectedAgent.avatar || '🦄'}</span>
                  ) : (
                    <Sparkles className="w-10 h-10 text-unicorn-400" />
                  )}
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">
                  {selectedAgent ? `Chat with ${selectedAgent.displayName || selectedAgent.name}` : 'Start a Conversation'}
                </h2>
                <p className="text-slate-400 max-w-md mb-4">
                  {selectedAgent
                    ? selectedAgent.bio || selectedAgent.title || 'Ready to assist you with your questions.'
                    : 'Select an agent from the dropdown and ask anything.'}
                </p>

                {/* Show agent tools summary */}
                {selectedAgent && (selectedAgent.tools?.length > 0 || selectedAgent.agentTools?.length > 0) && (
                  <div className="mb-6 px-4 py-3 rounded-xl bg-slate-800/40 border border-slate-700/30 max-w-md">
                    <div className="flex items-center justify-center space-x-2 mb-2">
                      <Wrench className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm font-medium text-slate-300">
                        {selectedAgent.tools?.length || selectedAgent.agentTools?.length || 0} Tools Available
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 justify-center">
                      {(selectedAgent.tools || selectedAgent.agentTools || []).slice(0, 5).map((tool, idx) => {
                        const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name || 'tool');
                        return (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded bg-slate-700/50 text-xs text-slate-400"
                          >
                            {toolName}
                          </span>
                        );
                      })}
                      {(selectedAgent.tools?.length || selectedAgent.agentTools?.length || 0) > 5 && (
                        <span className="px-2 py-0.5 rounded bg-slate-700/50 text-xs text-slate-400">
                          +{(selectedAgent.tools?.length || selectedAgent.agentTools?.length || 0) - 5} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {selectedAgent && (
                  <div className="flex flex-wrap gap-2 justify-center">
                    {['Tell me about yourself', 'What can you help with?', 'Show me what you can do'].map(
                      (prompt) => (
                        <button
                          key={prompt}
                          onClick={() => {
                            setInput(prompt);
                            textareaRef.current?.focus();
                          }}
                          className="px-4 py-2 rounded-full bg-slate-800/60 border border-slate-700/50 text-sm text-slate-300 hover:border-unicorn-500/40 hover:text-white transition-all"
                        >
                          {prompt}
                        </button>
                      )
                    )}
                  </div>
                )}
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'user' ? (
                      /* User message */
                      <div className="max-w-[80%]">
                        <div className="px-5 py-3 rounded-2xl rounded-br-md bg-unicorn-600/80 text-white">
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      </div>
                    ) : (
                      /* Assistant message */
                      <div className="max-w-[85%] group">
                        <div className="flex items-start space-x-3">
                          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-slate-700 to-slate-600 flex items-center justify-center text-lg">
                            {msg.agent?.avatar || '🦄'}
                          </div>
                          <div className="flex-1 min-w-0">
                            {/* Agent name */}
                            <div className="flex items-center space-x-2 mb-1">
                              <span className="text-xs font-semibold text-unicorn-400">
                                {msg.agent?.name || 'Agent'}
                              </span>
                              {msg.model && (
                                <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded bg-slate-800/60 text-[10px] text-slate-400">
                                  <Zap className="w-2.5 h-2.5" />
                                  <span>{msg.model.split('/').pop()}</span>
                                </span>
                              )}
                            </div>

                            {/* Tool calls */}
                            {msg.toolCalls && msg.toolCalls.length > 0 && (
                              <div className="mb-2">
                                {msg.toolCalls.map((tc, i) => (
                                  <ToolCallCard key={`${msg.id}-tool-${i}`} toolCall={tc} />
                                ))}
                              </div>
                            )}

                            {/* Message content */}
                            <div
                              className={`prose prose-invert prose-sm max-w-none ${
                                msg.isError ? 'text-red-400' : 'text-slate-200'
                              }`}
                            >
                              {msg.content ? (
                                <ReactMarkdown
                                  components={{
                                    code({ node, inline, className, children, ...props }) {
                                      if (inline) {
                                        return (
                                          <code className="px-1.5 py-0.5 rounded bg-slate-800 text-unicorn-300 text-xs" {...props}>
                                            {children}
                                          </code>
                                        );
                                      }
                                      return (
                                        <div className="relative my-3">
                                          <pre className="rounded-lg bg-slate-900/80 border border-slate-700/50 p-4 overflow-x-auto text-xs">
                                            <code className={className} {...props}>
                                              {children}
                                            </code>
                                          </pre>
                                        </div>
                                      );
                                    },
                                    p({ children }) {
                                      return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
                                    },
                                    ul({ children }) {
                                      return <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>;
                                    },
                                    ol({ children }) {
                                      return <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>;
                                    }
                                  }}
                                >
                                  {msg.content}
                                </ReactMarkdown>
                              ) : msg.isStreaming ? (
                                <span className="inline-block w-1.5 h-4 bg-unicorn-400 animate-pulse rounded-sm"></span>
                              ) : null}
                            </div>

                            {/* Error message with retry */}
                            {msg.isError && !msg.isStreaming && (
                              <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                <div className="flex items-start space-x-2">
                                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                                  <div className="flex-1">
                                    <p className="text-xs text-red-400 font-medium mb-1">Something went wrong</p>
                                    <p className="text-xs text-red-300/70">{msg.errorDetails || 'An error occurred while processing your request.'}</p>
                                  </div>
                                </div>
                                <button
                                  onClick={() => retryLastMessage(msg)}
                                  disabled={isStreaming}
                                  className="mt-2 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-medium transition-colors disabled:opacity-50"
                                >
                                  <RefreshCw className="w-3 h-3" />
                                  <span>Retry</span>
                                </button>
                              </div>
                            )}

                            {/* Copy button - always visible for non-error messages */}
                            {msg.content && !msg.isStreaming && !msg.isError && (
                              <div className="mt-2 flex items-center space-x-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={() => copyToClipboard(msg.content, msg.id)}
                                  className="flex items-center space-x-1 text-xs text-slate-400 hover:text-slate-300 transition-colors"
                                >
                                  {copiedId === msg.id ? (
                                    <>
                                      <Check className="w-3 h-3" />
                                      <span>Copied</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="w-3 h-3" />
                                      <span>Copy response</span>
                                    </>
                                  )}
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </motion.div>
                ))}

                {/* Thinking / Tool Execution indicator */}
                {(isThinking || isExecutingTool) && (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="flex items-start space-x-3">
                      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-slate-700 to-slate-600 flex items-center justify-center text-lg">
                        {selectedAgent?.avatar || '🦄'}
                      </div>
                      <div className={`px-4 py-3 rounded-2xl rounded-bl-md border ${
                        isExecutingTool
                          ? 'bg-amber-500/10 border-amber-500/30'
                          : 'bg-slate-800/60 border-slate-700/40'
                      }`}>
                        <div className="flex items-center space-x-2">
                          {isExecutingTool ? (
                            <>
                              <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
                              <div className="flex flex-col">
                                <span className="text-xs text-amber-400 font-medium">
                                  Executing tool: {currentToolName}
                                </span>
                                <span className="text-[10px] text-amber-400/60">
                                  Running tool and processing results...
                                </span>
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="flex space-x-1">
                                <span className="w-2 h-2 bg-unicorn-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                <span className="w-2 h-2 bg-unicorn-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                <span className="w-2 h-2 bg-unicorn-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                              </div>
                              <span className="text-xs text-slate-400">
                                {selectedAgent?.displayName || 'Agent'} is thinking...
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 border-t border-slate-700/50 backdrop-blur-xl bg-slate-900/80">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex items-end space-x-3">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedAgent
                    ? `Message ${selectedAgent.displayName || selectedAgent.name}...`
                    : 'Select an agent to start...'
                }
                disabled={!selectedAgent || isStreaming || loadingConversation}
                rows={1}
                className="w-full resize-none rounded-xl bg-slate-800/60 border border-slate-700/50 px-4 py-3 pr-12 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-unicorn-500/50 focus:ring-1 focus:ring-unicorn-500/20 disabled:opacity-40 transition-all"
              />
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || !selectedAgent || isStreaming || loadingConversation}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-unicorn-600 hover:bg-unicorn-500 disabled:bg-slate-700 disabled:text-slate-400 text-white flex items-center justify-center transition-all disabled:opacity-40"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
          <p className="mt-2 text-[10px] text-slate-600 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Voice Call Modal */}
      <VoiceCallModal
        isOpen={showVoiceModal}
        onClose={() => setShowVoiceModal(false)}
        agent={selectedAgent}
        onCallStart={() => {
          setIsInVoiceCall(true);
          toast.success(`Voice call started with ${selectedAgent?.displayName || selectedAgent?.name}`);
        }}
        onCallEnd={() => {
          setIsInVoiceCall(false);
          toast.success('Voice call ended');
        }}
      />
    </div>
  );
};

export default AgentChat;
