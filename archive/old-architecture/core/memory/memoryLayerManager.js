const NodeCache = require('node-cache');
const agentMemoryService = require('./agentMemory');
const vectorMemoryService = require('./vectorMemoryService');
const contextualMemoryManager = require('./contextualMemoryManager');
const memoryAnalyticsService = require('./memoryAnalyticsService');
const memoryPersistenceLayer = require('./memoryPersistenceLayer');

/**
 * UC2 Unified Memory Layer Manager
 * Central orchestrator for all memory services and operations
 * Part of the Unicorn Command & Control Platform
 */
class MemoryLayerManager {
  constructor() {
    this.cache = new NodeCache({ stdTTL: 600 }); // 10 minutes cache for coordination
    this.operationQueue = new Map(); // Async operation queue
    this.memoryServices = {
      agent: agentMemoryService,
      vector: vectorMemoryService,
      contextual: contextualMemoryManager,
      analytics: memoryAnalyticsService,
      persistence: memoryPersistenceLayer
    };

    // Configuration
    this.autoTiering = true;
    this.autoBackup = true;
    this.analyticsEnabled = true;
    this.crossServiceSync = true;
    this.operationTimeout = 30000; // 30 seconds

    // Performance metrics
    this.metrics = {
      operations: new Map(),
      performance: new Map(),
      errors: new Map()
    };

    this.initializeServices();
    console.log('🧠 Memory Layer Manager initialized - All services coordinated');
  }

  /**
   * Initialize all memory services
   */
  async initializeServices() {
    try {
      console.log('🔄 Initializing memory services...');

      // Start background processes
      if (this.autoTiering) {
        this.startAutoTiering();
      }
      if (this.autoBackup) {
        this.startAutoBackup();
      }
      if (this.analyticsEnabled) {
        this.startAnalyticsCollection();
      }

      console.log('✅ All memory services initialized successfully');
    } catch (error) {
      console.error('❌ Error initializing memory services:', error);
    }
  }

  /**
   * Store memory across all appropriate services
   */
  async storeMemory(agentId, memory, options = {}) {
    const startTime = Date.now();
    const operationId = this.generateOperationId();

    try {
      const {
        storeInAgent = true,
        storeInVector = true,
        storeInContextual = true,
        storeInPersistence = true,
        context = {},
        tier = 'hot',
        compress = false,
        backup = this.autoBackup
      } = options;

      console.log(`💭 Storing memory across services [${operationId}]`);

      const results = {
        operationId,
        agentId,
        timestamp: new Date(),
        services: {},
        success: true,
        errors: []
      };

      // Store in parallel across all requested services
      const storagePromises = [];

      if (storeInAgent) {
        storagePromises.push(
          this.executeWithTimeout(
            () => this.memoryServices.agent.storeMemory(agentId, memory),
            'agent',
            results
          )
        );
      }

      if (storeInVector) {
        storagePromises.push(
          this.executeWithTimeout(
            () => this.memoryServices.vector.storeVectorMemory(agentId, memory),
            'vector',
            results
          )
        );
      }

      if (storeInContextual) {
        storagePromises.push(
          this.executeWithTimeout(
            () => this.memoryServices.contextual.storeContextualMemory(agentId, memory, context),
            'contextual',
            results
          )
        );
      }

      if (storeInPersistence) {
        storagePromises.push(
          this.executeWithTimeout(
            () => this.memoryServices.persistence.persistMemory(agentId, memory, {
              tier, compress, backup
            }),
            'persistence',
            results
          )
        );
      }

      // Wait for all storage operations
      await Promise.allSettled(storagePromises);

      // Calculate success rate
      const successful = Object.values(results.services).filter(s => s.success).length;
      const total = storagePromises.length;
      results.successRate = successful / total;
      results.success = results.successRate > 0.5; // Succeed if majority succeed

      // Record metrics
      this.recordOperation('store', Date.now() - startTime, results.success);

      // Trigger analytics update if enabled
      if (this.analyticsEnabled && results.success) {
        this.queueAnalyticsUpdate(agentId, 'store', memory);
      }

      console.log(`✅ Memory storage completed [${operationId}] - Success rate: ${(results.successRate * 100).toFixed(1)}%`);

      return results;

    } catch (error) {
      console.error(`❌ Error in unified memory storage [${operationId}]:`, error);
      this.recordOperation('store', Date.now() - startTime, false, error);
      throw error;
    }
  }

