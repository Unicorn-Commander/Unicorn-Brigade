/**
 * Encryption Tool - Security foundation for encryption/decryption operations
 * UC2 Internal Tool v1.0.0
 */

const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

class EncryptionTool {
    constructor() {
        this.name = 'encryptionTool';
        this.version = '1.0.0';
        this.description = 'Comprehensive encryption, decryption, and cryptographic operations';
        this.category = 'security';
        this.permissions = ['security', 'filesystem'];

        // Supported algorithms and their parameters
        this.algorithms = {
            aes: {
                modes: ['aes-256-gcm', 'aes-256-cbc', 'aes-192-gcm', 'aes-128-gcm'],
                keyLengths: { 'aes-256-gcm': 32, 'aes-256-cbc': 32, 'aes-192-gcm': 24, 'aes-128-gcm': 16 },
                ivLengths: { 'aes-256-gcm': 16, 'aes-256-cbc': 16, 'aes-192-gcm': 12, 'aes-128-gcm': 12 }
            },
            rsa: {
                keyLengths: [2048, 3072, 4096],
                padding: ['OAEP', 'PKCS1']
            },
            hash: {
                algorithms: ['sha256', 'sha512', 'sha1', 'md5', 'sha3-256', 'sha3-512'],
                hmacAlgorithms: ['sha256', 'sha512', 'sha1']
            }
        };

        this.schema = {
            type: 'object',
            properties: {
                operation: {
                    type: 'string',
                    enum: [
                        'aes-encrypt', 'aes-decrypt',
                        'rsa-generate-keys', 'rsa-encrypt', 'rsa-decrypt',
                        'hash', 'hmac', 'verify-hmac',
                        'generate-password', 'derive-key',
                        'encrypt-file', 'decrypt-file',
                        'secure-random', 'sign', 'verify-signature'
                    ],
                    description: 'Cryptographic operation to perform'
                },
                data: {
                    type: 'string',
                    description: 'Data to encrypt/decrypt/hash (string or base64)'
                },
                key: {
                    type: 'string',
                    description: 'Encryption key (hex, base64, or string)'
                },
                password: {
                    type: 'string',
                    description: 'Password for key derivation'
                },
                algorithm: {
                    type: 'string',
                    description: 'Algorithm to use (aes-256-gcm, sha256, etc.)'
                },
                keyLength: {
                    type: 'number',
                    description: 'Key length in bits (for key generation)'
                },
                iterations: {
                    type: 'number',
                    default: 100000,
                    description: 'PBKDF2 iterations for key derivation'
                },
                salt: {
                    type: 'string',
                    description: 'Salt for key derivation (hex or base64)'
                },
                iv: {
                    type: 'string',
                    description: 'Initialization vector (hex or base64)'
                },
                publicKey: {
                    type: 'string',
                    description: 'RSA public key (PEM format)'
                },
                privateKey: {
                    type: 'string',
                    description: 'RSA private key (PEM format)'
                },
                filePath: {
                    type: 'string',
                    description: 'File path for file encryption operations'
                },
                outputPath: {
                    type: 'string',
                    description: 'Output file path'
                },
                outputFormat: {
                    type: 'string',
                    enum: ['hex', 'base64', 'utf8', 'binary'],
                    default: 'hex',
                    description: 'Output format for results'
                },
                inputFormat: {
                    type: 'string',
                    enum: ['hex', 'base64', 'utf8', 'binary'],
                    default: 'utf8',
                    description: 'Input format for data'
                },
                passwordLength: {
                    type: 'number',
                    default: 16,
                    minimum: 8,
                    maximum: 256,
                    description: 'Length of generated password'
                },
                passwordComplexity: {
                    type: 'object',
                    properties: {
                        uppercase: { type: 'boolean', default: true },
                        lowercase: { type: 'boolean', default: true },
                        numbers: { type: 'boolean', default: true },
                        symbols: { type: 'boolean', default: true },
                        excludeSimilar: { type: 'boolean', default: false }
                    },
                    description: 'Password complexity requirements'
                },
                randomBytes: {
                    type: 'number',
                    default: 32,
                    minimum: 1,
                    maximum: 1024,
                    description: 'Number of random bytes to generate'
                }
            },
            required: ['operation']
        };
    }

