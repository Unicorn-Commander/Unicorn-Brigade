const NodeCache = require('node-cache');
const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');
const fetch = require('node-fetch');

const prisma = new PrismaClient();

/**
 * UC2 Vector Memory Service
 * Advanced semantic memory with embeddings, similarity search, and clustering
 * Part of the Unicorn Command & Control Platform
 */
class VectorMemoryService {
  constructor() {
    this.cache = new NodeCache({ stdTTL: 3600 }); // 1 hour cache
    this.vectorCache = new Map(); // In-memory vector storage
    this.embeddingProvider = process.env.EMBEDDING_PROVIDER || 'openai';
    this.embeddingModel = process.env.EMBEDDING_MODEL || 'text-embedding-ada-002';
    this.vectorDimensions = 1536; // OpenAI ada-002 dimensions
    this.similarityThreshold = 0.7;
    this.mockMode = process.env.NODE_ENV === 'test' || !process.env.OPENAI_API_KEY;

    // Initialize vector indexes
    this.vectorIndexes = new Map();
    this.clusterCache = new Map();

    console.log('🧠 Vector Memory Service initialized');
  }

  /**
   * Generate embedding for text content
   */
  async generateEmbedding(text, options = {}) {
    try {
      const {
        model = this.embeddingModel,
        maxTokens = 8000
      } = options;

      // Truncate text if too long
      const truncatedText = text.length > maxTokens ?
        text.substring(0, maxTokens) : text;

      if (this.mockMode) {
        // Generate mock embedding for testing
        return this.generateMockEmbedding(truncatedText);
      }

      // Use OpenAI Embeddings API
      if (this.embeddingProvider === 'openai') {
        const response = await fetch('https://api.openai.com/v1/embeddings', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            input: truncatedText,
            model: model
          })
        });

        if (!response.ok) {
          throw new Error(`OpenAI API error: ${response.statusText}`);
        }

