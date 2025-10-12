/**
 * API Caller Tool - Universal REST API Integration
 * UC2 Internal Tool v1.0.0
 *
 * Provides secure, flexible API calling capabilities with comprehensive
 * authentication, error handling, and response processing.
 */

const axios = require('axios');
const crypto = require('crypto');

class ApiCallerTool {
    constructor() {
        this.name = 'apiCaller';
        this.version = '1.0.0';
        this.description = 'Universal REST API client with authentication and error handling';
        this.category = 'integration';
        this.permissions = ['network', 'api'];

        this.schema = {
            type: 'object',
            properties: {
                url: {
                    type: 'string',
                    format: 'uri',
                    description: 'Target API endpoint URL'
                },
                method: {
                    type: 'string',
                    enum: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],
                    default: 'GET',
                    description: 'HTTP method to use'
                },
                headers: {
                    type: 'object',
                    description: 'HTTP headers to include',
                    additionalProperties: {
                        type: 'string'
                    }
                },
                data: {
                    type: ['object', 'string', 'array'],
                    description: 'Request body data (for POST, PUT, PATCH)'
                },
                params: {
                    type: 'object',
                    description: 'URL query parameters',
                    additionalProperties: {
                        type: ['string', 'number', 'boolean']
                    }
                },
                auth: {
                    type: 'object',
                    description: 'Authentication configuration',
                    properties: {
                        type: {
                            type: 'string',
                            enum: ['bearer', 'basic', 'apikey', 'oauth2', 'custom'],
                            description: 'Authentication type'
                        },
                        token: {
                            type: 'string',
                            description: 'Bearer token or API key'
                        },
                        username: {
                            type: 'string',
                            description: 'Username for basic auth'
                        },
                        password: {
                            type: 'string',
                            description: 'Password for basic auth'
                        },
                        header: {
                            type: 'string',
                            description: 'Custom header name for API key'
                        },
                        prefix: {
                            type: 'string',
                            description: 'Token prefix (e.g., "Bearer ", "Token ")'
                        }
                    }
                },
                timeout: {
                    type: 'number',
                    default: 30000,
                    minimum: 1000,
                    maximum: 300000,
                    description: 'Request timeout in milliseconds (1s - 5min)'
                },
                retries: {
                    type: 'number',
                    default: 2,
                    minimum: 0,
                    maximum: 5,
                    description: 'Number of retry attempts for failed requests'
                },
                validateStatus: {
                    type: 'array',
                    items: {
                        type: 'number'
                    },
                    description: 'HTTP status codes to consider successful',
                    default: [200, 201, 202, 204]
                },
                responseFormat: {
                    type: 'string',
                    enum: ['json', 'text', 'stream', 'arraybuffer'],
                    default: 'json',
                    description: 'Expected response format'
                },
                followRedirects: {
                    type: 'boolean',
                    default: true,
                    description: 'Whether to follow HTTP redirects'
                },
                maxContentLength: {
                    type: 'number',
                    default: 50 * 1024 * 1024, // 50MB
                    description: 'Maximum response content length in bytes'
                }
            },
            required: ['url']
        };

        // Rate limiting and caching
        this.rateLimits = new Map();
        this.responseCache = new Map();
        this.maxCacheSize = 100;
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes

        // Security settings
        this.security = {
            allowedDomains: [], // Empty = allow all, populated = whitelist
            blockedDomains: [
                'localhost', '127.0.0.1', '0.0.0.0',
                '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'
            ],
            maxRedirects: 5,
            userAgent: 'UC2-ApiCaller/1.0.0'
        };

