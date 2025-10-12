/**
 * Web Search Tool - Search the web via API
 * UC2 Internal Tool v1.0.0
 */

const https = require('https');
const http = require('http');

class WebSearchTool {
    constructor() {
        this.name = 'webSearch';
        this.version = '1.0.0';
        this.description = 'Search the web using various search engines and APIs';
        this.category = 'search';
        this.permissions = ['network', 'api'];
        this.schema = {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Search query string'
                },
                engine: {
                    type: 'string',
                    enum: ['duckduckgo', 'searx', 'google', 'bing'],
                    default: 'duckduckgo',
                    description: 'Search engine to use'
                },
                limit: {
                    type: 'number',
                    default: 10,
                    minimum: 1,
                    maximum: 50,
                    description: 'Maximum number of results to return'
                },
                safe: {
                    type: 'boolean',
                    default: true,
                    description: 'Enable safe search filter'
                },
                lang: {
                    type: 'string',
                    default: 'en',
                    description: 'Language code for search results'
                }
            },
            required: ['query']
        };

        // Configure search engines
        this.engines = {
            duckduckgo: {
                baseUrl: 'https://api.duckduckgo.com',
                free: true
            },
            searx: {
                baseUrl: process.env.SEARX_URL || 'https://searx.be',
                free: true
            },
            google: {
                baseUrl: 'https://www.googleapis.com/customsearch/v1',
                apiKey: process.env.GOOGLE_SEARCH_API_KEY,
                searchEngineId: process.env.GOOGLE_SEARCH_ENGINE_ID,
                free: false
            },
            bing: {
                baseUrl: 'https://api.bing.microsoft.com/v7.0/search',
                apiKey: process.env.BING_SEARCH_API_KEY,
                free: false
            }
        };
    }

    /**
     * Execute web search
     */
    async execute(params, context = {}) {
        try {
            const { query, engine = 'duckduckgo', limit = 10, safe = true, lang = 'en' } = params;

            // Input validation
            if (!query || typeof query !== 'string') {
                throw new Error('Search query is required and must be a string');
            }

            if (query.length > 500) {
                throw new Error('Search query is too long (max 500 characters)');
            }

            // Check if engine is supported
            if (!this.engines[engine]) {
                throw new Error(`Unsupported search engine: ${engine}`);
            }

            const startTime = process.hrtime.bigint();

            // Perform search based on engine
            let results;
            switch (engine) {
                case 'duckduckgo':
                    results = await this._searchDuckDuckGo(query, limit, safe);
                    break;
                case 'searx':
                    results = await this._searchSearx(query, limit, safe, lang);
                    break;
                case 'google':
                    results = await this._searchGoogle(query, limit, safe, lang);
                    break;
                case 'bing':
                    results = await this._searchBing(query, limit, safe, lang);
                    break;
                default:
                    throw new Error(`Search engine ${engine} not implemented`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to milliseconds

            return {
                success: true,
                query: query,
                engine: engine,
                results: results,
                count: results.length,
                executionTime: `${executionTime.toFixed(2)}ms`,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                query: params.query,
                engine: params.engine || 'duckduckgo',
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Search using DuckDuckGo Instant Answer API
     * @private
     */
    async _searchDuckDuckGo(query, limit, safe) {
        const encodedQuery = encodeURIComponent(query);
        const url = `https://api.duckduckgo.com/?q=${encodedQuery}&format=json&no_redirect=1&skip_disambig=1&safe_search=${safe ? 'strict' : 'off'}`;

        const data = await this._makeHttpRequest(url);
        const results = [];

        // Parse DuckDuckGo response
        if (data.AbstractText && data.AbstractURL) {
            results.push({
                title: data.AbstractSource || 'DuckDuckGo Instant Answer',
                snippet: data.AbstractText,
                url: data.AbstractURL,
                source: 'instant_answer'
            });
        }

        // Add related topics
        if (data.RelatedTopics && Array.isArray(data.RelatedTopics)) {
            for (const topic of data.RelatedTopics.slice(0, limit - 1)) {
                if (topic.Text && topic.FirstURL) {
                    results.push({
                        title: topic.Text.split(' - ')[0] || topic.Text.substring(0, 100),
                        snippet: topic.Text,
                        url: topic.FirstURL,
                        source: 'related_topic'
                    });
                }
            }
        }

        return results.slice(0, limit);
    }

    /**
     * Search using SearX instance
     * @private
     */
    async _searchSearx(query, limit, safe, lang) {
        const encodedQuery = encodeURIComponent(query);
        const safeValue = safe ? 1 : 0;
        const url = `${this.engines.searx.baseUrl}/search?q=${encodedQuery}&format=json&safesearch=${safeValue}&language=${lang}`;

        try {
            const data = await this._makeHttpRequest(url, {
                timeout: 10000,
                headers: {
                    'User-Agent': 'UC2-WebSearchTool/1.0.0'
                }
            });

            const results = [];
            if (data.results && Array.isArray(data.results)) {
                for (const item of data.results.slice(0, limit)) {
                    results.push({
                        title: item.title || 'No Title',
                        snippet: item.content || item.title || '',
                        url: item.url,
                        source: 'searx',
                        engine: item.engine
                    });
                }
            }

            return results;
        } catch (error) {
            // Fallback to DuckDuckGo if SearX fails
            console.warn('SearX search failed, falling back to DuckDuckGo:', error.message);
            return await this._searchDuckDuckGo(query, limit, safe);
        }
    }

    /**
     * Search using Google Custom Search API
     * @private
     */
    async _searchGoogle(query, limit, safe, lang) {
        const config = this.engines.google;
        if (!config.apiKey || !config.searchEngineId) {
            throw new Error('Google Search API requires API key and Search Engine ID');
        }

        const encodedQuery = encodeURIComponent(query);
        const safeValue = safe ? 'active' : 'off';
        const url = `${config.baseUrl}?q=${encodedQuery}&cx=${config.searchEngineId}&key=${config.apiKey}&num=${limit}&safe=${safeValue}&lr=lang_${lang}`;

        const data = await this._makeHttpRequest(url);
        const results = [];

        if (data.items && Array.isArray(data.items)) {
            for (const item of data.items) {
                results.push({
                    title: item.title,
                    snippet: item.snippet || '',
                    url: item.link,
                    source: 'google'
                });
            }
        }

        return results;
    }

    /**
     * Search using Bing Search API
     * @private
     */
    async _searchBing(query, limit, safe, lang) {
        const config = this.engines.bing;
        if (!config.apiKey) {
            throw new Error('Bing Search API requires API key');
        }

        const encodedQuery = encodeURIComponent(query);
        const safeValue = safe ? 'Strict' : 'Off';
        const url = `${config.baseUrl}?q=${encodedQuery}&count=${limit}&safeSearch=${safeValue}&mkt=${lang}-US`;

        const data = await this._makeHttpRequest(url, {
            headers: {
                'Ocp-Apim-Subscription-Key': config.apiKey
            }
        });

        const results = [];
        if (data.webPages && data.webPages.value) {
            for (const item of data.webPages.value) {
                results.push({
                    title: item.name,
                    snippet: item.snippet || '',
                    url: item.url,
                    source: 'bing'
                });
            }
        }

        return results;
    }

    /**
     * Make HTTP request with timeout and error handling
     * @private
     */
    _makeHttpRequest(url, options = {}) {
        return new Promise((resolve, reject) => {
            const isHttps = url.startsWith('https');
            const client = isHttps ? https : http;
            const timeout = options.timeout || 10000;

            const req = client.request(url, {
                method: 'GET',
                timeout: timeout,
                headers: {
                    'User-Agent': 'UC2-WebSearchTool/1.0.0',
                    'Accept': 'application/json',
                    ...options.headers
                }
            }, (res) => {
                let data = '';

                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        if (res.statusCode >= 400) {
                            reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
                            return;
                        }

                        const parsed = JSON.parse(data);
                        resolve(parsed);
                    } catch (error) {
                        reject(new Error(`Failed to parse JSON response: ${error.message}`));
                    }
                });
            });

            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });

            req.end();
        });
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
            supportedEngines: Object.keys(this.engines),
            examples: [
                {
                    description: 'Basic web search',
                    input: { query: 'UC2 artificial intelligence' },
                    output: { count: 10, engine: 'duckduckgo' }
                },
                {
                    description: 'Limited results with specific engine',
                    input: { query: 'machine learning trends', engine: 'searx', limit: 5 },
                    output: { count: 5, engine: 'searx' }
                }
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        // Check if at least one search engine is properly configured
        let hasValidEngine = false;
        for (const [name, config] of Object.entries(this.engines)) {
            if (config.free || (config.apiKey && config.apiKey.length > 0)) {
                hasValidEngine = true;
                break;
            }
        }

        if (!hasValidEngine) {
            issues.push('No search engines are properly configured');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

module.exports = WebSearchTool;