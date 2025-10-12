const NodeCache = require('node-cache');
const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');

const prisma = new PrismaClient();

/**
 * UC2 Contextual Memory Manager
 * Advanced context-aware memory management with temporal relationships
 * Part of the Unicorn Command & Control Platform
 */
class ContextualMemoryManager {
  constructor() {
    this.cache = new NodeCache({ stdTTL: 1800 }); // 30 minutes cache
    this.contextGraph = new Map(); // Context relationship graph
    this.temporalIndex = new Map(); // Time-based memory indexing
    this.contextTypes = new Set([
      'conversation', 'task', 'session', 'project', 'case',
      'investigation', 'analysis', 'planning', 'execution'
    ]);

    // Configuration
    this.maxContextDepth = 5;
    this.contextWindow = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
    this.relevanceThreshold = 0.6;

    console.log('🧠 Contextual Memory Manager initialized');
  }

  /**
   * Store memory with contextual relationships
   */
  async storeContextualMemory(agentId, memory, context = {}) {
    try {
      const memoryId = this.generateMemoryId(agentId, memory.content);

      const contextualMemory = {
        id: memoryId,
        agentId,
        type: memory.type || 'contextual',
        content: memory.content,
        context: {
          ...context,
          timestamp: new Date(),
          sessionId: context.sessionId || this.generateSessionId(),
          conversationId: context.conversationId,
          taskId: context.taskId,
          projectId: context.projectId,
          parentMemoryId: context.parentMemoryId,
          tags: context.tags || [],
          entities: context.entities || [],
          location: context.location,
          priority: context.priority || 'normal'
        },
        importance: memory.importance || this.calculateImportance(memory, context),
        timestamp: new Date(),
        metadata: {
          source: memory.source || 'contextual_manager',
          processingTime: Date.now(),
          contextType: context.type || 'general',
          relationships: context.relationships || [],
          temporalMarkers: this.extractTemporalMarkers(memory.content),
          entityReferences: this.extractEntityReferences(memory.content),
          actionItems: this.extractActionItems(memory.content)
        }
      };

      // Store in database
      await prisma.contextualMemory.create({
        data: {
          id: memoryId,
          agentId,
          type: contextualMemory.type,
          content: contextualMemory.content,
          context: JSON.stringify(contextualMemory.context),
          importance: contextualMemory.importance,
          metadata: JSON.stringify(contextualMemory.metadata)
        }
      }).catch(async (error) => {
        // Create table if it doesn't exist
        if (error.code === 'P2021') {
          await this.createContextualMemoryTable();
          return prisma.contextualMemory.create({
            data: {
              id: memoryId,
              agentId,
              type: contextualMemory.type,
              content: contextualMemory.content,
              context: JSON.stringify(contextualMemory.context),
              importance: contextualMemory.importance,
              metadata: JSON.stringify(contextualMemory.metadata)
            }
          });
        }
        throw error;
      });

      // Update context graph
      await this.updateContextGraph(contextualMemory);

      // Update temporal index
      this.updateTemporalIndex(contextualMemory);

      // Cache the memory
      this.cache.set(memoryId, contextualMemory);

      return contextualMemory;
    } catch (error) {
      console.error('Error storing contextual memory:', error);
      throw error;
    }
  }

  /**
   * Create contextual memory table
   */
  async createContextualMemoryTable() {
    try {
      await prisma.$executeRaw`
        CREATE TABLE IF NOT EXISTS "ContextualMemory" (
          "id" TEXT NOT NULL PRIMARY KEY,
          "agentId" TEXT NOT NULL,
          "type" TEXT NOT NULL DEFAULT 'contextual',
          "content" TEXT NOT NULL,
          "context" TEXT NOT NULL DEFAULT '{}',
          "importance" REAL NOT NULL DEFAULT 0.5,
          "metadata" TEXT NOT NULL DEFAULT '{}',
          "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
      `;
      console.log('✅ ContextualMemory table created successfully');
    } catch (error) {
      console.log('ContextualMemory table may already exist:', error.message);
    }
  }