  /**
   * Retrieve memory with intelligent service selection
   */
  async retrieveMemory(agentId, memoryId, options = {}) {
    const startTime = Date.now();
    const operationId = this.generateOperationId();

    try {
      const {
        preferredService = 'auto',
        includeVector = false,
        includeContextual = false,
        includeAnalytics = false,
        searchOptions = {}
      } = options;

      console.log(`🔍 Retrieving memory [${operationId}]`);

      let memory = null;
      let retrievedFrom = null;

      // Try services in order of performance/preference
      const serviceOrder = this.getServiceOrder(preferredService);

      for (const serviceName of serviceOrder) {
        try {
          const service = this.memoryServices[serviceName];
          let result = null;

          switch (serviceName) {
            case 'agent':
              const memories = await service.retrieveMemories(agentId, {
                searchQuery: memoryId,
                limit: 1
              });
              result = memories.length > 0 ? memories[0] : null;
              break;

            case 'persistence':
              result = await service.retrieveMemory(agentId, memoryId);
              break;

            case 'contextual':
              result = await service.getContextualMemory(agentId, memoryId);
              break;

            default:
              continue;
          }

          if (result) {
            memory = result;
            retrievedFrom = serviceName;
            break;
          }
        } catch (error) {
          console.warn(`Service ${serviceName} failed to retrieve memory:`, error.message);
          continue;
        }
      }

      if (!memory) {
        this.recordOperation('retrieve', Date.now() - startTime, false);
        return null;
      }

      // Enhance with additional data if requested
      const enhancedResult = {
        memory,
        retrievedFrom,
        operationId,
        timestamp: new Date()
      };

      if (includeVector) {
        try {
          const vectorMemories = await this.memoryServices.vector.getVectorMemories(agentId, {
            limit: 5,
            includeEmbeddings: false
          });
          enhancedResult.relatedVectors = vectorMemories.slice(0, 3);
        } catch (error) {
          console.warn('Failed to get vector memories:', error.message);
        }
      }

      if (includeContextual) {
        try {
          const contextThread = await this.memoryServices.contextual.buildContextThread(
            agentId,
            memoryId,
            { maxDepth: 3 }
          );
          enhancedResult.contextThread = contextThread;
        } catch (error) {
          console.warn('Failed to build context thread:', error.message);
        }
      }

      this.recordOperation('retrieve', Date.now() - startTime, true);
      console.log(`✅ Memory retrieved [${operationId}] from ${retrievedFrom}`);

      return enhancedResult;

    } catch (error) {
      console.error(`❌ Error retrieving memory [${operationId}]:`, error);
      this.recordOperation('retrieve', Date.now() - startTime, false, error);
      throw error;
    }
  }

