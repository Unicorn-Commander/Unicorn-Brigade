import { useState } from 'react';
import { X, Plus } from 'lucide-react';

const TagInput = ({
  tags = [],
  onAdd,
  onRemove,
  placeholder = 'Add tag...',
  maxTags = 10,
  disabled = false
}) => {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      handleAdd();
    }
  };

  const handleAdd = () => {
    const newTag = inputValue.trim();
    if (newTag && !tags.includes(newTag) && tags.length < maxTags) {
      onAdd(newTag);
      setInputValue('');
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {tags.map((tag, index) => (
          <div
            key={index}
            className="flex items-center space-x-1 px-3 py-1.5 bg-unicorn-500/20 border border-unicorn-500/30 rounded-lg text-sm text-unicorn-300"
          >
            <span className="font-mono">{tag}</span>
            {!disabled && (
              <button
                onClick={() => onRemove(tag)}
                className="ml-1 hover:bg-unicorn-500/30 rounded p-0.5 transition-colors"
                title="Remove tag"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        ))}

        {tags.length === 0 && (
          <p className="text-sm text-slate-500 italic">No tags added</p>
        )}
      </div>

      {!disabled && tags.length < maxTags && (
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-sm"
            maxLength={50}
          />
          <button
            onClick={handleAdd}
            disabled={!inputValue.trim()}
            className="btn-secondary px-3 py-2 flex items-center space-x-1 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Add tag"
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm">Add</span>
          </button>
        </div>
      )}

      {tags.length >= maxTags && !disabled && (
        <p className="text-xs text-amber-400">Maximum number of tags reached ({maxTags})</p>
      )}
    </div>
  );
};

export default TagInput;