  /**
   * Update context relationship graph
   */
  async updateContextGraph(memory) {
    const contextKey = `${memory.agentId}_${memory.context.sessionId}`;

    if (!this.contextGraph.has(contextKey)) {
      this.contextGraph.set(contextKey, {
        sessionId: memory.context.sessionId,
        agentId: memory.agentId,
        memories: new Map(),
        relationships: new Map(),
        timeline: [],
        entities: new Set(),
        topics: new Set()
      });
    }

    const contextData = this.contextGraph.get(contextKey);

    // Add memory to context
    contextData.memories.set(memory.id, memory);
    contextData.timeline.push({
      memoryId: memory.id,
      timestamp: memory.timestamp,
      type: memory.type,
      importance: memory.importance
    });

    // Track entities and topics
    if (memory.metadata.entityReferences) {
      memory.metadata.entityReferences.forEach(entity =>
        contextData.entities.add(entity)
      );
    }

    if (memory.context.tags) {
      memory.context.tags.forEach(tag =>
        contextData.topics.add(tag)
      );
    }

    // Create relationships with parent memory
    if (memory.context.parentMemoryId) {
      if (!contextData.relationships.has(memory.context.parentMemoryId)) {
        contextData.relationships.set(memory.context.parentMemoryId, []);
      }
      contextData.relationships.get(memory.context.parentMemoryId).push(memory.id);
    }

    // Sort timeline by timestamp
    contextData.timeline.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Limit context size (keep last 100 memories per context)
    if (contextData.memories.size > 100) {
      const oldestMemoryId = contextData.timeline.shift().memoryId;
      contextData.memories.delete(oldestMemoryId);
      contextData.relationships.delete(oldestMemoryId);
    }
  }

  /**
   * Update temporal index for time-based queries
   */
  updateTemporalIndex(memory) {
    const timeKey = this.getTimeKey(memory.timestamp);

    if (!this.temporalIndex.has(timeKey)) {
      this.temporalIndex.set(timeKey, []);
    }

    this.temporalIndex.get(timeKey).push({
      memoryId: memory.id,
      agentId: memory.agentId,
      importance: memory.importance,
      timestamp: memory.timestamp,
      contextType: memory.metadata.contextType
    });

    // Clean old entries (keep last 7 days)
    const cutoffTime = Date.now() - (7 * 24 * 60 * 60 * 1000);
    for (const [key, entries] of this.temporalIndex) {
      const filtered = entries.filter(entry =>
        new Date(entry.timestamp).getTime() > cutoffTime
      );
      if (filtered.length === 0) {
        this.temporalIndex.delete(key);
      } else {
        this.temporalIndex.set(key, filtered);
      }
    }
  }

  /**
   * Retrieve contextual memories with relationship awareness
   */
  async getContextualMemories(agentId, context, options = {}) {
    try {
      const {
        limit = 20,
        includeRelated = true,
        timeWindow = this.contextWindow,
        minImportance = 0.3
      } = options;

      // Build context-aware query
      const where = {
        agentId,
        importance: { gte: minImportance },
        createdAt: {
          gte: new Date(Date.now() - timeWindow)
        }
      };

      // Add context filters
      if (context.sessionId) {
        where.context = { contains: `"sessionId":"${context.sessionId}"` };
      }
      if (context.projectId) {
        where.OR = [
          { context: { contains: `"projectId":"${context.projectId}"` } },
          ...(where.OR || [])
        ];
      }

      const memories = await prisma.contextualMemory.findMany({
        where,
        orderBy: [
          { importance: 'desc' },
          { createdAt: 'desc' }
        ],
        take: limit
      });

      // Parse and enhance memories
      const enhancedMemories = memories.map(memory => ({
        ...memory,
        context: JSON.parse(memory.context || '{}'),
        metadata: JSON.parse(memory.metadata || '{}')
      }));

      // Include related memories if requested
      if (includeRelated) {
        const relatedMemories = await this.getRelatedMemories(
          agentId,
          enhancedMemories,
          { limit: Math.floor(limit * 0.3) }
        );
        enhancedMemories.push(...relatedMemories);
      }

      // Sort by relevance score
      return this.rankMemoriesByRelevance(enhancedMemories, context);

    } catch (error) {
      console.error('Error getting contextual memories:', error);
      return this.generateMockContextualMemories(agentId, Math.min(limit, 5));
    }
  }

