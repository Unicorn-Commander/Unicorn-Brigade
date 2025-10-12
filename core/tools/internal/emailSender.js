/**
 * Email Sender Tool - SMTP Email Communication
 * UC2 Internal Tool v1.0.0
 *
 * Provides secure email sending capabilities with comprehensive
 * SMTP support, templating, and delivery tracking.
 */

const nodemailer = require('nodemailer');
const crypto = require('crypto');

class EmailSenderTool {
    constructor() {
        this.name = 'emailSender';
        this.version = '1.0.0';
        this.description = 'Send emails via SMTP with templates and tracking';
        this.category = 'communication';
        this.permissions = ['network', 'email'];

        this.schema = {
            type: 'object',
            properties: {
                to: {
                    type: ['string', 'array'],
                    description: 'Recipient email address(es)',
                    items: {
                        type: 'string',
                        format: 'email'
                    }
                },
                from: {
                    type: 'string',
                    format: 'email',
                    description: 'Sender email address'
                },
                subject: {
                    type: 'string',
                    maxLength: 255,
                    description: 'Email subject line'
                },
                text: {
                    type: 'string',
                    description: 'Plain text email content'
                },
                html: {
                    type: 'string',
                    description: 'HTML email content'
                },
                cc: {
                    type: ['string', 'array'],
                    description: 'CC recipients',
                    items: {
                        type: 'string',
                        format: 'email'
                    }
                },
                bcc: {
                    type: ['string', 'array'],
                    description: 'BCC recipients',
                    items: {
                        type: 'string',
                        format: 'email'
                    }
                },
                replyTo: {
                    type: 'string',
                    format: 'email',
                    description: 'Reply-to email address'
                },
                attachments: {
                    type: 'array',
                    description: 'Email attachments',
                    items: {
                        type: 'object',
                        properties: {
                            filename: {
                                type: 'string',
                                description: 'Attachment filename'
                            },
                            content: {
                                type: 'string',
                                description: 'Base64 encoded content or file path'
                            },
                            contentType: {
                                type: 'string',
                                description: 'MIME type'
                            },
                            path: {
                                type: 'string',
                                description: 'File path (alternative to content)'
                            }
                        },
                        required: ['filename']
                    }
                },
                template: {
                    type: 'string',
                    description: 'Email template name',
                    enum: ['alert', 'report', 'notification', 'investigation', 'legal', 'custom']
                },
                templateData: {
                    type: 'object',
                    description: 'Data for template substitution'
                },
                priority: {
                    type: 'string',
                    enum: ['low', 'normal', 'high'],
                    default: 'normal',
                    description: 'Email priority level'
                },
                smtpConfig: {
                    type: 'object',
                    description: 'SMTP server configuration',
                    properties: {
                        host: {
                            type: 'string',
                            description: 'SMTP server hostname'
                        },
                        port: {
                            type: 'number',
                            description: 'SMTP server port (25, 465, 587, etc.)'
                        },
                        secure: {
                            type: 'boolean',
                            description: 'Use SSL/TLS connection'
                        },
                        auth: {
                            type: 'object',
                            properties: {
                                user: {
                                    type: 'string',
                                    description: 'SMTP username'
                                },
                                pass: {
                                    type: 'string',
                                    description: 'SMTP password or app password'
                                }
                            },
                            required: ['user', 'pass']
                        },
                        tls: {
                            type: 'object',
                            properties: {
                                rejectUnauthorized: {
                                    type: 'boolean',
                                    default: true
                                }
                            }
                        }
                    },
                    required: ['host', 'port', 'auth']
                },
                tracking: {
                    type: 'boolean',
                    default: false,
                    description: 'Enable delivery tracking'
                },
                headers: {
                    type: 'object',
                    description: 'Custom email headers'
                }
            },
            required: ['to', 'from', 'subject'],
            oneOf: [
                { required: ['text'] },
                { required: ['html'] },
                { required: ['template'] }
            ]
        };

        // Default SMTP configurations for common providers
        this.smtpPresets = {
            gmail: {
                host: 'smtp.gmail.com',
                port: 587,
                secure: false,
                auth: { user: '', pass: '' }, // App passwords required
                tls: { rejectUnauthorized: true }
            },
            outlook: {
                host: 'smtp.live.com',
                port: 587,
                secure: false,
                auth: { user: '', pass: '' },
                tls: { rejectUnauthorized: true }
            },
            yahoo: {
                host: 'smtp.mail.yahoo.com',
                port: 465,
                secure: true,
                auth: { user: '', pass: '' },
                tls: { rejectUnauthorized: true }
            },
            smtp: {
                host: 'localhost',
                port: 25,
                secure: false,
                auth: null
            }
        };

        // Email templates
        this.templates = {
            alert: {
                subject: '🚨 UC2 Alert: {alertType}',
                html: `
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                            <h1 style="color: white; margin: 0;">🚨 System Alert</h1>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa;">
                            <h2 style="color: #dc3545;">{alertType}</h2>
                            <p style="font-size: 16px; line-height: 1.6;">{message}</p>
                            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 4px; margin: 20px 0;">
                                <strong>Time:</strong> {timestamp}<br>
                                <strong>System:</strong> {system}<br>
                                <strong>Severity:</strong> <span style="color: {severityColor};">{severity}</span>
                            </div>
                            {details}
                            <hr style="margin: 20px 0;">
                            <p style="font-size: 12px; color: #6c757d;">
                                This is an automated message from UC2 Command & Control System.
                            </p>
                        </div>
                    </div>
                `,
                text: `UC2 SYSTEM ALERT\n\nType: {alertType}\nMessage: {message}\nTime: {timestamp}\nSystem: {system}\nSeverity: {severity}\n\nDetails:\n{details}\n\n---\nUC2 Command & Control System`
            },
            report: {
                subject: '📊 UC2 Report: {reportTitle}',
                html: `
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 20px; text-align: center;">
                            <h1 style="color: white; margin: 0;">📊 {reportTitle}</h1>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa;">
                            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <h3>Executive Summary</h3>
                                <p style="line-height: 1.6;">{summary}</p>
                            </div>
                            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <h3>Key Findings</h3>
                                {findings}
                            </div>
                            <div style="background: white; padding: 20px; border-radius: 8px;">
                                <h3>Recommendations</h3>
                                {recommendations}
                            </div>
                            <hr style="margin: 20px 0;">
                            <p style="font-size: 12px; color: #6c757d;">
                                Generated by: {agent} | Date: {date} | Report ID: {reportId}
                            </p>
                        </div>
                    </div>
                `,
                text: `UC2 REPORT: {reportTitle}\n\nExecutive Summary:\n{summary}\n\nKey Findings:\n{findings}\n\nRecommendations:\n{recommendations}\n\n---\nGenerated by: {agent} | Date: {date} | Report ID: {reportId}`
            },
            notification: {
                subject: '🔔 UC2 Notification: {title}',
                html: `
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: #28a745; padding: 20px; text-align: center;">
                            <h1 style="color: white; margin: 0;">🔔 {title}</h1>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa;">
                            <p style="font-size: 16px; line-height: 1.6;">{message}</p>
                            {action}
                            <hr style="margin: 20px 0;">
                            <p style="font-size: 12px; color: #6c757d;">
                                UC2 Command & Control System | {timestamp}
                            </p>
                        </div>
                    </div>
                `,
                text: `UC2 NOTIFICATION: {title}\n\n{message}\n\n{action}\n\n---\nUC2 Command & Control System | {timestamp}`
            },
            investigation: {
                subject: '🔍 Investigation Update: {caseName}',
                html: `
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                            <h1 style="color: white; margin: 0;">🔍 Case Update</h1>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa;">
                            <h2>{caseName}</h2>
                            <div style="background: white; padding: 15px; border-radius: 4px; margin: 15px 0;">
                                <strong>Case ID:</strong> {caseId}<br>
                                <strong>Status:</strong> {status}<br>
                                <strong>Lead Investigator:</strong> {investigator}<br>
                                <strong>Updated:</strong> {timestamp}
                            </div>
                            <h3>Latest Developments</h3>
                            <p style="line-height: 1.6;">{developments}</p>
                            <h3>Next Steps</h3>
                            <p style="line-height: 1.6;">{nextSteps}</p>
                            {evidence}
                            <hr style="margin: 20px 0;">
                            <p style="font-size: 12px; color: #6c757d;">
                                CONFIDENTIAL - Investigation Communication
                            </p>
                        </div>
                    </div>
                `,
                text: `INVESTIGATION UPDATE: {caseName}\n\nCase ID: {caseId}\nStatus: {status}\nLead Investigator: {investigator}\nUpdated: {timestamp}\n\nLatest Developments:\n{developments}\n\nNext Steps:\n{nextSteps}\n\nEvidence:\n{evidence}\n\n---\nCONFIDENTIAL - Investigation Communication`
            },
            legal: {
                subject: '⚖️ Legal Notice: {subject}',
                html: `
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: #6c757d; padding: 20px; text-align: center;">
                            <h1 style="color: white; margin: 0;">⚖️ Legal Notice</h1>
                        </div>
                        <div style="padding: 20px; background: #f8f9fa;">
                            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                                <strong>IMPORTANT LEGAL NOTICE</strong><br>
                                This communication may contain attorney-client privileged information.
                            </div>
                            <h2>{subject}</h2>
                            <p style="line-height: 1.6;">{content}</p>
                            {attachments}
                            <div style="background: white; padding: 15px; border-radius: 4px; margin: 20px 0;">
                                <strong>Legal Reference:</strong> {reference}<br>
                                <strong>Date:</strong> {date}<br>
                                <strong>Attorney:</strong> {attorney}
                            </div>
                            <hr style="margin: 20px 0;">
                            <p style="font-size: 11px; color: #6c757d;">
                                ATTORNEY-CLIENT PRIVILEGED AND CONFIDENTIAL<br>
                                This communication is protected by attorney-client privilege.
                            </p>
                        </div>
                    </div>
                `,
                text: `LEGAL NOTICE: {subject}\n\nIMPORTANT: This communication may contain attorney-client privileged information.\n\n{content}\n\nLegal Reference: {reference}\nDate: {date}\nAttorney: {attorney}\n\n---\nATTORNEY-CLIENT PRIVILEGED AND CONFIDENTIAL`
            }
        };

        // Delivery tracking
        this.deliveryLog = new Map();
        this.maxLogSize = 1000;
    }

