import React, { useState, useEffect } from 'react';
import { TrendingUp, Package, Lock, Unlock, BarChart3, AlertCircle } from 'lucide-react';
import ToolGrid from '../components/tools/ToolGrid';

/**
 * Tools Browser Page
 * Browse and explore all available MCP tools with filtering
 */
const Tools = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tools, setTools] = useState([]);
  const [lockedTools, setLockedTools] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [upgradeSuggestion, setUpgradeSuggestion] = useState(null);

  // Fetch tools data
  useEffect(() => {
    fetchToolsData();
  }, []);

  const fetchToolsData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch available tools
      const availableRes = await fetch('/api/tools/available', {
        credentials: 'include'
      });

      if (!availableRes.ok) {
        throw new Error('Failed to fetch available tools');
      }

      const availableData = await availableRes.json();
      setTools(availableData.tools || []);

      // Fetch locked tools
      const lockedRes = await fetch('/api/tools/locked', {
        credentials: 'include'
      });

      if (lockedRes.ok) {
        const lockedData = await lockedRes.json();
        setLockedTools(lockedData.tools || []);
        setUpgradeSuggestion(lockedData.upgradeSuggestion);
      }

      // Fetch statistics
      const statsRes = await fetch('/api/tools/statistics', {
        credentials: 'include'
      });

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStatistics(statsData.statistics);
      }

      setLoading(false);
    } catch (err) {
      console.error('Error fetching tools:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  const handleUpgrade = (tool) => {
    // Navigate to upgrade page with suggested tier
    if (upgradeSuggestion && upgradeSuggestion.suggestedTier) {
      window.location.href = `/upgrade?tier=${upgradeSuggestion.suggestedTier}&from=tools&tool=${tool.key}`;
    } else {
      window.location.href = '/upgrade?from=tools';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading tools...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <div className="flex items-center gap-3 mb-3">
            <AlertCircle className="text-red-600" size={24} />
            <h3 className="text-lg font-semibold text-red-900">Error Loading Tools</h3>
          </div>
          <p className="text-red-700 mb-4">{error}</p>
          <button
            onClick={fetchToolsData}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Package size={32} className="text-purple-600" />
            <h1 className="text-3xl font-bold text-gray-900">MCP Tools Library</h1>
          </div>
          <p className="text-gray-600">
            Browse and explore all available tools for your agents. {statistics && `${statistics.percentageUnlocked}% unlocked.`}
          </p>
        </div>

        {/* Statistics Cards */}
        {statistics && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {/* Total Tools */}
            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-600">Total Tools</span>
                <Package size={20} className="text-gray-400" />
              </div>
              <p className="text-3xl font-bold text-gray-900">{statistics.totalTools}</p>
            </div>

            {/* Available Tools */}
            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-600">Available</span>
                <Unlock size={20} className="text-green-500" />
              </div>
              <p className="text-3xl font-bold text-green-600">{statistics.availableTools}</p>
              <p className="text-xs text-gray-500 mt-1">{statistics.percentageUnlocked}% unlocked</p>
            </div>

            {/* Locked Tools */}
            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-600">Locked</span>
                <Lock size={20} className="text-gray-400" />
              </div>
              <p className="text-3xl font-bold text-gray-900">{statistics.lockedTools}</p>
              <p className="text-xs text-gray-500 mt-1">Upgrade to unlock</p>
            </div>

            {/* Current Tier */}
            <div className="bg-gradient-to-br from-purple-600 to-pink-600 rounded-lg shadow-sm p-6 border border-purple-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-purple-100">Your Tier</span>
                <BarChart3 size={20} className="text-purple-200" />
              </div>
              <p className="text-3xl font-bold text-white capitalize">{statistics.tier}</p>
              <p className="text-xs text-purple-100 mt-1">{statistics.roles.join(', ')}</p>
            </div>
          </div>
        )}

        {/* Upgrade Banner */}
        {upgradeSuggestion && upgradeSuggestion.needsUpgrade && (
          <div className="bg-gradient-to-r from-purple-600 to-pink-600 rounded-lg shadow-lg p-6 mb-8 text-white">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp size={24} />
                  <h3 className="text-xl font-bold">Unlock More Tools</h3>
                </div>
                <p className="text-purple-100 mb-3">
                  {upgradeSuggestion.message}
                </p>
                {upgradeSuggestion.benefits && upgradeSuggestion.benefits.length > 0 && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-purple-100 mb-1">Including:</p>
                    <ul className="text-sm text-purple-100 space-y-0.5">
                      {upgradeSuggestion.benefits.map((tool, idx) => (
                        <li key={idx} className="flex items-center gap-1">
                          <span>•</span>
                          <span>{tool}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <button
                onClick={() => handleUpgrade({})}
                className="ml-4 px-6 py-3 bg-white text-purple-600 rounded-lg font-semibold hover:bg-purple-50 transition-colors shadow-lg flex-shrink-0"
              >
                Upgrade to {upgradeSuggestion.suggestedTier}
              </button>
            </div>
          </div>
        )}

        {/* Category Breakdown */}
        {statistics && statistics.categories && statistics.categories.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200 mb-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Tools by Category</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {statistics.categories.map(cat => (
                <div key={cat.key} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">{cat.icon}</span>
                    <h4 className="font-semibold text-gray-900">{cat.name}</h4>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">{cat.description}</p>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Available:</span>
                      <span className="font-medium text-green-600">{cat.availableTools}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Locked:</span>
                      <span className="font-medium text-gray-900">{cat.lockedTools}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                      <div
                        className="bg-gradient-to-r from-purple-600 to-pink-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${cat.percentage}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 text-center mt-1">
                      {cat.percentage}% unlocked
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tools Grid */}
        <ToolGrid
          tools={tools}
          lockedTools={lockedTools}
          onUpgrade={handleUpgrade}
        />
      </div>
    </div>
  );
};

export default Tools;
