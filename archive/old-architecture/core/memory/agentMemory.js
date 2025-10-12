const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');

const prisma = new PrismaClient();

class AgentMemoryService {
  constructor() {
    this.memoryCache = new Map(); // In-memory cache for fast access
    this.sharedMemory = new Map(); // Shared memory pool for all agents
    this.maxMemorySize = parseInt(process.env.AGENT_MAX_MEMORY_SIZE) || 1000;
    this.enableSharedMemory = process.env.AGENT_SHARED_MEMORY === 'true';
    this.memoryRetentionDays = parseInt(process.env.AGENT_MEMORY_RETENTION_DAYS) || 30;
  }

  // Generate a unique memory ID
  generateMemoryId(agentId, content) {
    return crypto
      .createHash('sha256')
      .update(`${agentId}-${content}-${Date.now()}`)
      .digest('hex')
      .substring(0, 16);
  }

  // Store memory for an agent
  async storeMemory(agentId, memory) {
    try {
      const memoryId = this.generateMemoryId(agentId, memory.content);
      
      const memoryEntry = {
        id: memoryId,
        agentId,
        type: memory.type || 'conversation',
        content: memory.content,
        context: memory.context || {},
        embedding: memory.embedding || null,
        importance: memory.importance || 0.5,
        timestamp: new Date(),
        metadata: {
          source: memory.source || 'user_interaction',
          tags: memory.tags || [],
          entities: memory.entities || [],
          sentiment: memory.sentiment || 'neutral',
          keywords: memory.keywords || []
        }
      };

      // Store in database
      await prisma.agentMemory.create({
        data: {
          id: memoryId,
          agentId,
          type: memoryEntry.type,
          content: memoryEntry.content,
          context: JSON.stringify(memoryEntry.context),
          embedding: memoryEntry.embedding ? JSON.stringify(memoryEntry.embedding) : null,
          importance: memoryEntry.importance,
          metadata: JSON.stringify(memoryEntry.metadata)
        }
      });

      // Update cache
      if (!this.memoryCache.has(agentId)) {
        this.memoryCache.set(agentId, []);
      }
      const agentMemories = this.memoryCache.get(agentId);
      agentMemories.push(memoryEntry);
      
      // Limit cache size
      if (agentMemories.length > this.maxMemorySize) {
        agentMemories.shift(); // Remove oldest
      }

      // Store in shared memory if enabled
      if (this.enableSharedMemory && memory.shareable !== false) {
        await this.storeSharedMemory(memoryEntry);
      }

      return memoryEntry;
    } catch (error) {
      console.error('Error storing memory:', error);
      throw error;
    }
  }

  // Store memory in shared pool
  async storeSharedMemory(memory) {
    const category = memory.metadata?.category || 'general';
    
    if (!this.sharedMemory.has(category)) {
      this.sharedMemory.set(category, []);
    }
    
    const categoryMemories = this.sharedMemory.get(category);
    categoryMemories.push({
      ...memory,
      sharedAt: new Date(),
      accessCount: 0
    });
    
    // Limit shared memory size per category
    if (categoryMemories.length > 100) {
      categoryMemories.shift();
    }
  }

  // Retrieve memories for an agent
  async retrieveMemories(agentId, options = {}) {
    try {
      const {
        limit = 50,
        type = null,
        minImportance = 0,
        startDate = null,
        endDate = null,
        searchQuery = null
      } = options;

      // Check cache first
      if (this.memoryCache.has(agentId) && !searchQuery) {
        let memories = this.memoryCache.get(agentId);
        
        if (type) {
          memories = memories.filter(m => m.type === type);
        }
        if (minImportance > 0) {
          memories = memories.filter(m => m.importance >= minImportance);
        }
        
        return memories.slice(-limit);
      }

      // Query database
      const where = {
        agentId,
        ...(type && { type }),
        ...(minImportance > 0 && { importance: { gte: minImportance } }),
        ...(startDate && { createdAt: { gte: startDate } }),
        ...(endDate && { createdAt: { lte: endDate } })
      };

      if (searchQuery) {
        where.OR = [
          { content: { contains: searchQuery, mode: 'insensitive' } },
          { metadata: { contains: searchQuery, mode: 'insensitive' } }
        ];
      }

      const memories = await prisma.agentMemory.findMany({
        where,
        orderBy: { createdAt: 'desc' },
        take: limit
      });

      // Parse JSON fields
      return memories.map(m => ({
        ...m,
        context: JSON.parse(m.context || '{}'),
        metadata: JSON.parse(m.metadata || '{}'),
        embedding: m.embedding ? JSON.parse(m.embedding) : null
      }));
    } catch (error) {
      console.error('Error retrieving memories:', error);
      throw error;
    }
  }

