// Agent Execution Service - Handles real AI agent execution
const { PrismaClient } = require('@prisma/client');
const axios = require('axios');
const memoryService = require('./memoryService');
const inferenceProviderService = require('./inferenceProviderService');
const prisma = new PrismaClient();

class AgentExecutionService {
  constructor() {
    this.activeAgents = new Map();
  }

  // Load agent configuration from database
  async loadAgent(agentId) {
    try {
      const agent = await prisma.agentLibrary.findUnique({
        where: { id: agentId },
        include: { user: true }
      });

      if (!agent) {
        throw new Error(`Agent ${agentId} not found`);
      }

      // Parse JSON fields
      agent.tags = JSON.parse(agent.tags || '[]');
      agent.tools = JSON.parse(agent.tools || '[]');
      
      // Parse new configuration fields
      agent.memoryConfig = JSON.parse(agent.memoryConfig || '{"shortTerm": true, "longTerm": false, "scope": "conversation"}');
      agent.providerConfig = JSON.parse(agent.providerConfig || '{}');

      return agent;
    } catch (error) {
      console.error('Error loading agent:', error);
      throw error;
    }
  }

  // Execute agent with user input
  async executeAgent(agentId, userInput, sessionId = null, userId = null) {
    try {
      // Load agent configuration
      const agent = await this.loadAgent(agentId);

      // Get or create session
      let session;
      if (sessionId) {
        session = await this.getSession(sessionId);
      } else {
        session = await this.createSession(agentId, userId);
      }

      // Build memory context for this interaction
      const memoryContext = await memoryService.buildContextFromMemories(
        agentId,
        userId,
        userInput
      );

      // Add user message to session
      const userMessage = {
        role: 'user',
        content: userInput,
        timestamp: new Date().toISOString()
      };

      // Get AI response based on provider (with memory context)
      const aiResponse = await this.getAIResponse(
        agent,
        userInput,
        session.messages || [],
        memoryContext
      );

      // Add assistant message to session
      const assistantMessage = {
        role: 'assistant',
        content: aiResponse,
        timestamp: new Date().toISOString(),
        model: agent.model,
        provider: agent.provider
      };

      // Update session with new messages
      const updatedMessages = [
        ...(session.messages || []),
        userMessage,
        assistantMessage
      ];

      await this.updateSession(session.id, updatedMessages);

      // Extract and store important facts from the conversation
      try {
        await memoryService.extractFactsFromConversation(
          [userMessage, assistantMessage],
          agentId,
          userId
        );
      } catch (memoryError) {
        console.error('Error extracting facts from conversation:', memoryError);
        // Don't fail the main request if memory extraction fails
      }

      return {
        success: true,
        response: aiResponse,
        sessionId: session.id,
        agent: {
          id: agent.id,
          name: agent.name,
          avatar: agent.icon
        },
        memoryContext: memoryContext ? 'Memory context used' : 'No memory context'
      };
    } catch (error) {
      console.error('Error executing agent:', error);
      throw error;
    }
  }

  // Get AI response from provider using new inference service
  async getAIResponse(agent, userInput, previousMessages = [], memoryContext = '') {
    try {
      // Build enhanced system prompt with memory context
      let systemPrompt = agent.systemPrompt || 'You are a helpful AI assistant.';
      
      // Add custom instructions if provided
      if (agent.customInstructions) {
        systemPrompt += '\n\nADDITIONAL INSTRUCTIONS:\n' + agent.customInstructions;
      }
      
      if (memoryContext && memoryContext.trim()) {
        systemPrompt += '\n\nRELEVANT CONTEXT FROM MEMORY:\n' + memoryContext;
        systemPrompt += '\n\nUse this context to provide more personalized and informed responses.';
      }

      // Build conversation prompt
      const conversationHistory = previousMessages.slice(-10).map(m => 
        `${m.role}: ${m.content}`
      ).join('\n');
      
      const fullPrompt = `${systemPrompt}\n\nCONVERSATION HISTORY:\n${conversationHistory}\n\nUser: ${userInput}\n\nAssistant:`;

      // Use the new inference provider service
      const options = {
        preferredProvider: agent.provider || agent.providerConfig?.provider,
        model: agent.model || agent.providerConfig?.model,
        temperature: agent.temperature || agent.providerConfig?.temperature || 0.7,
        maxTokens: agent.maxTokens || agent.providerConfig?.maxTokens || 2000,
        fallbacks: true,
        trackUsage: true
      };

      const result = await inferenceProviderService.executePrompt(fullPrompt, options);
      return result.content;
      
    } catch (error) {
      console.error('Error getting AI response:', error);
      
      // Fallback to direct provider calls if inference service fails
      console.log('Falling back to direct provider call...');
      return await this.getAIResponseDirectly(agent, userInput, previousMessages, memoryContext);
    }
  }

  // Fallback method using direct provider calls
  async getAIResponseDirectly(agent, userInput, previousMessages = [], memoryContext = '') {
    const provider = agent.provider || 'openrouter';
    const model = agent.model || 'gpt-3.5-turbo';

    // Build enhanced system prompt with memory context
    let systemPrompt = agent.systemPrompt || 'You are a helpful AI assistant.';
    
    if (agent.customInstructions) {
      systemPrompt += '\n\nADDITIONAL INSTRUCTIONS:\n' + agent.customInstructions;
    }
    
    if (memoryContext && memoryContext.trim()) {
      systemPrompt += '\n\nRELEVANT CONTEXT FROM MEMORY:\n' + memoryContext;
      systemPrompt += '\n\nUse this context to provide more personalized and informed responses.';
    }

    // Build messages array with enhanced system prompt
    const messages = [
      {
        role: 'system',
        content: systemPrompt
      },
      // Include previous messages for context (limit to last 10)
      ...previousMessages.slice(-10),
      {
        role: 'user',
        content: userInput
      }
    ];

    try {
      switch (provider) {
        case 'openrouter':
          return await this.callOpenRouter(model, messages, agent);
        case 'openai':
          return await this.callOpenAI(model, messages, agent);
        case 'anthropic':
          return await this.callAnthropic(model, messages, agent);
        case 'google':
          return await this.callGoogleAI(model, messages, agent);
        case 'ollama':
          return await this.callOllama(model, messages, agent);
        default:
          throw new Error(`Provider '${provider}' is not supported`);
      }
    } catch (error) {
      console.error(`Error calling ${provider}:`, error.message);
      throw error;
    }
  }

  // OpenRouter API call
  async callOpenRouter(model, messages, agent) {
    if (!process.env.OPENROUTER_API_KEY) {
      throw new Error('OpenRouter API key not configured');
    }

    const response = await axios.post(
      'https://openrouter.ai/api/v1/chat/completions',
      {
        model: model,
        messages: messages,
        temperature: agent.temperature || 0.7,
        max_tokens: agent.maxTokens || 2000,
        top_p: agent.topP || 1,
        frequency_penalty: agent.frequencyPenalty || 0,
        presence_penalty: agent.presencePenalty || 0
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
          'HTTP-Referer': 'https://crisis-management-ops.local',
          'X-Title': 'Crisis Management Ops',
          'Content-Type': 'application/json'
        },
        timeout: 30000
      }
    );

