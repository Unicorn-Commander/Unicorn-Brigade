import { Plus, X, Settings } from 'lucide-react';

const ToolCard = ({ tool, action, onAction, onConfigure }) => {
  return (
    <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700 hover:border-cyan-500/50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <h4 className="font-medium">{tool.name}</h4>
            <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300">
              {tool.type}
            </span>
          </div>
          <p className="text-sm text-slate-400">{tool.description}</p>
        </div>

        <div className="flex items-center space-x-2 ml-4">
          {onConfigure && (
            <button
              onClick={onConfigure}
              className="p-2 rounded-lg hover:bg-slate-700 transition-colors"
              title="Configure"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={onAction}
            className={`p-2 rounded-lg transition-colors ${
              action === 'add'
                ? 'hover:bg-emerald-500/20 text-emerald-400'
                : 'hover:bg-red-500/20 text-red-400'
            }`}
            title={action === 'add' ? 'Add tool' : 'Remove tool'}
          >
            {action === 'add' ? (
              <Plus className="w-4 h-4" />
            ) : (
              <X className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ToolCard;
