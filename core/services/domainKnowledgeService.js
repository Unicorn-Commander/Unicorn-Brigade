/**
 * Domain Knowledge Service
 * Manages domain-specific knowledge and distributes it to agents
 */

const { PrismaClient } = require('@prisma/client');
const agentMemory = require('../memory/agentMemory');
const EventEmitter = require('events');

const prisma = new PrismaClient();

class DomainKnowledgeService extends EventEmitter {
  constructor() {
    super();
    
    // Knowledge stores by domain
    this.domainKnowledge = new Map();
    
    // Agent-domain mapping
    this.agentDomains = new Map();
    
    // Knowledge update queue
    this.updateQueue = [];
    this.isProcessing = false;
    
    // Knowledge categories
    this.knowledgeCategories = {
      legal: ['case_law', 'regulations', 'precedents', 'procedures', 'contracts'],
      investigation: ['osint_techniques', 'evidence_handling', 'intelligence_methods', 'tools'],
      financial: ['fraud_patterns', 'regulations', 'analysis_methods', 'indicators'],
      crisis: ['protocols', 'communication_strategies', 'escalation_procedures'],
      administration: ['system_procedures', 'policies', 'workflows']
    };
    
    // Initialize knowledge stores
    this.initializeKnowledgeStores();
  }

  /**
   * Initialize knowledge stores for each domain
   */
  initializeKnowledgeStores() {
    const domains = ['legal', 'investigation', 'financial', 'crisis', 'administration', 'global'];
    
    domains.forEach(domain => {
      this.domainKnowledge.set(domain, {
        facts: [],           // Core facts and information
        procedures: [],      // Standard operating procedures
        bestPractices: [],   // Best practices and guidelines
        patterns: [],        // Patterns and insights
        tools: [],          // Available tools and resources
        contacts: [],       // Key contacts and resources
        updates: [],        // Recent updates and changes
        metadata: {
          lastUpdated: new Date(),
          version: '1.0.0',
          entryCount: 0
        }
      });
    });
  }

  /**
   * Add knowledge to a domain
   */
  async addDomainKnowledge(domain, category, knowledge) {
    if (!this.domainKnowledge.has(domain)) {
      throw new Error(`Unknown domain: ${domain}`);
    }
    
    const store = this.domainKnowledge.get(domain);
    const entry = {
      id: `${domain}_${category}_${Date.now()}`,
      category,
      content: knowledge.content,
      source: knowledge.source || 'system',
      confidence: knowledge.confidence || 0.8,
      tags: knowledge.tags || [],
      entities: knowledge.entities || [],
      importance: knowledge.importance || 0.5,
      expiresAt: knowledge.expiresAt || null,
      createdAt: new Date(),
      metadata: knowledge.metadata || {}
    };
    
    // Add to appropriate category
    if (store[category]) {
      store[category].push(entry);
    } else {
      store.updates.push(entry);
    }
    
    // Update metadata
    store.metadata.lastUpdated = new Date();
    store.metadata.entryCount++;
    
    // Queue distribution to agents
    this.queueKnowledgeUpdate(domain, entry);
    
    // Emit event
    this.emit('knowledge:added', { domain, category, entry });
    
    // Persist to database
    await this.persistKnowledge(domain, entry);
    
    return entry;
  }

  /**
   * Get knowledge for a domain
   */
  async getDomainKnowledge(domain, options = {}) {
    if (!this.domainKnowledge.has(domain)) {
      throw new Error(`Unknown domain: ${domain}`);
    }
    
    const store = this.domainKnowledge.get(domain);
    const {
      category = null,
      tags = [],
      minImportance = 0,
      limit = 100,
      includeExpired = false
    } = options;
    
    let knowledge = [];
    
    // Collect from specified category or all
    if (category && store[category]) {
      knowledge = [...store[category]];
    } else {
      Object.keys(store).forEach(key => {
        if (Array.isArray(store[key])) {
          knowledge.push(...store[key]);
        }
      });
    }
    
    // Apply filters
    knowledge = knowledge.filter(entry => {
      // Check expiration
      if (!includeExpired && entry.expiresAt && new Date(entry.expiresAt) < new Date()) {
        return false;
      }
      
      // Check importance
      if (entry.importance < minImportance) {
        return false;
      }
      
      // Check tags
      if (tags.length > 0 && !tags.some(tag => entry.tags.includes(tag))) {
        return false;
      }
      
      return true;
    });
    
    // Sort by importance and recency
    knowledge.sort((a, b) => {
      const importanceDiff = b.importance - a.importance;
      if (importanceDiff !== 0) return importanceDiff;
      
      return new Date(b.createdAt) - new Date(a.createdAt);
    });
    
    return knowledge.slice(0, limit);
  }

