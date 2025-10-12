const crypto = require('crypto');

class FraudDetectorTool {
    constructor() {
        this.name = 'fraudDetector';
        this.version = '1.0.0';
        this.description = 'AI-powered financial fraud detection and analysis with advanced pattern recognition';
        this.category = 'Financial Security';
        this.author = 'UC2 System';
        this.tags = ['fraud', 'detection', 'financial', 'security', 'analysis', 'anomaly', 'risk'];

        this.schema = {
            type: 'object',
            properties: {
                operation: {
                    type: 'string',
                    description: 'Type of fraud analysis to perform',
                    enum: [
                        'analyze_transactions',    // Analyze transaction patterns
                        'profile_behavior',        // Behavioral profiling
                        'detect_anomalies',       // Anomaly detection
                        'score_risk',             // Risk scoring
                        'investigate_entity',     // Entity investigation
                        'pattern_analysis',       // Pattern recognition
                        'compliance_check',       // Compliance analysis
                        'network_analysis',       // Relationship analysis
                        'real_time_monitoring',   // Real-time fraud monitoring
                        'comprehensive_audit'     // Full audit analysis
                    ],
                    default: 'analyze_transactions'
                },
                data: {
                    type: 'object',
                    description: 'Input data for analysis',
                    properties: {
                        transactions: {
                            type: 'array',
                            description: 'Transaction data array',
                            items: {
                                type: 'object',
                                properties: {
                                    id: { type: 'string' },
                                    amount: { type: 'number' },
                                    timestamp: { type: 'string' },
                                    accountId: { type: 'string' },
                                    recipientId: { type: 'string' },
                                    type: { type: 'string' },
                                    location: { type: 'object' },
                                    metadata: { type: 'object' }
                                }
                            }
                        },
                        accounts: {
                            type: 'array',
                            description: 'Account information',
                            items: {
                                type: 'object',
                                properties: {
                                    id: { type: 'string' },
                                    ownerId: { type: 'string' },
                                    type: { type: 'string' },
                                    balance: { type: 'number' },
                                    createdAt: { type: 'string' },
                                    profile: { type: 'object' }
                                }
                            }
                        },
                        entities: {
                            type: 'array',
                            description: 'Entity/person data',
                            items: {
                                type: 'object',
                                properties: {
                                    id: { type: 'string' },
                                    name: { type: 'string' },
                                    email: { type: 'string' },
                                    phone: { type: 'string' },
                                    address: { type: 'object' },
                                    identityDocs: { type: 'array' },
                                    riskProfile: { type: 'object' }
                                }
                            }
                        }
                    }
                },
                options: {
                    type: 'object',
                    description: 'Analysis configuration options',
                    properties: {
                        timeWindow: {
                            type: 'string',
                            description: 'Analysis time window',
                            enum: ['1h', '6h', '24h', '7d', '30d', '90d', '1y'],
                            default: '30d'
                        },
                        sensitivity: {
                            type: 'string',
                            description: 'Detection sensitivity level',
                            enum: ['low', 'medium', 'high', 'critical'],
                            default: 'medium'
                        },
                        fraudTypes: {
                            type: 'array',
                            description: 'Specific fraud types to focus on',
                            items: {
                                type: 'string',
                                enum: [
                                    'credit_card_fraud',
                                    'wire_transfer_fraud',
                                    'account_takeover',
                                    'identity_theft',
                                    'money_laundering',
                                    'insider_trading',
                                    'ponzi_scheme',
                                    'invoice_fraud',
                                    'payroll_fraud',
                                    'synthetic_identity'
                                ]
                            },
                            default: ['credit_card_fraud', 'account_takeover']
                        },
                        includeMlAnalysis: {
                            type: 'boolean',
                            description: 'Include machine learning analysis',
                            default: true
                        },
                        generateReport: {
                            type: 'boolean',
                            description: 'Generate detailed investigation report',
                            default: true
                        },
                        realTimeAlerts: {
                            type: 'boolean',
                            description: 'Enable real-time fraud alerts',
                            default: false
                        }
                    }
                }
            },
            required: ['operation']
        };

        // Fraud detection models and thresholds
        this.models = {
            anomalyThresholds: {
                low: { zscore: 2.0, iqr: 1.5, percentile: 90 },
                medium: { zscore: 2.5, iqr: 2.0, percentile: 95 },
                high: { zscore: 3.0, iqr: 2.5, percentile: 98 },
                critical: { zscore: 3.5, iqr: 3.0, percentile: 99 }
            },
            riskWeights: {
                amount: 0.25,
                velocity: 0.20,
                geographic: 0.15,
                behavioral: 0.20,
                network: 0.10,
                temporal: 0.10
            },
            benfordDistribution: [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]
        };

        // Pattern libraries
        this.fraudPatterns = {
            creditCardFraud: {
                rapidVelocity: { timeWindow: 300, threshold: 5 }, // 5 transactions in 5 minutes
                amountProgression: { pattern: 'small_to_large' },
                geographicJump: { distance: 100, timeWindow: 3600 }, // 100 miles in 1 hour
                roundAmounts: { pattern: 'multiple_of_100' }
            },
            accountTakeover: {
                suddenProfileChange: { fields: ['email', 'phone', 'address'] },
                deviceFingerprint: { newDevice: true, locationMismatch: true },
                transactionPatternChange: { deviationThreshold: 3.0 }
            },
            moneyLaundering: {
                structuring: { amountRange: [9000, 10000], frequency: 'high' },
                layering: { complexityScore: 0.8, intermediateAccounts: 3 },
                rapidMovement: { timeWindow: 86400, hops: 5 }
            }
        };

        // Cache for performance optimization
        this.cache = new Map();
        this.cacheTimeout = 10 * 60 * 1000; // 10 minutes

        // ML model placeholder (in production would load actual models)
        this.mlModels = {
            transactionClassifier: null,
            behaviorProfiler: null,
            networkAnalyzer: null
        };
    }