    /**
     * Execute email sending with comprehensive error handling
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate parameters
            this.validateEmailParams(params);

            // Prepare email content
            const emailContent = await this.prepareEmailContent(params);

            // Configure SMTP transport
            const transporter = await this.createTransporter(params.smtpConfig);

            // Send email
            const result = await this.sendEmail(transporter, emailContent, params);

            // Log delivery
            if (params.tracking) {
                this.logDelivery(result, params);
            }

            return {
                success: true,
                messageId: result.messageId,
                accepted: result.accepted,
                rejected: result.rejected,
                response: result.response,
                executionTime: `${Date.now() - startTime}ms`
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                errorType: error.constructor.name,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    /**
     * Validate email parameters
     */
    validateEmailParams(params) {
        // Required fields
        if (!params.to || !params.from || !params.subject) {
            throw new Error('Missing required fields: to, from, subject');
        }

        // Content validation
        if (!params.text && !params.html && !params.template) {
            throw new Error('Email must have text, html, or template content');
        }

        // Email format validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        const validateEmail = (email) => {
            if (!emailRegex.test(email)) {
                throw new Error(`Invalid email format: ${email}`);
            }
        };

        // Validate recipient emails
        const recipients = Array.isArray(params.to) ? params.to : [params.to];
        recipients.forEach(validateEmail);

