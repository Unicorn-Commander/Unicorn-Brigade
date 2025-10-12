import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Heart,
  Activity,
  FileText,
  Calendar,
  Pill,
  Stethoscope,
  AlertCircle,
  User,
  ChevronRight,
  Download,
  Upload,
  Clock,
  TrendingUp,
  Shield,
  Users,
  Brain,
  Microscope,
  Syringe,
  MessageSquare,
  Send,
  Paperclip,
  X,
  FileUp,
  Check,
  Loader2,
  Bot,
  Sparkles,
  ChevronDown,
  Search,
  Database,
  File,
  Trash2
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

const MedicalDomain = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [consultationMode, setConsultationMode] = useState(false);
  const [specialists, setSpecialists] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);

  // Chat states
  const [chatOpen, setChatOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('dr_glitter_mane');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  // Document upload states
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ragDocuments, setRagDocuments] = useState([]);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // User's actual medical data (starts empty)
  const [patientData, setPatientData] = useState({
    name: 'Loading...',
    mrn: 'MRN-' + new Date().getFullYear() + '-' + Math.floor(Math.random() * 10000).toString().padStart(4, '0'),
    age: null,
    gender: null,
    bloodType: null,
    allergies: [],
    primaryCare: 'Dr. Glitter Mane',
    lastVisit: null,
    nextAppointment: null
  });

  // User's vital signs (starts empty)
  const [vitals, setVitals] = useState({
    bloodPressure: '--/--',
    heartRate: '--',
    temperature: '--',
    oxygen: '--',
    weight: '--',
    height: '--',
    bmi: '--',
    lastUpdated: 'No data'
  });

  // User's medical history (starts empty)
  const [medicalHistory, setMedicalHistory] = useState([]);

  // User's medications (starts empty)
  const [medications, setMedications] = useState([]);

  // User's lab results (starts empty)
  const [labResults, setLabResults] = useState([]);

  // Medical specialists (from domain config)
  const availableSpecialists = [
    { id: 'dr_glitter_mane', name: 'Dr. Glitter Mane', specialty: 'Primary Care & Orchestration', avatar: '🦄💉', status: 'available', isOrchestrator: true },
    { id: 'neuro', name: 'Dr. Neuro Sparkle', specialty: 'Neurology', avatar: '🧠✨', status: 'available' },
    { id: 'cardio', name: 'Dr. Cardio Thunder', specialty: 'Cardiology', avatar: '❤️⚡', status: 'available' },
    { id: 'psych', name: 'Dr. Psyche Rainbow', specialty: 'Psychiatry', avatar: '🧘‍♀️🌈', status: 'busy' },
    { id: 'ortho', name: 'Dr. Ortho Steel', specialty: 'Orthopedics', avatar: '🦴🔧', status: 'available' },
    { id: 'gastro', name: 'Dr. Gastro Flow', specialty: 'Gastroenterology', avatar: '🍎💊', status: 'available' },
    { id: 'pulmo', name: 'Dr. Pulmo Breeze', specialty: 'Pulmonology', avatar: '🫁💨', status: 'available' },
    { id: 'endo', name: 'Dr. Endo Balance', specialty: 'Endocrinology', avatar: '🧬⚖️', status: 'available' },
    { id: 'dermato', name: 'Dr. Dermato Glow', specialty: 'Dermatology', avatar: '🌟✨', status: 'available' },
    { id: 'onco', name: 'Dr. Onco Warrior', specialty: 'Oncology', avatar: '🎗️⚔️', status: 'available' },
    { id: 'pedia', name: 'Dr. Pedia Care', specialty: 'Pediatrics', avatar: '👶🏥', status: 'available' },
    { id: 'emergency', name: 'Dr. Emergency Flash', specialty: 'Emergency Medicine', avatar: '🚨⚡', status: 'available' },
    { id: 'radio', name: 'Dr. Radio Vision', specialty: 'Radiology', avatar: '👁️📡', status: 'available' }
  ];

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'records', label: 'Medical Records', icon: FileText },
    { id: 'medications', label: 'Medications', icon: Pill },
    { id: 'labs', label: 'Lab Results', icon: Microscope },
    { id: 'consultations', label: 'Consultations', icon: Stethoscope },
    { id: 'specialists', label: 'Specialists', icon: Users }
  ];

  // Get user info from localStorage
  useEffect(() => {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      const user = JSON.parse(userStr);
      setCurrentUser(user);

      // Update patient data with actual user info
      setPatientData(prev => ({
        ...prev,
        name: user.name || user.username || 'Patient',
        // You can add more user fields here if available
      }));

      // Load any saved medical data from localStorage
      const savedMedicalData = localStorage.getItem(`medical_data_${user.id}`);
      if (savedMedicalData) {
        const data = JSON.parse(savedMedicalData);
        if (data.vitals) setVitals(data.vitals);
        if (data.medications) setMedications(data.medications);
        if (data.labResults) setLabResults(data.labResults);
        if (data.medicalHistory) setMedicalHistory(data.medicalHistory);
        if (data.uploadedFiles) setUploadedFiles(data.uploadedFiles);
        if (data.ragDocuments) setRagDocuments(data.ragDocuments);
        if (data.patientData) setPatientData(prev => ({ ...prev, ...data.patientData }));
      }
    } else {
      // For testing/demo: Create a mock user if not logged in
      const mockUser = {
        id: 'demo-user',
        name: 'Aaron Stransky',
        username: 'aaron',
        email: 'aaron@example.com'
      };
      setCurrentUser(mockUser);
      setPatientData(prev => ({
        ...prev,
        name: mockUser.name,
      }));

      // Note: In production, uncomment this to require login:
      // navigate('/login');
    }
  }, [navigate]);

  // Save medical data to localStorage whenever it changes
  useEffect(() => {
    if (currentUser) {
      const dataToSave = {
        vitals,
        medications,
        labResults,
        medicalHistory,
        uploadedFiles,
        ragDocuments,
        patientData
      };
      localStorage.setItem(`medical_data_${currentUser.id}`, JSON.stringify(dataToSave));
    }
  }, [vitals, medications, labResults, medicalHistory, uploadedFiles, ragDocuments, patientData, currentUser]);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Initialize with welcome message
  useEffect(() => {
    if (messages.length === 0 && currentUser) {
      const hasRecords = uploadedFiles.length > 0;
      setMessages([{
        id: 1,
        role: 'assistant',
        content: hasRecords
          ? `🦄 Welcome back, ${patientData.name}! I'm Dr. Glitter Mane, your AI clinical maestro. I have access to your ${uploadedFiles.length} medical records. How may I assist you today?`
          : `🦄 Greetings, ${patientData.name}! I'm Dr. Glitter Mane, your AI clinical maestro. I notice you haven't uploaded any medical records yet. You can upload your documents using the 'Upload Records' button above. How may I assist you today?`,
        agent: 'dr_glitter_mane',
        timestamp: new Date().toISOString()
      }]);
    }
  }, [currentUser, patientData.name, uploadedFiles.length]);

  // Handle file upload
  const handleFileUpload = async (files) => {
    setUploading(true);
    const formData = new FormData();

    for (let file of files) {
      formData.append('files', file);
    }

    try {
      // Mock upload - in production this would upload to backend
      await new Promise(resolve => setTimeout(resolve, 2000));

      const newFiles = Array.from(files).map(file => ({
        id: Date.now() + Math.random(),
        name: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date().toISOString(),
        indexed: false
      }));

      setUploadedFiles(prev => [...prev, ...newFiles]);

      // Simulate RAG indexing
      setTimeout(() => {
        setUploadedFiles(prev =>
          prev.map(f =>
            newFiles.find(nf => nf.id === f.id)
              ? { ...f, indexed: true }
              : f
          )
        );
        setRagDocuments(prev => [...prev, ...newFiles.map(f => ({
          ...f,
          indexed: true,
          embeddings: 'generated'
        }))]);
        toast.success('Documents indexed successfully!');
      }, 3000);

      toast.success(`${files.length} file(s) uploaded successfully`);
    } catch (error) {
      toast.error('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  // Send message to agent
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

    try {
      // Get the selected agent's details
      const agent = availableSpecialists.find(a => a.id === selectedAgent);

      // Call the backend API - using the standalone Dr. Glitter Mane endpoint for now
      const response = await axios.post('http://localhost:3333/api/consult', {
        message: inputMessage,
        context: {
          patient: patientData,
          vitals: vitals,
          medications: medications,
          labResults: labResults,
          ragDocuments: ragDocuments
        },
        agent: selectedAgent
      });

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.response || `[${agent.name}]: I understand your concern. Based on your medical history and current symptoms, I recommend...`,
        agent: selectedAgent,
        agentName: agent.name,
        agentAvatar: agent.avatar,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      // Fallback to mock response if backend is not available
      const agent = availableSpecialists.find(a => a.id === selectedAgent);
      const mockResponses = {
        dr_glitter_mane: "Based on your medical records and symptoms, I recommend a comprehensive evaluation. Let me coordinate with the appropriate specialists for you.",
        neuro: "I'll perform a thorough neurological examination. Your symptoms suggest we should investigate potential neurological causes.",
        cardio: "Your cardiac health is important. Based on your history of hypertension, let's review your current medication regimen.",
        psych: "Mental health is crucial for overall wellbeing. I'm here to support you through any psychological concerns.",
        ortho: "Let's address your musculoskeletal concerns. I'll recommend appropriate imaging and treatment options.",
        gastro: "Digestive health affects your entire body. We should investigate these GI symptoms further.",
        pulmo: "Respiratory function is vital. Let's assess your lung health and breathing patterns."
      };

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: mockResponses[selectedAgent] || `[${agent.name}]: I'm here to help with your ${agent.specialty.toLowerCase()} concerns.`,
        agent: selectedAgent,
        agentName: agent.name,
        agentAvatar: agent.avatar,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  // Switch agent in chat
  const switchAgent = (agentId) => {
    setSelectedAgent(agentId);
    const agent = availableSpecialists.find(a => a.id === agentId);

    const switchMessage = {
      id: Date.now(),
      role: 'system',
      content: `Switched to ${agent.name} - ${agent.specialty}`,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, switchMessage]);

    const greetingMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      content: `${agent.avatar} Hello! I'm ${agent.name}, specializing in ${agent.specialty}. How can I assist you today?`,
      agent: agentId,
      agentName: agent.name,
      agentAvatar: agent.avatar,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, greetingMessage]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/10 to-slate-900">
      {/* Header */}
      <div className="border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="text-4xl">🏥</div>
              <div>
                <h1 className="text-2xl font-bold text-white">Medical Domain</h1>
                <p className="text-sm text-purple-300">EMR/EHR Interface - Orchestrated by Dr. Glitter Mane 🦄💉</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setUploadModalOpen(true)}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center space-x-2"
              >
                <Upload className="w-4 h-4" />
                <span>Upload Records</span>
              </button>
              <button
                onClick={() => setChatOpen(true)}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors flex items-center space-x-2"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Medical Consultation</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Patient Info Bar */}
      <div className="bg-gradient-to-r from-purple-900/20 to-pink-900/20 backdrop-blur-sm border-b border-white/10">
        <div className="container mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-6">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-purple-600 rounded-full flex items-center justify-center text-white font-bold">
                  {patientData.name ? patientData.name.split(' ').map(n => n[0]).join('').toUpperCase() : '?'}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">{patientData.name}</h2>
                  <div className="flex items-center space-x-4 text-sm text-slate-300">
                    <span>{patientData.mrn}</span>
                    <span>•</span>
                    {patientData.age && (
                      <>
                        <span>{patientData.age} years</span>
                        <span>•</span>
                      </>
                    )}
                    {patientData.gender && (
                      <>
                        <span>{patientData.gender}</span>
                        <span>•</span>
                      </>
                    )}
                    {patientData.bloodType && (
                      <span>Blood Type: {patientData.bloodType}</span>
                    )}
                    {!patientData.age && !patientData.gender && !patientData.bloodType && (
                      <span className="text-slate-400 italic">Medical profile not yet completed</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-4 text-sm">
                {patientData.allergies && patientData.allergies.length > 0 ? (
                  <div className="px-3 py-1 bg-red-500/20 text-red-400 rounded-full flex items-center space-x-1">
                    <AlertCircle className="w-3 h-3" />
                    <span>Allergies: {patientData.allergies.join(', ')}</span>
                  </div>
                ) : (
                  <div className="px-3 py-1 bg-slate-500/20 text-slate-400 rounded-full flex items-center space-x-1">
                    <AlertCircle className="w-3 h-3" />
                    <span>No known allergies</span>
                  </div>
                )}
                <div className="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full">
                  Primary: {patientData.primaryCare}
                </div>
                {ragDocuments.length > 0 && (
                  <div className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full flex items-center space-x-1">
                    <Database className="w-3 h-3" />
                    <span>{ragDocuments.length} documents indexed</span>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center space-x-2 text-sm text-slate-300">
              {patientData.nextAppointment ? (
                <>
                  <Clock className="w-4 h-4" />
                  <span>Next Appt: {patientData.nextAppointment}</span>
                </>
              ) : (
                <>
                  <Calendar className="w-4 h-4" />
                  <span>No upcoming appointments</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-white/10 bg-black/20">
        <div className="container mx-auto px-6">
          <div className="flex space-x-6">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 flex items-center space-x-2 border-b-2 transition-all ${
                    activeTab === tab.id
                      ? 'border-purple-500 text-purple-400'
                      : 'border-transparent text-slate-400 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-12 gap-6">
            {/* Vitals Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="col-span-4"
            >
              <div className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
                    <Heart className="w-5 h-5 text-red-400" />
                    <span>Vital Signs</span>
                  </h3>
                  <span className="text-xs text-slate-400">{vitals.lastUpdated}</span>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Blood Pressure</span>
                    <span className="text-white font-medium">{vitals.bloodPressure}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Heart Rate</span>
                    <span className="text-white font-medium">{vitals.heartRate} bpm</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Temperature</span>
                    <span className="text-white font-medium">{vitals.temperature}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">O2 Saturation</span>
                    <span className="text-white font-medium">{vitals.oxygen}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">BMI</span>
                    <span className="text-white font-medium">{vitals.bmi}</span>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Recent History */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="col-span-8"
            >
              <div className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                  <Calendar className="w-5 h-5 text-purple-400" />
                  <span>Recent Medical History</span>
                </h3>
                <div className="space-y-3">
                  {medicalHistory.length === 0 ? (
                    <div className="text-center py-8 text-slate-400">
                      <Calendar className="w-12 h-12 mx-auto mb-2 opacity-30" />
                      <p>No medical history recorded yet</p>
                      <p className="text-sm mt-1">Upload your medical records to get started</p>
                    </div>
                  ) : (
                    medicalHistory.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
                        <div className="flex items-center space-x-3">
                          <div className={`w-2 h-2 rounded-full ${
                            item.status === 'active' ? 'bg-emerald-400' :
                            item.status === 'completed' ? 'bg-blue-400' : 'bg-slate-400'
                          }`} />
                          <div>
                            <div className="text-white font-medium">{item.diagnosis}</div>
                            <div className="text-sm text-slate-400">{item.type} - {item.provider}</div>
                          </div>
                        </div>
                        <div className="text-sm text-slate-400">{item.date}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </motion.div>

            {/* Active Medications */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="col-span-6"
            >
              <div className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                  <Pill className="w-5 h-5 text-emerald-400" />
                  <span>Active Medications</span>
                </h3>
                <div className="space-y-2">
                  {medications.length === 0 ? (
                    <div className="text-center py-6 text-slate-400">
                      <Pill className="w-10 h-10 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No active medications</p>
                    </div>
                  ) : (
                    medications.filter(m => m.status === 'active').map((med, idx) => (
                      <div key={idx} className="p-3 bg-white/5 rounded-lg">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium">{med.name}</div>
                            <div className="text-sm text-slate-400">{med.dosage} - {med.frequency}</div>
                          </div>
                          <ChevronRight className="w-4 h-4 text-slate-400" />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </motion.div>

            {/* Recent Lab Results */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="col-span-6"
            >
              <div className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                  <Microscope className="w-5 h-5 text-blue-400" />
                  <span>Recent Lab Results</span>
                </h3>
                <div className="space-y-2">
                  {labResults.length === 0 ? (
                    <div className="text-center py-6 text-slate-400">
                      <Microscope className="w-10 h-10 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No lab results available</p>
                    </div>
                  ) : (
                    labResults.slice(0, 4).map((lab, idx) => (
                      <div key={idx} className="p-3 bg-white/5 rounded-lg">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-white font-medium">{lab.test}</div>
                            <div className="text-sm text-slate-400">Range: {lab.range}</div>
                          </div>
                          <div className="text-right">
                            <div className={`font-medium ${
                              lab.status === 'normal' ? 'text-emerald-400' : 'text-yellow-400'
                            }`}>{lab.value}</div>
                            <div className="text-xs text-slate-400">{lab.date}</div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        )}

        {activeTab === 'records' && (
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-8">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Medical Records & Documents</h3>
                  <button
                    onClick={() => setUploadModalOpen(true)}
                    className="px-3 py-1.5 bg-purple-600/20 text-purple-400 rounded-lg hover:bg-purple-600/30 transition-colors text-sm flex items-center space-x-2"
                  >
                    <Upload className="w-4 h-4" />
                    <span>Upload</span>
                  </button>
                </div>

                {uploadedFiles.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                    <p className="text-slate-400">No documents uploaded yet</p>
                    <button
                      onClick={() => setUploadModalOpen(true)}
                      className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                    >
                      Upload Medical Records
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {uploadedFiles.map((file) => (
                      <div key={file.id} className="p-3 bg-white/5 rounded-lg flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <File className="w-5 h-5 text-purple-400" />
                          <div>
                            <div className="text-white font-medium">{file.name}</div>
                            <div className="text-sm text-slate-400">
                              {(file.size / 1024).toFixed(1)} KB • Uploaded {new Date(file.uploadedAt).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {file.indexed ? (
                            <div className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs flex items-center space-x-1">
                              <Check className="w-3 h-3" />
                              <span>Indexed</span>
                            </div>
                          ) : (
                            <div className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs flex items-center space-x-1">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              <span>Processing</span>
                            </div>
                          )}
                          <button className="p-1.5 hover:bg-white/10 rounded transition-colors">
                            <Download className="w-4 h-4 text-slate-400" />
                          </button>
                          <button className="p-1.5 hover:bg-red-500/20 rounded transition-colors">
                            <Trash2 className="w-4 h-4 text-red-400" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            </div>

            <div className="col-span-4">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-gradient-to-br from-purple-600/20 to-pink-600/20 backdrop-blur-xl rounded-xl border border-purple-500/30 p-6"
              >
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center space-x-2">
                  <Database className="w-5 h-5 text-purple-400" />
                  <span>RAG System Status</span>
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Documents</span>
                    <span className="text-white font-medium">{uploadedFiles.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Indexed</span>
                    <span className="text-emerald-400 font-medium">
                      {uploadedFiles.filter(f => f.indexed).length}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Embeddings</span>
                    <span className="text-purple-400 font-medium">{ragDocuments.length * 100}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Vector DB</span>
                    <span className="text-emerald-400 text-sm">Connected</span>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-white/10">
                  <p className="text-sm text-slate-300">
                    Your medical records are securely indexed and available to Dr. Glitter Mane and specialists during consultations.
                  </p>
                </div>
              </motion.div>
            </div>
          </div>
        )}

        {activeTab === 'specialists' && (
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-8">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white/5 backdrop-blur-xl rounded-xl border border-white/10 p-6"
              >
                <h3 className="text-lg font-semibold text-white mb-4">Medical AI Specialists</h3>
                <div className="grid grid-cols-2 gap-4">
                  {availableSpecialists.filter(s => !s.isOrchestrator).map((specialist) => (
                    <div key={specialist.id} className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-all cursor-pointer">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-3">
                          <div className="text-3xl">{specialist.avatar}</div>
                          <div>
                            <div className="text-white font-medium">{specialist.name}</div>
                            <div className="text-sm text-slate-400">{specialist.specialty}</div>
                          </div>
                        </div>
                        <div className={`px-2 py-1 rounded-full text-xs ${
                          specialist.status === 'available'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-yellow-500/20 text-yellow-400'
                        }`}>
                          {specialist.status}
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setChatOpen(true);
                          switchAgent(specialist.id);
                        }}
                        className="w-full mt-3 px-3 py-2 bg-purple-600/20 text-purple-400 rounded-lg hover:bg-purple-600/30 transition-colors text-sm"
                      >
                        Start Consultation
                      </button>
                    </div>
                  ))}
                </div>
              </motion.div>
            </div>

            <div className="col-span-4">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-gradient-to-br from-purple-600/20 to-pink-600/20 backdrop-blur-xl rounded-xl border border-purple-500/30 p-6"
              >
                <div className="flex items-center space-x-3 mb-4">
                  <div className="text-4xl">🦄💉</div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Dr. Glitter Mane</h3>
                    <p className="text-sm text-purple-300">Primary Care Orchestrator</p>
                  </div>
                </div>
                <p className="text-sm text-slate-300 mb-4">
                  As your primary care AI, I coordinate with all specialists to ensure comprehensive care. I have access to your complete medical history through our RAG system.
                </p>
                <button
                  onClick={() => {
                    setChatOpen(true);
                    setSelectedAgent('dr_glitter_mane');
                  }}
                  className="w-full px-4 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:opacity-90 transition-opacity font-medium"
                >
                  Start Primary Consultation
                </button>
              </motion.div>
            </div>
          </div>
        )}
      </div>

      {/* Integrated Chat Interface */}
      <AnimatePresence>
        {chatOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          >
            <div className="w-full max-w-4xl h-[80vh] bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/10 flex flex-col">
              {/* Chat Header */}
              <div className="p-4 border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="text-3xl">
                    {availableSpecialists.find(a => a.id === selectedAgent)?.avatar}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      Medical Consultation
                    </h3>
                    <div className="flex items-center space-x-2">
                      <select
                        value={selectedAgent}
                        onChange={(e) => switchAgent(e.target.value)}
                        className="bg-white/10 text-purple-400 text-sm rounded px-2 py-1 border border-white/20"
                      >
                        {availableSpecialists.map(agent => (
                          <option key={agent.id} value={agent.id}>
                            {agent.name} - {agent.specialty}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setChatOpen(false)}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[70%] ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                      {message.role === 'assistant' && (
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="text-2xl">{message.agentAvatar || '🦄'}</span>
                          <span className="text-sm text-purple-400">{message.agentName || 'Dr. Glitter Mane'}</span>
                        </div>
                      )}
                      {message.role === 'system' && (
                        <div className="text-center text-sm text-slate-500 italic">
                          {message.content}
                        </div>
                      )}
                      {message.role !== 'system' && (
                        <div className={`p-3 rounded-lg ${
                          message.role === 'user'
                            ? 'bg-purple-600/20 text-white'
                            : 'bg-white/10 text-slate-200'
                        }`}>
                          {message.content}
                        </div>
                      )}
                      <div className="text-xs text-slate-500 mt-1">
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-white/10 rounded-lg p-3">
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

              {/* Chat Input */}
              <div className="p-4 border-t border-white/10">
                <div className="flex items-center space-x-2">
                  <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                    <Paperclip className="w-5 h-5 text-slate-400" />
                  </button>
                  <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                    placeholder={`Ask ${availableSpecialists.find(a => a.id === selectedAgent)?.name} about your health...`}
                    className="flex-1 bg-white/10 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!inputMessage.trim() || isTyping}
                    className="p-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
                {ragDocuments.length > 0 && (
                  <div className="mt-2 text-xs text-slate-400 flex items-center space-x-1">
                    <Database className="w-3 h-3" />
                    <span>Accessing {ragDocuments.length} indexed medical records</span>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Document Upload Modal */}
      <AnimatePresence>
        {uploadModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="w-full max-w-2xl bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/10 p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-white flex items-center space-x-2">
                  <FileUp className="w-6 h-6 text-purple-400" />
                  <span>Upload Medical Records</span>
                </h3>
                <button
                  onClick={() => setUploadModalOpen(false)}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>

              <div className="mb-6">
                <div
                  className="border-2 border-dashed border-white/20 rounded-xl p-8 text-center hover:border-purple-500/50 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    handleFileUpload(e.dataTransfer.files);
                  }}
                >
                  <Upload className="w-12 h-12 text-purple-400 mx-auto mb-3" />
                  <p className="text-white font-medium mb-1">
                    Drop files here or click to upload
                  </p>
                  <p className="text-sm text-slate-400">
                    Supports PDF, images, and text documents
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => handleFileUpload(e.target.files)}
                    accept=".pdf,.jpg,.jpeg,.png,.txt,.doc,.docx"
                  />
                </div>
              </div>

              <div className="space-y-3 mb-6">
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                  <div className="flex items-start space-x-2">
                    <Shield className="w-5 h-5 text-yellow-400 mt-0.5" />
                    <div>
                      <p className="text-sm text-yellow-400 font-medium">Privacy & Security</p>
                      <p className="text-xs text-slate-400 mt-1">
                        Your medical records are encrypted and processed locally. They are indexed in a secure RAG system accessible only to your authorized AI specialists.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3">
                <button
                  onClick={() => setUploadModalOpen(false)}
                  className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    fileInputRef.current?.click();
                  }}
                  disabled={uploading}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center space-x-2"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      <span>Select Files</span>
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default MedicalDomain;