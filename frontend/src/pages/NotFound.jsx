import React from 'react';
import { Link } from 'react-router-dom';
import { Home, Search, ArrowLeft } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center">
        <h1 className="text-9xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-4">
          404
        </h1>

        <h2 className="text-3xl font-bold text-white mb-4">
          Page Not Found
        </h2>

        <p className="text-slate-300 text-lg mb-8">
          The page you are looking for does not exist or has been moved.
        </p>

        <div className="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-xl p-6 mb-8">
          <h3 className="text-lg font-semibold text-white mb-4">
            Try these instead:
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
            <Link
              to="/dashboard"
              className="flex items-center space-x-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors group"
            >
              <Home className="w-5 h-5 text-purple-400" />
              <div>
                <div className="text-white font-medium group-hover:text-purple-400 transition-colors">Dashboard</div>
                <div className="text-xs text-slate-400">View overview</div>
              </div>
            </Link>

            <Link
              to="/library"
              className="flex items-center space-x-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors group"
            >
              <Search className="w-5 h-5 text-purple-400" />
              <div>
                <div className="text-white font-medium group-hover:text-purple-400 transition-colors">Agent Library</div>
                <div className="text-xs text-slate-400">Browse agents</div>
              </div>
            </Link>

            <Link
              to="/workflows"
              className="flex items-center space-x-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors group"
            >
              <Search className="w-5 h-5 text-purple-400" />
              <div>
                <div className="text-white font-medium group-hover:text-purple-400 transition-colors">Workflows</div>
                <div className="text-xs text-slate-400">Execute workflows</div>
              </div>
            </Link>

            <Link
              to="/mcp-servers"
              className="flex items-center space-x-3 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-lg transition-colors group"
            >
              <Search className="w-5 h-5 text-purple-400" />
              <div>
                <div className="text-white font-medium group-hover:text-purple-400 transition-colors">MCP Servers</div>
                <div className="text-xs text-slate-400">Manage servers</div>
              </div>
            </Link>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => window.history.back()}
            className="px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors flex items-center justify-center space-x-2"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Go Back</span>
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
