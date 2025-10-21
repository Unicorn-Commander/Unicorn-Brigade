import React, { useState, useMemo } from 'react';
import { Search, Filter, Lock, Unlock } from 'lucide-react';
import ToolCard from './ToolCard';

/**
 * ToolGrid Component
 * Grid display of tools with search and filtering
 */
const ToolGrid = ({ tools = [], lockedTools = [], onUpgrade, onSelectTool, selectedTools = [] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [showLocked, setShowLocked] = useState(false);

  // Combine available and locked tools
  const allTools = useMemo(() => {
    if (showLocked) {
      return [...tools, ...lockedTools];
    }
    return tools;
  }, [tools, lockedTools, showLocked]);

  // Filter tools by search and category
  const filteredTools = useMemo(() => {
    return allTools.filter(tool => {
      const matchesSearch = tool.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           tool.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = selectedCategory === 'all' || tool.category === selectedCategory;

      return matchesSearch && matchesCategory;
    });
  }, [allTools, searchTerm, selectedCategory]);

  // Get unique categories
  const categories = useMemo(() => {
    const cats = new Set(allTools.map(t => t.category));
    return ['all', ...Array.from(cats)];
  }, [allTools]);

  // Count tools by category
  const categoryCounts = useMemo(() => {
    const counts = { all: allTools.length };
    allTools.forEach(tool => {
      counts[tool.category] = (counts[tool.category] || 0) + 1;
    });
    return counts;
  }, [allTools]);

  // Category display names and icons
  const categoryInfo = {
    all: { name: 'All Tools', icon: '🔧', color: 'gray' },
    common: { name: 'Common', icon: '🔧', color: 'green' },
    advanced: { name: 'Advanced', icon: '⚡', color: 'blue' },
    premium: { name: 'Premium', icon: '💎', color: 'purple' },
    admin: { name: 'Admin', icon: '👑', color: 'red' }
  };

  const getCategoryColorClass = (cat, type = 'bg') => {
    const colors = {
      gray: type === 'bg' ? 'bg-gray-100 hover:bg-gray-200 text-gray-800' : 'bg-gray-600',
      green: type === 'bg' ? 'bg-green-100 hover:bg-green-200 text-green-800' : 'bg-green-600',
      blue: type === 'bg' ? 'bg-blue-100 hover:bg-blue-200 text-blue-800' : 'bg-blue-600',
      purple: type === 'bg' ? 'bg-purple-100 hover:bg-purple-200 text-purple-800' : 'bg-purple-600',
      red: type === 'bg' ? 'bg-red-100 hover:bg-red-200 text-red-800' : 'bg-red-600'
    };
    return colors[categoryInfo[cat]?.color || 'gray'];
  };

  return (
    <div className="space-y-6">
      {/* Header with Stats */}
      <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Tools Library</h2>
            <p className="text-sm text-gray-600 mt-1">
              {tools.length} available • {lockedTools.length} locked
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLocked(!showLocked)}
              className={`
                flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors
                ${showLocked
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {showLocked ? <Unlock size={18} /> : <Lock size={18} />}
              {showLocked ? 'Hide Locked' : 'Show Locked'}
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Search tools by name or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Category Tabs */}
      <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
        <div className="flex items-center gap-2 mb-2">
          <Filter size={18} className="text-gray-600" />
          <span className="font-medium text-gray-700">Filter by Category:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`
                px-4 py-2 rounded-lg font-medium transition-all
                ${selectedCategory === cat
                  ? `${getCategoryColorClass(cat, 'badge')} text-white shadow-md`
                  : getCategoryColorClass(cat, 'bg')
                }
              `}
            >
              <span className="mr-2">{categoryInfo[cat]?.icon}</span>
              {categoryInfo[cat]?.name}
              <span className={`
                ml-2 px-2 py-0.5 rounded-full text-xs font-bold
                ${selectedCategory === cat ? 'bg-white/20' : 'bg-black/10'}
              `}>
                {categoryCounts[cat] || 0}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Tools Grid */}
      {filteredTools.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredTools.map(tool => (
            <ToolCard
              key={tool.key}
              tool={tool}
              selected={selectedTools.includes(tool.key)}
              onUpgrade={onUpgrade}
              onSelect={onSelectTool}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm p-12 border border-gray-200 text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">No tools found</h3>
          <p className="text-gray-600">
            {searchTerm
              ? `No tools match "${searchTerm}". Try a different search term.`
              : 'No tools available in this category.'
            }
          </p>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
            >
              Clear Search
            </button>
          )}
        </div>
      )}

      {/* Results Summary */}
      {filteredTools.length > 0 && (
        <div className="text-center text-sm text-gray-600">
          Showing {filteredTools.length} of {allTools.length} tools
          {searchTerm && ` matching "${searchTerm}"`}
          {selectedCategory !== 'all' && ` in ${categoryInfo[selectedCategory]?.name}`}
        </div>
      )}
    </div>
  );
};

export default ToolGrid;