  /**
   * Semantic search across vector and contextual services
   */
  async searchMemories(agentId, query, options = {}) {
    const startTime = Date.now();
    const operationId = this.generateOperationId();

    try {
      const {
        limit = 10,
        threshold = 0.7,
        includeVector = true,
        includeContextual = true,
        includeAgent = true,
        mergeResults = true
      } = options;

      console.log(`🔎 Searching memories [${operationId}]: "${query}"`);

      const searchPromises = [];
      const results = {
        operationId,
        query,
        agentId,
        timestamp: new Date(),
        sources: {},
        combined: [],
        totalFound: 0
      };

      // Search across all requested services
      if (includeVector) {
        searchPromises.push(
          this.executeSearch('vector', () =>
            this.memoryServices.vector.semanticSearch(agentId, query, {
              limit: Math.ceil(limit / 2),
              threshold
            })
          ).then(result => {
            results.sources.vector = result;
            return result;
          }).catch(error => {
            console.warn('Vector search failed:', error.message);
            results.sources.vector = { success: false, error: error.message };
            return [];
          })
        );
      }

      if (includeContextual) {
        searchPromises.push(
          this.executeSearch('contextual', () =>
            this.memoryServices.contextual.getContextualMemories(agentId, {
              entities: [query],
              tags: [query]
            }, { limit: Math.ceil(limit / 2) })
          ).then(result => {
            results.sources.contextual = result;
            return result;
          }).catch(error => {
            console.warn('Contextual search failed:', error.message);
            results.sources.contextual = { success: false, error: error.message };
            return [];
          })
        );
      }

      if (includeAgent) {
        searchPromises.push(
          this.executeSearch('agent', () =>
            this.memoryServices.agent.searchMemories(agentId, query, {
              limit: Math.ceil(limit / 2),
              threshold
            })
          ).then(result => {
            results.sources.agent = result;
            return result;
          }).catch(error => {
            console.warn('Agent search failed:', error.message);
            results.sources.agent = { success: false, error: error.message };
            return [];
          })
        );
      }

      // Wait for all searches to complete
      const searchResults = await Promise.allSettled(searchPromises);

      // Merge and rank results if requested
      if (mergeResults) {
        const allResults = searchResults
          .filter(result => result.status === 'fulfilled' && Array.isArray(result.value))
          .flatMap(result => result.value);

        // Remove duplicates and rank by relevance/importance
        const uniqueResults = this.deduplicateMemories(allResults);
        const rankedResults = this.rankMemories(uniqueResults, query);

        results.combined = rankedResults.slice(0, limit);
        results.totalFound = uniqueResults.length;
      }

      this.recordOperation('search', Date.now() - startTime, true);
      console.log(`✅ Search completed [${operationId}] - Found ${results.totalFound} results`);

      return results;

    } catch (error) {
      console.error(`❌ Error searching memories [${operationId}]:`, error);
      this.recordOperation('search', Date.now() - startTime, false, error);
      throw error;
    }
  }

  /**
   * Generate comprehensive analytics report
   */
  async getAnalyticsReport(agentId, options = {}) {
    const startTime = Date.now();

    try {
      const {
        timeframe = 'week',
        includeRecommendations = true,
        includeInsights = true
      } = options;

      console.log(`📊 Generating analytics report for agent ${agentId}`);

      // Get analytics from analytics service
      const analyticsReport = await this.memoryServices.analytics.generateAnalyticsReport(
        agentId,
        { timeframe, includeInsights, includePredictions: true }
      );

      // Enhance with cross-service statistics
      const enhancedReport = {
        ...analyticsReport,
        crossServiceStats: await this.getCrossServiceStats(agentId),
        performanceMetrics: this.getPerformanceMetrics(agentId),
        serviceHealth: await this.getServiceHealth()
      };

      // Add recommendations if requested
      if (includeRecommendations) {
        enhancedReport.systemRecommendations = await this.generateSystemRecommendations(
          agentId,
          enhancedReport
        );
      }

      this.recordOperation('analytics', Date.now() - startTime, true);
      console.log(`✅ Analytics report generated for agent ${agentId}`);

      return enhancedReport;

    } catch (error) {
      console.error('❌ Error generating analytics report:', error);
      this.recordOperation('analytics', Date.now() - startTime, false, error);
      throw error;
    }
  }