  /**
   * Get related memories based on context relationships
   */
  async getRelatedMemories(agentId, baseMemories, options = {}) {
    const { limit = 10 } = options;
    const relatedIds = new Set();
    const related = [];

    // Find related memories through context graph
    for (const memory of baseMemories) {
      const contextKey = `${memory.agentId}_${memory.context.sessionId}`;
      const contextData = this.contextGraph.get(contextKey);

      if (contextData) {
        // Get parent/child relationships
        if (memory.context.parentMemoryId &&
            contextData.memories.has(memory.context.parentMemoryId)) {
          relatedIds.add(memory.context.parentMemoryId);
        }

        // Get child memories
        const children = contextData.relationships.get(memory.id) || [];
        children.forEach(childId => relatedIds.add(childId));

        // Get memories from same entities
        for (const [memId, mem] of contextData.memories) {
          if (mem.metadata.entityReferences) {
            const hasCommonEntities = mem.metadata.entityReferences.some(entity =>
              memory.metadata.entityReferences?.includes(entity)
            );
            if (hasCommonEntities) {
              relatedIds.add(memId);
            }
          }
        }
      }
    }

    // Fetch related memories from database if not in context graph
    if (relatedIds.size > 0) {
      const relatedMemories = await prisma.contextualMemory.findMany({
        where: {
          agentId,
          id: { in: Array.from(relatedIds) }
        },
        take: limit
      });

      related.push(...relatedMemories.map(memory => ({
        ...memory,
        context: JSON.parse(memory.context || '{}'),
        metadata: JSON.parse(memory.metadata || '{}'),
        isRelated: true
      })));
    }

    return related;
  }

  /**
   * Rank memories by contextual relevance
   */
  rankMemoriesByRelevance(memories, context) {
    return memories.map(memory => {
      let relevanceScore = memory.importance || 0.5;

      // Boost score for context matches
      if (memory.context.sessionId === context.sessionId) {
        relevanceScore += 0.3;
      }
      if (memory.context.projectId === context.projectId) {
        relevanceScore += 0.2;
      }
      if (memory.context.taskId === context.taskId) {
        relevanceScore += 0.2;
      }

      // Boost score for recent memories
      const ageHours = (Date.now() - new Date(memory.timestamp).getTime()) / (1000 * 60 * 60);
      if (ageHours < 1) relevanceScore += 0.2;
      else if (ageHours < 6) relevanceScore += 0.1;

      // Boost score for entity matches
      if (context.entities && memory.metadata.entityReferences) {
        const commonEntities = context.entities.filter(entity =>
          memory.metadata.entityReferences.includes(entity)
        );
        relevanceScore += commonEntities.length * 0.1;
      }

      return {
        ...memory,
        relevanceScore: Math.min(relevanceScore, 1.0)
      };
    })
    .sort((a, b) => b.relevanceScore - a.relevanceScore);
  }

  /**
   * Build context thread from related memories
   */
  async buildContextThread(agentId, memoryId, options = {}) {
    try {
      const { maxDepth = this.maxContextDepth } = options;

      const rootMemory = await this.getContextualMemory(agentId, memoryId);
      if (!rootMemory) {
        return { thread: [], totalMemories: 0 };
      }

      const thread = [rootMemory];
      const visited = new Set([memoryId]);

      // Build thread by following relationships
      await this.buildThreadRecursively(
        agentId,
        rootMemory,
        thread,
        visited,
        maxDepth,
        0
      );

      // Sort thread chronologically
      thread.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

      return {
        thread,
        totalMemories: thread.length,
        timeSpan: {
          start: thread[0]?.timestamp,
          end: thread[thread.length - 1]?.timestamp
        },
        entities: [...new Set(thread.flatMap(m => m.metadata.entityReferences || []))],
        topics: [...new Set(thread.flatMap(m => m.context.tags || []))]
      };

    } catch (error) {
      console.error('Error building context thread:', error);
      return { thread: [], totalMemories: 0 };
    }
  }

