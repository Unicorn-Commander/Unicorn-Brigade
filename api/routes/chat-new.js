/**
 * NEW ARCHITECTURE: Chat API Route
 * Demonstrates integration of LiteLLM, Mem0, and Langfuse
 *
 * This is an example showing how to migrate from old architecture to new
 */

const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');

// New service imports
const litellm = require('../../core/services/litellmProvider');
const mem0 = require('../../core/services/mem0Provider');
const langfuse = require('../../core/services/langfuseProvider');

const prisma = new PrismaClient();

/**
 * POST /api/chat/message
 * Send message to agent with full observability and memory
 */
router.post('/message', async (req, res) => {
  const startTime = Date.now();

  try {
    const { agentId, userId, message, sessionId } = req.body;

    // Validation
    if (!agentId || !userId || !message) {
      return res.status(400).json({
        error: 'Missing required fields: agentId, userId, message'
      });
    }

    // Create observability trace
    const trace = langfuse.createTrace(
      'agent-chat',
      userId,
      { agentId, sessionId },
      {
        sessionId: sessionId || `session-${userId}-${Date.now()}`,
        tags: ['chat', 'agent'],
        input: { message, agentId }
      }
    );

    // Fetch agent configuration
    const agent = await prisma.agent.findUnique({
      where: { id: agentId }
    });

    if (!agent) {
      return res.status(404).json({ error: 'Agent not found' });
    }

    // Step 1: Search relevant memories
    langfuse.logSpan(trace, {
      name: 'memory-search',
      input: { query: message, userId, agentId },
      startTime: new Date()
    });

    const memories = await mem0.searchMemories(message, userId, agentId, 5);
    const memoryContext = mem0.buildContext(message, userId, agentId, 5);

    langfuse.logSpan(trace, {
      name: 'memory-search',
      output: { memoriesFound: memories.length },
      endTime: new Date()
    });

    // Step 2: Build LLM messages with context
    const messages = [
      {
        role: 'system',
        content: agent.systemPrompt || `You are ${agent.name}, a helpful AI assistant.`
      }
    ];

    // Add memory context if available
    if (await memoryContext) {
      messages.push({
        role: 'system',
        content: await memoryContext
      });
    }

    // Add user message
    messages.push({
      role: 'user',
      content: message
    });

    // Step 3: Call LLM via LiteLLM
    const llmStartTime = new Date();
    const response = await litellm.sendMessage(
      agent.model || 'gpt-4-turbo',
      messages,
      {
        temperature: agent.temperature || 0.7,
        maxTokens: agent.maxTokens || 2000
      }
    );

    // Log LLM generation to Langfuse
    langfuse.logGeneration(trace, {
      name: 'agent-llm-call',
      model: agent.model || 'gpt-4-turbo',
      temperature: agent.temperature || 0.7,
      maxTokens: agent.maxTokens || 2000,
      input: messages,
      output: response.content,
      usage: response.usage,
      provider: response.provider,
      agentId: agentId,
      startTime: llmStartTime,
      endTime: new Date()
    });

    // Step 4: Store conversation in Mem0
    langfuse.logSpan(trace, {
      name: 'memory-store',
      input: { userMessage: message, assistantResponse: response.content },
      startTime: new Date()
    });

    await mem0.addMemory(
      [
        { role: 'user', content: message },
        { role: 'assistant', content: response.content }
      ],
      userId,
      agentId,
      {
        sessionId,
        timestamp: new Date().toISOString(),
        model: agent.model,
        conversationId: sessionId
      }
    );

    langfuse.logSpan(trace, {
      name: 'memory-store',
      output: { stored: true },
      endTime: new Date()
    });

    // Step 5: Store in database for persistence
    const userMessage = await prisma.agentMessage.create({
      data: {
        agentId,
        role: 'user',
        content: message,
        userId,
        metadata: JSON.stringify({
          timestamp: new Date().toISOString(),
          sessionId
        })
      }
    });

    const agentMessage = await prisma.agentMessage.create({
      data: {
        agentId,
        role: 'assistant',
        content: response.content,
        metadata: JSON.stringify({
          model: response.model,
          usage: response.usage,
          provider: response.provider,
          timestamp: new Date().toISOString(),
          sessionId
        })
      }
    });

    // Step 6: Update agent stats
    const stats = JSON.parse(agent.stats || '{}');
    stats.tasksCompleted = (stats.tasksCompleted || 0) + 1;
    stats.totalTokens = (stats.totalTokens || 0) + (response.usage?.total_tokens || 0);
    stats.lastActive = new Date().toISOString();

    await prisma.agent.update({
      where: { id: agentId },
      data: { stats: JSON.stringify(stats) }
    });

    // Complete trace
    const duration = Date.now() - startTime;
    trace.update({
      output: { response: response.content },
      metadata: {
        duration: duration,
        tokensUsed: response.usage?.total_tokens,
        memoriesUsed: memories.length
      }
    });

    // Return response
    res.json({
      success: true,
      response: response.content,
      metadata: {
        userMessageId: userMessage.id,
        agentMessageId: agentMessage.id,
        model: response.model,
        provider: response.provider,
        usage: response.usage,
        memoriesUsed: memories.length,
        duration: duration,
        traceId: trace.id
      }
    });

  } catch (error) {
    console.error('❌ Chat error:', error);

    // Log error to Langfuse if trace exists
    if (trace) {
      langfuse.logEvent(trace, {
        name: 'error',
        input: { error: error.message },
        level: 'ERROR'
      });
    }

    res.status(500).json({
      error: 'Failed to process message',
      message: error.message,
      duration: Date.now() - startTime
    });
  }
});