    /**
     * Execute cryptographic operation
     */
    async execute(params, context = {}) {
        try {
            const { operation } = params;

            // Input validation
            if (!operation) {
                throw new Error('Operation is required');
            }

            const startTime = process.hrtime.bigint();
            let result;

            // Route to appropriate operation
            switch (operation) {
                case 'aes-encrypt':
                    result = await this._aesEncrypt(params);
                    break;
                case 'aes-decrypt':
                    result = await this._aesDecrypt(params);
                    break;
                case 'rsa-generate-keys':
                    result = await this._rsaGenerateKeys(params);
                    break;
                case 'rsa-encrypt':
                    result = await this._rsaEncrypt(params);
                    break;
                case 'rsa-decrypt':
                    result = await this._rsaDecrypt(params);
                    break;
                case 'hash':
                    result = await this._hash(params);
                    break;
                case 'hmac':
                    result = await this._hmac(params);
                    break;
                case 'verify-hmac':
                    result = await this._verifyHmac(params);
                    break;
                case 'generate-password':
                    result = await this._generatePassword(params);
                    break;
                case 'derive-key':
                    result = await this._deriveKey(params);
                    break;
                case 'encrypt-file':
                    result = await this._encryptFile(params);
                    break;
                case 'decrypt-file':
                    result = await this._decryptFile(params);
                    break;
                case 'secure-random':
                    result = await this._secureRandom(params);
                    break;
                case 'sign':
                    result = await this._sign(params);
                    break;
                case 'verify-signature':
                    result = await this._verifySignature(params);
                    break;
                default:
                    throw new Error(`Unsupported operation: ${operation}`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000;

            return {
                success: true,
                operation: operation,
                result: result,
                executionTime: `${executionTime.toFixed(2)}ms`,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            return {
                success: false,
                operation: params.operation,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * AES Encryption
     * @private
     */
    async _aesEncrypt(params) {
        const {
            data,
            key,
            algorithm = 'aes-256-gcm',
            iv,
            inputFormat = 'utf8',
            outputFormat = 'hex'
        } = params;

        if (!data) {
            throw new Error('Data is required for encryption');
        }

        if (!key) {
            throw new Error('Key is required for encryption');
        }

        // Parse key and IV
        const keyBuffer = this._parseBuffer(key, 'hex');
        const ivBuffer = iv ? this._parseBuffer(iv, 'hex') : crypto.randomBytes(this.algorithms.aes.ivLengths[algorithm] || 16);

        // Validate key length
        const expectedKeyLength = this.algorithms.aes.keyLengths[algorithm];
        if (keyBuffer.length !== expectedKeyLength) {
            throw new Error(`Key length must be ${expectedKeyLength} bytes for ${algorithm}`);
        }

        // Parse input data
        const dataBuffer = this._parseBuffer(data, inputFormat);

        // Create cipher
        const cipher = crypto.createCipher(algorithm, keyBuffer);
        if (algorithm.includes('gcm') || algorithm.includes('cbc')) {
            cipher.setAAD ? cipher.setAAD(Buffer.alloc(0)) : null;
        }

        // Encrypt
        let encrypted = cipher.update(dataBuffer);
        encrypted = Buffer.concat([encrypted, cipher.final()]);

        let result = {
            encrypted: this._formatBuffer(encrypted, outputFormat),
            algorithm: algorithm,
            iv: this._formatBuffer(ivBuffer, 'hex')
        };

        // Add auth tag for GCM mode
        if (algorithm.includes('gcm') && cipher.getAuthTag) {
            result.authTag = cipher.getAuthTag().toString('hex');
        }

        return result;
    }

    /**
     * AES Decryption
     * @private
     */
    async _aesDecrypt(params) {
        const {
            data,
            key,
            iv,
            authTag,
            algorithm = 'aes-256-gcm',
            inputFormat = 'hex',
            outputFormat = 'utf8'
        } = params;

        if (!data || !key || !iv) {
            throw new Error('Data, key, and IV are required for decryption');
        }

        // Parse inputs
        const keyBuffer = this._parseBuffer(key, 'hex');
        const ivBuffer = this._parseBuffer(iv, 'hex');
        const encryptedBuffer = this._parseBuffer(data, inputFormat);

        // Create decipher
        const decipher = crypto.createDecipher(algorithm, keyBuffer);

        // Set auth tag for GCM mode
        if (algorithm.includes('gcm') && authTag) {
            decipher.setAuthTag(Buffer.from(authTag, 'hex'));
        }

        // Decrypt
        let decrypted = decipher.update(encryptedBuffer);
        decrypted = Buffer.concat([decrypted, decipher.final()]);

        return {
            decrypted: this._formatBuffer(decrypted, outputFormat),
            algorithm: algorithm
        };
    }

    /**
     * RSA Key Generation
     * @private
     */
    async _rsaGenerateKeys(params) {
        const { keyLength = 2048 } = params;

        if (!this.algorithms.rsa.keyLengths.includes(keyLength)) {
            throw new Error(`Unsupported RSA key length: ${keyLength}`);
        }

        const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
            modulusLength: keyLength,
            publicKeyEncoding: {
                type: 'spki',
                format: 'pem'
            },
            privateKeyEncoding: {
                type: 'pkcs8',
                format: 'pem'
            }
        });

        return {
            publicKey: publicKey,
            privateKey: privateKey,
            keyLength: keyLength,
            format: 'PEM'
        };
    }

    /**
     * RSA Encryption
     * @private
     */
    async _rsaEncrypt(params) {
        const { data, publicKey, inputFormat = 'utf8', outputFormat = 'base64' } = params;

        if (!data || !publicKey) {
            throw new Error('Data and public key are required for RSA encryption');
        }

        const dataBuffer = this._parseBuffer(data, inputFormat);
        const encrypted = crypto.publicEncrypt(publicKey, dataBuffer);

        return {
            encrypted: this._formatBuffer(encrypted, outputFormat),
            algorithm: 'RSA'
        };
    }

    /**
     * RSA Decryption
     * @private
     */
    async _rsaDecrypt(params) {
        const { data, privateKey, inputFormat = 'base64', outputFormat = 'utf8' } = params;

        if (!data || !privateKey) {
            throw new Error('Data and private key are required for RSA decryption');
        }

        const encryptedBuffer = this._parseBuffer(data, inputFormat);
        const decrypted = crypto.privateDecrypt(privateKey, encryptedBuffer);

        return {
            decrypted: this._formatBuffer(decrypted, outputFormat),
            algorithm: 'RSA'
        };
    }

    /**
     * Hash Generation
     * @private
     */
    async _hash(params) {
        const { data, algorithm = 'sha256', inputFormat = 'utf8', outputFormat = 'hex' } = params;

        if (!data) {
            throw new Error('Data is required for hashing');
        }

        if (!this.algorithms.hash.algorithms.includes(algorithm)) {
            throw new Error(`Unsupported hash algorithm: ${algorithm}`);
        }

        const dataBuffer = this._parseBuffer(data, inputFormat);
        const hash = crypto.createHash(algorithm).update(dataBuffer).digest();

        return {
            hash: this._formatBuffer(hash, outputFormat),
            algorithm: algorithm,
            inputLength: dataBuffer.length
        };
    }

    /**
     * HMAC Generation
     * @private
     */
    async _hmac(params) {
        const { data, key, algorithm = 'sha256', inputFormat = 'utf8', outputFormat = 'hex' } = params;

        if (!data || !key) {
            throw new Error('Data and key are required for HMAC');
        }

        if (!this.algorithms.hash.hmacAlgorithms.includes(algorithm)) {
            throw new Error(`Unsupported HMAC algorithm: ${algorithm}`);
        }

        const dataBuffer = this._parseBuffer(data, inputFormat);
        const keyBuffer = this._parseBuffer(key, 'utf8');
        const hmac = crypto.createHmac(algorithm, keyBuffer).update(dataBuffer).digest();

        return {
            hmac: this._formatBuffer(hmac, outputFormat),
            algorithm: algorithm,
            keyLength: keyBuffer.length
        };
    }

    /**
     * HMAC Verification
     * @private
     */
    async _verifyHmac(params) {
        const { data, key, hmac, algorithm = 'sha256', inputFormat = 'utf8' } = params;

        if (!data || !key || !hmac) {
            throw new Error('Data, key, and HMAC are required for verification');
        }

        // Generate HMAC
        const computedHmac = await this._hmac({ data, key, algorithm, inputFormat, outputFormat: 'hex' });

        // Compare HMACs using timing-safe comparison
        const providedHmacBuffer = Buffer.from(hmac, 'hex');
        const computedHmacBuffer = Buffer.from(computedHmac.hmac, 'hex');

        const isValid = crypto.timingSafeEqual(providedHmacBuffer, computedHmacBuffer);

        return {
            valid: isValid,
            algorithm: algorithm,
            providedHmac: hmac,
            computedHmac: computedHmac.hmac
        };
    }

    /**
     * Password Generation
     * @private
     */
    async _generatePassword(params) {
        const {
            passwordLength = 16,
            passwordComplexity = {
                uppercase: true,
                lowercase: true,
                numbers: true,
                symbols: true,
                excludeSimilar: false
            }
        } = params;

        if (passwordLength < 8 || passwordLength > 256) {
            throw new Error('Password length must be between 8 and 256 characters');
        }

        // Character sets
        const charSets = {
            uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            lowercase: 'abcdefghijklmnopqrstuvwxyz',
            numbers: '0123456789',
            symbols: '!@#$%^&*()_+-=[]{}|;:,.<>?',
            similarChars: 'il1Lo0O'
        };

        // Build character pool
        let charPool = '';
        const requiredChars = [];

        if (passwordComplexity.uppercase) {
            charPool += charSets.uppercase;
            requiredChars.push(this._getRandomChar(charSets.uppercase));
        }
        if (passwordComplexity.lowercase) {
            charPool += charSets.lowercase;
            requiredChars.push(this._getRandomChar(charSets.lowercase));
        }
        if (passwordComplexity.numbers) {
            charPool += charSets.numbers;
            requiredChars.push(this._getRandomChar(charSets.numbers));
        }
        if (passwordComplexity.symbols) {
            charPool += charSets.symbols;
            requiredChars.push(this._getRandomChar(charSets.symbols));
        }

        // Exclude similar characters if requested
        if (passwordComplexity.excludeSimilar) {
            for (const char of charSets.similarChars) {
                charPool = charPool.replace(new RegExp(char.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '');
            }
        }

        if (charPool.length === 0) {
            throw new Error('No valid characters available for password generation');
        }

        // Generate password
        const password = [];

        // Add required characters first
        for (const char of requiredChars) {
            password.push(char);
        }

        // Fill remaining length with random characters
        for (let i = requiredChars.length; i < passwordLength; i++) {
            password.push(this._getRandomChar(charPool));
        }

        // Shuffle the password
        for (let i = password.length - 1; i > 0; i--) {
            const j = crypto.randomInt(0, i + 1);
            [password[i], password[j]] = [password[j], password[i]];
        }

        return {
            password: password.join(''),
            length: passwordLength,
            complexity: passwordComplexity,
            entropy: Math.log2(charPool.length) * passwordLength
        };
    }

    /**
     * Key Derivation (PBKDF2)
     * @private
     */
    async _deriveKey(params) {
        const {
            password,
            salt,
            iterations = 100000,
            keyLength = 32,
            algorithm = 'sha256',
            outputFormat = 'hex'
        } = params;

        if (!password) {
            throw new Error('Password is required for key derivation');
        }

        // Generate salt if not provided
        const saltBuffer = salt ? this._parseBuffer(salt, 'hex') : crypto.randomBytes(32);

        const derivedKey = crypto.pbkdf2Sync(password, saltBuffer, iterations, keyLength, algorithm);

        return {
            key: this._formatBuffer(derivedKey, outputFormat),
            salt: saltBuffer.toString('hex'),
            iterations: iterations,
            keyLength: keyLength,
            algorithm: algorithm
        };
    }

    /**
     * File Encryption
     * @private
     */
    async _encryptFile(params) {
        const {
            filePath,
            outputPath,
            key,
            algorithm = 'aes-256-gcm'
        } = params;

        if (!filePath || !key) {
            throw new Error('File path and key are required for file encryption');
        }

        // Read file
        const fileData = await fs.readFile(filePath);

        // Encrypt data
        const encryptionResult = await this._aesEncrypt({
            data: fileData.toString('base64'),
            key: key,
            algorithm: algorithm,
            inputFormat: 'base64',
            outputFormat: 'hex'
        });

        // Create encrypted file data
        const encryptedFileData = {
            algorithm: algorithm,
            iv: encryptionResult.iv,
            authTag: encryptionResult.authTag,
            encrypted: encryptionResult.encrypted,
            originalSize: fileData.length,
            timestamp: new Date().toISOString()
        };

        const outputFilePath = outputPath || `${filePath}.encrypted`;

        // Write encrypted file
        await fs.writeFile(outputFilePath, JSON.stringify(encryptedFileData, null, 2));

        return {
            inputFile: filePath,
            outputFile: outputFilePath,
            originalSize: fileData.length,
            encryptedSize: JSON.stringify(encryptedFileData).length,
            algorithm: algorithm
        };
    }

    /**
     * File Decryption
     * @private
     */
    async _decryptFile(params) {
        const {
            filePath,
            outputPath,
            key
        } = params;

        if (!filePath || !key) {
            throw new Error('File path and key are required for file decryption');
        }

        // Read encrypted file
        const encryptedData = JSON.parse(await fs.readFile(filePath, 'utf8'));

        // Decrypt data
        const decryptionResult = await this._aesDecrypt({
            data: encryptedData.encrypted,
            key: key,
            iv: encryptedData.iv,
            authTag: encryptedData.authTag,
            algorithm: encryptedData.algorithm,
            inputFormat: 'hex',
            outputFormat: 'base64'
        });

        // Convert back to original format
        const originalData = Buffer.from(decryptionResult.decrypted, 'base64');

        const outputFilePath = outputPath || filePath.replace('.encrypted', '.decrypted');

        // Write decrypted file
        await fs.writeFile(outputFilePath, originalData);

        return {
            inputFile: filePath,
            outputFile: outputFilePath,
            originalSize: encryptedData.originalSize,
            decryptedSize: originalData.length,
            algorithm: encryptedData.algorithm
        };
    }

    /**
     * Secure Random Generation
     * @private
     */
    async _secureRandom(params) {
        const { randomBytes = 32, outputFormat = 'hex' } = params;

        if (randomBytes < 1 || randomBytes > 1024) {
            throw new Error('Random bytes must be between 1 and 1024');
        }

        const randomBuffer = crypto.randomBytes(randomBytes);

        return {
            random: this._formatBuffer(randomBuffer, outputFormat),
            bytes: randomBytes,
            format: outputFormat,
            entropy: randomBytes * 8
        };
    }

    /**
     * Digital Signature
     * @private
     */
    async _sign(params) {
        const { data, privateKey, algorithm = 'RSA-SHA256', inputFormat = 'utf8', outputFormat = 'base64' } = params;

        if (!data || !privateKey) {
            throw new Error('Data and private key are required for signing');
        }

        const dataBuffer = this._parseBuffer(data, inputFormat);
        const signature = crypto.sign(algorithm, dataBuffer, privateKey);

        return {
            signature: this._formatBuffer(signature, outputFormat),
            algorithm: algorithm,
            dataLength: dataBuffer.length
        };
    }

    /**
     * Signature Verification
     * @private
     */
    async _verifySignature(params) {
        const { data, signature, publicKey, algorithm = 'RSA-SHA256', inputFormat = 'utf8' } = params;

        if (!data || !signature || !publicKey) {
            throw new Error('Data, signature, and public key are required for verification');
        }

        const dataBuffer = this._parseBuffer(data, inputFormat);
        const signatureBuffer = this._parseBuffer(signature, 'base64');

        const isValid = crypto.verify(algorithm, dataBuffer, publicKey, signatureBuffer);

        return {
            valid: isValid,
            algorithm: algorithm,
            dataLength: dataBuffer.length
        };
    }

    /**
     * Parse buffer from various formats
     * @private
     */
    _parseBuffer(data, format) {
        switch (format) {
            case 'hex':
                return Buffer.from(data, 'hex');
            case 'base64':
                return Buffer.from(data, 'base64');
            case 'utf8':
            case 'string':
                return Buffer.from(data, 'utf8');
            case 'binary':
                return Buffer.from(data, 'binary');
            default:
                return Buffer.from(data);
        }
    }

    /**
     * Format buffer to various formats
     * @private
     */
    _formatBuffer(buffer, format) {
        switch (format) {
            case 'hex':
                return buffer.toString('hex');
            case 'base64':
                return buffer.toString('base64');
            case 'utf8':
            case 'string':
                return buffer.toString('utf8');
            case 'binary':
                return buffer.toString('binary');
            default:
                return buffer.toString('hex');
        }
    }

    /**
     * Get random character from string
     * @private
     */
    _getRandomChar(str) {
        return str[crypto.randomInt(0, str.length)];
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
            supportedOperations: [
                'aes-encrypt', 'aes-decrypt',
                'rsa-generate-keys', 'rsa-encrypt', 'rsa-decrypt',
                'hash', 'hmac', 'verify-hmac',
                'generate-password', 'derive-key',
                'encrypt-file', 'decrypt-file',
                'secure-random', 'sign', 'verify-signature'
            ],
            algorithms: this.algorithms,
            examples: [
                {
                    description: 'AES encryption',
                    input: {
                        operation: 'aes-encrypt',
                        data: 'Hello World',
                        key: crypto.randomBytes(32).toString('hex')
                    },
                    output: { encrypted: 'hex_string', iv: 'hex_string' }
                },
                {
                    description: 'Generate RSA key pair',
                    input: {
                        operation: 'rsa-generate-keys',
                        keyLength: 2048
                    },
                    output: { publicKey: 'PEM_string', privateKey: 'PEM_string' }
                },
                {
                    description: 'Hash data',
                    input: {
                        operation: 'hash',
                        data: 'Hello World',
                        algorithm: 'sha256'
                    },
                    output: { hash: 'hex_string', algorithm: 'sha256' }
                },
                {
                    description: 'Generate secure password',
                    input: {
                        operation: 'generate-password',
                        passwordLength: 20,
                        passwordComplexity: {
                            uppercase: true,
                            lowercase: true,
                            numbers: true,
                            symbols: false
                        }
                    },
                    output: { password: 'secure_password', entropy: 119.5 }
                }
            ],
            securityNotes: [
                'All cryptographic operations use Node.js crypto module',
                'Keys and sensitive data should be handled securely',
                'Use strong, unique keys for each encryption operation',
                'Consider key rotation and secure key storage',
                'Verify HMAC signatures to prevent tampering'
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        // Check Node.js crypto module
        try {
            const testHash = crypto.createHash('sha256').update('test').digest('hex');
            if (!testHash) {
                issues.push('Crypto module not functioning correctly');
            }
        } catch (error) {
            issues.push(`Crypto module error: ${error.message}`);
        }

        // Validate algorithm support
        try {
            crypto.getCiphers();
            crypto.getHashes();
        } catch (error) {
            issues.push(`Algorithm enumeration failed: ${error.message}`);
        }

        return {
            valid: issues.length === 0,
            issues: issues,
            capabilities: {
                aesEncryption: true,
                rsaEncryption: true,
                hashing: true,
                hmac: true,
                passwordGeneration: true,
                keyDerivation: true,
                fileEncryption: true,
                digitalSignatures: true,
                secureRandom: true
            }
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EncryptionTool;
} else if (typeof exports !== 'undefined') {
    exports.EncryptionTool = EncryptionTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = EncryptionTool;
}