  // Search memories using semantic similarity
  async searchMemories(agentId, query, options = {}) {
    try {
      const {
        limit = 10,
        includeShared = true,
        threshold = 0.7
      } = options;

      // Get agent's memories
      const agentMemories = await this.retrieveMemories(agentId, { limit: 100 });
      
      // Include shared memories if enabled
      let allMemories = [...agentMemories];
      if (includeShared && this.enableSharedMemory) {
        const sharedMemories = await this.getRelevantSharedMemories(query);
        allMemories = [...allMemories, ...sharedMemories];
      }

      // Simple keyword matching (in production, use embeddings)
      const queryWords = query.toLowerCase().split(' ');
      const scoredMemories = allMemories.map(memory => {
        const content = memory.content.toLowerCase();
        const score = queryWords.reduce((acc, word) => {
          return acc + (content.includes(word) ? 1 : 0);
        }, 0) / queryWords.length;
        
        return { ...memory, relevanceScore: score };
      });

      // Filter and sort by relevance
      return scoredMemories
        .filter(m => m.relevanceScore >= threshold)
        .sort((a, b) => b.relevanceScore - a.relevanceScore)
        .slice(0, limit);
    } catch (error) {
      console.error('Error searching memories:', error);
      throw error;
    }
  }

  // Get relevant shared memories
  async getRelevantSharedMemories(query, limit = 5) {
    const allShared = [];
    
    for (const [category, memories] of this.sharedMemory) {
      allShared.push(...memories.map(m => ({
        ...m,
        category,
        isShared: true
      })));
    }
    
    // Simple relevance scoring
    const queryWords = query.toLowerCase().split(' ');
    const scored = allShared.map(memory => {
      const content = memory.content.toLowerCase();
      const score = queryWords.reduce((acc, word) => {
        return acc + (content.includes(word) ? 1 : 0);
      }, 0) / queryWords.length;
      
      // Increment access count
      memory.accessCount++;
      
      return { ...memory, relevanceScore: score };
    });
    
    return scored
      .filter(m => m.relevanceScore > 0)
      .sort((a, b) => b.relevanceScore - a.relevanceScore)
      .slice(0, limit);
  }

  // Consolidate memories (reduce redundancy)
  async consolidateMemories(agentId) {
    try {
      const memories = await this.retrieveMemories(agentId, { limit: 1000 });
      
      // Group similar memories
      const groups = [];
      const used = new Set();
      
      for (let i = 0; i < memories.length; i++) {
        if (used.has(i)) continue;
        
        const group = [memories[i]];
        used.add(i);
        
        for (let j = i + 1; j < memories.length; j++) {
          if (used.has(j)) continue;
          
          // Calculate similarity (simple approach)
          const similarity = this.calculateSimilarity(memories[i].content, memories[j].content);
          if (similarity > 0.8) {
            group.push(memories[j]);
            used.add(j);
          }
        }
        
        groups.push(group);
      }
      
      // Create consolidated memories
      const consolidated = [];
      for (const group of groups) {
        if (group.length === 1) {
          consolidated.push(group[0]);
        } else {
          // Merge similar memories
          const merged = {
            id: this.generateMemoryId(agentId, 'consolidated'),
            agentId,
            type: 'consolidated',
            content: this.mergeContents(group.map(m => m.content)),
            context: this.mergeContexts(group.map(m => m.context)),
            importance: Math.max(...group.map(m => m.importance)),
            timestamp: new Date(),
            metadata: {
              originalCount: group.length,
              dateRange: {
                start: Math.min(...group.map(m => m.timestamp)),
                end: Math.max(...group.map(m => m.timestamp))
              }
            }
          };
          consolidated.push(merged);
          
          // Delete original memories
          for (const memory of group) {
            await prisma.agentMemory.delete({
              where: { id: memory.id }
            });
          }
          
          // Store consolidated memory
          await this.storeMemory(agentId, merged);
        }
      }
      
      return {
        originalCount: memories.length,
        consolidatedCount: consolidated.length,
        reduction: ((memories.length - consolidated.length) / memories.length * 100).toFixed(2)
      };
    } catch (error) {
      console.error('Error consolidating memories:', error);
      throw error;
    }
  }

