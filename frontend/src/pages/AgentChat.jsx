import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Bot,
  Sparkles,
  ChevronDown,
  Copy,
  Check,
  Loader2,
  RotateCcw,
  Trash2,
  Cpu,
  Zap,
  Plus,
  Wrench,
  ChevronRight
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { toast } from 'react-hot-toast';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

// Tool call card — shows tool name, args, and collapsible result
const ToolCallCard = ({ toolCall }) => {
  const [expanded, setExpanded] = useState(false);
  const hasResult = toolCall.result !== undefined || toolCall.error;
  const isError = !!toolCall.error;

  return (
    <div className="my-2 rounded-lg border border-slate-700/50 bg-slate-800/40 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center space-x-2 px-3 py-2 text-left hover:bg-slate-700/30 transition-colors"
      >
        <Wrench className={`w-3.5 h-3.5 flex-shrink-0 ${isError ? 'text-red-400' : hasResult ? 'text-green-400' : 'text-yellow-400 animate-pulse'}`} />
        <span className="text-xs font-medium text-slate-300">{toolCall.name}</span>
        {hasResult && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${isError ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
            {isError ? 'error' : 'done'}
          </span>
        )}
        {!hasResult && (
          <Loader2 className="w-3 h-3 text-yellow-400 animate-spin" />
        )}
        <div className="flex-1" />
        <ChevronRight className={`w-3.5 h-3.5 text-slate-500 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded && (
        <div className="px-3 pb-2 space-y-1.5 border-t border-slate-700/30">
          <div className="pt-1.5">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Arguments</p>
            <pre className="text-[11px] text-slate-400 bg-slate-900/50 rounded p-1.5 mt-0.5 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {hasResult && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">{isError ? 'Error' : 'Result'}</p>
              <pre className={`text-[11px] ${isError ? 'text-red-400' : 'text-slate-400'} bg-slate-900/50 rounded p-1.5 mt-0.5 overflow-x-auto max-h-40`}>
                {isError ? toolCall.error : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AgentChat = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Conversation persistence state
  const [conversationId, setConversationId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState(null);
  const [loadingConversation, setLoadingConversation] = useState(false);

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
      const res = await fetch(`${API_BASE}/agents`);
      const data = await res.json();
      setAgents(data.agents || []);
      // Auto-select first active agent only if no conversation is being loaded
      const convId = searchParams.get('conversation');
      if (!convId) {
        const active = (data.agents || []).find(a => a.status === 'active');
        if (active && !selectedAgent) {
          setSelectedAgent(active);
        }
      }
    } catch (err) {
      console.error('Failed to load agents:', err);
    }
  };

  const loadConversation = async (convId) => {
    setLoadingConversation(true);
    try {
      const res = await fetch(`${API_BASE}/conversations/${convId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

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
      const res = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: agentId,
          user_id: 'anonymous',
          model: model
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
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
      await fetch(`${API_BASE}/conversations/${convId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      const res = await fetch(`${API_BASE}/agents/${selectedAgent.id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg.content,
          stream: true,
          history,
          model: selectedAgent.model,
          temperature: selectedAgent.temperature
        })
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
              // Tool is being called — show it in the message
              setIsThinking(false);
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
              // Tool returned a result — update the matching tool call
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
                  isStreaming: false
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
            isStreaming: false
          }
        ];
      });
    } finally {
      setIsStreaming(false);
      setIsThinking(false);
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
      <div className="flex-shrink-0 border-b border-slate-700/50 backdrop-blur-xl bg-slate-900/80">
        <div className="flex items-center justify-between px-6 py-3">
          {/* Left: Agent Selector + Conversation Title */}
          <div className="flex items-center space-x-4">
            {/* Agent Selector */}
            <div className="relative">
              <button
                onClick={() => setShowAgentPicker(!showAgentPicker)}
                className="flex items-center space-x-3 px-4 py-2 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-purple-500/40 transition-all"
              >
                {selectedAgent ? (
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
                    {Object.entries(agentsByDomain).map(([domain, domainAgents]) => (
                      <div key={domain}>
                        <p className="px-4 pt-3 pb-1 text-[10px] font-semibold tracking-widest text-slate-500 uppercase">
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
                              selectedAgent?.id === agent.id ? 'bg-purple-500/10' : ''
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
                              <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                            )}
                          </button>
                        ))}
                      </div>
                    ))}
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
              <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/40">
                <Cpu className="w-3 h-3 text-slate-400" />
                <span className="text-xs text-slate-400">
                  {(selectedAgent.model || 'gpt-4o-mini').split('/').pop()}
                </span>
              </div>
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
          </div>
        </div>
      </div>

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
            <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-3" />
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
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center mb-6">
                  <Sparkles className="w-10 h-10 text-purple-400" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">Start a Conversation</h2>
                <p className="text-slate-400 max-w-md mb-6">
                  Select an agent from the dropdown and ask anything. Your messages are sent to real AI models through Ops-Center.
                </p>
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
                          className="px-4 py-2 rounded-full bg-slate-800/60 border border-slate-700/50 text-sm text-slate-300 hover:border-purple-500/40 hover:text-white transition-all"
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
                        <div className="px-5 py-3 rounded-2xl rounded-br-md bg-purple-600/80 text-white">
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
                              <span className="text-xs font-semibold text-purple-400">
                                {msg.agent?.name || 'Agent'}
                              </span>
                              {msg.model && (
                                <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded bg-slate-800/60 text-[10px] text-slate-500">
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
                                          <code className="px-1.5 py-0.5 rounded bg-slate-800 text-purple-300 text-xs" {...props}>
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
                                <span className="inline-block w-1.5 h-4 bg-purple-400 animate-pulse rounded-sm"></span>
                              ) : null}
                            </div>

                            {/* Copy button */}
                            {msg.content && !msg.isStreaming && (
                              <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                  onClick={() => copyToClipboard(msg.content, msg.id)}
                                  className="flex items-center space-x-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                                >
                                  {copiedId === msg.id ? (
                                    <>
                                      <Check className="w-3 h-3" />
                                      <span>Copied</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="w-3 h-3" />
                                      <span>Copy</span>
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

                {/* Thinking indicator */}
                {isThinking && (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="flex items-start space-x-3">
                      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-slate-700 to-slate-600 flex items-center justify-center text-lg">
                        {selectedAgent?.avatar || '🦄'}
                      </div>
                      <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-slate-800/60 border border-slate-700/40">
                        <div className="flex items-center space-x-2">
                          <div className="flex space-x-1">
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                            <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                          </div>
                          <span className="text-xs text-slate-500">
                            {selectedAgent?.displayName || 'Agent'} is thinking...
                          </span>
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
                className="w-full resize-none rounded-xl bg-slate-800/60 border border-slate-700/50 px-4 py-3 pr-12 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 disabled:opacity-40 transition-all"
              />
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || !selectedAgent || isStreaming || loadingConversation}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white flex items-center justify-center transition-all disabled:opacity-40"
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
    </div>
  );
};

export default AgentChat;
