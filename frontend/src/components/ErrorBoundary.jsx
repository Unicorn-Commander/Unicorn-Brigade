import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
    });

    this.setState((prev) => ({
      errorInfo,
      errorCount: prev.errorCount + 1,
    }));
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-slate-800/90 backdrop-blur-xl border border-red-500/30 rounded-xl shadow-2xl p-8">
            <div className="flex justify-center mb-6">
              <div className="p-4 bg-red-500/20 rounded-full">
                <AlertTriangle className="w-16 h-16 text-red-400" />
              </div>
            </div>

            <h1 className="text-3xl font-bold text-white text-center mb-4">
              Something Went Wrong
            </h1>

            <p className="text-slate-300 text-center mb-6">
              We encountered an unexpected error. This has been logged and our team will investigate.
            </p>

            {import.meta.env.DEV && this.state.error && (
              <details className="mb-6 bg-slate-900/50 rounded-lg p-4 border border-slate-700">
                <summary className="cursor-pointer text-sm font-medium text-slate-400 hover:text-white">
                  Error Details (Development)
                </summary>
                <div className="mt-4 space-y-2">
                  <div className="text-sm">
                    <span className="text-red-400 font-medium">Error:</span>
                    <pre className="mt-2 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                      {this.state.error.toString()}
                    </pre>
                  </div>
                  {this.state.errorInfo && (
                    <div className="text-sm">
                      <span className="text-red-400 font-medium">Component Stack:</span>
                      <pre className="mt-2 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center justify-center space-x-2"
              >
                <RefreshCw className="w-5 h-5" />
                <span>Try Again</span>
              </button>

              <button
                onClick={this.handleReload}
                className="px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors flex items-center justify-center space-x-2"
              >
                <RefreshCw className="w-5 h-5" />
                <span>Reload Page</span>
              </button>

              <Link
                to="/dashboard"
                className="px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors flex items-center justify-center space-x-2"
              >
                <Home className="w-5 h-5" />
                <span>Go Home</span>
              </Link>
            </div>

            {this.state.errorCount > 2 && (
              <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <p className="text-sm text-yellow-300 text-center">
                  Warning: Multiple errors detected ({this.state.errorCount}). Consider clearing your browser cache or contacting support.
                </p>
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
