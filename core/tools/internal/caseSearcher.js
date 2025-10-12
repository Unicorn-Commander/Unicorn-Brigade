const axios = require('axios');

class CaseSearcherTool {
    constructor() {
        this.name = 'caseSearcher';
        this.version = '1.0.0';
        this.description = 'Legal case database search and precedent analysis';
        this.category = 'Legal Research';
        this.author = 'UC2 System';
        this.tags = ['legal', 'cases', 'precedent', 'research', 'law'];

        this.schema = {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'Search query for legal cases',
                    minLength: 3,
                    maxLength: 500
                },
                jurisdiction: {
                    type: 'string',
                    description: 'Legal jurisdiction to search',
                    enum: [
                        'federal',
                        'supreme-court',
                        'appellate',
                        'district',
                        'state',
                        'california',
                        'new-york',
                        'texas',
                        'florida',
                        'international',
                        'all'
                    ],
                    default: 'federal'
                },
                searchType: {
                    type: 'string',
                    description: 'Type of legal search to perform',
                    enum: [
                        'cases',           // Case law search
                        'statutes',        // Statutory law
                        'regulations',     // Federal/state regulations
                        'opinions',        // Court opinions
                        'precedents',      // Similar precedents
                        'citations',       // Citation analysis
                        'comprehensive'    // All types
                    ],
                    default: 'cases'
                },
                dateRange: {
                    type: 'object',
                    properties: {
                        start: {
                            type: 'string',
                            description: 'Start date (YYYY-MM-DD)',
                            pattern: '^\\d{4}-\\d{2}-\\d{2}$'
                        },
                        end: {
                            type: 'string',
                            description: 'End date (YYYY-MM-DD)',
                            pattern: '^\\d{4}-\\d{2}-\\d{2}$'
                        }
                    }
                },
                court: {
                    type: 'string',
                    description: 'Specific court to search'
                },
                limit: {
                    type: 'number',
                    description: 'Maximum number of results to return',
                    minimum: 1,
                    maximum: 100,
                    default: 20
                },
                relevanceThreshold: {
                    type: 'number',
                    description: 'Minimum relevance score (0.0-1.0)',
                    minimum: 0.0,
                    maximum: 1.0,
                    default: 0.6
                },
                includeSummary: {
                    type: 'boolean',
                    description: 'Include AI-generated case summaries',
                    default: true
                },
                analyzeRelevance: {
                    type: 'boolean',
                    description: 'Analyze legal precedent relevance',
                    default: true
                }
            },
            required: ['query']
        };

        // Mock legal databases (in real implementation, would connect to actual APIs)
        this.databases = {
            'caselaw-access-project': {
                name: 'Caselaw Access Project',
                url: 'https://api.case.law/v1/',
                apiKey: process.env.CAP_API_KEY,
                enabled: !!process.env.CAP_API_KEY
            },
            'courtlistener': {
                name: 'CourtListener',
                url: 'https://www.courtlistener.com/api/rest/v3/',
                apiKey: process.env.COURTLISTENER_API_KEY,
                enabled: !!process.env.COURTLISTENER_API_KEY
            },
            'justia': {
                name: 'Justia',
                url: 'https://law.justia.com/api/',
                enabled: true // Free tier
            },
            'mock': {
                name: 'Mock Legal Database',
                enabled: true // For demonstration
            }
        };

        // Legal citation patterns
        this.citationPatterns = {
            federalReporter: /\d+\s+F\.\d+\s+\d+/g,
            supremeCourt: /\d+\s+U\.S\.\s+\d+/g,
            stateReporter: /\d+\s+[A-Z][a-z]*\.?\s*\d*d?\s+\d+/g,
            statute: /\d+\s+U\.S\.C\.?\s*§?\s*\d+/g,
            cfr: /\d+\s+C\.F\.R\.?\s*§?\s*\d+/g
        };

        // Legal areas for categorization
        this.legalAreas = [
            'constitutional', 'criminal', 'civil rights', 'contract', 'tort',
            'employment', 'intellectual property', 'corporate', 'tax',
            'environmental', 'healthcare', 'immigration', 'family',
            'bankruptcy', 'securities', 'antitrust', 'administrative'
        ];

        // Cache for frequent searches
        this.cache = new Map();
        this.cacheTimeout = 15 * 60 * 1000; // 15 minutes
    }

    async execute(params) {
        const startTime = Date.now();

        try {
            this.validateParams(params);

            const result = {
                success: true,
                query: params.query,
                searchType: params.searchType || 'cases',
                jurisdiction: params.jurisdiction || 'federal',
                timestamp: new Date().toISOString(),
                cases: [],
                analysis: {},
                metadata: {
                    version: this.version,
                    sources: [],
                    totalResults: 0,
                    searchTime: null,
                    cached: false
                }
            };

            // Check cache
            const cacheKey = this.generateCacheKey(params);
            const cached = this.getFromCache(cacheKey);
            if (cached) {
                result.cases = cached.cases;
                result.analysis = cached.analysis;
                result.metadata = { ...result.metadata, ...cached.metadata, cached: true };
                result.metadata.searchTime = `${Date.now() - startTime}ms`;
                return result;
            }

            // Perform search based on type
            switch (params.searchType || 'cases') {
                case 'cases':
                    result.cases = await this.searchCases(params);
                    break;
                case 'statutes':
                    result.cases = await this.searchStatutes(params);
                    break;
                case 'regulations':
                    result.cases = await this.searchRegulations(params);
                    break;
                case 'opinions':
                    result.cases = await this.searchOpinions(params);
                    break;
                case 'precedents':
                    result.cases = await this.searchPrecedents(params);
                    break;
                case 'citations':
                    result.cases = await this.searchCitations(params);
                    break;
                case 'comprehensive':
                    result.cases = await this.comprehensiveSearch(params);
                    break;
            }

            // Filter by relevance threshold
            result.cases = result.cases.filter(c =>
                c.relevanceScore >= (params.relevanceThreshold || 0.6)
            );

            // Sort by relevance
            result.cases.sort((a, b) => b.relevanceScore - a.relevanceScore);

            // Limit results
            result.cases = result.cases.slice(0, params.limit || 20);

            // Generate analysis
            if (params.analyzeRelevance) {
                result.analysis = this.analyzeResults(result.cases, params.query);
            }

            // Generate summaries
            if (params.includeSummary) {
                result.cases = await this.addCaseSummaries(result.cases);
            }

            result.metadata.totalResults = result.cases.length;
            result.metadata.searchTime = `${Date.now() - startTime}ms`;

            // Cache the result
            this.setCache(cacheKey, {
                cases: result.cases,
                analysis: result.analysis,
                metadata: result.metadata
            });

            return result;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                query: params.query,
                searchTime: `${Date.now() - startTime}ms`
            };
        }
    }

    validateParams(params) {
        if (!params.query || typeof params.query !== 'string') {
            throw new Error('Query parameter is required and must be a string');
        }

        if (params.query.length < 3) {
            throw new Error('Query must be at least 3 characters long');
        }

        if (params.query.length > 500) {
            throw new Error('Query must be less than 500 characters');
        }
    }

    async searchCases(params) {
        // Try multiple sources for better coverage
        const sources = [];

        // Try Mock Database (always available for demonstration)
        try {
            const mockResults = await this.searchMockDatabase(params);
            sources.push(...mockResults);
        } catch (error) {
            console.warn('Mock database search failed:', error.message);
        }

        // Try Caselaw Access Project if available
        if (this.databases['caselaw-access-project'].enabled) {
            try {
                const capResults = await this.searchCaseLawAccessProject(params);
                sources.push(...capResults);
            } catch (error) {
                console.warn('CAP search failed:', error.message);
            }
        }

        // Try CourtListener if available
        if (this.databases['courtlistener'].enabled) {
            try {
                const clResults = await this.searchCourtListener(params);
                sources.push(...clResults);
            } catch (error) {
                console.warn('CourtListener search failed:', error.message);
            }
        }

        // Deduplicate and enhance results
        return this.processAndDeduplicateResults(sources, params);
    }

    async searchMockDatabase(params) {
        // Mock legal cases for demonstration
        const mockCases = [
            {
                id: 'mock-001',
                title: 'Brown v. Board of Education',
                citation: '347 U.S. 483 (1954)',
                court: 'Supreme Court of the United States',
                year: 1954,
                jurisdiction: 'federal',
                summary: 'Landmark civil rights case that declared state laws establishing separate public schools for black and white students to be unconstitutional.',
                keyPoints: [
                    'Overturned Plessy v. Ferguson doctrine of "separate but equal"',
                    'Established that segregated schools are inherently unequal',
                    'Applied Equal Protection Clause to education'
                ],
                relevanceScore: this.calculateMockRelevance(params.query, 'education civil rights constitutional equal protection'),
                legalArea: 'civil rights',
                precedentialValue: 'binding',
                status: 'final'
            },
            {
                id: 'mock-002',
                title: 'Miranda v. Arizona',
                citation: '384 U.S. 436 (1966)',
                court: 'Supreme Court of the United States',
                year: 1966,
                jurisdiction: 'federal',
                summary: 'Established the requirement that suspects be informed of their rights before custodial interrogation.',
                keyPoints: [
                    'Created the Miranda warning requirement',
                    'Protected Fifth Amendment rights against self-incrimination',
                    'Applied to custodial interrogations'
                ],
                relevanceScore: this.calculateMockRelevance(params.query, 'criminal rights interrogation fifth amendment constitutional'),
                legalArea: 'criminal',
                precedentialValue: 'binding',
                status: 'final'
            },
            {
                id: 'mock-003',
                title: 'Roe v. Wade',
                citation: '410 U.S. 113 (1973)',
                court: 'Supreme Court of the United States',
                year: 1973,
                jurisdiction: 'federal',
                summary: 'Established constitutional right to abortion under the right to privacy.',
                keyPoints: [
                    'Recognized constitutional right to privacy in reproductive decisions',
                    'Established trimester framework for abortion regulation',
                    'Applied Due Process Clause of Fourteenth Amendment'
                ],
                relevanceScore: this.calculateMockRelevance(params.query, 'privacy constitutional reproductive rights due process'),
                legalArea: 'constitutional',
                precedentialValue: 'overruled',
                status: 'overruled',
                overruledBy: 'Dobbs v. Jackson Women\'s Health Organization (2022)'
            },
            {
                id: 'mock-004',
                title: 'Citizens United v. FEC',
                citation: '558 U.S. 310 (2010)',
                court: 'Supreme Court of the United States',
                year: 2010,
                jurisdiction: 'federal',
                summary: 'Held that political spending by corporations and unions is a form of protected speech under the First Amendment.',
                keyPoints: [
                    'Extended First Amendment protection to corporate political speech',
                    'Overturned portions of McCain-Feingold Act',
                    'Distinguished between direct contributions and independent expenditures'
                ],
                relevanceScore: this.calculateMockRelevance(params.query, 'first amendment corporate speech political campaign finance'),
                legalArea: 'constitutional',
                precedentialValue: 'binding',
                status: 'final'
            },
            {
                id: 'mock-005',
                title: 'Google v. Oracle America',
                citation: '141 S. Ct. 1183 (2021)',
                court: 'Supreme Court of the United States',
                year: 2021,
                jurisdiction: 'federal',
                summary: 'Ruled that Google\'s use of Java API code was fair use under copyright law.',
                keyPoints: [
                    'Applied fair use doctrine to software APIs',
                    'Considered transformative nature of Google\'s use',
                    'Balanced copyright protection with innovation'
                ],
                relevanceScore: this.calculateMockRelevance(params.query, 'copyright fair use software api intellectual property technology'),
                legalArea: 'intellectual property',
                precedentialValue: 'binding',
                status: 'final'
            }
        ];

        // Filter by jurisdiction
        let filtered = mockCases;
        if (params.jurisdiction && params.jurisdiction !== 'all') {
            filtered = mockCases.filter(c =>
                c.jurisdiction === params.jurisdiction || params.jurisdiction === 'federal'
            );
        }

        // Filter by date range
        if (params.dateRange) {
            const startYear = params.dateRange.start ? new Date(params.dateRange.start).getFullYear() : 0;
            const endYear = params.dateRange.end ? new Date(params.dateRange.end).getFullYear() : 9999;

            filtered = filtered.filter(c => c.year >= startYear && c.year <= endYear);
        }

        // Filter by court
        if (params.court) {
            filtered = filtered.filter(c =>
                c.court.toLowerCase().includes(params.court.toLowerCase())
            );
        }

        return filtered;
    }

    calculateMockRelevance(query, content) {
        const queryWords = query.toLowerCase().split(/\s+/);
        const contentWords = content.toLowerCase().split(/\s+/);

        let matches = 0;
        for (const word of queryWords) {
            if (contentWords.some(cw => cw.includes(word) || word.includes(cw))) {
                matches++;
            }
        }

        const baseScore = matches / queryWords.length;
        const randomFactor = 0.8 + (Math.random() * 0.4); // 0.8 to 1.2
        return Math.min(1.0, baseScore * randomFactor);
    }

    async searchCaseLawAccessProject(params) {
        // Placeholder for actual CAP API integration
        return [];
    }

    async searchCourtListener(params) {
        // Placeholder for actual CourtListener API integration
        return [];
    }

    async searchStatutes(params) {
        // Mock statutory search
        const statutes = [
            {
                id: 'statute-001',
                title: 'Civil Rights Act of 1964',
                citation: '42 U.S.C. § 2000e',
                jurisdiction: 'federal',
                type: 'statute',
                summary: 'Prohibits employment discrimination based on race, color, religion, sex, or national origin.',
                relevanceScore: this.calculateMockRelevance(params.query, 'employment discrimination civil rights'),
                enacted: '1964-07-02',
                status: 'active'
            },
            {
                id: 'statute-002',
                title: 'Americans with Disabilities Act',
                citation: '42 U.S.C. § 12101',
                jurisdiction: 'federal',
                type: 'statute',
                summary: 'Prohibits discrimination against individuals with disabilities in employment, public accommodations, and other areas.',
                relevanceScore: this.calculateMockRelevance(params.query, 'disability discrimination accessibility employment'),
                enacted: '1990-07-26',
                status: 'active'
            }
        ];

        return statutes.filter(s => s.relevanceScore >= (params.relevanceThreshold || 0.6));
    }

    async searchRegulations(params) {
        // Mock regulatory search
        const regulations = [
            {
                id: 'reg-001',
                title: 'GDPR Compliance Regulations',
                citation: 'Regulation (EU) 2016/679',
                jurisdiction: 'international',
                type: 'regulation',
                summary: 'General Data Protection Regulation governing data privacy in the European Union.',
                relevanceScore: this.calculateMockRelevance(params.query, 'privacy data protection gdpr eu'),
                effectiveDate: '2018-05-25',
                status: 'active'
            }
        ];

        return regulations.filter(r => r.relevanceScore >= (params.relevanceThreshold || 0.6));
    }

    async searchOpinions(params) {
        // Use same mock data as cases but focus on opinions
        return this.searchMockDatabase(params);
    }

    async searchPrecedents(params) {
        const cases = await this.searchMockDatabase(params);
        // Add precedential analysis
        return cases.map(c => ({
            ...c,
            precedentialAnalysis: {
                citedBy: Math.floor(Math.random() * 500) + 10,
                distinguishedBy: Math.floor(Math.random() * 50),
                followedBy: Math.floor(Math.random() * 200) + 20,
                jurisdictionalWeight: this.calculateJurisdictionalWeight(c.court),
                ageWeight: this.calculateAgeWeight(c.year)
            }
        }));
    }

    async searchCitations(params) {
        // Extract citations from query and search for them
        const citations = this.extractCitations(params.query);
        const results = [];

        for (const citation of citations) {
            // Mock citation lookup
            results.push({
                id: `citation-${citation.replace(/\s+/g, '-')}`,
                originalCitation: citation,
                title: `Case for ${citation}`,
                type: 'citation-lookup',
                relevanceScore: 1.0,
                found: Math.random() > 0.3 // 70% chance of finding
            });
        }

        return results;
    }

    async comprehensiveSearch(params) {
        const [cases, statutes, regulations] = await Promise.all([
            this.searchCases(params),
            this.searchStatutes(params),
            this.searchRegulations(params)
        ]);

        return [...cases, ...statutes, ...regulations];
    }

    processAndDeduplicateResults(sources, params) {
        const seen = new Set();
        const unique = [];

        for (const result of sources) {
            const key = `${result.citation || result.title}-${result.year || ''}`;
            if (!seen.has(key)) {
                seen.add(key);
                unique.push(result);
            }
        }

        return unique;
    }

    async addCaseSummaries(cases) {
        // In real implementation, would use AI to generate summaries
        return cases.map(c => ({
            ...c,
            aiSummary: c.summary ? {
                brief: c.summary.substring(0, 200) + '...',
                keyHoldings: c.keyPoints || [],
                legalPrinciples: this.extractLegalPrinciples(c.summary),
                practicalImplications: this.generatePracticalImplications(c)
            } : null
        }));
    }

    analyzeResults(cases, query) {
        const analysis = {
            totalCases: cases.length,
            jurisdictions: this.analyzeJurisdictions(cases),
            timeDistribution: this.analyzeTimeDistribution(cases),
            legalAreas: this.analyzeLegalAreas(cases),
            precedentialValue: this.analyzePrecedentialValue(cases),
            relevanceDistribution: this.analyzeRelevanceDistribution(cases),
            keyThemes: this.extractKeyThemes(cases, query),
            recommendations: this.generateRecommendations(cases, query)
        };

        return analysis;
    }

    analyzeJurisdictions(cases) {
        const jurisdictions = {};
        cases.forEach(c => {
            jurisdictions[c.jurisdiction] = (jurisdictions[c.jurisdiction] || 0) + 1;
        });
        return jurisdictions;
    }

    analyzeTimeDistribution(cases) {
        const decades = {};
        cases.forEach(c => {
            if (c.year) {
                const decade = Math.floor(c.year / 10) * 10;
                decades[`${decade}s`] = (decades[`${decade}s`] || 0) + 1;
            }
        });
        return decades;
    }

    analyzeLegalAreas(cases) {
        const areas = {};
        cases.forEach(c => {
            if (c.legalArea) {
                areas[c.legalArea] = (areas[c.legalArea] || 0) + 1;
            }
        });
        return areas;
    }

    analyzePrecedentialValue(cases) {
        const values = {};
        cases.forEach(c => {
            const value = c.precedentialValue || 'unknown';
            values[value] = (values[value] || 0) + 1;
        });
        return values;
    }

    analyzeRelevanceDistribution(cases) {
        const distribution = {
            high: cases.filter(c => c.relevanceScore >= 0.8).length,
            medium: cases.filter(c => c.relevanceScore >= 0.6 && c.relevanceScore < 0.8).length,
            low: cases.filter(c => c.relevanceScore < 0.6).length
        };
        return distribution;
    }

    extractKeyThemes(cases, query) {
        const themes = new Map();
        const queryWords = query.toLowerCase().split(/\s+/);

        cases.forEach(c => {
            const text = `${c.title} ${c.summary || ''} ${(c.keyPoints || []).join(' ')}`.toLowerCase();
            queryWords.forEach(word => {
                if (text.includes(word) && word.length > 3) {
                    themes.set(word, (themes.get(word) || 0) + 1);
                }
            });
        });

        return Array.from(themes.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([theme, count]) => ({ theme, frequency: count }));
    }

    generateRecommendations(cases, query) {
        const recommendations = [];

        if (cases.length === 0) {
            recommendations.push({
                type: 'search_strategy',
                message: 'No results found. Try broadening your search terms or checking spelling.',
                priority: 'high'
            });
        } else if (cases.length < 5) {
            recommendations.push({
                type: 'search_strategy',
                message: 'Limited results found. Consider expanding search to additional jurisdictions or time periods.',
                priority: 'medium'
            });
        }

        const highRelevance = cases.filter(c => c.relevanceScore >= 0.9);
        if (highRelevance.length > 0) {
            recommendations.push({
                type: 'priority_cases',
                message: `${highRelevance.length} highly relevant cases found. Focus on these for strongest precedential value.`,
                priority: 'high',
                cases: highRelevance.slice(0, 3).map(c => c.citation)
            });
        }

        const recentCases = cases.filter(c => c.year && c.year >= new Date().getFullYear() - 5);
        if (recentCases.length > 0) {
            recommendations.push({
                type: 'recent_developments',
                message: `${recentCases.length} recent cases found. Review for latest legal developments.`,
                priority: 'medium'
            });
        }

        return recommendations;
    }

    extractCitations(text) {
        const citations = [];
        Object.entries(this.citationPatterns).forEach(([type, pattern]) => {
            const matches = text.match(pattern) || [];
            citations.push(...matches);
        });
        return [...new Set(citations)]; // Deduplicate
    }

    extractLegalPrinciples(summary) {
        // Simple keyword-based extraction (would use NLP in real implementation)
        const principles = [];
        const principleKeywords = [
            'due process', 'equal protection', 'first amendment', 'fourth amendment',
            'reasonable expectation', 'compelling interest', 'strict scrutiny',
            'intermediate scrutiny', 'rational basis', 'fundamental right'
        ];

        const text = summary.toLowerCase();
        principleKeywords.forEach(keyword => {
            if (text.includes(keyword)) {
                principles.push(keyword);
            }
        });

        return principles;
    }

    generatePracticalImplications(case_) {
        // Generate practical implications based on case type and area
        const implications = [];

        switch (case_.legalArea) {
            case 'employment':
                implications.push('Review hiring practices for compliance');
                implications.push('Update employee handbook policies');
                break;
            case 'intellectual property':
                implications.push('Evaluate IP protection strategies');
                implications.push('Review licensing agreements');
                break;
            case 'constitutional':
                implications.push('Consider impact on government actions');
                implications.push('Review policy implementation');
                break;
            default:
                implications.push('Analyze impact on current practices');
                implications.push('Consider policy adjustments');
        }

        return implications;
    }

    calculateJurisdictionalWeight(court) {
        const weights = {
            'Supreme Court of the United States': 1.0,
            'Federal Circuit': 0.8,
            'Court of Appeals': 0.7,
            'District Court': 0.5,
            'State Supreme Court': 0.6,
            'State Appellate Court': 0.4
        };

        for (const [courtType, weight] of Object.entries(weights)) {
            if (court.includes(courtType)) {
                return weight;
            }
        }

        return 0.3; // Default for unknown courts
    }

    calculateAgeWeight(year) {
        const currentYear = new Date().getFullYear();
        const age = currentYear - year;

        if (age <= 5) return 1.0;      // Very recent
        if (age <= 10) return 0.9;     // Recent
        if (age <= 20) return 0.7;     // Moderately recent
        if (age <= 50) return 0.5;     // Older
        return 0.3;                    // Very old
    }

    // Cache methods
    generateCacheKey(params) {
        return JSON.stringify({
            query: params.query,
            searchType: params.searchType,
            jurisdiction: params.jurisdiction,
            dateRange: params.dateRange,
            court: params.court,
            limit: params.limit
        });
    }

    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        this.cache.delete(key);
        return null;
    }

    setCache(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });

        // Clean old entries
        if (this.cache.size > 50) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
}

module.exports = CaseSearcherTool;