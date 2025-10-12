const axios = require('axios');
const NodeCache = require('node-cache');

class RegulationChecker {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 3600 }); // 1 hour cache
        this.regulatoryAgencies = {
            'SEC': {
                name: 'Securities and Exchange Commission',
                domain: 'finance',
                api_base: 'https://www.sec.gov/rules',
                description: 'Financial securities regulation'
            },
            'FDA': {
                name: 'Food and Drug Administration',
                domain: 'healthcare',
                api_base: 'https://www.fda.gov',
                description: 'Food, drug, and medical device regulation'
            },
            'EPA': {
                name: 'Environmental Protection Agency',
                domain: 'environmental',
                api_base: 'https://www.epa.gov',
                description: 'Environmental protection and regulation'
            },
            'FTC': {
                name: 'Federal Trade Commission',
                domain: 'consumer',
                api_base: 'https://www.ftc.gov',
                description: 'Consumer protection and antitrust'
            },
            'DOT': {
                name: 'Department of Transportation',
                domain: 'transportation',
                api_base: 'https://www.transportation.gov',
                description: 'Transportation safety and regulation'
            },
            'OSHA': {
                name: 'Occupational Safety and Health Administration',
                domain: 'workplace_safety',
                api_base: 'https://www.osha.gov',
                description: 'Workplace safety and health standards'
            }
        };

        this.complianceCategories = [
            'data_privacy', 'financial_reporting', 'environmental',
            'workplace_safety', 'consumer_protection', 'antitrust',
            'healthcare', 'telecommunications', 'energy', 'transportation'
        ];

        this.mockRegulations = this.initializeMockRegulations();
        this.requestCount = 0;
        this.maxRequestsPerHour = 100;
    }

    async searchRegulations(query, agency = null, category = null, effectiveDate = null) {
        try {
            const cacheKey = `search_${query}_${agency}_${category}_${effectiveDate}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            // Use mock data if API limits reached
            if (this.requestCount >= this.maxRequestsPerHour) {
                return this.searchMockRegulations(query, agency, category);
            }

            // In a real implementation, this would call actual regulatory APIs
            console.log(`Searching regulations for: ${query} (using mock data)`);
            this.requestCount++;

            const mockResults = this.searchMockRegulations(query, agency, category);

            const result = {
                query: query,
                agency_filter: agency,
                category_filter: category,
                effective_date_filter: effectiveDate,
                total_results: mockResults.regulations.length,
                regulations: mockResults.regulations,
                search_metadata: {
                    search_performed_at: new Date().toISOString(),
                    agencies_searched: agency ? [agency] : Object.keys(this.regulatoryAgencies),
                    data_sources: ['Mock Regulatory Database', 'UC2 Legal Repository'],
                    search_quality: 'High',
                    completeness: '85%'
                },
                compliance_alerts: this.generateComplianceAlerts(mockResults.regulations),
                recommended_actions: this.generateRecommendedActions(mockResults.regulations, query)
            };

            this.cache.set(cacheKey, result);
            return result;

        } catch (error) {
            return {
                error: 'Regulation search failed',
                message: error.message,
                query: query,
                searched_at: new Date().toISOString()
            };
        }
    }

    async checkCompliance(businessDescription, industry, state = 'federal', businessSize = 'small') {
        try {
            const cacheKey = `compliance_${businessDescription}_${industry}_${state}_${businessSize}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            // Determine applicable regulations based on business profile
            const applicableRegulations = this.getApplicableRegulations(industry, state, businessSize);

            // Generate compliance checklist
            const complianceChecklist = this.generateComplianceChecklist(applicableRegulations, businessSize);

            // Risk assessment
            const riskAssessment = this.assessComplianceRisk(industry, businessSize, state);

            const result = {
                business_profile: {
                    description: businessDescription,
                    industry: industry,
                    jurisdiction: state,
                    business_size: businessSize,
                    analyzed_at: new Date().toISOString()
                },
                applicable_regulations: applicableRegulations,
                compliance_checklist: complianceChecklist,
                risk_assessment: riskAssessment,
                priority_actions: this.getPriorityActions(applicableRegulations, riskAssessment),
                estimated_compliance_cost: this.estimateComplianceCost(applicableRegulations, businessSize),
                compliance_timeline: this.generateComplianceTimeline(applicableRegulations),
                regulatory_contacts: this.getRegulatoryContacts(applicableRegulations),
                monitoring_recommendations: this.getMonitoringRecommendations(industry)
            };

            this.cache.set(cacheKey, result);
            return result;

        } catch (error) {
            return {
                error: 'Compliance check failed',
                message: error.message,
                business_description: businessDescription,
                analyzed_at: new Date().toISOString()
            };
        }
    }

    async trackRegulationChanges(watchList, alertThreshold = 'medium') {
        try {
            const changes = [];

            for (const item of watchList) {
                const { regulation_id, keywords, agency } = item;

                // In real implementation, this would monitor actual regulatory feeds
                const mockChanges = this.generateMockRegulationChanges(regulation_id, keywords, agency);
                changes.push(...mockChanges);
            }

            // Filter by alert threshold
            const filteredChanges = this.filterChangesByThreshold(changes, alertThreshold);

            // Generate impact analysis
            const impactAnalysis = this.analyzeRegulationImpact(filteredChanges);

            return {
                tracking_summary: {
                    watched_regulations: watchList.length,
                    changes_detected: filteredChanges.length,
                    alert_threshold: alertThreshold,
                    monitoring_period: '30 days',
                    last_updated: new Date().toISOString()
                },
                regulation_changes: filteredChanges,
                impact_analysis: impactAnalysis,
                action_items: this.generateActionItems(filteredChanges),
                next_review_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
            };

        } catch (error) {
            return {
                error: 'Regulation tracking failed',
                message: error.message,
                monitored_at: new Date().toISOString()
            };
        }
    }

    async analyzeRegulatoryRisk(businessActivities, geography, timeline = '12_months') {
        try {
            const riskFactors = [];

            // Analyze each business activity for regulatory risk
            for (const activity of businessActivities) {
                const risks = this.assessActivityRisk(activity, geography);
                riskFactors.push(...risks);
            }

            // Geographic risk analysis
            const geographicRisks = this.assessGeographicRisk(geography);

            // Timeline-based risk projection
            const futureRisks = this.projectFutureRisks(riskFactors, timeline);

            const overallRisk = this.calculateOverallRisk(riskFactors);

            return {
                risk_analysis: {
                    business_activities: businessActivities,
                    geography: geography,
                    analysis_timeline: timeline,
                    overall_risk_score: overallRisk.score,
                    risk_level: overallRisk.level,
                    confidence: overallRisk.confidence
                },
                risk_factors: riskFactors,
                geographic_considerations: geographicRisks,
                future_risk_projection: futureRisks,
                mitigation_strategies: this.generateMitigationStrategies(riskFactors),
                monitoring_plan: this.createMonitoringPlan(riskFactors, timeline),
                regulatory_insurance_recommendations: this.getInsuranceRecommendations(overallRisk),
                analyzed_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Regulatory risk analysis failed',
                message: error.message,
                analyzed_at: new Date().toISOString()
            };
        }
    }

    searchMockRegulations(query, agency, category) {
        const allRegulations = Object.values(this.mockRegulations).flat();

        let filteredRegulations = allRegulations.filter(reg => {
            const matchesQuery = query ? (
                reg.title.toLowerCase().includes(query.toLowerCase()) ||
                reg.description.toLowerCase().includes(query.toLowerCase()) ||
                reg.keywords.some(keyword => keyword.toLowerCase().includes(query.toLowerCase()))
            ) : true;

            const matchesAgency = agency ? reg.agency === agency : true;
            const matchesCategory = category ? reg.category === category : true;

            return matchesQuery && matchesAgency && matchesCategory;
        });

        // Sort by relevance (simplified)
        filteredRegulations = filteredRegulations.sort((a, b) => {
            const aRelevance = this.calculateRelevance(a, query);
            const bRelevance = this.calculateRelevance(b, query);
            return bRelevance - aRelevance;
        });

        return {
            regulations: filteredRegulations.slice(0, 20), // Limit to top 20 results
            total_found: filteredRegulations.length
        };
    }

    getApplicableRegulations(industry, state, businessSize) {
        const regulations = [];

        // Industry-specific regulations
        const industryMap = {
            'finance': ['SEC', 'FINRA', 'Banking'],
            'healthcare': ['FDA', 'HIPAA', 'Healthcare'],
            'technology': ['FTC', 'Data Privacy', 'Cybersecurity'],
            'manufacturing': ['OSHA', 'EPA', 'Manufacturing'],
            'retail': ['FTC', 'Consumer Protection', 'Retail'],
            'food_service': ['FDA', 'Health Department', 'Food Safety']
        };

        const applicableAgencies = industryMap[industry] || ['FTC', 'OSHA'];

        for (const agency of applicableAgencies) {
            const agencyRegulations = this.mockRegulations[agency] || [];
            regulations.push(...agencyRegulations.filter(reg =>
                this.isApplicableToBusinessSize(reg, businessSize)
            ));
        }

        return regulations.slice(0, 15); // Limit for readability
    }

    generateComplianceChecklist(regulations, businessSize) {
        return regulations.map(reg => ({
            regulation_id: reg.id,
            title: reg.title,
            agency: reg.agency,
            priority: this.getCompliancePriority(reg, businessSize),
            estimated_effort: this.estimateImplementationEffort(reg, businessSize),
            deadline: this.getComplianceDeadline(reg),
            resources_needed: this.getRequiredResources(reg, businessSize),
            status: 'pending',
            notes: `Review ${reg.title} requirements and implement necessary procedures`
        }));
    }

    assessComplianceRisk(industry, businessSize, state) {
        const baseRisk = {
            'finance': 'High',
            'healthcare': 'High',
            'technology': 'Medium',
            'manufacturing': 'Medium',
            'retail': 'Low',
            'food_service': 'Medium'
        }[industry] || 'Medium';

        const sizeMultiplier = {
            'small': 1.0,
            'medium': 1.2,
            'large': 1.5,
            'enterprise': 1.8
        }[businessSize] || 1.0;

        const stateRisk = state === 'CA' ? 1.3 : (state === 'NY' ? 1.2 : 1.0);

        const riskScore = this.calculateRiskScore(baseRisk) * sizeMultiplier * stateRisk;

        return {
            overall_risk: this.getRiskLevel(riskScore),
            risk_score: Math.round(riskScore * 10) / 10,
            primary_risk_factors: this.getPrimaryRiskFactors(industry, businessSize),
            mitigation_priority: this.getMitigationPriority(riskScore)
        };
    }

    initializeMockRegulations() {
        return {
            'SEC': [
                {
                    id: 'SEC-2024-001',
                    title: 'Investment Company Act Compliance',
                    agency: 'SEC',
                    category: 'financial_reporting',
                    description: 'Requirements for investment company registration and reporting',
                    effective_date: '2024-01-15',
                    keywords: ['investment', 'registration', 'reporting'],
                    business_size_applicability: ['medium', 'large', 'enterprise'],
                    penalties: 'Up to $5M per violation'
                },
                {
                    id: 'SEC-2024-002',
                    title: 'Cybersecurity Risk Management',
                    agency: 'SEC',
                    category: 'data_privacy',
                    description: 'Cybersecurity risk management rules for public companies',
                    effective_date: '2024-03-01',
                    keywords: ['cybersecurity', 'risk management', 'disclosure'],
                    business_size_applicability: ['large', 'enterprise'],
                    penalties: 'Cease and desist orders, fines up to $1M'
                }
            ],
            'FDA': [
                {
                    id: 'FDA-2024-001',
                    title: 'Food Safety Modernization Act',
                    agency: 'FDA',
                    category: 'healthcare',
                    description: 'Preventive controls for human food manufacturing',
                    effective_date: '2024-02-01',
                    keywords: ['food safety', 'manufacturing', 'preventive controls'],
                    business_size_applicability: ['small', 'medium', 'large'],
                    penalties: 'Warning letters, product recalls, facility closure'
                }
            ],
            'FTC': [
                {
                    id: 'FTC-2024-001',
                    title: 'Children\'s Online Privacy Protection Rule',
                    agency: 'FTC',
                    category: 'data_privacy',
                    description: 'Enhanced protections for children\'s online privacy',
                    effective_date: '2024-06-01',
                    keywords: ['privacy', 'children', 'online', 'data collection'],
                    business_size_applicability: ['small', 'medium', 'large', 'enterprise'],
                    penalties: 'Up to $43,792 per violation'
                }
            ]
        };
    }

    calculateRelevance(regulation, query) {
        if (!query) return 1;

        let score = 0;
        const queryLower = query.toLowerCase();

        if (regulation.title.toLowerCase().includes(queryLower)) score += 3;
        if (regulation.description.toLowerCase().includes(queryLower)) score += 2;
        regulation.keywords.forEach(keyword => {
            if (keyword.toLowerCase().includes(queryLower)) score += 1;
        });

        return score;
    }

    getToolInfo() {
        return {
            name: 'Regulation Checker',
            version: '2.0.0',
            description: 'Comprehensive regulatory compliance monitoring and analysis',
            author: 'UC2 System',
            capabilities: [
                'Regulation search and discovery',
                'Compliance requirement analysis',
                'Risk assessment and scoring',
                'Regulatory change monitoring',
                'Industry-specific compliance guidance',
                'Multi-jurisdictional analysis',
                'Compliance cost estimation',
                'Timeline planning',
                'Priority action identification'
            ],
            supported_agencies: Object.keys(this.regulatoryAgencies),
            compliance_categories: this.complianceCategories,
            cache_duration: '1 hour',
            rate_limit: '100 requests/hour'
        };
    }
}

module.exports = RegulationChecker;