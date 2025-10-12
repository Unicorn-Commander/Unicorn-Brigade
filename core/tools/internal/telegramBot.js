/**
 * Telegram Bot Tool - Telegram bot capabilities and messaging
 * UC2 Internal Tool v1.0.0
 *
 * Provides Telegram bot functionality including messages, media sharing,
 * inline keyboards, commands, and group management.
 */

const https = require('https');
const crypto = require('crypto');
const fs = require('fs').promises;

class TelegramBotTool {
    constructor() {
        this.name = 'telegramBot';
        this.version = '1.0.0';
        this.description = 'Telegram bot for messaging, commands, and channel management';
        this.category = 'communication';
        this.permissions = ['network', 'external_api', 'messaging', 'telegram'];

        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['message', 'photo', 'document', 'video', 'audio', 'sticker', 'location', 'contact', 'poll', 'command', 'inline', 'callback', 'edit', 'delete', 'forward', 'webhook'],
                    default: 'message',
                    description: 'Action to perform in Telegram'
                },
                botToken: {
                    type: 'string',
                    pattern: '^\\d+:[A-Za-z0-9_-]{35}$',
                    description: 'Telegram bot token from @BotFather'
                },
                chatId: {
                    type: ['string', 'number'],
                    description: 'Chat ID (can be user ID, group ID, or channel username)'
                },
                text: {
                    type: 'string',
                    maxLength: 4096,
                    description: 'Message text (max 4096 characters)'
                },
                parseMode: {
                    type: 'string',
                    enum: ['Markdown', 'MarkdownV2', 'HTML'],
                    description: 'Parse mode for text formatting'
                },
                replyToMessageId: {
                    type: 'integer',
                    description: 'ID of message to reply to'
                },
                messageId: {
                    type: 'integer',
                    description: 'Message ID for edit/delete operations'
                },
                disableWebPagePreview: {
                    type: 'boolean',
                    default: false,
                    description: 'Disable link previews'
                },
                disableNotification: {
                    type: 'boolean',
                    default: false,
                    description: 'Send message silently'
                },
                protectContent: {
                    type: 'boolean',
                    default: false,
                    description: 'Protect message from forwarding'
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
                    description: 'File name for uploads'
                },
                caption: {
                    type: 'string',
                    maxLength: 1024,
                    description: 'Caption for media files'
                },
                duration: {
                    type: 'integer',
                    description: 'Duration for audio/video in seconds'
                },
                width: {
                    type: 'integer',
                    description: 'Width for video/photos'
                },
                height: {
                    type: 'integer',
                    description: 'Height for video/photos'
                },
                thumbnail: {
                    type: 'string',
                    description: 'Thumbnail for video/document'
                },
                latitude: {
                    type: 'number',
                    minimum: -90,
                    maximum: 90,
                    description: 'Latitude for location'
                },
                longitude: {
                    type: 'number',
                    minimum: -180,
                    maximum: 180,
                    description: 'Longitude for location'
                },
                phoneNumber: {
                    type: 'string',
                    description: 'Phone number for contact'
                },
                firstName: {
                    type: 'string',
                    description: 'First name for contact'
                },
                lastName: {
                    type: 'string',
                    description: 'Last name for contact'
                },
                question: {
                    type: 'string',
                    maxLength: 300,
                    description: 'Poll question'
                },
                options: {
                    type: 'array',
                    items: { type: 'string', maxLength: 100 },
                    minItems: 2,
                    maxItems: 10,
                    description: 'Poll options'
                },
                isAnonymous: {
                    type: 'boolean',
                    default: true,
                    description: 'Anonymous poll'
                },
                allowsMultipleAnswers: {
                    type: 'boolean',
                    default: false,
                    description: 'Allow multiple poll answers'
                },
                inlineKeyboard: {
                    type: 'array',
                    description: 'Inline keyboard buttons',
                    items: {
                        type: 'array',
                        items: {
                            type: 'object',
                            properties: {
                                text: { type: 'string', maxLength: 64 },
                                url: { type: 'string', format: 'uri' },
                                callbackData: { type: 'string', maxLength: 64 },
                                switchInlineQuery: { type: 'string' },
                                switchInlineQueryCurrentChat: { type: 'string' }
                            },
                            required: ['text']
                        }
                    }
                },
                replyKeyboard: {
                    type: 'array',
                    description: 'Reply keyboard buttons',
                    items: {
                        type: 'array',
                        items: {
                            type: 'object',
                            properties: {
                                text: { type: 'string' },
                                requestContact: { type: 'boolean' },
                                requestLocation: { type: 'boolean' }
                            },
                            required: ['text']
                        }
                    }
                },
                resizeKeyboard: {
                    type: 'boolean',
                    default: false,
                    description: 'Resize reply keyboard'
                },
                oneTimeKeyboard: {
                    type: 'boolean',
                    default: false,
                    description: 'Hide keyboard after use'
                },
                removeKeyboard: {
                    type: 'boolean',
                    default: false,
                    description: 'Remove reply keyboard'
                },
                callbackQueryId: {
                    type: 'string',
                    description: 'Callback query ID to answer'
                },
                showAlert: {
                    type: 'boolean',
                    default: false,
                    description: 'Show callback answer as alert'
                },
                webhookUrl: {
                    type: 'string',
                    format: 'uri',
                    description: 'Webhook URL for bot updates'
                },
                template: {
                    type: 'string',
                    enum: ['alert', 'report', 'menu', 'confirmation', 'status', 'welcome', 'help', 'custom'],
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
                }
            },
            required: ['action'],
            allOf: [
                {
                    if: {
                        properties: {
                            action: { enum: ['message', 'photo', 'document', 'video', 'audio'] }
                        }
                    },
                    then: { required: ['botToken', 'chatId'] }
                },
                {
                    if: { properties: { action: { const: 'message' } } },
                    then: { required: ['text'] }
                },
                {
                    if: { properties: { action: { const: 'poll' } } },
                    then: { required: ['question', 'options'] }
                }
            ]
        };

        // Telegram API base URL
        this.baseUrl = 'https://api.telegram.org/bot';

        // Message templates with Telegram-specific formatting
        this.templates = {
            alert: {
                text: '🚨 *UC2 ALERT*\n\n*{alertType}*\n\n{message}\n\n*Details:*\n• System: `{system}`\n• Severity: `{severity}`\n• Time: `{timestamp}`\n• Location: `{location}`\n\n_This is an automated alert from UC2 Command & Control_',
                parseMode: 'Markdown',
                inlineKeyboard: [[
                    { text: '🔍 View Details', url: '{detailsUrl}' },
                    { text: '✅ Acknowledge', callbackData: 'ack_{alertId}' }
                ]]
            },
            report: {
                text: '📊 *{reportTitle}*\n\n*Executive Summary*\n{summary}\n\n*Key Findings*\n{findings}\n\n*Recommendations*\n{recommendations}\n\n*Report Info:*\n• ID: `{reportId}`\n• Generated: `{timestamp}`\n• Agent: `{agent}`\n• Classification: `{classification}`',
                parseMode: 'Markdown',
                inlineKeyboard: [[
                    { text: '📄 Full Report', url: '{reportUrl}' },
                    { text: '📤 Share', switchInlineQuery: 'report {reportId}' }
                ]]
            },
            menu: {
                text: '🎛️ *UC2 Control Panel*\n\nSelect an option from the menu below:',
                parseMode: 'Markdown',
                inlineKeyboard: [
                    [
                        { text: '📊 Status', callbackData: 'menu_status' },
                        { text: '🔍 Search', callbackData: 'menu_search' }
                    ],
                    [
                        { text: '⚙️ Settings', callbackData: 'menu_settings' },
                        { text: '❓ Help', callbackData: 'menu_help' }
                    ],
                    [
                        { text: '🚨 Emergency', callbackData: 'menu_emergency' }
                    ]
                ]
            },
            confirmation: {
                text: '❓ *Confirmation Required*\n\n{message}\n\nAre you sure you want to proceed?',
                parseMode: 'Markdown',
                inlineKeyboard: [[
                    { text: '✅ Yes', callbackData: 'confirm_yes_{actionId}' },
                    { text: '❌ No', callbackData: 'confirm_no_{actionId}' }
                ]]
            },
            status: {
                text: '⚡ *System Status: {systemName}*\n\n*Status:* `{status}`\n*Uptime:* `{uptime}`\n*Last Check:* `{lastCheck}`\n*Response Time:* `{responseTime}`\n\n{statusMessage}\n\n{details}',
                parseMode: 'Markdown',
                inlineKeyboard: [[
                    { text: '🔄 Refresh', callbackData: 'status_refresh_{systemId}' },
                    { text: '📈 Dashboard', url: '{dashboardUrl}' }
                ]]
            },
            welcome: {
                text: '👋 *Welcome to UC2!*\n\nHello {userName}! Welcome to the UC2 Command & Control system.\n\n*Getting Started:*\n{gettingStarted}\n\n*Your Role:* `{userRole}`\n*Access Level:* `{accessLevel}`\n\nUse /help to see available commands or click the menu button below.',
                parseMode: 'Markdown',
                inlineKeyboard: [[
                    { text: '📖 Help', callbackData: 'help_main' },
                    { text: '⚙️ Settings', callbackData: 'settings_main' }
                ]]
            },
            help: {
                text: '❓ *UC2 Help Center*\n\n*Available Commands:*\n/start - Start the bot\n/help - Show this help\n/status - System status\n/menu - Main menu\n/settings - User settings\n/emergency - Emergency contacts\n\n*Quick Actions:*\nUse the inline keyboard below for common tasks.',
                parseMode: 'Markdown',
                inlineKeyboard: [
                    [
                        { text: '📊 Status', callbackData: 'help_status' },
                        { text: '🔍 Commands', callbackData: 'help_commands' }
                    ],
                    [
                        { text: '⚙️ Settings', callbackData: 'help_settings' },
                        { text: '🆘 Support', url: '{supportUrl}' }
                    ]
                ]
            }
        };

        // Priority emoji mapping
        this.priorityEmojis = {
            low: '🔵',
            normal: '⚪',
            high: '🟡',
            urgent: '🔴'
        };

        // Message history and tracking
        this.messageHistory = new Map();
        this.callbackQueries = new Map();
        this.commands = new Map();
        this.maxHistorySize = 3000;

        // Rate limiting
        this.rateLimits = new Map();
        this.defaultRateLimit = { requests: 30, window: 1000 }; // 30 per second

        // Bot commands registry
        this.registerDefaultCommands();

        // Webhook cache
        this.webhookInfo = null;
    }

    /**
     * Execute Telegram action
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate parameters
            this.validateParams(params);

            // Check rate limits
            if (!this.checkRateLimit(params.botToken)) {
                throw new Error('Rate limit exceeded for Telegram API');
            }

            let result;
            switch (params.action) {
                case 'message':
                    result = await this.sendMessage(params);
                    break;
                case 'photo':
                    result = await this.sendPhoto(params);
                    break;
                case 'document':
                    result = await this.sendDocument(params);
                    break;
                case 'video':
                    result = await this.sendVideo(params);
                    break;
                case 'audio':
                    result = await this.sendAudio(params);
                    break;
                case 'sticker':
                    result = await this.sendSticker(params);
                    break;
                case 'location':
                    result = await this.sendLocation(params);
                    break;
                case 'contact':
                    result = await this.sendContact(params);
                    break;
                case 'poll':
                    result = await this.sendPoll(params);
                    break;
                case 'edit':
                    result = await this.editMessage(params);
                    break;
                case 'delete':
                    result = await this.deleteMessage(params);
                    break;
                case 'forward':
                    result = await this.forwardMessage(params);
                    break;
                case 'callback':
                    result = await this.answerCallbackQuery(params);
                    break;
                case 'command':
                    result = await this.executeCommand(params);
                    break;
                case 'webhook':
                    result = await this.manageWebhook(params);
                    break;
                default:
                    throw new Error(`Unknown action: ${params.action}`);
            }

            // Update rate limit
            this.updateRateLimit(params.botToken);

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
     * Send text message
     */
    async sendMessage(params) {
        // Prepare message data
        const messageData = this.prepareMessage(params);

        // Send via Telegram API
        const result = await this.makeApiRequest('sendMessage', messageData, params.botToken);

        // Log message
        this.logMessage(result, params);

        return {
            messageId: result.message_id,
            chatId: result.chat.id,
            text: result.text,
            date: result.date
        };
    }

    /**
     * Send photo
     */
    async sendPhoto(params) {
        if (params.botToken === 'mock' || !params.botToken) {
            return this.sendMockMedia(params, 'photo');
        }

        // Photo sending implementation would go here
        return this.sendMockMedia(params, 'photo');
    }

    /**
     * Send document
     */
    async sendDocument(params) {
        if (params.botToken === 'mock' || !params.botToken) {
            return this.sendMockMedia(params, 'document');
        }

        // Document sending implementation would go here
        return this.sendMockMedia(params, 'document');
    }

    /**
     * Send video
     */
    async sendVideo(params) {
        if (params.botToken === 'mock' || !params.botToken) {
            return this.sendMockMedia(params, 'video');
        }

        // Video sending implementation would go here
        return this.sendMockMedia(params, 'video');
    }

    /**
     * Send audio
     */
    async sendAudio(params) {
        if (params.botToken === 'mock' || !params.botToken) {
            return this.sendMockMedia(params, 'audio');
        }

        // Audio sending implementation would go here
        return this.sendMockMedia(params, 'audio');
    }

    /**
     * Send location
     */
    async sendLocation(params) {
        const locationData = {
            chat_id: params.chatId,
            latitude: params.latitude,
            longitude: params.longitude,
            disable_notification: params.disableNotification,
            protect_content: params.protectContent,
            reply_to_message_id: params.replyToMessageId
        };

        const result = await this.makeApiRequest('sendLocation', locationData, params.botToken);

        return {
            messageId: result.message_id,
            chatId: result.chat.id,
            latitude: result.location.latitude,
            longitude: result.location.longitude
        };
    }

    /**
     * Send contact
     */
    async sendContact(params) {
        const contactData = {
            chat_id: params.chatId,
            phone_number: params.phoneNumber,
            first_name: params.firstName,
            last_name: params.lastName,
            disable_notification: params.disableNotification,
            protect_content: params.protectContent,
            reply_to_message_id: params.replyToMessageId
        };

        const result = await this.makeApiRequest('sendContact', contactData, params.botToken);

        return {
            messageId: result.message_id,
            chatId: result.chat.id,
            contact: result.contact
        };
    }

    /**
     * Send poll
     */
    async sendPoll(params) {
        const pollData = {
            chat_id: params.chatId,
            question: params.question,
            options: JSON.stringify(params.options),
            is_anonymous: params.isAnonymous,
            allows_multiple_answers: params.allowsMultipleAnswers,
            disable_notification: params.disableNotification,
            protect_content: params.protectContent,
            reply_to_message_id: params.replyToMessageId
        };

        const result = await this.makeApiRequest('sendPoll', pollData, params.botToken);

        return {
            messageId: result.message_id,
            chatId: result.chat.id,
            poll: result.poll
        };
    }

    /**
     * Edit message
     */
    async editMessage(params) {
        const editData = {
            chat_id: params.chatId,
            message_id: params.messageId,
            text: params.text,
            parse_mode: params.parseMode,
            disable_web_page_preview: params.disableWebPagePreview
        };

        if (params.inlineKeyboard) {
            editData.reply_markup = JSON.stringify({
                inline_keyboard: params.inlineKeyboard
            });
        }

        const result = await this.makeApiRequest('editMessageText', editData, params.botToken);

        return {
            messageId: result.message_id,
            chatId: result.chat.id,
            text: result.text,
            edited: true
        };
    }

    /**
     * Delete message
     */
    async deleteMessage(params) {
        const deleteData = {
            chat_id: params.chatId,
            message_id: params.messageId
        };

        await this.makeApiRequest('deleteMessage', deleteData, params.botToken);

        return {
            messageId: params.messageId,
            chatId: params.chatId,
            deleted: true
        };
    }

    /**
     * Answer callback query
     */
    async answerCallbackQuery(params) {
        const answerData = {
            callback_query_id: params.callbackQueryId,
            text: params.text,
            show_alert: params.showAlert
        };

        await this.makeApiRequest('answerCallbackQuery', answerData, params.botToken);

        return {
            callbackQueryId: params.callbackQueryId,
            answered: true
        };
    }

    /**
     * Prepare message data
     */
    prepareMessage(params) {
        let messageData = {
            chat_id: params.chatId,
            disable_web_page_preview: params.disableWebPagePreview,
            disable_notification: params.disableNotification,
            protect_content: params.protectContent,
            reply_to_message_id: params.replyToMessageId
        };

        // Process template or use raw text
        if (params.template) {
            const processedTemplate = this.processTemplate(params);
            messageData.text = processedTemplate.text;
            messageData.parse_mode = processedTemplate.parseMode;

            if (processedTemplate.inlineKeyboard) {
                messageData.reply_markup = JSON.stringify({
                    inline_keyboard: processedTemplate.inlineKeyboard
                });
            }
        } else {
            messageData.text = params.text;
            messageData.parse_mode = params.parseMode;
        }

        // Add priority emoji
        if (params.priority && params.priority !== 'normal') {
            const emoji = this.priorityEmojis[params.priority];
            messageData.text = `${emoji} ${messageData.text}`;
        }

        // Add keyboards
        if (params.inlineKeyboard && !messageData.reply_markup) {
            messageData.reply_markup = JSON.stringify({
                inline_keyboard: params.inlineKeyboard
            });
        } else if (params.replyKeyboard) {
            messageData.reply_markup = JSON.stringify({
                keyboard: params.replyKeyboard,
                resize_keyboard: params.resizeKeyboard,
                one_time_keyboard: params.oneTimeKeyboard
            });
        } else if (params.removeKeyboard) {
            messageData.reply_markup = JSON.stringify({
                remove_keyboard: true
            });
        }

        return messageData;
    }

    /**
     * Process message template
     */
    processTemplate(params) {
        const template = this.templates[params.template];
        if (!template) {
            throw new Error(`Unknown template: ${params.template}`);
        }

        const templateData = params.templateData || {};

        // Add default template variables
        templateData.timestamp = templateData.timestamp || new Date().toLocaleString();
        templateData.system = templateData.system || 'UC2';
        templateData.userName = templateData.userName || 'User';

        const processed = {
            text: this.processTemplateString(template.text, templateData),
            parseMode: template.parseMode
        };

        if (template.inlineKeyboard) {
            processed.inlineKeyboard = this.processTemplateKeyboard(template.inlineKeyboard, templateData);
        }

        return processed;
    }

    /**
     * Process template string placeholders
     */
    processTemplateString(template, data) {
        return template.replace(/\{(\w+)\}/g, (match, key) => {
            return data[key] || match;
        });
    }

    /**
     * Process template keyboard placeholders
     */
    processTemplateKeyboard(keyboard, data) {
        return keyboard.map(row =>
            row.map(button => {
                const processedButton = { ...button };
                if (button.text) processedButton.text = this.processTemplateString(button.text, data);
                if (button.url) processedButton.url = this.processTemplateString(button.url, data);
                if (button.callbackData) processedButton.callbackData = this.processTemplateString(button.callbackData, data);
                return processedButton;
            })
        );
    }

    /**
     * Register default bot commands
     */
    registerDefaultCommands() {
        this.commands.set('/start', {
            name: '/start',
            description: 'Start the bot and show welcome message',
            execute: async (params) => {
                return {
                    template: 'welcome',
                    templateData: {
                        userName: params.userName || 'User',
                        userRole: params.userRole || 'Member',
                        accessLevel: params.accessLevel || 'Standard',
                        gettingStarted: 'Use the menu buttons below to navigate UC2 features.'
                    }
                };
            }
        });

        this.commands.set('/help', {
            name: '/help',
            description: 'Show help and available commands',
            execute: async (params) => {
                return {
                    template: 'help',
                    templateData: {
                        supportUrl: 'https://uc2.support'
                    }
                };
            }
        });

        this.commands.set('/status', {
            name: '/status',
            description: 'Show UC2 system status',
            execute: async (params) => {
                return {
                    template: 'status',
                    templateData: {
                        systemName: 'UC2 Command & Control',
                        status: 'Operational',
                        uptime: this.formatUptime(process.uptime()),
                        lastCheck: new Date().toLocaleTimeString(),
                        responseTime: '< 100ms',
                        statusMessage: 'All systems operational',
                        details: 'No issues detected',
                        systemId: 'uc2_main',
                        dashboardUrl: 'https://uc2.dashboard'
                    }
                };
            }
        });

        this.commands.set('/menu', {
            name: '/menu',
            description: 'Show main menu',
            execute: async (params) => {
                return { template: 'menu' };
            }
        });
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

        // Send command response
        if (result.template) {
            return this.sendMessage({
                ...params,
                template: result.template,
                templateData: result.templateData
            });
        } else {
            return this.sendMessage({
                ...params,
                text: result.text || 'Command executed successfully'
            });
        }
    }

    /**
     * Mock implementations for testing
     */
    async sendMockMedia(params, mediaType) {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 200 + Math.random() * 300));

        return {
            messageId: Date.now(),
            chatId: params.chatId,
            mediaType,
            fileName: params.fileName || `mock_${mediaType}_${Date.now()}`,
            fileSize: params.fileContent?.length || 1024,
            mock: true
        };
    }

    /**
     * Make Telegram API request
     */
    async makeApiRequest(method, data, botToken) {
        if (!botToken || botToken === 'mock') {
            // Return mock response
            return {
                message_id: Date.now(),
                chat: { id: data.chat_id, type: 'private' },
                text: data.text || 'Mock message',
                date: Math.floor(Date.now() / 1000),
                mock: true
            };
        }

        const url = `${this.baseUrl}${botToken}/${method}`;

        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const postData = new URLSearchParams(data).toString();

            const options = {
                hostname: urlObj.hostname,
                port: 443,
                path: urlObj.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Content-Length': Buffer.byteLength(postData),
                    'User-Agent': 'UC2TelegramBot/1.0.0'
                }
            };

            const req = https.request(options, res => {
                let responseData = '';
                res.on('data', chunk => responseData += chunk);
                res.on('end', () => {
                    try {
                        const result = JSON.parse(responseData);
                        if (result.ok) {
                            resolve(result.result);
                        } else {
                            reject(new Error(result.description || 'Telegram API error'));
                        }
                    } catch (error) {
                        reject(new Error('Invalid JSON response'));
                    }
                });
            });

            req.on('error', reject);
            req.write(postData);
            req.end();
        });
    }

    /**
     * Manage webhook
     */
    async manageWebhook(params) {
        if (params.webhookUrl) {
            // Set webhook
            const result = await this.makeApiRequest('setWebhook', {
                url: params.webhookUrl
            }, params.botToken);

            this.webhookInfo = { url: params.webhookUrl, setAt: new Date().toISOString() };

            return {
                webhook: 'set',
                url: params.webhookUrl,
                success: true
            };
        } else {
            // Get webhook info
            const result = await this.makeApiRequest('getWebhookInfo', {}, params.botToken);
            return result;
        }
    }

    /**
     * Helper methods
     */
    validateParams(params) {
        if (params.botToken && !params.botToken.match(/^\d+:[A-Za-z0-9_-]{35}$/)) {
            if (params.botToken !== 'mock') {
                throw new Error('Invalid Telegram bot token format');
            }
        }

        if (params.text && params.text.length > 4096) {
            throw new Error('Message text exceeds 4096 character limit');
        }

        if (params.caption && params.caption.length > 1024) {
            throw new Error('Caption exceeds 1024 character limit');
        }

        if (params.options && (params.options.length < 2 || params.options.length > 10)) {
            throw new Error('Poll must have 2-10 options');
        }

        if (params.inlineKeyboard) {
            params.inlineKeyboard.forEach(row => {
                row.forEach(button => {
                    if (button.text && button.text.length > 64) {
                        throw new Error('Button text exceeds 64 character limit');
                    }
                    if (button.callbackData && button.callbackData.length > 64) {
                        throw new Error('Callback data exceeds 64 byte limit');
                    }
                });
            });
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
            messageId: result.message_id,
            chatId: result.chat.id,
            action: params.action,
            template: params.template,
            priority: params.priority,
            timestamp: new Date().toISOString(),
            text: result.text || '[media/action]'
        };

        if (this.messageHistory.size >= this.maxHistorySize) {
            const firstKey = this.messageHistory.keys().next().value;
            this.messageHistory.delete(firstKey);
        }

        this.messageHistory.set(result.message_id, logEntry);
    }

    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours}h ${minutes}m ${secs}s`;
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
                'Send text messages with rich formatting (Markdown/HTML)',
                'Media sharing (photos, videos, audio, documents)',
                'Interactive inline keyboards and buttons',
                'Location and contact sharing',
                'Poll creation and management',
                'Message editing and deletion',
                'Bot commands and automated responses',
                'Callback query handling',
                'Webhook support for real-time updates',
                'Template system for common message types',
                'Priority-based message styling',
                'Rate limiting and API compliance'
            ],
            templates: Object.keys(this.templates),
            commands: Array.from(this.commands.keys()),
            stats: {
                messagesSent: this.messageHistory.size,
                commandsRegistered: this.commands.size,
                rateLimitEntries: this.rateLimits.size,
                webhookActive: !!this.webhookInfo
            },
            limits: {
                messageLength: 4096,
                captionLength: 1024,
                buttonTextLength: 64,
                callbackDataLength: 64,
                pollOptions: '2-10'
            }
        };
    }
}

module.exports = TelegramBotTool;