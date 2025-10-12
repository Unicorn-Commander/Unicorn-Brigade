/**
 * Slack Notifier Tool - Slack team communication
 * UC2 Internal Tool v1.0.0
 * Send messages, files, and manage Slack communications
 */

const https = require('https');
const fs = require('fs').promises;
const path = require('path');

class SlackNotifierTool {
    constructor() {
        this.name = 'slackNotifier';
        this.version = '1.0.0';
        this.description = 'Send messages, files, and manage Slack team communications';
        this.category = 'communication';
        this.permissions = ['network', 'external_api', 'messaging'];
        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['message', 'file', 'thread', 'reaction', 'status', 'channel', 'webhook'],
                    description: 'Action to perform in Slack'
                },
                token: {
                    type: 'string',
                    description: 'Slack bot token (xoxb-000000000000-000000000000-000000000000-000000000000)'
                },
                webhookUrl: {
                    type: 'string',
                    description: 'Slack webhook URL (alternative to token)'
                },
                channel: {
                    type: 'string',
                    description: 'Channel ID, channel name (#general), or user ID for DM'
                },
                text: {
                    type: 'string',
                    description: 'Message text content'
                },
                blocks: {
                    type: 'array',
                    description: 'Slack Block Kit blocks for rich formatting'
                },
                attachments: {
                    type: 'array',
                    description: 'Legacy message attachments'
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
                    description: 'Name for uploaded file'
                },
                fileType: {
                    type: 'string',
                    description: 'MIME type of file'
                },
                threadTs: {
                    type: 'string',
                    description: 'Timestamp of parent message for threading'
                },
                emoji: {
                    type: 'string',
                    description: 'Emoji for reaction (without colons)'
                },
                messageTs: {
                    type: 'string',
                    description: 'Timestamp of message to react to'
                },
                username: {
                    type: 'string',
                    description: 'Custom username for webhook messages'
                },
                iconEmoji: {
                    type: 'string',
                    description: 'Custom emoji icon for webhook messages'
                },
                iconUrl: {
                    type: 'string',
                    description: 'Custom icon URL for webhook messages'
                },
                priority: {
                    type: 'string',
                    enum: ['low', 'normal', 'high', 'urgent'],
                    default: 'normal',
                    description: 'Message priority level'
                },
                mentions: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'User IDs to mention in message'
                },
                channelAction: {
                    type: 'string',
                    enum: ['create', 'archive', 'invite', 'info'],
                    description: 'Channel management action'
                },
                channelName: {
                    type: 'string',
                    description: 'Channel name for channel actions'
                },
                users: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'User IDs for channel invitations'
                }
            },
            required: ['action']
        };

        this.mockMode = !this._checkSlackPackageAvailable();
        this.baseUrl = 'https://slack.com/api';
    }

    /**
     * Execute Slack communication action
     * @param {Object} params - Action parameters
     * @returns {Object} Action result
     */
    async execute(params, context = {}) {
        const startTime = process.hrtime.bigint();

        try {
            const {
                action,
                token,
                webhookUrl,
                channel,
                text,
                blocks,
                attachments,
                filePath,
                fileContent,
                fileName,
                fileType,
                threadTs,
                emoji,
                messageTs,
                username,
                iconEmoji,
                iconUrl,
                priority = 'normal',
                mentions = [],
                channelAction,
                channelName,
                users = []
            } = params;

            // Validate action
            if (!['message', 'file', 'thread', 'reaction', 'status', 'channel', 'webhook'].includes(action)) {
                throw new Error(`Invalid action: ${action}`);
            }

            // Check authentication
            if (!token && !webhookUrl && !this.mockMode) {
                throw new Error('Either Slack token or webhook URL is required');
            }

            let result;

            switch (action) {
                case 'message':
                    result = await this._sendMessage(token, channel, text, blocks, attachments, threadTs, mentions, priority);
                    break;
                case 'file':
                    result = await this._uploadFile(token, channel, filePath, fileContent, fileName, fileType, text);
                    break;
                case 'thread':
                    result = await this._sendThreadReply(token, channel, threadTs, text, blocks);
                    break;
                case 'reaction':
                    result = await this._addReaction(token, channel, messageTs, emoji);
                    break;
                case 'status':
                    result = await this._setStatus(token, text, emoji);
                    break;
                case 'channel':
                    result = await this._manageChannel(token, channelAction, channelName, users);
                    break;
                case 'webhook':
                    result = await this._sendWebhook(webhookUrl, text, blocks, username, iconEmoji, iconUrl);
                    break;
                default:
                    throw new Error(`Unsupported action: ${action}`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to ms

            return {
                success: true,
                action: action,
                result: result,
                timestamp: new Date().toISOString(),
                executionTime: `${executionTime.toFixed(2)}ms`,
                mockMode: this.mockMode
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                action: params.action,
                timestamp: new Date().toISOString(),
                mockMode: this.mockMode
            };
        }
    }

    /**
     * Send message to Slack channel or user
     * @private
     */
    async _sendMessage(token, channel, text, blocks, attachments, threadTs, mentions, priority) {
        if (!channel || (!text && !blocks)) {
            throw new Error('Channel and message content (text or blocks) are required');
        }

        if (this.mockMode) {
            return this._mockSendMessage(channel, text, blocks, threadTs, mentions);
        }

        try {
            // Add mentions to text
            let finalText = text || '';
            if (mentions.length > 0) {
                const mentionText = mentions.map(userId => `<@${userId}>`).join(' ');
                finalText = `${mentionText} ${finalText}`;
            }

            // Add priority indicator
            if (priority === 'urgent') {
                finalText = `🚨 URGENT: ${finalText}`;
            } else if (priority === 'high') {
                finalText = `⚠️ HIGH: ${finalText}`;
            }

            const payload = {
                channel: channel,
                text: finalText
            };

            if (blocks) {
                payload.blocks = blocks;
            }

            if (attachments) {
                payload.attachments = attachments;
            }

            if (threadTs) {
                payload.thread_ts = threadTs;
            }

            const response = await this._makeSlackAPICall('chat.postMessage', payload, token);

            return {
                messageId: response.ts,
                channel: response.channel,
                text: finalText,
                timestamp: response.ts,
                url: `https://app.slack.com/client/${response.team}/${response.channel}/thread/${response.channel}-${response.ts}`,
                sent: true
            };

        } catch (error) {
            throw new Error(`Failed to send message: ${error.message}`);
        }
    }

    /**
     * Upload file to Slack
     * @private
     */
    async _uploadFile(token, channel, filePath, fileContent, fileName, fileType, initialComment) {
        if (!channel) {
            throw new Error('Channel is required for file upload');
        }

        if (!filePath && !fileContent) {
            throw new Error('Either file path or file content is required');
        }

        if (this.mockMode) {
            return this._mockUploadFile(channel, fileName, filePath);
        }

        try {
            let fileData;
            let finalFileName;
            let finalFileType;

            if (filePath) {
                await fs.access(filePath);
                fileData = await fs.readFile(filePath);
                finalFileName = fileName || path.basename(filePath);
                finalFileType = fileType || this._getMimeType(filePath);
            } else {
                fileData = Buffer.from(fileContent, 'base64');
                finalFileName = fileName || 'file';
                finalFileType = fileType || 'application/octet-stream';
            }

            const payload = {
                channels: channel,
                filename: finalFileName,
                filetype: finalFileType,
                file: fileData,
                initial_comment: initialComment || ''
            };

            const response = await this._makeSlackAPICall('files.upload', payload, token);

            return {
                fileId: response.file.id,
                fileName: response.file.name,
                fileUrl: response.file.url_private,
                channel: channel,
                size: response.file.size,
                uploaded: true,
                timestamp: response.file.timestamp
            };

        } catch (error) {
            throw new Error(`Failed to upload file: ${error.message}`);
        }
    }

    /**
     * Send reply in thread
     * @private
     */
    async _sendThreadReply(token, channel, threadTs, text, blocks) {
        if (!threadTs) {
            throw new Error('Thread timestamp is required for thread reply');
        }

        return await this._sendMessage(token, channel, text, blocks, null, threadTs, [], 'normal');
    }

    /**
     * Add reaction to message
     * @private
     */
    async _addReaction(token, channel, messageTs, emoji) {
        if (!channel || !messageTs || !emoji) {
            throw new Error('Channel, message timestamp, and emoji are required');
        }

        if (this.mockMode) {
            return this._mockAddReaction(channel, messageTs, emoji);
        }

        try {
            const payload = {
                channel: channel,
                timestamp: messageTs,
                name: emoji.replace(/:/g, '') // Remove colons if present
            };

            const response = await this._makeSlackAPICall('reactions.add', payload, token);

            return {
                channel: channel,
                messageTs: messageTs,
                emoji: emoji,
                added: true
            };

        } catch (error) {
            throw new Error(`Failed to add reaction: ${error.message}`);
        }
    }

    /**
     * Set user status
     * @private
     */
    async _setStatus(token, statusText, statusEmoji) {
        if (this.mockMode) {
            return this._mockSetStatus(statusText, statusEmoji);
        }

        try {
            const profile = {
                status_text: statusText || '',
                status_emoji: statusEmoji || ''
            };

            const payload = { profile: JSON.stringify(profile) };
            const response = await this._makeSlackAPICall('users.profile.set', payload, token);

            return {
                statusText: statusText,
                statusEmoji: statusEmoji,
                updated: true
            };

        } catch (error) {
            throw new Error(`Failed to set status: ${error.message}`);
        }
    }

    /**
     * Manage Slack channels
     * @private
     */
    async _manageChannel(token, channelAction, channelName, users) {
        if (!channelAction) {
            throw new Error('Channel action is required');
        }

        if (this.mockMode) {
            return this._mockManageChannel(channelAction, channelName, users);
        }

        try {
            let result;

            switch (channelAction) {
                case 'create':
                    if (!channelName) {
                        throw new Error('Channel name is required to create channel');
                    }
                    result = await this._createChannel(token, channelName);
                    break;
                case 'archive':
                    if (!channelName) {
                        throw new Error('Channel name is required to archive channel');
                    }
                    result = await this._archiveChannel(token, channelName);
                    break;
                case 'invite':
                    if (!channelName || !users.length) {
                        throw new Error('Channel name and users are required for invitation');
                    }
                    result = await this._inviteToChannel(token, channelName, users);
                    break;
                case 'info':
                    if (!channelName) {
                        throw new Error('Channel name is required to get channel info');
                    }
                    result = await this._getChannelInfo(token, channelName);
                    break;
                default:
                    throw new Error(`Unsupported channel action: ${channelAction}`);
            }

            return result;

        } catch (error) {
            throw new Error(`Channel management failed: ${error.message}`);
        }
    }

    /**
     * Send webhook message
     * @private
     */
    async _sendWebhook(webhookUrl, text, blocks, username, iconEmoji, iconUrl) {
        if (!webhookUrl) {
            throw new Error('Webhook URL is required');
        }

        if (!text && !blocks) {
            throw new Error('Message content (text or blocks) is required');
        }

        if (this.mockMode) {
            return this._mockSendWebhook(webhookUrl, text, blocks, username);
        }

        try {
            const payload = {};

            if (text) payload.text = text;
            if (blocks) payload.blocks = blocks;
            if (username) payload.username = username;
            if (iconEmoji) payload.icon_emoji = iconEmoji;
            if (iconUrl) payload.icon_url = iconUrl;

            const response = await this._makeWebhookCall(webhookUrl, payload);

            return {
                webhookUrl: webhookUrl,
                text: text,
                username: username,
                sent: true,
                response: response
            };

        } catch (error) {
            throw new Error(`Webhook failed: ${error.message}`);
        }
    }

    /**
     * Helper methods for channel management
     */
    async _createChannel(token, channelName) {
        const payload = { name: channelName };
        const response = await this._makeSlackAPICall('conversations.create', payload, token);

        return {
            channelId: response.channel.id,
            channelName: response.channel.name,
            created: true
        };
    }

    async _archiveChannel(token, channelName) {
        // First get channel ID
        const channelInfo = await this._getChannelInfo(token, channelName);
        const payload = { channel: channelInfo.channelId };

        const response = await this._makeSlackAPICall('conversations.archive', payload, token);

        return {
            channelId: channelInfo.channelId,
            channelName: channelName,
            archived: true
        };
    }

    async _inviteToChannel(token, channelName, users) {
        // First get channel ID
        const channelInfo = await this._getChannelInfo(token, channelName);
        const payload = {
            channel: channelInfo.channelId,
            users: users.join(',')
        };

        const response = await this._makeSlackAPICall('conversations.invite', payload, token);

        return {
            channelId: channelInfo.channelId,
            channelName: channelName,
            invitedUsers: users,
            invited: true
        };
    }

    async _getChannelInfo(token, channelName) {
        const payload = { channel: channelName };
        const response = await this._makeSlackAPICall('conversations.info', payload, token);

        return {
            channelId: response.channel.id,
            channelName: response.channel.name,
            memberCount: response.channel.num_members,
            topic: response.channel.topic.value,
            purpose: response.channel.purpose.value
        };
    }

    /**
     * Make Slack API call
     * @private
     */
    async _makeSlackAPICall(method, payload, token) {
        return new Promise((resolve, reject) => {
            const data = JSON.stringify(payload);

            const options = {
                hostname: 'slack.com',
                path: `/api/${method}`,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                    'Content-Length': Buffer.byteLength(data)
                }
            };

            const req = https.request(options, (res) => {
                let responseBody = '';

                res.on('data', (chunk) => {
                    responseBody += chunk;
                });

                res.on('end', () => {
                    try {
                        const response = JSON.parse(responseBody);

                        if (response.ok) {
                            resolve(response);
                        } else {
                            reject(new Error(response.error || 'Slack API error'));
                        }
                    } catch (error) {
                        reject(new Error(`Invalid JSON response: ${error.message}`));
                    }
                });
            });

            req.on('error', (error) => {
                reject(new Error(`Request failed: ${error.message}`));
            });

            req.write(data);
            req.end();
        });
    }

    /**
     * Make webhook call
     * @private
     */
    async _makeWebhookCall(webhookUrl, payload) {
        return new Promise((resolve, reject) => {
            const data = JSON.stringify(payload);
            const url = new URL(webhookUrl);

            const options = {
                hostname: url.hostname,
                path: url.pathname + url.search,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(data)
                }
            };

            const req = https.request(options, (res) => {
                let responseBody = '';

                res.on('data', (chunk) => {
                    responseBody += chunk;
                });

                res.on('end', () => {
                    if (res.statusCode === 200) {
                        resolve(responseBody || 'ok');
                    } else {
                        reject(new Error(`Webhook failed with status ${res.statusCode}: ${responseBody}`));
                    }
                });
            });

            req.on('error', (error) => {
                reject(new Error(`Webhook request failed: ${error.message}`));
            });

            req.write(data);
            req.end();
        });
    }

    /**
     * Mock implementations for demo mode
     */
    _mockSendMessage(channel, text, blocks, threadTs, mentions) {
        const messageId = `${Date.now()}.000123`;
        const mentionText = mentions.length > 0 ? mentions.map(u => `<@${u}>`).join(' ') + ' ' : '';

        return {
            messageId: messageId,
            channel: channel,
            text: mentionText + (text || 'Block message'),
            timestamp: messageId,
            url: `https://app.slack.com/client/T123ABC/C123ABC/thread/C123ABC-${messageId}`,
            sent: true,
            isThread: !!threadTs,
            note: 'Mock mode - message would be sent in real implementation'
        };
    }

    _mockUploadFile(channel, fileName, filePath) {
        return {
            fileId: `F${Date.now()}`,
            fileName: fileName || path.basename(filePath || 'file.txt'),
            fileUrl: 'https://files.slack.com/files-pri/T123ABC-F123ABC/file.txt',
            channel: channel,
            size: 1024,
            uploaded: true,
            timestamp: Math.floor(Date.now() / 1000),
            note: 'Mock mode - file would be uploaded in real implementation'
        };
    }

    _mockAddReaction(channel, messageTs, emoji) {
        return {
            channel: channel,
            messageTs: messageTs,
            emoji: emoji,
            added: true,
            note: 'Mock mode - reaction would be added in real implementation'
        };
    }

    _mockSetStatus(statusText, statusEmoji) {
        return {
            statusText: statusText || '',
            statusEmoji: statusEmoji || '',
            updated: true,
            note: 'Mock mode - status would be set in real implementation'
        };
    }

    _mockManageChannel(action, channelName, users) {
        const channelId = `C${Date.now()}`;

        switch (action) {
            case 'create':
                return {
                    channelId: channelId,
                    channelName: channelName,
                    created: true,
                    note: 'Mock mode - channel would be created in real implementation'
                };
            case 'archive':
                return {
                    channelId: channelId,
                    channelName: channelName,
                    archived: true,
                    note: 'Mock mode - channel would be archived in real implementation'
                };
            case 'invite':
                return {
                    channelId: channelId,
                    channelName: channelName,
                    invitedUsers: users,
                    invited: true,
                    note: 'Mock mode - users would be invited in real implementation'
                };
            case 'info':
                return {
                    channelId: channelId,
                    channelName: channelName,
                    memberCount: 42,
                    topic: 'Sample channel topic',
                    purpose: 'Sample channel purpose',
                    note: 'Mock mode - real channel info would be retrieved in real implementation'
                };
        }
    }

    _mockSendWebhook(webhookUrl, text, blocks, username) {
        return {
            webhookUrl: webhookUrl,
            text: text || 'Block message',
            username: username || 'UC2 Bot',
            sent: true,
            response: 'ok',
            note: 'Mock mode - webhook would be sent in real implementation'
        };
    }

    /**
     * Helper methods
     */
    _checkSlackPackageAvailable() {
        try {
            // Check if @slack/web-api package is available
            require('@slack/web-api');
            return true;
        } catch (error) {
            console.warn('Slack Web API package not available, using mock mode');
            return false;
        }
    }

    _getMimeType(filePath) {
        const ext = path.extname(filePath).toLowerCase();
        const mimeTypes = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.zip': 'application/zip',
            '.json': 'application/json',
            '.csv': 'text/csv'
        };

        return mimeTypes[ext] || 'application/octet-stream';
    }

    /**
     * Create sample block message
     */
    createSampleBlocks(title, message, priority = 'normal') {
        const priorityEmoji = {
            low: '🔵',
            normal: '🟢',
            high: '🟡',
            urgent: '🔴'
        };

        return [
            {
                type: 'header',
                text: {
                    type: 'plain_text',
                    text: `${priorityEmoji[priority]} ${title}`
                }
            },
            {
                type: 'section',
                text: {
                    type: 'mrkdwn',
                    text: message
                }
            },
            {
                type: 'context',
                elements: [
                    {
                        type: 'mrkdwn',
                        text: `Generated by UC2 • ${new Date().toLocaleString()}`
                    }
                ]
            }
        ];
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
            mockMode: this.mockMode,
            supportedActions: ['message', 'file', 'thread', 'reaction', 'status', 'channel', 'webhook'],
            examples: [
                {
                    description: 'Send simple message',
                    input: {
                        action: 'message',
                        channel: '#general',
                        text: 'Hello from UC2!'
                    },
                    output: { sent: true, messageId: '1234567890.000123' }
                },
                {
                    description: 'Upload file',
                    input: {
                        action: 'file',
                        channel: '#uploads',
                        filePath: '/path/to/document.pdf',
                        text: 'Important document attached'
                    },
                    output: { uploaded: true, fileId: 'F1234567890' }
                },
                {
                    description: 'Send webhook message',
                    input: {
                        action: 'webhook',
                        webhookUrl: 'https://hooks.slack.com/services/...',
                        text: 'Alert from UC2 system',
                        username: 'UC2 Alert Bot'
                    },
                    output: { sent: true, response: 'ok' }
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

        if (!this.schema || typeof this.schema !== 'object') {
            issues.push('Tool schema is required and must be an object');
        }

        if (!this.baseUrl || typeof this.baseUrl !== 'string') {
            issues.push('Base URL is required and must be a string');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SlackNotifierTool;
} else if (typeof exports !== 'undefined') {
    exports.SlackNotifierTool = SlackNotifierTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = SlackNotifierTool;
}