/**
 * Webhook Trigger Tool - HTTP webhook integration
 * UC2 Internal Tool v1.0.0
 * Send webhooks to external systems with retry logic and signature verification
 */

const https = require('https');
const http = require('http');
const crypto = require('crypto');
const fs = require('fs').promises;

class WebhookTriggerTool {
    constructor() {
        this.name = 'webhookTrigger';
        this.version = '1.0.0';
        this.description = 'Send HTTP webhooks to external systems with retry logic and security';
        this.category = 'integration';
        this.permissions = ['network', 'external_api', 'webhook'];
        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['send', 'test', 'verify', 'batch', 'schedule', 'template'],
                    description: 'Webhook action to perform'
                },
                url: {
                    type: 'string',
                    description: 'Target webhook URL'
                },
                method: {
                    type: 'string',
                    enum: ['POST', 'PUT', 'PATCH'],
                    default: 'POST',
                    description: 'HTTP method for webhook'
                },
                payload: {
                    type: 'object',
                    description: 'Webhook payload data'
                },
                headers: {
                    type: 'object',
                    description: 'Custom HTTP headers'
                },
                secret: {
                    type: 'string',
                    description: 'Secret key for HMAC signature'
                },
                signatureHeader: {
                    type: 'string',
                    default: 'X-Signature-256',
                    description: 'Header name for HMAC signature'
                },
                signaturePrefix: {
                    type: 'string',
                    default: 'sha256=',
                    description: 'Signature prefix (e.g., sha256=, sha1=)'
                },
                timeout: {
                    type: 'number',
                    default: 30000,
                    description: 'Request timeout in milliseconds'
                },
                retryAttempts: {
                    type: 'number',
                    default: 3,
                    description: 'Number of retry attempts on failure'
                },
                retryDelay: {
                    type: 'number',
                    default: 1000,
                    description: 'Initial retry delay in milliseconds'
                },
                retryBackoff: {
                    type: 'string',
                    enum: ['linear', 'exponential'],
                    default: 'exponential',
                    description: 'Retry backoff strategy'
                },
                expectedStatus: {
                    type: 'array',
                    items: { type: 'number' },
                    default: [200, 201, 202, 204],
                    description: 'Expected HTTP status codes for success'
                },
                template: {
                    type: 'string',
                    enum: ['slack', 'discord', 'teams', 'github', 'generic'],
                    description: 'Predefined webhook template'
                },
                templateData: {
                    type: 'object',
                    description: 'Data for webhook template'
                },
                batchUrls: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Array of URLs for batch sending'
                },
                circuitBreaker: {
                    type: 'object',
                    properties: {
                        enabled: { type: 'boolean', default: false },
                        threshold: { type: 'number', default: 5 },
                        timeout: { type: 'number', default: 60000 }
                    },
                    description: 'Circuit breaker configuration'
                },
                logRequests: {
                    type: 'boolean',
                    default: true,
                    description: 'Whether to log webhook requests and responses'
                },
                validateSsl: {
                    type: 'boolean',
                    default: true,
                    description: 'Whether to validate SSL certificates'
                }
            },
            required: ['action']
        };

        this.mockMode = process.env.NODE_ENV === 'test' || process.env.WEBHOOK_MOCK_MODE === 'true';
        this.circuitBreakerState = new Map(); // URL -> { failures: 0, lastFailure: null, state: 'closed|open|half-open' }
        this.requestLog = [];
        this.templates = this._loadWebhookTemplates();
    }

    /**
     * Execute webhook operation
     * @param {Object} params - Webhook parameters
     * @returns {Object} Operation result
     */
    async execute(params, context = {}) {
        const startTime = process.hrtime.bigint();

        try {
            const {
                action,
                url,
                method = 'POST',
                payload,
                headers = {},
                secret,
                signatureHeader = 'X-Signature-256',
                signaturePrefix = 'sha256=',
                timeout = 30000,
                retryAttempts = 3,
                retryDelay = 1000,
                retryBackoff = 'exponential',
                expectedStatus = [200, 201, 202, 204],
                template,
                templateData,
                batchUrls = [],
                circuitBreaker = { enabled: false },
                logRequests = true,
                validateSsl = true
            } = params;

            // Validate action
            if (!['send', 'test', 'verify', 'batch', 'schedule', 'template'].includes(action)) {
                throw new Error(`Invalid action: ${action}`);
            }

            let result;

            switch (action) {
                case 'send':
                    result = await this._sendWebhook({
                        url, method, payload, headers, secret, signatureHeader, signaturePrefix,
                        timeout, retryAttempts, retryDelay, retryBackoff, expectedStatus,
                        circuitBreaker, logRequests, validateSsl
                    });
                    break;
                case 'test':
                    result = await this._testWebhook(url, timeout, validateSsl);
                    break;
                case 'verify':
                    result = await this._verifySignature(payload, secret, params.signature, signaturePrefix);
                    break;
                case 'batch':
                    result = await this._sendBatchWebhooks(batchUrls, {
                        method, payload, headers, secret, signatureHeader, signaturePrefix,
                        timeout, retryAttempts, retryDelay, retryBackoff, expectedStatus,
                        circuitBreaker, logRequests, validateSsl
                    });
                    break;
                case 'schedule':
                    result = await this._scheduleWebhook(params);
                    break;
                case 'template':
                    result = await this._useTemplate(template, templateData, url, headers, secret);
                    break;
                default:
                    throw new Error(`Unsupported action: ${action}`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to ms

            return {
                success: true,
                action: action,
                result: result,
                timestamp: new Date().toISOString(),
                executionTime: `${executionTime.toFixed(2)}ms`,
                mockMode: this.mockMode
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                action: params.action,
                timestamp: new Date().toISOString(),
                mockMode: this.mockMode
            };
        }
    }

    /**
     * Send webhook with retry logic and circuit breaker
     * @private
     */
    async _sendWebhook(options) {
        const { url, method, payload, headers, secret, signatureHeader, signaturePrefix,
                timeout, retryAttempts, retryDelay, retryBackoff, expectedStatus,
                circuitBreaker, logRequests, validateSsl } = options;

        if (!url) {
            throw new Error('Webhook URL is required');
        }

        // Check circuit breaker
        if (circuitBreaker.enabled && this._isCircuitOpen(url, circuitBreaker)) {
            throw new Error(`Circuit breaker is open for URL: ${url}`);
        }

        if (this.mockMode) {
            return this._mockSendWebhook(url, method, payload, headers);
        }

        let lastError;
        let attempt = 0;

        while (attempt <= retryAttempts) {
            try {
                const requestId = crypto.randomUUID();
                const requestStartTime = Date.now();

                // Prepare request data
                const bodyData = JSON.stringify(payload || {});
                const requestHeaders = { ...headers };

                // Add default headers
                requestHeaders['Content-Type'] = requestHeaders['Content-Type'] || 'application/json';
                requestHeaders['Content-Length'] = Buffer.byteLength(bodyData);
                requestHeaders['User-Agent'] = requestHeaders['User-Agent'] || 'UC2-WebhookTrigger/1.0.0';
                requestHeaders['X-Request-ID'] = requestId;

                // Add HMAC signature if secret provided
                if (secret) {
                    const signature = this._generateSignature(bodyData, secret, signaturePrefix);
                    requestHeaders[signatureHeader] = signature;
                }

                // Make the HTTP request
                const response = await this._makeHttpRequest(url, method, bodyData, requestHeaders, timeout, validateSsl);
                const requestEndTime = Date.now();

                // Check if status is expected
                if (!expectedStatus.includes(response.statusCode)) {
                    throw new Error(`Unexpected status code: ${response.statusCode}`);
                }

                // Record success
                this._recordCircuitBreakerSuccess(url);

                // Log request if enabled
                if (logRequests) {
                    this._logRequest({
                        requestId,
                        url,
                        method,
                        attempt: attempt + 1,
                        statusCode: response.statusCode,
                        responseTime: requestEndTime - requestStartTime,
                        success: true,
                        timestamp: new Date().toISOString()
                    });
                }

                return {
                    requestId: requestId,
                    url: url,
                    method: method,
                    statusCode: response.statusCode,
                    headers: response.headers,
                    body: response.body,
                    responseTime: requestEndTime - requestStartTime,
                    attempt: attempt + 1,
                    success: true
                };

            } catch (error) {
                lastError = error;
                attempt++;

                // Record failure for circuit breaker
                if (circuitBreaker.enabled) {
                    this._recordCircuitBreakerFailure(url);
                }

                // Log failed attempt if enabled
                if (logRequests) {
                    this._logRequest({
                        requestId: crypto.randomUUID(),
                        url,
                        method,
                        attempt,
                        error: error.message,
                        success: false,
                        timestamp: new Date().toISOString()
                    });
                }

                // If this was the last attempt, throw the error
                if (attempt > retryAttempts) {
                    break;
                }

                // Calculate retry delay
                const delay = this._calculateRetryDelay(attempt, retryDelay, retryBackoff);
                console.log(`Webhook attempt ${attempt} failed, retrying in ${delay}ms: ${error.message}`);

                // Wait before retrying
                await this._sleep(delay);
            }
        }

        throw new Error(`Webhook failed after ${attempt} attempts. Last error: ${lastError.message}`);
    }

    /**
     * Test webhook endpoint availability
     * @private
     */
    async _testWebhook(url, timeout = 30000, validateSsl = true) {
        if (!url) {
            throw new Error('URL is required for webhook test');
        }

        if (this.mockMode) {
            return this._mockTestWebhook(url);
        }

        try {
            const startTime = Date.now();
            const testPayload = JSON.stringify({ test: true, timestamp: new Date().toISOString() });

            const response = await this._makeHttpRequest(
                url,
                'POST',
                testPayload,
                {
                    'Content-Type': 'application/json',
                    'User-Agent': 'UC2-WebhookTrigger/1.0.0 (Test)',
                    'X-Test-Request': 'true'
                },
                timeout,
                validateSsl
            );

            const endTime = Date.now();

            return {
                url: url,
                available: true,
                statusCode: response.statusCode,
                responseTime: endTime - startTime,
                headers: response.headers,
                testResult: 'success'
            };

        } catch (error) {
            return {
                url: url,
                available: false,
                error: error.message,
                testResult: 'failed'
            };
        }
    }

    /**
     * Verify webhook signature
     * @private
     */
    async _verifySignature(payload, secret, receivedSignature, signaturePrefix = 'sha256=') {
        if (!secret || !receivedSignature) {
            throw new Error('Secret and signature are required for verification');
        }

        try {
            const bodyData = typeof payload === 'string' ? payload : JSON.stringify(payload);
            const expectedSignature = this._generateSignature(bodyData, secret, signaturePrefix);

            const isValid = crypto.timingSafeEqual(
                Buffer.from(receivedSignature),
                Buffer.from(expectedSignature)
            );

            return {
                valid: isValid,
                expectedSignature: expectedSignature,
                receivedSignature: receivedSignature,
                signaturePrefix: signaturePrefix
            };

        } catch (error) {
            return {
                valid: false,
                error: error.message,
                expectedSignature: null,
                receivedSignature: receivedSignature
            };
        }
    }

    /**
     * Send webhooks to multiple URLs
     * @private
     */
    async _sendBatchWebhooks(urls, options) {
        if (!urls || !Array.isArray(urls) || urls.length === 0) {
            throw new Error('Array of URLs is required for batch sending');
        }

        const results = [];
        const promises = urls.map(async (url) => {
            try {
                const result = await this._sendWebhook({ ...options, url });
                return { url, success: true, result };
            } catch (error) {
                return { url, success: false, error: error.message };
            }
        });

        const batchResults = await Promise.allSettled(promises);

        batchResults.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                results.push(result.value);
            } else {
                results.push({
                    url: urls[index],
                    success: false,
                    error: result.reason.message
                });
            }
        });

        const successCount = results.filter(r => r.success).length;
        const failureCount = results.length - successCount;

        return {
            totalUrls: urls.length,
            successCount: successCount,
            failureCount: failureCount,
            results: results,
            batchComplete: true
        };
    }

    /**
     * Schedule webhook for later execution
     * @private
     */
    async _scheduleWebhook(params) {
        const { scheduleTime, cronExpression, recurring } = params;

        // In a real implementation, this would integrate with a job scheduler like node-cron or Bull
        if (this.mockMode) {
            return this._mockScheduleWebhook(params);
        }

        // For now, return a mock implementation
        return {
            scheduled: true,
            scheduleId: crypto.randomUUID(),
            scheduleTime: scheduleTime,
            cronExpression: cronExpression,
            recurring: recurring || false,
            status: 'pending',
            note: 'Webhook scheduling requires job queue integration'
        };
    }

    /**
     * Use predefined webhook template
     * @private
     */
    async _useTemplate(templateName, templateData, url, headers = {}, secret) {
        if (!templateName) {
            throw new Error('Template name is required');
        }

        const template = this.templates[templateName];
        if (!template) {
            throw new Error(`Unknown template: ${templateName}`);
        }

        // Apply template data to template
        const compiledPayload = this._compileTemplate(template.payload, templateData || {});
        const compiledHeaders = { ...template.headers, ...headers };

        // Send webhook using template
        return await this._sendWebhook({
            url: url || template.defaultUrl,
            method: template.method || 'POST',
            payload: compiledPayload,
            headers: compiledHeaders,
            secret: secret,
            signatureHeader: template.signatureHeader,
            signaturePrefix: template.signaturePrefix,
            timeout: 30000,
            retryAttempts: 3,
            retryDelay: 1000,
            retryBackoff: 'exponential',
            expectedStatus: template.expectedStatus || [200, 201, 202, 204],
            circuitBreaker: { enabled: false },
            logRequests: true,
            validateSsl: true
        });
    }

    /**
     * HTTP request helper
     * @private
     */
    async _makeHttpRequest(url, method, body, headers, timeout, validateSsl) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const isHttps = urlObj.protocol === 'https:';

            const options = {
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: urlObj.pathname + urlObj.search,
                method: method,
                headers: headers,
                timeout: timeout
            };

            if (isHttps && !validateSsl) {
                options.rejectUnauthorized = false;
            }

            const httpModule = isHttps ? https : http;

            const req = httpModule.request(options, (res) => {
                let responseBody = '';

                res.on('data', (chunk) => {
                    responseBody += chunk;
                });

                res.on('end', () => {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        body: responseBody
                    });
                });
            });

            req.on('error', (error) => {
                reject(new Error(`Request failed: ${error.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error(`Request timed out after ${timeout}ms`));
            });

            if (body) {
                req.write(body);
            }

            req.end();
        });
    }

    /**
     * Circuit breaker helpers
     */
    _isCircuitOpen(url, circuitBreakerConfig) {
        const state = this.circuitBreakerState.get(url);
        if (!state) return false;

        if (state.state === 'open') {
            // Check if enough time has passed to try half-open
            if (Date.now() - state.lastFailure > circuitBreakerConfig.timeout) {
                state.state = 'half-open';
                this.circuitBreakerState.set(url, state);
                return false;
            }
            return true;
        }

        return false;
    }

    _recordCircuitBreakerFailure(url) {
        const state = this.circuitBreakerState.get(url) || { failures: 0, lastFailure: null, state: 'closed' };
        state.failures++;
        state.lastFailure = Date.now();

        if (state.failures >= 5 && state.state === 'closed') { // Default threshold
            state.state = 'open';
        }

        this.circuitBreakerState.set(url, state);
    }

    _recordCircuitBreakerSuccess(url) {
        const state = this.circuitBreakerState.get(url);
        if (state) {
            if (state.state === 'half-open') {
                state.state = 'closed';
                state.failures = 0;
            } else if (state.state === 'closed') {
                state.failures = Math.max(0, state.failures - 1);
            }
            this.circuitBreakerState.set(url, state);
        }
    }

    /**
     * Helper methods
     */
    _generateSignature(body, secret, prefix = 'sha256=') {
        const algorithm = prefix.replace('=', '');
        const hmac = crypto.createHmac(algorithm, secret);
        hmac.update(body, 'utf8');
        return prefix + hmac.digest('hex');
    }

    _calculateRetryDelay(attempt, baseDelay, strategy) {
        if (strategy === 'exponential') {
            return baseDelay * Math.pow(2, attempt - 1);
        }
        return baseDelay * attempt; // linear
    }

    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    _logRequest(logEntry) {
        this.requestLog.push(logEntry);
        // Keep only last 1000 entries
        if (this.requestLog.length > 1000) {
            this.requestLog.shift();
        }
    }

    _loadWebhookTemplates() {
        return {
            slack: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                payload: {
                    text: '{{message}}',
                    username: '{{username}}',
                    channel: '{{channel}}',
                    icon_emoji: '{{icon_emoji}}'
                },
                expectedStatus: [200]
            },
            discord: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                payload: {
                    content: '{{message}}',
                    username: '{{username}}',
                    avatar_url: '{{avatar_url}}'
                },
                expectedStatus: [200, 204]
            },
            teams: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                payload: {
                    text: '{{message}}',
                    title: '{{title}}'
                },
                expectedStatus: [200]
            },
            github: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                payload: {
                    event_type: '{{event_type}}',
                    client_payload: '{{payload}}'
                },
                expectedStatus: [204]
            },
            generic: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                payload: {
                    message: '{{message}}',
                    timestamp: '{{timestamp}}',
                    source: 'UC2'
                },
                expectedStatus: [200, 201, 202, 204]
            }
        };
    }

    _compileTemplate(template, data) {
        let compiled = JSON.stringify(template);

        Object.keys(data).forEach(key => {
            const regex = new RegExp(`{{${key}}}`, 'g');
            compiled = compiled.replace(regex, data[key]);
        });

        // Replace any remaining placeholders with empty strings
        compiled = compiled.replace(/\{\{[^}]+\}\}/g, '');

        return JSON.parse(compiled);
    }

    /**
     * Mock implementations
     */
    _mockSendWebhook(url, method, payload, headers) {
        const requestId = crypto.randomUUID();
        return {
            requestId: requestId,
            url: url,
            method: method,
            statusCode: 200,
            headers: { 'content-type': 'application/json' },
            body: '{"success": true}',
            responseTime: Math.floor(Math.random() * 500) + 100,
            attempt: 1,
            success: true,
            note: 'Mock mode - webhook would be sent in real implementation'
        };
    }

    _mockTestWebhook(url) {
        return {
            url: url,
            available: true,
            statusCode: 200,
            responseTime: Math.floor(Math.random() * 200) + 50,
            headers: { 'content-type': 'application/json' },
            testResult: 'success',
            note: 'Mock mode - webhook test would be performed in real implementation'
        };
    }

    _mockScheduleWebhook(params) {
        return {
            scheduled: true,
            scheduleId: crypto.randomUUID(),
            scheduleTime: params.scheduleTime,
            cronExpression: params.cronExpression,
            recurring: params.recurring || false,
            status: 'pending',
            note: 'Mock mode - webhook would be scheduled in real implementation'
        };
    }

    /**
     * Get webhook logs
     */
    getLogs(limit = 100) {
        return this.requestLog.slice(-limit);
    }

    /**
     * Get circuit breaker status
     */
    getCircuitBreakerStatus() {
        const status = {};
        this.circuitBreakerState.forEach((state, url) => {
            status[url] = { ...state };
        });
        return status;
    }

    /**
     * Reset circuit breaker for URL
     */
    resetCircuitBreaker(url) {
        this.circuitBreakerState.delete(url);
        return { url, reset: true };
    }

    /**
     * Get tool information
     */
    getInfo() {
        return {
            name: this.name,
            version: this.version,
            description: this.description,
            category: this.category,
            permissions: this.permissions,
            schema: this.schema,
            mockMode: this.mockMode,
            supportedActions: ['send', 'test', 'verify', 'batch', 'schedule', 'template'],
            templates: Object.keys(this.templates),
            examples: [
                {
                    description: 'Send webhook with retry logic',
                    input: {
                        action: 'send',
                        url: 'https://api.example.com/webhook',
                        payload: { message: 'Hello from UC2' },
                        retryAttempts: 3
                    },
                    output: { success: true, statusCode: 200, responseTime: 250 }
                },
                {
                    description: 'Send batch webhooks',
                    input: {
                        action: 'batch',
                        batchUrls: ['https://api1.com/webhook', 'https://api2.com/webhook'],
                        payload: { alert: 'System update' }
                    },
                    output: { successCount: 2, failureCount: 0, batchComplete: true }
                },
                {
                    description: 'Use Slack template',
                    input: {
                        action: 'template',
                        template: 'slack',
                        url: 'https://hooks.slack.com/services/...',
                        templateData: { message: 'UC2 Alert', channel: '#alerts' }
                    },
                    output: { success: true, statusCode: 200 }
                }
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        if (!this.name || typeof this.name !== 'string') {
            issues.push('Tool name is required and must be a string');
        }

        if (!this.version || typeof this.version !== 'string') {
            issues.push('Tool version is required and must be a string');
        }

        if (!this.schema || typeof this.schema !== 'object') {
            issues.push('Tool schema is required and must be an object');
        }

        if (!this.templates || typeof this.templates !== 'object') {
            issues.push('Templates must be an object');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebhookTriggerTool;
} else if (typeof exports !== 'undefined') {
    exports.WebhookTriggerTool = WebhookTriggerTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = WebhookTriggerTool;
}