        const data = await response.json();
        return data.data[0].embedding;
      }

      // Fallback to mock
      return this.generateMockEmbedding(truncatedText);

    } catch (error) {
      console.error('Error generating embedding:', error);
      // Return mock embedding as fallback
      return this.generateMockEmbedding(text);
    }
  }

  /**
   * Generate mock embedding for testing/fallback
   */
  generateMockEmbedding(text) {
    const hash = crypto.createHash('md5').update(text).digest('hex');
    const embedding = [];

    // Generate deterministic mock embedding based on text hash
    for (let i = 0; i < this.vectorDimensions; i++) {
      const seedValue = parseInt(hash.substring(i % 32, (i % 32) + 2), 16);
      embedding.push((Math.sin(seedValue + i) + Math.cos(seedValue * i)) / 2);
    }

    // Normalize vector
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / magnitude);
  }

  /**
   * Store memory with vector embedding
   */
  async storeVectorMemory(agentId, memory) {
    try {
      const memoryId = this.generateMemoryId(agentId, memory.content);

      // Generate embedding for the content
      const embedding = await this.generateEmbedding(memory.content);

      const vectorMemory = {
        id: memoryId,
        agentId,
        type: memory.type || 'semantic',
        content: memory.content,
        embedding: embedding,
        context: memory.context || {},
        importance: memory.importance || 0.5,
        timestamp: new Date(),
        metadata: {
          source: memory.source || 'vector_store',
          tags: memory.tags || [],
          entities: memory.entities || [],
          sentiment: memory.sentiment || 'neutral',
          keywords: memory.keywords || [],
          vectorDimensions: this.vectorDimensions,
          embeddingModel: this.embeddingModel
        }
      };

      // Store in database
      await prisma.vectorMemory.create({
        data: {
          id: memoryId,
          agentId,
          type: vectorMemory.type,
          content: vectorMemory.content,
          embedding: JSON.stringify(embedding),
          context: JSON.stringify(vectorMemory.context),
          importance: vectorMemory.importance,
          metadata: JSON.stringify(vectorMemory.metadata)
        }
      }).catch(async (error) => {
        // If table doesn't exist, create it first
        if (error.code === 'P2021') {
          await this.createVectorMemoryTable();
          return prisma.vectorMemory.create({
            data: {
              id: memoryId,
              agentId,
              type: vectorMemory.type,
              content: vectorMemory.content,
              embedding: JSON.stringify(embedding),
              context: JSON.stringify(vectorMemory.context),
              importance: vectorMemory.importance,
              metadata: JSON.stringify(vectorMemory.metadata)
            }
          });
        }
        throw error;
      });

      // Store in vector cache
      this.vectorCache.set(memoryId, {
        ...vectorMemory,
        embedding: embedding
      });

      // Update vector index
      this.updateVectorIndex(agentId, memoryId, embedding);

      return vectorMemory;
    } catch (error) {
      console.error('Error storing vector memory:', error);
      throw error;
    }
  }

  /**
   * Create vector memory table if it doesn't exist
   */
  async createVectorMemoryTable() {
    try {
      await prisma.$executeRaw`
        CREATE TABLE IF NOT EXISTS "VectorMemory" (
          "id" TEXT NOT NULL PRIMARY KEY,
          "agentId" TEXT NOT NULL,
          "type" TEXT NOT NULL DEFAULT 'semantic',
          "content" TEXT NOT NULL,
          "embedding" TEXT NOT NULL,
          "context" TEXT NOT NULL DEFAULT '{}',
          "importance" REAL NOT NULL DEFAULT 0.5,
          "metadata" TEXT NOT NULL DEFAULT '{}',
          "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
      `;
      console.log('✅ VectorMemory table created successfully');
    } catch (error) {
      console.log('VectorMemory table may already exist:', error.message);
    }
  }

  /**
   * Update vector index for fast similarity search
   */
  updateVectorIndex(agentId, memoryId, embedding) {
    if (!this.vectorIndexes.has(agentId)) {
      this.vectorIndexes.set(agentId, new Map());
    }

    const agentIndex = this.vectorIndexes.get(agentId);
    agentIndex.set(memoryId, embedding);

    // Limit index size (keep most recent 1000 vectors per agent)
    if (agentIndex.size > 1000) {
      const firstKey = agentIndex.keys().next().value;
      agentIndex.delete(firstKey);
    }
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  calculateCosineSimilarity(vectorA, vectorB) {
    if (vectorA.length !== vectorB.length) {
      throw new Error('Vectors must have the same dimensions');
    }

    let dotProduct = 0;
    let magnitudeA = 0;
    let magnitudeB = 0;

    for (let i = 0; i < vectorA.length; i++) {
      dotProduct += vectorA[i] * vectorB[i];
      magnitudeA += vectorA[i] * vectorA[i];
      magnitudeB += vectorB[i] * vectorB[i];
    }

    magnitudeA = Math.sqrt(magnitudeA);
    magnitudeB = Math.sqrt(magnitudeB);

    if (magnitudeA === 0 || magnitudeB === 0) {
      return 0;
    }

    return dotProduct / (magnitudeA * magnitudeB);
  }

  /**
   * Semantic search using vector similarity
   */
  async semanticSearch(agentId, query, options = {}) {
    try {
      const {
        limit = 10,
        threshold = this.similarityThreshold,
        includeContent = true,
        includeContext = false
      } = options;

      // Generate embedding for query
      const queryEmbedding = await this.generateEmbedding(query);

      // Check vector index first for fast search
      if (this.vectorIndexes.has(agentId)) {
        const agentIndex = this.vectorIndexes.get(agentId);
        const similarities = [];

        for (const [memoryId, embedding] of agentIndex) {
          const similarity = this.calculateCosineSimilarity(queryEmbedding, embedding);
          if (similarity >= threshold) {
            similarities.push({
              memoryId,
              similarity,
              embedding
            });
          }
        }

        // Sort by similarity (highest first)
        similarities.sort((a, b) => b.similarity - a.similarity);

        // Get detailed memory data
        const results = [];
        for (const sim of similarities.slice(0, limit)) {
          const memory = this.vectorCache.get(sim.memoryId);
          if (memory) {
            results.push({
              ...memory,
              similarity: sim.similarity,
              embedding: includeContent ? undefined : sim.embedding
            });
          }
        }

        if (results.length > 0) {
          return results;
        }
      }

      // Fallback to database search
      return await this.databaseSemanticSearch(agentId, queryEmbedding, {
        limit,
        threshold,
        includeContent,
        includeContext
      });

    } catch (error) {
      console.error('Error in semantic search:', error);
      // Return empty results on error
      return [];
    }
  }

  /**
   * Database-based semantic search (fallback)
   */
  async databaseSemanticSearch(agentId, queryEmbedding, options) {
    try {
      const memories = await prisma.vectorMemory.findMany({
        where: { agentId },
        orderBy: { createdAt: 'desc' },
        take: 500 // Limit for performance
      });

      const similarities = [];

      for (const memory of memories) {
        try {
          const embedding = JSON.parse(memory.embedding);
          const similarity = this.calculateCosineSimilarity(queryEmbedding, embedding);

          if (similarity >= options.threshold) {
            similarities.push({
              ...memory,
              context: JSON.parse(memory.context || '{}'),
              metadata: JSON.parse(memory.metadata || '{}'),
              embedding: options.includeContent ? undefined : embedding,
              similarity
            });
          }
        } catch (parseError) {
          console.warn('Error parsing embedding for memory:', memory.id);
        }
      }

      // Sort and limit results
      return similarities
        .sort((a, b) => b.similarity - a.similarity)
        .slice(0, options.limit);

    } catch (error) {
      console.error('Error in database semantic search:', error);
      return [];
    }
  }

  /**
   * Cluster memories by semantic similarity
   */
  async clusterMemories(agentId, options = {}) {
    try {
      const {
        clusterCount = 5,
        minClusterSize = 3,
        maxIterations = 10
      } = options;

      const cacheKey = `clusters_${agentId}_${clusterCount}`;

      // Check cache first
      if (this.clusterCache.has(cacheKey)) {
        return this.clusterCache.get(cacheKey);
      }

      // Get all memories for agent
      const memories = await this.getVectorMemories(agentId, { limit: 1000 });

      if (memories.length < minClusterSize) {
        return { clusters: [memories], centroids: [] };
      }

      // Perform K-means clustering
      const clusters = await this.performKMeansClustering(
        memories,
        clusterCount,
        maxIterations
      );

      // Filter out small clusters
      const validClusters = clusters.filter(cluster =>
        cluster.memories.length >= minClusterSize
      );

      const result = {
        clusters: validClusters,
        totalMemories: memories.length,
        clusterCount: validClusters.length,
        averageClusterSize: validClusters.length > 0 ?
          memories.length / validClusters.length : 0,
        timestamp: new Date()
      };

      // Cache results
      this.clusterCache.set(cacheKey, result);

      return result;
    } catch (error) {
      console.error('Error clustering memories:', error);
      throw error;
    }
  }

  /**
   * Perform K-means clustering on memory vectors
   */
  async performKMeansClustering(memories, k, maxIterations) {
    const vectors = memories.map(m => m.embedding);
    const n = vectors.length;
    const dimensions = vectors[0].length;

    // Initialize centroids randomly
    let centroids = [];
    for (let i = 0; i < k; i++) {
      const centroid = [];
      for (let j = 0; j < dimensions; j++) {
        centroid.push(Math.random() * 2 - 1); // Random values between -1 and 1
      }
      centroids.push(centroid);
    }

    let assignments = new Array(n).fill(0);
    let converged = false;
    let iteration = 0;

    while (!converged && iteration < maxIterations) {
      // Assign points to nearest centroid
      const newAssignments = new Array(n);
      for (let i = 0; i < n; i++) {
        let maxSimilarity = -1;
        let bestCluster = 0;

        for (let j = 0; j < k; j++) {
          const similarity = this.calculateCosineSimilarity(vectors[i], centroids[j]);
          if (similarity > maxSimilarity) {
            maxSimilarity = similarity;
            bestCluster = j;
          }
        }
        newAssignments[i] = bestCluster;
      }

      // Check for convergence
      converged = newAssignments.every((assignment, i) => assignment === assignments[i]);
      assignments = newAssignments;

      // Update centroids
      for (let j = 0; j < k; j++) {
        const clusterPoints = [];
        for (let i = 0; i < n; i++) {
          if (assignments[i] === j) {
            clusterPoints.push(vectors[i]);
          }
        }

        if (clusterPoints.length > 0) {
          // Calculate mean of cluster points
          const newCentroid = new Array(dimensions).fill(0);
          for (const point of clusterPoints) {
            for (let d = 0; d < dimensions; d++) {
              newCentroid[d] += point[d];
            }
          }
          for (let d = 0; d < dimensions; d++) {
            newCentroid[d] /= clusterPoints.length;
          }
          centroids[j] = newCentroid;
        }
      }

      iteration++;
    }

    // Build final clusters
    const clusters = [];
    for (let j = 0; j < k; j++) {
      const clusterMemories = [];
      for (let i = 0; i < n; i++) {
        if (assignments[i] === j) {
          clusterMemories.push(memories[i]);
        }
      }

      if (clusterMemories.length > 0) {
        clusters.push({
          id: j,
          centroid: centroids[j],
          memories: clusterMemories,
          size: clusterMemories.length,
          theme: this.extractClusterTheme(clusterMemories)
        });
      }
    }

    return clusters;
  }

  /**
   * Extract theme/topic from cluster memories
   */
  extractClusterTheme(memories) {
    const allWords = [];
    const entities = [];
    const tags = [];

    for (const memory of memories) {
      // Extract keywords from content
      const words = memory.content
        .toLowerCase()
        .split(/\s+/)
        .filter(word => word.length > 3)
        .slice(0, 10);
      allWords.push(...words);

      // Collect entities and tags
      if (memory.metadata?.entities) {
        entities.push(...memory.metadata.entities);
      }
      if (memory.metadata?.tags) {
        tags.push(...memory.metadata.tags);
      }
    }

    // Find most common words/entities/tags
    const wordCounts = {};
    allWords.forEach(word => {
      wordCounts[word] = (wordCounts[word] || 0) + 1;
    });

    const topWords = Object.entries(wordCounts)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5)
      .map(([word]) => word);

    return {
      keywords: topWords,
      entities: [...new Set(entities)].slice(0, 5),
      tags: [...new Set(tags)].slice(0, 5),
      memoryCount: memories.length,
      timeRange: {
        start: Math.min(...memories.map(m => new Date(m.timestamp).getTime())),
        end: Math.max(...memories.map(m => new Date(m.timestamp).getTime()))
      }
    };
  }

  /**
   * Get vector memories for an agent
   */
  async getVectorMemories(agentId, options = {}) {
    try {
      const { limit = 100, includeEmbeddings = true } = options;

      const memories = await prisma.vectorMemory.findMany({
        where: { agentId },
        orderBy: { createdAt: 'desc' },
        take: limit
      });

      return memories.map(memory => ({
        ...memory,
        context: JSON.parse(memory.context || '{}'),
        metadata: JSON.parse(memory.metadata || '{}'),
        embedding: includeEmbeddings ? JSON.parse(memory.embedding) : undefined
      }));
    } catch (error) {
      console.error('Error getting vector memories:', error);
      // Return mock data on error
      return this.generateMockMemories(agentId, Math.min(limit, 5));
    }
  }

  /**
   * Generate memory ID
   */
  generateMemoryId(agentId, content) {
    return crypto
      .createHash('sha256')
      .update(`vector_${agentId}_${content}_${Date.now()}`)
      .digest('hex')
      .substring(0, 16);
  }

  /**
   * Generate mock memories for testing
   */
  generateMockMemories(agentId, count = 5) {
    const topics = [
      'system analysis', 'user interaction', 'task execution',
      'error handling', 'performance optimization'
    ];

    return Array.from({ length: count }, (_, i) => ({
      id: `mock_${i}`,
      agentId,
      type: 'semantic',
      content: `Mock semantic memory about ${topics[i % topics.length]} with detailed information and context.`,
      embedding: this.generateMockEmbedding(`mock content ${i}`),
      context: { mock: true, index: i },
      importance: 0.5 + (i * 0.1),
      timestamp: new Date(Date.now() - i * 60000),
      metadata: {
        source: 'mock_generator',
        tags: [topics[i % topics.length]],
        entities: [`entity_${i}`],
        sentiment: 'neutral',
        keywords: [`keyword_${i}`, 'memory', 'vector'],
        vectorDimensions: this.vectorDimensions,
        embeddingModel: 'mock'
      }
    }));
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'UC2 Vector Memory Service',
      version: '1.0.0',
      description: 'Advanced semantic memory with embeddings and similarity search',
      capabilities: [
        'Semantic embeddings generation',
        'Vector similarity search',
        'Memory clustering',
        'Multi-provider embedding support',
        'Real-time vector indexing',
        'Contextual search',
        'Memory analytics'
      ],
      status: 'operational',
      embeddingProvider: this.embeddingProvider,
      embeddingModel: this.embeddingModel,
      vectorDimensions: this.vectorDimensions,
      mockMode: this.mockMode,
      cacheSize: this.vectorCache.size,
      indexedAgents: this.vectorIndexes.size
    };
  }
}

module.exports = new VectorMemoryService();