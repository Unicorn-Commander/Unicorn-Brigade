import { useState } from 'react';
import { AlertTriangle, Copy, CheckCircle, Shield } from 'lucide-react';
import { toast } from 'react-hot-toast';

const KeyRevealModal = ({ apiKey, onClose }) => {
  const [copied, setCopied] = useState(false);

  const keyValue = apiKey.key || '';

  const handleCopy = () => {
    navigator.clipboard.writeText(keyValue);
    setCopied(true);
    toast.success('Copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Warning Header */}
        <div className="p-6 bg-gradient-to-r from-amber-500/10 to-red-500/10 border-b border-amber-500/20">
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-amber-500/20 flex-shrink-0">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white mb-1">Save This Key Now</h2>
              <p className="text-sm text-amber-200">
                This is the only time you'll see this key. Store it securely!
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Key Name */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Key Name</label>
            <p className="text-slate-200 font-medium">{apiKey.name}</p>
          </div>

          {/* API Key Display */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-2">API Key</label>
            <div className="relative">
              <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                <div className="flex items-center justify-between">
                  <code className="text-sm font-mono text-unicorn-400 flex-1 break-all pr-3">
                    {keyValue}
                  </code>
                  <button
                    onClick={handleCopy}
                    className="ml-3 p-2 hover:bg-slate-700 rounded-lg transition-colors flex-shrink-0"
                    title="Copy to clipboard"
                  >
                    {copied ? (
                      <CheckCircle className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <Copy className="w-5 h-5 text-slate-400" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Key Details */}
          <div className="grid grid-cols-2 gap-4 pt-2">
            <div className="p-3 rounded-lg bg-slate-800/50">
              <p className="text-xs text-slate-400 mb-1">Permissions</p>
              <div className="flex flex-wrap gap-1">
                {apiKey.permissions?.map((perm, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-xs bg-cyan-500/20 text-cyan-300"
                  >
                    {perm}
                  </span>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-800/50">
              <p className="text-xs text-slate-400 mb-1">Rate Limit</p>
              <p className="text-sm text-slate-200 font-medium">
                {apiKey.rateLimit} req/min
              </p>
            </div>
          </div>

          {/* Security Notice */}
          <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/50">
            <div className="flex items-start space-x-3">
              <Shield className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 text-xs text-slate-400 space-y-1">
                <p className="font-medium text-slate-300">Security Best Practices:</p>
                <ul className="list-disc list-inside space-y-0.5 ml-1">
                  <li>Store this key in a secure location (e.g., password manager)</li>
                  <li>Never commit API keys to version control</li>
                  <li>Use environment variables in your applications</li>
                  <li>Revoke immediately if compromised</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Usage Example */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-2">Usage Example</label>
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
              <code className="text-xs font-mono text-slate-400">
                <span className="text-purple-400">curl</span>{' '}
                <span className="text-emerald-400">-X POST</span>{' '}
                <span className="text-slate-300">https://api.unicornbrigade.com/agents/invoke</span> \<br />
                {'  '}<span className="text-emerald-400">-H</span>{' '}
                <span className="text-amber-300">"X-API-Key: {keyValue.substring(0, 20)}..."</span> \<br />
                {'  '}<span className="text-emerald-400">-H</span>{' '}
                <span className="text-amber-300">"Content-Type: application/json"</span>
              </code>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-700">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gradient-to-r from-unicorn-500 to-cyan-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-unicorn-500/50 transition-all"
          >
            I've Saved It
          </button>
          <p className="text-xs text-center text-slate-500 mt-3">
            You can manage this key in the API Keys tab
          </p>
        </div>
      </div>
    </div>
  );
};

export default KeyRevealModal;
