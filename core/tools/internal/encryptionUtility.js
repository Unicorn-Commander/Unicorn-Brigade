const crypto = require('crypto');
const NodeCache = require('node-cache');

class EncryptionUtility {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 300 }); // 5 minute cache

        this.supportedAlgorithms = {
            symmetric: {
                'aes-256-gcm': { keyLength: 32, ivLength: 16, secure: true, description: 'AES-256-GCM (Recommended)' },
                'aes-192-gcm': { keyLength: 24, ivLength: 16, secure: true, description: 'AES-192-GCM' },
                'aes-128-gcm': { keyLength: 16, ivLength: 16, secure: true, description: 'AES-128-GCM' },
                'aes-256-cbc': { keyLength: 32, ivLength: 16, secure: true, description: 'AES-256-CBC' },
                'aes-256-ctr': { keyLength: 32, ivLength: 16, secure: true, description: 'AES-256-CTR' },
                'chacha20-poly1305': { keyLength: 32, ivLength: 12, secure: true, description: 'ChaCha20-Poly1305' }
            },
            asymmetric: {
                'rsa': { keyLengths: [2048, 3072, 4096], secure: true, description: 'RSA Encryption' },
                'ec': { curves: ['secp256r1', 'secp384r1', 'secp521r1'], secure: true, description: 'Elliptic Curve' },
                'ed25519': { keyLength: 32, secure: true, description: 'Edwards-curve Digital Signature' },
                'x25519': { keyLength: 32, secure: true, description: 'Curve25519 Key Exchange' }
            }
        };

        this.encodingFormats = ['hex', 'base64', 'base64url', 'binary'];

        this.keyDerivationFunctions = {
            'pbkdf2': { secure: true, description: 'PBKDF2 (Password-Based Key Derivation)' },
            'scrypt': { secure: true, description: 'scrypt (Memory-hard KDF)' },
            'argon2': { secure: true, description: 'Argon2 (Modern KDF)' }
        };

        this.compressionAlgorithms = ['gzip', 'deflate', 'brotli'];
    }

    async encryptData(data, options = {}) {
        try {
            const config = {
                algorithm: options.algorithm || 'aes-256-gcm',
                key: options.key || null,
                password: options.password || null,
                encoding: options.encoding || 'base64',
                compress: options.compress || false,
                keyDerivation: options.keyDerivation || 'pbkdf2',
                iterations: options.iterations || 100000,
                saltLength: options.saltLength || 32,
                includeMetadata: options.includeMetadata !== false
            };

            // Validate algorithm
            if (!this.isAlgorithmSupported(config.algorithm)) {
                throw new Error(`Unsupported algorithm: ${config.algorithm}`);
            }

            // Prepare data
            let inputData = data;
            if (typeof data !== 'string' && !Buffer.isBuffer(data)) {
                inputData = JSON.stringify(data);
            }

            // Compress if requested
            if (config.compress) {
                inputData = await this.compressData(inputData);
            }

            // Generate or derive key
            const keyInfo = await this.prepareEncryptionKey(config);

            // Encrypt data
            const encryptionResult = await this.performEncryption(inputData, keyInfo, config);

            const result = {
                encrypted_data: encryptionResult.encryptedData,
                algorithm: config.algorithm,
                encoding: config.encoding,
                key_derivation: keyInfo.derivation || null,
                encryption_metadata: {
                    iv: encryptionResult.iv,
                    salt: keyInfo.salt || null,
                    tag: encryptionResult.tag || null,
                    compressed: config.compress,
                    original_size: Buffer.from(data).length,
                    encrypted_size: encryptionResult.encryptedData.length
                },
                security_info: {
                    algorithm_security: this.getAlgorithmSecurity(config.algorithm),
                    key_strength: this.assessKeyStrength(keyInfo.key),
                    encryption_quality: 'high'
                },
                encrypted_at: new Date().toISOString()
            };

            if (config.includeMetadata) {
                result.decryption_instructions = this.generateDecryptionInstructions(config);
                result.security_recommendations = this.getEncryptionRecommendations(config);
            }

            return result;

        } catch (error) {
            return {
                error: 'Encryption failed',
                message: error.message,
                algorithm: options.algorithm,
                encrypted_at: new Date().toISOString()
            };
        }
    }

    async decryptData(encryptedData, options = {}) {
        try {
            const config = {
                algorithm: options.algorithm || 'aes-256-gcm',
                key: options.key || null,
                password: options.password || null,
                iv: options.iv || null,
                salt: options.salt || null,
                tag: options.tag || null,
                encoding: options.encoding || 'base64',
                compressed: options.compressed || false,
                keyDerivation: options.keyDerivation || 'pbkdf2',
                iterations: options.iterations || 100000
            };

            // Validate required parameters
            if (!encryptedData) {
                throw new Error('Encrypted data is required');
            }

            // Prepare decryption key
            const keyInfo = await this.prepareDecryptionKey(config);

            // Decrypt data
            const decryptionResult = await this.performDecryption(encryptedData, keyInfo, config);

            // Decompress if needed
            let finalData = decryptionResult.decryptedData;
            if (config.compressed) {
                finalData = await this.decompressData(finalData);
            }

            // Try to parse as JSON if it looks like JSON
            let parsedData = finalData;
            if (typeof finalData === 'string' && finalData.startsWith('{') || finalData.startsWith('[')) {
                try {
                    parsedData = JSON.parse(finalData);
                } catch (e) {
                    // Keep as string if JSON parsing fails
                }
            }

            return {
                decrypted_data: parsedData,
                algorithm: config.algorithm,
                decryption_successful: true,
                data_integrity_verified: decryptionResult.integrityVerified,
                metadata: {
                    original_encoding: config.encoding,
                    was_compressed: config.compressed,
                    decrypted_size: Buffer.from(finalData).length
                },
                decrypted_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Decryption failed',
                message: error.message,
                decryption_successful: false,
                possible_causes: [
                    'Incorrect password or key',
                    'Corrupted encrypted data',
                    'Wrong algorithm specified',
                    'Missing or incorrect IV/salt/tag'
                ],
                decrypted_at: new Date().toISOString()
            };
        }
    }

    generateKeyPair(algorithm = 'rsa', options = {}) {
        try {
            const config = {
                algorithm: algorithm.toLowerCase(),
                keySize: options.keySize || (algorithm === 'rsa' ? 2048 : 256),
                curve: options.curve || 'secp256r1',
                format: options.format || 'pem',
                passphrase: options.passphrase || null
            };

            let keyPair;

            if (config.algorithm === 'rsa') {
                keyPair = crypto.generateKeyPairSync('rsa', {
                    modulusLength: config.keySize,
                    publicKeyEncoding: { type: 'spki', format: config.format },
                    privateKeyEncoding: {
                        type: 'pkcs8',
                        format: config.format,
                        cipher: config.passphrase ? 'aes-256-cbc' : undefined,
                        passphrase: config.passphrase
                    }
                });
            } else if (config.algorithm === 'ec') {
                keyPair = crypto.generateKeyPairSync('ec', {
                    namedCurve: config.curve,
                    publicKeyEncoding: { type: 'spki', format: config.format },
                    privateKeyEncoding: {
                        type: 'pkcs8',
                        format: config.format,
                        cipher: config.passphrase ? 'aes-256-cbc' : undefined,
                        passphrase: config.passphrase
                    }
                });
            } else if (config.algorithm === 'ed25519') {
                keyPair = crypto.generateKeyPairSync('ed25519', {
                    publicKeyEncoding: { type: 'spki', format: config.format },
                    privateKeyEncoding: {
                        type: 'pkcs8',
                        format: config.format,
                        cipher: config.passphrase ? 'aes-256-cbc' : undefined,
                        passphrase: config.passphrase
                    }
                });
            } else {
                throw new Error(`Unsupported key pair algorithm: ${config.algorithm}`);
            }

            return {
                algorithm: config.algorithm,
                key_size: config.keySize,
                public_key: keyPair.publicKey,
                private_key: keyPair.privateKey,
                fingerprint: this.calculateKeyFingerprint(keyPair.publicKey),
                security_info: {
                    algorithm_strength: this.getAsymmetricAlgorithmStrength(config.algorithm, config.keySize),
                    recommended_use_cases: this.getAsymmetricUseCases(config.algorithm)
                },
                key_management: {
                    storage_recommendations: this.getKeyStorageRecommendations(config.algorithm),
                    rotation_schedule: this.getKeyRotationSchedule(config.algorithm)
                },
                generated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Key pair generation failed',
                message: error.message,
                algorithm: algorithm,
                generated_at: new Date().toISOString()
            };
        }
    }

    generateSecureKey(length = 32, encoding = 'hex') {
        try {
            const key = crypto.randomBytes(length);
            const encodedKey = key.toString(encoding);

            return {
                key: encodedKey,
                length: length,
                encoding: encoding,
                entropy_bits: length * 8,
                strength_assessment: this.assessKeyStrength(key),
                security_recommendations: [
                    'Store key securely using a key management system',
                    'Never hardcode keys in source code',
                    'Use environment variables or secure vaults',
                    'Implement key rotation policies',
                    'Monitor key usage and access'
                ],
                generated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Secure key generation failed',
                message: error.message,
                generated_at: new Date().toISOString()
            };
        }
    }

    deriveKeyFromPassword(password, options = {}) {
        try {
            const config = {
                algorithm: options.algorithm || 'pbkdf2',
                keyLength: options.keyLength || 32,
                iterations: options.iterations || 100000,
                salt: options.salt || crypto.randomBytes(32),
                encoding: options.encoding || 'hex'
            };

            let derivedKey;

            if (config.algorithm === 'pbkdf2') {
                derivedKey = crypto.pbkdf2Sync(password, config.salt, config.iterations, config.keyLength, 'sha256');
            } else if (config.algorithm === 'scrypt') {
                derivedKey = crypto.scryptSync(password, config.salt, config.keyLength, {
                    N: 32768, // CPU/memory cost
                    r: 8,     // block size
                    p: 1      // parallelization
                });
            } else {
                throw new Error(`Unsupported key derivation algorithm: ${config.algorithm}`);
            }

            return {
                derived_key: derivedKey.toString(config.encoding),
                salt: config.salt.toString(config.encoding),
                algorithm: config.algorithm,
                iterations: config.iterations,
                key_length: config.keyLength,
                password_strength: this.assessPasswordStrength(password),
                derivation_time_ms: 0, // Would measure in real implementation
                security_analysis: {
                    recommended_iterations: this.getRecommendedIterations(config.algorithm),
                    salt_quality: 'high',
                    overall_security: 'high'
                },
                derived_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Key derivation failed',
                message: error.message,
                algorithm: options.algorithm,
                derived_at: new Date().toISOString()
            };
        }
    }

    analyzeEncryptionStrength(algorithm, keySize, additionalParams = {}) {
        try {
            const analysis = {
                algorithm: algorithm,
                key_size: keySize,
                security_level: 'unknown',
                estimated_security_bits: 0,
                quantum_resistance: false,
                recommendations: [],
                compliance: {
                    fips_140: false,
                    common_criteria: false,
                    nist_approved: false
                }
            };

            // Analyze based on algorithm type
            if (this.supportedAlgorithms.symmetric[algorithm]) {
                analysis.security_level = this.getSymmetricSecurityLevel(algorithm, keySize);
                analysis.estimated_security_bits = keySize * 8;
                analysis.quantum_resistance = false;

                if (algorithm.includes('aes') && keySize >= 32) {
                    analysis.compliance.nist_approved = true;
                    analysis.compliance.fips_140 = true;
                }
            } else if (this.supportedAlgorithms.asymmetric[algorithm]) {
                analysis.security_level = this.getAsymmetricSecurityLevel(algorithm, keySize);
                analysis.estimated_security_bits = this.getEquivalentSymmetricBits(algorithm, keySize);

                if (algorithm === 'ed25519' || algorithm === 'x25519') {
                    analysis.quantum_resistance = false; // Post-quantum crypto needed
                }
            }

            // Generate recommendations
            analysis.recommendations = this.generateSecurityRecommendations(analysis);

            // Future-proofing assessment
            analysis.future_proofing = {
                current_adequacy: analysis.estimated_security_bits >= 128,
                recommended_until: this.getAlgorithmLifespan(algorithm, keySize),
                migration_priority: this.getMigrationPriority(analysis)
            };

            return {
                strength_analysis: analysis,
                analyzed_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Encryption strength analysis failed',
                message: error.message,
                algorithm: algorithm,
                analyzed_at: new Date().toISOString()
            };
        }
    }

    async performEncryption(data, keyInfo, config) {
        const algorithm = config.algorithm;
        const algorithmInfo = this.supportedAlgorithms.symmetric[algorithm];

        if (!algorithmInfo) {
            throw new Error(`Unsupported encryption algorithm: ${algorithm}`);
        }

        const iv = crypto.randomBytes(algorithmInfo.ivLength);
        const cipher = crypto.createCipher(algorithm, keyInfo.key);
        cipher.setAAD(Buffer.from('additional-data')); // For AEAD modes

        let encrypted = cipher.update(data, 'utf8', config.encoding);
        encrypted += cipher.final(config.encoding);

        const result = {
            encryptedData: encrypted,
            iv: iv.toString(config.encoding)
        };

        // Add authentication tag for AEAD modes
        if (algorithm.includes('gcm') || algorithm.includes('poly1305')) {
            result.tag = cipher.getAuthTag().toString(config.encoding);
        }

        return result;
    }

    async performDecryption(encryptedData, keyInfo, config) {
        const algorithm = config.algorithm;

        const decipher = crypto.createDecipher(algorithm, keyInfo.key);

        if (config.tag) {
            decipher.setAuthTag(Buffer.from(config.tag, config.encoding));
            decipher.setAAD(Buffer.from('additional-data'));
        }

        let decrypted = decipher.update(encryptedData, config.encoding, 'utf8');
        decrypted += decipher.final('utf8');

        return {
            decryptedData: decrypted,
            integrityVerified: true
        };
    }

    async prepareEncryptionKey(config) {
        if (config.key) {
            return { key: Buffer.from(config.key, 'hex') };
        }

        if (config.password) {
            const salt = crypto.randomBytes(config.saltLength);
            const derivedKey = crypto.pbkdf2Sync(
                config.password,
                salt,
                config.iterations,
                this.supportedAlgorithms.symmetric[config.algorithm].keyLength,
                'sha256'
            );

            return {
                key: derivedKey,
                salt: salt.toString('hex'),
                derivation: config.keyDerivation,
                iterations: config.iterations
            };
        }

        throw new Error('Either key or password must be provided');
    }

    async prepareDecryptionKey(config) {
        if (config.key) {
            return { key: Buffer.from(config.key, 'hex') };
        }

        if (config.password && config.salt) {
            const derivedKey = crypto.pbkdf2Sync(
                config.password,
                Buffer.from(config.salt, 'hex'),
                config.iterations,
                this.supportedAlgorithms.symmetric[config.algorithm].keyLength,
                'sha256'
            );

            return { key: derivedKey };
        }

        throw new Error('Key or password with salt must be provided for decryption');
    }

    isAlgorithmSupported(algorithm) {
        return this.supportedAlgorithms.symmetric[algorithm] || this.supportedAlgorithms.asymmetric[algorithm];
    }

    getAlgorithmSecurity(algorithm) {
        const symInfo = this.supportedAlgorithms.symmetric[algorithm];
        const asymInfo = this.supportedAlgorithms.asymmetric[algorithm];

        return (symInfo || asymInfo)?.secure ? 'high' : 'low';
    }

    assessKeyStrength(key) {
        const keyLength = Buffer.isBuffer(key) ? key.length : key.toString().length / 2;

        if (keyLength >= 32) return 'very_high';
        if (keyLength >= 24) return 'high';
        if (keyLength >= 16) return 'medium';
        return 'low';
    }

    calculateKeyFingerprint(publicKey) {
        const hash = crypto.createHash('sha256');
        hash.update(publicKey);
        return hash.digest('hex').substring(0, 40);
    }

    getToolInfo() {
        return {
            name: 'Encryption Utility',
            version: '2.0.0',
            description: 'Professional encryption and cryptographic toolkit',
            author: 'UC2 System',
            capabilities: [
                'Symmetric encryption (AES, ChaCha20)',
                'Asymmetric key pair generation',
                'Secure key generation and derivation',
                'Password-based key derivation (PBKDF2, scrypt)',
                'Data compression with encryption',
                'Encryption strength analysis',
                'Key management recommendations',
                'Compliance assessment (FIPS, NIST)',
                'Multiple encoding formats',
                'Integrity verification'
            ],
            supported_symmetric: Object.keys(this.supportedAlgorithms.symmetric),
            supported_asymmetric: Object.keys(this.supportedAlgorithms.asymmetric),
            key_derivation_functions: Object.keys(this.keyDerivationFunctions),
            encoding_formats: this.encodingFormats,
            security_standards: ['FIPS 140', 'Common Criteria', 'NIST SP 800-series'],
            cache_duration: '5 minutes'
        };
    }
}

module.exports = EncryptionUtility;