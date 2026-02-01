import React from 'react';
import { Link } from 'react-router-dom';
import { Home, RefreshCw, AlertTriangle } from 'lucide-react';

export default function ServerError() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-red-900/20 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center">
        <div className="flex justify-center mb-6">
          <div className="p-6 bg-red-500/20 rounded-full">
            <AlertTriangle className="w-24 h-24 text-red-400" />
          </div>
        </div>

        <h1 className="text-4xl font-bold text-white mb-4">
          Server Error
        </h1>

        <p className="text-slate-300 text-lg mb-8">
          We are experiencing technical difficulties. Our team has been notified and is working to fix the issue.
        </p>

        <div className="bg-slate-800/50 backdrop-blur-xl border border-red-500/30 rounded-xl p-6 mb-8">
          <h3 className="text-lg font-semibold text-white mb-4">
            What you can do:
          </h3>
          <ul className="text-left space-y-2 text-slate-300">
            <li className="flex items-start space-x-2">
              <span className="text-red-400 mt-1">•</span>
              <span>Wait a few moments and try again</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-red-400 mt-1">•</span>
              <span>Clear your browser cache and reload</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-red-400 mt-1">•</span>
              <span>Check the status page for updates</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-red-400 mt-1">•</span>
              <span>Contact support if the problem persists</span>
            </li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors flex items-center justify-center space-x-2"
          >
            <RefreshCw className="w-5 h-5" />
            <span>Reload Page</span>
          </button>

          <Link
            to="/dashboard"
            className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:from-purple-700 hover:to-pink-700 transition-colors flex items-center justify-center space-x-2"
          >
            <Home className="w-5 h-5" />
            <span>Go to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
