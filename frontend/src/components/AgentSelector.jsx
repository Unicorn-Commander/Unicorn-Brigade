import { useState, useEffect } from 'react';
import { Search, Bot, Shield, Users, User } from 'lucide-react';

const AgentSelector = ({ selectedAgent, onSelectAgent }) => {
  const [agents, setAgents] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    // Mock agents - will be replaced with API call
    const mockAgents = [
      { id: 1, name: 'The Colonel', type: 'orchestrator', status: 'online', domain: 'command' },
      { id: 2, name: 'Detective Sherlock', type: 'individual', status: 'online', domain: 'investigation' },
      { id: 3, name: 'Financial Analyst', type: 'individual', status: 'busy', domain: 'financial' },
      { id: 4, name: 'Legal Eagle', type: 'team_lead', status: 'offline', domain: 'legal' },
      { id: 5, name: 'Data Scientist', type: 'individual', status: 'online', domain: 'technology' },
      { id: 6, name: 'Security Analyst', type: 'individual', status: 'online', domain: 'security' },
    ];
    setAgents(mockAgents);
  }, []);

  const getIcon = (type) => {
    switch(type) {
      case 'orchestrator':
        return Shield;
      case 'team_lead':
        return Users;
      default:
        return User;
    }
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'online':
        return 'bg-emerald-500';
      case 'busy':
        return 'bg-amber-500';
      default:
        return 'bg-slate-500';
    }
  };

  const filteredAgents = agents.filter(agent =>
    agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    agent.domain.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col">
      <h3 className="text-lg font-semibold mb-4">Available Agents</h3>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search agents..."
          className="w-full pl-10 input"
        />
      </div>

      {/* Agent List */}
      <div className="flex-1 space-y-2 overflow-y-auto scrollbar-thin">
        {filteredAgents.map((agent) => {
          const Icon = getIcon(agent.type);
          const isSelected = selectedAgent?.id === agent.id;

          return (
            <button
              key={agent.id}
              onClick={() => onSelectAgent(agent)}
              className={`w-full p-3 rounded-lg transition-all duration-200 text-left ${
                isSelected
                  ? 'bg-unicorn-500/20 border border-unicorn-500/30'
                  : 'glass-hover'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className="relative">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-500/20 to-cyan-500/20 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-unicorn-400" />
                  </div>
                  <div className={`absolute bottom-0 right-0 w-3 h-3 rounded-full ${getStatusColor(agent.status)} border-2 border-slate-900`}></div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{agent.name}</p>
                  <p className="text-xs text-slate-500">{agent.domain}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AgentSelector;