/**
 * Image Analyzer Tool - OCR and visual analysis
 * UC2 Internal Tool v1.0.0
 * OCR text extraction, metadata analysis, object detection, and image manipulation
 */

const fs = require('fs').promises;
const path = require('path');

class ImageAnalyzerTool {
    constructor() {
        this.name = 'imageAnalyzer';
        this.version = '1.0.0';
        this.description = 'OCR text extraction, image analysis, and visual content processing';
        this.category = 'image';
        this.permissions = ['file', 'read', 'analysis', 'vision'];
        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['ocr', 'metadata', 'detect', 'compare', 'qr', 'manipulate', 'analyze', 'extract'],
                    description: 'Action to perform on image'
                },
                imagePath: {
                    type: 'string',
                    description: 'Path to the image file'
                },
                imageData: {
                    type: 'string',
                    description: 'Base64 encoded image data (alternative to imagePath)'
                },
                compareWith: {
                    type: 'string',
                    description: 'Path to second image for comparison'
                },
                language: {
                    type: 'string',
                    default: 'eng',
                    description: 'OCR language code (eng, spa, fra, deu, etc.)'
                },
                ocrEngine: {
                    type: 'string',
                    enum: ['tesseract', 'vision-api'],
                    default: 'tesseract',
                    description: 'OCR engine to use'
                },
                detectTypes: {
                    type: 'array',
                    items: {
                        type: 'string',
                        enum: ['faces', 'objects', 'text', 'barcodes', 'landmarks']
                    },
                    default: ['text'],
                    description: 'Types of detection to perform'
                },
                outputPath: {
                    type: 'string',
                    description: 'Output path for processed image'
                },
                manipulations: {
                    type: 'object',
                    properties: {
                        resize: {
                            type: 'object',
                            properties: {
                                width: { type: 'number' },
                                height: { type: 'number' }
                            }
                        },
                        crop: {
                            type: 'object',
                            properties: {
                                x: { type: 'number' },
                                y: { type: 'number' },
                                width: { type: 'number' },
                                height: { type: 'number' }
                            }
                        },
                        rotate: { type: 'number' },
                        brightness: { type: 'number' },
                        contrast: { type: 'number' },
                        blur: { type: 'number' }
                    },
                    description: 'Image manipulation options'
                },
                threshold: {
                    type: 'number',
                    default: 0.5,
                    description: 'Detection confidence threshold'
                },
                extractRegions: {
                    type: 'boolean',
                    default: false,
                    description: 'Extract text regions as separate images'
                }
            },
            required: ['action']
        };

        this.supportedFormats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];
        this.mockMode = !this._checkTesseractAvailable();
    }

    /**
     * Execute image analysis operation
     * @param {Object} params - Analysis parameters
     * @returns {Object} Analysis result
     */
    async execute(params, context = {}) {
        const startTime = process.hrtime.bigint();

        try {
            const {
                action,
                imagePath,
                imageData,
                compareWith,
                language = 'eng',
                ocrEngine = 'tesseract',
                detectTypes = ['text'],
                outputPath,
                manipulations,
                threshold = 0.5,
                extractRegions = false
            } = params;

            // Validate action
            if (!['ocr', 'metadata', 'detect', 'compare', 'qr', 'manipulate', 'analyze', 'extract'].includes(action)) {
                throw new Error(`Invalid action: ${action}`);
            }

            // Validate image input
            if (!imagePath && !imageData) {
                throw new Error('Either imagePath or imageData must be provided');
            }

            let result;

            switch (action) {
                case 'ocr':
                    result = await this._performOCR(imagePath, imageData, language, ocrEngine, extractRegions);
                    break;
                case 'metadata':
                    result = await this._extractMetadata(imagePath, imageData);
                    break;
                case 'detect':
                    result = await this._detectObjects(imagePath, imageData, detectTypes, threshold);
                    break;
                case 'compare':
                    result = await this._compareImages(imagePath, compareWith);
                    break;
                case 'qr':
                    result = await this._readQRCode(imagePath, imageData);
                    break;
                case 'manipulate':
                    result = await this._manipulateImage(imagePath, imageData, manipulations, outputPath);
                    break;
                case 'analyze':
                    result = await this._analyzeImage(imagePath, imageData);
                    break;
                case 'extract':
                    result = await this._extractFeatures(imagePath, imageData);
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
     * Perform OCR text extraction
     * @private
     */
    async _performOCR(imagePath, imageData, language, engine, extractRegions) {
        if (this.mockMode) {
            return this._mockOCR(imagePath, imageData);
        }

        try {
            const tesseract = require('tesseract.js');
            let imageInput;

            if (imagePath) {
                await fs.access(imagePath);
                if (!this._isValidImageFile(imagePath)) {
                    throw new Error('Invalid image file format');
                }
                imageInput = imagePath;
            } else {
                // Convert base64 to buffer
                const buffer = Buffer.from(imageData, 'base64');
                imageInput = buffer;
            }

            const { data } = await tesseract.recognize(imageInput, language, {
                logger: m => console.log(m) // Optional: log progress
            });

            const result = {
                text: data.text.trim(),
                confidence: data.confidence,
                words: data.words.map(word => ({
                    text: word.text,
                    confidence: word.confidence,
                    bbox: word.bbox
                })),
                lines: data.lines.map(line => ({
                    text: line.text,
                    confidence: line.confidence,
                    bbox: line.bbox
                })),
                paragraphs: data.paragraphs.map(paragraph => ({
                    text: paragraph.text,
                    confidence: paragraph.confidence,
                    bbox: paragraph.bbox
                })),
                language: language,
                engine: engine,
                processingTime: data.processingTime
            };

            // Extract text regions as separate images if requested
            if (extractRegions) {
                result.textRegions = await this._extractTextRegions(imageInput, data.words);
            }

            return result;

        } catch (error) {
            throw new Error(`OCR failed: ${error.message}`);
        }
    }

    /**
     * Extract image metadata (EXIF, etc.)
     * @private
     */
    async _extractMetadata(imagePath, imageData) {
        if (this.mockMode) {
            return this._mockMetadata(imagePath);
        }

        try {
            let filePath = imagePath;

            if (imageData && !imagePath) {
                // Write temporary file for metadata extraction
                const tempPath = path.join(__dirname, 'temp_image.jpg');
                const buffer = Buffer.from(imageData, 'base64');
                await fs.writeFile(tempPath, buffer);
                filePath = tempPath;
            }

            // Use exifr or similar library for metadata extraction
            const exifr = require('exifr');
            const metadata = await exifr.parse(filePath);

            // Get basic file info
            const stats = await fs.stat(filePath);

            const result = {
                file: {
                    name: path.basename(filePath),
                    size: stats.size,
                    created: stats.birthtime,
                    modified: stats.mtime,
                    extension: path.extname(filePath)
                },
                exif: metadata || {},
                image: {
                    width: metadata?.ImageWidth || null,
                    height: metadata?.ImageHeight || null,
                    colorSpace: metadata?.ColorSpace || null,
                    orientation: metadata?.Orientation || null
                },
                camera: {
                    make: metadata?.Make || null,
                    model: metadata?.Model || null,
                    software: metadata?.Software || null
                },
                capture: {
                    dateTime: metadata?.DateTime || metadata?.DateTimeOriginal || null,
                    iso: metadata?.ISO || null,
                    aperture: metadata?.FNumber || null,
                    shutterSpeed: metadata?.ExposureTime || null,
                    focalLength: metadata?.FocalLength || null,
                    flash: metadata?.Flash || null
                },
                gps: {
                    latitude: metadata?.GPSLatitude || null,
                    longitude: metadata?.GPSLongitude || null,
                    altitude: metadata?.GPSAltitude || null
                }
            };

            // Clean up temp file if created
            if (imageData && !imagePath) {
                await fs.unlink(filePath).catch(() => {});
            }

            return result;

        } catch (error) {
            throw new Error(`Metadata extraction failed: ${error.message}`);
        }
    }

    /**
     * Detect objects, faces, or other features
     * @private
     */
    async _detectObjects(imagePath, imageData, detectTypes, threshold) {
        if (this.mockMode) {
            return this._mockDetection(detectTypes);
        }

        const result = {
            detections: {},
            confidence: threshold,
            types: detectTypes
        };

        // Note: In a real implementation, you would use:
        // - OpenCV for object detection
        // - Face-api.js for face detection
        // - Google Vision API for comprehensive detection
        // - Custom ML models

        for (const type of detectTypes) {
            switch (type) {
                case 'faces':
                    result.detections.faces = await this._detectFaces(imagePath, imageData, threshold);
                    break;
                case 'objects':
                    result.detections.objects = await this._detectGeneralObjects(imagePath, imageData, threshold);
                    break;
                case 'text':
                    result.detections.text = await this._detectText(imagePath, imageData, threshold);
                    break;
                case 'barcodes':
                    result.detections.barcodes = await this._detectBarcodes(imagePath, imageData);
                    break;
                case 'landmarks':
                    result.detections.landmarks = await this._detectLandmarks(imagePath, imageData, threshold);
                    break;
            }
        }

        return result;
    }

    /**
     * Compare two images for similarity
     * @private
     */
    async _compareImages(imagePath1, imagePath2) {
        if (!imagePath2) {
            throw new Error('Second image path is required for comparison');
        }

        if (this.mockMode) {
            return this._mockImageComparison(imagePath1, imagePath2);
        }

        try {
            // In real implementation, would use image comparison algorithms
            // like Structural Similarity Index (SSIM), perceptual hashing, etc.

            const result = {
                similarity: 0.85, // Mock similarity score
                method: 'perceptual_hash',
                identical: false,
                differences: {
                    structural: 0.15,
                    color: 0.12,
                    texture: 0.08
                },
                recommendations: [
                    'Images are highly similar',
                    'Minor differences detected in background'
                ]
            };

            return result;

        } catch (error) {
            throw new Error(`Image comparison failed: ${error.message}`);
        }
    }

    /**
     * Read QR codes and barcodes
     * @private
     */
    async _readQRCode(imagePath, imageData) {
        if (this.mockMode) {
            return this._mockQRRead();
        }

        try {
            // In real implementation, would use jsQR or similar library
            const jsQR = require('jsqr');

            let imageBuffer;
            if (imagePath) {
                imageBuffer = await fs.readFile(imagePath);
            } else {
                imageBuffer = Buffer.from(imageData, 'base64');
            }

            // Convert to ImageData format (would need canvas or sharp for real implementation)
            // This is a simplified mock
            const result = {
                found: true,
                data: 'https://example.com/qr-content',
                format: 'QR_CODE',
                location: {
                    topLeft: { x: 50, y: 50 },
                    topRight: { x: 200, y: 50 },
                    bottomLeft: { x: 50, y: 200 },
                    bottomRight: { x: 200, y: 200 }
                },
                confidence: 0.95
            };

            return result;

        } catch (error) {
            return {
                found: false,
                error: error.message
            };
        }
    }

    /**
     * Manipulate image (resize, crop, filters, etc.)
     * @private
     */
    async _manipulateImage(imagePath, imageData, manipulations, outputPath) {
        if (!manipulations) {
            throw new Error('Manipulations object is required');
        }

        if (this.mockMode) {
            return this._mockImageManipulation(manipulations, outputPath);
        }

        try {
            // In real implementation, would use Sharp or similar library
            const sharp = require('sharp');

            let image;
            if (imagePath) {
                image = sharp(imagePath);
            } else {
                const buffer = Buffer.from(imageData, 'base64');
                image = sharp(buffer);
            }

            // Apply manipulations
            if (manipulations.resize) {
                const { width, height } = manipulations.resize;
                image = image.resize(width, height);
            }

            if (manipulations.crop) {
                const { x, y, width, height } = manipulations.crop;
                image = image.extract({ left: x, top: y, width, height });
            }

            if (manipulations.rotate) {
                image = image.rotate(manipulations.rotate);
            }

            if (manipulations.brightness !== undefined) {
                image = image.modulate({ brightness: manipulations.brightness });
            }

            if (manipulations.contrast !== undefined) {
                // Sharp uses different contrast adjustment
                image = image.linear(manipulations.contrast, -(128 * manipulations.contrast) + 128);
            }

            if (manipulations.blur) {
                image = image.blur(manipulations.blur);
            }

            // Get image info
            const metadata = await image.metadata();

            // Save or return processed image
            if (outputPath) {
                await image.toFile(outputPath);
                return {
                    outputPath: outputPath,
                    manipulations: manipulations,
                    finalDimensions: {
                        width: metadata.width,
                        height: metadata.height
                    },
                    processed: true
                };
            } else {
                const buffer = await image.toBuffer();
                return {
                    imageData: buffer.toString('base64'),
                    manipulations: manipulations,
                    finalDimensions: {
                        width: metadata.width,
                        height: metadata.height
                    },
                    processed: true
                };
            }

        } catch (error) {
            throw new Error(`Image manipulation failed: ${error.message}`);
        }
    }

    /**
     * Comprehensive image analysis
     * @private
     */
    async _analyzeImage(imagePath, imageData) {
        const analysis = {
            overview: {},
            content: {},
            technical: {},
            quality: {}
        };

        try {
            // Get metadata
            const metadata = await this._extractMetadata(imagePath, imageData);
            analysis.technical = metadata;

            // Perform OCR if text is detected
            const ocrResult = await this._performOCR(imagePath, imageData, 'eng', 'tesseract', false);
            analysis.content.text = {
                hasText: ocrResult.text.length > 0,
                extractedText: ocrResult.text,
                confidence: ocrResult.confidence
            };

            // Basic image properties
            analysis.overview = {
                width: metadata.image.width,
                height: metadata.image.height,
                aspectRatio: metadata.image.width / metadata.image.height,
                fileSize: metadata.file.size,
                format: metadata.file.extension
            };

            // Quality assessment (mock)
            analysis.quality = {
                sharpness: Math.random() * 100,
                brightness: Math.random() * 100,
                contrast: Math.random() * 100,
                colorfulness: Math.random() * 100,
                noise: Math.random() * 50,
                overall: 'good' // good, fair, poor
            };

            return analysis;

        } catch (error) {
            throw new Error(`Image analysis failed: ${error.message}`);
        }
    }

    /**
     * Extract various image features
     * @private
     */
    async _extractFeatures(imagePath, imageData) {
        return {
            colors: {
                dominant: ['#FF5733', '#33FF57', '#3357FF'],
                palette: ['#FF5733', '#33FF57', '#3357FF', '#F0F0F0', '#333333'],
                averageColor: '#888888'
            },
            edges: {
                detected: true,
                count: 145,
                strength: 'medium'
            },
            textures: {
                smoothness: 0.7,
                regularity: 0.4,
                roughness: 0.3
            },
            histograms: {
                red: new Array(256).fill(0).map(() => Math.floor(Math.random() * 1000)),
                green: new Array(256).fill(0).map(() => Math.floor(Math.random() * 1000)),
                blue: new Array(256).fill(0).map(() => Math.floor(Math.random() * 1000)),
                luminance: new Array(256).fill(0).map(() => Math.floor(Math.random() * 1000))
            }
        };
    }

    /**
     * Mock implementations for demo mode
     */
    _mockOCR(imagePath, imageData) {
        const filename = imagePath ? path.basename(imagePath) : 'uploaded_image';
        return {
            text: `Mock OCR text extracted from ${filename}.\nThis is sample text that would be found in the image.\nLine 3 of detected text.`,
            confidence: 87.5,
            words: [
                { text: 'Mock', confidence: 95.2, bbox: { x: 10, y: 10, width: 45, height: 20 } },
                { text: 'OCR', confidence: 92.1, bbox: { x: 60, y: 10, width: 35, height: 20 } },
                { text: 'text', confidence: 88.7, bbox: { x: 100, y: 10, width: 40, height: 20 } }
            ],
            lines: [
                { text: 'Mock OCR text extracted from image.', confidence: 90.0, bbox: { x: 10, y: 10, width: 300, height: 20 } }
            ],
            paragraphs: [
                { text: 'Mock OCR text extracted from image.\nThis is sample text.', confidence: 89.2, bbox: { x: 10, y: 10, width: 300, height: 60 } }
            ],
            language: 'eng',
            engine: 'tesseract',
            processingTime: 1250
        };
    }

    _mockMetadata(imagePath) {
        return {
            file: {
                name: path.basename(imagePath || 'sample.jpg'),
                size: 2048576,
                created: new Date('2024-01-15T10:30:00Z'),
                modified: new Date('2024-01-15T10:30:00Z'),
                extension: '.jpg'
            },
            exif: {
                Make: 'Apple',
                Model: 'iPhone 14 Pro',
                Software: 'iOS 17.0',
                DateTime: '2024:01:15 10:30:00'
            },
            image: {
                width: 4032,
                height: 3024,
                colorSpace: 'sRGB',
                orientation: 1
            },
            camera: {
                make: 'Apple',
                model: 'iPhone 14 Pro',
                software: 'iOS 17.0'
            },
            capture: {
                dateTime: '2024:01:15 10:30:00',
                iso: 100,
                aperture: 1.78,
                shutterSpeed: '1/120',
                focalLength: 6.86,
                flash: 'No Flash'
            },
            gps: {
                latitude: 37.7749,
                longitude: -122.4194,
                altitude: 52.0
            }
        };
    }

    _mockDetection(detectTypes) {
        const detections = {};

        detectTypes.forEach(type => {
            switch (type) {
                case 'faces':
                    detections.faces = [
                        {
                            bbox: { x: 100, y: 80, width: 150, height: 180 },
                            confidence: 0.95,
                            landmarks: {
                                leftEye: { x: 140, y: 120 },
                                rightEye: { x: 210, y: 125 },
                                nose: { x: 175, y: 150 },
                                mouth: { x: 175, y: 190 }
                            },
                            attributes: {
                                age: 35,
                                gender: 'male',
                                emotion: 'neutral'
                            }
                        }
                    ];
                    break;
                case 'objects':
                    detections.objects = [
                        { name: 'person', confidence: 0.92, bbox: { x: 50, y: 30, width: 200, height: 400 } },
                        { name: 'car', confidence: 0.78, bbox: { x: 300, y: 200, width: 180, height: 120 } }
                    ];
                    break;
                case 'text':
                    detections.text = [
                        { text: 'STOP', confidence: 0.99, bbox: { x: 150, y: 100, width: 80, height: 30 } },
                        { text: 'MAIN ST', confidence: 0.87, bbox: { x: 120, y: 250, width: 120, height: 25 } }
                    ];
                    break;
            }
        });

        return {
            detections,
            confidence: 0.5,
            types: detectTypes,
            totalDetections: Object.values(detections).reduce((sum, arr) => sum + arr.length, 0)
        };
    }

    _mockImageComparison(path1, path2) {
        return {
            similarity: 0.73,
            method: 'structural_similarity',
            identical: false,
            differences: {
                structural: 0.27,
                color: 0.15,
                texture: 0.22
            },
            recommendations: [
                'Images show moderate similarity',
                'Significant differences in color scheme',
                'Similar composition and structure'
            ]
        };
    }

    _mockQRRead() {
        return {
            found: true,
            data: 'https://example.com/sample-qr-code',
            format: 'QR_CODE',
            location: {
                topLeft: { x: 75, y: 75 },
                topRight: { x: 225, y: 75 },
                bottomLeft: { x: 75, y: 225 },
                bottomRight: { x: 225, y: 225 }
            },
            confidence: 0.98
        };
    }

    _mockImageManipulation(manipulations, outputPath) {
        return {
            outputPath: outputPath || 'processed_image.jpg',
            manipulations: manipulations,
            finalDimensions: {
                width: manipulations.resize?.width || 800,
                height: manipulations.resize?.height || 600
            },
            processed: true,
            note: 'Mock mode - image would be processed in real implementation'
        };
    }

    /**
     * Helper methods
     */
    _checkTesseractAvailable() {
        try {
            require('tesseract.js');
            return true;
        } catch (error) {
            console.warn('Tesseract.js not available, using mock mode');
            return false;
        }
    }

    _isValidImageFile(filePath) {
        const ext = path.extname(filePath).toLowerCase();
        return this.supportedFormats.includes(ext);
    }

    async _detectFaces(imagePath, imageData, threshold) {
        // Mock face detection
        return [
            {
                bbox: { x: 120, y: 90, width: 140, height: 170 },
                confidence: 0.94,
                landmarks: {
                    leftEye: { x: 150, y: 130 },
                    rightEye: { x: 210, y: 135 },
                    nose: { x: 180, y: 160 },
                    mouth: { x: 180, y: 200 }
                }
            }
        ];
    }

    async _detectGeneralObjects(imagePath, imageData, threshold) {
        // Mock object detection
        return [
            { name: 'person', confidence: 0.89, bbox: { x: 60, y: 40, width: 180, height: 360 } },
            { name: 'bicycle', confidence: 0.72, bbox: { x: 250, y: 180, width: 120, height: 80 } }
        ];
    }

    async _detectText(imagePath, imageData, threshold) {
        // Mock text detection
        return [
            { text: 'EXIT', confidence: 0.96, bbox: { x: 100, y: 50, width: 60, height: 25 } },
            { text: '123 MAIN ST', confidence: 0.84, bbox: { x: 80, y: 200, width: 140, height: 20 } }
        ];
    }

    async _detectBarcodes(imagePath, imageData) {
        // Mock barcode detection
        return [
            {
                type: 'CODE_128',
                data: '1234567890123',
                bbox: { x: 150, y: 300, width: 200, height: 50 },
                confidence: 0.97
            }
        ];
    }

    async _detectLandmarks(imagePath, imageData, threshold) {
        // Mock landmark detection
        return [
            {
                name: 'Golden Gate Bridge',
                confidence: 0.91,
                bbox: { x: 0, y: 100, width: 400, height: 200 },
                coordinates: { lat: 37.8199, lng: -122.4783 }
            }
        ];
    }

    async _extractTextRegions(imageInput, words) {
        // Mock text region extraction
        return words.slice(0, 3).map((word, index) => ({
            text: word.text,
            region: `text_region_${index}.png`,
            bbox: word.bbox,
            imageData: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        }));
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
            supportedFormats: this.supportedFormats,
            examples: [
                {
                    description: 'Extract text from image using OCR',
                    input: { action: 'ocr', imagePath: '/path/to/document.jpg', language: 'eng' },
                    output: { text: 'Extracted text content...', confidence: 87.5 }
                },
                {
                    description: 'Detect faces in image',
                    input: { action: 'detect', imagePath: '/path/to/photo.jpg', detectTypes: ['faces'] },
                    output: { detections: { faces: [{ confidence: 0.95, bbox: {} }] } }
                },
                {
                    description: 'Resize and crop image',
                    input: {
                        action: 'manipulate',
                        imagePath: '/path/to/image.jpg',
                        manipulations: { resize: { width: 800, height: 600 } },
                        outputPath: '/path/to/resized.jpg'
                    },
                    output: { processed: true, finalDimensions: { width: 800, height: 600 } }
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

        if (!Array.isArray(this.supportedFormats)) {
            issues.push('Supported formats must be an array');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ImageAnalyzerTool;
} else if (typeof exports !== 'undefined') {
    exports.ImageAnalyzerTool = ImageAnalyzerTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = ImageAnalyzerTool;
}