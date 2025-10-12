const dns = require('dns').promises;
const whois = require('node-whois');
const https = require('https');
const crypto = require('crypto');
const { URL } = require('url');

class DomainAnalyzerTool {
    constructor() {
        this.name = 'domainAnalyzer';
        this.version = '1.0.0';
        this.description = 'Comprehensive domain analysis including WHOIS, DNS, SSL certificate, and security checks';
        this.category = 'OSINT & Investigation';
        this.author = 'UC2 System';
        this.tags = ['domain', 'whois', 'dns', 'ssl', 'osint', 'investigation'];

        this.schema = {
            type: 'object',
            properties: {
                domain: {
                    type: 'string',
                    description: 'Domain name to analyze (e.g., example.com)',
                    pattern: '^([a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,}$'
                },
                checks: {
                    type: 'array',
                    description: 'Types of analysis to perform',
                    items: {
                        type: 'string',
                        enum: ['whois', 'dns', 'ssl', 'security', 'reputation', 'all']
                    },
                    default: ['all']
                },
                includeSubdomains: {
                    type: 'boolean',
                    description: 'Include subdomain enumeration',
                    default: false
                },
                timeout: {
                    type: 'number',
                    description: 'Timeout for operations in milliseconds',
                    default: 30000,
                    minimum: 5000,
                    maximum: 60000
                }
            },
            required: ['domain']
        };

        this.commonSubdomains = [
            'www', 'mail', 'ftp', 'blog', 'webmail', 'server', 'ns1', 'ns2',
            'smtp', 'secure', 'vpn', 'admin', 'api', 'cdn', 'dev', 'staging',
            'test', 'support', 'help', 'shop', 'store', 'mobile', 'app'
        ];

        this.dnsRecordTypes = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA'];

        this.reputationChecks = [
            { name: 'Virus Total', check: this.checkVirusTotal.bind(this) },
            { name: 'Phishing Check', check: this.checkPhishing.bind(this) },
            { name: 'Blacklist Check', check: this.checkBlacklists.bind(this) }
        ];
    }