        // Validate sender email
        validateEmail(params.from);

        // Validate optional emails
        if (params.cc) {
            const ccList = Array.isArray(params.cc) ? params.cc : [params.cc];
            ccList.forEach(validateEmail);
        }

        if (params.bcc) {
            const bccList = Array.isArray(params.bcc) ? params.bcc : [params.bcc];
            bccList.forEach(validateEmail);
        }

        if (params.replyTo) {
            validateEmail(params.replyTo);
        }

        // Validate SMTP configuration
        if (params.smtpConfig) {
            if (!params.smtpConfig.host || !params.smtpConfig.port) {
                throw new Error('SMTP configuration requires host and port');
            }
        }
    }

    /**
     * Prepare email content with templates
     */
    async prepareEmailContent(params) {
        let emailContent = {
            from: params.from,
            to: params.to,
            subject: params.subject,
            text: params.text,
            html: params.html
        };

        // Add optional fields
        if (params.cc) emailContent.cc = params.cc;
        if (params.bcc) emailContent.bcc = params.bcc;
        if (params.replyTo) emailContent.replyTo = params.replyTo;

        // Process template if specified
        if (params.template) {
            const template = this.templates[params.template];
            if (!template) {
                throw new Error(`Unknown template: ${params.template}`);
            }

            const templateData = params.templateData || {};

            // Add default template variables
            templateData.timestamp = templateData.timestamp || new Date().toISOString();
            templateData.system = templateData.system || 'UC2 Command & Control';
            templateData.date = templateData.date || new Date().toLocaleDateString();

            // Process subject
            emailContent.subject = this.processTemplate(template.subject, templateData);

            // Process content
            if (template.html) {
                emailContent.html = this.processTemplate(template.html, templateData);
            }
            if (template.text) {
                emailContent.text = this.processTemplate(template.text, templateData);
            }
        }

        // Add attachments
        if (params.attachments && params.attachments.length > 0) {
            emailContent.attachments = await this.processAttachments(params.attachments);
        }

        // Add custom headers
        if (params.headers) {
            emailContent.headers = params.headers;
        }

        // Add priority
        if (params.priority && params.priority !== 'normal') {
            const priorityHeaders = {
                'low': { 'X-Priority': '5', 'X-MSMail-Priority': 'Low' },
                'high': { 'X-Priority': '1', 'X-MSMail-Priority': 'High' }
            };
            emailContent.headers = { ...emailContent.headers, ...priorityHeaders[params.priority] };
        }

        // Add tracking headers if enabled
        if (params.tracking) {
            const trackingId = crypto.randomUUID();
            emailContent.headers = {
                ...emailContent.headers,
                'X-UC2-Tracking-ID': trackingId
            };
        }

        return emailContent;
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
     * Process email attachments
     */
    async processAttachments(attachments) {
        const fs = require('fs').promises;
        const processedAttachments = [];

        for (const attachment of attachments) {
            const processed = {
                filename: attachment.filename
            };

            if (attachment.path) {
                // File path attachment
                try {
                    await fs.access(attachment.path);
                    processed.path = attachment.path;
                } catch (error) {
                    throw new Error(`Attachment file not found: ${attachment.path}`);
                }
            } else if (attachment.content) {
                // Base64 content attachment
                processed.content = Buffer.from(attachment.content, 'base64');
            } else {
                throw new Error(`Attachment ${attachment.filename} must have either path or content`);
            }

            if (attachment.contentType) {
                processed.contentType = attachment.contentType;
            }

            processedAttachments.push(processed);
        }

        return processedAttachments;
    }

    /**
     * Create SMTP transporter
     */
    async createTransporter(smtpConfig) {
        // Use provided config or default
        const config = smtpConfig || this.getDefaultSmtpConfig();

        // Validate SMTP configuration
        if (!config.host || !config.port) {
            throw new Error('SMTP configuration incomplete: missing host or port');
        }

        // Create transporter
        const transporter = nodemailer.createTransporter(config);

        // Verify connection
        try {
            await transporter.verify();
        } catch (error) {
            throw new Error(`SMTP connection failed: ${error.message}`);
        }

        return transporter;
    }

    /**
     * Get default SMTP configuration
     */
    getDefaultSmtpConfig() {
        // Try to use environment variables or default to localhost
        return {
            host: process.env.SMTP_HOST || 'localhost',
            port: parseInt(process.env.SMTP_PORT) || 25,
            secure: process.env.SMTP_SECURE === 'true',
            auth: process.env.SMTP_USER ? {
                user: process.env.SMTP_USER,
                pass: process.env.SMTP_PASS
            } : null
        };
    }

    /**
     * Send email with error handling
     */
    async sendEmail(transporter, emailContent, params) {
        try {
            const result = await transporter.sendMail(emailContent);
            return result;
        } catch (error) {
            // Handle specific SMTP errors
            if (error.code === 'EAUTH') {
                throw new Error('SMTP authentication failed - check credentials');
            } else if (error.code === 'EENVELOPE') {
                throw new Error('Invalid recipient or sender address');
            } else if (error.code === 'EMESSAGE') {
                throw new Error('Message content error');
            } else {
                throw new Error(`Email sending failed: ${error.message}`);
            }
        }
    }

    /**
     * Log email delivery for tracking
     */
    logDelivery(result, params) {
        const logEntry = {
            messageId: result.messageId,
            to: params.to,
            from: params.from,
            subject: params.subject,
            timestamp: new Date().toISOString(),
            status: 'sent',
            accepted: result.accepted,
            rejected: result.rejected,
            response: result.response
        };

        // Manage log size
        if (this.deliveryLog.size >= this.maxLogSize) {
            const firstKey = this.deliveryLog.keys().next().value;
            this.deliveryLog.delete(firstKey);
        }

        this.deliveryLog.set(result.messageId, logEntry);
    }

    /**
     * Send email using preset configuration
     */
    async sendWithPreset(presetName, emailParams, credentials) {
        const preset = this.smtpPresets[presetName];
        if (!preset) {
            throw new Error(`Unknown SMTP preset: ${presetName}`);
        }

        // Merge preset with credentials
        const smtpConfig = {
            ...preset,
            auth: credentials
        };

        return this.execute({
            ...emailParams,
            smtpConfig
        });
    }

    /**
     * Get delivery status
     */
    getDeliveryStatus(messageId) {
        return this.deliveryLog.get(messageId) || null;
    }

    /**
     * Get delivery log
     */
    getDeliveryLog(limit = 50) {
        const entries = Array.from(this.deliveryLog.values())
            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
            .slice(0, limit);

        return {
            total: this.deliveryLog.size,
            entries
        };
    }

    /**
     * Get available templates
     */
    getTemplates() {
        return Object.keys(this.templates);
    }

    /**
     * Get SMTP presets
     */
    getSmtpPresets() {
        return Object.keys(this.smtpPresets);
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
                'SMTP email sending with authentication',
                'HTML and text email support',
                'Email templates (alert, report, notification, investigation, legal)',
                'File attachments support',
                'Email priority settings',
                'Delivery tracking and logging',
                'SMTP preset configurations',
                'Custom headers support',
                'CC/BCC recipient support'
            ],
            templates: this.getTemplates(),
            smtpPresets: this.getSmtpPresets(),
            deliveryStats: {
                totalSent: this.deliveryLog.size,
                maxLogSize: this.maxLogSize
            }
        };
    }
}

module.exports = EmailSenderTool;