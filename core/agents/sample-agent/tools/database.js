/**
 * Database Tool - Query Prisma database safely
 * UC2 Internal Tool v1.0.0
 */

class DatabaseTool {
    constructor(prismaClient = null) {
        this.name = 'database';
        this.version = '1.0.0';
        this.description = 'Execute safe database queries using Prisma ORM';
        this.category = 'database';
        this.permissions = ['database', 'read', 'write'];
        this.prisma = prismaClient;

        // Define allowed models and operations for security
        this.allowedModels = [
            'agent', 'agentMessage', 'agentTask', 'orchestration', 'memory',
            'tool', 'workflow', 'aiProvider', 'user', 'session'
        ];

        this.allowedOperations = {
            read: ['findMany', 'findFirst', 'findUnique', 'count', 'aggregate'],
            write: ['create', 'update', 'upsert'],
            delete: ['delete', 'deleteMany']
        };

        this.schema = {
            type: 'object',
            properties: {
                operation: {
                    type: 'string',
                    enum: ['find', 'findMany', 'findFirst', 'findUnique', 'create', 'update', 'upsert', 'delete', 'deleteMany', 'count', 'aggregate'],
                    description: 'Database operation to perform'
                },
                model: {
                    type: 'string',
                    enum: this.allowedModels,
                    description: 'Database model to operate on'
                },
                data: {
                    type: 'object',
                    description: 'Data for create/update operations'
                },
                where: {
                    type: 'object',
                    description: 'Filter conditions'
                },
                select: {
                    type: 'object',
                    description: 'Fields to select'
                },
                include: {
                    type: 'object',
                    description: 'Relations to include'
                },
                orderBy: {
                    type: 'object',
                    description: 'Sort order'
                },
                take: {
                    type: 'number',
                    maximum: 1000,
                    description: 'Limit results (max 1000)'
                },
                skip: {
                    type: 'number',
                    description: 'Skip results (for pagination)'
                }
            },
            required: ['operation', 'model']
        };

        // Security rules
        this.securityRules = {
            // Prevent access to sensitive fields
            restrictedFields: {
                user: ['password'],
                session: ['token'],
                aiProvider: ['apiKey']
            },
            // Limit operations per model
            modelPermissions: {
                user: ['find', 'findMany', 'findFirst', 'count'],
                session: ['find', 'findMany', 'delete'],
                aiProvider: ['find', 'findMany', 'findFirst']
            },
            // Maximum results per query
            maxResults: 1000
        };
    }