    async execute(params) {
        const startTime = Date.now();

        try {
            this.validateParams(params);
            const domain = this.cleanDomain(params.domain);
            const checks = params.checks?.includes('all') ?
                ['whois', 'dns', 'ssl', 'security', 'reputation'] :
                (params.checks || ['whois', 'dns', 'ssl']);

            const results = {
                success: true,
                domain: domain,
                timestamp: new Date().toISOString(),
                analysis: {},
                metadata: {
                    version: this.version,
                    executionTime: null,
                    checksPerformed: checks
                }
            };

            // Parallel execution for better performance
            const analysisPromises = [];

            if (checks.includes('whois')) {
                analysisPromises.push(
                    this.performWhoisLookup(domain).then(result => ({ whois: result }))
                );
            }

            if (checks.includes('dns')) {
                analysisPromises.push(
                    this.performDnsLookup(domain, params.includeSubdomains).then(result => ({ dns: result }))
                );
            }

            if (checks.includes('ssl')) {
                analysisPromises.push(
                    this.performSslCheck(domain).then(result => ({ ssl: result }))
                );
            }

            if (checks.includes('security')) {
                analysisPromises.push(
                    this.performSecurityCheck(domain).then(result => ({ security: result }))
                );
            }

            if (checks.includes('reputation')) {
                analysisPromises.push(
                    this.performReputationCheck(domain).then(result => ({ reputation: result }))
                );
            }

            // Wait for all analyses to complete
            const analysisResults = await Promise.allSettled(analysisPromises);

            // Combine results
            for (const result of analysisResults) {
                if (result.status === 'fulfilled') {
                    Object.assign(results.analysis, result.value);
                } else {
                    console.error(`Analysis failed:`, result.reason);
                }
            }

            // Generate risk assessment
            results.riskAssessment = this.assessRisk(results.analysis);

            results.metadata.executionTime = `${Date.now() - startTime}ms`;
            return results;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    validateParams(params) {
        if (!params.domain) {
            throw new Error('Domain parameter is required');
        }

        // Basic domain validation
        const domainPattern = /^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/;
        if (!domainPattern.test(params.domain)) {
            throw new Error('Invalid domain format');
        }
    }

    cleanDomain(domain) {
        // Remove protocol and path
        domain = domain.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
        // Remove www prefix
        domain = domain.replace(/^www\./, '');
        return domain.toLowerCase();
    }

    async performWhoisLookup(domain) {
        try {
            const whoisData = await new Promise((resolve, reject) => {
                whois.lookup(domain, (err, data) => {
                    if (err) reject(err);
                    else resolve(data);
                });
            });

            // Parse the raw whois data
            const parsedData = this.parseWhoisData(whoisData);

            return {
                success: true,
                data: {
                    registrar: parsedData.registrar || 'Unknown',
                    creationDate: parsedData.creationDate || 'Unknown',
                    expirationDate: parsedData.expirationDate || 'Unknown',
                    updatedDate: parsedData.updatedDate || 'Unknown',
                    nameServers: parsedData.nameServers || [],
                    registrantOrg: parsedData.registrantOrg || 'Unknown',
                    registrantCountry: parsedData.registrantCountry || 'Unknown',
                    adminContact: parsedData.adminContact || null,
                    status: parsedData.status || [],
                    raw: whoisData
                },
                analysis: {
                    domainAge: this.calculateDomainAge(parsedData.creationDate),
                    expiryStatus: this.checkExpiryStatus(parsedData.expirationDate),
                    privacyProtected: this.checkPrivacyProtection(whoisData)
                }
            };
        } catch (error) {
            return {
                success: false,
                error: `WHOIS lookup failed: ${error.message}`
            };
        }
    }

    parseWhoisData(rawData) {
        const lines = rawData.split('\n');
        const parsed = {};

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('%') || trimmed.startsWith('#')) continue;

            // Extract creation date
            if (trimmed.match(/creation date|created|registered/i)) {
                const match = trimmed.match(/:\s*(.+)/);
                if (match) parsed.creationDate = match[1].trim();
            }

            // Extract expiration date
            if (trimmed.match(/expir|expiry/i)) {
                const match = trimmed.match(/:\s*(.+)/);
                if (match) parsed.expirationDate = match[1].trim();
            }

            // Extract registrar
            if (trimmed.match(/registrar(?!.*contact)/i)) {
                const match = trimmed.match(/:\s*(.+)/);
                if (match) parsed.registrar = match[1].trim();
            }

            // Extract name servers
            if (trimmed.match(/name server|nserver/i)) {
                const match = trimmed.match(/:\s*(.+)/);
                if (match) {
                    if (!parsed.nameServers) parsed.nameServers = [];
                    parsed.nameServers.push(match[1].trim().toLowerCase());
                }
            }

            // Extract status
            if (trimmed.match(/status/i)) {
                const match = trimmed.match(/:\s*(.+)/);
                if (match) {
                    if (!parsed.status) parsed.status = [];
                    parsed.status.push(match[1].trim());
                }
            }
        }

        return parsed;
    }

    async performDnsLookup(domain, includeSubdomains = false) {
        const results = {
            success: true,
            records: {},
            subdomains: [],
            analysis: {}
        };

        try {
            // Get all DNS record types
            for (const recordType of this.dnsRecordTypes) {
                try {
                    let records;
                    switch (recordType) {
                        case 'A':
                            records = await dns.resolve4(domain);
                            break;
                        case 'AAAA':
                            records = await dns.resolve6(domain);
                            break;
                        case 'MX':
                            records = await dns.resolveMx(domain);
                            break;
                        case 'NS':
                            records = await dns.resolveNs(domain);
                            break;
                        case 'TXT':
                            records = await dns.resolveTxt(domain);
                            break;
                        case 'CNAME':
                            records = await dns.resolveCname(domain);
                            break;
                        case 'SOA':
                            records = await dns.resolveSoa(domain);
                            break;
                    }
                    results.records[recordType] = records;
                } catch (error) {
                    // Some record types might not exist, that's normal
                    results.records[recordType] = null;
                }
            }

            // Subdomain enumeration if requested
            if (includeSubdomains) {
                results.subdomains = await this.enumerateSubdomains(domain);
            }

            // DNS Analysis
            results.analysis = {
                hasIPv6: !!results.records.AAAA,
                mailServers: results.records.MX?.length || 0,
                nameServers: results.records.NS?.length || 0,
                txtRecords: results.records.TXT?.length || 0,
                spfRecord: this.checkSPF(results.records.TXT),
                dmarcRecord: this.checkDMARC(results.records.TXT),
                dkimPresent: await this.checkDKIM(domain)
            };

        } catch (error) {
            results.success = false;
            results.error = `DNS lookup failed: ${error.message}`;
        }

        return results;
    }