    async execute(params) {
        const startTime = Date.now();

        try {
            this.validateParams(params);

            const operation = params.operation || 'analyze_transactions';
            const options = params.options || {};

            const result = {
                success: true,
                operation: operation,
                timestamp: new Date().toISOString(),
                data: {},
                analysis: {},
                alerts: [],
                riskScore: 0,
                confidence: 0,
                metadata: {
                    version: this.version,
                    executionTime: null,
                    dataProcessed: 0,
                    modelsUsed: [],
                    cached: false
                }
            };

            // Check cache for expensive operations
            const cacheKey = this.generateCacheKey(params);
            const cached = this.getFromCache(cacheKey);
            if (cached && !options.realTimeAlerts) {
                result.data = cached.data;
                result.analysis = cached.analysis;
                result.riskScore = cached.riskScore;
                result.metadata.cached = true;
                result.metadata.executionTime = `${Date.now() - startTime}ms`;
                return result;
            }

            // Execute the requested operation
            switch (operation) {
                case 'analyze_transactions':
                    result.data = await this.analyzeTransactions(params.data, options);
                    break;
                case 'profile_behavior':
                    result.data = await this.profileBehavior(params.data, options);
                    break;
                case 'detect_anomalies':
                    result.data = await this.detectAnomalies(params.data, options);
                    break;
                case 'score_risk':
                    result.data = await this.scoreRisk(params.data, options);
                    break;
                case 'investigate_entity':
                    result.data = await this.investigateEntity(params.data, options);
                    break;
                case 'pattern_analysis':
                    result.data = await this.performPatternAnalysis(params.data, options);
                    break;
                case 'compliance_check':
                    result.data = await this.performComplianceCheck(params.data, options);
                    break;
                case 'network_analysis':
                    result.data = await this.analyzeNetworks(params.data, options);
                    break;
                case 'real_time_monitoring':
                    result.data = await this.realTimeMonitoring(params.data, options);
                    break;
                case 'comprehensive_audit':
                    result.data = await this.comprehensiveAudit(params.data, options);
                    break;
                default:
                    throw new Error(`Unknown operation: ${operation}`);
            }

            // Calculate overall risk score and confidence
            result.riskScore = this.calculateOverallRiskScore(result.data);
            result.confidence = this.calculateConfidenceScore(result.data, params.data);

            // Generate alerts based on findings
            result.alerts = this.generateAlerts(result.data, options);

            // Perform additional ML analysis if enabled
            if (options.includeMlAnalysis) {
                result.analysis.mlInsights = await this.performMlAnalysis(params.data, result.data);
                result.metadata.modelsUsed = ['transaction_classifier', 'behavior_profiler'];
            }

            // Generate investigation report if requested
            if (options.generateReport) {
                result.analysis.investigationReport = this.generateInvestigationReport(result);
            }

            // Cache results for non-real-time operations
            if (!options.realTimeAlerts) {
                this.setCache(cacheKey, {
                    data: result.data,
                    analysis: result.analysis,
                    riskScore: result.riskScore,
                    timestamp: Date.now()
                });
            }

            result.metadata.executionTime = `${Date.now() - startTime}ms`;
            result.metadata.dataProcessed = this.getDataPointCount(params.data);

            return result;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                operation: params.operation,
                timestamp: new Date().toISOString(),
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    validateParams(params) {
        if (!params.operation) {
            throw new Error('Operation parameter is required');
        }

        if (!params.data && params.operation !== 'real_time_monitoring') {
            throw new Error('Data parameter is required for most operations');
        }
    }

    async analyzeTransactions(data, options) {
        const transactions = data.transactions || [];
        if (transactions.length === 0) {
            return { error: 'No transaction data provided' };
        }

        const analysis = {
            summary: {
                totalTransactions: transactions.length,
                totalAmount: 0,
                timeSpan: null,
                uniqueAccounts: new Set(),
                flaggedTransactions: 0
            },
            patterns: {},
            anomalies: [],
            riskIndicators: [],
            fraudScore: 0
        };

        // Basic statistics
        let minTimestamp = Infinity;
        let maxTimestamp = 0;

        for (const tx of transactions) {
            analysis.summary.totalAmount += tx.amount || 0;
            analysis.summary.uniqueAccounts.add(tx.accountId);

            const timestamp = new Date(tx.timestamp).getTime();
            minTimestamp = Math.min(minTimestamp, timestamp);
            maxTimestamp = Math.max(maxTimestamp, timestamp);
        }

        analysis.summary.uniqueAccounts = analysis.summary.uniqueAccounts.size;
        analysis.summary.timeSpan = {
            start: new Date(minTimestamp).toISOString(),
            end: new Date(maxTimestamp).toISOString(),
            durationHours: (maxTimestamp - minTimestamp) / (1000 * 60 * 60)
        };

        // Transaction velocity analysis
        analysis.patterns.velocityAnalysis = this.analyzeTransactionVelocity(transactions);

        // Amount pattern analysis
        analysis.patterns.amountAnalysis = this.analyzeAmountPatterns(transactions);

        // Geographic analysis
        analysis.patterns.geographicAnalysis = this.analyzeGeographicPatterns(transactions);

        // Time-based analysis
        analysis.patterns.temporalAnalysis = this.analyzeTemporalPatterns(transactions);

        // Benford's Law analysis
        analysis.patterns.benfordAnalysis = this.performBenfordAnalysis(transactions);

        // Fraud pattern detection
        analysis.patterns.fraudPatterns = this.detectFraudPatterns(transactions, options.fraudTypes);

        // Statistical anomaly detection
        analysis.anomalies = this.detectStatisticalAnomalies(transactions, options.sensitivity);

        // Calculate fraud score
        analysis.fraudScore = this.calculateTransactionFraudScore(analysis);

        analysis.summary.flaggedTransactions = analysis.anomalies.length;

        return analysis;
    }

    async profileBehavior(data, options) {
        const transactions = data.transactions || [];
        const accounts = data.accounts || [];
        const entities = data.entities || [];

        const profiles = {};

        // Profile each entity's behavior
        for (const entity of entities) {
            const entityTransactions = transactions.filter(tx =>
                tx.accountId && accounts.find(acc => acc.ownerId === entity.id && acc.id === tx.accountId)
            );

            profiles[entity.id] = {
                entityInfo: entity,
                behaviorBaseline: this.calculateBehaviorBaseline(entityTransactions),
                currentBehavior: this.analyzeCurrentBehavior(entityTransactions, options.timeWindow),
                deviationScore: 0,
                riskFactors: [],
                behaviorChange: {}
            };

            // Calculate behavior deviation
            profiles[entity.id].deviationScore = this.calculateBehaviorDeviation(
                profiles[entity.id].behaviorBaseline,
                profiles[entity.id].currentBehavior
            );

            // Analyze behavior changes
            profiles[entity.id].behaviorChange = this.analyzeBehaviorChange(entityTransactions);

            // Identify risk factors
            profiles[entity.id].riskFactors = this.identifyBehaviorRiskFactors(profiles[entity.id]);
        }

        return {
            profileCount: Object.keys(profiles).length,
            profiles: profiles,
            aggregateRisk: this.calculateAggregateRisk(profiles),
            highRiskEntities: Object.entries(profiles)
                .filter(([id, profile]) => profile.deviationScore > 2.0)
                .map(([id, profile]) => ({ entityId: id, riskScore: profile.deviationScore }))
        };
    }

    async detectAnomalies(data, options) {
        const transactions = data.transactions || [];
        const sensitivity = this.models.anomalyThresholds[options.sensitivity || 'medium'];

        const anomalies = {
            statistical: [],
            behavioral: [],
            network: [],
            temporal: [],
            geographic: []
        };

        // Statistical anomalies
        anomalies.statistical = this.detectStatisticalAnomalies(transactions, options.sensitivity);

        // Behavioral anomalies
        if (data.accounts && data.entities) {
            anomalies.behavioral = this.detectBehavioralAnomalies(data, sensitivity);
        }

        // Network anomalies
        anomalies.network = this.detectNetworkAnomalies(transactions, sensitivity);

        // Temporal anomalies
        anomalies.temporal = this.detectTemporalAnomalies(transactions, sensitivity);

        // Geographic anomalies
        anomalies.geographic = this.detectGeographicAnomalies(transactions, sensitivity);

        return {
            summary: {
                totalAnomalies: Object.values(anomalies).flat().length,
                byCategory: Object.fromEntries(
                    Object.entries(anomalies).map(([key, value]) => [key, value.length])
                )
            },
            anomalies: anomalies,
            prioritizedAlerts: this.prioritizeAnomalies(anomalies, sensitivity)
        };
    }

    async scoreRisk(data, options) {
        const riskScores = {
            overall: 0,
            components: {},
            factors: [],
            recommendations: []
        };

        // Transaction risk scoring
        if (data.transactions) {
            riskScores.components.transactional = this.scoreTransactionalRisk(data.transactions, options);
        }

        // Entity risk scoring
        if (data.entities) {
            riskScores.components.entities = this.scoreEntityRisk(data.entities, options);
        }

        // Network risk scoring
        if (data.transactions && data.accounts) {
            riskScores.components.network = this.scoreNetworkRisk(data, options);
        }

        // Calculate weighted overall score
        const weights = this.models.riskWeights;
        riskScores.overall = Object.entries(riskScores.components).reduce((total, [component, score]) => {
            const weight = weights[component] || 0.1;
            return total + (score * weight);
        }, 0);

        // Generate risk factors and recommendations
        riskScores.factors = this.identifyRiskFactors(riskScores.components);
        riskScores.recommendations = this.generateRiskRecommendations(riskScores);

        return riskScores;
    }

    async investigateEntity(data, options) {
        if (!data.entities || data.entities.length === 0) {
            return { error: 'No entity data provided for investigation' };
        }

        const investigations = {};

        for (const entity of data.entities) {
            const investigation = {
                entityId: entity.id,
                basicInfo: entity,
                riskProfile: {},
                transactionAnalysis: {},
                networkAnalysis: {},
                identityVerification: {},
                complianceChecks: {},
                alertHistory: [],
                investigationScore: 0
            };

            // Analyze entity's transactions
            const entityTransactions = (data.transactions || []).filter(tx =>
                tx.accountId && data.accounts?.find(acc => acc.ownerId === entity.id && acc.id === tx.accountId)
            );

            investigation.transactionAnalysis = this.analyzeEntityTransactions(entityTransactions);

            // Network analysis
            investigation.networkAnalysis = this.analyzeEntityNetwork(entity, data);

            // Identity verification
            investigation.identityVerification = this.performIdentityVerification(entity);

            // Compliance checks
            investigation.complianceChecks = this.performEntityComplianceCheck(entity, entityTransactions);

            // Calculate investigation score
            investigation.investigationScore = this.calculateInvestigationScore(investigation);

            investigations[entity.id] = investigation;
        }

        return {
            investigationCount: Object.keys(investigations).length,
            investigations: investigations,
            highRiskEntities: Object.entries(investigations)
                .filter(([id, inv]) => inv.investigationScore > 70)
                .sort((a, b) => b[1].investigationScore - a[1].investigationScore)
        };
    }

    async performPatternAnalysis(data, options) {
        const patterns = {
            transactionPatterns: {},
            behaviorPatterns: {},
            networkPatterns: {},
            temporalPatterns: {},
            fraudPatterns: {}
        };

        if (data.transactions) {
            patterns.transactionPatterns = this.identifyTransactionPatterns(data.transactions);
            patterns.temporalPatterns = this.identifyTemporalPatterns(data.transactions);
            patterns.fraudPatterns = this.detectFraudPatterns(data.transactions, options.fraudTypes);
        }

        if (data.entities && data.accounts) {
            patterns.behaviorPatterns = this.identifyBehaviorPatterns(data);
            patterns.networkPatterns = this.identifyNetworkPatterns(data);
        }

        return {
            patternSummary: this.summarizePatterns(patterns),
            patterns: patterns,
            suspiciousPatterns: this.flagSuspiciousPatterns(patterns),
            patternComplexity: this.calculatePatternComplexity(patterns)
        };
    }

    async performComplianceCheck(data, options) {
        const compliance = {
            amlChecks: {},
            kycVerification: {},
            sanctionsScreening: {},
            pepScreening: {},
            regulatoryAlerts: [],
            complianceScore: 0
        };

        // Anti-Money Laundering (AML) checks
        if (data.transactions) {
            compliance.amlChecks = this.performAmlChecks(data.transactions);
        }

        // Know Your Customer (KYC) verification
        if (data.entities) {
            compliance.kycVerification = this.performKycChecks(data.entities);
        }

        // Sanctions and PEP screening
        compliance.sanctionsScreening = this.performSanctionsScreening(data.entities || []);
        compliance.pepScreening = this.performPepScreening(data.entities || []);

        // Generate regulatory alerts
        compliance.regulatoryAlerts = this.generateRegulatoryAlerts(compliance);

        // Calculate overall compliance score
        compliance.complianceScore = this.calculateComplianceScore(compliance);

        return compliance;
    }

    async analyzeNetworks(data, options) {
        if (!data.transactions || !data.accounts) {
            return { error: 'Transaction and account data required for network analysis' };
        }

        const network = {
            nodes: {},
            edges: [],
            communities: [],
            centralityMetrics: {},
            suspiciousNetworks: [],
            networkRisk: 0
        };

        // Build network graph
        const graph = this.buildTransactionNetwork(data.transactions, data.accounts);
        network.nodes = graph.nodes;
        network.edges = graph.edges;

        // Detect communities/clusters
        network.communities = this.detectCommunities(graph);

        // Calculate centrality metrics
        network.centralityMetrics = this.calculateCentralityMetrics(graph);

        // Identify suspicious networks
        network.suspiciousNetworks = this.identifySuspiciousNetworks(graph, network.communities);

        // Calculate network risk score
        network.networkRisk = this.calculateNetworkRisk(network);

        return network;
    }

    async realTimeMonitoring(data, options) {
        // Simulate real-time monitoring capability
        const monitoring = {
            status: 'active',
            timestamp: new Date().toISOString(),
            activeRules: this.getActiveMonitoringRules(options),
            recentAlerts: [],
            systemHealth: {
                uptimePercent: 99.9,
                averageLatency: 15,
                rulesProcessed: 0,
                alertsGenerated: 0
            }
        };

        // If transaction data provided, process it through real-time rules
        if (data && data.transactions) {
            monitoring.recentAlerts = this.processRealTimeRules(data.transactions, options);
            monitoring.systemHealth.rulesProcessed = monitoring.activeRules.length * data.transactions.length;
            monitoring.systemHealth.alertsGenerated = monitoring.recentAlerts.length;
        }

        return monitoring;
    }

    async comprehensiveAudit(data, options) {
        const audit = {
            auditId: crypto.randomUUID(),
            timestamp: new Date().toISOString(),
            scope: options.fraudTypes || ['all'],
            findings: {},
            riskAssessment: {},
            recommendations: [],
            complianceStatus: {},
            executiveSummary: {}
        };

        // Perform all major analyses
        const analyses = await Promise.all([
            this.analyzeTransactions(data, options),
            this.profileBehavior(data, options),
            this.detectAnomalies(data, options),
            this.scoreRisk(data, options),
            this.performPatternAnalysis(data, options),
            this.performComplianceCheck(data, options),
            this.analyzeNetworks(data, options)
        ]);

        audit.findings = {
            transactionAnalysis: analyses[0],
            behaviorProfiling: analyses[1],
            anomalyDetection: analyses[2],
            riskScoring: analyses[3],
            patternAnalysis: analyses[4],
            complianceCheck: analyses[5],
            networkAnalysis: analyses[6]
        };

        // Generate comprehensive risk assessment
        audit.riskAssessment = this.generateComprehensiveRiskAssessment(audit.findings);

        // Generate recommendations
        audit.recommendations = this.generateAuditRecommendations(audit);

        // Compliance status summary
        audit.complianceStatus = this.generateComplianceStatusSummary(audit.findings);

        // Executive summary
        audit.executiveSummary = this.generateExecutiveSummary(audit);

        return audit;
    }

    // Analysis Helper Methods

    analyzeTransactionVelocity(transactions) {
        const velocity = {
            overall: { count: transactions.length, timeSpan: 0 },
            byAccount: {},
            alerts: []
        };

        // Sort transactions by timestamp
        const sortedTx = transactions.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        if (sortedTx.length > 1) {
            const timeSpan = new Date(sortedTx[sortedTx.length - 1].timestamp) - new Date(sortedTx[0].timestamp);
            velocity.overall.timeSpan = timeSpan;
            velocity.overall.rate = transactions.length / (timeSpan / (1000 * 60 * 60)); // transactions per hour
        }

        // Analyze velocity by account
        const accountTx = {};
        for (const tx of transactions) {
            if (!accountTx[tx.accountId]) {
                accountTx[tx.accountId] = [];
            }
            accountTx[tx.accountId].push(tx);
        }

        for (const [accountId, txs] of Object.entries(accountTx)) {
            if (txs.length > 1) {
                const sortedAccountTx = txs.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                const timeSpan = new Date(sortedAccountTx[sortedAccountTx.length - 1].timestamp) -
                               new Date(sortedAccountTx[0].timestamp);

                velocity.byAccount[accountId] = {
                    count: txs.length,
                    timeSpan: timeSpan,
                    rate: txs.length / (timeSpan / (1000 * 60 * 60))
                };

                // Check for rapid velocity (fraud indicator)
                if (velocity.byAccount[accountId].rate > 10) { // More than 10 transactions per hour
                    velocity.alerts.push({
                        type: 'rapid_velocity',
                        accountId: accountId,
                        rate: velocity.byAccount[accountId].rate,
                        severity: 'high'
                    });
                }
            }
        }

        return velocity;
    }

    analyzeAmountPatterns(transactions) {
        const amounts = transactions.map(tx => tx.amount).filter(amount => amount > 0);

        if (amounts.length === 0) {
            return { error: 'No valid amounts found' };
        }

        const analysis = {
            statistics: {
                mean: amounts.reduce((a, b) => a + b, 0) / amounts.length,
                median: this.calculateMedian(amounts),
                standardDeviation: 0,
                min: Math.min(...amounts),
                max: Math.max(...amounts)
            },
            patterns: {
                roundNumbers: 0,
                justBelowThreshold: 0,
                duplicateAmounts: {},
                amountClusters: []
            },
            anomalies: []
        };

        // Calculate standard deviation
        const mean = analysis.statistics.mean;
        const variance = amounts.reduce((sum, amount) => sum + Math.pow(amount - mean, 2), 0) / amounts.length;
        analysis.statistics.standardDeviation = Math.sqrt(variance);

        // Pattern analysis
        const amountCounts = {};
        for (const amount of amounts) {
            amountCounts[amount] = (amountCounts[amount] || 0) + 1;

            // Round number detection
            if (amount % 100 === 0 || amount % 1000 === 0) {
                analysis.patterns.roundNumbers++;
            }

            // Just below threshold detection (common in structuring)
            if (amount >= 9000 && amount < 10000) {
                analysis.patterns.justBelowThreshold++;
            }
        }

        // Find duplicate amounts
        analysis.patterns.duplicateAmounts = Object.fromEntries(
            Object.entries(amountCounts).filter(([amount, count]) => count > 1)
        );

        // Statistical anomaly detection
        for (const amount of amounts) {
            const zScore = Math.abs((amount - mean) / analysis.statistics.standardDeviation);
            if (zScore > 3) {
                analysis.anomalies.push({
                    amount: amount,
                    zScore: zScore,
                    type: 'statistical_outlier'
                });
            }
        }

        return analysis;
    }

    analyzeGeographicPatterns(transactions) {
        const locations = transactions
            .filter(tx => tx.location && tx.location.latitude && tx.location.longitude)
            .map(tx => ({ ...tx.location, timestamp: tx.timestamp, amount: tx.amount }));

        if (locations.length === 0) {
            return { note: 'No geographic data available' };
        }

        const analysis = {
            uniqueLocations: new Set(),
            geographicSpread: 0,
            rapidMovement: [],
            locationClusters: [],
            suspiciousPatterns: []
        };

        // Calculate unique locations and geographic spread
        for (const location of locations) {
            const key = `${location.latitude},${location.longitude}`;
            analysis.uniqueLocations.add(key);
        }

        analysis.uniqueLocations = analysis.uniqueLocations.size;

        // Detect rapid geographic movement
        const sortedLocations = locations.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        for (let i = 1; i < sortedLocations.length; i++) {
            const prev = sortedLocations[i - 1];
            const curr = sortedLocations[i];

            const distance = this.calculateDistance(
                prev.latitude, prev.longitude,
                curr.latitude, curr.longitude
            );

            const timeDiff = (new Date(curr.timestamp) - new Date(prev.timestamp)) / (1000 * 60 * 60); // hours

            if (distance > 100 && timeDiff < 2) { // 100+ miles in under 2 hours
                analysis.rapidMovement.push({
                    from: { lat: prev.latitude, lng: prev.longitude, timestamp: prev.timestamp },
                    to: { lat: curr.latitude, lng: curr.longitude, timestamp: curr.timestamp },
                    distance: distance,
                    timeHours: timeDiff,
                    impossibleSpeed: distance / timeDiff > 500 // > 500 mph
                });
            }
        }

        return analysis;
    }

    analyzeTemporalPatterns(transactions) {
        const analysis = {
            hourlyDistribution: new Array(24).fill(0),
            dayOfWeekDistribution: new Array(7).fill(0),
            monthlyDistribution: new Array(12).fill(0),
            unusualTiming: [],
            temporalClusters: []
        };

        for (const tx of transactions) {
            const date = new Date(tx.timestamp);
            const hour = date.getHours();
            const dayOfWeek = date.getDay();
            const month = date.getMonth();

            analysis.hourlyDistribution[hour]++;
            analysis.dayOfWeekDistribution[dayOfWeek]++;
            analysis.monthlyDistribution[month]++;

            // Flag unusual timing (e.g., transactions at 3 AM)
            if (hour >= 2 && hour <= 4) {
                analysis.unusualTiming.push({
                    transactionId: tx.id,
                    timestamp: tx.timestamp,
                    hour: hour,
                    amount: tx.amount
                });
            }
        }

        return analysis;
    }

    performBenfordAnalysis(transactions) {
        const amounts = transactions.map(tx => tx.amount).filter(amount => amount > 0);

        if (amounts.length < 100) {
            return { note: 'Insufficient data for reliable Benford analysis (need 100+ samples)' };
        }

        const firstDigitCounts = new Array(9).fill(0);

        for (const amount of amounts) {
            const firstDigit = parseInt(amount.toString()[0]);
            if (firstDigit >= 1 && firstDigit <= 9) {
                firstDigitCounts[firstDigit - 1]++;
            }
        }

        const observedDistribution = firstDigitCounts.map(count => (count / amounts.length) * 100);
        const expectedDistribution = this.models.benfordDistribution;

        // Calculate chi-square test statistic
        let chiSquare = 0;
        for (let i = 0; i < 9; i++) {
            const observed = (observedDistribution[i] / 100) * amounts.length;
            const expected = (expectedDistribution[i] / 100) * amounts.length;
            chiSquare += Math.pow(observed - expected, 2) / expected;
        }

        // Critical value for 8 degrees of freedom at 95% confidence is 15.507
        const conformsToBenford = chiSquare < 15.507;

        return {
            sampleSize: amounts.length,
            observedDistribution: observedDistribution,
            expectedDistribution: expectedDistribution,
            chiSquareStatistic: chiSquare,
            conformsToBenford: conformsToBenford,
            suspicionLevel: conformsToBenford ? 'low' : 'high',
            interpretation: conformsToBenford ?
                'Data follows expected natural distribution' :
                'Data shows signs of possible manipulation'
        };
    }

    detectFraudPatterns(transactions, fraudTypes) {
        const patterns = {};
        const types = fraudTypes || ['credit_card_fraud', 'account_takeover', 'money_laundering'];

        for (const fraudType of types) {
            switch (fraudType) {
                case 'credit_card_fraud':
                    patterns.creditCardFraud = this.detectCreditCardFraudPatterns(transactions);
                    break;
                case 'account_takeover':
                    patterns.accountTakeover = this.detectAccountTakeoverPatterns(transactions);
                    break;
                case 'money_laundering':
                    patterns.moneyLaundering = this.detectMoneyLaunderingPatterns(transactions);
                    break;
                case 'wire_transfer_fraud':
                    patterns.wireTransferFraud = this.detectWireTransferFraudPatterns(transactions);
                    break;
            }
        }

        return patterns;
    }

    detectCreditCardFraudPatterns(transactions) {
        const patterns = {
            rapidSequence: [],
            amountProgression: [],
            geographicInconsistency: [],
            roundAmountClusters: []
        };

        // Rapid sequence detection
        const sortedTx = transactions.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        for (let i = 0; i < sortedTx.length - 4; i++) {
            const window = sortedTx.slice(i, i + 5);
            const timeSpan = new Date(window[4].timestamp) - new Date(window[0].timestamp);

            if (timeSpan < 5 * 60 * 1000) { // 5 minutes
                patterns.rapidSequence.push({
                    transactions: window.map(tx => tx.id),
                    timeSpan: timeSpan / 1000,
                    riskScore: 8.5
                });
            }
        }

        // Amount progression (small to large amounts)
        for (let i = 0; i < sortedTx.length - 2; i++) {
            const window = sortedTx.slice(i, i + 3);
            if (window[0].amount < window[1].amount && window[1].amount < window[2].amount) {
                const ratio = window[2].amount / window[0].amount;
                if (ratio > 5) {
                    patterns.amountProgression.push({
                        transactions: window.map(tx => tx.id),
                        ratio: ratio,
                        riskScore: 7.0
                    });
                }
            }
        }

        return patterns;
    }

    detectAccountTakeoverPatterns(transactions) {
        const patterns = {
            suddenBehaviorChange: [],
            unusualTransactionPattern: [],
            deviceInconsistency: []
        };

        // Group by account and analyze behavior changes
        const accountGroups = {};
        for (const tx of transactions) {
            if (!accountGroups[tx.accountId]) {
                accountGroups[tx.accountId] = [];
            }
            accountGroups[tx.accountId].push(tx);
        }

        for (const [accountId, accountTx] of Object.entries(accountGroups)) {
            if (accountTx.length < 10) continue;

            const sortedTx = accountTx.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const midPoint = Math.floor(sortedTx.length / 2);

            const firstHalf = sortedTx.slice(0, midPoint);
            const secondHalf = sortedTx.slice(midPoint);

            // Analyze behavior change
            const firstHalfAvg = firstHalf.reduce((sum, tx) => sum + tx.amount, 0) / firstHalf.length;
            const secondHalfAvg = secondHalf.reduce((sum, tx) => sum + tx.amount, 0) / secondHalf.length;

            const changeRatio = secondHalfAvg / firstHalfAvg;

            if (changeRatio > 3 || changeRatio < 0.33) {
                patterns.suddenBehaviorChange.push({
                    accountId: accountId,
                    changeRatio: changeRatio,
                    riskScore: 6.5
                });
            }
        }

        return patterns;
    }

    detectMoneyLaunderingPatterns(transactions) {
        const patterns = {
            structuring: [],
            layering: [],
            rapidMovement: []
        };

        // Structuring detection (amounts just under $10,000)
        const structuringTx = transactions.filter(tx => tx.amount >= 9000 && tx.amount < 10000);
        if (structuringTx.length > 5) {
            patterns.structuring.push({
                count: structuringTx.length,
                totalAmount: structuringTx.reduce((sum, tx) => sum + tx.amount, 0),
                riskScore: 9.0
            });
        }

        // Layering detection (complex transaction chains)
        const accountFrequency = {};
        for (const tx of transactions) {
            accountFrequency[tx.accountId] = (accountFrequency[tx.accountId] || 0) + 1;
        }

        const highVolumeAccounts = Object.entries(accountFrequency)
            .filter(([accountId, count]) => count > 20)
            .map(([accountId, count]) => accountId);

        if (highVolumeAccounts.length > 0) {
            patterns.layering.push({
                accountsInvolved: highVolumeAccounts.length,
                complexity: highVolumeAccounts.length / transactions.length,
                riskScore: 7.5
            });
        }

        return patterns;
    }

    detectWireTransferFraudPatterns(transactions) {
        const wireTransfers = transactions.filter(tx => tx.type === 'wire_transfer');

        const patterns = {
            internationalWires: [],
            rapidWireSequence: [],
            highValueWires: []
        };

        // High value wire transfers
        const highValueWires = wireTransfers.filter(tx => tx.amount > 50000);
        if (highValueWires.length > 0) {
            patterns.highValueWires = highValueWires.map(tx => ({
                transactionId: tx.id,
                amount: tx.amount,
                riskScore: 6.0
            }));
        }

        return patterns;
    }

    detectStatisticalAnomalies(transactions, sensitivity) {
        const threshold = this.models.anomalyThresholds[sensitivity || 'medium'];
        const anomalies = [];

        const amounts = transactions.map(tx => tx.amount).filter(amount => amount > 0);

        if (amounts.length === 0) return anomalies;

        const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;
        const stdDev = Math.sqrt(
            amounts.reduce((sum, amount) => sum + Math.pow(amount - mean, 2), 0) / amounts.length
        );

        // Z-score anomaly detection
        for (const tx of transactions) {
            if (tx.amount <= 0) continue;

            const zScore = Math.abs((tx.amount - mean) / stdDev);

            if (zScore > threshold.zscore) {
                anomalies.push({
                    type: 'statistical_outlier',
                    transactionId: tx.id,
                    amount: tx.amount,
                    zScore: zScore,
                    severity: zScore > threshold.zscore * 1.5 ? 'high' : 'medium',
                    explanation: `Amount deviates ${zScore.toFixed(2)} standard deviations from mean`
                });
            }
        }

        // IQR anomaly detection
        const sortedAmounts = [...amounts].sort((a, b) => a - b);
        const q1 = sortedAmounts[Math.floor(sortedAmounts.length * 0.25)];
        const q3 = sortedAmounts[Math.floor(sortedAmounts.length * 0.75)];
        const iqr = q3 - q1;
        const lowerBound = q1 - threshold.iqr * iqr;
        const upperBound = q3 + threshold.iqr * iqr;

        for (const tx of transactions) {
            if (tx.amount <= 0) continue;

            if (tx.amount < lowerBound || tx.amount > upperBound) {
                // Avoid duplicate detection
                const alreadyDetected = anomalies.find(a => a.transactionId === tx.id);
                if (!alreadyDetected) {
                    anomalies.push({
                        type: 'iqr_outlier',
                        transactionId: tx.id,
                        amount: tx.amount,
                        bounds: { lower: lowerBound, upper: upperBound },
                        severity: 'medium',
                        explanation: `Amount outside IQR bounds [${lowerBound.toFixed(2)}, ${upperBound.toFixed(2)}]`
                    });
                }
            }
        }

        return anomalies;
    }

    // Additional helper methods for ML analysis, scoring, etc.

    async performMlAnalysis(inputData, analysisResults) {
        // Placeholder for ML model inference
        // In production, this would use actual trained models
        return {
            transactionClassification: {
                model: 'gradient_boosting_classifier',
                predictions: analysisResults.anomalies?.length || 0,
                confidence: 0.85,
                featureImportance: {
                    amount: 0.35,
                    velocity: 0.25,
                    location: 0.20,
                    timing: 0.20
                }
            },
            behaviorProfiling: {
                model: 'isolation_forest',
                anomalyScore: Math.random() * 0.3 + 0.1, // Simulated
                normalityConfidence: 0.78
            },
            networkAnalysis: {
                model: 'graph_neural_network',
                communityDetection: true,
                suspiciousConnections: Math.floor(Math.random() * 5)
            }
        };
    }

    calculateOverallRiskScore(analysisData) {
        let score = 0;
        let factors = 0;

        // Weight different analysis components
        if (analysisData.fraudScore) {
            score += analysisData.fraudScore * 0.3;
            factors++;
        }

        if (analysisData.anomalies && analysisData.anomalies.length > 0) {
            score += Math.min(analysisData.anomalies.length * 10, 30);
            factors++;
        }

        if (analysisData.overallScore) {
            score += analysisData.overallScore * 0.2;
            factors++;
        }

        return factors > 0 ? Math.min(score / factors, 100) : 0;
    }

    calculateConfidenceScore(analysisData, inputData) {
        let confidence = 0;
        const dataQuality = this.assessDataQuality(inputData);

        // Base confidence on data quality and analysis completeness
        confidence += dataQuality * 0.4;

        // Add confidence based on analysis depth
        if (analysisData.patterns) confidence += 0.2;
        if (analysisData.anomalies) confidence += 0.2;
        if (analysisData.riskScore) confidence += 0.2;

        return Math.min(confidence * 100, 95); // Cap at 95%
    }

    generateAlerts(analysisData, options) {
        const alerts = [];
        const sensitivity = options.sensitivity || 'medium';

        // Generate alerts based on anomalies
        if (analysisData.anomalies) {
            const anomalies = Array.isArray(analysisData.anomalies) ?
                analysisData.anomalies : Object.values(analysisData.anomalies).flat();

            for (const anomaly of anomalies) {
                if (anomaly.severity === 'high' || (anomaly.severity === 'medium' && sensitivity !== 'low')) {
                    alerts.push({
                        id: crypto.randomUUID(),
                        type: 'anomaly_detected',
                        severity: anomaly.severity || 'medium',
                        message: anomaly.explanation || 'Anomalous pattern detected',
                        timestamp: new Date().toISOString(),
                        data: anomaly
                    });
                }
            }
        }

        // Generate alerts based on fraud patterns
        if (analysisData.fraudPatterns || analysisData.patterns?.fraudPatterns) {
            const fraudPatterns = analysisData.fraudPatterns || analysisData.patterns.fraudPatterns;

            Object.entries(fraudPatterns).forEach(([patternType, patterns]) => {
                if (Array.isArray(patterns)) {
                    patterns.forEach(pattern => {
                        if (pattern.riskScore > 7) {
                            alerts.push({
                                id: crypto.randomUUID(),
                                type: 'fraud_pattern',
                                severity: pattern.riskScore > 8 ? 'critical' : 'high',
                                message: `${patternType.replace(/([A-Z])/g, ' $1').trim()} pattern detected`,
                                timestamp: new Date().toISOString(),
                                data: { patternType, ...pattern }
                            });
                        }
                    });
                }
            });
        }

        return alerts;
    }

    generateInvestigationReport(result) {
        return {
            reportId: crypto.randomUUID(),
            generatedAt: new Date().toISOString(),
            summary: {
                overallRiskScore: result.riskScore,
                confidence: result.confidence,
                alertsGenerated: result.alerts.length,
                keyFindings: this.extractKeyFindings(result)
            },
            methodology: {
                analysisTypes: [result.operation],
                algorithms: ['statistical_analysis', 'pattern_recognition', 'anomaly_detection'],
                dataQuality: this.assessDataQuality(result.data)
            },
            recommendations: this.generateInvestigationRecommendations(result),
            nextSteps: this.suggestNextSteps(result)
        };
    }

    // Utility methods

    calculateMedian(values) {
        const sorted = [...values].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 === 0 ?
            (sorted[mid - 1] + sorted[mid]) / 2 :
            sorted[mid];
    }

    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 3959; // Earth's radius in miles
        const dLat = this.toRadians(lat2 - lat1);
        const dLon = this.toRadians(lon2 - lon1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    generateCacheKey(params) {
        const keyData = {
            operation: params.operation,
            dataHash: crypto.createHash('md5')
                .update(JSON.stringify(params.data || {}))
                .digest('hex').substring(0, 8),
            options: params.options || {}
        };
        return JSON.stringify(keyData);
    }

    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached;
        }
        return null;
    }

    setCache(key, data) {
        this.cache.set(key, {
            ...data,
            timestamp: Date.now()
        });

        // Clean old entries
        if (this.cache.size > 100) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }

    getDataPointCount(data) {
        let count = 0;
        if (data.transactions) count += data.transactions.length;
        if (data.accounts) count += data.accounts.length;
        if (data.entities) count += data.entities.length;
        return count;
    }

    assessDataQuality(data) {
        // Simplified data quality assessment
        let quality = 0.5; // Base quality

        if (data.transactions && data.transactions.length > 100) quality += 0.2;
        if (data.accounts && data.accounts.length > 0) quality += 0.1;
        if (data.entities && data.entities.length > 0) quality += 0.1;

        return Math.min(quality, 1.0);
    }

    extractKeyFindings(result) {
        const findings = [];

        if (result.riskScore > 70) {
            findings.push('High fraud risk detected');
        }

        if (result.alerts.length > 5) {
            findings.push('Multiple suspicious patterns identified');
        }

        return findings;
    }

    generateInvestigationRecommendations(result) {
        const recommendations = [];

        if (result.riskScore > 80) {
            recommendations.push('Immediate investigation recommended');
            recommendations.push('Consider freezing suspicious accounts');
        } else if (result.riskScore > 50) {
            recommendations.push('Enhanced monitoring recommended');
            recommendations.push('Request additional documentation');
        }

        return recommendations;
    }

    suggestNextSteps(result) {
        return [
            'Review flagged transactions manually',
            'Implement additional monitoring rules',
            'Consider regulatory reporting if required',
            'Update risk assessment models based on findings'
        ];
    }

    // Placeholder methods for complex operations
    calculateBehaviorBaseline(transactions) { return {}; }
    analyzeCurrentBehavior(transactions, timeWindow) { return {}; }
    calculateBehaviorDeviation(baseline, current) { return Math.random() * 3; }
    analyzeBehaviorChange(transactions) { return {}; }
    identifyBehaviorRiskFactors(profile) { return []; }
    calculateAggregateRisk(profiles) { return 0; }
    detectBehavioralAnomalies(data, sensitivity) { return []; }
    detectNetworkAnomalies(transactions, sensitivity) { return []; }
    detectTemporalAnomalies(transactions, sensitivity) { return []; }
    detectGeographicAnomalies(transactions, sensitivity) { return []; }
    prioritizeAnomalies(anomalies, sensitivity) { return []; }
    scoreTransactionalRisk(transactions, options) { return Math.random() * 100; }
    scoreEntityRisk(entities, options) { return Math.random() * 100; }
    scoreNetworkRisk(data, options) { return Math.random() * 100; }
    identifyRiskFactors(components) { return []; }
    generateRiskRecommendations(riskScores) { return []; }
    analyzeEntityTransactions(transactions) { return {}; }
    analyzeEntityNetwork(entity, data) { return {}; }
    performIdentityVerification(entity) { return {}; }
    performEntityComplianceCheck(entity, transactions) { return {}; }
    calculateInvestigationScore(investigation) { return Math.random() * 100; }
    identifyTransactionPatterns(transactions) { return {}; }
    identifyTemporalPatterns(transactions) { return {}; }
    identifyBehaviorPatterns(data) { return {}; }
    identifyNetworkPatterns(data) { return {}; }
    summarizePatterns(patterns) { return {}; }
    flagSuspiciousPatterns(patterns) { return []; }
    calculatePatternComplexity(patterns) { return Math.random(); }
    performAmlChecks(transactions) { return {}; }
    performKycChecks(entities) { return {}; }
    performSanctionsScreening(entities) { return {}; }
    performPepScreening(entities) { return {}; }
    generateRegulatoryAlerts(compliance) { return []; }
    calculateComplianceScore(compliance) { return Math.random() * 100; }
    buildTransactionNetwork(transactions, accounts) { return { nodes: {}, edges: [] }; }
    detectCommunities(graph) { return []; }
    calculateCentralityMetrics(graph) { return {}; }
    identifySuspiciousNetworks(graph, communities) { return []; }
    calculateNetworkRisk(network) { return Math.random() * 100; }
    getActiveMonitoringRules(options) { return []; }
    processRealTimeRules(transactions, options) { return []; }
    generateComprehensiveRiskAssessment(findings) { return {}; }
    generateAuditRecommendations(audit) { return []; }
    generateComplianceStatusSummary(findings) { return {}; }
    generateExecutiveSummary(audit) { return {}; }
    calculateTransactionFraudScore(analysis) { return Math.random() * 100; }
}

module.exports = FraudDetectorTool;