  /**
   * Perform memory management operations
   */
  async performMaintenance(agentId, options = {}) {
    const startTime = Date.now();
    const operationId = this.generateOperationId();

    try {
      const {
        consolidateMemories = true,
        performTiering = true,
        createBackup = this.autoBackup,
        cleanupOld = true,
        updateAnalytics = true
      } = options;

      console.log(`🔧 Performing maintenance [${operationId}] for agent ${agentId}`);

      const results = {
        operationId,
        agentId,
        timestamp: new Date(),
        operations: {},
        success: true,
        errors: []
      };

      // Consolidate memories
      if (consolidateMemories) {
        try {
          const consolidation = await this.memoryServices.agent.consolidateMemories(agentId);
          results.operations.consolidation = {
            success: true,
            ...consolidation
          };
          console.log(`📦 Memory consolidation: ${consolidation.reduction}% reduction`);
        } catch (error) {
          results.operations.consolidation = { success: false, error: error.message };
          results.errors.push('consolidation failed');
        }
      }

      // Perform tiering
      if (performTiering) {
        try {
          const tiering = await this.memoryServices.persistence.performTiering(agentId, {
            maxOperations: 50
          });
          results.operations.tiering = {
            success: true,
            ...tiering.summary
          };
          console.log(`🏗️ Memory tiering: ${tiering.summary.totalOperations} operations`);
        } catch (error) {
          results.operations.tiering = { success: false, error: error.message };
          results.errors.push('tiering failed');
        }
      }

      // Create backup
      if (createBackup) {
        try {
          const backup = await this.memoryServices.persistence.createBackup(agentId, {
            includeAllTiers: false, // Only backup active memories
            compress: true
          });
          results.operations.backup = {
            success: true,
            backupId: backup.backupId,
            totalSize: backup.statistics.totalSize
          };
          console.log(`💾 Backup created: ${backup.backupId}`);
        } catch (error) {
          results.operations.backup = { success: false, error: error.message };
          results.errors.push('backup failed');
        }
      }

      // Cleanup old memories
      if (cleanupOld) {
        try {
          const cleanup = await this.memoryServices.persistence.cleanupMemories(agentId, {
            olderThanDays: 120,
            minImportance: 0.2,
            maxDeletions: 100
          });
          results.operations.cleanup = {
            success: true,
            ...cleanup.summary
          };
          console.log(`🧹 Cleanup: ${cleanup.deleted} memories removed`);
        } catch (error) {
          results.operations.cleanup = { success: false, error: error.message };
          results.errors.push('cleanup failed');
        }
      }

      // Update analytics
      if (updateAnalytics) {
        try {
          await this.queueAnalyticsUpdate(agentId, 'maintenance', results);
          results.operations.analytics = { success: true, queued: true };
        } catch (error) {
          results.operations.analytics = { success: false, error: error.message };
          results.errors.push('analytics update failed');
        }
      }

      results.success = results.errors.length === 0;
      this.recordOperation('maintenance', Date.now() - startTime, results.success);

      console.log(`✅ Maintenance completed [${operationId}] - ${results.errors.length} errors`);

      return results;

    } catch (error) {
      console.error(`❌ Error performing maintenance [${operationId}]:`, error);
      this.recordOperation('maintenance', Date.now() - startTime, false, error);
      throw error;
    }
  }

  // Background processes

  /**
   * Start automatic tiering process
   */
  startAutoTiering() {
    console.log('🔄 Starting auto-tiering process...');

    setInterval(async () => {
      try {
        // Get all agents with significant memory
        const agents = await this.getActiveAgents();

        for (const agentId of agents) {
          try {
            await this.memoryServices.persistence.performTiering(agentId, {
              dryRun: false,
              maxOperations: 25
            });
          } catch (error) {
            console.warn(`Auto-tiering failed for agent ${agentId}:`, error.message);
          }
        }
      } catch (error) {
        console.error('Auto-tiering process error:', error);
      }
    }, 4 * 60 * 60 * 1000); // Every 4 hours
  }

  /**
   * Start automatic backup process
   */
  startAutoBackup() {
    console.log('💾 Starting auto-backup process...');

    setInterval(async () => {
      try {
        const agents = await this.getActiveAgents();

        for (const agentId of agents) {
          try {
            await this.memoryServices.persistence.createBackup(agentId, {
              includeAllTiers: false,
              compress: true,
              metadata: { type: 'automatic', creator: 'memory_layer_manager' }
            });
          } catch (error) {
            console.warn(`Auto-backup failed for agent ${agentId}:`, error.message);
          }
        }
      } catch (error) {
        console.error('Auto-backup process error:', error);
      }
    }, 24 * 60 * 60 * 1000); // Daily backups
  }

  /**
   * Start analytics collection process
   */
  startAnalyticsCollection() {
    console.log('📊 Starting analytics collection...');

    setInterval(async () => {
      try {
        // Process queued analytics updates
        const updates = Array.from(this.operationQueue.values());
        this.operationQueue.clear();

        if (updates.length > 0) {
          console.log(`📈 Processing ${updates.length} analytics updates`);
        }
      } catch (error) {
        console.error('Analytics collection error:', error);
      }
    }, 10 * 60 * 1000); // Every 10 minutes
  }