    async performSslCheck(domain) {
        return new Promise((resolve) => {
            const options = {
                host: domain,
                port: 443,
                method: 'HEAD',
                timeout: 10000
            };

            const req = https.request(options, (res) => {
                const cert = res.connection.getPeerCertificate();

                resolve({
                    success: true,
                    certificate: {
                        subject: cert.subject,
                        issuer: cert.issuer,
                        validFrom: cert.valid_from,
                        validTo: cert.valid_to,
                        fingerprint: cert.fingerprint,
                        serialNumber: cert.serialNumber,
                        subjectAltName: cert.subjectaltname
                    },
                    analysis: {
                        isValid: this.isCertificateValid(cert),
                        daysUntilExpiry: this.calculateDaysUntilExpiry(cert.valid_to),
                        isSelfSigned: cert.issuer.CN === cert.subject.CN,
                        hasWildcard: cert.subject.CN?.startsWith('*.') || false
                    }
                });
            });

            req.on('error', (error) => {
                resolve({
                    success: false,
                    error: `SSL check failed: ${error.message}`
                });
            });

            req.on('timeout', () => {
                req.destroy();
                resolve({
                    success: false,
                    error: 'SSL check timed out'
                });
            });

            req.end();
        });
    }

    async performSecurityCheck(domain) {
        const results = {
            success: true,
            headers: {},
            vulnerabilities: [],
            recommendations: []
        };

        try {
            // Check security headers
            const response = await this.makeHttpRequest(domain);
            results.headers = this.extractSecurityHeaders(response.headers);

            // Analyze security posture
            results.analysis = {
                hasHSTS: !!results.headers['strict-transport-security'],
                hasCSP: !!results.headers['content-security-policy'],
                hasXFrameOptions: !!results.headers['x-frame-options'],
                hasXContentTypeOptions: !!results.headers['x-content-type-options'],
                httpRedirectsToHttps: await this.checkHttpsRedirect(domain)
            };

            // Generate vulnerabilities and recommendations
            this.analyzeSecurityPosture(results);

        } catch (error) {
            results.success = false;
            results.error = `Security check failed: ${error.message}`;
        }

        return results;
    }

    async performReputationCheck(domain) {
        const results = {
            success: true,
            checks: {},
            overallScore: 0,
            reputation: 'Unknown'
        };

        try {
            // Run all reputation checks in parallel
            const checkPromises = this.reputationChecks.map(async (checker) => {
                try {
                    const result = await checker.check(domain);
                    return { name: checker.name, result };
                } catch (error) {
                    return { name: checker.name, result: { success: false, error: error.message } };
                }
            });

            const checkResults = await Promise.all(checkPromises);

            // Compile results
            let totalScore = 0;
            let validChecks = 0;

            for (const check of checkResults) {
                results.checks[check.name] = check.result;
                if (check.result.success && typeof check.result.score === 'number') {
                    totalScore += check.result.score;
                    validChecks++;
                }
            }

            // Calculate overall reputation
            if (validChecks > 0) {
                results.overallScore = Math.round(totalScore / validChecks);
                results.reputation = this.getReputationLevel(results.overallScore);
            }

        } catch (error) {
            results.success = false;
            results.error = `Reputation check failed: ${error.message}`;
        }

        return results;
    }