  /**
   * Recursively build context thread
   */
  async buildThreadRecursively(agentId, currentMemory, thread, visited, maxDepth, depth) {
    if (depth >= maxDepth) return;

    const contextKey = `${agentId}_${currentMemory.context.sessionId}`;
    const contextData = this.contextGraph.get(contextKey);

    if (contextData) {
      // Get parent memory
      if (currentMemory.context.parentMemoryId &&
          !visited.has(currentMemory.context.parentMemoryId)) {
        const parentMemory = contextData.memories.get(currentMemory.context.parentMemoryId);
        if (parentMemory) {
          thread.push(parentMemory);
          visited.add(parentMemory.id);
          await this.buildThreadRecursively(
            agentId, parentMemory, thread, visited, maxDepth, depth + 1
          );
        }
      }

      // Get child memories
      const children = contextData.relationships.get(currentMemory.id) || [];
      for (const childId of children) {
        if (!visited.has(childId)) {
          const childMemory = contextData.memories.get(childId);
          if (childMemory) {
            thread.push(childMemory);
            visited.add(childId);
            await this.buildThreadRecursively(
              agentId, childMemory, thread, visited, maxDepth, depth + 1
            );
          }
        }
      }
    }
  }

  /**
   * Get single contextual memory
   */
  async getContextualMemory(agentId, memoryId) {
    try {
      // Check cache first
      if (this.cache.has(memoryId)) {
        return this.cache.get(memoryId);
      }

      const memory = await prisma.contextualMemory.findUnique({
        where: { id: memoryId }
      });

      if (memory && memory.agentId === agentId) {
        const parsed = {
          ...memory,
          context: JSON.parse(memory.context || '{}'),
          metadata: JSON.parse(memory.metadata || '{}')
        };

        this.cache.set(memoryId, parsed);
        return parsed;
      }

      return null;
    } catch (error) {
      console.error('Error getting contextual memory:', error);
      return null;
    }
  }

  /**
   * Calculate importance score for memory
   */
  calculateImportance(memory, context) {
    let importance = 0.5; // Base importance

    // Boost for certain types
    const typeBoosts = {
      'error': 0.8,
      'warning': 0.7,
      'success': 0.6,
      'task_completion': 0.8,
      'user_feedback': 0.7
    };

    importance = typeBoosts[memory.type] || importance;

    // Boost for priority context
    const priorityBoosts = {
      'critical': 0.9,
      'high': 0.8,
      'normal': 0.5,
      'low': 0.3
    };

    importance = Math.max(importance, priorityBoosts[context.priority] || 0.5);

    // Boost for action items
    if (memory.content.includes('TODO') || memory.content.includes('ACTION')) {
      importance += 0.2;
    }

    // Boost for questions
    if (memory.content.includes('?')) {
      importance += 0.1;
    }

    return Math.min(importance, 1.0);
  }

  /**
   * Extract temporal markers from content
   */
  extractTemporalMarkers(content) {
    const markers = [];
    const timePatterns = [
      /\b(today|tomorrow|yesterday)\b/gi,
      /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/gi,
      /\b\d{1,2}:\d{2}\s*(am|pm)?\b/gi,
      /\b\d{1,2}\/\d{1,2}\/\d{2,4}\b/gi,
      /\b(next|last|this)\s+(week|month|year)\b/gi,
      /\bin\s+\d+\s+(minutes?|hours?|days?|weeks?)\b/gi
    ];

    timePatterns.forEach(pattern => {
      const matches = content.match(pattern);
      if (matches) {
        markers.push(...matches.map(m => m.toLowerCase()));
      }
    });

    return [...new Set(markers)];
  }

