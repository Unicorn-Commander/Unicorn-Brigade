/**
 * Tool Executor Service - Handle tool loading and execution
 * UC2 Backend Service v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');
const vm = require('vm');
const { PrismaClient } = require('@prisma/client');

class ToolExecutorService {
    constructor() {
        this.loadedTools = new Map();
        this.executionHistory = [];
        this.maxHistorySize = 1000;

        // Security settings
        this.security = {
            maxExecutionTime: 30000, // 30 seconds
            maxMemoryUsage: 100 * 1024 * 1024, // 100MB
            allowedOrigins: ['internal', 'trusted'],
            rateLimits: {
                perTool: 100,        // per hour
                perUser: 1000,       // per hour
                global: 10000        // per hour
            }
        };

        // Tool paths
        this.toolPaths = {
            internal: path.join(__dirname, '../../core/tools/internal'),
            external: path.join(__dirname, '../../core/tools/external'),
            agents: path.join(__dirname, '../../core/agents')
        };

        // Permission matrix
        this.permissions = {
            basic: ['calculator'],
            network: ['webSearch'],
            filesystem: ['filesystem'],
            database: ['database'],
            admin: ['*']
        };

        // Initialize rate limiting
        this.rateLimiter = new Map();
        this.setupRateLimitCleanup();
    }

    /**
     * Initialize the tool executor
     */
    async initialize() {
        try {
            // Load internal tools
            await this.loadInternalTools();

            // Load external tools
            await this.loadExternalTools();

            console.log(`✅ ToolExecutor initialized with ${this.loadedTools.size} tools`);
            return {
                success: true,
                toolsLoaded: this.loadedTools.size,
                availableTools: Array.from(this.loadedTools.keys())
            };
        } catch (error) {
            console.error('❌ Failed to initialize ToolExecutor:', error);
            throw error;
        }
    }

    /**
     * Load internal tools from the tools directory
     */
    async loadInternalTools() {
        try {
            const internalPath = this.toolPaths.internal;
            const files = await fs.readdir(internalPath);

            for (const file of files) {
                if (file.endsWith('.js')) {
                    const toolPath = path.join(internalPath, file);
                    await this.loadTool(toolPath, 'internal');
                }
            }
        } catch (error) {
            console.warn('⚠️ Could not load internal tools:', error.message);
        }
    }

    /**
     * Load external tools
     */
    async loadExternalTools() {
        try {
            const externalPath = this.toolPaths.external;

            // Check if external tools directory exists
            try {
                await fs.access(externalPath);
            } catch {
                // Create directory if it doesn't exist
                await fs.mkdir(externalPath, { recursive: true });
                return;
            }

            const files = await fs.readdir(externalPath);

            for (const file of files) {
                if (file.endsWith('.js')) {
                    const toolPath = path.join(externalPath, file);
                    await this.loadTool(toolPath, 'external');
                }
            }
        } catch (error) {
            console.warn('⚠️ Could not load external tools:', error.message);
        }
    }

    /**
     * Load a single tool
     */
    async loadTool(toolPath, origin = 'internal') {
        try {
            // Clear require cache to allow hot reloading
            delete require.cache[require.resolve(toolPath)];

            const ToolClass = require(toolPath);
            const tool = new ToolClass();

            // Validate tool structure
            const validation = tool.validate ? tool.validate() : { valid: true, issues: [] };
            if (!validation.valid) {
                throw new Error(`Tool validation failed: ${validation.issues.join(', ')}`);
            }

            // Add metadata
            tool._metadata = {
                path: toolPath,
                origin: origin,
                loadedAt: new Date().toISOString(),
                version: tool.version || '1.0.0'
            };

            this.loadedTools.set(tool.name, tool);
            console.log(`📦 Loaded tool: ${tool.name} v${tool.version} (${origin})`);

        } catch (error) {
            console.error(`❌ Failed to load tool from ${toolPath}:`, error.message);
        }
    }

    /**
     * Execute a tool with parameters
     */
    async executeTool(toolName, parameters = {}, context = {}) {
        const startTime = process.hrtime.bigint();
        const executionId = this.generateExecutionId();

        try {
            // Get the tool
            const tool = this.loadedTools.get(toolName);
            if (!tool) {
                throw new Error(`Tool '${toolName}' not found`);
            }

            // Check permissions
            await this.checkPermissions(tool, context);

            // Rate limiting
            await this.checkRateLimit(toolName, context);

            // Parameter validation
            const validatedParams = await this.validateParameters(tool, parameters);

            // Execute the tool in a controlled environment
            const result = await this.executeInSandbox(tool, validatedParams, context);

            // Record execution
            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to ms

            const executionRecord = {
                id: executionId,
                toolName: toolName,
                parameters: validatedParams,
                result: result,
                executionTime: executionTime,
                context: {
                    userId: context.userId,
                    agentId: context.agentId,
                    sessionId: context.sessionId
                },
                timestamp: new Date().toISOString(),
                success: result.success !== false
            };

            this.recordExecution(executionRecord);

            return {
                ...result,
                executionId: executionId,
                executionTime: `${executionTime.toFixed(2)}ms`,
                toolInfo: {
                    name: tool.name,
                    version: tool.version,
                    category: tool.category
                }
            };

        } catch (error) {
            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000;

            const errorRecord = {
                id: executionId,
                toolName: toolName,
                parameters: parameters,
                error: error.message,
                executionTime: executionTime,
                context: {
                    userId: context.userId,
                    agentId: context.agentId,
                    sessionId: context.sessionId
                },
                timestamp: new Date().toISOString(),
                success: false
            };

            this.recordExecution(errorRecord);

            return {
                success: false,
                error: error.message,
                executionId: executionId,
                executionTime: `${executionTime.toFixed(2)}ms`,
                toolName: toolName
            };
        }
    }

    /**
     * Execute tool in a controlled sandbox environment
     */
    async executeInSandbox(tool, parameters, context) {
        return new Promise((resolve, reject) => {
            // Set execution timeout
            const timeout = setTimeout(() => {
                reject(new Error(`Tool execution timed out after ${this.security.maxExecutionTime}ms`));
            }, this.security.maxExecutionTime);

            // Execute the tool
            tool.execute(parameters, context)
                .then(result => {
                    clearTimeout(timeout);
                    resolve(result);
                })
                .catch(error => {
                    clearTimeout(timeout);
                    reject(error);
                });
        });
    }

    /**
     * Check user permissions for tool execution
     */
    async checkPermissions(tool, context) {
        const userRole = context.user?.role || 'basic';
        const userPermissions = context.user?.permissions ? JSON.parse(context.user.permissions) : [];

        // Admin users have access to everything
        if (userRole === 'admin' || userPermissions.includes('tools:*')) {
            return true;
        }

        // Check if user has permission for this tool's required permissions
        const toolPermissions = tool.permissions || ['basic'];

        for (const permission of toolPermissions) {
            const allowedTools = this.permissions[permission] || [];

            if (allowedTools.includes('*') || allowedTools.includes(tool.name)) {
                // Check if user has this permission level
                if (userPermissions.includes(`tools:${permission}`) || userPermissions.includes(permission)) {
                    return true;
                }
            }
        }

        throw new Error(`Insufficient permissions to execute tool '${tool.name}'. Required: ${toolPermissions.join(', ')}`);
    }

    /**
     * Rate limiting check
     */
    async checkRateLimit(toolName, context) {
        const now = Date.now();
        const hour = Math.floor(now / (1000 * 60 * 60));
        const userId = context.userId || 'anonymous';

        // Initialize rate limit counters
        if (!this.rateLimiter.has(hour)) {
            this.rateLimiter.set(hour, {
                global: 0,
                users: new Map(),
                tools: new Map()
            });
        }

        const hourlyLimits = this.rateLimiter.get(hour);

        // Check global limit
        if (hourlyLimits.global >= this.security.rateLimits.global) {
            throw new Error('Global rate limit exceeded. Please try again later.');
        }

        // Check per-user limit
        const userCount = hourlyLimits.users.get(userId) || 0;
        if (userCount >= this.security.rateLimits.perUser) {
            throw new Error('User rate limit exceeded. Please try again later.');
        }

        // Check per-tool limit
        const toolCount = hourlyLimits.tools.get(toolName) || 0;
        if (toolCount >= this.security.rateLimits.perTool) {
            throw new Error(`Rate limit exceeded for tool '${toolName}'. Please try again later.`);
        }

        // Increment counters
        hourlyLimits.global++;
        hourlyLimits.users.set(userId, userCount + 1);
        hourlyLimits.tools.set(toolName, toolCount + 1);
    }

    /**
     * Validate tool parameters against schema
     */
    async validateParameters(tool, parameters) {
        if (!tool.schema) {
            return parameters;
        }

        // Basic validation - in production, use a proper JSON schema validator
        const schema = tool.schema;
        const validated = { ...parameters };

        // Check required parameters
        if (schema.required) {
            for (const requiredParam of schema.required) {
                if (!(requiredParam in validated)) {
                    throw new Error(`Missing required parameter: ${requiredParam}`);
                }
            }
        }

        // Apply defaults and validate types
        if (schema.properties) {
            for (const [paramName, paramSchema] of Object.entries(schema.properties)) {
                if (paramSchema.default !== undefined && !(paramName in validated)) {
                    validated[paramName] = paramSchema.default;
                }

                if (paramName in validated) {
                    // Basic type checking
                    const value = validated[paramName];
                    const expectedType = paramSchema.type;

                    if (expectedType === 'string' && typeof value !== 'string') {
                        throw new Error(`Parameter '${paramName}' must be a string`);
                    }
                    if (expectedType === 'number' && typeof value !== 'number') {
                        throw new Error(`Parameter '${paramName}' must be a number`);
                    }
                    if (expectedType === 'boolean' && typeof value !== 'boolean') {
                        throw new Error(`Parameter '${paramName}' must be a boolean`);
                    }
                    if (expectedType === 'object' && typeof value !== 'object') {
                        throw new Error(`Parameter '${paramName}' must be an object`);
                    }

                    // Check enum values
                    if (paramSchema.enum && !paramSchema.enum.includes(value)) {
                        throw new Error(`Parameter '${paramName}' must be one of: ${paramSchema.enum.join(', ')}`);
                    }

                    // Check numeric limits
                    if (expectedType === 'number') {
                        if (paramSchema.minimum !== undefined && value < paramSchema.minimum) {
                            throw new Error(`Parameter '${paramName}' must be at least ${paramSchema.minimum}`);
                        }
                        if (paramSchema.maximum !== undefined && value > paramSchema.maximum) {
                            throw new Error(`Parameter '${paramName}' must be at most ${paramSchema.maximum}`);
                        }
                    }
                }
            }
        }

        return validated;
    }

    /**
     * Get list of available tools
     */
    getAvailableTools(context = {}) {
        const tools = [];

        for (const [name, tool] of this.loadedTools) {
            try {
                // Check if user has permission for this tool
                this.checkPermissions(tool, context);

                tools.push({
                    name: tool.name,
                    version: tool.version,
                    description: tool.description,
                    category: tool.category,
                    permissions: tool.permissions,
                    schema: tool.schema,
                    metadata: tool._metadata
                });
            } catch (error) {
                // Skip tools user doesn't have permission for
                continue;
            }
        }

        return tools;
    }

    /**
     * Get tool information
     */
    getToolInfo(toolName) {
        const tool = this.loadedTools.get(toolName);
        if (!tool) {
            return null;
        }

        return tool.getInfo ? tool.getInfo() : {
            name: tool.name,
            version: tool.version,
            description: tool.description,
            category: tool.category,
            permissions: tool.permissions,
            schema: tool.schema
        };
    }

    /**
     * Reload a tool (for development)
     */
    async reloadTool(toolName) {
        const tool = this.loadedTools.get(toolName);
        if (!tool || !tool._metadata) {
            throw new Error(`Tool '${toolName}' not found or metadata missing`);
        }

        const { path: toolPath, origin } = tool._metadata;

        // Remove old tool
        this.loadedTools.delete(toolName);

        // Reload tool
        await this.loadTool(toolPath, origin);

        return {
            success: true,
            toolName: toolName,
            reloadedAt: new Date().toISOString()
        };
    }

    /**
     * Get execution history
     */
    getExecutionHistory(limit = 100) {
        return this.executionHistory
            .slice(-limit)
            .reverse();
    }

    /**
     * Get execution statistics
     */
    getExecutionStats() {
        const now = Date.now();
        const oneHour = 60 * 60 * 1000;
        const oneDay = 24 * oneHour;

        const recentExecutions = this.executionHistory.filter(exec =>
            now - new Date(exec.timestamp).getTime() < oneDay
        );

        const hourlyExecutions = this.executionHistory.filter(exec =>
            now - new Date(exec.timestamp).getTime() < oneHour
        );

        const toolUsage = {};
        recentExecutions.forEach(exec => {
            toolUsage[exec.toolName] = (toolUsage[exec.toolName] || 0) + 1;
        });

        const successRate = recentExecutions.length > 0
            ? (recentExecutions.filter(exec => exec.success).length / recentExecutions.length) * 100
            : 0;

        return {
            totalTools: this.loadedTools.size,
            executionsLast24h: recentExecutions.length,
            executionsLastHour: hourlyExecutions.length,
            successRate: parseFloat(successRate.toFixed(2)),
            toolUsage: toolUsage,
            averageExecutionTime: recentExecutions.length > 0
                ? recentExecutions.reduce((sum, exec) => sum + exec.executionTime, 0) / recentExecutions.length
                : 0
        };
    }

    /**
     * Record tool execution
     * @private
     */
    recordExecution(executionRecord) {
        this.executionHistory.push(executionRecord);

        // Maintain history size limit
        if (this.executionHistory.length > this.maxHistorySize) {
            this.executionHistory = this.executionHistory.slice(-this.maxHistorySize);
        }
    }

    /**
     * Generate unique execution ID
     * @private
     */
    generateExecutionId() {
        return `exec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Setup rate limit cleanup
     * @private
     */
    setupRateLimitCleanup() {
        // Clean up old rate limit data every hour
        setInterval(() => {
            const now = Date.now();
            const currentHour = Math.floor(now / (1000 * 60 * 60));

            // Keep only current and previous hour
            for (const [hour, data] of this.rateLimiter) {
                if (hour < currentHour - 1) {
                    this.rateLimiter.delete(hour);
                }
            }
        }, 60 * 60 * 1000); // Run every hour
    }
}

// Singleton pattern
let toolExecutorInstance = null;

function getToolExecutor() {
    if (!toolExecutorInstance) {
        toolExecutorInstance = new ToolExecutorService();
    }
    return toolExecutorInstance;
}

module.exports = {
    ToolExecutorService,
    getToolExecutor
};