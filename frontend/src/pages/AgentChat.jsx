import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Mic,
  MicOff,
  Video,
  VideoOff,
  Phone,
  PhoneOff,
  Settings,
  Users,
  Bot,
  Sparkles,
  Volume2,
  Paperclip
} from 'lucide-react';
import LiveKitRoom from '../components/LiveKitRoom';
import AgentSelector from '../components/AgentSelector';
import ChatMessage from '../components/ChatMessage';
import api from '../services/api';

const AgentChat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [isVideoEnabled, setIsVideoEnabled] = useState(false);
  const [isCallActive, setIsCallActive] = useState(false);
  const [showLiveKit, setShowLiveKit] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!inputMessage.trim() || !selectedAgent || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    const messageContent = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      // Prepare conversation context - combine persona and system prompt for the LLM
      // The persona IS part of the system prompt that shapes the agent's behavior
      const systemMessage = selectedAgent.systemPrompt ?
        `${selectedAgent.persona ? selectedAgent.persona + '\n\n' : ''}${selectedAgent.systemPrompt}` :
        `You are ${selectedAgent.name}, an AI agent with the following background: ${selectedAgent.persona || selectedAgent.description || 'a specialized assistant'}. Your capabilities include: ${selectedAgent.capabilities?.join(', ') || 'general assistance'}. Respond in character as this agent.`;

      const conversationMessages = [
        {
          role: 'system',
          content: systemMessage
        },
        // Include recent conversation history
        ...messages.slice(-5).map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        {
          role: 'user',
          content: messageContent
        }
      ];

      // Call real AI API
      const response = await api.chatCompletion(
        conversationMessages,
        selectedAgent.id,
        'openai/gpt-3.5-turbo' // You can make this configurable later
      );

      const agentMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        agent: selectedAgent,
        content: response.content,
        timestamp: new Date().toISOString(),
        model: response.model,
        provider: response.provider,
        usage: response.usage
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        agent: selectedAgent,
        content: `I apologize, but I'm having trouble connecting to my AI systems right now. Please check the provider settings or try again later. Error: ${error.message}`,
        timestamp: new Date().toISOString(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const startVoiceCall = () => {
    setIsCallActive(true);
    setIsVoiceEnabled(true);
    setShowLiveKit(true);
  };

  const endCall = () => {
    setIsCallActive(false);
    setIsVoiceEnabled(false);
    setIsVideoEnabled(false);
    setShowLiveKit(false);
  };

  return (
    <div className="flex h-screen">
      {/* Agent Sidebar */}
      <div className="w-80 glass border-r border-slate-800/50 p-4">
        <AgentSelector
          selectedAgent={selectedAgent}
          onSelectAgent={setSelectedAgent}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="glass border-b border-slate-800/50 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {selectedAgent ? (
                <>
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center">
                    <Bot className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="font-semibold">{selectedAgent.name}</h2>
                    <p className="text-sm text-slate-400">{selectedAgent.status}</p>
                  </div>
                </>
              ) : (
                <div>
                  <h2 className="font-semibold">Select an Agent</h2>
                  <p className="text-sm text-slate-400">Choose an agent to start chatting</p>
                </div>
              )}
            </div>

            {/* Voice/Video Controls */}
            <div className="flex items-center space-x-2">
              {!isCallActive ? (
                <button
                  onClick={startVoiceCall}
                  disabled={!selectedAgent}
                  className="p-2 rounded-lg glass-hover disabled:opacity-50"
                >
                  <Phone className="w-5 h-5" />
                </button>
              ) : (
                <>
                  <button
                    onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
                    className={`p-2 rounded-lg ${isVoiceEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'glass-hover'}`}
                  >
                    {isVoiceEnabled ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
                  </button>
                  <button
                    onClick={() => setIsVideoEnabled(!isVideoEnabled)}
                    className={`p-2 rounded-lg ${isVideoEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'glass-hover'}`}
                  >
                    {isVideoEnabled ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
                  </button>
                  <button
                    onClick={endCall}
                    className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30"
                  >
                    <PhoneOff className="w-5 h-5" />
                  </button>
                </>
              )}
              <button className="p-2 rounded-lg glass-hover">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* LiveKit Video/Audio */}
        {showLiveKit && (
          <LiveKitRoom
            isVideoEnabled={isVideoEnabled}
            isAudioEnabled={isVoiceEnabled}
            agentName={selectedAgent?.name}
          />
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-unicorn-500/20 to-cyan-500/20 flex items-center justify-center mb-4">
                <Sparkles className="w-10 h-10 text-unicorn-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Start a Conversation</h3>
              <p className="text-slate-400 max-w-md">
                Select an agent from the sidebar and start chatting. You can use text, voice, or video to communicate.
              </p>
            </div>
          ) : (
            <AnimatePresence>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
            </AnimatePresence>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="glass border-t border-slate-800/50 p-4">
          <div className="flex items-center space-x-3">
            <button className="p-2 rounded-lg glass-hover">
              <Paperclip className="w-5 h-5" />
            </button>
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder={selectedAgent ? `Message ${selectedAgent.name}...` : 'Select an agent to start chatting...'}
              disabled={!selectedAgent}
              className="flex-1 input"
            />
            <button
              onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
              className={`p-2 rounded-lg ${isVoiceEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'glass-hover'}`}
            >
              <Mic className="w-5 h-5" />
            </button>
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || !selectedAgent}
              className="btn-primary px-4 py-2 disabled:opacity-50"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentChat;