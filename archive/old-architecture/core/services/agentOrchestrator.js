const { PrismaClient } = require('@prisma/client');
const aiProviders = require('./aiProviders');
const prisma = new PrismaClient();

class AgentOrchestrator {
  constructor() {
    this.activeAgents = new Map();
    this.taskQueue = [];
    this.memoryStore = new Map();
  }

  // Initialize an agent
  async initializeAgent(agentId) {
    try {
      const agent = await prisma.agent.findUnique({
        where: { id: agentId }
      });

      if (!agent) {
        throw new Error('Agent not found');
      }

      // Parse JSON fields
      const agentConfig = {
        ...agent,
        capabilities: JSON.parse(agent.capabilities),
        memory: JSON.parse(agent.memory),
        permissions: JSON.parse(agent.permissions),
        stats: JSON.parse(agent.stats)
      };

      // Initialize agent memory
      this.initializeMemory(agentId, agentConfig.memory);

      // Add to active agents
      this.activeAgents.set(agentId, {
        config: agentConfig,
        status: 'active',
        lastActive: new Date()
      });

      // Update agent status in database
      await prisma.agent.update({
        where: { id: agentId },
        data: { 
          status: 'active',
          stats: JSON.stringify({
            ...agentConfig.stats,
            lastActive: new Date()
          })
        }
      });

      return agentConfig;
    } catch (error) {
      console.error('Error initializing agent:', error);
      throw error;
    }
  }

  // Initialize agent memory
  initializeMemory(agentId, memoryConfig) {
    this.memoryStore.set(agentId, {
      individual: {
        capacity: memoryConfig.individual || 10, // MB
        used: 0,
        data: []
      },
      shared: {
        capacity: memoryConfig.shared || 100, // MB
        used: 0,
        data: []
      },
      crossCase: {
        capacity: memoryConfig.crossCase || 1000, // MB
        used: 0,
        data: []
      }
    });
  }

  // Process a message with an agent
  async processMessage(agentId, userId, message, context = {}) {
    try {
      // Get or initialize agent
      let agent = this.activeAgents.get(agentId);
      if (!agent) {
        const agentConfig = await this.initializeAgent(agentId);
        agent = this.activeAgents.get(agentId);
      }

      // Store user message
      const userMessage = await prisma.agentMessage.create({
        data: {
          agentId,
          role: 'user',
          content: message,
          userId,
          metadata: JSON.stringify({ timestamp: new Date(), context })
        }
      });

      // Get conversation history
      const history = await this.getConversationHistory(agentId, 10);

      // Prepare messages for AI
      const messages = [
        {
          role: 'system',
          content: agent.config.systemPrompt || this.getDefaultSystemPrompt(agent.config)
        },
        ...history.map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        {
          role: 'user',
          content: message
        }
      ];

      // Send to AI provider
      const aiResponse = await aiProviders.sendMessage(
        agent.config.aiProvider || 'mock',
        agent.config.model,
        messages,
        {
          temperature: agent.config.temperature,
          maxTokens: agent.config.maxTokens
        }
      );

      // Store agent response
      const agentMessage = await prisma.agentMessage.create({
        data: {
          agentId,
          role: 'assistant',
          content: aiResponse.content,
          metadata: JSON.stringify({
            model: aiResponse.model,
            usage: aiResponse.usage,
            timestamp: new Date()
          })
        }
      });

      // Update agent stats
      await this.updateAgentStats(agentId, aiResponse.usage);

      // Update memory
      await this.updateMemory(agentId, message, aiResponse.content);

      return {
        userMessage,
        agentMessage,
        agent: agent.config
      };
    } catch (error) {
      console.error('Error processing message:', error);
      throw error;
    }
  }

  // Get conversation history
  async getConversationHistory(agentId, limit = 10) {
    return await prisma.agentMessage.findMany({
      where: { agentId },
      orderBy: { createdAt: 'asc' },
      take: limit * 2, // Get more to ensure context
      skip: 0
    });
  }

  // Update agent statistics
  async updateAgentStats(agentId, usage) {
    const agent = await prisma.agent.findUnique({
      where: { id: agentId }
    });

    const stats = JSON.parse(agent.stats);
    stats.tasksCompleted = (stats.tasksCompleted || 0) + 1;
    stats.totalTokens = (stats.totalTokens || 0) + (usage?.total_tokens || 0);
    stats.lastActive = new Date();

    await prisma.agent.update({
      where: { id: agentId },
      data: {
        stats: JSON.stringify(stats)
      }
    });
  }

  // Update agent memory
  async updateMemory(agentId, userMessage, agentResponse) {
    const memory = this.memoryStore.get(agentId);
    if (!memory) return;

    // Add to individual memory
    memory.individual.data.push({
      timestamp: new Date(),
      user: userMessage,
      agent: agentResponse
    });

    // Trim if exceeds capacity (keep last 100 entries)
    if (memory.individual.data.length > 100) {
      memory.individual.data = memory.individual.data.slice(-100);
    }

    // Update used memory estimate
    memory.individual.used = JSON.stringify(memory.individual.data).length / 1024 / 1024;
  }

  // Get default system prompt based on agent type
  getDefaultSystemPrompt(agent) {
    const prompts = {
      'Concierge Agent': 'You are a professional concierge agent for a crisis management platform. Your role is to communicate with clients, provide updates, and answer questions about their cases in a clear, professional manner.',
      'Evidence Analyzer': 'You are an evidence analysis specialist. You excel at examining documents, classifying evidence, and identifying patterns that others might miss.',
      'Legal Researcher': 'You are a legal research specialist. You analyze case law, develop legal strategies, and provide comprehensive legal insights.',
      'Financial Forensics': 'You are a financial forensics expert. You track money flows, detect fraud patterns, and uncover hidden financial relationships.',
      'Conspiracy Analyzer': 'You are a conspiracy analysis specialist. You separate fact from fiction, analyze conspiracy theories objectively, and identify credible evidence patterns.'
    };

    return prompts[agent.name] || 'You are an AI assistant helping with crisis management and investigation tasks.';
  }

  // Create a task for an agent
  async createTask(agentId, taskType, input, priority = 5) {
    try {
      const task = await prisma.agentTask.create({
        data: {
          agentId,
          type: taskType,
          input: JSON.stringify(input),
          status: 'pending',
          priority,
          metadata: JSON.stringify({
            createdAt: new Date(),
            estimatedDuration: this.estimateTaskDuration(taskType)
          })
        }
      });

      // Add to task queue
      this.taskQueue.push({
        id: task.id,
        agentId,
        priority,
        createdAt: new Date()
      });

      // Sort queue by priority
      this.taskQueue.sort((a, b) => b.priority - a.priority);

      return task;
    } catch (error) {
      console.error('Error creating task:', error);
      throw error;
    }
  }

  // Process task queue
  async processTaskQueue() {
    if (this.taskQueue.length === 0) return;

    const task = this.taskQueue.shift();
    
    try {
      // Get task details
      const taskDetails = await prisma.agentTask.findUnique({
        where: { id: task.id }
      });

      if (!taskDetails) return;

      // Update task status
      await prisma.agentTask.update({
        where: { id: task.id },
        data: {
          status: 'processing',
          startedAt: new Date(),
          progress: 10
        }
      });

      // Process based on task type
      const result = await this.executeTask(taskDetails);

      // Update task with result
      await prisma.agentTask.update({
        where: { id: task.id },
        data: {
          status: 'completed',
          output: JSON.stringify(result),
          completedAt: new Date(),
          progress: 100
        }
      });

      return result;
    } catch (error) {
      console.error('Error processing task:', error);
      
      // Mark task as failed
      await prisma.agentTask.update({
        where: { id: task.id },
        data: {
          status: 'failed',
          output: JSON.stringify({ error: error.message }),
          completedAt: new Date()
        }
      });
    }
  }

  // Execute a specific task
  async executeTask(task) {
    const input = JSON.parse(task.input);
    
    switch (task.type) {
      case 'analysis':
        return await this.executeAnalysisTask(task.agentId, input);
      case 'research':
        return await this.executeResearchTask(task.agentId, input);
      case 'monitoring':
        return await this.executeMonitoringTask(task.agentId, input);
      case 'report':
        return await this.executeReportTask(task.agentId, input);
      default:
        throw new Error(`Unknown task type: ${task.type}`);
    }
  }

  // Execute analysis task
  async executeAnalysisTask(agentId, input) {
    const agent = await this.initializeAgent(agentId);
    
    const messages = [
      {
        role: 'system',
        content: `You are ${agent.name}. Analyze the following data and provide insights.`
      },
      {
        role: 'user',
        content: `Analyze this: ${JSON.stringify(input)}`
      }
    ];

    const response = await aiProviders.sendMessage(
      agent.aiProvider || 'mock',
      agent.model,
      messages,
      {
        temperature: 0.3,
        maxTokens: 3000
      }
    );

    return {
      analysis: response.content,
      confidence: Math.random() * 0.3 + 0.7,
      timestamp: new Date()
    };
  }

  // Execute research task
  async executeResearchTask(agentId, input) {
    // Simulate research task
    return {
      findings: `Research completed on topic: ${input.topic}`,
      sources: ['Source 1', 'Source 2', 'Source 3'],
      relevance: 0.85,
      timestamp: new Date()
    };
  }

  // Execute monitoring task
  async executeMonitoringTask(agentId, input) {
    // Simulate monitoring task
    return {
      status: 'No anomalies detected',
      metrics: {
        eventsProcessed: 234,
        alertsGenerated: 0
      },
      timestamp: new Date()
    };
  }

  // Execute report generation task
  async executeReportTask(agentId, input) {
    const agent = await this.initializeAgent(agentId);
    
    const messages = [
      {
        role: 'system',
        content: `You are ${agent.name}. Generate a comprehensive report based on the provided data.`
      },
      {
        role: 'user',
        content: `Generate a report on: ${JSON.stringify(input)}`
      }
    ];

    const response = await aiProviders.sendMessage(
      agent.aiProvider || 'mock',
      agent.model,
      messages,
      {
        temperature: 0.5,
        maxTokens: 4000
      }
    );

    return {
      report: response.content,
      sections: ['Executive Summary', 'Findings', 'Recommendations'],
      timestamp: new Date()
    };
  }

  // Estimate task duration
  estimateTaskDuration(taskType) {
    const estimates = {
      'analysis': 30,
      'research': 120,
      'monitoring': 10,
      'report': 60
    };
    
    return estimates[taskType] || 30;
  }

  // Orchestrate multiple agents
  async orchestrateAgents(agents, task, pattern = 'sequential') {
    switch (pattern) {
      case 'sequential':
        return await this.orchestrateSequential(agents, task);
      case 'parallel':
        return await this.orchestrateParallel(agents, task);
      case 'hierarchical':
        return await this.orchestrateHierarchical(agents, task);
      case 'collaborative':
        return await this.orchestrateCollaborative(agents, task);
      default:
        throw new Error(`Unknown orchestration pattern: ${pattern}`);
    }
  }

  // Sequential orchestration
  async orchestrateSequential(agents, task) {
    const results = [];
    let previousOutput = task.input;

    for (const agentId of agents) {
      const agent = await this.initializeAgent(agentId);
      const result = await this.processMessage(
        agentId,
        task.userId,
        previousOutput,
        { orchestration: 'sequential', step: results.length + 1 }
      );
      
      results.push(result);
      previousOutput = result.agentMessage.content;
    }

    return results;
  }

  // Parallel orchestration
  async orchestrateParallel(agents, task) {
    const promises = agents.map(agentId => 
      this.processMessage(
        agentId,
        task.userId,
        task.input,
        { orchestration: 'parallel' }
      )
    );

    return await Promise.all(promises);
  }

