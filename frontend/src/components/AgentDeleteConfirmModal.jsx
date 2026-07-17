import React, { useState } from 'react';
import { AlertTriangle, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import api from '../services/api';
import Modal from './ui/Modal';

export default function AgentDeleteConfirmModal({ agent, onClose, onDelete }) {
  const [loading, setLoading] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const handleDelete = async () => {
    if (confirmText !== agent.name) {
      toast.error('Agent name does not match');
      return;
    }

    setLoading(true);
    const rollback = onDelete?.(agent, { optimistic: true });
    try {
      await api.deleteAgent(agent.id);
      notify.success(`${agent.displayName || agent.name} deleted successfully`);
      onDelete?.(agent, { optimistic: false });
      onClose();
    } catch (error) {
      console.error('Failed to delete agent:', error);
      toast.error(error?.message || 'Failed to delete agent');
      if (rollback) rollback();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      onClose={loading ? () => {} : onClose}
      ariaLabel="Delete agent confirmation"
      showClose={false}
      panelClassName="bg-slate-800/90 backdrop-blur-xl border border-red-500/50 rounded-xl shadow-2xl max-w-md w-full"
    >
        <div className="p-6 border-b border-slate-700/50">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-red-500/20 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Delete Agent</h2>
              <p className="text-sm text-slate-400 mt-1">This action cannot be undone</p>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-slate-300">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-white">{agent.displayName || agent.name}</span>?
          </p>

          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-sm text-red-300 mb-3">
              This will permanently delete:
            </p>
            <ul className="text-sm text-slate-400 space-y-1 list-disc list-inside">
              <li>All agent configuration</li>
              <li>Associated conversations and history</li>
              <li>API keys linked to this agent</li>
            </ul>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Type <span className="font-mono text-white">{agent.name}</span> to confirm:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-red-500"
              placeholder={agent.name}
              autoFocus
              disabled={loading}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 p-6 border-t border-slate-700/50 bg-slate-800/50">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-6 py-2.5 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={loading || confirmText !== agent.name}
            className="px-6 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Deleting...</span>
              </>
            ) : (
              <>
                <Trash2 className="w-4 h-4" />
                <span>Delete Agent</span>
              </>
            )}
          </button>
        </div>
    </Modal>
  );
}
