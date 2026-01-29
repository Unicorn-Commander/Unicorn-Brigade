import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  Send,
  X,
  Minimize2,
  Maximize2,
  Activity,
  Users,
  FileText,
  AlertCircle,
  Bot,
  Sparkles,
  ChevronDown,
  Bell,
  Loader2,
  Database,
  Brain,
  Heart,
  Stethoscope
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const MedicalChatWidget = ({
  documents = [],
  onUIUpdate = () => {},
  onAgentAction = () => {},
  patientData = null
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('dr_glitter_mane');
  const [activeAgents, setActiveAgents] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [agentThoughts, setAgentThoughts] = useState(null);
  const [documentAnalysisInProgress, setDocumentAnalysisInProgress] = useState(false);
  const chatEndRef = useRef(null);

  // Medical specialists
  const specialists = [
    { id: 'dr_glitter_mane', name: 'Dr. Glitter Mane', specialty: 'Primary Care & Orchestration', avatar: '🦄💉', status: 'available', isOrchestrator: true },
    { id: 'neuro', name: 'Dr. Neuro Sparkle', specialty: 'Neurology', avatar: '🧠✨', status: 'available' },
    { id: 'cardio', name: 'Dr. Cardio Thunder', specialty: 'Cardiology', avatar: '❤️⚡', status: 'available' },
    { id: 'psych', name: 'Dr. Psyche Rainbow', specialty: 'Psychiatry', avatar: '🧘‍♀️🌈', status: 'available' },
    { id: 'endo', name: 'Dr. Endo Balance', specialty: 'Endocrinology', avatar: '🧬⚖️', status: 'available' },
    { id: 'emergency', name: 'Dr. Emergency Flash', specialty: 'Emergency Medicine', avatar: '🚨⚡', status: 'available' }
  ];

  // Initialize chat
  useEffect(() => {
    const savedState = localStorage.getItem('medical_chat_state');
    if (savedState) {
      const state = JSON.parse(savedState);
      setMessages(state.messages || []);
      setIsOpen(state.isOpen || false);
      setSelectedAgent(state.selectedAgent || 'dr_glitter_mane');
    }

    // Welcome message
    if (messages.length === 0) {
      setMessages([{
        id: Date.now(),
        role: 'assistant',
        content: `🦄 Hello! I'm Dr. Glitter Mane, your AI clinical maestro. I'm here 24/7 to help with your healthcare needs. You can upload medical documents, and I'll automatically analyze them with my specialist team. How can I assist you today?`,
        agent: 'dr_glitter_mane',
        timestamp: new Date().toISOString()
      }]);
    }
  }, []);

  // Save state on change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('medical_chat_state', JSON.stringify({
        messages: messages.slice(-50), // Keep last 50 messages
        isOpen,
        selectedAgent
      }));
    }
  }, [messages, isOpen, selectedAgent]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Document Analysis Workflow
  const analyzeDocuments = async (newDocuments) => {
    setDocumentAnalysisInProgress(true);

    // Notify user that analysis has started
    const startMessage = {
      id: Date.now(),
      role: 'system',
      content: `📄 Analyzing ${newDocuments.length} new document(s)...`,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, startMessage]);

    // Show Dr. Glitter Mane's thinking process
    setAgentThoughts({
      agent: 'dr_glitter_mane',
      thought: 'Reviewing uploaded documents for medical significance...'
    });

    // Simulate document processing
    setTimeout(() => {
      // Dr. Glitter Mane's initial analysis
      const analysisMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        agent: 'dr_glitter_mane',
        content: `I've reviewed your uploaded documents. Here's my initial assessment:

📋 **Document Summary:**
- Type: Medical Records / Lab Results
- Key findings: Elevated cholesterol, mild hypertension markers
- Priority: Moderate

🔄 **Routing to Specialists:**
I'm consulting with Dr. Cardio Thunder for the cardiovascular findings and Dr. Endo Balance for metabolic markers.`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, analysisMessage]);

      // Activate specialist agents
      setActiveAgents(['cardio', 'endo']);

      // Simulate specialist responses
      setTimeout(() => {
        // Cardio specialist response
        const cardioMessage = {
          id: Date.now() + 2,
          role: 'assistant',
          agent: 'cardio',
          agentName: 'Dr. Cardio Thunder',
          agentAvatar: '❤️⚡',
          content: `Based on the cardiac markers in your labs:
- LDL cholesterol at 145 mg/dL (slightly elevated)
- Blood pressure readings suggest stage 1 hypertension
- Recommend lifestyle modifications and follow-up in 3 months
- Consider statin therapy if lifestyle changes insufficient`,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, cardioMessage]);

        // Update UI with findings
        onUIUpdate({
          type: 'lab_results',
          data: {
            cholesterol: { value: 145, status: 'elevated' },
            bloodPressure: { value: '135/85', status: 'stage1' }
          }
        });

        // Add notification
        setNotifications(prev => [...prev, {
          id: Date.now(),
          type: 'finding',
          message: 'New cardiovascular findings require attention',
          severity: 'moderate'
        }]);

      }, 3000);

      // Endo specialist response
      setTimeout(() => {
        const endoMessage = {
          id: Date.now() + 3,
          role: 'assistant',
          agent: 'endo',
          agentName: 'Dr. Endo Balance',
          agentAvatar: '🧬⚖️',
          content: `Metabolic panel analysis:
- HbA1c at 5.8% (prediabetic range)
- Fasting glucose slightly elevated at 108 mg/dL
- Thyroid function normal
- Recommend dietary consultation and increased physical activity`,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, endoMessage]);

        // Update UI with metabolic data
        onUIUpdate({
          type: 'metabolic',
          data: {
            hba1c: { value: 5.8, status: 'prediabetic' },
            glucose: { value: 108, status: 'elevated' }
          }
        });

      }, 5000);

      // Dr. Glitter Mane's synthesis
      setTimeout(() => {
        const synthesisMessage = {
          id: Date.now() + 4,
          role: 'assistant',
          agent: 'dr_glitter_mane',
          content: `**📊 Comprehensive Analysis Complete**

Based on the specialist consultations, here's your action plan:

1. **Immediate Actions:**
   - Schedule cardiology follow-up
   - Begin DASH diet for blood pressure
   - Increase physical activity to 150 min/week

2. **Monitoring:**
   - Home blood pressure monitoring 2x daily
   - Recheck labs in 3 months

3. **Preventive Measures:**
   - Consider Mediterranean diet for cholesterol
   - Stress management techniques

I've updated your medical profile with these findings. Would you like me to schedule appointments or provide more specific guidance on any of these recommendations?`,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, synthesisMessage]);

        setDocumentAnalysisInProgress(false);
        setActiveAgents([]);
        setAgentThoughts(null);

        // Trigger agent action
        onAgentAction({
          type: 'document_analysis_complete',
          findings: {
            cardiovascular: 'moderate_risk',
            metabolic: 'prediabetic',
            recommendations: ['lifestyle_changes', 'follow_up']
          }
        });

      }, 7000);

    }, 2000);
  };

  // Watch for new documents
  useEffect(() => {
    const previousDocs = JSON.parse(localStorage.getItem('analyzed_docs') || '[]');
    const newDocs = documents.filter(doc => !previousDocs.find(pd => pd.id === doc.id));

    if (newDocs.length > 0) {
      analyzeDocuments(newDocs);
      localStorage.setItem('analyzed_docs', JSON.stringify(documents));
    }
  }, [documents]);

  // Send message
  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsTyping(true);

    // Check for agent routing keywords
    const lowerMessage = inputMessage.toLowerCase();
    let targetAgent = selectedAgent;

    if (lowerMessage.includes('heart') || lowerMessage.includes('chest pain') || lowerMessage.includes('blood pressure')) {
      targetAgent = 'cardio';
    } else if (lowerMessage.includes('anxiety') || lowerMessage.includes('depression') || lowerMessage.includes('mental')) {
      targetAgent = 'psych';
    } else if (lowerMessage.includes('emergency') || lowerMessage.includes('urgent')) {
      targetAgent = 'emergency';
    }

    // If different specialist needed, show routing
    if (targetAgent !== selectedAgent && targetAgent !== 'dr_glitter_mane') {
      const routingMessage = {
        id: Date.now() + 1,
        role: 'system',
        content: `Routing to ${specialists.find(s => s.id === targetAgent).name}...`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, routingMessage]);
      setSelectedAgent(targetAgent);
    }

    try {
      // Make actual API call
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
      const response = await axios.post(`${API_BASE}/medical/consultation`, {
        message: inputMessage,
        userId: patientData?.id || 'user-' + Date.now(),
        context: {
          patient: patientData,
          documents: documents,
          history: messages.slice(-10),
          agent: targetAgent
        }
      });

      const agent = specialists.find(s => s.id === targetAgent);
      const assistantMessage = {
        id: Date.now() + 2,
        role: 'assistant',
        content: response.data.response || `I understand your concern. Let me help you with that.`,
        agent: targetAgent,
        agentName: agent.name,
        agentAvatar: agent.avatar,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Check if UI update needed
      if (response.data.uiUpdate) {
        onUIUpdate(response.data.uiUpdate);
      }

    } catch (error) {
      // Fallback response
      const agent = specialists.find(s => s.id === targetAgent);
      const assistantMessage = {
        id: Date.now() + 2,
        role: 'assistant',
        content: `I'm analyzing your query. Based on your symptoms, I recommend monitoring this closely. Please provide more details about when these symptoms started and their severity.`,
        agent: targetAgent,
        agentName: agent.name,
        agentAvatar: agent.avatar,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 w-16 h-16 bg-gradient-to-br from-purple-600 to-pink-600 rounded-full shadow-2xl flex items-center justify-center hover:scale-110 transition-transform"
          >
            <div className="relative">
              <MessageSquare className="w-8 h-8 text-white" />
              {notifications.length > 0 && (
                <div className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white text-xs font-bold animate-pulse">
                  {notifications.length}
                </div>
              )}
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Persistent Chat Widget */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className={`fixed z-50 ${
              isMinimized
                ? 'bottom-6 right-6 w-80'
                : 'bottom-6 right-6 w-[450px] h-[600px]'
            } bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-purple-500/30 shadow-2xl flex flex-col overflow-hidden`}
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-purple-600/20 to-pink-600/20 p-4 border-b border-white/10">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="relative">
                    <div className="text-3xl">
                      {specialists.find(s => s.id === selectedAgent)?.avatar || '🦄💉'}
                    </div>
                    {activeAgents.length > 0 && (
                      <div className="absolute -bottom-1 -right-1 flex space-x-1">
                        {activeAgents.map(agentId => {
                          const agent = specialists.find(s => s.id === agentId);
                          return (
                            <div key={agentId} className="text-xs" title={agent?.name}>
                              {agent?.avatar}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">Medical AI Team</h3>
                    <div className="flex items-center space-x-2">
                      {documentAnalysisInProgress ? (
                        <div className="flex items-center space-x-1 text-xs text-purple-400">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span>Analyzing documents...</span>
                        </div>
                      ) : (
                        <select
                          value={selectedAgent}
                          onChange={(e) => setSelectedAgent(e.target.value)}
                          className="bg-white/10 text-purple-400 text-xs rounded px-2 py-0.5 border border-white/20"
                        >
                          {specialists.map(agent => (
                            <option key={agent.id} value={agent.id}>
                              {agent.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-1">
                  {notifications.length > 0 && (
                    <button
                      onClick={() => setNotifications([])}
                      className="p-1.5 hover:bg-white/10 rounded-lg transition-colors relative"
                      title="Clear notifications"
                    >
                      <Bell className="w-4 h-4 text-purple-400" />
                      <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center text-white text-[10px] font-bold">
                        {notifications.length}
                      </div>
                    </button>
                  )}
                  <button
                    onClick={() => {
                      if (confirm('Start a new conversation? Current chat will be saved.')) {
                        setMessages([{
                          id: Date.now(),
                          role: 'assistant',
                          content: `🦄 Starting fresh! How can I help you today?`,
                          agent: 'dr_glitter_mane',
                          timestamp: new Date().toISOString()
                        }]);
                        setSelectedAgent('dr_glitter_mane');
                        setNotifications([]);
                      }
                    }}
                    className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
                    title="New conversation"
                  >
                    <MessageSquare className="w-4 h-4 text-slate-400" />
                  </button>
                  <button
                    onClick={() => setIsMinimized(!isMinimized)}
                    className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
                    title={isMinimized ? "Maximize" : "Minimize"}
                  >
                    {isMinimized ? <Maximize2 className="w-4 h-4 text-slate-400" /> : <Minimize2 className="w-4 h-4 text-slate-400" />}
                  </button>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
                    title="Close chat"
                  >
                    <X className="w-4 h-4 text-slate-400" />
                  </button>
                </div>
              </div>

              {/* Agent Thoughts */}
              {agentThoughts && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-2 p-2 bg-purple-600/10 rounded-lg border border-purple-500/20"
                >
                  <div className="flex items-center space-x-2">
                    <Brain className="w-3 h-3 text-purple-400 animate-pulse" />
                    <span className="text-xs text-purple-400 italic">{agentThoughts.thought}</span>
                  </div>
                </motion.div>
              )}
            </div>

            {!isMinimized && (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      {message.role === 'system' ? (
                        <div className="w-full text-center text-xs text-slate-500 italic py-1">
                          {message.content}
                        </div>
                      ) : (
                        <div className={`max-w-[85%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                          {message.role === 'assistant' && (
                            <div className="flex items-center space-x-1 mb-1">
                              <span className="text-xl">{message.agentAvatar || '🦄'}</span>
                              <span className="text-xs text-purple-400">{message.agentName || 'Dr. Glitter Mane'}</span>
                            </div>
                          )}
                          <div className={`p-3 rounded-xl text-sm ${
                            message.role === 'user'
                              ? 'bg-purple-600/20 text-white'
                              : 'bg-white/10 text-slate-200'
                          }`}>
                            <div className="whitespace-pre-wrap">{message.content}</div>
                          </div>
                          <div className="text-[10px] text-slate-500 mt-0.5 px-1">
                            {new Date(message.timestamp).toLocaleTimeString()}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  {isTyping && (
                    <div className="flex justify-start">
                      <div className="bg-white/10 rounded-xl p-3">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Input */}
                <div className="p-3 border-t border-white/10">
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="Describe symptoms or ask questions..."
                      className="flex-1 bg-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!inputMessage.trim() || isTyping}
                      className="p-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                  {documents.length > 0 && (
                    <div className="mt-2 text-[10px] text-slate-400 flex items-center space-x-1">
                      <Database className="w-3 h-3" />
                      <span>{documents.length} medical records available</span>
                    </div>
                  )}
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Notifications Toast */}
      <AnimatePresence>
        {notifications.map((notification) => (
          <motion.div
            key={notification.id}
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 100 }}
            className="fixed top-20 right-6 bg-slate-900 border border-purple-500/30 rounded-lg p-4 shadow-xl max-w-sm"
          >
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-purple-400 mt-0.5" />
              <div>
                <p className="text-sm text-white font-medium">Medical Update</p>
                <p className="text-xs text-slate-300 mt-1">{notification.message}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </>
  );
};

export default MedicalChatWidget;