import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Activity,
  Zap,
  Shield,
  MessageSquare,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock
} from 'lucide-react';
import AgentCard from '../components/AgentCard';
import ActivityFeed from '../components/ActivityFeed';
import SystemMetrics from '../components/SystemMetrics';

const CommandCenter = () => {
  const [agents, setAgents] = useState([]);
  const [activities, setActivities] = useState([]);
  const [metrics, setMetrics] = useState({
    totalAgents: 42,
    activeAgents: 18,
    tasksCompleted: 1247,
    successRate: 94.8
  });

  useEffect(() => {
    // Simulate real-time data
    const mockAgents = [
      { id: 1, name: 'The Colonel', type: 'orchestrator', status: 'active', domain: 'command' },
      { id: 2, name: 'Dr. Glitter Mane', type: 'orchestrator', status: 'active', domain: 'medical', avatar: '🦄💉' },
      { id: 3, name: 'Detective Sherlock', type: 'individual', status: 'busy', domain: 'investigation' },
      { id: 4, name: 'Financial Analyst', type: 'individual', status: 'active', domain: 'financial' },
      { id: 5, name: 'Legal Eagle', type: 'team_lead', status: 'inactive', domain: 'legal' },
      { id: 6, name: 'Dr. Neuro Sparkle', type: 'specialist', status: 'active', domain: 'medical', avatar: '🧠✨' },
      { id: 7, name: 'Dr. Cardio Thunder', type: 'specialist', status: 'active', domain: 'medical', avatar: '❤️⚡' },
    ];

    const mockActivities = [
      { id: 1, type: 'medical', message: 'Dr. Glitter Mane completed patient consultation', time: '1 min ago', status: 'success' },
      { id: 2, type: 'referral', message: 'Patient referred to Dr. Cardio Thunder for cardiac evaluation', time: '3 min ago', status: 'info' },
      { id: 3, type: 'task', message: 'Investigation completed by Detective Sherlock', time: '7 min ago', status: 'success' },
      { id: 4, type: 'orchestration', message: 'New mission started: Financial Analysis', time: '10 min ago', status: 'info' },
      { id: 5, type: 'medical', message: 'Medical records processed and indexed in RAG system', time: '15 min ago', status: 'success' },
      { id: 6, type: 'alert', message: 'Emergency protocol activated - chest pain symptoms detected', time: '20 min ago', status: 'warning' },
    ];

    setAgents(mockAgents);
    setActivities(mockActivities);
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-between items-center"
      >
        <div>
          <h1 className="text-3xl font-bold text-gradient">Command Center</h1>
          <p className="text-slate-400 mt-1">Monitor and control your AI agent fleet</p>
        </div>
        <div className="flex space-x-3">
          <button className="btn-secondary flex items-center space-x-2">
            <MessageSquare className="w-5 h-5" />
            <span>New Chat</span>
          </button>
          <button className="btn-primary flex items-center space-x-2">
            <Zap className="w-5 h-5" />
            <span>Deploy Mission</span>
          </button>
        </div>
      </motion.div>

      {/* Metrics Cards */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
      >
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Total Agents</p>
              <p className="text-2xl font-bold mt-1">{metrics.totalAgents}</p>
            </div>
            <Users className="w-8 h-8 text-unicorn-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Active Now</p>
              <p className="text-2xl font-bold mt-1 text-emerald-400">{metrics.activeAgents}</p>
            </div>
            <Activity className="w-8 h-8 text-emerald-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Tasks Completed</p>
              <p className="text-2xl font-bold mt-1">{metrics.tasksCompleted.toLocaleString()}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-cyan-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Success Rate</p>
              <p className="text-2xl font-bold mt-1">{metrics.successRate}%</p>
            </div>
            <TrendingUp className="w-8 h-8 text-amber-500" />
          </div>
        </div>
      </motion.div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent List */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-2 space-y-4"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Active Agents</h2>
            <button className="text-sm text-unicorn-400 hover:text-unicorn-300">
              View All →
            </button>
          </div>

          <div className="space-y-3">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </motion.div>

        {/* Activity Feed */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          <ActivityFeed activities={activities} />
        </motion.div>
      </div>

      {/* System Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <SystemMetrics />
      </motion.div>
    </div>
  );
};

export default CommandCenter;