    return response.data.choices[0].message.content;
  }

  // OpenAI API call
  async callOpenAI(model, messages, agent) {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error('OpenAI API key not configured');
    }

    const response = await axios.post(
      'https://api.openai.com/v1/chat/completions',
      {
        model: model,
        messages: messages,
        temperature: agent.temperature || 0.7,
        max_tokens: agent.maxTokens || 2000,
        top_p: agent.topP || 1,
        frequency_penalty: agent.frequencyPenalty || 0,
        presence_penalty: agent.presencePenalty || 0
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
          'Content-Type': 'application/json'
        },
        timeout: 30000
      }
    );

    return response.data.choices[0].message.content;
  }

  // Anthropic API call
  async callAnthropic(model, messages, agent) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error('Anthropic API key not configured');
    }

    // Convert messages to Anthropic format
    const systemPrompt = messages.find(m => m.role === 'system')?.content || '';
    const anthropicMessages = messages
      .filter(m => m.role !== 'system')
      .map(m => ({
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content
      }));

    const response = await axios.post(
      'https://api.anthropic.com/v1/messages',
      {
        model: model,
        system: systemPrompt,
        messages: anthropicMessages,
        max_tokens: agent.maxTokens || 2000,
        temperature: agent.temperature || 0.7
      },
      {
        headers: {
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
          'Content-Type': 'application/json'
        },
        timeout: 30000
      }
    );

    return response.data.content[0].text;
  }

  // Google AI API call
  async callGoogleAI(model, messages, agent) {
    if (!process.env.GOOGLE_AI_API_KEY) {
      throw new Error('Google AI API key not configured');
    }

    // Convert messages to Google AI format
    const contents = messages
      .filter(m => m.role !== 'system')
      .map(m => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }]
      }));

    // Add system prompt as first user message if exists
    const systemPrompt = messages.find(m => m.role === 'system')?.content;
    if (systemPrompt) {
      contents.unshift({
        role: 'user',
        parts: [{ text: `System: ${systemPrompt}` }]
      });
    }

    const response = await axios.post(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${process.env.GOOGLE_AI_API_KEY}`,
      {
        contents: contents,
        generationConfig: {
          temperature: agent.temperature || 0.7,
          maxOutputTokens: agent.maxTokens || 2000,
          topP: agent.topP || 1
        }
      },
      {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 30000
      }
    );

    return response.data.candidates[0].content.parts[0].text;
  }

  // Ollama API call (local)
  async callOllama(model, messages, agent) {
    const ollamaUrl = process.env.OLLAMA_URL || 'http://localhost:11434';

    // Convert to Ollama format
    const prompt = messages.map(m => {
      if (m.role === 'system') return `System: ${m.content}`;
      if (m.role === 'user') return `User: ${m.content}`;
      if (m.role === 'assistant') return `Assistant: ${m.content}`;
      return m.content;
    }).join('\n\n') + '\n\nAssistant:';

    const response = await axios.post(
      `${ollamaUrl}/api/generate`,
      {
        model: model,
        prompt: prompt,
        options: {
          temperature: agent.temperature || 0.7,
          num_predict: agent.maxTokens || 2000,
          top_p: agent.topP || 1
        },
        stream: false
      },
      {
        timeout: 60000 // Longer timeout for local models
      }
    );

    return response.data.response;
  }

  // Mock response for testing
  async getMockResponse(agent, userInput) {
    const responses = [
      `As ${agent.name}, I understand your request regarding "${userInput}". Let me analyze this from my expertise in ${agent.category}.`,
      `Thank you for your query. Based on my role as ${agent.title || agent.name}, I can provide insights on this matter.`,
      `I'm processing your request about "${userInput}". My specialized knowledge in ${agent.category} allows me to offer comprehensive assistance.`,
      `Understood. As an AI agent specializing in ${agent.category}, I'll help you with this request.`
    ];

    // Simulate processing time
    await new Promise(resolve => setTimeout(resolve, 1000));

    return responses[Math.floor(Math.random() * responses.length)];
  }

  // Session management
  async createSession(agentId, userId) {
    try {
      const session = await prisma.agentSession.create({
        data: {
          agentId: agentId,
          userId: userId || 'anonymous',
          messages: JSON.stringify([]),
          context: JSON.stringify({
            startTime: new Date().toISOString(),
            platform: 'crisis-management-ops'
          })
        }
      });

      return {
        ...session,
        messages: []
      };
    } catch (error) {
      console.error('Error creating session:', error);
      // Return a temporary session if database fails
      return {
        id: `temp-${Date.now()}`,
        agentId,
        userId: userId || 'anonymous',
        messages: []
      };
    }
  }

  async getSession(sessionId) {
    try {
      const session = await prisma.agentSession.findUnique({
        where: { id: sessionId }
      });

      if (!session) {
        throw new Error(`Session ${sessionId} not found`);
      }

      return {
        ...session,
        messages: JSON.parse(session.messages || '[]'),
        context: JSON.parse(session.context || '{}')
      };
    } catch (error) {
      console.error('Error getting session:', error);
      // Return empty session if not found
      return {
        id: sessionId,
        messages: []
      };
    }
  }

  async updateSession(sessionId, messages) {
    try {
      // Skip update for temporary sessions
      if (sessionId.startsWith('temp-')) {
        return;
      }

      await prisma.agentSession.update({
        where: { id: sessionId },
        data: {
          messages: JSON.stringify(messages),
          updatedAt: new Date()
        }
      });
    } catch (error) {
      console.error('Error updating session:', error);
      // Continue without saving if update fails
    }
  }

  // Get active agents for a domain
  async getActiveAgentsForDomain(domain) {
    try {
      const agents = await prisma.agentLibrary.findMany({
        where: {
          category: domain,
          isDeleted: false
        },
        take: 5
      });

      return agents.map(agent => ({
        id: agent.id,
        name: agent.name,
        title: agent.description,
        avatar: agent.icon || '🤖',
        status: 'active',
        systemPrompt: agent.systemPrompt,
        provider: agent.provider,
        model: agent.model
      }));
    } catch (error) {
      console.error('Error loading domain agents:', error);
      return [];
    }
  }
}

module.exports = AgentExecutionService;