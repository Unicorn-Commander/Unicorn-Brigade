import React, { useState, useMemo } from 'react';
import { Check, Lock, Info, Search, X } from 'lucide-react';

/**
 * ToolSelector Component
 * Multi-select tool picker with permission checking for agent builder
 */
const ToolSelector = ({
  availableTools = [],
  lockedTools = [],
  selectedTools = [],
  onSelectionChange,
  onUpgrade,
  maxSelection = null
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedCategory, setExpandedCategory] = useState('common');

  // Group tools by category
  const toolsByCategory = useMemo(() => {
    const grouped = {
      common: { available: [], locked: [] },
      advanced: { available: [], locked: [] },
      premium: { available: [], locked: [] },
      admin: { available: [], locked: [] }
    };

    availableTools.forEach(tool => {
      if (grouped[tool.category]) {
        grouped[tool.category].available.push(tool);
      }
    });

    lockedTools.forEach(tool => {
      if (grouped[tool.category]) {
        grouped[tool.category].locked.push(tool);
      }
    });

    return grouped;
  }, [availableTools, lockedTools]);

  // Filter tools by search
  const filteredCategories = useMemo(() => {
    if (!searchTerm) return toolsByCategory;

    const filtered = {};
    Object.entries(toolsByCategory).forEach(([category, tools]) => {
      const matchingAvailable = tools.available.filter(t =>
        t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.description.toLowerCase().includes(searchTerm.toLowerCase())
      );
      const matchingLocked = tools.locked.filter(t =>
        t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.description.toLowerCase().includes(searchTerm.toLowerCase())
      );

      if (matchingAvailable.length > 0 || matchingLocked.length > 0) {
        filtered[category] = {
          available: matchingAvailable,
          locked: matchingLocked
        };
      }
    });

    return filtered;
  }, [toolsByCategory, searchTerm]);

  // Handle tool selection toggle
  const toggleTool = (toolKey) => {
    const isSelected = selectedTools.includes(toolKey);

    if (isSelected) {
      // Remove from selection
      onSelectionChange(selectedTools.filter(t => t !== toolKey));
    } else {
      // Add to selection (if not at max)
      if (maxSelection && selectedTools.length >= maxSelection) {
        alert(`Maximum ${maxSelection} tools can be selected`);
        return;
      }
      onSelectionChange([...selectedTools, toolKey]);
    }
  };

  // Clear all selections
  const clearSelection = () => {
    onSelectionChange([]);
  };

  // Category info
  const categoryInfo = {
    common: { name: 'Common Tools', icon: '🔧', color: 'green' },
    advanced: { name: 'Advanced Tools', icon: '⚡', color: 'blue' },
    premium: { name: 'Premium Tools', icon: '💎', color: 'purple' },
    admin: { name: 'Admin Tools', icon: '👑', color: 'red' }
  };

  const getCategoryColor = (cat) => {
    const colors = {
      green: 'bg-green-100 text-green-800 border-green-300',
      blue: 'bg-blue-100 text-blue-800 border-blue-300',
      purple: 'bg-purple-100 text-purple-800 border-purple-300',
      red: 'bg-red-100 text-red-800 border-red-300'
    };
    return colors[categoryInfo[cat]?.color] || colors.green;
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Select Tools</h3>
          <p className="text-sm text-gray-600">
            {selectedTools.length} selected
            {maxSelection && ` (max ${maxSelection})`}
          </p>
        </div>
        {selectedTools.length > 0 && (
          <button
            onClick={clearSelection}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <X size={16} />
            Clear All
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
        <input
          type="text"
          placeholder="Search tools..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm"
        />
      </div>

      {/* Selected Tools Summary */}
      {selectedTools.length > 0 && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
          <p className="text-sm font-medium text-purple-900 mb-2">Selected Tools:</p>
          <div className="flex flex-wrap gap-2">
            {selectedTools.map(toolKey => {
              const tool = availableTools.find(t => t.key === toolKey);
              return tool ? (
                <span
                  key={toolKey}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-purple-200 text-purple-900 rounded text-xs font-medium"
                >
                  {tool.icon} {tool.name}
                  <button
                    onClick={() => toggleTool(toolKey)}
                    className="ml-1 hover:bg-purple-300 rounded-full p-0.5"
                  >
                    <X size={12} />
                  </button>
                </span>
              ) : null;
            })}
          </div>
        </div>
      )}

      {/* Category Groups */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {Object.entries(filteredCategories).map(([category, tools]) => {
          const totalTools = tools.available.length + tools.locked.length;
          if (totalTools === 0) return null;

          const isExpanded = expandedCategory === category;

          return (
            <div key={category} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Category Header */}
              <button
                onClick={() => setExpandedCategory(isExpanded ? null : category)}
                className={`
                  w-full px-4 py-3 flex items-center justify-between
                  ${getCategoryColor(category)}
                  hover:opacity-80 transition-opacity
                `}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xl">{categoryInfo[category].icon}</span>
                  <span className="font-semibold">{categoryInfo[category].name}</span>
                  <span className="text-xs opacity-75">
                    ({tools.available.length} available, {tools.locked.length} locked)
                  </span>
                </div>
                <svg
                  className={`w-5 h-5 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>

              {/* Tool List */}
              {isExpanded && (
                <div className="bg-white divide-y divide-gray-100">
                  {/* Available Tools */}
                  {tools.available.map(tool => {
                    const isSelected = selectedTools.includes(tool.key);
                    return (
                      <div
                        key={tool.key}
                        onClick={() => toggleTool(tool.key)}
                        className={`
                          px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors
                          ${isSelected ? 'bg-purple-50' : ''}
                        `}
                      >
                        <div className="flex items-start gap-3">
                          {/* Checkbox */}
                          <div className={`
                            flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center
                            ${isSelected
                              ? 'bg-purple-600 border-purple-600'
                              : 'border-gray-300 bg-white'
                            }
                          `}>
                            {isSelected && <Check size={14} className="text-white" />}
                          </div>

                          {/* Tool Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-lg">{tool.icon}</span>
                              <span className="font-medium text-gray-900">{tool.name}</span>
                            </div>
                            <p className="text-sm text-gray-600 mt-0.5">{tool.description}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Locked Tools */}
                  {tools.locked.map(tool => (
                    <div
                      key={tool.key}
                      className="px-4 py-3 bg-gray-50 opacity-60"
                    >
                      <div className="flex items-start gap-3">
                        {/* Lock Icon */}
                        <div className="flex-shrink-0 w-5 h-5 rounded border-2 border-gray-300 bg-gray-200 flex items-center justify-center">
                          <Lock size={12} className="text-gray-500" />
                        </div>

                        {/* Tool Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-lg grayscale">{tool.icon}</span>
                            <span className="font-medium text-gray-600">{tool.name}</span>
                            <Lock size={14} className="text-gray-400" />
                          </div>
                          <p className="text-sm text-gray-500 mt-0.5">{tool.description}</p>

                          {/* Unlock Requirements */}
                          {tool.unlockRequirements && tool.unlockRequirements.length > 0 && (
                            <div className="mt-2 flex items-start gap-1.5">
                              <Info size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                              <div className="text-xs text-gray-600">
                                <span className="font-medium">To unlock:</span> {tool.unlockRequirements[0].message}
                              </div>
                            </div>
                          )}

                          {onUpgrade && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpgrade(tool);
                              }}
                              className="mt-2 text-xs text-purple-600 hover:text-purple-700 font-medium"
                            >
                              Upgrade to unlock →
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty State */}
      {Object.keys(filteredCategories).length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <Search size={48} className="mx-auto mb-2 opacity-50" />
          <p>No tools found matching "{searchTerm}"</p>
        </div>
      )}
    </div>
  );
};

export default ToolSelector;