  // Helper methods

  async executeWithTimeout(operation, serviceName, results) {
    const startTime = Date.now();

    try {
      const result = await Promise.race([
        operation(),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), this.operationTimeout)
        )
      ]);

      results.services[serviceName] = {
        success: true,
        result,
        duration: Date.now() - startTime
      };

      return result;
    } catch (error) {
      results.services[serviceName] = {
        success: false,
        error: error.message,
        duration: Date.now() - startTime
      };
      results.errors.push(`${serviceName}: ${error.message}`);
      throw error;
    }
  }

  async executeSearch(serviceName, searchFn) {
    const startTime = Date.now();

    try {
      const result = await Promise.race([
        searchFn(),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Search timeout')), this.operationTimeout)
        )
      ]);

      return Array.isArray(result) ? result : [];
    } catch (error) {
      console.warn(`Search failed for ${serviceName}:`, error.message);
      return [];
    }
  }

  getServiceOrder(preferredService) {
    if (preferredService !== 'auto') {
      return [preferredService, 'agent', 'contextual', 'persistence'];
    }

    // Intelligent ordering based on performance metrics
    return ['agent', 'contextual', 'persistence', 'vector'];
  }

  deduplicateMemories(memories) {
    const seen = new Set();
    const unique = [];

    for (const memory of memories) {
      const key = memory.content || memory.id || JSON.stringify(memory);
      const hash = require('crypto').createHash('md5').update(key).digest('hex');

      if (!seen.has(hash)) {
        seen.add(hash);
        unique.push(memory);
      }
    }

    return unique;
  }

  rankMemories(memories, query) {
    return memories
      .map(memory => ({
        ...memory,
        combinedScore: (memory.relevanceScore || memory.importance || 0.5) +
                      (memory.accessCount || 0) * 0.01 +
                      (memory.similarity || 0) * 0.5
      }))
      .sort((a, b) => b.combinedScore - a.combinedScore);
  }

  async getCrossServiceStats(agentId) {
    try {
      const [agentStats, vectorStats, contextualStats, persistenceStats] = await Promise.allSettled([
        this.memoryServices.agent.getMemoryStats(agentId),
        this.memoryServices.vector.getServiceInfo(),
        this.memoryServices.contextual.getServiceInfo(),
        this.memoryServices.persistence.getStorageStatistics(agentId)
      ]);

      return {
        agent: agentStats.status === 'fulfilled' ? agentStats.value : null,
        vector: vectorStats.status === 'fulfilled' ? vectorStats.value : null,
        contextual: contextualStats.status === 'fulfilled' ? contextualStats.value : null,
        persistence: persistenceStats.status === 'fulfilled' ? persistenceStats.value : null
      };
    } catch (error) {
      console.error('Error getting cross-service stats:', error);
      return {};
    }
  }

  getPerformanceMetrics(agentId) {
    const metrics = {
      operations: {},
      averageResponseTime: 0,
      successRate: 0,
      errorRate: 0
    };

    // Calculate metrics from recorded operations
    for (const [operation, times] of this.metrics.operations) {
      metrics.operations[operation] = {
        count: times.length,
        averageTime: times.reduce((sum, time) => sum + time, 0) / times.length || 0,
        successCount: times.filter(t => t.success).length
      };
    }

    // Calculate overall metrics
    const allTimes = Array.from(this.metrics.operations.values()).flat();
    if (allTimes.length > 0) {
      metrics.averageResponseTime = allTimes.reduce((sum, t) => sum + t.duration, 0) / allTimes.length;
      metrics.successRate = allTimes.filter(t => t.success).length / allTimes.length;
      metrics.errorRate = 1 - metrics.successRate;
    }

    return metrics;
  }

  async getServiceHealth() {
    const health = {};

    for (const [name, service] of Object.entries(this.memoryServices)) {
      try {
        if (typeof service.getServiceInfo === 'function') {
          const info = service.getServiceInfo();
          health[name] = {
            status: info.status || 'unknown',
            capabilities: info.capabilities || [],
            version: info.version || '1.0.0'
          };
        } else {
          health[name] = { status: 'operational', note: 'No health check available' };
        }
      } catch (error) {
        health[name] = { status: 'error', error: error.message };
      }
    }

    return health;
  }

  async generateSystemRecommendations(agentId, analyticsReport) {
    const recommendations = [];

    // Memory growth recommendations
    if (analyticsReport.basicStats?.totalMemories > 1000) {
      recommendations.push({
        category: 'performance',
        priority: 'high',
        title: 'Implement Aggressive Memory Consolidation',
        description: 'High memory count detected. Consider more frequent consolidation.',
        action: 'Schedule daily memory consolidation'
      });
    }

    // Service performance recommendations
    const avgResponseTime = this.getPerformanceMetrics(agentId).averageResponseTime;
    if (avgResponseTime > 2000) {
      recommendations.push({
        category: 'performance',
        priority: 'medium',
        title: 'Optimize Memory Access Patterns',
        description: 'High response times detected across memory operations.',
        action: 'Enable additional caching layers'
      });
    }

    return recommendations;
  }

  recordOperation(operation, duration, success, error = null) {
    if (!this.metrics.operations.has(operation)) {
      this.metrics.operations.set(operation, []);
    }

    this.metrics.operations.get(operation).push({
      timestamp: Date.now(),
      duration,
      success,
      error: error?.message
    });

    // Keep only last 100 operations per type
    const operations = this.metrics.operations.get(operation);
    if (operations.length > 100) {
      operations.splice(0, operations.length - 100);
    }
  }

  queueAnalyticsUpdate(agentId, operation, data) {
    const updateId = `${agentId}_${operation}_${Date.now()}`;
    this.operationQueue.set(updateId, {
      agentId,
      operation,
      data,
      timestamp: Date.now()
    });
  }

  async getActiveAgents() {
    // Mock implementation - would query database for active agents
    return ['agent_001', 'agent_002', 'agent_003'];
  }

  generateOperationId() {
    return require('crypto').randomBytes(4).toString('hex');
  }

  /**
   * Get comprehensive system status
   */
  async getSystemStatus() {
    try {
      const status = {
        timestamp: new Date(),
        manager: {
          status: 'operational',
          version: '1.0.0',
          uptime: process.uptime(),
          configuration: {
            autoTiering: this.autoTiering,
            autoBackup: this.autoBackup,
            analyticsEnabled: this.analyticsEnabled,
            crossServiceSync: this.crossServiceSync
          }
        },
        services: await this.getServiceHealth(),
        performance: {
          operationQueue: this.operationQueue.size,
          cacheSize: this.cache.keys().length,
          totalOperations: Array.from(this.metrics.operations.values())
            .reduce((sum, ops) => sum + ops.length, 0)
        },
        backgroundProcesses: {
          autoTiering: { enabled: this.autoTiering, interval: '4 hours' },
          autoBackup: { enabled: this.autoBackup, interval: '24 hours' },
          analytics: { enabled: this.analyticsEnabled, interval: '10 minutes' }
        }
      };

      return status;
    } catch (error) {
      console.error('Error getting system status:', error);
      return {
        timestamp: new Date(),
        status: 'error',
        error: error.message
      };
    }
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'UC2 Memory Layer Manager',
      version: '1.0.0',
      description: 'Unified orchestrator for all memory services and operations',
      capabilities: [
        'Cross-service memory orchestration',
        'Intelligent service selection',
        'Unified search and retrieval',
        'Automated maintenance',
        'Performance monitoring',
        'Background processes',
        'Service health monitoring',
        'Analytics coordination'
      ],
      status: 'operational',
      managedServices: Object.keys(this.memoryServices),
      activeOperations: this.operationQueue.size,
      performanceMetrics: {
        totalOperations: Array.from(this.metrics.operations.values())
          .reduce((sum, ops) => sum + ops.length, 0),
        averageResponseTime: this.getPerformanceMetrics().averageResponseTime,
        successRate: this.getPerformanceMetrics().successRate
      },
      configuration: {
        autoTiering: this.autoTiering,
        autoBackup: this.autoBackup,
        analyticsEnabled: this.analyticsEnabled,
        operationTimeout: this.operationTimeout
      }
    };
  }
}

module.exports = new MemoryLayerManager();