  // Calculate similarity between two strings
  calculateSimilarity(str1, str2) {
    const words1 = new Set(str1.toLowerCase().split(' '));
    const words2 = new Set(str2.toLowerCase().split(' '));
    
    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);
    
    return intersection.size / union.size;
  }

  // Merge multiple contents
  mergeContents(contents) {
    // Remove duplicates and join
    const unique = [...new Set(contents)];
    return unique.join(' | ');
  }

  // Merge multiple contexts
  mergeContexts(contexts) {
    const merged = {};
    for (const context of contexts) {
      Object.assign(merged, context);
    }
    return merged;
  }

  // Get memory statistics
  async getMemoryStats(agentId) {
    try {
      const stats = await prisma.agentMemory.groupBy({
        by: ['type'],
        where: { agentId },
        _count: true,
        _avg: {
          importance: true
        }
      });
      
      const total = await prisma.agentMemory.count({
        where: { agentId }
      });
      
      const oldestMemory = await prisma.agentMemory.findFirst({
        where: { agentId },
        orderBy: { createdAt: 'asc' }
      });
      
      const newestMemory = await prisma.agentMemory.findFirst({
        where: { agentId },
        orderBy: { createdAt: 'desc' }
      });
      
      return {
        total,
        byType: stats,
        oldestMemory: oldestMemory?.createdAt,
        newestMemory: newestMemory?.createdAt,
        cacheSize: this.memoryCache.get(agentId)?.length || 0,
        sharedMemoryCategories: Array.from(this.sharedMemory.keys())
      };
    } catch (error) {
      console.error('Error getting memory stats:', error);
      throw error;
    }
  }

  // Clear old memories
  async clearOldMemories(daysToKeep = null) {
    try {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - (daysToKeep || this.memoryRetentionDays));
      
      const deleted = await prisma.agentMemory.deleteMany({
        where: {
          createdAt: { lt: cutoffDate }
        }
      });
      
      // Clear cache for affected agents
      this.memoryCache.clear();
      
      return {
        deletedCount: deleted.count,
        cutoffDate
      };
    } catch (error) {
      console.error('Error clearing old memories:', error);
      throw error;
    }
  }

  // Export agent memories
  async exportMemories(agentId, format = 'json') {
    try {
      const memories = await this.retrieveMemories(agentId, { limit: 10000 });
      
      if (format === 'json') {
        return JSON.stringify(memories, null, 2);
      } else if (format === 'csv') {
        // Convert to CSV
        const headers = ['timestamp', 'type', 'content', 'importance', 'tags'];
        const rows = memories.map(m => [
          m.timestamp,
          m.type,
          m.content.replace(/,/g, ';'),
          m.importance,
          m.metadata?.tags?.join(';') || ''
        ]);
        
        return [headers, ...rows].map(row => row.join(',')).join('\n');
      }
      
      throw new Error('Unsupported export format');
    } catch (error) {
      console.error('Error exporting memories:', error);
      throw error;
    }
  }

  // Import memories for an agent
  async importMemories(agentId, data, format = 'json') {
    try {
      let memories = [];
      
      if (format === 'json') {
        memories = JSON.parse(data);
      } else if (format === 'csv') {
        // Parse CSV
        const lines = data.split('\n');
        const headers = lines[0].split(',');
        
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(',');
          if (values.length === headers.length) {
            memories.push({
              content: values[2].replace(/;/g, ','),
              type: values[1],
              importance: parseFloat(values[3]),
              timestamp: new Date(values[0]),
              tags: values[4] ? values[4].split(';') : []
            });
          }
        }
      }
      
      // Store imported memories
      const results = [];
      for (const memory of memories) {
        const stored = await this.storeMemory(agentId, memory);
        results.push(stored);
      }
      
      return {
        imported: results.length,
        memories: results
      };
    } catch (error) {
      console.error('Error importing memories:', error);
      throw error;
    }
  }
}

module.exports = new AgentMemoryService();