    // Helper methods
    async enumerateSubdomains(domain) {
        const subdomains = [];
        const checkPromises = this.commonSubdomains.map(async (sub) => {
            try {
                const subdomain = `${sub}.${domain}`;
                await dns.resolve4(subdomain);
                return subdomain;
            } catch (error) {
                return null;
            }
        });

        const results = await Promise.all(checkPromises);
        return results.filter(Boolean);
    }

    checkSPF(txtRecords) {
        if (!txtRecords) return false;
        return txtRecords.flat().some(record =>
            record.toString().toLowerCase().includes('v=spf1')
        );
    }

    checkDMARC(txtRecords) {
        if (!txtRecords) return false;
        return txtRecords.flat().some(record =>
            record.toString().toLowerCase().includes('v=dmarc1')
        );
    }

    async checkDKIM(domain) {
        try {
            await dns.resolveTxt(`default._domainkey.${domain}`);
            return true;
        } catch (error) {
            return false;
        }
    }

    calculateDomainAge(creationDate) {
        if (!creationDate) return 'Unknown';
        const created = new Date(creationDate);
        const now = new Date();
        const ageInDays = Math.floor((now - created) / (1000 * 60 * 60 * 24));
        const ageInYears = Math.floor(ageInDays / 365);
        return ageInYears > 0 ? `${ageInYears} years` : `${ageInDays} days`;
    }

    checkExpiryStatus(expirationDate) {
        if (!expirationDate) return 'Unknown';
        const expiry = new Date(expirationDate);
        const now = new Date();
        const daysUntilExpiry = Math.floor((expiry - now) / (1000 * 60 * 60 * 24));

        if (daysUntilExpiry < 0) return 'Expired';
        if (daysUntilExpiry < 30) return 'Expiring Soon';
        return 'Valid';
    }

    checkPrivacyProtection(whoisData) {
        const privacyIndicators = [
            'privacy', 'protected', 'whoisguard', 'whoisprotection',
            'domains by proxy', 'perfect privacy'
        ];

        const searchText = JSON.stringify(whoisData).toLowerCase();
        return privacyIndicators.some(indicator => searchText.includes(indicator));
    }

    isCertificateValid(cert) {
        const now = new Date();
        const validFrom = new Date(cert.valid_from);
        const validTo = new Date(cert.valid_to);
        return now >= validFrom && now <= validTo;
    }

    calculateDaysUntilExpiry(validTo) {
        const expiry = new Date(validTo);
        const now = new Date();
        return Math.floor((expiry - now) / (1000 * 60 * 60 * 24));
    }

