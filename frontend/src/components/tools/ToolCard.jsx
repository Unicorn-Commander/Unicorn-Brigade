import React from 'react';
import { Lock, Info, TrendingUp, Shield } from 'lucide-react';

/**
 * ToolCard Component
 * Displays individual tool with lock state and permission info
 */
const ToolCard = ({ tool, onUpgrade, onSelect, selected = false }) => {
  const { name, description, icon, category, locked, riskLevel, unlockRequirements = [] } = tool;

  // Risk level colors
  const riskColors = {
    low: 'text-green-600 bg-green-50',
    medium: 'text-yellow-600 bg-yellow-50',
    high: 'text-orange-600 bg-orange-50',
    critical: 'text-red-600 bg-red-50'
  };

  // Category colors
  const categoryColors = {
    common: 'bg-green-100 text-green-800',
    advanced: 'bg-blue-100 text-blue-800',
    premium: 'bg-unicorn-100 text-unicorn-800',
    admin: 'bg-red-100 text-red-800'
  };

  const handleClick = () => {
    if (!locked && onSelect) {
      onSelect(tool);
    }
  };

  return (
    <div
      className={`
        relative rounded-lg border-2 transition-all duration-200
        ${locked
          ? 'border-gray-300 bg-gray-50 opacity-75'
          : selected
            ? 'border-unicorn-500 bg-unicorn-50 shadow-md'
            : 'border-gray-200 bg-white hover:border-unicorn-300 hover:shadow-md'
        }
        ${!locked && onSelect ? 'cursor-pointer' : ''}
      `}
      onClick={handleClick}
    >
      {/* Lock Overlay */}
      {locked && (
        <div className="absolute top-2 right-2 z-10">
          <div className="bg-gray-700 text-white p-1.5 rounded-full">
            <Lock size={16} />
          </div>
        </div>
      )}

      {/* Selection Indicator */}
      {selected && !locked && (
        <div className="absolute top-2 left-2 z-10">
          <div className="bg-unicorn-600 text-white p-1 rounded-full">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
        </div>
      )}

      <div className="p-4">
        {/* Icon and Name */}
        <div className="flex items-start gap-3 mb-3">
          <div className="text-3xl">{icon}</div>
          <div className="flex-1">
            <h3 className={`font-semibold text-lg ${locked ? 'text-gray-600' : 'text-gray-900'}`}>
              {name}
            </h3>
            <div className="flex gap-2 mt-1">
              {/* Category Badge */}
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryColors[category]}`}>
                {category}
              </span>
              {/* Risk Level Badge */}
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${riskColors[riskLevel]}`}>
                {riskLevel} risk
              </span>
            </div>
          </div>
        </div>

        {/* Description */}
        <p className={`text-sm mb-3 ${locked ? 'text-gray-500' : 'text-gray-700'}`}>
          {description}
        </p>

        {/* Locked State - Show Unlock Requirements */}
        {locked && unlockRequirements.length > 0 && (
          <div className="border-t pt-3 mt-3 border-gray-300">
            <div className="flex items-start gap-2 mb-2">
              <Info size={16} className="text-gray-600 mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-medium text-gray-700 mb-1">To unlock this tool:</p>
                <ul className="text-xs text-gray-600 space-y-1">
                  {unlockRequirements.map((req, idx) => (
                    <li key={idx} className="flex items-start gap-1">
                      <span className="text-unicorn-600">•</span>
                      <span>{req.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {onUpgrade && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onUpgrade(tool);
                }}
                className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white text-sm font-medium rounded-md hover:from-unicorn-600 hover:to-unicorn-500 transition-colors"
              >
                <TrendingUp size={14} />
                Upgrade to Unlock
              </button>
            )}
          </div>
        )}

        {/* Available State - Show Risk Info */}
        {!locked && riskLevel !== 'low' && (
          <div className="border-t pt-3 mt-3 border-gray-200">
            <div className="flex items-start gap-2">
              <Shield size={14} className={riskColors[riskLevel].split(' ')[0]} />
              <p className={`text-xs ${riskColors[riskLevel].split(' ')[0]}`}>
                {riskLevel === 'critical' && 'Critical risk - requires admin approval'}
                {riskLevel === 'high' && 'High risk - use with caution'}
                {riskLevel === 'medium' && 'Medium risk - review before use'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ToolCard;
