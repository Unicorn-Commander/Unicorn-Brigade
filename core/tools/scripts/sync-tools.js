#!/usr/bin/env node

/**
 * Tool Sync Utility - Synchronize tools between core and agents with version tracking
 * UC2 Core Tool v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

class ToolSyncUtility {
    constructor() {
        this.baseDir = path.join(__dirname, '../../../');
        this.toolsDir = path.join(this.baseDir, 'core/tools');
        this.agentsDir = path.join(this.baseDir, 'core/agents');
        this.registryPath = path.join(this.toolsDir, 'registry.json');

        this.syncLog = [];
        this.errors = [];
        this.warnings = [];

        // Version tracking
        this.versionFile = path.join(this.toolsDir, '.versions.json');
    }

    /**
     * Main sync process
     */
    async sync(options = {}) {
        const {
            agentFilter = null,      // Sync specific agent only
            toolFilter = null,       // Sync specific tool only
            dryRun = false,         // Preview changes without applying
            force = false,          // Force sync even if versions match
            updateOnly = false      // Only update existing tools, don't add new ones
        } = options;

        console.log('🔄 UC2 Tool Sync Utility v1.0.0');
        console.log('=====================================');

        if (dryRun) {
            console.log('🔍 DRY RUN MODE - No changes will be made\n');
        }

        try {
            // Load registry and version info
            const registry = await this.loadRegistry();
            const versions = await this.loadVersions();

            // Find all agents
            const agents = await this.findAgents(agentFilter);
            console.log(`📋 Found ${agents.length} agents to process\n`);

            // Process each agent
            for (const agentPath of agents) {
                await this.syncAgent(agentPath, registry, versions, {
                    toolFilter,
                    dryRun,
                    force,
                    updateOnly
                });
            }

            // Update version tracking
            if (!dryRun) {
                await this.updateVersions(versions);
            }

            // Generate sync report
            this.generateReport();

        } catch (error) {
            console.error('❌ Sync failed:', error.message);
            process.exit(1);
        }
    }

    /**
     * Load tool registry
     */
    async loadRegistry() {
        try {
            const registryContent = await fs.readFile(this.registryPath, 'utf8');
            return JSON.parse(registryContent);
        } catch (error) {
            throw new Error(`Failed to load registry: ${error.message}`);
        }
    }

    /**
     * Load version tracking info
     */
    async loadVersions() {
        try {
            const versionsContent = await fs.readFile(this.versionFile, 'utf8');
            return JSON.parse(versionsContent);
        } catch (error) {
            // Create new versions file if it doesn't exist
            return {
                lastSync: null,
                tools: {},
                agents: {}
            };
        }
    }

    /**
     * Find all agents or specific agent
     */
    async findAgents(agentFilter) {
        const agents = [];
        const agentDirs = await fs.readdir(this.agentsDir, { withFileTypes: true });

        for (const entry of agentDirs) {
            if (entry.isDirectory() && entry.name !== 'shared') {
                const agentPath = path.join(this.agentsDir, entry.name);
                const agentConfigPath = path.join(agentPath, 'agent.json');

                try {
                    await fs.access(agentConfigPath);

                    if (!agentFilter || entry.name === agentFilter) {
                        agents.push(agentPath);
                    }
                } catch (error) {
                    this.warnings.push(`Agent ${entry.name} has no agent.json config`);
                }
            }
        }

        return agents;
    }

    /**
     * Sync tools for a specific agent
     */
    async syncAgent(agentPath, registry, versions, options) {
        const agentName = path.basename(agentPath);
        console.log(`🤖 Processing agent: ${agentName}`);

        try {
            // Load agent configuration
            const agentConfig = await this.loadAgentConfig(agentPath);
            const agentToolsDir = path.join(agentPath, 'tools');

            // Ensure tools directory exists
            await fs.mkdir(agentToolsDir, { recursive: true });

            // Load or create tool manifest
            const manifestPath = path.join(agentToolsDir, 'manifest.json');
            let manifest = await this.loadOrCreateManifest(manifestPath, agentConfig);

            let changesCount = 0;

            // Process each enabled tool
            for (const toolName of agentConfig.tools?.enabled || []) {
                if (options.toolFilter && toolName !== options.toolFilter) {
                    continue;
                }

                const syncResult = await this.syncTool(
                    toolName,
                    agentPath,
                    agentToolsDir,
                    registry,
                    versions,
                    manifest,
                    options
                );

                if (syncResult.changed) {
                    changesCount++;
                }
            }

            // Remove disabled tools
            await this.removeDisabledTools(agentToolsDir, agentConfig.tools?.enabled || [], options);

            // Update manifest
            if (changesCount > 0 && !options.dryRun) {
                manifest.lastSynced = new Date().toISOString();
                await this.saveManifest(manifestPath, manifest);
            }

            console.log(`   ✅ Synced ${changesCount} tools for ${agentName}\n`);

            this.syncLog.push({
                agent: agentName,
                toolsProcessed: agentConfig.tools?.enabled?.length || 0,
                changesCount: changesCount
            });

        } catch (error) {
            this.errors.push(`Failed to sync agent ${agentName}: ${error.message}`);
            console.error(`   ❌ Error syncing ${agentName}: ${error.message}\n`);
        }
    }

    /**
     * Sync a single tool for an agent
     */
    async syncTool(toolName, agentPath, agentToolsDir, registry, versions, manifest, options) {
        const toolInfo = registry.tools[toolName];
        if (!toolInfo) {
            this.warnings.push(`Tool ${toolName} not found in registry`);
            return { changed: false };
        }

        const sourcePath = path.join(this.toolsDir, toolInfo.path);
        const destPath = path.join(agentToolsDir, path.basename(toolInfo.path));

        try {
            // Check if source tool exists
            await fs.access(sourcePath);

            // Calculate checksums
            const sourceChecksum = await this.calculateChecksum(sourcePath);
            const destExists = await this.fileExists(destPath);
            const destChecksum = destExists ? await this.calculateChecksum(destPath) : null;

            // Check version tracking
            const toolVersionKey = `${toolName}@${toolInfo.version}`;
            const lastSyncChecksum = versions.tools[toolVersionKey]?.checksum;

            // Determine if sync is needed
            const needsSync = options.force ||
                             !destExists ||
                             sourceChecksum !== destChecksum ||
                             sourceChecksum !== lastSyncChecksum;

            if (!needsSync) {
                console.log(`   ⚪ ${toolName} - up to date`);
                return { changed: false };
            }

            if (options.updateOnly && !destExists) {
                console.log(`   ⚪ ${toolName} - skipping (new tool, update-only mode)`);
                return { changed: false };
            }

            // Perform sync
            if (!options.dryRun) {
                await fs.copyFile(sourcePath, destPath);

                // Update version tracking
                versions.tools[toolVersionKey] = {
                    checksum: sourceChecksum,
                    lastSynced: new Date().toISOString(),
                    agent: path.basename(agentPath)
                };

                // Update manifest
                const manifestTool = manifest.tools.find(t => t.name === toolName);
                if (manifestTool) {
                    manifestTool.checksum = `sha256:${sourceChecksum}`;
                    manifestTool.lastUpdated = new Date().toISOString();
                    manifestTool.version = toolInfo.version;
                } else {
                    manifest.tools.push({
                        name: toolName,
                        version: toolInfo.version,
                        source: toolInfo.type,
                        path: path.basename(toolInfo.path),
                        enabled: true,
                        permissions: toolInfo.permissions,
                        lastUpdated: new Date().toISOString(),
                        checksum: `sha256:${sourceChecksum}`
                    });
                }
            }

            console.log(`   ✅ ${toolName} - ${destExists ? 'updated' : 'added'}`);
            return { changed: true };

        } catch (error) {
            this.errors.push(`Failed to sync tool ${toolName}: ${error.message}`);
            console.log(`   ❌ ${toolName} - error: ${error.message}`);
            return { changed: false };
        }
    }

    /**
     * Remove tools that are no longer enabled
     */
    async removeDisabledTools(agentToolsDir, enabledTools, options) {
        try {
            const existingFiles = await fs.readdir(agentToolsDir);
            const toolFiles = existingFiles.filter(file =>
                file.endsWith('.js') &&
                file !== 'manifest.json'
            );

            for (const toolFile of toolFiles) {
                const toolName = path.basename(toolFile, '.js');
                if (!enabledTools.includes(toolName)) {
                    const filePath = path.join(agentToolsDir, toolFile);

                    if (!options.dryRun) {
                        await fs.unlink(filePath);
                    }

                    console.log(`   🗑️ ${toolName} - removed (disabled)`);
                }
            }
        } catch (error) {
            this.warnings.push(`Failed to clean up disabled tools: ${error.message}`);
        }
    }

    /**
     * Load agent configuration
     */
    async loadAgentConfig(agentPath) {
        const configPath = path.join(agentPath, 'agent.json');
        const content = await fs.readFile(configPath, 'utf8');
        return JSON.parse(content);
    }

    /**
     * Load or create tool manifest
     */
    async loadOrCreateManifest(manifestPath, agentConfig) {
        try {
            const content = await fs.readFile(manifestPath, 'utf8');
            return JSON.parse(content);
        } catch (error) {
            // Create new manifest
            return {
                agentId: agentConfig.id,
                agentName: agentConfig.name,
                toolsVersion: "1.0.0",
                lastSynced: null,
                syncSource: "core/tools",
                tools: [],
                customTools: [],
                validation: {
                    lastValidated: null,
                    status: "pending",
                    issues: []
                }
            };
        }
    }

    /**
     * Save tool manifest
     */
    async saveManifest(manifestPath, manifest) {
        await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
    }

    /**
     * Update version tracking
     */
    async updateVersions(versions) {
        versions.lastSync = new Date().toISOString();
        await fs.writeFile(this.versionFile, JSON.stringify(versions, null, 2), 'utf8');
    }

    /**
     * Calculate file checksum
     */
    async calculateChecksum(filePath) {
        const content = await fs.readFile(filePath);
        return crypto.createHash('sha256').update(content).digest('hex');
    }

    /**
     * Check if file exists
     */
    async fileExists(filePath) {
        try {
            await fs.access(filePath);
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Generate sync report
     */
    generateReport() {
        console.log('\n📊 SYNC REPORT');
        console.log('================');

        // Summary
        const totalAgents = this.syncLog.length;
        const totalChanges = this.syncLog.reduce((sum, log) => sum + log.changesCount, 0);

        console.log(`Agents processed: ${totalAgents}`);
        console.log(`Total changes: ${totalChanges}`);
        console.log(`Warnings: ${this.warnings.length}`);
        console.log(`Errors: ${this.errors.length}`);

        // Detailed results
        if (this.syncLog.length > 0) {
            console.log('\nAgent Details:');
            for (const log of this.syncLog) {
                console.log(`  ${log.agent}: ${log.changesCount}/${log.toolsProcessed} tools updated`);
            }
        }

        // Warnings
        if (this.warnings.length > 0) {
            console.log('\n⚠️ Warnings:');
            for (const warning of this.warnings) {
                console.log(`  - ${warning}`);
            }
        }

        // Errors
        if (this.errors.length > 0) {
            console.log('\n❌ Errors:');
            for (const error of this.errors) {
                console.log(`  - ${error}`);
            }
        }

        console.log('\n✅ Sync complete!');
    }

    /**
     * Validate tool integrity
     */
    async validateTools(agentPath) {
        const agentToolsDir = path.join(agentPath, 'tools');
        const manifestPath = path.join(agentToolsDir, 'manifest.json');

        try {
            const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
            const issues = [];

            for (const tool of manifest.tools) {
                const toolPath = path.join(agentToolsDir, tool.path);

                // Check if file exists
                if (!await this.fileExists(toolPath)) {
                    issues.push(`Tool file missing: ${tool.path}`);
                    continue;
                }

                // Validate checksum
                const actualChecksum = await this.calculateChecksum(toolPath);
                const expectedChecksum = tool.checksum?.replace('sha256:', '');

                if (expectedChecksum && actualChecksum !== expectedChecksum) {
                    issues.push(`Checksum mismatch for ${tool.name}: expected ${expectedChecksum}, got ${actualChecksum}`);
                }

                // Try to load and validate tool
                try {
                    delete require.cache[require.resolve(toolPath)];
                    const ToolClass = require(toolPath);
                    const toolInstance = new ToolClass();

                    if (toolInstance.validate) {
                        const validation = toolInstance.validate();
                        if (!validation.valid) {
                            issues.push(`Tool validation failed for ${tool.name}: ${validation.issues.join(', ')}`);
                        }
                    }
                } catch (error) {
                    issues.push(`Failed to load tool ${tool.name}: ${error.message}`);
                }
            }

            // Update manifest validation
            manifest.validation = {
                lastValidated: new Date().toISOString(),
                status: issues.length === 0 ? 'valid' : 'invalid',
                issues: issues
            };

            await this.saveManifest(manifestPath, manifest);

            return {
                valid: issues.length === 0,
                issues: issues
            };

        } catch (error) {
            return {
                valid: false,
                issues: [`Failed to validate tools: ${error.message}`]
            };
        }
    }
}

// CLI Interface
if (require.main === module) {
    const args = process.argv.slice(2);
    const options = {};

    // Parse command line arguments
    for (let i = 0; i < args.length; i++) {
        switch (args[i]) {
            case '--agent':
                options.agentFilter = args[++i];
                break;
            case '--tool':
                options.toolFilter = args[++i];
                break;
            case '--dry-run':
                options.dryRun = true;
                break;
            case '--force':
                options.force = true;
                break;
            case '--update-only':
                options.updateOnly = true;
                break;
            case '--help':
                console.log(`
UC2 Tool Sync Utility

Usage:
  node sync-tools.js [options]

Options:
  --agent <name>     Sync specific agent only
  --tool <name>      Sync specific tool only
  --dry-run          Preview changes without applying them
  --force            Force sync even if versions match
  --update-only      Only update existing tools, don't add new ones
  --help             Show this help message

Examples:
  node sync-tools.js                           # Sync all agents
  node sync-tools.js --agent sample-agent      # Sync specific agent
  node sync-tools.js --dry-run                 # Preview changes
  node sync-tools.js --tool calculator         # Sync specific tool
`);
                process.exit(0);
        }
    }

    // Run sync
    const syncUtility = new ToolSyncUtility();
    syncUtility.sync(options).catch(console.error);
}

module.exports = ToolSyncUtility;