        // Common API configurations
        this.presets = {
            openai: {
                baseURL: 'https://api.openai.com/v1',
                headers: {
                    'Content-Type': 'application/json'
                },
                auth: {
                    type: 'bearer',
                    header: 'Authorization'
                }
            },
            github: {
                baseURL: 'https://api.github.com',
                headers: {
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'UC2-ApiCaller/1.0.0'
                },
                auth: {
                    type: 'bearer',
                    header: 'Authorization'
                }
            },
            slack: {
                baseURL: 'https://slack.com/api',
                headers: {
                    'Content-Type': 'application/json'
                },
                auth: {
                    type: 'bearer',
                    header: 'Authorization'
                }
            },
            stripe: {
                baseURL: 'https://api.stripe.com/v1',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                auth: {
                    type: 'bearer',
                    header: 'Authorization'
                }
            }
        };
    }

    /**
     * Execute API call with comprehensive error handling
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate and sanitize parameters
            const config = await this.validateAndPrepareRequest(params);

            // Check rate limits
            await this.checkRateLimit(config.url);

            // Check cache first
            const cacheKey = this.generateCacheKey(config);
            const cached = this.getFromCache(cacheKey);
            if (cached) {
                return {
                    success: true,
                    data: cached.data,
                    status: cached.status,
                    headers: cached.headers,
                    cached: true,
                    executionTime: `${Date.now() - startTime}ms`
                };
            }

            // Make the API call with retries
            const response = await this.makeRequestWithRetry(config);

            // Process response
            const result = await this.processResponse(response, config);

            // Cache successful responses
            if (result.success && config.method === 'GET') {
                this.addToCache(cacheKey, result);
            }

            // Update rate limit tracking
            this.updateRateLimit(config.url);

            result.executionTime = `${Date.now() - startTime}ms`;
            return result;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                errorType: error.constructor.name,
                status: error.response?.status || 0,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    /**
     * Validate request parameters and prepare axios config
     */
    async validateAndPrepareRequest(params) {
        // Basic validation
        if (!params.url) {
            throw new Error('URL is required');
        }

        // Security validation
        await this.validateSecurity(params.url);

        // Prepare axios configuration
        const config = {
            url: params.url,
            method: (params.method || 'GET').toUpperCase(),
            timeout: params.timeout || 30000,
            maxRedirects: Math.min(params.followRedirects ? this.security.maxRedirects : 0, 10),
            maxContentLength: params.maxContentLength || 50 * 1024 * 1024,
            validateStatus: (status) => {
                const validStatuses = params.validateStatus || [200, 201, 202, 204];
                return validStatuses.includes(status);
            },
            responseType: this.mapResponseFormat(params.responseFormat || 'json')
        };

        // Add headers
        config.headers = {
            'User-Agent': this.security.userAgent,
            'Accept': this.getDefaultAcceptHeader(params.responseFormat),
            ...params.headers
        };

        // Add query parameters
        if (params.params) {
            config.params = params.params;
        }

        // Add request body
        if (params.data && ['POST', 'PUT', 'PATCH'].includes(config.method)) {
            config.data = params.data;

            // Set appropriate content-type if not specified
            if (!config.headers['Content-Type']) {
                config.headers['Content-Type'] = typeof params.data === 'string'
                    ? 'text/plain'
                    : 'application/json';
            }
        }

        // Configure authentication
        if (params.auth) {
            this.configureAuthentication(config, params.auth);
        }

        return config;
    }

    /**
     * Configure authentication based on type
     */
    configureAuthentication(config, auth) {
        switch (auth.type) {
            case 'bearer':
                const prefix = auth.prefix || 'Bearer ';
                config.headers.Authorization = `${prefix}${auth.token}`;
                break;

            case 'basic':
                if (!auth.username || !auth.password) {
                    throw new Error('Basic auth requires username and password');
                }
                const credentials = Buffer.from(`${auth.username}:${auth.password}`).toString('base64');
                config.headers.Authorization = `Basic ${credentials}`;
                break;

            case 'apikey':
                const headerName = auth.header || 'X-API-Key';
                const tokenPrefix = auth.prefix || '';
                config.headers[headerName] = `${tokenPrefix}${auth.token}`;
                break;

            case 'custom':
                if (auth.header && auth.token) {
                    const customPrefix = auth.prefix || '';
                    config.headers[auth.header] = `${customPrefix}${auth.token}`;
                }
                break;

            case 'oauth2':
                // OAuth2 typically uses bearer tokens
                config.headers.Authorization = `Bearer ${auth.token}`;
                break;

            default:
                throw new Error(`Unsupported authentication type: ${auth.type}`);
        }
    }

    /**
     * Security validation for URLs
     */
    async validateSecurity(url) {
        try {
            const urlObj = new URL(url);

            // Check protocol
            if (!['http:', 'https:'].includes(urlObj.protocol)) {
                throw new Error(`Unsupported protocol: ${urlObj.protocol}`);
            }

            // Check against blocked domains
            if (this.security.blockedDomains.some(blocked =>
                urlObj.hostname.includes(blocked) || url.includes(blocked))) {
                throw new Error(`Blocked domain: ${urlObj.hostname}`);
            }

            // Check against allowed domains (if configured)
            if (this.security.allowedDomains.length > 0) {
                if (!this.security.allowedDomains.some(allowed =>
                    urlObj.hostname.includes(allowed))) {
                    throw new Error(`Domain not in allowlist: ${urlObj.hostname}`);
                }
            }

            // Prevent SSRF attacks
            if (this.isPrivateIP(urlObj.hostname)) {
                throw new Error(`Private IP address not allowed: ${urlObj.hostname}`);
            }

        } catch (error) {
            if (error.message.includes('Invalid URL')) {
                throw new Error('Invalid URL format');
            }
            throw error;
        }
    }

    /**
     * Check if hostname is a private IP address
     */
    isPrivateIP(hostname) {
        const privateRanges = [
            /^127\./, // 127.0.0.0/8
            /^10\./, // 10.0.0.0/8
            /^172\.(1[6-9]|2[0-9]|3[01])\./, // 172.16.0.0/12
            /^192\.168\./, // 192.168.0.0/16
            /^localhost$/i,
            /^::1$/, // IPv6 loopback
            /^fe80::/i // IPv6 link-local
        ];

        return privateRanges.some(range => range.test(hostname));
    }

    /**
     * Make HTTP request with retry logic
     */
    async makeRequestWithRetry(config) {
        const maxRetries = config.retries || 2;
        let lastError;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const response = await axios(config);
                return response;
            } catch (error) {
                lastError = error;

                // Don't retry on client errors (4xx)
                if (error.response && error.response.status >= 400 && error.response.status < 500) {
                    break;
                }

                // Don't retry on last attempt
                if (attempt === maxRetries) {
                    break;
                }

                // Exponential backoff
                const delay = Math.pow(2, attempt) * 1000 + Math.random() * 1000;
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }

        throw lastError;
    }

    /**
     * Process API response
     */
    async processResponse(response, config) {
        const result = {
            success: true,
            status: response.status,
            statusText: response.statusText,
            headers: response.headers,
            data: response.data
        };

        // Add metadata for certain content types
        if (response.headers['content-type']) {
            result.contentType = response.headers['content-type'];
        }

        if (response.headers['content-length']) {
            result.contentLength = parseInt(response.headers['content-length']);
        }

        // Handle different response formats
        if (config.responseType === 'stream') {
            result.data = '[Stream Data]';
            result.streamSize = response.headers['content-length'] || 'unknown';
        } else if (config.responseType === 'arraybuffer') {
            result.data = `[Binary Data: ${response.data.byteLength} bytes]`;
            result.binarySize = response.data.byteLength;
        }

        return result;
    }

    /**
     * Rate limiting implementation
     */
    async checkRateLimit(url) {
        const domain = new URL(url).hostname;
        const now = Date.now();

        if (!this.rateLimits.has(domain)) {
            this.rateLimits.set(domain, {
                requests: 0,
                windowStart: now,
                maxRequests: 100, // per minute
                windowSize: 60000 // 1 minute
            });
        }

        const limit = this.rateLimits.get(domain);

        // Reset window if expired
        if (now - limit.windowStart >= limit.windowSize) {
            limit.requests = 0;
            limit.windowStart = now;
        }

        // Check if rate limit exceeded
        if (limit.requests >= limit.maxRequests) {
            const waitTime = limit.windowStart + limit.windowSize - now;
            throw new Error(`Rate limit exceeded for ${domain}. Wait ${waitTime}ms`);
        }
    }

    /**
     * Update rate limit counter
     */
    updateRateLimit(url) {
        const domain = new URL(url).hostname;
        const limit = this.rateLimits.get(domain);
        if (limit) {
            limit.requests++;
        }
    }

    /**
     * Cache management
     */
    generateCacheKey(config) {
        const key = `${config.method}:${config.url}:${JSON.stringify(config.params || {})}`;
        return crypto.createHash('sha256').update(key).digest('hex').substring(0, 16);
    }

    getFromCache(key) {
        const entry = this.responseCache.get(key);
        if (entry && Date.now() - entry.timestamp < this.cacheTimeout) {
            return entry;
        }

        if (entry) {
            this.responseCache.delete(key);
        }

        return null;
    }

    addToCache(key, result) {
        // Manage cache size
        if (this.responseCache.size >= this.maxCacheSize) {
            const firstKey = this.responseCache.keys().next().value;
            this.responseCache.delete(firstKey);
        }

        this.responseCache.set(key, {
            ...result,
            timestamp: Date.now()
        });
    }

    /**
     * Helper methods
     */
    mapResponseFormat(format) {
        const mapping = {
            'json': 'json',
            'text': 'text',
            'stream': 'stream',
            'arraybuffer': 'arraybuffer'
        };
        return mapping[format] || 'json';
    }

    getDefaultAcceptHeader(format) {
        const headers = {
            'json': 'application/json',
            'text': 'text/plain',
            'stream': '*/*',
            'arraybuffer': 'application/octet-stream'
        };
        return headers[format] || 'application/json';
    }

    /**
     * Quick preset configurations
     */
    async executeWithPreset(presetName, endpoint, params = {}) {
        const preset = this.presets[presetName];
        if (!preset) {
            throw new Error(`Unknown preset: ${presetName}`);
        }

        const url = endpoint.startsWith('http') ? endpoint : `${preset.baseURL}${endpoint}`;

        const mergedParams = {
            url,
            headers: { ...preset.headers, ...params.headers },
            ...params
        };

        if (preset.auth && !params.auth) {
            mergedParams.auth = preset.auth;
        }

        return this.execute(mergedParams);
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
            features: [
                'Multiple HTTP methods (GET, POST, PUT, PATCH, DELETE)',
                'Comprehensive authentication (Bearer, Basic, API Key, OAuth2)',
                'Automatic retries with exponential backoff',
                'Response caching for GET requests',
                'Rate limiting per domain',
                'Security validation (SSRF protection, domain filtering)',
                'Multiple response formats (JSON, text, binary, stream)',
                'API presets for common services',
                'Comprehensive error handling'
            ],
            presets: Object.keys(this.presets),
            rateLimits: Array.from(this.rateLimits.entries()).map(([domain, limit]) => ({
                domain,
                requests: limit.requests,
                maxRequests: limit.maxRequests,
                windowStart: new Date(limit.windowStart).toISOString()
            })),
            cacheStats: {
                size: this.responseCache.size,
                maxSize: this.maxCacheSize,
                timeout: `${this.cacheTimeout / 1000}s`
            }
        };
    }

    /**
     * Clear caches and reset rate limits
     */
    clearCache() {
        this.responseCache.clear();
        this.rateLimits.clear();
        return { success: true, message: 'Cache and rate limits cleared' };
    }
}

module.exports = ApiCallerTool;