  /**
   * Search knowledge across domains
   */
  async searchKnowledge(query, options = {}) {
    const {
      domains = Array.from(this.domainKnowledge.keys()),
      limit = 50,
      threshold = 0.3
    } = options;
    
    const results = [];
    const queryLower = query.toLowerCase();
    const queryWords = queryLower.split(' ');
    
    for (const domain of domains) {
      const knowledge = await this.getDomainKnowledge(domain);
      
      knowledge.forEach(entry => {
        const content = JSON.stringify(entry).toLowerCase();
        const score = this.calculateRelevance(queryWords, content);
        
        if (score >= threshold) {
          results.push({
            ...entry,
            domain,
            relevanceScore: score
          });
        }
      });
    }
    
    // Sort by relevance
    results.sort((a, b) => b.relevanceScore - a.relevanceScore);
    
    return results.slice(0, limit);
  }

  /**
   * Calculate relevance score
   */
  calculateRelevance(queryWords, content) {
    let matches = 0;
    queryWords.forEach(word => {
      if (content.includes(word)) {
        matches++;
      }
    });
    
    return matches / queryWords.length;
  }

  /**
   * Queue knowledge update for distribution
   */
  queueKnowledgeUpdate(domain, knowledge) {
    this.updateQueue.push({
      domain,
      knowledge,
      timestamp: new Date()
    });
    
    // Process queue
    this.processUpdateQueue();
  }

  /**
   * Process knowledge update queue
   */
  async processUpdateQueue() {
    if (this.isProcessing || this.updateQueue.length === 0) return;
    
    this.isProcessing = true;
    
    while (this.updateQueue.length > 0) {
      const update = this.updateQueue.shift();
      
      try {
        await this.distributeKnowledgeToAgents(update.domain, update.knowledge);
      } catch (error) {
        console.error('Error distributing knowledge:', error);
      }
    }
    
    this.isProcessing = false;
  }

  /**
   * Distribute knowledge to relevant agents
   */
  async distributeKnowledgeToAgents(domain, knowledge) {
    // Get agents in this domain
    const agents = await this.getAgentsByDomain(domain);
    
    for (const agent of agents) {
      try {
        // Determine relevance for this specific agent
        const relevance = await this.assessRelevanceForAgent(agent, knowledge);
        
        if (relevance > 0.5) {
          // Store in agent's memory
          await agentMemory.storeMemory(agent.id, {
            type: 'domain_knowledge',
            content: `New ${domain} knowledge: ${knowledge.content}`,
            context: {
              domain,
              category: knowledge.category,
              source: knowledge.source
            },
            importance: knowledge.importance * relevance,
            tags: [...knowledge.tags, 'domain_update'],
            shareable: true,
            metadata: {
              knowledgeId: knowledge.id,
              distributedAt: new Date()
            }
          });
          
          console.log(`Distributed knowledge to agent ${agent.id} with relevance ${relevance}`);
        }
      } catch (error) {
        console.error(`Error distributing to agent ${agent.id}:`, error);
      }
    }
  }

  /**
   * Get agents by domain
   */
  async getAgentsByDomain(domain) {
    const agents = await prisma.agent.findMany({
      where: {
        OR: [
          { stats: { contains: `"domain":"${domain}"` } },
          { stats: { contains: '"domain":"global"' } }
        ]
      }
    });
    
    return agents.map(agent => ({
      ...agent,
      parsedStats: JSON.parse(agent.stats || '{}')
    }));
  }

