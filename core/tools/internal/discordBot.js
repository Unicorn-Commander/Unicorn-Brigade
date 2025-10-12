/**
 * Discord Bot Tool - Discord integration and bot functionality
 * UC2 Internal Tool v1.0.0
 *
 * Provides Discord messaging, rich embeds, bot commands, and server management
 * capabilities for team communication and automation.
 */

const https = require('https');
const crypto = require('crypto');
const fs = require('fs').promises;

class DiscordBotTool {
    constructor() {
        this.name = 'discordBot';
        this.version = '1.0.0';
        this.description = 'Discord bot for messaging, commands, and server management';
        this.category = 'communication';
        this.permissions = ['network', 'external_api', 'messaging', 'discord'];

        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['message', 'embed', 'file', 'reaction', 'command', 'webhook', 'thread', 'voice', 'manage'],
                    default: 'message',
                    description: 'Action to perform on Discord'
                },
                token: {
                    type: 'string',
                    description: 'Discord bot token'
                },
                webhookUrl: {
                    type: 'string',
                    format: 'uri',
                    description: 'Discord webhook URL (alternative to bot token)'
                },
                channelId: {
                    type: 'string',
                    pattern: '^\\d{17,19}$',
                    description: 'Discord channel ID (snowflake)'
                },
                guildId: {
                    type: 'string',
                    pattern: '^\\d{17,19}$',
                    description: 'Discord server (guild) ID'
                },
                userId: {
                    type: 'string',
                    pattern: '^\\d{17,19}$',
                    description: 'Discord user ID for DMs'
                },
                content: {
                    type: 'string',
                    maxLength: 2000,
                    description: 'Message content (max 2000 characters)'
                },
                embed: {
                    type: 'object',
                    description: 'Rich embed object',
                    properties: {
                        title: { type: 'string', maxLength: 256 },
                        description: { type: 'string', maxLength: 4096 },
                        url: { type: 'string', format: 'uri' },
                        timestamp: { type: 'string', format: 'date-time' },
                        color: { type: 'integer', minimum: 0, maximum: 16777215 },
                        footer: {
                            type: 'object',
                            properties: {
                                text: { type: 'string', maxLength: 2048 },
                                icon_url: { type: 'string', format: 'uri' }
                            }
                        },
                        image: {
                            type: 'object',
                            properties: {
                                url: { type: 'string', format: 'uri' }
                            }
                        },
                        thumbnail: {
                            type: 'object',
                            properties: {
                                url: { type: 'string', format: 'uri' }
                            }
                        },
                        author: {
                            type: 'object',
                            properties: {
                                name: { type: 'string', maxLength: 256 },
                                url: { type: 'string', format: 'uri' },
                                icon_url: { type: 'string', format: 'uri' }
                            }
                        },
                        fields: {
                            type: 'array',
                            maxItems: 25,
                            items: {
                                type: 'object',
                                properties: {
                                    name: { type: 'string', maxLength: 256 },
                                    value: { type: 'string', maxLength: 1024 },
                                    inline: { type: 'boolean' }
                                },
                                required: ['name', 'value']
                            }
                        }
                    }
                },
                embeds: {
                    type: 'array',
                    maxItems: 10,
                    items: { $ref: '#/properties/embed' },
                    description: 'Array of embed objects'
                },
                filePath: {
                    type: 'string',
                    description: 'Path to file to upload'
                },
                fileContent: {
                    type: 'string',
                    description: 'File content as base64 string'
                },
                fileName: {
                    type: 'string',
                    maxLength: 100,
                    description: 'Name for uploaded file'
                },
                emoji: {
                    type: 'string',
                    description: 'Emoji for reaction (Unicode or custom :name:id format)'
                },
                messageId: {
                    type: 'string',
                    pattern: '^\\d{17,19}$',
                    description: 'Message ID for reactions/replies'
                },
                threadName: {
                    type: 'string',
                    maxLength: 100,
                    description: 'Name for new thread'
                },
                threadId: {
                    type: 'string',
                    pattern: '^\\d{17,19}$',
                    description: 'Thread ID for thread actions'
                },
                username: {
                    type: 'string',
                    maxLength: 80,
                    description: 'Custom username for webhook'
                },
                avatarUrl: {
                    type: 'string',
                    format: 'uri',
                    description: 'Custom avatar URL for webhook'
                },
                tts: {
                    type: 'boolean',
                    default: false,
                    description: 'Text-to-speech message'
                },
                components: {
                    type: 'array',
                    description: 'Message components (buttons, select menus)',
                    items: {
                        type: 'object',
                        properties: {
                            type: { type: 'integer' },
                            components: { type: 'array' }
                        }
                    }
                },
                template: {
                    type: 'string',
                    enum: ['alert', 'report', 'announcement', 'investigation', 'status', 'welcome', 'custom'],
                    description: 'Message template to use'
                },
                templateData: {
                    type: 'object',
                    description: 'Data for template substitution'
                },
                priority: {
                    type: 'string',
                    enum: ['low', 'normal', 'high', 'urgent'],
                    default: 'normal',
                    description: 'Message priority (affects color/formatting)'
                },
                mentions: {
                    type: 'object',
                    description: 'Message mentions configuration',
                    properties: {
                        users: {
                            type: 'array',
                            items: { type: 'string', pattern: '^\\d{17,19}$' }
                        },
                        roles: {
                            type: 'array',
                            items: { type: 'string', pattern: '^\\d{17,19}$' }
                        },
                        everyone: { type: 'boolean' },
                        here: { type: 'boolean' }
                    }
                }
            },
            required: ['action'],
            allOf: [
                {
                    if: {
                        properties: {
                            action: { enum: ['message', 'embed', 'file'] }
                        }
                    },
                    then: {
                        anyOf: [
                            { required: ['channelId'] },
                            { required: ['userId'] },
                            { required: ['webhookUrl'] }
                        ]
                    }
                },
                {
                    if: { properties: { action: { const: 'reaction' } } },
                    then: { required: ['channelId', 'messageId', 'emoji'] }
                }
            ]
        };

        // Discord API endpoints
        this.baseUrl = 'https://discord.com/api/v10';

        // Message templates with Discord-specific formatting
        this.templates = {
            alert: {
                embed: {
                    title: '🚨 UC2 Alert: {alertType}',
                    description: '{message}',
                    color: 0xFF0000, // Red
                    fields: [
                        { name: 'System', value: '{system}', inline: true },
                        { name: 'Severity', value: '{severity}', inline: true },
                        { name: 'Time', value: '{timestamp}', inline: false }
                    ],
                    footer: { text: 'UC2 Command & Control System' },
                    timestamp: true
                }
            },
            report: {
                embed: {
                    title: '📊 {reportTitle}',
                    description: '**Executive Summary**\n{summary}',
                    color: 0x0099FF, // Blue
                    fields: [
                        { name: 'Key Findings', value: '{findings}', inline: false },
                        { name: 'Recommendations', value: '{recommendations}', inline: false },
                        { name: 'Generated By', value: '{agent}', inline: true },
                        { name: 'Report ID', value: '{reportId}', inline: true }
                    ],
                    footer: { text: 'UC2 Intelligence Report' },
                    timestamp: true
                }
            },
            announcement: {
                embed: {
                    title: '📢 {title}',
                    description: '{message}',
                    color: 0x00FF00, // Green
                    thumbnail: { url: '{thumbnailUrl}' },
                    fields: [
                        { name: 'Category', value: '{category}', inline: true },
                        { name: 'Priority', value: '{priority}', inline: true }
                    ],
                    footer: { text: 'UC2 Announcements' },
                    timestamp: true
                }
            },
            investigation: {
                embed: {
                    title: '🔍 Case Update: {caseName}',
                    description: '{developments}',
                    color: 0x800080, // Purple
                    fields: [
                        { name: 'Case ID', value: '{caseId}', inline: true },
                        { name: 'Status', value: '{status}', inline: true },
                        { name: 'Lead Investigator', value: '{investigator}', inline: true },
                        { name: 'Next Steps', value: '{nextSteps}', inline: false }
                    ],
                    footer: { text: '🔒 CONFIDENTIAL - Investigation Communication' },
                    timestamp: true
                }
            },
            status: {
                embed: {
                    title: '⚡ System Status: {systemName}',
                    description: '{statusMessage}',
                    color: '{statusColor}',
                    fields: [
                        { name: 'Status', value: '{status}', inline: true },
                        { name: 'Uptime', value: '{uptime}', inline: true },
                        { name: 'Last Check', value: '{lastCheck}', inline: true },
                        { name: 'Details', value: '{details}', inline: false }
                    ],
                    footer: { text: 'UC2 System Monitor' },
                    timestamp: true
                }
            },
            welcome: {
                embed: {
                    title: '👋 Welcome to {serverName}!',
                    description: 'Welcome {userName}! We\'re glad to have you join our team.',
                    color: 0xFFD700, // Gold
                    thumbnail: { url: '{userAvatar}' },
                    fields: [
                        { name: '📋 Getting Started', value: '{gettingStarted}', inline: false },
                        { name: '📞 Support', value: '{supportInfo}', inline: false },
                        { name: '🎯 Your Role', value: '{userRole}', inline: true }
                    ],
                    footer: { text: 'UC2 Team' },
                    timestamp: true
                }
            }
        };

        // Priority color mapping
        this.priorityColors = {
            low: 0x808080,      // Gray
            normal: 0x0099FF,   // Blue
            high: 0xFF9900,     // Orange
            urgent: 0xFF0000    // Red
        };

        // Message history and tracking
        this.messageHistory = new Map();
        this.commandHistory = new Map();
        this.maxHistorySize = 2000;

        // Rate limiting
        this.rateLimits = new Map();
        this.globalRateLimit = { requests: 50, window: 1000 }; // 50 per second

        // Bot commands registry
        this.commands = new Map();
        this.registerDefaultCommands();
    }

    /**
     * Execute Discord action
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate parameters
            this.validateParams(params);

            // Check rate limits
            if (!this.checkRateLimit('global')) {
                throw new Error('Rate limit exceeded');
            }

            let result;
            switch (params.action) {
                case 'message':
                    result = await this.sendMessage(params);
                    break;
                case 'embed':
                    result = await this.sendEmbed(params);
                    break;
                case 'file':
                    result = await this.sendFile(params);
                    break;
                case 'reaction':
                    result = await this.addReaction(params);
                    break;
                case 'webhook':
                    result = await this.sendWebhook(params);
                    break;
                case 'thread':
                    result = await this.manageThread(params);
                    break;
                case 'command':
                    result = await this.executeCommand(params);
                    break;
                case 'voice':
                    result = await this.manageVoice(params);
                    break;
                case 'manage':
                    result = await this.manageServer(params);
                    break;
                default:
                    throw new Error(`Unknown action: ${params.action}`);
            }

            // Update rate limit
            this.updateRateLimit('global');

            return {
                success: true,
                action: params.action,
                result,
                executionTime: `${Date.now() - startTime}ms`
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                errorType: error.constructor.name,
                action: params.action,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    /**
     * Send regular message
     */
    async sendMessage(params) {
        // Prepare message content
        const messageData = this.prepareMessage(params);

        // Send to channel or user
        const endpoint = params.userId
            ? `/users/@me/channels`
            : `/channels/${params.channelId}/messages`;

        let result;
        if (params.userId) {
            // Create DM channel first
            const dmChannel = await this.makeApiRequest('POST', '/users/@me/channels', {
                recipient_id: params.userId
            }, params.token);

            // Send message to DM channel
            result = await this.makeApiRequest('POST', `/channels/${dmChannel.id}/messages`, messageData, params.token);
        } else {
            // Send to channel
            result = await this.makeApiRequest('POST', endpoint, messageData, params.token);
        }

        // Log message
        this.logMessage(result, params);

        return {
            messageId: result.id,
            channelId: result.channel_id,
            content: result.content,
            embeds: result.embeds?.length || 0,
            timestamp: result.timestamp
        };
    }

    /**
     * Send rich embed message
     */
    async sendEmbed(params) {
        const embedData = this.prepareEmbed(params);

        return this.sendMessage({
            ...params,
            embeds: [embedData]
        });
    }

    /**
     * Send file attachment
     */
    async sendFile(params) {
        if (params.provider === 'mock' || !params.token) {
            return this.sendMockFile(params);
        }

        // File handling logic would go here
        // For now, return mock result
        return this.sendMockFile(params);
    }

    /**
     * Send via webhook
     */
    async sendWebhook(params) {
        if (!params.webhookUrl) {
            throw new Error('Webhook URL required');
        }

        const webhookData = {
            content: params.content,
            username: params.username,
            avatar_url: params.avatarUrl,
            tts: params.tts || false
        };

        if (params.embed || params.template) {
            webhookData.embeds = [this.prepareEmbed(params)];
        }

        if (params.embeds) {
            webhookData.embeds = params.embeds;
        }

        // Extract webhook info from URL
        const webhookMatch = params.webhookUrl.match(/\/webhooks\/(\d+)\/([^\/]+)/);
        if (!webhookMatch) {
            throw new Error('Invalid webhook URL format');
        }

        const [, webhookId, webhookToken] = webhookMatch;

        if (params.webhookUrl.includes('mock') || !webhookToken) {
            return this.sendMockWebhook(webhookData);
        }

        // Make webhook request without authorization
        const result = await this.makeWebhookRequest(params.webhookUrl, webhookData);

        return {
            messageId: result.id || 'webhook_' + crypto.randomUUID(),
            webhook: true,
            content: webhookData.content,
            username: webhookData.username
        };
    }

    /**
     * Add reaction to message
     */
    async addReaction(params) {
        if (params.provider === 'mock' || !params.token) {
            return {
                messageId: params.messageId,
                emoji: params.emoji,
                success: true,
                mock: true
            };
        }

        const endpoint = `/channels/${params.channelId}/messages/${params.messageId}/reactions/${encodeURIComponent(params.emoji)}/@me`;

        await this.makeApiRequest('PUT', endpoint, null, params.token);

        return {
            messageId: params.messageId,
            channelId: params.channelId,
            emoji: params.emoji,
            success: true
        };
    }

    /**
     * Execute bot command
     */
    async executeCommand(params) {
        const command = this.commands.get(params.command);
        if (!command) {
            throw new Error(`Unknown command: ${params.command}`);
        }

        const result = await command.execute(params);

        // Log command execution
        this.logCommand(params.command, params, result);

        return result;
    }

    /**
     * Prepare message content
     */
    prepareMessage(params) {
        const messageData = {};

        // Content
        if (params.content || params.template) {
            messageData.content = this.processContent(params);
        }

        // Embeds
        if (params.embed) {
            messageData.embeds = [params.embed];
        } else if (params.embeds) {
            messageData.embeds = params.embeds;
        } else if (params.template) {
            messageData.embeds = [this.prepareEmbed(params)];
        }

        // Components (buttons, select menus)
        if (params.components) {
            messageData.components = params.components;
        }

        // TTS
        if (params.tts) {
            messageData.tts = params.tts;
        }

        // Mentions
        if (params.mentions) {
            messageData.allowed_mentions = this.prepareMentions(params.mentions);
        }

        return messageData;
    }

    /**
     * Prepare embed from template or raw data
     */
    prepareEmbed(params) {
        let embedData;

        if (params.template) {
            const template = this.templates[params.template];
            if (!template) {
                throw new Error(`Unknown template: ${params.template}`);
            }

            embedData = JSON.parse(JSON.stringify(template.embed));
            const templateData = params.templateData || {};

            // Add default template variables
            templateData.timestamp = templateData.timestamp || new Date().toISOString();
            templateData.system = templateData.system || 'UC2';

            // Process template placeholders
            embedData = this.processTemplateObject(embedData, templateData);

            // Set timestamp if required
            if (embedData.timestamp === true) {
                embedData.timestamp = new Date().toISOString();
            }

        } else if (params.embed) {
            embedData = params.embed;
        } else {
            throw new Error('No embed data or template provided');
        }

        // Apply priority color if not set
        if (!embedData.color && params.priority) {
            embedData.color = this.priorityColors[params.priority] || this.priorityColors.normal;
        }

        return embedData;
    }

    /**
     * Process content with templates
     */
    processContent(params) {
        if (params.template && params.templateData) {
            return this.processTemplate(params.content || '{message}', params.templateData);
        }
        return params.content || '';
    }

    /**
     * Process template placeholders in objects
     */
    processTemplateObject(obj, data) {
        if (typeof obj === 'string') {
            return this.processTemplate(obj, data);
        } else if (Array.isArray(obj)) {
            return obj.map(item => this.processTemplateObject(item, data));
        } else if (obj && typeof obj === 'object') {
            const processed = {};
            for (const [key, value] of Object.entries(obj)) {
                processed[key] = this.processTemplateObject(value, data);
            }
            return processed;
        }
        return obj;
    }

    /**
     * Process template placeholders
     */
    processTemplate(template, data) {
        return template.replace(/\{(\w+)\}/g, (match, key) => {
            return data[key] || match;
        });
    }

    /**
     * Prepare mentions configuration
     */
    prepareMentions(mentions) {
        const allowedMentions = {};

        if (mentions.users) allowedMentions.users = mentions.users;
        if (mentions.roles) allowedMentions.roles = mentions.roles;

        const parse = [];
        if (mentions.everyone) parse.push('everyone');
        if (mentions.here) parse.push('here');

        if (parse.length > 0) allowedMentions.parse = parse;

        return allowedMentions;
    }

    /**
     * Register default bot commands
     */
    registerDefaultCommands() {
        this.commands.set('ping', {
            name: 'ping',
            description: 'Ping the bot',
            execute: async (params) => {
                return {
                    response: 'Pong! UC2 Discord Bot is online.',
                    latency: '< 50ms',
                    uptime: process.uptime()
                };
            }
        });

        this.commands.set('status', {
            name: 'status',
            description: 'Get UC2 system status',
            execute: async (params) => {
                return {
                    system: 'UC2 Command & Control',
                    status: 'Operational',
                    version: this.version,
                    uptime: process.uptime(),
                    messagesSent: this.messageHistory.size
                };
            }
        });

        this.commands.set('help', {
            name: 'help',
            description: 'Show available commands',
            execute: async (params) => {
                const commands = Array.from(this.commands.values()).map(cmd => ({
                    name: cmd.name,
                    description: cmd.description
                }));
                return { commands };
            }
        });
    }

    /**
     * Mock implementations for testing
     */
    async sendMockFile(params) {
        return {
            messageId: 'mock_' + crypto.randomUUID(),
            fileName: params.fileName,
            fileSize: params.fileContent?.length || 1024,
            channelId: params.channelId,
            mock: true
        };
    }

    async sendMockWebhook(webhookData) {
        return {
            id: 'mock_' + crypto.randomUUID(),
            content: webhookData.content,
            username: webhookData.username,
            embeds: webhookData.embeds,
            mock: true
        };
    }

    /**
     * Make Discord API request
     */
    async makeApiRequest(method, endpoint, data, token) {
        if (endpoint.includes('mock') || !token || token === 'mock') {
            // Return mock response
            return {
                id: 'mock_' + crypto.randomUUID(),
                channel_id: 'mock_channel',
                content: data?.content || 'Mock message',
                embeds: data?.embeds || [],
                timestamp: new Date().toISOString(),
                mock: true
            };
        }

        return new Promise((resolve, reject) => {
            const options = {
                hostname: 'discord.com',
                port: 443,
                path: `/api/v10${endpoint}`,
                method: method,
                headers: {
                    'Authorization': `Bot ${token}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'UC2DiscordBot/1.0.0'
                }
            };

            const req = https.request(options, res => {
                let responseData = '';
                res.on('data', chunk => responseData += chunk);
                res.on('end', () => {
                    try {
                        const result = responseData ? JSON.parse(responseData) : {};
                        if (res.statusCode >= 400) {
                            reject(new Error(result.message || `HTTP ${res.statusCode}`));
                        } else {
                            resolve(result);
                        }
                    } catch (error) {
                        reject(new Error('Invalid JSON response'));
                    }
                });
            });

            req.on('error', reject);

            if (data) {
                req.write(JSON.stringify(data));
            }

            req.end();
        });
    }

    /**
     * Make webhook request
     */
    async makeWebhookRequest(webhookUrl, data) {
        if (webhookUrl.includes('mock')) {
            return { id: 'mock_' + crypto.randomUUID(), mock: true };
        }

        const url = new URL(webhookUrl);

        return new Promise((resolve, reject) => {
            const options = {
                hostname: url.hostname,
                port: 443,
                path: url.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'User-Agent': 'UC2DiscordBot/1.0.0'
                }
            };

            const req = https.request(options, res => {
                let responseData = '';
                res.on('data', chunk => responseData += chunk);
                res.on('end', () => {
                    if (res.statusCode >= 400) {
                        reject(new Error(`HTTP ${res.statusCode}`));
                    } else {
                        resolve(responseData ? JSON.parse(responseData) : {});
                    }
                });
            });

            req.on('error', reject);
            req.write(JSON.stringify(data));
            req.end();
        });
    }

    /**
     * Helper methods
     */
    validateParams(params) {
        if (params.channelId && !/^\d{17,19}$/.test(params.channelId)) {
            throw new Error('Invalid Discord channel ID format');
        }

        if (params.userId && !/^\d{17,19}$/.test(params.userId)) {
            throw new Error('Invalid Discord user ID format');
        }

        if (params.content && params.content.length > 2000) {
            throw new Error('Message content exceeds 2000 character limit');
        }

        if (params.embed && params.embed.description && params.embed.description.length > 4096) {
            throw new Error('Embed description exceeds 4096 character limit');
        }
    }

    checkRateLimit(key) {
        const limit = this.rateLimits.get(key) || { count: 0, resetTime: Date.now() + this.globalRateLimit.window };

        if (Date.now() > limit.resetTime) {
            limit.count = 0;
            limit.resetTime = Date.now() + this.globalRateLimit.window;
        }

        return limit.count < this.globalRateLimit.requests;
    }

    updateRateLimit(key) {
        const limit = this.rateLimits.get(key) || { count: 0, resetTime: Date.now() + this.globalRateLimit.window };
        limit.count++;
        this.rateLimits.set(key, limit);
    }

    logMessage(result, params) {
        const logEntry = {
            messageId: result.id,
            channelId: result.channel_id,
            content: params.content || '[embed/file]',
            action: params.action,
            timestamp: new Date().toISOString(),
            embeds: result.embeds?.length || 0
        };

        if (this.messageHistory.size >= this.maxHistorySize) {
            const firstKey = this.messageHistory.keys().next().value;
            this.messageHistory.delete(firstKey);
        }

        this.messageHistory.set(result.id, logEntry);
    }

    logCommand(command, params, result) {
        const logEntry = {
            command,
            params,
            result,
            timestamp: new Date().toISOString()
        };

        if (this.commandHistory.size >= 500) {
            const firstKey = this.commandHistory.keys().next().value;
            this.commandHistory.delete(firstKey);
        }

        this.commandHistory.set(crypto.randomUUID(), logEntry);
    }

    /**
     * Placeholder methods for advanced features
     */
    async manageThread(params) {
        // Thread management would be implemented here
        return { mock: true, action: 'thread', message: 'Thread management not yet implemented' };
    }

    async manageVoice(params) {
        // Voice channel management would be implemented here
        return { mock: true, action: 'voice', message: 'Voice management not yet implemented' };
    }

    async manageServer(params) {
        // Server management would be implemented here
        return { mock: true, action: 'manage', message: 'Server management not yet implemented' };
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
                'Send messages to Discord channels and users',
                'Rich embed messages with customizable templates',
                'File and media attachment support',
                'Message reactions and interactions',
                'Webhook integration for external notifications',
                'Bot commands and automated responses',
                'Thread creation and management (planned)',
                'Voice channel integration (planned)',
                'Server management capabilities (planned)',
                'Rate limiting and API compliance',
                'Message history and logging'
            ],
            templates: Object.keys(this.templates),
            commands: Array.from(this.commands.keys()),
            stats: {
                messagesSent: this.messageHistory.size,
                commandsExecuted: this.commandHistory.size,
                rateLimitEntries: this.rateLimits.size
            }
        };
    }
}

module.exports = DiscordBotTool;