    /**
     * Execute database operation
     */
    async execute(params, context = {}) {
        try {
            if (!this.prisma) {
                throw new Error('Database client not initialized');
            }

            const { operation, model, data, where, select, include, orderBy, take, skip } = params;

            // Input validation
            if (!this.allowedModels.includes(model)) {
                throw new Error(`Model '${model}' is not allowed`);
            }

            // Check operation permissions
            await this._validateOperation(operation, model, context);

            // Sanitize query parameters
            const sanitizedParams = this._sanitizeQueryParams({
                data, where, select, include, orderBy, take, skip
            }, model);

            const startTime = process.hrtime.bigint();

            // Execute the operation
            let result;
            const modelClient = this.prisma[model];

            if (!modelClient) {
                throw new Error(`Model '${model}' not found in Prisma client`);
            }

            switch (operation) {
                case 'find':
                case 'findMany':
                    result = await modelClient.findMany(sanitizedParams);
                    break;

                case 'findFirst':
                    result = await modelClient.findFirst(sanitizedParams);
                    break;

                case 'findUnique':
                    if (!sanitizedParams.where) {
                        throw new Error('findUnique requires where clause');
                    }
                    result = await modelClient.findUnique({
                        where: sanitizedParams.where,
                        select: sanitizedParams.select,
                        include: sanitizedParams.include
                    });
                    break;

                case 'create':
                    if (!sanitizedParams.data) {
                        throw new Error('create operation requires data');
                    }
                    result = await modelClient.create({
                        data: sanitizedParams.data,
                        select: sanitizedParams.select,
                        include: sanitizedParams.include
                    });
                    break;

                case 'update':
                    if (!sanitizedParams.data || !sanitizedParams.where) {
                        throw new Error('update operation requires data and where clause');
                    }
                    result = await modelClient.update({
                        where: sanitizedParams.where,
                        data: sanitizedParams.data,
                        select: sanitizedParams.select,
                        include: sanitizedParams.include
                    });
                    break;

                case 'upsert':
                    if (!sanitizedParams.where || !sanitizedParams.data) {
                        throw new Error('upsert operation requires where clause and data');
                    }
                    result = await modelClient.upsert({
                        where: sanitizedParams.where,
                        update: sanitizedParams.data,
                        create: sanitizedParams.data,
                        select: sanitizedParams.select,
                        include: sanitizedParams.include
                    });
                    break;

                case 'delete':
                    if (!sanitizedParams.where) {
                        throw new Error('delete operation requires where clause');
                    }
                    result = await modelClient.delete({
                        where: sanitizedParams.where
                    });
                    break;

                case 'deleteMany':
                    result = await modelClient.deleteMany({
                        where: sanitizedParams.where || {}
                    });
                    break;

                case 'count':
                    result = await modelClient.count({
                        where: sanitizedParams.where
                    });
                    break;

                case 'aggregate':
                    result = await modelClient.aggregate({
                        where: sanitizedParams.where,
                        _count: true,
                        _min: sanitizedParams._min,
                        _max: sanitizedParams._max,
                        _avg: sanitizedParams._avg,
                        _sum: sanitizedParams._sum
                    });
                    break;

                default:
                    throw new Error(`Unsupported operation: ${operation}`);
            }

            // Post-process result to remove sensitive fields
            const sanitizedResult = this._sanitizeResult(result, model);

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000;

            return {
                success: true,
                operation: operation,
                model: model,
                result: sanitizedResult,
                count: Array.isArray(sanitizedResult) ? sanitizedResult.length : (sanitizedResult ? 1 : 0),
                executionTime: `${executionTime.toFixed(2)}ms`,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            return {
                success: false,
                operation: params.operation,
                model: params.model,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Validate operation permissions
     * @private
     */
    async _validateOperation(operation, model, context) {
        // Check if operation is allowed for this model
        const modelPerms = this.securityRules.modelPermissions[model];
        if (modelPerms && !modelPerms.includes(operation)) {
            throw new Error(`Operation '${operation}' not allowed for model '${model}'`);
        }

        // Check user permissions if context provided
        if (context.user && context.user.role !== 'admin') {
            const writeOperations = ['create', 'update', 'upsert', 'delete', 'deleteMany'];
            if (writeOperations.includes(operation)) {
                const userPerms = JSON.parse(context.user.permissions || '[]');
                if (!userPerms.includes('database:write')) {
                    throw new Error('Insufficient permissions for write operations');
                }
            }
        }
    }

    /**
     * Sanitize query parameters
     * @private
     */
    _sanitizeQueryParams(params, model) {
        const sanitized = { ...params };

        // Apply take limit
        if (sanitized.take && sanitized.take > this.securityRules.maxResults) {
            sanitized.take = this.securityRules.maxResults;
        }

        // Remove restricted fields from select
        if (sanitized.select) {
            const restrictedFields = this.securityRules.restrictedFields[model] || [];
            for (const field of restrictedFields) {
                if (sanitized.select[field]) {
                    delete sanitized.select[field];
                }
            }
        }

        // Validate where clause to prevent SQL injection (Prisma handles this, but extra safety)
        if (sanitized.where) {
            sanitized.where = this._validateWhereClause(sanitized.where);
        }

        return sanitized;
    }

    /**
     * Validate where clause for security
     * @private
     */
    _validateWhereClause(where) {
        if (typeof where !== 'object' || where === null) {
            throw new Error('Where clause must be an object');
        }

        // Check for dangerous operations
        const dangerousKeys = ['$raw', '$queryRaw', '$executeRaw'];
        for (const key of dangerousKeys) {
            if (where[key]) {
                throw new Error(`Dangerous operation '${key}' not allowed in where clause`);
            }
        }

        return where;
    }

    /**
     * Remove sensitive fields from result
     * @private
     */
    _sanitizeResult(result, model) {
        if (!result) return result;

        const restrictedFields = this.securityRules.restrictedFields[model] || [];
        if (restrictedFields.length === 0) return result;

        const sanitizeObject = (obj) => {
            if (Array.isArray(obj)) {
                return obj.map(sanitizeObject);
            }
            if (obj && typeof obj === 'object') {
                const sanitized = { ...obj };
                for (const field of restrictedFields) {
                    if (sanitized[field]) {
                        sanitized[field] = '[REDACTED]';
                    }
                }
                return sanitized;
            }
            return obj;
        };

        return sanitizeObject(result);
    }

    /**
     * Get database schema information
     */
    async getSchema() {
        if (!this.prisma) {
            throw new Error('Database client not initialized');
        }

        return {
            models: this.allowedModels,
            operations: this.allowedOperations,
            securityRules: this.securityRules
        };
    }

    /**
     * Test database connection
     */
    async testConnection() {
        if (!this.prisma) {
            return { connected: false, error: 'Database client not initialized' };
        }

        try {
            await this.prisma.$queryRaw`SELECT 1 as test`;
            return {
                connected: true,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            return {
                connected: false,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
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
            allowedModels: this.allowedModels,
            allowedOperations: this.allowedOperations,
            securityRules: this.securityRules,
            examples: [
                {
                    description: 'Find all active agents',
                    input: {
                        operation: 'findMany',
                        model: 'agent',
                        where: { status: 'active' },
                        select: { id: true, name: true, type: true, status: true }
                    },
                    output: { count: 3, result: [] }
                },
                {
                    description: 'Create a new memory entry',
                    input: {
                        operation: 'create',
                        model: 'memory',
                        data: {
                            type: 'semantic',
                            scope: 'global',
                            content: 'Important system information',
                            category: 'system'
                        }
                    },
                    output: { success: true }
                },
                {
                    description: 'Count agent tasks by status',
                    input: {
                        operation: 'count',
                        model: 'agentTask',
                        where: { status: 'completed' }
                    },
                    output: { result: 42 }
                }
            ]
        };
    }

    /**
     * Initialize database connection
     */
    async initialize(prismaClient) {
        this.prisma = prismaClient;
        return await this.testConnection();
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        if (!this.prisma) {
            issues.push('Database client not provided');
        }

        if (!this.allowedModels || this.allowedModels.length === 0) {
            issues.push('No allowed models configured');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

module.exports = DatabaseTool;