/**
 * POST /api/chat/stream
 * Stream response from agent
 */
router.post('/stream', async (req, res) => {
  try {
    const { agentId, userId, message, sessionId } = req.body;

    if (!agentId || !userId || !message) {
      return res.status(400).json({
        error: 'Missing required fields'
      });
    }

    // Set headers for SSE
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    // Get agent
    const agent = await prisma.agent.findUnique({ where: { id: agentId } });
    if (!agent) {
      res.write(`data: ${JSON.stringify({ error: 'Agent not found' })}\n\n`);
      return res.end();
    }

    // Get memory context
    const memoryContext = await mem0.buildContext(message, userId, agentId, 5);

    // Build messages
    const messages = [
      {
        role: 'system',
        content: agent.systemPrompt || `You are ${agent.name}.`
      }
    ];

    if (memoryContext) {
      messages.push({ role: 'system', content: memoryContext });
    }

    messages.push({ role: 'user', content: message });

    // Stream response
    let fullResponse = '';

    for await (const chunk of litellm.streamMessage(
      agent.model || 'gpt-4-turbo',
      messages,
      {
        temperature: agent.temperature || 0.7,
        maxTokens: agent.maxTokens || 2000
      }
    )) {
      fullResponse += chunk;
      res.write(`data: ${JSON.stringify({ chunk, type: 'content' })}\n\n`);
    }

    // Store in memory after stream completes
    await mem0.addMemory(
      [
        { role: 'user', content: message },
        { role: 'assistant', content: fullResponse }
      ],
      userId,
      agentId,
      { sessionId }
    );

    // Send completion event
    res.write(`data: ${JSON.stringify({ type: 'done', fullResponse })}\n\n`);
    res.end();

  } catch (error) {
    console.error('❌ Stream error:', error);
    res.write(`data: ${JSON.stringify({ error: error.message })}\n\n`);
    res.end();
  }
});

/**
 * GET /api/chat/history/:userId/:agentId
 * Get chat history with memory insights
 */
router.get('/history/:userId/:agentId', async (req, res) => {
  try {
    const { userId, agentId } = req.params;
    const { limit = 50 } = req.query;

    // Get database history
    const messages = await prisma.agentMessage.findMany({
      where: {
        agentId,
        userId
      },
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit)
    });

    // Get Mem0 memories with analytics
    const memoryData = await mem0.getMemoriesWithAnalytics(userId, agentId);

    res.json({
      success: true,
      messages: messages.reverse(), // Oldest first
      memories: memoryData.memories,
      analytics: memoryData.analytics,
      stats: {
        totalMessages: messages.length,
        totalMemories: memoryData.count,
        hasAnalytics: memoryData.hasAnalytics
      }
    });

  } catch (error) {
    console.error('❌ History error:', error);
    res.status(500).json({
      error: 'Failed to fetch history',
      message: error.message
    });
  }
});

/**
 * DELETE /api/chat/memory/:userId/:agentId
 * Clear memories for user/agent
 */
router.delete('/memory/:userId/:agentId', async (req, res) => {
  try {
    const { userId, agentId } = req.params;

    const result = await mem0.deleteAllMemories(userId, agentId);

    res.json({
      success: result.success,
      message: 'Memories cleared',
      result: result.result
    });

  } catch (error) {
    console.error('❌ Memory deletion error:', error);
    res.status(500).json({
      error: 'Failed to clear memories',
      message: error.message
    });
  }
});

/**
 * GET /api/chat/health
 * Health check for chat services
 */
router.get('/health', async (req, res) => {
  try {
    const [litellmHealth, mem0Health, langfuseHealth] = await Promise.all([
      litellm.healthCheck(),
      mem0.healthCheck(),
      langfuse.healthCheck()
    ]);

    const allHealthy =
      litellmHealth.status === 'healthy' &&
      mem0Health.status === 'healthy' &&
      (langfuseHealth.status === 'healthy' || langfuseHealth.status === 'disabled');

    res.json({
      status: allHealthy ? 'healthy' : 'degraded',
      services: {
        litellm: litellmHealth,
        mem0: mem0Health,
        langfuse: langfuseHealth
      },
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});

module.exports = router;
