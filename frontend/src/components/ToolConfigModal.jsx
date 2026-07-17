import { useState, useEffect } from 'react';
import { X, Settings } from 'lucide-react';
import Modal from './ui/Modal';

const ToolConfigModal = ({ tool, config, onSave, onClose }) => {
  const [formData, setFormData] = useState({});

  useEffect(() => {
    // Initialize form data with existing config or defaults
    const initialData = {};
    if (tool.schema) {
      Object.keys(tool.schema).forEach(key => {
        initialData[key] = config[key] !== undefined
          ? config[key]
          : tool.schema[key].default;
      });
    }
    setFormData(initialData);
  }, [tool, config]);

  const handleChange = (key, value, type) => {
    let parsedValue = value;

    // Parse value based on type
    if (type === 'number') {
      parsedValue = parseFloat(value) || 0;
    } else if (type === 'boolean') {
      parsedValue = value === 'true' || value === true;
    }

    setFormData({ ...formData, [key]: parsedValue });
  };

  const handleSubmit = () => {
    onSave(formData);
  };

  const renderField = (key, field) => {
    const value = formData[key];

    switch (field.type) {
      case 'string':
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => handleChange(key, e.target.value, 'string')}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
            placeholder={field.default}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            value={value || ''}
            onChange={(e) => handleChange(key, e.target.value, 'number')}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
            placeholder={field.default?.toString()}
          />
        );

      case 'boolean':
        return (
          <div className="flex items-center space-x-3">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                name={key}
                checked={value === true}
                onChange={() => handleChange(key, true, 'boolean')}
                className="w-4 h-4 text-cyan-500 focus:ring-cyan-500 focus:ring-2"
              />
              <span className="text-sm">Yes</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                name={key}
                checked={value === false}
                onChange={() => handleChange(key, false, 'boolean')}
                className="w-4 h-4 text-cyan-500 focus:ring-cyan-500 focus:ring-2"
              />
              <span className="text-sm">No</span>
            </label>
          </div>
        );

      default:
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => handleChange(key, e.target.value, 'string')}
            className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
          />
        );
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      ariaLabel={`Configure ${tool.name}`}
      showClose={false}
      closeOnBackdrop={false}
      panelClassName="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-w-md w-full max-h-[80vh] overflow-hidden flex flex-col focus:outline-none"
    >
        {/* Header */}
        <div className="p-6 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-cyan-500/20">
              <Settings className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Configure {tool.name}</h2>
              <p className="text-sm text-slate-400">Customize tool settings</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
          {tool.schema && Object.keys(tool.schema).length > 0 ? (
            Object.entries(tool.schema).map(([key, field]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  {field.label || key}
                </label>
                {renderField(key, field)}
                {field.help && (
                  <p className="text-xs text-slate-400 mt-1">{field.help}</p>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8">
              <p className="text-slate-400">No configuration options available</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-700 flex space-x-3">
          <button
            onClick={handleSubmit}
            className="flex-1 px-4 py-2 bg-gradient-to-r from-unicorn-500 to-cyan-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-unicorn-500/50 transition-all"
          >
            Save Configuration
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg font-medium hover:bg-slate-700 transition-colors"
          >
            Cancel
          </button>
        </div>
    </Modal>
  );
};

export default ToolConfigModal;
