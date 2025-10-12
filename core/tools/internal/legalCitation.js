const NodeCache = require('node-cache');

class LegalCitation {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 7200 }); // 2 hour cache

        this.citationStyles = {
            'bluebook': 'The Bluebook: A Uniform System of Citation (21st ed.)',
            'alwd': 'ALWD Citation Manual (7th ed.)',
            'apa': 'American Psychological Association (7th ed.)',
            'mla': 'Modern Language Association (9th ed.)',
            'chicago': 'Chicago Manual of Style (17th ed.)'
        };

        this.jurisdictionAbbreviations = {
            'federal': {
                'US': 'United States',
                'S. Ct.': 'Supreme Court',
                'F.3d': 'Federal Reporter, Third Series',
                'F. Supp. 3d': 'Federal Supplement, Third Series',
                'F.4th': 'Federal Reporter, Fourth Series'
            },
            'state': {
                'Cal.': 'California',
                'N.Y.': 'New York',
                'Tex.': 'Texas',
                'Fla.': 'Florida',
                'Ill.': 'Illinois'
            }
        };

        this.sourceTypes = [
            'case', 'statute', 'regulation', 'law_review', 'book',
            'newspaper', 'website', 'treaty', 'constitution', 'legislative_history'
        ];

        this.mockCitationDatabase = this.initializeMockCitations();
        this.shepardizeDatabase = this.initializeShepardizeData();
    }

    async formatCitation(sourceInfo, style = 'bluebook', includeParallel = false) {
        try {
            const cacheKey = `format_${JSON.stringify(sourceInfo)}_${style}_${includeParallel}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            const sourceType = sourceInfo.type || this.detectSourceType(sourceInfo);
            let formattedCitation = '';

            switch (sourceType) {
                case 'case':
                    formattedCitation = this.formatCaseCitation(sourceInfo, style, includeParallel);
                    break;
                case 'statute':
                    formattedCitation = this.formatStatuteCitation(sourceInfo, style);
                    break;
                case 'regulation':
                    formattedCitation = this.formatRegulationCitation(sourceInfo, style);
                    break;
                case 'law_review':
                    formattedCitation = this.formatLawReviewCitation(sourceInfo, style);
                    break;
                case 'book':
                    formattedCitation = this.formatBookCitation(sourceInfo, style);
                    break;
                case 'website':
                    formattedCitation = this.formatWebCitation(sourceInfo, style);
                    break;
                default:
                    formattedCitation = this.formatGenericCitation(sourceInfo, style);
            }

            const result = {
                original_source: sourceInfo,
                citation_style: style,
                source_type: sourceType,
                formatted_citation: formattedCitation,
                parallel_citations: includeParallel ? this.getParallelCitations(sourceInfo) : null,
                citation_elements: this.extractCitationElements(sourceInfo, sourceType),
                validation: this.validateCitation(formattedCitation, sourceType, style),
                shepardizing: sourceType === 'case' ? this.getShepardInfo(sourceInfo) : null,
                formatted_at: new Date().toISOString()
            };

            this.cache.set(cacheKey, result);
            return result;

        } catch (error) {
            return {
                error: 'Citation formatting failed',
                message: error.message,
                source: sourceInfo,
                formatted_at: new Date().toISOString()
            };
        }
    }

    async generateBibliography(sources, style = 'bluebook', sortBy = 'alphabetical') {
        try {
            const bibliography = {
                style: style,
                sort_method: sortBy,
                total_sources: sources.length,
                generated_at: new Date().toISOString(),
                citations: []
            };

            // Format each source
            for (const source of sources) {
                const formatted = await this.formatCitation(source, style, false);
                bibliography.citations.push({
                    id: source.id || `source_${bibliography.citations.length + 1}`,
                    citation: formatted.formatted_citation,
                    source_type: formatted.source_type,
                    validation_status: formatted.validation.is_valid
                });
            }

            // Sort bibliography
            bibliography.citations = this.sortBibliography(bibliography.citations, sortBy);

            // Add formatting suggestions
            bibliography.formatting_notes = this.getBibliographyFormattingNotes(style);

            return bibliography;

        } catch (error) {
            return {
                error: 'Bibliography generation failed',
                message: error.message,
                generated_at: new Date().toISOString()
            };
        }
    }

    async validateCitationFormat(citation, expectedStyle = 'bluebook') {
        try {
            const validation = {
                citation_text: citation,
                expected_style: expectedStyle,
                is_valid: true,
                errors: [],
                warnings: [],
                suggestions: [],
                confidence: 0,
                validated_at: new Date().toISOString()
            };

            // Detect source type from citation
            const detectedType = this.detectSourceTypeFromCitation(citation);
            validation.detected_source_type = detectedType;

            // Run validation checks based on style and type
            const checks = this.getValidationChecks(expectedStyle, detectedType);

            for (const check of checks) {
                const result = this.runValidationCheck(citation, check);

                if (result.type === 'error') {
                    validation.errors.push(result);
                    validation.is_valid = false;
                } else if (result.type === 'warning') {
                    validation.warnings.push(result);
                } else if (result.type === 'suggestion') {
                    validation.suggestions.push(result);
                }
            }

            // Calculate confidence score
            validation.confidence = this.calculateValidationConfidence(validation);

            // Generate corrected citation if errors found
            if (!validation.is_valid) {
                validation.corrected_citation = this.generateCorrectedCitation(citation, validation.errors);
            }

            return validation;

        } catch (error) {
            return {
                error: 'Citation validation failed',
                message: error.message,
                citation: citation,
                validated_at: new Date().toISOString()
            };
        }
    }

    async shepardizeCitation(citation, analysisDepth = 'standard') {
        try {
            const cacheKey = `shepardize_${citation}_${analysisDepth}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            // Extract case information from citation
            const caseInfo = this.extractCaseInfoFromCitation(citation);

            if (!caseInfo) {
                return {
                    error: 'Unable to extract case information from citation',
                    citation: citation,
                    analyzed_at: new Date().toISOString()
                };
            }

            // Get Shepard's data (mock)
            const shepardData = this.getShepardInfo(caseInfo);

            const analysis = {
                citation: citation,
                case_information: caseInfo,
                analysis_depth: analysisDepth,
                treatment_summary: shepardData.treatment,
                citing_references: shepardData.citing_cases,
                history: shepardData.history,
                reliability_assessment: this.assessCaseReliability(shepardData),
                citation_analysis: {
                    total_citing_cases: shepardData.citing_cases.length,
                    positive_treatment: shepardData.citing_cases.filter(c => c.treatment === 'followed').length,
                    negative_treatment: shepardData.citing_cases.filter(c => c.treatment === 'criticized').length,
                    neutral_treatment: shepardData.citing_cases.filter(c => c.treatment === 'mentioned').length
                },
                research_recommendations: this.generateResearchRecommendations(shepardData),
                analyzed_at: new Date().toISOString()
            };

            // Add deep analysis if requested
            if (analysisDepth === 'comprehensive') {
                analysis.jurisdictional_analysis = this.analyzeJurisdictionalTrend(shepardData);
                analysis.temporal_analysis = this.analyzeTemporalTrends(shepardData);
                analysis.topic_analysis = this.analyzeTopicalTreatment(shepardData);
            }

            this.cache.set(cacheKey, analysis);
            return analysis;

        } catch (error) {
            return {
                error: 'Shepardizing failed',
                message: error.message,
                citation: citation,
                analyzed_at: new Date().toISOString()
            };
        }
    }

    formatCaseCitation(sourceInfo, style, includeParallel) {
        const { case_name, volume, reporter, page, court, year } = sourceInfo;

        switch (style) {
            case 'bluebook':
                let citation = `${case_name}, ${volume} ${reporter} ${page}`;
                if (court && court !== 'US') citation += ` (${court} ${year})`;
                else if (year) citation += ` (${year})`;
                return citation;

            case 'alwd':
                return `${case_name}, ${volume} ${reporter} ${page} (${court || 'US'} ${year})`;

            case 'apa':
                return `${case_name}, ${volume} ${reporter} ${page} (${court || 'US'} ${year})`;

            default:
                return `${case_name}, ${volume} ${reporter} ${page} (${year})`;
        }
    }

    formatStatuteCitation(sourceInfo, style) {
        const { title, section, year, code } = sourceInfo;

        switch (style) {
            case 'bluebook':
                return `${title} U.S.C. § ${section} (${year})`;

            case 'alwd':
                return `${title} U.S.C. § ${section} (${year})`;

            default:
                return `${title} USC § ${section} (${year})`;
        }
    }

    formatLawReviewCitation(sourceInfo, style) {
        const { author, title, volume, journal, page, year } = sourceInfo;

        switch (style) {
            case 'bluebook':
                return `${author}, ${title}, ${volume} ${journal} ${page} (${year})`;

            case 'alwd':
                return `${author}, ${title}, ${volume} ${journal} ${page} (${year})`;

            default:
                return `${author}, "${title}," ${journal} ${volume} (${year}): ${page}`;
        }
    }

    detectSourceType(sourceInfo) {
        if (sourceInfo.case_name || sourceInfo.reporter) return 'case';
        if (sourceInfo.title && (sourceInfo.section || sourceInfo.code)) return 'statute';
        if (sourceInfo.cfr || sourceInfo.federal_register) return 'regulation';
        if (sourceInfo.journal && sourceInfo.volume) return 'law_review';
        if (sourceInfo.publisher && sourceInfo.edition) return 'book';
        if (sourceInfo.url) return 'website';
        return 'unknown';
    }

    getParallelCitations(sourceInfo) {
        // Mock parallel citations
        return [
            `${sourceInfo.volume} ${sourceInfo.reporter} ${sourceInfo.page}`,
            `${sourceInfo.volume + 100} P.3d ${sourceInfo.page + 50}`,
            `${sourceInfo.volume - 10} Cal.4th ${sourceInfo.page - 20}`
        ].filter(Boolean);
    }

    extractCitationElements(sourceInfo, sourceType) {
        const elements = {};

        switch (sourceType) {
            case 'case':
                elements.case_name = sourceInfo.case_name;
                elements.volume = sourceInfo.volume;
                elements.reporter = sourceInfo.reporter;
                elements.page = sourceInfo.page;
                elements.court = sourceInfo.court;
                elements.year = sourceInfo.year;
                break;

            case 'statute':
                elements.title = sourceInfo.title;
                elements.section = sourceInfo.section;
                elements.code = sourceInfo.code;
                elements.year = sourceInfo.year;
                break;

            case 'law_review':
                elements.author = sourceInfo.author;
                elements.title = sourceInfo.title;
                elements.volume = sourceInfo.volume;
                elements.journal = sourceInfo.journal;
                elements.page = sourceInfo.page;
                elements.year = sourceInfo.year;
                break;
        }

        return elements;
    }

    validateCitation(citation, sourceType, style) {
        const validation = {
            is_valid: true,
            errors: [],
            score: 100
        };

        // Basic validation rules
        if (!citation || citation.trim().length === 0) {
            validation.is_valid = false;
            validation.errors.push('Citation cannot be empty');
            validation.score = 0;
        }

        // Style-specific validation
        if (style === 'bluebook') {
            if (sourceType === 'case' && !citation.includes(',')) {
                validation.errors.push('Case citations should include commas after case name');
                validation.score -= 20;
            }
        }

        return validation;
    }

    initializeMockCitations() {
        return [
            {
                id: 'case_001',
                type: 'case',
                case_name: 'Brown v. Board of Education',
                volume: '347',
                reporter: 'U.S.',
                page: '483',
                year: '1954',
                court: 'US'
            },
            {
                id: 'statute_001',
                type: 'statute',
                title: '42',
                section: '1983',
                code: 'U.S.C.',
                year: '2018'
            },
            {
                id: 'law_review_001',
                type: 'law_review',
                author: 'John Smith',
                title: 'The Future of Constitutional Law',
                volume: '125',
                journal: 'Harv. L. Rev.',
                page: '234',
                year: '2024'
            }
        ];
    }

    initializeShepardizeData() {
        return {
            'Brown v. Board of Education': {
                treatment: 'Good Law',
                citing_cases: [
                    {
                        case_name: 'Loving v. Virginia',
                        citation: '388 U.S. 1 (1967)',
                        treatment: 'followed',
                        year: '1967'
                    },
                    {
                        case_name: 'Swann v. Charlotte-Mecklenburg',
                        citation: '402 U.S. 1 (1971)',
                        treatment: 'followed',
                        year: '1971'
                    }
                ],
                history: [
                    {
                        case_name: 'Brown v. Board of Education',
                        citation: '347 U.S. 483 (1954)',
                        disposition: 'Original decision'
                    }
                ]
            }
        };
    }

    getShepardInfo(caseInfo) {
        const caseName = caseInfo.case_name || 'Unknown Case';
        return this.shepardizeDatabase[caseName] || {
            treatment: 'Unknown',
            citing_cases: [],
            history: []
        };
    }

    assessCaseReliability(shepardData) {
        const positiveCount = shepardData.citing_cases.filter(c => c.treatment === 'followed').length;
        const totalCount = shepardData.citing_cases.length;

        if (totalCount === 0) return 'Insufficient data';

        const positiveRatio = positiveCount / totalCount;

        if (positiveRatio > 0.8) return 'Highly reliable';
        if (positiveRatio > 0.6) return 'Generally reliable';
        if (positiveRatio > 0.4) return 'Moderately reliable';
        return 'Questionable reliability';
    }

    getToolInfo() {
        return {
            name: 'Legal Citation',
            version: '2.0.0',
            description: 'Professional legal citation formatting and validation system',
            author: 'UC2 System',
            capabilities: [
                'Multi-style citation formatting',
                'Citation validation and correction',
                'Bibliography generation',
                'Shepardizing and case analysis',
                'Parallel citation identification',
                'Source type detection',
                'Citation element extraction',
                'Reliability assessment',
                'Research recommendations'
            ],
            supported_styles: Object.keys(this.citationStyles),
            source_types: this.sourceTypes,
            jurisdictions: Object.keys(this.jurisdictionAbbreviations),
            cache_duration: '2 hours'
        };
    }
}

module.exports = LegalCitation;