  // Hierarchical orchestration
  async orchestrateHierarchical(agents, task) {
    // First agent acts as coordinator
    const coordinatorId = agents[0];
    const workerIds = agents.slice(1);

    // Coordinator assigns tasks
    const coordinatorResult = await this.processMessage(
      coordinatorId,
      task.userId,
      `Coordinate this task: ${task.input}`,
      { orchestration: 'hierarchical', role: 'coordinator' }
    );

    // Workers execute in parallel
    const workerResults = await this.orchestrateParallel(workerIds, {
      ...task,
      input: coordinatorResult.agentMessage.content
    });

    // Coordinator reviews results
    const review = await this.processMessage(
      coordinatorId,
      task.userId,
      `Review these results: ${JSON.stringify(workerResults.map(r => r.agentMessage.content))}`,
      { orchestration: 'hierarchical', role: 'reviewer' }
    );

    return {
      coordinator: coordinatorResult,
      workers: workerResults,
      review
    };
  }

  // Collaborative orchestration
  async orchestrateCollaborative(agents, task) {
    const results = [];
    const sharedContext = [];

    for (let round = 0; round < 3; round++) {
      for (const agentId of agents) {
        const context = `Round ${round + 1}. Previous insights: ${JSON.stringify(sharedContext)}`;
        const result = await this.processMessage(
          agentId,
          task.userId,
          `${task.input}\n\nContext: ${context}`,
          { orchestration: 'collaborative', round: round + 1 }
        );
        
        results.push(result);
        sharedContext.push({
          agent: result.agent.name,
          insight: result.agentMessage.content.substring(0, 200)
        });
      }
    }

    return results;
  }

  // Deactivate an agent
  async deactivateAgent(agentId) {
    try {
      // Remove from active agents
      this.activeAgents.delete(agentId);

      // Clear memory
      this.memoryStore.delete(agentId);

      // Update database
      await prisma.agent.update({
        where: { id: agentId },
        data: { status: 'offline' }
      });

      return true;
    } catch (error) {
      console.error('Error deactivating agent:', error);
      throw error;
    }
  }

  // Get agent metrics
  async getAgentMetrics(agentId) {
    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      include: {
        messages: {
          orderBy: { createdAt: 'desc' },
          take: 100
        },
        tasks: {
          orderBy: { createdAt: 'desc' },
          take: 50
        }
      }
    });

    if (!agent) {
      throw new Error('Agent not found');
    }

    const stats = JSON.parse(agent.stats);
    const memory = this.memoryStore.get(agentId);

    return {
      agent: {
        ...agent,
        capabilities: JSON.parse(agent.capabilities),
        stats
      },
      metrics: {
        totalMessages: agent.messages.length,
        totalTasks: agent.tasks.length,
        completedTasks: agent.tasks.filter(t => t.status === 'completed').length,
        failedTasks: agent.tasks.filter(t => t.status === 'failed').length,
        averageResponseTime: this.calculateAverageResponseTime(agent.messages),
        memoryUsage: memory ? {
          individual: `${memory.individual.used.toFixed(2)}/${memory.individual.capacity} MB`,
          shared: `${memory.shared.used.toFixed(2)}/${memory.shared.capacity} MB`,
          crossCase: `${memory.crossCase.used.toFixed(2)}/${memory.crossCase.capacity} MB`
        } : null
      }
    };
  }

  // Calculate average response time
  calculateAverageResponseTime(messages) {
    if (messages.length < 2) return 0;

    let totalTime = 0;
    let count = 0;

    for (let i = 1; i < messages.length; i++) {
      if (messages[i].role === 'assistant' && messages[i-1].role === 'user') {
        const timeDiff = new Date(messages[i].createdAt) - new Date(messages[i-1].createdAt);
        totalTime += timeDiff;
        count++;
      }
    }

    return count > 0 ? Math.round(totalTime / count / 1000) : 0; // Return in seconds
  }
}

module.exports = new AgentOrchestrator();