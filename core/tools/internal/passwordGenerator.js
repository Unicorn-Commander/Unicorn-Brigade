const crypto = require('crypto');
const NodeCache = require('node-cache');

class PasswordGenerator {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 300 }); // 5 minute cache for analysis results

        this.characterSets = {
            lowercase: 'abcdefghijklmnopqrstuvwxyz',
            uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
            numbers: '0123456789',
            symbols: '!@#$%^&*()_+-=[]{}|;:,.<>?',
            similarChars: 'il1Lo0O',
            ambiguousChars: '{}[]()/\\\'"`~,;.<>',
            extendedSymbols: '¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿'
        };

        this.commonPasswords = [
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', '1234567890', 'abc123',
            'Password1', 'password1', '12345678', 'welcome123'
        ];

        this.passphraseWordlists = {
            eff_large: [
                'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb',
                'abstract', 'absurd', 'abuse', 'access', 'accident', 'account',
                'accuse', 'achieve', 'acid', 'acoustic', 'acquire', 'across',
                'action', 'actor', 'actual', 'adapt', 'add', 'addict', 'address'
            ],
            diceware: [
                'aback', 'abase', 'abash', 'abate', 'abbey', 'abbot', 'abhor',
                'abide', 'abled', 'abode', 'abort', 'about', 'above', 'abuse',
                'abyss', 'acorn', 'acrid', 'actor', 'acute', 'adage', 'adapt'
            ]
        };

        this.securityLevels = {
            weak: { minLength: 8, complexity: 2 },
            medium: { minLength: 12, complexity: 3 },
            strong: { minLength: 16, complexity: 4 },
            enterprise: { minLength: 20, complexity: 4 }
        };
    }

    generatePassword(options = {}) {
        try {
            const config = {
                length: options.length || 16,
                includeUppercase: options.includeUppercase !== false,
                includeLowercase: options.includeLowercase !== false,
                includeNumbers: options.includeNumbers !== false,
                includeSymbols: options.includeSymbols !== false,
                excludeSimilar: options.excludeSimilar || false,
                excludeAmbiguous: options.excludeAmbiguous || false,
                startWithLetter: options.startWithLetter || false,
                noConsecutive: options.noConsecutive || false,
                customCharset: options.customCharset || null,
                minNumeric: options.minNumeric || 0,
                minSymbols: options.minSymbols || 0,
                pattern: options.pattern || null // e.g., "ULNS" for Upper, Lower, Number, Symbol
            };

            // Build character set
            let charset = '';
            if (config.includeLowercase) charset += this.characterSets.lowercase;
            if (config.includeUppercase) charset += this.characterSets.uppercase;
            if (config.includeNumbers) charset += this.characterSets.numbers;
            if (config.includeSymbols) charset += this.characterSets.symbols;

            if (config.customCharset) {
                charset = config.customCharset;
            }

            // Remove unwanted characters
            if (config.excludeSimilar) {
                charset = charset.replace(new RegExp(`[${this.characterSets.similarChars}]`, 'g'), '');
            }

            if (config.excludeAmbiguous) {
                charset = charset.replace(new RegExp(`[${this.escapeRegex(this.characterSets.ambiguousChars)}]`, 'g'), '');
            }

            if (charset.length === 0) {
                throw new Error('No characters available for password generation');
            }

            let password = '';

            // Generate based on pattern if provided
            if (config.pattern) {
                password = this.generateByPattern(config.pattern, config);
            } else {
                // Standard random generation
                for (let i = 0; i < config.length; i++) {
                    const randomIndex = crypto.randomInt(0, charset.length);
                    const char = charset[randomIndex];

                    // Check constraints
                    if (config.noConsecutive && password.length > 0 && password[password.length - 1] === char) {
                        i--; // Retry
                        continue;
                    }

                    if (config.startWithLetter && i === 0 && !/[a-zA-Z]/.test(char)) {
                        i--; // Retry
                        continue;
                    }

                    password += char;
                }

                // Ensure minimum requirements
                password = this.ensureMinimumRequirements(password, config, charset);
            }

            // Analyze the generated password
            const analysis = this.analyzePassword(password);

            return {
                password: password,
                length: password.length,
                configuration: config,
                strength: analysis.strength,
                entropy: analysis.entropy,
                crack_time: analysis.crackTime,
                charset_size: charset.length,
                meets_requirements: this.checkRequirements(password, config),
                security_recommendations: this.getSecurityRecommendations(password, analysis),
                generated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Password generation failed',
                message: error.message,
                generated_at: new Date().toISOString()
            };
        }
    }

    generatePassphrase(options = {}) {
        try {
            const config = {
                wordCount: options.wordCount || 4,
                separator: options.separator || '-',
                wordlist: options.wordlist || 'eff_large',
                includeNumbers: options.includeNumbers || false,
                capitalize: options.capitalize || false,
                minWordLength: options.minWordLength || 3,
                maxWordLength: options.maxWordLength || 10,
                customWords: options.customWords || null
            };

            let wordList = this.passphraseWordlists[config.wordlist] || this.passphraseWordlists.eff_large;

            // Filter by word length
            wordList = wordList.filter(word =>
                word.length >= config.minWordLength &&
                word.length <= config.maxWordLength
            );

            if (config.customWords && Array.isArray(config.customWords)) {
                wordList = config.customWords;
            }

            if (wordList.length === 0) {
                throw new Error('No words available for passphrase generation');
            }

            const words = [];

            for (let i = 0; i < config.wordCount; i++) {
                const randomIndex = crypto.randomInt(0, wordList.length);
                let word = wordList[randomIndex];

                if (config.capitalize) {
                    word = word.charAt(0).toUpperCase() + word.slice(1);
                }

                words.push(word);
            }

            // Add numbers if requested
            if (config.includeNumbers) {
                const randomPosition = crypto.randomInt(0, words.length + 1);
                const randomNumber = crypto.randomInt(10, 999);
                words.splice(randomPosition, 0, randomNumber.toString());
            }

            const passphrase = words.join(config.separator);
            const analysis = this.analyzePassword(passphrase);

            return {
                passphrase: passphrase,
                words: words,
                word_count: words.filter(w => isNaN(w)).length,
                length: passphrase.length,
                configuration: config,
                strength: analysis.strength,
                entropy: analysis.entropy,
                crack_time: analysis.crackTime,
                wordlist_size: wordList.length,
                security_recommendations: this.getSecurityRecommendations(passphrase, analysis),
                generated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Passphrase generation failed',
                message: error.message,
                generated_at: new Date().toISOString()
            };
        }
    }

    analyzePassword(password) {
        try {
            const cacheKey = `analyze_${crypto.createHash('sha256').update(password).digest('hex')}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            const analysis = {
                length: password.length,
                character_types: this.getCharacterTypes(password),
                entropy: this.calculateEntropy(password),
                strength: 'weak',
                score: 0,
                crackTime: {},
                vulnerabilities: [],
                recommendations: []
            };

            // Calculate strength score
            analysis.score = this.calculateStrengthScore(password, analysis);
            analysis.strength = this.determineStrength(analysis.score);

            // Calculate crack time estimates
            analysis.crackTime = this.estimateCrackTime(password, analysis.entropy);

            // Check for vulnerabilities
            analysis.vulnerabilities = this.identifyVulnerabilities(password);

            // Generate recommendations
            analysis.recommendations = this.generateRecommendations(password, analysis);

            // Pattern analysis
            analysis.patterns = this.detectPatterns(password);

            // Dictionary check
            analysis.dictionary_words = this.checkDictionaryWords(password);

            // Common password check
            analysis.is_common = this.isCommonPassword(password);

            const result = analysis;
            this.cache.set(cacheKey, result);
            return result;

        } catch (error) {
            return {
                error: 'Password analysis failed',
                message: error.message,
                length: password.length
            };
        }
    }

    generateBulkPasswords(count, options = {}) {
        try {
            if (count > 1000) {
                throw new Error('Maximum bulk generation limit is 1000 passwords');
            }

            const passwords = [];
            const duplicateCheck = new Set();

            for (let i = 0; i < count; i++) {
                let attempts = 0;
                let password;

                do {
                    const result = this.generatePassword(options);
                    if (result.error) {
                        throw new Error(result.message);
                    }

                    password = result.password;
                    attempts++;

                    if (attempts > 100) {
                        throw new Error('Too many attempts to generate unique passwords');
                    }
                } while (duplicateCheck.has(password));

                duplicateCheck.add(password);
                passwords.push({
                    id: i + 1,
                    password: password,
                    strength: this.determineStrength(this.calculateStrengthScore(password))
                });
            }

            return {
                total_generated: count,
                passwords: passwords,
                generation_options: options,
                uniqueness: '100%',
                average_strength: this.calculateAverageStrength(passwords),
                generated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Bulk password generation failed',
                message: error.message,
                generated_at: new Date().toISOString()
            };
        }
    }

    checkPasswordBreach(password) {
        try {
            // In real implementation, would check against Have I Been Pwned API
            // For now, check against common passwords
            const isCommon = this.isCommonPassword(password);

            // Simulate breach check
            const hash = crypto.createHash('sha1').update(password).digest('hex').toUpperCase();
            const mockBreachData = {
                breached: isCommon,
                breach_count: isCommon ? Math.floor(Math.random() * 1000000) + 1000 : 0,
                hash_prefix: hash.substring(0, 5),
                recommendations: []
            };

            if (mockBreachData.breached) {
                mockBreachData.recommendations = [
                    'This password has been found in data breaches',
                    'Change this password immediately',
                    'Generate a new, unique password',
                    'Enable two-factor authentication'
                ];
            } else {
                mockBreachData.recommendations = [
                    'Password not found in known breaches',
                    'Continue monitoring for future breaches',
                    'Consider using a password manager'
                ];
            }

            return {
                password_status: mockBreachData.breached ? 'BREACHED' : 'SAFE',
                breach_details: mockBreachData,
                checked_at: new Date().toISOString(),
                data_source: 'Have I Been Pwned (Simulated)'
            };

        } catch (error) {
            return {
                error: 'Breach check failed',
                message: error.message,
                checked_at: new Date().toISOString()
            };
        }
    }

    calculateEntropy(password) {
        const charsetSize = this.getCharsetSize(password);
        const length = password.length;
        return Math.log2(Math.pow(charsetSize, length));
    }

    calculateStrengthScore(password, analysis = null) {
        if (!analysis) {
            analysis = { character_types: this.getCharacterTypes(password) };
        }

        let score = 0;

        // Length scoring
        if (password.length >= 20) score += 30;
        else if (password.length >= 16) score += 25;
        else if (password.length >= 12) score += 20;
        else if (password.length >= 8) score += 15;
        else score += password.length * 2;

        // Character type diversity
        score += analysis.character_types.length * 10;

        // Entropy bonus
        if (analysis.entropy) {
            if (analysis.entropy >= 60) score += 20;
            else if (analysis.entropy >= 40) score += 15;
            else if (analysis.entropy >= 28) score += 10;
        }

        // Penalties
        if (this.isCommonPassword(password)) score -= 30;
        if (this.hasRepeatingChars(password)) score -= 10;
        if (this.hasSequentialChars(password)) score -= 15;

        return Math.max(0, Math.min(100, score));
    }

    getCharacterTypes(password) {
        const types = [];
        if (/[a-z]/.test(password)) types.push('lowercase');
        if (/[A-Z]/.test(password)) types.push('uppercase');
        if (/[0-9]/.test(password)) types.push('numbers');
        if (/[^a-zA-Z0-9]/.test(password)) types.push('symbols');
        return types;
    }

    getCharsetSize(password) {
        const types = this.getCharacterTypes(password);
        let size = 0;

        if (types.includes('lowercase')) size += 26;
        if (types.includes('uppercase')) size += 26;
        if (types.includes('numbers')) size += 10;
        if (types.includes('symbols')) size += 32; // Approximate

        return size;
    }

    isCommonPassword(password) {
        return this.commonPasswords.includes(password.toLowerCase()) ||
               this.commonPasswords.some(common => password.toLowerCase().includes(common));
    }

    getToolInfo() {
        return {
            name: 'Password Generator',
            version: '2.0.0',
            description: 'Advanced password and passphrase generation with security analysis',
            author: 'UC2 System',
            capabilities: [
                'Cryptographically secure password generation',
                'Customizable character sets and patterns',
                'Passphrase generation with multiple wordlists',
                'Password strength analysis and scoring',
                'Entropy calculation',
                'Breach checking (simulated)',
                'Bulk password generation',
                'Pattern detection',
                'Security recommendations',
                'Multiple generation strategies'
            ],
            security_levels: Object.keys(this.securityLevels),
            wordlists: Object.keys(this.passphraseWordlists),
            max_bulk_generation: 1000,
            cache_duration: '5 minutes'
        };
    }
}

module.exports = PasswordGenerator;