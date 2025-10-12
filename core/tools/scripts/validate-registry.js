#!/usr/bin/env node

/**
 * Registry Validation Utility - Validate tool registry and tool implementations
 * UC2 Core Tool v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');

class RegistryValidator {
    constructor() {
        this.toolsDir = path.join(__dirname, '..');
        this.registryPath = path.join(this.toolsDir, 'registry.json');
        this.errors = [];
        this.warnings = [];
    }

    /**
     * Validate complete registry
     */
    async validate() {
        console.log('🔍 UC2 Registry Validator v1.0.0');
        console.log('==================================');

        try {
            // Load and validate registry format
            const registry = await this.loadRegistry();
            await this.validateRegistryStructure(registry);

            // Validate each tool
            for (const [toolName, toolInfo] of Object.entries(registry.tools)) {
                await this.validateTool(toolName, toolInfo);
            }

            // Validate categories and permissions
            await this.validateCategories(registry);
            await this.validatePermissions(registry);

            // Generate report
            this.generateReport();

            return {
                valid: this.errors.length === 0,
                errors: this.errors,
                warnings: this.warnings
            };

        } catch (error) {
            console.error('❌ Validation failed:', error.message);
            return { valid: false, errors: [error.message], warnings: [] };
        }
    }

    /**
     * Load registry file
     */
    async loadRegistry() {
        try {
            const content = await fs.readFile(this.registryPath, 'utf8');
            return JSON.parse(content);
        } catch (error) {
            throw new Error(`Failed to load registry: ${error.message}`);
        }
    }

    /**
     * Validate registry structure
     */
    async validateRegistryStructure(registry) {
        const requiredFields = ['version', 'description', 'tools', 'categories', 'permissionLevels'];

        for (const field of requiredFields) {
            if (!registry[field]) {
                this.errors.push(`Registry missing required field: ${field}`);
            }
        }

        // Validate version format
        if (registry.version && !/^\d+\.\d+\.\d+$/.test(registry.version)) {
            this.errors.push(`Invalid version format: ${registry.version}`);
        }

        // Validate tools structure
        if (registry.tools && typeof registry.tools !== 'object') {
            this.errors.push('Registry tools must be an object');
        }
    }

    /**
     * Validate individual tool
     */
    async validateTool(toolName, toolInfo) {
        console.log(`🔧 Validating tool: ${toolName}`);

        // Required fields
        const requiredFields = ['name', 'version', 'type', 'category', 'description', 'path', 'permissions'];
        for (const field of requiredFields) {
            if (!toolInfo[field]) {
                this.errors.push(`Tool ${toolName} missing required field: ${field}`);
            }
        }

        // Validate name consistency
        if (toolInfo.name !== toolName) {
            this.errors.push(`Tool ${toolName} has mismatched name in registry: ${toolInfo.name}`);
        }

        // Validate version format
        if (toolInfo.version && !/^\d+\.\d+\.\d+$/.test(toolInfo.version)) {
            this.errors.push(`Tool ${toolName} has invalid version format: ${toolInfo.version}`);
        }

        // Validate type
        const validTypes = ['internal', 'external', 'custom'];
        if (toolInfo.type && !validTypes.includes(toolInfo.type)) {
            this.errors.push(`Tool ${toolName} has invalid type: ${toolInfo.type}`);
        }

        // Validate file exists
        if (toolInfo.path) {
            const toolPath = path.join(this.toolsDir, toolInfo.path);
            try {
                await fs.access(toolPath);

                // Load and validate tool implementation
                await this.validateToolImplementation(toolName, toolPath, toolInfo);
            } catch (error) {
                this.errors.push(`Tool ${toolName} file not found: ${toolInfo.path}`);
            }
        }

        // Validate schema
        if (toolInfo.schema) {
            await this.validateToolSchema(toolName, toolInfo.schema);
        }

        // Validate examples
        if (toolInfo.examples) {
            await this.validateToolExamples(toolName, toolInfo.examples);
        }
    }

    /**
     * Validate tool implementation
     */
    async validateToolImplementation(toolName, toolPath, toolInfo) {
        try {
            // Clear require cache
            delete require.cache[require.resolve(toolPath)];

            const ToolClass = require(toolPath);
            const toolInstance = new ToolClass();

            // Check required methods
            const requiredMethods = ['execute', 'getInfo'];
            for (const method of requiredMethods) {
                if (typeof toolInstance[method] !== 'function') {
                    this.errors.push(`Tool ${toolName} missing required method: ${method}`);
                }
            }

            // Check required properties
            const requiredProps = ['name', 'version', 'description', 'category'];
            for (const prop of requiredProps) {
                if (!toolInstance[prop]) {
                    this.warnings.push(`Tool ${toolName} missing recommended property: ${prop}`);
                }
            }

            // Validate consistency with registry
            if (toolInstance.name !== toolName) {
                this.errors.push(`Tool ${toolName} implementation name mismatch: ${toolInstance.name}`);
            }

            if (toolInstance.version !== toolInfo.version) {
                this.warnings.push(`Tool ${toolName} version mismatch between registry (${toolInfo.version}) and implementation (${toolInstance.version})`);
            }

            if (toolInstance.category !== toolInfo.category) {
                this.warnings.push(`Tool ${toolName} category mismatch between registry (${toolInfo.category}) and implementation (${toolInstance.category})`);
            }

            // Run tool's own validation if available
            if (toolInstance.validate) {
                const validation = toolInstance.validate();
                if (!validation.valid) {
                    this.errors.push(`Tool ${toolName} self-validation failed: ${validation.issues.join(', ')}`);
                }
            }

            console.log(`   ✅ Implementation valid`);

        } catch (error) {
            this.errors.push(`Tool ${toolName} implementation error: ${error.message}`);
            console.log(`   ❌ Implementation error: ${error.message}`);
        }
    }

    /**
     * Validate tool schema
     */
    async validateToolSchema(toolName, schema) {
        try {
            if (typeof schema !== 'object') {
                this.errors.push(`Tool ${toolName} schema must be an object`);
                return;
            }

            if (schema.type !== 'object') {
                this.warnings.push(`Tool ${toolName} schema should have type 'object'`);
            }

            if (schema.properties && typeof schema.properties !== 'object') {
                this.errors.push(`Tool ${toolName} schema properties must be an object`);
            }

            if (schema.required && !Array.isArray(schema.required)) {
                this.errors.push(`Tool ${toolName} schema required must be an array`);
            }

        } catch (error) {
            this.errors.push(`Tool ${toolName} schema validation error: ${error.message}`);
        }
    }

    /**
     * Validate tool examples
     */
    async validateToolExamples(toolName, examples) {
        if (!Array.isArray(examples)) {
            this.errors.push(`Tool ${toolName} examples must be an array`);
            return;
        }

        for (let i = 0; i < examples.length; i++) {
            const example = examples[i];

            if (!example.description) {
                this.warnings.push(`Tool ${toolName} example ${i + 1} missing description`);
            }

            if (!example.input) {
                this.errors.push(`Tool ${toolName} example ${i + 1} missing input`);
            }

            if (!example.expectedOutput && !example.output) {
                this.warnings.push(`Tool ${toolName} example ${i + 1} missing expected output`);
            }
        }
    }

    /**
     * Validate categories
     */
    async validateCategories(registry) {
        const categories = registry.categories || {};
        const toolCategories = new Set();

        // Collect all tool categories
        for (const toolInfo of Object.values(registry.tools)) {
            if (toolInfo.category) {
                toolCategories.add(toolInfo.category);
            }
        }

        // Check that all tool categories are defined
        for (const category of toolCategories) {
            if (!categories[category]) {
                this.warnings.push(`Category '${category}' used by tools but not defined in categories`);
            }
        }

        // Check category definitions
        for (const [categoryName, categoryInfo] of Object.entries(categories)) {
            if (!categoryInfo.description) {
                this.warnings.push(`Category '${categoryName}' missing description`);
            }

            if (!categoryInfo.tools || !Array.isArray(categoryInfo.tools)) {
                this.errors.push(`Category '${categoryName}' missing or invalid tools array`);
            } else {
                // Check that listed tools exist and have correct category
                for (const toolName of categoryInfo.tools) {
                    if (!registry.tools[toolName]) {
                        this.errors.push(`Category '${categoryName}' references non-existent tool: ${toolName}`);
                    } else if (registry.tools[toolName].category !== categoryName) {
                        this.errors.push(`Tool '${toolName}' category mismatch: listed in '${categoryName}' but tool has category '${registry.tools[toolName].category}'`);
                    }
                }
            }
        }
    }

    /**
     * Validate permission levels
     */
    async validatePermissions(registry) {
        const permissionLevels = registry.permissionLevels || {};
        const toolPermissions = new Set();

        // Collect all tool permissions
        for (const toolInfo of Object.values(registry.tools)) {
            if (toolInfo.permissions) {
                for (const permission of toolInfo.permissions) {
                    toolPermissions.add(permission);
                }
            }
        }

        // Check that all tool permissions are defined
        for (const permission of toolPermissions) {
            if (!permissionLevels[permission]) {
                this.warnings.push(`Permission '${permission}' used by tools but not defined in permissionLevels`);
            }
        }

        // Check permission level definitions
        for (const [levelName, levelInfo] of Object.entries(permissionLevels)) {
            if (!levelInfo.description) {
                this.warnings.push(`Permission level '${levelName}' missing description`);
            }

            if (!levelInfo.tools || !Array.isArray(levelInfo.tools)) {
                this.errors.push(`Permission level '${levelName}' missing or invalid tools array`);
            } else {
                // Check that listed tools exist and have correct permissions
                for (const toolName of levelInfo.tools) {
                    if (toolName === '*') continue; // Wildcard is valid

                    if (!registry.tools[toolName]) {
                        this.errors.push(`Permission level '${levelName}' references non-existent tool: ${toolName}`);
                    } else if (!registry.tools[toolName].permissions?.includes(levelName)) {
                        this.errors.push(`Tool '${toolName}' permissions mismatch: listed in '${levelName}' but tool doesn't have this permission`);
                    }
                }
            }
        }
    }

    /**
     * Generate validation report
     */
    generateReport() {
        console.log('\n📊 VALIDATION REPORT');
        console.log('====================');

        console.log(`Errors: ${this.errors.length}`);
        console.log(`Warnings: ${this.warnings.length}`);

        if (this.errors.length > 0) {
            console.log('\n❌ Errors:');
            for (const error of this.errors) {
                console.log(`  - ${error}`);
            }
        }

        if (this.warnings.length > 0) {
            console.log('\n⚠️ Warnings:');
            for (const warning of this.warnings) {
                console.log(`  - ${warning}`);
            }
        }

        if (this.errors.length === 0 && this.warnings.length === 0) {
            console.log('\n✅ All validations passed!');
        } else if (this.errors.length === 0) {
            console.log('\n✅ No errors found! (warnings can be addressed)');
        } else {
            console.log('\n❌ Validation failed - please fix errors before proceeding');
        }
    }
}

// CLI Interface
if (require.main === module) {
    const validator = new RegistryValidator();
    validator.validate()
        .then(result => {
            process.exit(result.valid ? 0 : 1);
        })
        .catch(error => {
            console.error('Validation error:', error);
            process.exit(1);
        });
}

module.exports = RegistryValidator;