  /**
   * Extract entity references from content
   */
  extractEntityReferences(content) {
    const entities = [];

    // Extract @mentions
    const mentions = content.match(/@\w+/g) || [];
    entities.push(...mentions);

    // Extract #hashtags
    const hashtags = content.match(/#\w+/g) || [];
    entities.push(...hashtags);

    // Extract capitalized words (potential names/entities)
    const capitalizedWords = content.match(/\b[A-Z][a-z]+\b/g) || [];
    entities.push(...capitalizedWords.slice(0, 5)); // Limit to first 5

    return [...new Set(entities)];
  }

  /**
   * Extract action items from content
   */
  extractActionItems(content) {
    const actionItems = [];
    const actionPatterns = [
      /TODO:?\s*([^\n]+)/gi,
      /ACTION:?\s*([^\n]+)/gi,
      /TASK:?\s*([^\n]+)/gi,
      /\[ \]\s*([^\n]+)/gi, // Checkbox items
      /need to\s+([^\n]+)/gi,
      /should\s+([^\n]+)/gi,
      /must\s+([^\n]+)/gi
    ];

    actionPatterns.forEach(pattern => {
      const matches = [...content.matchAll(pattern)];
      matches.forEach(match => {
        actionItems.push({
          text: match[1] ? match[1].trim() : match[0].trim(),
          type: match[0].toLowerCase().includes('todo') ? 'todo' :
                match[0].toLowerCase().includes('action') ? 'action' :
                match[0].toLowerCase().includes('task') ? 'task' : 'general',
          priority: content.toLowerCase().includes('urgent') ? 'high' : 'normal'
        });
      });
    });

    return actionItems;
  }

  /**
   * Generate time-based key for temporal indexing
   */
  getTimeKey(timestamp) {
    const date = new Date(timestamp);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  /**
   * Generate session ID
   */
  generateSessionId() {
    return crypto.randomBytes(8).toString('hex');
  }

  /**
   * Generate memory ID
   */
  generateMemoryId(agentId, content) {
    return crypto
      .createHash('sha256')
      .update(`contextual_${agentId}_${content}_${Date.now()}`)
      .digest('hex')
      .substring(0, 16);
  }

  /**
   * Generate mock contextual memories
   */
  generateMockContextualMemories(agentId, count = 5) {
    const sessionId = this.generateSessionId();

    return Array.from({ length: count }, (_, i) => ({
      id: `mock_ctx_${i}`,
      agentId,
      type: 'contextual',
      content: `Mock contextual memory ${i + 1} with detailed information about user interaction and task execution.`,
      context: {
        sessionId,
        timestamp: new Date(Date.now() - i * 60000),
        tags: [`tag_${i}`, 'contextual'],
        entities: [`entity_${i}`],
        priority: i === 0 ? 'high' : 'normal'
      },
      importance: 0.7 - (i * 0.1),
      timestamp: new Date(Date.now() - i * 60000),
      metadata: {
        source: 'mock_generator',
        contextType: 'general',
        temporalMarkers: ['today', 'now'],
        entityReferences: [`@user_${i}`, `#project_${i}`],
        actionItems: [{
          text: `Complete task ${i}`,
          type: 'todo',
          priority: 'normal'
        }]
      },
      relevanceScore: 0.8 - (i * 0.1)
    }));
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'UC2 Contextual Memory Manager',
      version: '1.0.0',
      description: 'Advanced context-aware memory management with temporal relationships',
      capabilities: [
        'Contextual memory storage',
        'Relationship graph management',
        'Temporal indexing',
        'Context-aware retrieval',
        'Thread building',
        'Entity extraction',
        'Action item detection',
        'Relevance scoring'
      ],
      status: 'operational',
      contextTypes: Array.from(this.contextTypes),
      activeContexts: this.contextGraph.size,
      temporalEntries: this.temporalIndex.size,
      cacheSize: this.cache.keys().length,
      maxContextDepth: this.maxContextDepth,
      contextWindow: this.contextWindow
    };
  }
}

module.exports = new ContextualMemoryManager();