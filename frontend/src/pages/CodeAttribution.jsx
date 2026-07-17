import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileCode,
  Search,
  Filter,
  Calendar,
  Download,
  RefreshCw,
  User,
  BarChart3,
  Clock,
  Loader2,
  X,
  ChevronDown
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import traceService from '../services/traceService';
import CodeAttributionCard from '../components/CodeAttributionCard';
import AttributionTimeline from '../components/AttributionTimeline';
import FileAttributionViewer from '../components/FileAttributionViewer';
import AttributionStats from '../components/AttributionStats';
import Breadcrumbs from '../components/Breadcrumbs';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import ListSkeleton from '../components/skeletons/ListSkeleton';

// Map the UI date-range picker to the trace API's `days` lookback param
// (1-90). "All time" is capped at the API maximum of 90 days.
const DATE_RANGE_DAYS = { '24h': 1, '7d': 7, '30d': 30, all: 90 };

const CodeAttribution = () => {
  const [activeTab, setActiveTab] = useState('by-file');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Data
  const [attributions, setAttributions] = useState([]);
  const [fileTree, setFileTree] = useState([]);
  const [agentList, setAgentList] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);

  // Filters
  const [dateRange, setDateRange] = useState('7d'); // 24h, 7d, 30d, all
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showFilters, setShowFilters] = useState(false);

  // Viewer
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerData, setViewerData] = useState(null);

  // Auto-refresh for recent activity
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Load initial data (agent filter is applied client-side, no refetch needed)
  useEffect(() => {
    loadData();
  }, [dateRange]);

  // Auto-refresh recent activity every 10 seconds
  useEffect(() => {
    if (activeTab === 'recent' && autoRefresh) {
      const interval = setInterval(() => {
        loadRecentActivity();
      }, 10000);

      return () => clearInterval(interval);
    }
  }, [activeTab, autoRefresh]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Date range filter — the trace API filters by a `days` lookback
      const filters = { days: DATE_RANGE_DAYS[dateRange] || 7 };

      // Load all data in parallel (stats endpoint takes no filters)
      const [attributionsData, fileTreeData, statsData] = await Promise.all([
        traceService.getAttributions(filters),
        traceService.getFileTree(),
        traceService.getStatistics(),
        new Promise(resolve => setTimeout(resolve, 300)),
      ]);

      setAttributions(attributionsData || []);
      setFileTree(fileTreeData || []);
      setStatistics(statsData || null);

      // Extract unique agents from attributions (deduped by id)
      const agents = [...new Map(
        (attributionsData || []).map(a => [
          a.agent_id,
          { id: a.agent_id, name: a.agent_name || a.agent_id }
        ])
      ).values()].filter(a => a.id);
      setAgentList(agents);

    } catch (error) {
      console.error('Failed to load attribution data:', error);
      toast.error('Failed to load attribution data');
    } finally {
      setLoading(false);
    }
  };

  const loadRecentActivity = async () => {
    setRefreshing(true);
    try {
      // getRecentActivity takes DAYS, not hours ("Last 7 days" → days=7)
      const data = await traceService.getRecentActivity(DATE_RANGE_DAYS[dateRange] || 7);
      setRecentActivity(data || []);
    } catch (error) {
      console.error('Failed to load recent activity:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      loadData();
      return;
    }

    setLoading(true);
    try {
      const results = await traceService.searchAttributions(searchQuery, {
        days: DATE_RANGE_DAYS[dateRange] || 7,
      });
      setAttributions(results || []);
    } catch (error) {
      console.error('Search failed:', error);
      toast.error('Search failed');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, dateRange]);

  const handleExport = async () => {
    try {
      toast.loading('Generating report...');

      const filters = {};
      if (dateRange !== 'all') {
        const now = new Date();
        const start = new Date();

        if (dateRange === '24h') {
          start.setHours(now.getHours() - 24);
        } else if (dateRange === '7d') {
          start.setDate(now.getDate() - 7);
        } else if (dateRange === '30d') {
          start.setDate(now.getDate() - 30);
        }

        filters.startDate = start.toISOString();
        filters.endDate = now.toISOString();
      }

      if (selectedAgent) {
        filters.agentId = selectedAgent;
      }

      const blob = await traceService.exportReport(filters, 'json');

      // Download the file
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attribution-report-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.dismiss();
      notify.success('Report downloaded');
    } catch (error) {
      toast.dismiss();
      toast.error('Export failed');
      console.error('Export failed:', error);
    }
  };

  const handleFileClick = async (filePath) => {
    try {
      toast.loading('Loading file...');
      const fileData = await traceService.getFileAttributions(filePath);

      setViewerData({
        filePath,
        attributions: fileData.attributions || [],
        code: fileData.code || ''
      });
      setViewerOpen(true);
      toast.dismiss();
    } catch (error) {
      toast.dismiss();
      toast.error('Failed to load file');
      console.error('Failed to load file:', error);
    }
  };

  const handleAgentClick = async (agentId) => {
    setSelectedAgent(agentId === selectedAgent ? null : agentId);
  };

  // Filter attributions based on selected agent + search
  const filteredAttributions = attributions.filter(attr => {
    if (selectedAgent && attr.agent_id !== selectedAgent) return false;
    if (!searchQuery.trim()) return true;

    const query = searchQuery.toLowerCase();
    return (
      attr.file_path?.toLowerCase().includes(query) ||
      attr.agent_name?.toLowerCase().includes(query) ||
      attr.agent_id?.toLowerCase().includes(query) ||
      attr.model?.toLowerCase().includes(query) ||
      attr.prompt?.toLowerCase().includes(query)
    );
  });

  // Group files for "By File" view
  const groupedFiles = filteredAttributions.reduce((acc, attr) => {
    if (!acc[attr.file_path]) {
      acc[attr.file_path] = [];
    }
    acc[attr.file_path].push(attr);
    return acc;
  }, {});

  // Group by agent for "By Agent" view
  const groupedAgents = filteredAttributions.reduce((acc, attr) => {
    const agentKey = attr.agent_id;
    if (!acc[agentKey]) {
      acc[agentKey] = {
        id: attr.agent_id,
        name: attr.agent_name || attr.agent_id,
        attributions: []
      };
    }
    acc[agentKey].attributions.push(attr);
    return acc;
  }, {});

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FileCode className="w-8 h-8 text-unicorn-400" />
              <h1 className="text-3xl font-bold bg-gradient-to-r from-unicorn-500 to-unicorn-400 bg-clip-text text-transparent">
                Code Attribution
              </h1>
            </div>
            <p className="text-slate-400">
              Track which AI agents generated which code for audit trails and compliance
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExport}
              className="btn btn-secondary flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export Report
            </button>
            <button
              onClick={() => loadData()}
              className="btn btn-secondary"
              disabled={loading}
              aria-label="Refresh attributions"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="card">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search Bar */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search files, agents, models, or prompts..."
                className="input pl-10 w-full"
              />
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery('');
                    loadData();
                  }}
                  aria-label="Clear search"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Date Range Filter */}
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-400" />
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="input w-40"
              >
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="all">All time</option>
              </select>
            </div>

            {/* Agent Filter */}
            {agentList.length > 0 && (
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-slate-400" />
                <select
                  value={selectedAgent || ''}
                  onChange={(e) => setSelectedAgent(e.target.value || null)}
                  className="input w-48"
                >
                  <option value="">All agents</option>
                  {agentList.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800">
          {[
            { id: 'by-file', label: 'By File', icon: FileCode },
            { id: 'by-agent', label: 'By Agent', icon: User },
            { id: 'recent', label: 'Recent Activity', icon: Clock },
            { id: 'statistics', label: 'Statistics', icon: BarChart3 }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id === 'recent') loadRecentActivity();
              }}
              className={`
                flex items-center gap-2 px-4 py-3 border-b-2 transition-all
                ${activeTab === tab.id
                  ? 'border-unicorn-500 text-unicorn-400'
                  : 'border-transparent text-slate-400 hover:text-slate-300'
                }
              `}
            >
              <tab.icon className="w-4 h-4" />
              <span className="font-medium">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-6"
            >
              {activeTab === 'recent' ? <ListSkeleton rows={6} /> : <TableSkeleton rows={6} columns={4} />}
            </motion.div>
          ) : (
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.2 }}
            >
              {/* By File View */}
              {activeTab === 'by-file' && (
                <div className="space-y-4">
                  {Object.keys(groupedFiles).length > 0 ? (
                    Object.entries(groupedFiles).map(([filePath, attrs]) => (
                      <div key={filePath} className="card">
                        <button
                          onClick={() => handleFileClick(filePath)}
                          className="w-full text-left"
                        >
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <FileCode className="w-5 h-5 text-unicorn-400 flex-shrink-0" />
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium text-slate-200 truncate">
                                  {filePath.split('/').pop()}
                                </p>
                                <p className="text-xs text-slate-400 truncate">
                                  {filePath}
                                </p>
                              </div>
                            </div>
                            <span className="badge badge-purple ml-4">
                              {attrs.length} {attrs.length === 1 ? 'attribution' : 'attributions'}
                            </span>
                          </div>
                        </button>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
                          {attrs.slice(0, 3).map((attr, index) => (
                            <CodeAttributionCard
                              key={attr.id || index}
                              attribution={attr}
                              compact
                            />
                          ))}
                        </div>

                        {attrs.length > 3 && (
                          <button
                            onClick={() => handleFileClick(filePath)}
                            className="w-full mt-3 py-2 text-xs text-unicorn-400 hover:text-unicorn-300 transition-colors"
                          >
                            View all {attrs.length} attributions →
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="card text-center py-12">
                      <FileCode className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                      <p className="text-slate-400">No attributed files found</p>
                    </div>
                  )}
                </div>
              )}

              {/* By Agent View */}
              {activeTab === 'by-agent' && (
                <div className="space-y-4">
                  {Object.keys(groupedAgents).length > 0 ? (
                    Object.entries(groupedAgents).map(([agentId, agentData]) => {
                      const totalLines = agentData.attributions.reduce(
                        (sum, attr) => sum + (attr.lines_count || 0), 0
                      );
                      const uniqueFiles = new Set(agentData.attributions.map(a => a.file_path)).size;

                      return (
                        <div key={agentId} className="card">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-unicorn-500/20 rounded-lg">
                                <User className="w-5 h-5 text-unicorn-400" />
                              </div>
                              <div>
                                <h3 className="text-lg font-semibold text-slate-200">
                                  {agentData.name}
                                </h3>
                                <p className="text-xs text-slate-400">{agentId}</p>
                              </div>
                            </div>

                            <div className="flex items-center gap-4 text-sm">
                              <div className="text-right">
                                <p className="text-slate-400">Lines</p>
                                <p className="font-medium text-unicorn-400">
                                  {totalLines.toLocaleString()}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-slate-400">Files</p>
                                <p className="font-medium text-unicorn-400">
                                  {uniqueFiles}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {agentData.attributions.slice(0, 4).map((attr, index) => (
                              <CodeAttributionCard
                                key={attr.id || index}
                                attribution={attr}
                                onClick={() => handleFileClick(attr.file_path)}
                                compact
                              />
                            ))}
                          </div>

                          {agentData.attributions.length > 4 && (
                            <p className="text-xs text-slate-400 mt-3 text-center">
                              + {agentData.attributions.length - 4} more attributions
                            </p>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="card text-center py-12">
                      <User className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                      <p className="text-slate-400">No agents found</p>
                    </div>
                  )}
                </div>
              )}

              {/* Recent Activity View */}
              {activeTab === 'recent' && (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <Clock className="w-5 h-5 text-unicorn-400" />
                      <h2 className="text-lg font-semibold text-slate-200">
                        Recent Activity
                      </h2>
                      {refreshing && (
                        <Loader2 className="w-4 h-4 text-unicorn-400 animate-spin" />
                      )}
                    </div>

                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={autoRefresh}
                        onChange={(e) => setAutoRefresh(e.target.checked)}
                        className="rounded border-slate-700 bg-slate-800 text-unicorn-500 focus:ring-unicorn-500"
                      />
                      <span className="text-slate-400">Auto-refresh (10s)</span>
                    </label>
                  </div>

                  <AttributionTimeline
                    attributions={recentActivity.length > 0 ? recentActivity : filteredAttributions}
                    onItemClick={(attr) => handleFileClick(attr.file_path)}
                  />
                </div>
              )}

              {/* Statistics View */}
              {activeTab === 'statistics' && (
                <AttributionStats statistics={statistics} />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* File Attribution Viewer Modal */}
      <AnimatePresence>
        {viewerOpen && viewerData && (
          <FileAttributionViewer
            filePath={viewerData.filePath}
            attributions={viewerData.attributions}
            code={viewerData.code}
            onClose={() => {
              setViewerOpen(false);
              setViewerData(null);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default CodeAttribution;