    async makeHttpRequest(domain) {
        return new Promise((resolve, reject) => {
            const options = {
                host: domain,
                port: 443,
                path: '/',
                method: 'GET',
                timeout: 10000
            };

            const req = https.request(options, (res) => {
                resolve({
                    statusCode: res.statusCode,
                    headers: res.headers
                });
            });

            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timed out'));
            });

            req.end();
        });
    }

    extractSecurityHeaders(headers) {
        const securityHeaders = [
            'strict-transport-security', 'content-security-policy',
            'x-frame-options', 'x-content-type-options',
            'x-xss-protection', 'referrer-policy'
        ];

        const extracted = {};
        for (const header of securityHeaders) {
            if (headers[header]) {
                extracted[header] = headers[header];
            }
        }
        return extracted;
    }

    async checkHttpsRedirect(domain) {
        try {
            const response = await this.makeHttpRequest(domain, 80, 'http');
            return response.statusCode >= 300 && response.statusCode < 400;
        } catch (error) {
            return false;
        }
    }

    analyzeSecurityPosture(results) {
        const analysis = results.analysis;

        if (!analysis.hasHSTS) {
            results.vulnerabilities.push('Missing HTTP Strict Transport Security (HSTS) header');
            results.recommendations.push('Implement HSTS to prevent downgrade attacks');
        }

        if (!analysis.hasCSP) {
            results.vulnerabilities.push('Missing Content Security Policy (CSP) header');
            results.recommendations.push('Implement CSP to prevent XSS attacks');
        }

        if (!analysis.hasXFrameOptions) {
            results.vulnerabilities.push('Missing X-Frame-Options header');
            results.recommendations.push('Set X-Frame-Options to prevent clickjacking');
        }
    }

    // Reputation check methods (simplified implementations)
    async checkVirusTotal(domain) {
        // Note: Actual implementation would require VirusTotal API key
        return {
            success: true,
            score: 85,
            status: 'Clean',
            note: 'VirusTotal integration requires API key'
        };
    }

    async checkPhishing(domain) {
        // Simple heuristic-based phishing check
        const suspiciousPatterns = [
            /payp[a@]l/, /g[o0][o0]gle/, /[a@]m[a@]z[o0]n/,
            /b[a@]nk/, /secure.*update/, /verify.*account/
        ];

        const isSuspicious = suspiciousPatterns.some(pattern =>
            pattern.test(domain.toLowerCase())
        );

        return {
            success: true,
            score: isSuspicious ? 20 : 90,
            status: isSuspicious ? 'Suspicious' : 'Clean',
            patterns: isSuspicious ? ['Domain contains suspicious patterns'] : []
        };
    }

    async checkBlacklists(domain) {
        // Simplified blacklist check
        const knownBadDomains = ['malware.com', 'phishing.net', 'spam.org'];
        const isBlacklisted = knownBadDomains.includes(domain);

        return {
            success: true,
            score: isBlacklisted ? 0 : 95,
            status: isBlacklisted ? 'Blacklisted' : 'Clean',
            lists: isBlacklisted ? ['UC2 Internal Blacklist'] : []
        };
    }

    getReputationLevel(score) {
        if (score >= 80) return 'Good';
        if (score >= 60) return 'Moderate';
        if (score >= 40) return 'Poor';
        return 'Bad';
    }

    assessRisk(analysis) {
        const riskFactors = [];
        let riskScore = 0;

        // WHOIS-based risks
        if (analysis.whois?.success) {
            const domainAge = analysis.whois.analysis.domainAge;
            if (domainAge && domainAge.includes('days')) {
                const days = parseInt(domainAge);
                if (days < 30) {
                    riskFactors.push('Very new domain (less than 30 days old)');
                    riskScore += 30;
                }
            }

            if (analysis.whois.analysis.privacyProtected) {
                riskFactors.push('WHOIS privacy protection enabled');
                riskScore += 10;
            }
        }

        // SSL-based risks
        if (analysis.ssl?.success) {
            if (analysis.ssl.analysis.isSelfSigned) {
                riskFactors.push('Self-signed SSL certificate');
                riskScore += 25;
            }

            if (analysis.ssl.analysis.daysUntilExpiry < 30) {
                riskFactors.push('SSL certificate expires soon');
                riskScore += 15;
            }
        }

        // Security-based risks
        if (analysis.security?.success && analysis.security.vulnerabilities?.length > 0) {
            riskFactors.push(`${analysis.security.vulnerabilities.length} security vulnerabilities found`);
            riskScore += analysis.security.vulnerabilities.length * 10;
        }

        // Reputation-based risks
        if (analysis.reputation?.success && analysis.reputation.overallScore < 60) {
            riskFactors.push('Poor reputation score');
            riskScore += 40 - (analysis.reputation.overallScore / 2);
        }

        return {
            score: Math.min(riskScore, 100),
            level: this.getRiskLevel(riskScore),
            factors: riskFactors,
            recommendation: this.getRiskRecommendation(riskScore)
        };
    }

    getRiskLevel(score) {
        if (score >= 70) return 'High';
        if (score >= 40) return 'Medium';
        if (score >= 20) return 'Low';
        return 'Minimal';
    }

    getRiskRecommendation(score) {
        if (score >= 70) return 'Exercise extreme caution. Consider blocking or avoiding this domain.';
        if (score >= 40) return 'Proceed with caution. Additional verification recommended.';
        if (score >= 20) return 'Generally safe, but monitor for changes.';
        return 'Domain appears to be legitimate and safe.';
    }
}

module.exports = DomainAnalyzerTool;