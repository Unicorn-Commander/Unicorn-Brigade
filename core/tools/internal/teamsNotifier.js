/**
 * Teams Notifier Tool - Microsoft Teams integration
 * UC2 Internal Tool v1.0.0
 *
 * Provides Microsoft Teams messaging, adaptive cards, and workflow
 * integration for enterprise communication and collaboration.
 */

const https = require('https');
const crypto = require('crypto');

class TeamsNotifierTool {
    constructor() {
        this.name = 'teamsNotifier';
        this.version = '1.0.0';
        this.description = 'Microsoft Teams messaging and collaboration integration';
        this.category = 'communication';
        this.permissions = ['network', 'external_api', 'messaging', 'teams'];

        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['message', 'card', 'webhook', 'notification', 'meeting', 'channel', 'chat'],
                    default: 'message',
                    description: 'Action to perform in Teams'
                },
                webhookUrl: {
                    type: 'string',
                    format: 'uri',
                    description: 'Teams webhook URL for incoming messages'
                },
                accessToken: {
                    type: 'string',
                    description: 'Microsoft Graph API access token'
                },
                tenantId: {
                    type: 'string',
                    description: 'Azure AD tenant ID'
                },
                teamId: {
                    type: 'string',
                    description: 'Microsoft Teams team ID'
                },
                channelId: {
                    type: 'string',
                    description: 'Teams channel ID'
                },
                chatId: {
                    type: 'string',
                    description: 'Teams chat ID for direct messages'
                },
                userId: {
                    type: 'string',
                    description: 'User ID for mentions or direct messaging'
                },
                text: {
                    type: 'string',
                    maxLength: 28000,
                    description: 'Message text content'
                },
                title: {
                    type: 'string',
                    maxLength: 255,
                    description: 'Message title'
                },
                summary: {
                    type: 'string',
                    maxLength: 255,
                    description: 'Message summary for notifications'
                },
                themeColor: {
                    type: 'string',
                    pattern: '^[0-9A-Fa-f]{6}$',
                    description: 'Hex color code for message theme (without #)'
                },
                activityTitle: {
                    type: 'string',
                    maxLength: 255,
                    description: 'Activity title for feed'
                },
                activitySubtitle: {
                    type: 'string',
                    maxLength: 255,
                    description: 'Activity subtitle'
                },
                activityImage: {
                    type: 'string',
                    format: 'uri',
                    description: 'Activity image URL'
                },
                facts: {
                    type: 'array',
                    description: 'Key-value facts to display',
                    items: {
                        type: 'object',
                        properties: {
                            name: { type: 'string', maxLength: 50 },
                            value: { type: 'string', maxLength: 255 }
                        },
                        required: ['name', 'value']
                    },
                    maxItems: 10
                },
                actions: {
                    type: 'array',
                    description: 'Action buttons for the message',
                    items: {
                        type: 'object',
                        properties: {
                            type: { type: 'string', enum: ['Action.OpenUrl', 'Action.Http', 'Action.ShowCard'] },
                            title: { type: 'string', maxLength: 100 },
                            url: { type: 'string', format: 'uri' },
                            method: { type: 'string', enum: ['GET', 'POST'] },
                            headers: { type: 'object' },
                            body: { type: 'string' }
                        },
                        required: ['type', 'title']
                    },
                    maxItems: 6
                },
                sections: {
                    type: 'array',
                    description: 'Message sections with content',
                    items: {
                        type: 'object',
                        properties: {
                            activityTitle: { type: 'string' },
                            activitySubtitle: { type: 'string' },
                            activityText: { type: 'string' },
                            activityImage: { type: 'string', format: 'uri' },
                            heroImage: {
                                type: 'object',
                                properties: {
                                    image: { type: 'string', format: 'uri' }
                                }
                            },
                            facts: {
                                type: 'array',
                                items: {
                                    type: 'object',
                                    properties: {
                                        name: { type: 'string' },
                                        value: { type: 'string' }
                                    }
                                }
                            },
                            markdown: { type: 'boolean', default: true }
                        }
                    }
                },
                adaptiveCard: {
                    type: 'object',
                    description: 'Full Adaptive Card JSON payload'
                },
                template: {
                    type: 'string',
                    enum: ['alert', 'report', 'approval', 'notification', 'status', 'meeting', 'task', 'custom'],
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
                    description: 'Message priority level'
                },
                mentions: {
                    type: 'array',
                    description: 'User mentions in the message',
                    items: {
                        type: 'object',
                        properties: {
                            id: { type: 'string', description: 'User ID' },
                            name: { type: 'string', description: 'Display name' },
                            email: { type: 'string', format: 'email' }
                        },
                        required: ['id', 'name']
                    }
                },
                importance: {
                    type: 'string',
                    enum: ['low', 'normal', 'high'],
                    default: 'normal',
                    description: 'Message importance level'
                }
            },
            required: ['action'],
            allOf: [
                {
                    if: { properties: { action: { enum: ['message', 'card', 'notification'] } } },
                    then: {
                        anyOf: [
                            { required: ['webhookUrl'] },
                            { required: ['accessToken', 'teamId', 'channelId'] },
                            { required: ['accessToken', 'chatId'] }
                        ]
                    }
                }
            ]
        };

        // Teams color themes based on priority
        this.priorityColors = {
            low: '808080',      // Gray
            normal: '0078D4',   // Teams Blue
            high: 'FF8C00',     // Orange
            urgent: 'DC143C'    // Red
        };

        // Message templates with Teams-specific formatting
        this.templates = {
            alert: {
                title: '🚨 UC2 Alert: {alertType}',
                summary: 'UC2 System Alert',
                themeColor: 'DC143C',
                sections: [{
                    activityTitle: '{alertType}',
                    activitySubtitle: 'System Alert - {severity}',
                    activityText: '{message}',
                    facts: [
                        { name: 'System', value: '{system}' },
                        { name: 'Severity', value: '{severity}' },
                        { name: 'Time', value: '{timestamp}' },
                        { name: 'Location', value: '{location}' }
                    ]
                }],
                actions: [{
                    type: 'Action.OpenUrl',
                    title: 'View Details',
                    url: '{detailsUrl}'
                }]
            },
            report: {
                title: '📊 {reportTitle}',
                summary: 'UC2 Intelligence Report',
                themeColor: '0078D4',
                sections: [{
                    activityTitle: '{reportTitle}',
                    activitySubtitle: 'Generated by {agent}',
                    activityText: '**Executive Summary**\n\n{summary}',
                    facts: [
                        { name: 'Report ID', value: '{reportId}' },
                        { name: 'Generated', value: '{timestamp}' },
                        { name: 'Classification', value: '{classification}' }
                    ]
                }, {
                    activityTitle: 'Key Findings',
                    activityText: '{findings}'
                }, {
                    activityTitle: 'Recommendations',
                    activityText: '{recommendations}'
                }],
                actions: [{
                    type: 'Action.OpenUrl',
                    title: 'Full Report',
                    url: '{reportUrl}'
                }]
            },
            approval: {
                title: '✅ Approval Required: {subject}',
                summary: 'UC2 Approval Request',
                themeColor: 'FF8C00',
                sections: [{
                    activityTitle: '{subject}',
                    activitySubtitle: 'Requested by {requester}',
                    activityText: '{description}',
                    facts: [
                        { name: 'Request Type', value: '{requestType}' },
                        { name: 'Priority', value: '{priority}' },
                        { name: 'Due Date', value: '{dueDate}' },
                        { name: 'Cost', value: '{cost}' }
                    ]
                }],
                actions: [
                    {
                        type: 'Action.Http',
                        title: '✅ Approve',
                        method: 'POST',
                        url: '{approveUrl}',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{"action": "approve", "id": "{requestId}"}'
                    },
                    {
                        type: 'Action.Http',
                        title: '❌ Reject',
                        method: 'POST',
                        url: '{rejectUrl}',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{"action": "reject", "id": "{requestId}"}'
                    }
                ]
            },
            notification: {
                title: '🔔 {title}',
                summary: 'UC2 Notification',
                themeColor: '00B294',
                sections: [{
                    activityTitle: '{title}',
                    activitySubtitle: '{category}',
                    activityText: '{message}',
                    facts: [
                        { name: 'Time', value: '{timestamp}' },
                        { name: 'Source', value: '{source}' }
                    ]
                }]
            },
            status: {
                title: '⚡ System Status: {systemName}',
                summary: 'UC2 System Status Update',
                themeColor: '{statusColor}',
                sections: [{
                    activityTitle: '{systemName}',
                    activitySubtitle: 'Status: {status}',
                    activityText: '{statusMessage}',
                    facts: [
                        { name: 'Status', value: '{status}' },
                        { name: 'Uptime', value: '{uptime}' },
                        { name: 'Last Check', value: '{lastCheck}' },
                        { name: 'Response Time', value: '{responseTime}' }
                    ]
                }],
                actions: [{
                    type: 'Action.OpenUrl',
                    title: 'View Dashboard',
                    url: '{dashboardUrl}'
                }]
            },
            meeting: {
                title: '📅 Meeting: {meetingTitle}',
                summary: 'UC2 Meeting Notification',
                themeColor: '6264A7',
                sections: [{
                    activityTitle: '{meetingTitle}',
                    activitySubtitle: '{organizer} • {duration}',
                    activityText: '{agenda}',
                    facts: [
                        { name: 'Date & Time', value: '{dateTime}' },
                        { name: 'Location', value: '{location}' },
                        { name: 'Attendees', value: '{attendeeCount}' },
                        { name: 'Type', value: '{meetingType}' }
                    ]
                }],
                actions: [
                    {
                        type: 'Action.OpenUrl',
                        title: 'Join Meeting',
                        url: '{joinUrl}'
                    },
                    {
                        type: 'Action.OpenUrl',
                        title: 'View Calendar',
                        url: '{calendarUrl}'
                    }
                ]
            },
            task: {
                title: '📋 Task Assignment: {taskTitle}',
                summary: 'UC2 Task Assignment',
                themeColor: '8764B8',
                sections: [{
                    activityTitle: '{taskTitle}',
                    activitySubtitle: 'Assigned by {assigner}',
                    activityText: '{description}',
                    facts: [
                        { name: 'Priority', value: '{priority}' },
                        { name: 'Due Date', value: '{dueDate}' },
                        { name: 'Estimated Time', value: '{estimatedTime}' },
                        { name: 'Project', value: '{project}' }
                    ]
                }],
                actions: [
                    {
                        type: 'Action.Http',
                        title: '✅ Accept',
                        method: 'POST',
                        url: '{acceptUrl}',
                        headers: { 'Content-Type': 'application/json' },
                        body: '{"action": "accept", "taskId": "{taskId}"}'
                    },
                    {
                        type: 'Action.OpenUrl',
                        title: 'View Details',
                        url: '{taskUrl}'
                    }
                ]
            }
        };

        // Message history and tracking
        this.messageHistory = new Map();
        this.webhookCache = new Map();
        this.maxHistorySize = 2000;

        // Rate limiting
        this.rateLimits = new Map();
        this.defaultRateLimit = { requests: 4, window: 1000 }; // 4 per second (Teams limit)

        // Status color mapping
        this.statusColors = {
            online: '00B294',
            degraded: 'FF8C00',
            offline: 'DC143C',
            maintenance: '6264A7',
            unknown: '808080'
        };
    }

    /**
     * Execute Teams action
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate parameters
            this.validateParams(params);

            // Check rate limits
            if (!this.checkRateLimit(params.webhookUrl || 'api')) {
                throw new Error('Rate limit exceeded for Teams API');
            }

            let result;
            switch (params.action) {
                case 'message':
                    result = await this.sendMessage(params);
                    break;
                case 'card':
                    result = await this.sendAdaptiveCard(params);
                    break;
                case 'webhook':
                    result = await this.sendWebhook(params);
                    break;
                case 'notification':
                    result = await this.sendNotification(params);
                    break;
                case 'meeting':
                    result = await this.createMeeting(params);
                    break;
                case 'channel':
                    result = await this.manageChannel(params);
                    break;
                case 'chat':
                    result = await this.manageChat(params);
                    break;
                default:
                    throw new Error(`Unknown action: ${params.action}`);
            }

            // Update rate limit
            this.updateRateLimit(params.webhookUrl || 'api');

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
     * Send message to Teams
     */
    async sendMessage(params) {
        if (params.webhookUrl) {
            return this.sendWebhook(params);
        } else {
            return this.sendViaGraphApi(params);
        }
    }

    /**
     * Send via Teams webhook
     */
    async sendWebhook(params) {
        if (!params.webhookUrl) {
            throw new Error('Webhook URL required');
        }

        // Prepare message card
        const messageCard = this.prepareMessageCard(params);

        // Send webhook
        if (params.webhookUrl.includes('mock') || params.provider === 'mock') {
            return this.sendMockWebhook(messageCard, params);
        }

        const result = await this.makeWebhookRequest(params.webhookUrl, messageCard);

        // Log message
        this.logMessage(result, params);

        return {
            messageId: result.id || 'webhook_' + crypto.randomUUID(),
            webhook: true,
            title: messageCard.title,
            sections: messageCard.sections?.length || 0
        };
    }

    /**
     * Send Adaptive Card
     */
    async sendAdaptiveCard(params) {
        let cardPayload;

        if (params.adaptiveCard) {
            cardPayload = params.adaptiveCard;
        } else {
            cardPayload = this.createAdaptiveCard(params);
        }

        if (params.webhookUrl) {
            return this.makeWebhookRequest(params.webhookUrl, {
                type: 'message',
                attachments: [{
                    contentType: 'application/vnd.microsoft.card.adaptive',
                    content: cardPayload
                }]
            });
        } else {
            return this.sendViaGraphApi({
                ...params,
                attachments: [{
                    contentType: 'application/vnd.microsoft.card.adaptive',
                    content: cardPayload
                }]
            });
        }
    }

    /**
     * Send via Microsoft Graph API
     */
    async sendViaGraphApi(params) {
        if (!params.accessToken) {
            return this.sendMockGraphApi(params);
        }

        // Microsoft Graph API implementation would go here
        // For now, return mock result
        return this.sendMockGraphApi(params);
    }

    /**
     * Prepare message card for webhook
     */
    prepareMessageCard(params) {
        let messageCard = {};

        if (params.template) {
            const template = this.templates[params.template];
            if (!template) {
                throw new Error(`Unknown template: ${params.template}`);
            }

            messageCard = JSON.parse(JSON.stringify(template));
            const templateData = params.templateData || {};

            // Add default template variables
            templateData.timestamp = templateData.timestamp || new Date().toLocaleString();
            templateData.system = templateData.system || 'UC2';

            // Add status color mapping
            if (templateData.status && this.statusColors[templateData.status.toLowerCase()]) {
                templateData.statusColor = this.statusColors[templateData.status.toLowerCase()];
            }

            // Process template placeholders
            messageCard = this.processTemplateObject(messageCard, templateData);

        } else {
            // Build message card from individual properties
            messageCard = {
                '@type': 'MessageCard',
                '@context': 'https://schema.org/extensions'
            };

            if (params.title) messageCard.title = params.title;
            if (params.summary) messageCard.summary = params.summary;
            if (params.text) messageCard.text = params.text;
            if (params.themeColor) messageCard.themeColor = params.themeColor;
            if (params.sections) messageCard.sections = params.sections;
            if (params.actions) messageCard.potentialAction = params.actions;
        }

        // Apply priority color if not set
        if (!messageCard.themeColor && params.priority) {
            messageCard.themeColor = this.priorityColors[params.priority];
        }

        // Add context info
        if (!messageCard.summary) {
            messageCard.summary = params.title || 'UC2 Teams Message';
        }

        return messageCard;
    }

    /**
     * Create Adaptive Card
     */
    createAdaptiveCard(params) {
        const card = {
            type: 'AdaptiveCard',
            version: '1.4',
            body: []
        };

        // Add title
        if (params.title) {
            card.body.push({
                type: 'TextBlock',
                text: params.title,
                size: 'Large',
                weight: 'Bolder'
            });
        }

        // Add text content
        if (params.text) {
            card.body.push({
                type: 'TextBlock',
                text: params.text,
                wrap: true
            });
        }

        // Add facts
        if (params.facts && params.facts.length > 0) {
            card.body.push({
                type: 'FactSet',
                facts: params.facts
            });
        }

        // Add actions
        if (params.actions && params.actions.length > 0) {
            card.actions = params.actions.map(action => ({
                type: action.type,
                title: action.title,
                url: action.url,
                method: action.method,
                headers: action.headers,
                body: action.body
            }));
        }

        return card;
    }

    /**
     * Send notification
     */
    async sendNotification(params) {
        return this.sendMessage({
            ...params,
            template: params.template || 'notification'
        });
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
     * Mock implementations for testing
     */
    async sendMockWebhook(messageCard, params) {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 200));

        return {
            id: 'mock_' + crypto.randomUUID(),
            type: 'webhook',
            title: messageCard.title,
            status: 'sent',
            mock: true
        };
    }

    async sendMockGraphApi(params) {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 300));

        return {
            id: 'mock_' + crypto.randomUUID(),
            type: 'graph_api',
            teamId: params.teamId,
            channelId: params.channelId,
            chatId: params.chatId,
            status: 'sent',
            mock: true
        };
    }

    /**
     * Make Teams webhook request
     */
    async makeWebhookRequest(webhookUrl, messageCard) {
        if (webhookUrl.includes('mock')) {
            return { id: 'mock_' + crypto.randomUUID(), mock: true };
        }

        const url = new URL(webhookUrl);

        return new Promise((resolve, reject) => {
            const options = {
                hostname: url.hostname,
                port: 443,
                path: url.pathname + url.search,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'User-Agent': 'UC2TeamsBot/1.0.0'
                }
            };

            const req = https.request(options, res => {
                let responseData = '';
                res.on('data', chunk => responseData += chunk);
                res.on('end', () => {
                    if (res.statusCode >= 400) {
                        reject(new Error(`Teams webhook failed: HTTP ${res.statusCode}`));
                    } else {
                        resolve({
                            id: 'teams_' + crypto.randomUUID(),
                            status: 'sent',
                            statusCode: res.statusCode
                        });
                    }
                });
            });

            req.on('error', reject);
            req.write(JSON.stringify(messageCard));
            req.end();
        });
    }

    /**
     * Placeholder methods for advanced features
     */
    async createMeeting(params) {
        // Meeting creation would be implemented here using Graph API
        return {
            mock: true,
            action: 'meeting',
            message: 'Meeting creation not yet implemented',
            meetingId: 'mock_meeting_' + crypto.randomUUID()
        };
    }

    async manageChannel(params) {
        // Channel management would be implemented here
        return {
            mock: true,
            action: 'channel',
            message: 'Channel management not yet implemented',
            channelId: params.channelId
        };
    }

    async manageChat(params) {
        // Chat management would be implemented here
        return {
            mock: true,
            action: 'chat',
            message: 'Chat management not yet implemented',
            chatId: params.chatId
        };
    }

    /**
     * Helper methods
     */
    validateParams(params) {
        if (params.action === 'webhook' && !params.webhookUrl) {
            throw new Error('Webhook URL required for webhook action');
        }

        if (params.themeColor && !/^[0-9A-Fa-f]{6}$/.test(params.themeColor)) {
            throw new Error('Invalid hex color format. Use 6-digit hex without #');
        }

        if (params.text && params.text.length > 28000) {
            throw new Error('Message text exceeds Teams limit of 28,000 characters');
        }

        if (params.facts && params.facts.length > 10) {
            throw new Error('Maximum 10 facts allowed per message');
        }

        if (params.actions && params.actions.length > 6) {
            throw new Error('Maximum 6 actions allowed per message');
        }
    }

    checkRateLimit(key) {
        const limit = this.rateLimits.get(key) || {
            count: 0,
            resetTime: Date.now() + this.defaultRateLimit.window
        };

        if (Date.now() > limit.resetTime) {
            limit.count = 0;
            limit.resetTime = Date.now() + this.defaultRateLimit.window;
        }

        return limit.count < this.defaultRateLimit.requests;
    }

    updateRateLimit(key) {
        const limit = this.rateLimits.get(key) || {
            count: 0,
            resetTime: Date.now() + this.defaultRateLimit.window
        };
        limit.count++;
        this.rateLimits.set(key, limit);
    }

    logMessage(result, params) {
        const logEntry = {
            messageId: result.id,
            action: params.action,
            title: params.title,
            template: params.template,
            priority: params.priority,
            timestamp: new Date().toISOString(),
            webhook: !!params.webhookUrl
        };

        if (this.messageHistory.size >= this.maxHistorySize) {
            const firstKey = this.messageHistory.keys().next().value;
            this.messageHistory.delete(firstKey);
        }

        this.messageHistory.set(result.id, logEntry);
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
                'Send rich messages to Microsoft Teams channels',
                'Webhook integration for external notifications',
                'Adaptive Card support with interactive elements',
                'Message templates for common scenarios',
                'Microsoft Graph API integration (planned)',
                'Meeting creation and calendar integration (planned)',
                'Channel and chat management (planned)',
                'Action buttons and user interactions',
                'Fact sets and structured data display',
                'Priority-based color coding',
                'Rate limiting and API compliance'
            ],
            templates: Object.keys(this.templates),
            supportedActions: ['message', 'card', 'webhook', 'notification', 'meeting', 'channel', 'chat'],
            stats: {
                messagesSent: this.messageHistory.size,
                rateLimitEntries: this.rateLimits.size,
                webhooksCached: this.webhookCache.size
            }
        };
    }
}

module.exports = TeamsNotifierTool;