  /**
   * Assess knowledge relevance for specific agent
   */
  async assessRelevanceForAgent(agent, knowledge) {
    const agentStats = agent.parsedStats || {};
    const agentType = agentStats.type || 'ic';
    
    // Base relevance on agent type
    let relevance = 0.5;
    
    // Knowledge agents get everything
    if (agentType === 'knowledge') {
      relevance = 1.0;
    }
    // Team leads get high-importance knowledge
    else if (agentType === 'team_lead' && knowledge.importance > 0.7) {
      relevance = 0.9;
    }
    // Orchestrators get critical knowledge
    else if (agentType === 'orchestrator' && knowledge.importance > 0.8) {
      relevance = 0.95;
    }
    // ICs get role-specific knowledge
    else if (agentType === 'ic') {
      // Check if knowledge matches agent capabilities
      const capabilities = JSON.parse(agent.capabilities || '[]');
      const matchingCaps = capabilities.filter(cap => 
        knowledge.content.toLowerCase().includes(cap.toLowerCase())
      );
      
      relevance = 0.3 + (matchingCaps.length * 0.2);
    }
    
    // Boost relevance for tagged matches
    const agentTags = agentStats.metadata?.tags || [];
    const matchingTags = knowledge.tags.filter(tag => agentTags.includes(tag));
    relevance += matchingTags.length * 0.1;
    
    return Math.min(relevance, 1.0);
  }

  /**
   * Consolidate domain knowledge
   */
  async consolidateDomainKnowledge(domain) {
    if (!this.domainKnowledge.has(domain)) {
      throw new Error(`Unknown domain: ${domain}`);
    }
    
    const store = this.domainKnowledge.get(domain);
    const consolidationResults = {};
    
    // Consolidate each category
    for (const category of Object.keys(store)) {
      if (!Array.isArray(store[category])) continue;
      
      const original = store[category];
      const consolidated = this.consolidateEntries(original);
      
      store[category] = consolidated;
      consolidationResults[category] = {
        original: original.length,
        consolidated: consolidated.length,
        reduction: ((original.length - consolidated.length) / original.length * 100).toFixed(2)
      };
    }
    
    // Update metadata
    store.metadata.lastUpdated = new Date();
    store.metadata.entryCount = Object.values(store)
      .filter(Array.isArray)
      .reduce((sum, arr) => sum + arr.length, 0);
    
    return consolidationResults;
  }

  /**
   * Consolidate knowledge entries
   */
  consolidateEntries(entries) {
    if (entries.length < 2) return entries;
    
    const groups = [];
    const used = new Set();
    
    for (let i = 0; i < entries.length; i++) {
      if (used.has(i)) continue;
      
      const group = [entries[i]];
      used.add(i);
      
      for (let j = i + 1; j < entries.length; j++) {
        if (used.has(j)) continue;
        
        // Check similarity
        const similarity = this.calculateSimilarity(
          entries[i].content,
          entries[j].content
        );
        
        if (similarity > 0.8) {
          group.push(entries[j]);
          used.add(j);
        }
      }
      
      groups.push(group);
    }
    
    // Create consolidated entries
    return groups.map(group => {
      if (group.length === 1) return group[0];
      
      // Merge similar entries
      return {
        id: `consolidated_${Date.now()}`,
        category: group[0].category,
        content: this.mergeContents(group.map(e => e.content)),
        source: 'consolidated',
        confidence: Math.max(...group.map(e => e.confidence)),
        tags: [...new Set(group.flatMap(e => e.tags))],
        entities: [...new Set(group.flatMap(e => e.entities))],
        importance: Math.max(...group.map(e => e.importance)),
        createdAt: new Date(),
        metadata: {
          originalCount: group.length,
          sources: group.map(e => e.source)
        }
      };
    });
  }

  /**
   * Calculate similarity between contents
   */
  calculateSimilarity(content1, content2) {
    const words1 = new Set(content1.toLowerCase().split(' '));
    const words2 = new Set(content2.toLowerCase().split(' '));
    
    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);
    
