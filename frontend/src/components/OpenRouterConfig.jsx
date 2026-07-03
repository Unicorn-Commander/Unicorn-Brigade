import React, { useState, useEffect } from 'react';
import { Key, CheckCircle, AlertCircle, Send, Loader2 } from 'lucide-react';
import { apiJson, ApiError } from '../services/http';

const OpenRouterConfig = () => {
  const [apiKey, setApiKey] = useState('');
  const [testMessage, setTestMessage] = useState('I have a headache and feel dizzy');
  const [isLoading, setIsLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState(null);
  const [keyStored, setKeyStored] = useState(false);

  useEffect(() => {
    // Check if API key is stored in localStorage
    const storedKey = localStorage.getItem('openrouter_api_key');
    if (storedKey) {
      setApiKey(storedKey);
      setKeyStored(true);
    }
  }, []);

  const handleSaveKey = () => {
    if (apiKey.trim()) {
      localStorage.setItem('openrouter_api_key', apiKey.trim());
      setKeyStored(true);
      setError(null);
    }
  };

  const handleTestOpenRouter = async () => {
    if (!apiKey.trim()) {
      setError('Please enter your OpenRouter API key');
      return;
    }

    setIsLoading(true);
    setError(null);
    setTestResult(null);

    try {
      const data = await apiJson('/medical-test/test-openrouter', {
        method: 'POST',
        body: JSON.stringify({
          apiKey: apiKey.trim(),
          message: testMessage
        }),
      });

      if (data.success) {
        setTestResult(data);
        handleSaveKey(); // Auto-save on successful test
      } else {
        setError(data.error || 'Test failed');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.data?.error || err.message || 'Test failed');
      } else {
        setError('Failed to connect to server: ' + err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestConsultation = async () => {
    if (!apiKey.trim()) {
      setError('Please enter your OpenRouter API key');
      return;
    }

    setIsLoading(true);
    setError(null);
    setTestResult(null);

    try {
      const data = await apiJson('/medical-test/test-consultation', {
        method: 'POST',
        body: JSON.stringify({
          apiKey: apiKey.trim(),
          symptoms: testMessage
        }),
      });

      if (data.success) {
        setTestResult(data);
      } else {
        setError(data.error || 'Consultation test failed');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.data?.error || err.message || 'Consultation test failed');
      } else {
        setError('Failed to connect to server: ' + err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
        <div className="flex items-center space-x-3 mb-6">
          <Key className="w-6 h-6 text-cyan-400" />
          <h2 className="text-2xl font-bold text-white">OpenRouter Configuration</h2>
        </div>

        {/* API Key Input */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              OpenRouter API Key
            </label>
            <div className="flex space-x-2">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-or-v1-000000000000000000000000000000000000"
                className="flex-1 px-4 py-2 bg-black/30 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-cyan-400"
              />
              <button
                onClick={handleSaveKey}
                disabled={!apiKey.trim() || keyStored}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  keyStored
                    ? 'bg-green-600/20 text-green-400 border border-green-600/30'
                    : 'bg-cyan-600 text-white hover:bg-cyan-700'
                }`}
              >
                {keyStored ? <CheckCircle className="w-5 h-5" /> : 'Save'}
              </button>
            </div>
            {keyStored && (
              <p className="text-sm text-green-400 mt-2">
                ✓ API key saved to browser storage
              </p>
            )}
          </div>

          {/* Test Message Input */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Test Message (Symptoms)
            </label>
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 bg-black/30 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-cyan-400"
              placeholder="Describe symptoms to test..."
            />
          </div>

          {/* Test Buttons */}
          <div className="flex space-x-4">
            <button
              onClick={handleTestOpenRouter}
              disabled={isLoading || !apiKey.trim()}
              className="flex items-center space-x-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              <span>Test OpenRouter Direct</span>
            </button>

            <button
              onClick={handleTestConsultation}
              disabled={isLoading || !apiKey.trim()}
              className="flex items-center space-x-2 px-6 py-3 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              <span>Test Medical Consultation</span>
            </button>
          </div>

          {/* Error Display */}
          {error && (
            <div className="p-4 bg-red-900/20 border border-red-600/30 rounded-lg">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <p className="text-red-400">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {testResult && (
            <div className="p-4 bg-green-900/20 border border-green-600/30 rounded-lg">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <p className="text-green-400 font-semibold">Test Successful!</p>
                </div>

                {testResult.model && (
                  <div className="text-sm text-gray-300">
                    <span className="text-gray-400">Model:</span> {testResult.model}
                  </div>
                )}

                {testResult.response && (
                  <div className="mt-3 p-3 bg-black/30 rounded-lg">
                    <p className="text-sm text-gray-400 mb-2">AI Response:</p>
                    <p className="text-white whitespace-pre-wrap">{testResult.response.content || testResult.response}</p>
                  </div>
                )}

                {testResult.usage && (
                  <div className="text-xs text-gray-400 mt-2">
                    Tokens: {testResult.usage.total_tokens} |
                    Cost: ${testResult.usage.total_cost?.toFixed(4) || '0.0000'}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="mt-6 p-4 bg-blue-900/20 border border-blue-600/30 rounded-lg">
          <h3 className="text-sm font-semibold text-blue-400 mb-2">How to get your API key:</h3>
          <ol className="text-sm text-gray-300 space-y-1">
            <li>1. Visit <a href="https://openrouter.ai" target="_blank" rel="noopener noreferrer" className="text-cyan-400 underline">openrouter.ai</a></li>
            <li>2. Sign up or log in to your account</li>
            <li>3. Navigate to API Keys section</li>
            <li>4. Create a new API key and copy it here</li>
            <li>5. Add credits to your account ($5 minimum recommended)</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

export default OpenRouterConfig;