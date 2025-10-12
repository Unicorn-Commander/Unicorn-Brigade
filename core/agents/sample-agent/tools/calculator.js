/**
 * Calculator Tool - Safe mathematical operations
 * UC2 Internal Tool v1.0.0
 */

class CalculatorTool {
    constructor() {
        this.name = 'calculator';
        this.version = '1.0.0';
        this.description = 'Performs safe mathematical calculations';
        this.category = 'math';
        this.permissions = ['basic'];
        this.schema = {
            type: 'object',
            properties: {
                expression: {
                    type: 'string',
                    description: 'Mathematical expression to evaluate (supports +, -, *, /, %, ^, sqrt, sin, cos, tan, log)'
                },
                precision: {
                    type: 'number',
                    default: 10,
                    description: 'Decimal precision for results'
                }
            },
            required: ['expression']
        };
    }

    /**
     * Execute mathematical calculation
     * @param {Object} params - Calculation parameters
     * @param {string} params.expression - Mathematical expression
     * @param {number} params.precision - Decimal precision
     * @returns {Object} Calculation result
     */
    async execute(params, context = {}) {
        try {
            const { expression, precision = 10 } = params;

            // Input validation
            if (!expression || typeof expression !== 'string') {
                throw new Error('Expression is required and must be a string');
            }

            // Sanitize expression - only allow safe mathematical operations
            const sanitizedExpression = this._sanitizeExpression(expression);

            // Evaluate the expression safely
            const result = this._evaluateExpression(sanitizedExpression);

            // Apply precision
            const preciseResult = parseFloat(result.toFixed(precision));

            return {
                success: true,
                result: preciseResult,
                expression: expression,
                sanitizedExpression: sanitizedExpression,
                timestamp: new Date().toISOString(),
                executionTime: process.hrtime.bigint()
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                expression: params.expression,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Sanitize mathematical expression to prevent code injection
     * @private
     */
    _sanitizeExpression(expression) {
        // Remove whitespace
        let clean = expression.replace(/\s/g, '');

        // Replace mathematical functions (only if not already prefixed with Math.)
        clean = clean.replace(/(?<!Math\.)sqrt\(/g, 'Math.sqrt(');
        clean = clean.replace(/(?<!Math\.)sin\(/g, 'Math.sin(');
        clean = clean.replace(/(?<!Math\.)cos\(/g, 'Math.cos(');
        clean = clean.replace(/(?<!Math\.)tan\(/g, 'Math.tan(');
        clean = clean.replace(/(?<!Math\.)log\(/g, 'Math.log(');
        clean = clean.replace(/\^/g, '**'); // Convert ^ to **

        // Only allow safe characters: numbers, operators, parentheses, decimal points, Math functions
        const allowedPattern = /^[0-9+\-*/().%\s,MathPIsqrtincolangebf**]+$/;

        if (!allowedPattern.test(clean)) {
            throw new Error('Expression contains invalid characters. Only numbers and basic math operations are allowed.');
        }

        return clean;
    }

    /**
     * Safely evaluate mathematical expression
     * @private
     */
    _evaluateExpression(expression) {
        try {
            // Use Function constructor for safer evaluation than eval
            // Provide Math object in scope for mathematical functions
            const result = Function('Math', '"use strict"; return (' + expression + ')')(Math);

            if (typeof result !== 'number' || !isFinite(result)) {
                throw new Error('Expression did not evaluate to a valid number');
            }

            return result;
        } catch (error) {
            throw new Error(`Failed to evaluate expression: ${error.message}`);
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
            examples: [
                {
                    description: 'Basic arithmetic',
                    input: { expression: '2 + 3 * 4' },
                    output: { result: 14 }
                },
                {
                    description: 'Trigonometry',
                    input: { expression: 'sin(Math.PI / 2)' },
                    output: { result: 1 }
                },
                {
                    description: 'Complex calculation',
                    input: { expression: 'sqrt(16) + 2^3', precision: 2 },
                    output: { result: 12.00 }
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

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalculatorTool;
} else if (typeof exports !== 'undefined') {
    exports.CalculatorTool = CalculatorTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = CalculatorTool;
}