    return intersection.size / union.size;
  }

  /**
   * Merge multiple contents
   */
  mergeContents(contents) {
    // Remove duplicates and join
    const unique = [...new Set(contents)];
    if (unique.length === 1) return unique[0];
    
    return unique.join(' | ');
  }

  /**
   * Persist knowledge to database
   */
  async persistKnowledge(domain, entry) {
    try {
      await prisma.agentMemory.create({
        data: {
          id: entry.id,
          agentId: `domain-knowledge-${domain}`,
          type: 'domain_knowledge',
          category: domain,
          content: JSON.stringify(entry),
          metadata: JSON.stringify({
            domain,
            category: entry.category,
            source: entry.source,
            tags: entry.tags
          }),
          importance: entry.importance,
          accessCount: 0,
          lastAccessed: new Date()
        }
      });
    } catch (error) {
      console.error('Error persisting knowledge:', error);
    }
  }

  /**
   * Load knowledge from database
   */
  async loadKnowledgeFromDatabase() {
    try {
      const knowledgeEntries = await prisma.agentMemory.findMany({
        where: {
          type: 'domain_knowledge'
        }
      });
      
      knowledgeEntries.forEach(entry => {
        const content = JSON.parse(entry.content);
        const metadata = JSON.parse(entry.metadata || '{}');
        const domain = metadata.domain || 'global';
        
        if (this.domainKnowledge.has(domain)) {
          const store = this.domainKnowledge.get(domain);
          const category = content.category || 'updates';
          
          if (store[category]) {
            store[category].push(content);
          }
        }
      });
      
      console.log(`Loaded ${knowledgeEntries.length} knowledge entries from database`);
    } catch (error) {
      console.error('Error loading knowledge from database:', error);
    }
  }

  /**
   * Get knowledge statistics
   */
  getKnowledgeStats() {
    const stats = {
      domains: {},
      total: 0,
      byCategory: {},
      updateQueue: this.updateQueue.length
    };
    
    for (const [domain, store] of this.domainKnowledge) {
      const domainStats = {
        entryCount: store.metadata.entryCount,
        lastUpdated: store.metadata.lastUpdated,
        categories: {}
      };
      
      Object.keys(store).forEach(key => {
        if (Array.isArray(store[key])) {
          domainStats.categories[key] = store[key].length;
          stats.total += store[key].length;
          
          if (!stats.byCategory[key]) {
            stats.byCategory[key] = 0;
          }
          stats.byCategory[key] += store[key].length;
        }
      });
      
      stats.domains[domain] = domainStats;
    }
    
    return stats;
  }

  /**
   * Initialize with sample knowledge
   */
  async initializeSampleKnowledge() {
    const samples = {
      legal: {
        procedures: 'Always verify client identity and obtain proper authorization before proceeding with legal actions.',
        bestPractices: 'Document all communications and maintain chain of custody for evidence.',
        facts: 'Attorney-client privilege protects confidential communications.'
      },
      investigation: {
        procedures: 'Follow OSINT best practices and verify information from multiple sources.',
        tools: 'Use Maltego for entity relationship mapping and Shodan for infrastructure reconnaissance.',
        patterns: 'Social media correlation often reveals hidden connections between entities.'
      },
      financial: {
        patterns: 'Sudden large cash deposits followed by immediate transfers indicate potential money laundering.',
        regulations: 'SAR filing required for transactions over $10,000 or suspicious patterns.',
        indicators: 'Rapid account churning and layering are red flags for fraud.'
      }
    };
    
    for (const [domain, categories] of Object.entries(samples)) {
      for (const [category, content] of Object.entries(categories)) {
        await this.addDomainKnowledge(domain, category, {
          content,
          source: 'initial_setup',
          importance: 0.8,
          tags: ['core', 'essential']
        });
      }
    }
    
    console.log('Sample knowledge initialized');
  }
}

// Export singleton instance
module.exports = new DomainKnowledgeService();