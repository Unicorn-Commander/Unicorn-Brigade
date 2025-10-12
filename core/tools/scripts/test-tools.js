#!/usr/bin/env node

/**
 * Tool Testing Utility - Test all tools with their examples
 * UC2 Core Tool v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');

class ToolTester {
    constructor() {
        this.toolsDir = path.join(__dirname, '..');
        this.registryPath = path.join(this.toolsDir, 'registry.json');
        this.testResults = [];
        this.errors = [];
    }

    /**
     * Test all tools
     */
    async testAll(options = {}) {
        const { toolFilter = null, verbose = false } = options;

        console.log('🧪 UC2 Tool Tester v1.0.0');
        console.log('==========================');

        try {
            const registry = await this.loadRegistry();
            const tools = Object.entries(registry.tools);

            console.log(`📋 Testing ${tools.length} tools\n`);

            for (const [toolName, toolInfo] of tools) {
                if (toolFilter && toolName !== toolFilter) {
                    continue;
                }

                await this.testTool(toolName, toolInfo, { verbose });
            }

            this.generateReport();

            return {
                success: this.errors.length === 0,
                results: this.testResults,
                errors: this.errors
            };

        } catch (error) {
            console.error('❌ Testing failed:', error.message);
            return { success: false, results: [], errors: [error.message] };
        }
    }

    /**
     * Load registry
     */
    async loadRegistry() {
        const content = await fs.readFile(this.registryPath, 'utf8');
        return JSON.parse(content);
    }

    /**
     * Test individual tool
     */
    async testTool(toolName, toolInfo, options = {}) {
        console.log(`🔧 Testing tool: ${toolName}`);

        const result = {
            toolName: toolName,
            version: toolInfo.version,
            testsRun: 0,
            testsPassed: 0,
            testsFailed: 0,
            examples: [],
            errors: [],
            startTime: Date.now()
        };

        try {
            // Load tool implementation
            const toolPath = path.join(this.toolsDir, toolInfo.path);
            delete require.cache[require.resolve(toolPath)];
            const ToolClass = require(toolPath);
            const toolInstance = new ToolClass();

            // Test basic functionality
            await this.testBasicFunctionality(toolInstance, result);

            // Test examples if provided
            if (toolInfo.examples && toolInfo.examples.length > 0) {
                await this.testExamples(toolInstance, toolInfo.examples, result, options);
            } else {
                console.log('   ⚠️ No examples provided');
            }

            // Test error handling
            await this.testErrorHandling(toolInstance, result);

            result.endTime = Date.now();
            result.duration = result.endTime - result.startTime;

            console.log(`   ✅ ${result.testsPassed}/${result.testsRun} tests passed (${result.duration}ms)\n`);

        } catch (error) {
            result.errors.push(`Failed to load tool: ${error.message}`);
            this.errors.push(`${toolName}: ${error.message}`);
            console.log(`   ❌ Failed to load: ${error.message}\n`);
        }

        this.testResults.push(result);
    }

    /**
     * Test basic functionality
     */
    async testBasicFunctionality(toolInstance, result) {
        const tests = [
            {
                name: 'has_execute_method',
                test: () => typeof toolInstance.execute === 'function',
                description: 'Tool has execute method'
            },
            {
                name: 'has_name',
                test: () => typeof toolInstance.name === 'string' && toolInstance.name.length > 0,
                description: 'Tool has valid name'
            },
            {
                name: 'has_version',
                test: () => typeof toolInstance.version === 'string' && /^\d+\.\d+\.\d+$/.test(toolInstance.version),
                description: 'Tool has valid version'
            },
            {
                name: 'has_description',
                test: () => typeof toolInstance.description === 'string' && toolInstance.description.length > 0,
                description: 'Tool has valid description'
            },
            {
                name: 'has_category',
                test: () => typeof toolInstance.category === 'string' && toolInstance.category.length > 0,
                description: 'Tool has valid category'
            }
        ];

        for (const test of tests) {
            result.testsRun++;
            try {
                const passed = test.test();
                if (passed) {
                    result.testsPassed++;
                    console.log(`   ✅ ${test.description}`);
                } else {
                    result.testsFailed++;
                    result.errors.push(`Basic test failed: ${test.description}`);
                    console.log(`   ❌ ${test.description}`);
                }
            } catch (error) {
                result.testsFailed++;
                result.errors.push(`Basic test error: ${test.description} - ${error.message}`);
                console.log(`   ❌ ${test.description}: ${error.message}`);
            }
        }
    }

    /**
     * Test tool examples
     */
    async testExamples(toolInstance, examples, result, options) {
        console.log(`   📝 Testing ${examples.length} examples:`);

        for (let i = 0; i < examples.length; i++) {
            const example = examples[i];
            const exampleResult = {
                index: i + 1,
                description: example.description || `Example ${i + 1}`,
                input: example.input,
                expectedOutput: example.expectedOutput || example.output,
                actualOutput: null,
                passed: false,
                error: null,
                duration: 0
            };

            result.testsRun++;

            try {
                const startTime = Date.now();
                const output = await Promise.race([
                    toolInstance.execute(example.input, {}),
                    new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 10000))
                ]);
                exampleResult.duration = Date.now() - startTime;
                exampleResult.actualOutput = output;

                // Check if execution was successful
                if (output.success === false) {
                    throw new Error(output.error || 'Tool execution failed');
                }

                // Validate output if expected output is provided
                if (exampleResult.expectedOutput) {
                    const validationResult = this.validateOutput(output, exampleResult.expectedOutput);
                    if (validationResult.valid) {
                        exampleResult.passed = true;
                        result.testsPassed++;
                        console.log(`     ✅ ${exampleResult.description} (${exampleResult.duration}ms)`);
                    } else {
                        exampleResult.error = `Output validation failed: ${validationResult.reason}`;
                        result.testsFailed++;
                        result.errors.push(exampleResult.error);
                        console.log(`     ❌ ${exampleResult.description}: ${exampleResult.error}`);
                    }
                } else {
                    // No expected output provided, just check that it executed successfully
                    exampleResult.passed = true;
                    result.testsPassed++;
                    console.log(`     ✅ ${exampleResult.description} (${exampleResult.duration}ms)`);
                }

                if (options.verbose) {
                    console.log(`     📤 Input:`, JSON.stringify(example.input, null, 2));
                    console.log(`     📥 Output:`, JSON.stringify(output, null, 2));
                }

            } catch (error) {
                exampleResult.error = error.message;
                result.testsFailed++;
                result.errors.push(`Example ${i + 1}: ${error.message}`);
                console.log(`     ❌ ${exampleResult.description}: ${error.message}`);
            }

            result.examples.push(exampleResult);
        }
    }

    /**
     * Test error handling
     */
    async testErrorHandling(toolInstance, result) {
        const errorTests = [
            {
                name: 'missing_parameters',
                input: {},
                description: 'Handle missing required parameters'
            },
            {
                name: 'invalid_parameters',
                input: { invalid: 'parameter' },
                description: 'Handle invalid parameters'
            },
            {
                name: 'null_parameters',
                input: null,
                description: 'Handle null parameters'
            }
        ];

        console.log(`   🚫 Testing error handling:`);

        for (const test of errorTests) {
            result.testsRun++;

            try {
                const output = await toolInstance.execute(test.input, {});

                // Error handling test passes if the tool returns success: false
                // or throws an error (which we catch)
                if (output.success === false) {
                    result.testsPassed++;
                    console.log(`     ✅ ${test.description}`);
                } else {
                    result.testsFailed++;
                    result.errors.push(`Error test failed: ${test.description} - should have failed but succeeded`);
                    console.log(`     ❌ ${test.description}: should have failed but succeeded`);
                }

            } catch (error) {
                // Error was thrown, which is acceptable for error handling tests
                result.testsPassed++;
                console.log(`     ✅ ${test.description} (threw error as expected)`);
            }
        }
    }

    /**
     * Validate tool output against expected output
     */
    validateOutput(actual, expected) {
        try {
            // Simple validation - check if expected properties exist in actual output
            for (const [key, expectedValue] of Object.entries(expected)) {
                if (!(key in actual)) {
                    return { valid: false, reason: `Missing property: ${key}` };
                }

                if (typeof expectedValue === 'object' && expectedValue !== null) {
                    // Recursive validation for nested objects
                    const nestedValidation = this.validateOutput(actual[key], expectedValue);
                    if (!nestedValidation.valid) {
                        return { valid: false, reason: `${key}.${nestedValidation.reason}` };
                    }
                } else if (expectedValue !== null && actual[key] !== expectedValue) {
                    // Only validate non-null expected values
                    if (typeof expectedValue === 'number' && typeof actual[key] === 'number') {
                        // Allow small floating point differences
                        if (Math.abs(actual[key] - expectedValue) > 0.0001) {
                            return { valid: false, reason: `Property ${key}: expected ${expectedValue}, got ${actual[key]}` };
                        }
                    } else {
                        return { valid: false, reason: `Property ${key}: expected ${expectedValue}, got ${actual[key]}` };
                    }
                }
            }

            return { valid: true };
        } catch (error) {
            return { valid: false, reason: error.message };
        }
    }

    /**
     * Generate test report
     */
    generateReport() {
        console.log('\n📊 TEST REPORT');
        console.log('================');

        const totalTests = this.testResults.reduce((sum, result) => sum + result.testsRun, 0);
        const totalPassed = this.testResults.reduce((sum, result) => sum + result.testsPassed, 0);
        const totalFailed = this.testResults.reduce((sum, result) => sum + result.testsFailed, 0);
        const totalDuration = this.testResults.reduce((sum, result) => sum + (result.duration || 0), 0);

        console.log(`Tools tested: ${this.testResults.length}`);
        console.log(`Total tests: ${totalTests}`);
        console.log(`Passed: ${totalPassed}`);
        console.log(`Failed: ${totalFailed}`);
        console.log(`Success rate: ${totalTests > 0 ? ((totalPassed / totalTests) * 100).toFixed(1) : 0}%`);
        console.log(`Total duration: ${totalDuration}ms`);

        // Tool details
        if (this.testResults.length > 0) {
            console.log('\nTool Results:');
            for (const result of this.testResults) {
                const successRate = result.testsRun > 0 ? ((result.testsPassed / result.testsRun) * 100).toFixed(1) : 0;
                const status = result.testsFailed === 0 ? '✅' : '❌';
                console.log(`  ${status} ${result.toolName}: ${result.testsPassed}/${result.testsRun} (${successRate}%) - ${result.duration}ms`);
            }
        }

        // Errors summary
        if (this.errors.length > 0) {
            console.log('\n❌ Errors:');
            for (const error of this.errors) {
                console.log(`  - ${error}`);
            }
        }

        if (totalFailed === 0) {
            console.log('\n✅ All tests passed!');
        } else {
            console.log('\n❌ Some tests failed - check errors above');
        }
    }
}

// CLI Interface
if (require.main === module) {
    const args = process.argv.slice(2);
    const options = {};

    // Parse arguments
    for (let i = 0; i < args.length; i++) {
        switch (args[i]) {
            case '--tool':
                options.toolFilter = args[++i];
                break;
            case '--verbose':
            case '-v':
                options.verbose = true;
                break;
            case '--help':
                console.log(`
UC2 Tool Tester

Usage:
  node test-tools.js [options]

Options:
  --tool <name>     Test specific tool only
  --verbose, -v     Show detailed output
  --help           Show this help message

Examples:
  node test-tools.js                    # Test all tools
  node test-tools.js --tool calculator  # Test specific tool
  node test-tools.js --verbose          # Show detailed output
`);
                process.exit(0);
        }
    }

    const tester = new ToolTester();
    tester.testAll(options)
        .then(result => {
            process.exit(result.success ? 0 : 1);
        })
        .catch(error => {
            console.error('Testing error:', error);
            process.exit(1);
        });
}

module.exports = ToolTester;