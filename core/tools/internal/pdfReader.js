/**
 * PDF Reader Tool - Document Processing and Text Extraction
 * UC2 Internal Tool v1.0.0
 *
 * Provides comprehensive PDF processing capabilities including
 * text extraction, metadata analysis, and content structuring.
 */

const fs = require('fs').promises;
const path = require('path');

class PdfReaderTool {
    constructor() {
        this.name = 'pdfReader';
        this.version = '1.0.0';
        this.description = 'Extract text, metadata, and structure from PDF documents';
        this.category = 'document';
        this.permissions = ['filesystem', 'read'];

        this.schema = {
            type: 'object',
            properties: {
                input: {
                    type: 'string',
                    description: 'PDF file path or base64 encoded content'
                },
                inputType: {
                    type: 'string',
                    enum: ['filepath', 'base64', 'url'],
                    default: 'filepath',
                    description: 'Type of input provided'
                },
                extractionMode: {
                    type: 'string',
                    enum: ['text', 'structured', 'metadata', 'full'],
                    default: 'text',
                    description: 'Extraction mode - text only, structured, metadata, or full analysis'
                },
                pageRange: {
                    type: 'object',
                    properties: {
                        start: {
                            type: 'number',
                            minimum: 1,
                            description: 'Starting page number'
                        },
                        end: {
                            type: 'number',
                            minimum: 1,
                            description: 'Ending page number'
                        }
                    },
                    description: 'Range of pages to extract (optional)'
                },
                outputFormat: {
                    type: 'string',
                    enum: ['text', 'json', 'markdown'],
                    default: 'text',
                    description: 'Format for extracted content'
                },
                preserveFormatting: {
                    type: 'boolean',
                    default: false,
                    description: 'Attempt to preserve text formatting and layout'
                },
                extractImages: {
                    type: 'boolean',
                    default: false,
                    description: 'Extract embedded images from PDF'
                },
                extractTables: {
                    type: 'boolean',
                    default: false,
                    description: 'Attempt to extract and structure table data'
                },
                language: {
                    type: 'string',
                    default: 'en',
                    description: 'Document language for better OCR (if needed)'
                },
                password: {
                    type: 'string',
                    description: 'Password for encrypted PDFs'
                },
                maxFileSize: {
                    type: 'number',
                    default: 50 * 1024 * 1024, // 50MB
                    description: 'Maximum file size in bytes'
                },
                timeout: {
                    type: 'number',
                    default: 30000,
                    description: 'Processing timeout in milliseconds'
                }
            },
            required: ['input']
        };

        // PDF processing engines - fallback chain
        this.engines = [
            'pdf2pic', // Convert to images then OCR
            'pdf-parse', // JavaScript PDF parser
            'pdfjs-dist', // Mozilla PDF.js
            'fallback' // Manual parsing
        ];

        // Content analysis patterns
        this.patterns = {
            email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
            phone: /(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}/g,
            ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
            date: /\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b/g,
            currency: /\$[\d,]+\.?\d*/g,
            url: /https?:\/\/[^\s]+/g,
            legal_citation: /\d+\s+[A-Z][a-z]+\.?\s+\d+/g,
            case_number: /\b(?:Case|Docket|No\.?)\s*[:#]?\s*[\w\d-]+/gi
        };

        // Document type detection
        this.documentTypes = {
            contract: ['agreement', 'contract', 'terms', 'conditions', 'whereas'],
            legal: ['plaintiff', 'defendant', 'court', 'motion', 'brief', 'deposition'],
            financial: ['balance', 'income', 'statement', 'audit', 'transaction'],
            investigation: ['incident', 'report', 'evidence', 'witness', 'investigation'],
            medical: ['patient', 'diagnosis', 'treatment', 'medical', 'hospital'],
            technical: ['specification', 'manual', 'documentation', 'procedure']
        };

        this.cache = new Map();
        this.maxCacheSize = 100;
    }

    /**
     * Execute PDF processing with comprehensive error handling
     */
    async execute(params) {
        const startTime = Date.now();

        try {
            // Validate parameters
            this.validateParams(params);

            // Check cache first
            const cacheKey = this.generateCacheKey(params);
            if (this.cache.has(cacheKey)) {
                const cached = this.cache.get(cacheKey);
                return {
                    ...cached,
                    cached: true,
                    executionTime: `${Date.now() - startTime}ms`
                };
            }

            // Load PDF content
            const pdfBuffer = await this.loadPdfContent(params);

            // Process with available engine
            const result = await this.processPdfWithBestEngine(pdfBuffer, params);

            // Add to cache
            this.addToCache(cacheKey, result);

            result.executionTime = `${Date.now() - startTime}ms`;
            return result;

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
     * Validate input parameters
     */
    validateParams(params) {
        if (!params.input) {
            throw new Error('Input is required');
        }

        if (params.inputType === 'filepath') {
            // Will validate file existence during load
        } else if (params.inputType === 'base64') {
            try {
                Buffer.from(params.input, 'base64');
            } catch (error) {
                throw new Error('Invalid base64 content');
            }
        } else if (params.inputType === 'url') {
            try {
                new URL(params.input);
            } catch (error) {
                throw new Error('Invalid URL format');
            }
        }

        if (params.pageRange) {
            if (params.pageRange.start && params.pageRange.end) {
                if (params.pageRange.start > params.pageRange.end) {
                    throw new Error('Start page cannot be greater than end page');
                }
            }
        }
    }

    /**
     * Load PDF content from various sources
     */
    async loadPdfContent(params) {
        switch (params.inputType) {
            case 'filepath':
                return await this.loadFromFile(params.input, params.maxFileSize);

            case 'base64':
                return Buffer.from(params.input, 'base64');

            case 'url':
                return await this.loadFromUrl(params.input, params.maxFileSize);

            default:
                throw new Error(`Unsupported input type: ${params.inputType}`);
        }
    }

    /**
     * Load PDF from file path
     */
    async loadFromFile(filePath, maxFileSize) {
        try {
            // Security check - ensure file is in allowed directory
            const resolvedPath = path.resolve(filePath);
            const allowedDirs = [
                path.resolve('./workspace'),
                path.resolve('./uploads'),
                path.resolve('./documents')
            ];

            const isAllowed = allowedDirs.some(dir => resolvedPath.startsWith(dir));
            if (!isAllowed) {
                throw new Error('File access not allowed in this directory');
            }

            // Check file existence and size
            const stats = await fs.stat(resolvedPath);
            if (stats.size > maxFileSize) {
                throw new Error(`File size ${stats.size} exceeds maximum ${maxFileSize} bytes`);
            }

            // Verify file extension
            if (!resolvedPath.toLowerCase().endsWith('.pdf')) {
                throw new Error('File must have .pdf extension');
            }

            return await fs.readFile(resolvedPath);

        } catch (error) {
            if (error.code === 'ENOENT') {
                throw new Error('PDF file not found');
            } else if (error.code === 'EACCES') {
                throw new Error('Permission denied to read PDF file');
            }
            throw error;
        }
    }

    /**
     * Load PDF from URL
     */
    async loadFromUrl(url, maxFileSize) {
        try {
            const axios = require('axios');

            const response = await axios.get(url, {
                responseType: 'arraybuffer',
                timeout: 30000,
                maxContentLength: maxFileSize,
                headers: {
                    'User-Agent': 'UC2-PdfReader/1.0.0'
                }
            });

            // Verify content type
            const contentType = response.headers['content-type'];
            if (!contentType || !contentType.includes('pdf')) {
                throw new Error('URL does not point to a PDF file');
            }

            return Buffer.from(response.data);

        } catch (error) {
            throw new Error(`Failed to load PDF from URL: ${error.message}`);
        }
    }

    /**
     * Process PDF with the best available engine
     */
    async processPdfWithBestEngine(pdfBuffer, params) {
        let lastError = null;

        // Try PDF parsing engines in order of preference
        for (const engine of this.engines) {
            try {
                const result = await this.processPdfWithEngine(engine, pdfBuffer, params);
                if (result.success) {
                    return result;
                }
            } catch (error) {
                console.log(`PDF engine ${engine} failed: ${error.message}`);
                lastError = error;
            }
        }

        // If all engines failed, return fallback result
        return {
            success: false,
            error: 'All PDF processing engines failed',
            lastError: lastError ? lastError.message : 'Unknown error',
            fallbackText: await this.extractFallbackText(pdfBuffer),
            metadata: await this.extractBasicMetadata(pdfBuffer)
        };
    }

    /**
     * Process PDF with specific engine
     */
    async processPdfWithEngine(engine, pdfBuffer, params) {
        switch (engine) {
            case 'pdf-parse':
                return await this.processPdfWithPdfParse(pdfBuffer, params);

            case 'pdfjs-dist':
                return await this.processPdfWithPdfJs(pdfBuffer, params);

            case 'pdf2pic':
                return await this.processPdfWithPdf2Pic(pdfBuffer, params);

            case 'fallback':
                return await this.processPdfWithFallback(pdfBuffer, params);

            default:
                throw new Error(`Unknown PDF engine: ${engine}`);
        }
    }

    /**
     * Process PDF with pdf-parse library
     */
    async processPdfWithPdfParse(pdfBuffer, params) {
        try {
            // Try to require pdf-parse
            let pdfParse;
            try {
                pdfParse = require('pdf-parse');
            } catch (error) {
                throw new Error('pdf-parse library not available');
            }

            const options = {
                password: params.password
            };

            if (params.pageRange) {
                options.pagerender = (pageData) => {
                    const pageNum = pageData.pageNumber;
                    if (params.pageRange.start && pageNum < params.pageRange.start) return '';
                    if (params.pageRange.end && pageNum > params.pageRange.end) return '';
                    return pageData.getTextContent();
                };
            }

            const data = await pdfParse(pdfBuffer, options);

            // Process based on extraction mode
            const result = await this.processExtractedContent(data, params);

            return {
                success: true,
                engine: 'pdf-parse',
                ...result
            };

        } catch (error) {
            throw new Error(`pdf-parse processing failed: ${error.message}`);
        }
    }

    /**
     * Process PDF with PDF.js
     */
    async processPdfWithPdfJs(pdfBuffer, params) {
        try {
            // Try to require pdfjs-dist
            let pdfjsLib;
            try {
                pdfjsLib = require('pdfjs-dist/legacy/build/pdf.js');
            } catch (error) {
                throw new Error('pdfjs-dist library not available');
            }

            const loadingTask = pdfjsLib.getDocument({
                data: pdfBuffer,
                password: params.password
            });

            const pdf = await loadingTask.promise;

            let fullText = '';
            const pageTexts = [];
            const startPage = params.pageRange?.start || 1;
            const endPage = params.pageRange?.end || pdf.numPages;

            for (let pageNum = startPage; pageNum <= Math.min(endPage, pdf.numPages); pageNum++) {
                const page = await pdf.getPage(pageNum);
                const textContent = await page.getTextContent();

                let pageText = '';
                textContent.items.forEach(item => {
                    pageText += item.str + ' ';
                });

                pageTexts.push({
                    page: pageNum,
                    text: pageText.trim()
                });
                fullText += pageText + '\n';
            }

            const mockData = {
                text: fullText,
                numpages: pdf.numPages,
                info: await this.extractPdfJsMetadata(pdf),
                pages: pageTexts
            };

            const result = await this.processExtractedContent(mockData, params);

            return {
                success: true,
                engine: 'pdfjs-dist',
                ...result
            };

        } catch (error) {
            throw new Error(`pdfjs-dist processing failed: ${error.message}`);
        }
    }

    /**
     * Process PDF with pdf2pic (OCR fallback)
     */
    async processPdfWithPdf2Pic(pdfBuffer, params) {
        throw new Error('pdf2pic processing not yet implemented - requires ImageMagick');
    }

    /**
     * Fallback PDF processing (manual parsing)
     */
    async processPdfWithFallback(pdfBuffer, params) {
        // Basic PDF structure analysis
        const pdfString = pdfBuffer.toString('latin1');

        // Extract basic text using simple regex patterns
        const textMatches = pdfString.match(/BT\s+(.*?)\s+ET/g) || [];
        let extractedText = '';

        for (const match of textMatches) {
            // Very basic text extraction - not perfect but better than nothing
            const textContent = match.replace(/BT|ET/g, '').trim();
            extractedText += textContent + ' ';
        }

        // Clean up extracted text
        extractedText = extractedText
            .replace(/[^\x20-\x7E\s]/g, '') // Remove non-printable characters
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();

        const result = {
            text: extractedText || 'Unable to extract readable text',
            pages: 1,
            metadata: {
                title: 'Unknown',
                author: 'Unknown',
                creator: 'Unknown',
                producer: 'Unknown',
                creationDate: null,
                modificationDate: null
            },
            warning: 'Processed with fallback engine - text extraction may be incomplete'
        };

        return {
            success: true,
            engine: 'fallback',
            ...await this.processExtractedContent(result, params)
        };
    }

    /**
     * Process extracted content based on parameters
     */
    async processExtractedContent(data, params) {
        const result = {
            success: true,
            totalPages: data.numpages || data.pages || 1,
            extractedPages: params.pageRange ?
                (params.pageRange.end - params.pageRange.start + 1) :
                (data.numpages || 1)
        };

        // Basic content extraction
        if (params.extractionMode === 'text' || params.extractionMode === 'full') {
            result.text = data.text;
            result.textLength = data.text.length;
            result.wordCount = data.text.split(/\s+/).length;
        }

        // Metadata extraction
        if (params.extractionMode === 'metadata' || params.extractionMode === 'full') {
            result.metadata = {
                title: data.info?.Title || 'Unknown',
                author: data.info?.Author || 'Unknown',
                subject: data.info?.Subject || '',
                keywords: data.info?.Keywords || '',
                creator: data.info?.Creator || 'Unknown',
                producer: data.info?.Producer || 'Unknown',
                creationDate: data.info?.CreationDate || null,
                modificationDate: data.info?.ModDate || null,
                pdfVersion: data.version || 'Unknown'
            };
        }

        // Structured extraction
        if (params.extractionMode === 'structured' || params.extractionMode === 'full') {
            result.structured = await this.performStructuredExtraction(data.text);
        }

        // Format output
        if (params.outputFormat === 'json') {
            result.formattedOutput = JSON.stringify(result, null, 2);
        } else if (params.outputFormat === 'markdown') {
            result.formattedOutput = this.formatAsMarkdown(result, params);
        } else {
            result.formattedOutput = result.text || '';
        }

        return result;
    }

    /**
     * Perform structured data extraction
     */
    async performStructuredExtraction(text) {
        const structured = {
            documentType: this.detectDocumentType(text),
            extractedData: {},
            patterns: {}
        };

        // Extract patterns
        for (const [patternName, regex] of Object.entries(this.patterns)) {
            const matches = text.match(regex);
            if (matches) {
                structured.patterns[patternName] = [...new Set(matches)]; // Remove duplicates
            }
        }

        // Extract key-value pairs
        structured.extractedData.emails = structured.patterns.email || [];
        structured.extractedData.phones = structured.patterns.phone || [];
        structured.extractedData.dates = structured.patterns.date || [];
        structured.extractedData.amounts = structured.patterns.currency || [];
        structured.extractedData.urls = structured.patterns.url || [];

        // Legal document specific extraction
        if (structured.documentType === 'legal') {
            structured.extractedData.citations = structured.patterns.legal_citation || [];
            structured.extractedData.caseNumbers = structured.patterns.case_number || [];
        }

        return structured;
    }

    /**
     * Detect document type based on content
     */
    detectDocumentType(text) {
        const lowerText = text.toLowerCase();
        let maxScore = 0;
        let detectedType = 'unknown';

        for (const [type, keywords] of Object.entries(this.documentTypes)) {
            let score = 0;
            for (const keyword of keywords) {
                const occurrences = (lowerText.match(new RegExp(keyword, 'g')) || []).length;
                score += occurrences;
            }

            if (score > maxScore) {
                maxScore = score;
                detectedType = type;
            }
        }

        return detectedType;
    }

    /**
     * Format result as markdown
     */
    formatAsMarkdown(result, params) {
        let markdown = `# PDF Document Analysis\n\n`;

        if (result.metadata) {
            markdown += `## Document Information\n\n`;
            markdown += `- **Title**: ${result.metadata.title}\n`;
            markdown += `- **Author**: ${result.metadata.author}\n`;
            markdown += `- **Pages**: ${result.totalPages}\n`;
            markdown += `- **Created**: ${result.metadata.creationDate || 'Unknown'}\n\n`;
        }

        if (result.structured) {
            markdown += `## Document Type\n\n${result.structured.documentType}\n\n`;

            if (result.structured.extractedData.emails.length > 0) {
                markdown += `## Email Addresses\n\n`;
                result.structured.extractedData.emails.forEach(email => {
                    markdown += `- ${email}\n`;
                });
                markdown += `\n`;
            }

            if (result.structured.extractedData.phones.length > 0) {
                markdown += `## Phone Numbers\n\n`;
                result.structured.extractedData.phones.forEach(phone => {
                    markdown += `- ${phone}\n`;
                });
                markdown += `\n`;
            }
        }

        if (result.text) {
            markdown += `## Extracted Text\n\n${result.text}\n`;
        }

        return markdown;
    }

    /**
     * Extract metadata from PDF.js
     */
    async extractPdfJsMetadata(pdf) {
        try {
            const metadata = await pdf.getMetadata();
            return metadata.info;
        } catch (error) {
            return {};
        }
    }

    /**
     * Cache management
     */
    generateCacheKey(params) {
        const crypto = require('crypto');
        const key = JSON.stringify({
            input: params.inputType === 'filepath' ? params.input : 'content',
            extractionMode: params.extractionMode,
            pageRange: params.pageRange
        });
        return crypto.createHash('sha256').update(key).digest('hex').substring(0, 16);
    }

    addToCache(key, result) {
        if (this.cache.size >= this.maxCacheSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        this.cache.set(key, { ...result, timestamp: Date.now() });
    }

    /**
     * Extract basic metadata (fallback)
     */
    async extractBasicMetadata(pdfBuffer) {
        const pdfString = pdfBuffer.toString('latin1');
        return {
            size: pdfBuffer.length,
            hasText: pdfString.includes('BT') && pdfString.includes('ET'),
            hasImages: pdfString.includes('/Image'),
            hasForms: pdfString.includes('/AcroForm'),
            encrypted: pdfString.includes('/Encrypt')
        };
    }

    /**
     * Extract fallback text
     */
    async extractFallbackText(pdfBuffer) {
        return 'Text extraction failed - binary PDF content detected';
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
                'Text extraction from PDF documents',
                'Metadata extraction (title, author, dates, etc.)',
                'Structured data extraction (emails, phones, dates, URLs)',
                'Document type detection',
                'Page range selection',
                'Multiple output formats (text, JSON, markdown)',
                'Encrypted PDF support',
                'Content caching for performance',
                'Security restrictions for file access',
                'Fallback processing engines'
            ],
            supportedEngines: this.engines,
            documentTypes: Object.keys(this.documentTypes),
            patterns: Object.keys(this.patterns),
            cacheStats: {
                size: this.cache.size,
                maxSize: this.maxCacheSize
            }
        };
    }

    /**
     * Clear cache
     */
    clearCache() {
        this.cache.clear();
        return { success: true, message: 'PDF processing cache cleared' };
    }
}

module.exports = PdfReaderTool;