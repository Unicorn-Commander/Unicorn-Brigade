const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const bcrypt = require('bcrypt');
const crypto = require('crypto');

// ==================== AGENT CRUD OPERATIONS ====================

/**
 * GET /api/agents - List all agents
 * Query params: domain, subdomain, status, type, rank, search, limit, offset
 */
router.get('/', async (req, res) => {
  try {
    const {
      domain,
      subdomain,
      status,
      type,
      rank,
      search,
      limit = 50,
      offset = 0
    } = req.query;

    const where = {};

    // Filter by domain
    if (domain) where.domain = domain;
    if (subdomain) where.subdomain = subdomain;
    if (status) where.status = status;
    if (type) where.type = type;
    if (rank) where.rank = rank;

    // Search by name, title, or bio
    if (search) {
      where.OR = [
        { name: { contains: search, mode: 'insensitive' } },
        { title: { contains: search, mode: 'insensitive' } },
        { bio: { contains: search, mode: 'insensitive' } }
      ];
    }

    const agents = await prisma.agent.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit),
      skip: parseInt(offset),
      include: {
        agentTools: {
          include: {
            tool: true
          }
        },
        _count: {
          select: {
            messages: true,
            tasks: true,
            apiKeys: true
          }
        }
      }
    });

    // Parse JSON fields
    const formattedAgents = agents.map(agent => ({
      ...agent,
      capabilities: JSON.parse(agent.capabilities || '[]'),
      memory: JSON.parse(agent.memory || '{}'),
      performance: JSON.parse(agent.performance || '{}')
    }));

    // Count total for pagination
    const total = await prisma.agent.count({ where });

    res.json({
      agents: formattedAgents,
      total,
      limit: parseInt(limit),
      offset: parseInt(offset)
    });
  } catch (error) {
    console.error('Error fetching agents:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/agents/domains - List available domains with agent counts
 */
router.get('/domains', async (req, res) => {
  try {
    const domains = await prisma.agent.groupBy({
      by: ['domain'],
      _count: {
        domain: true
      },
      where: {
        domain: { not: null }
      }
    });

    const subdomains = await prisma.agent.groupBy({
      by: ['subdomain'],
      _count: {
        subdomain: true
      },
      where: {
        subdomain: { not: null }
      }
    });

    res.json({
      domains: domains.map(d => ({
        name: d.domain,
        count: d._count.domain
      })),
      subdomains: subdomains.map(s => ({
        name: s.subdomain,
        count: s._count.subdomain
      }))
    });
  } catch (error) {
    console.error('Error fetching domains:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/agents/:id - Get agent details
 */
router.get('/:id', async (req, res) => {
  try {
    const agent = await prisma.agent.findUnique({
      where: { id: req.params.id },
      include: {
        agentTools: {
          include: {
            tool: true
          }
        },
        apiKeys: {
          select: {
            id: true,
            name: true,
            keyPrefix: true,
            permissions: true,
            rateLimit: true,
            expiresAt: true,
            lastUsedAt: true,
            usageCount: true,
            isActive: true,
            createdAt: true
          }
        },
        messages: {
          take: 10,
          orderBy: { createdAt: 'desc' }
        },
        tasks: {
          take: 10,
          orderBy: { createdAt: 'desc' }
        },
        _count: {
          select: {
            messages: true,
            tasks: true,
            memories: true
          }
        }
      }
    });

    if (!agent) {
      return res.status(404).json({ error: 'Agent not found' });
    }

    // Parse JSON fields
    const formattedAgent = {
      ...agent,
      capabilities: JSON.parse(agent.capabilities || '[]'),
      memory: JSON.parse(agent.memory || '{}'),
      performance: JSON.parse(agent.performance || '{}'),
      apiKeys: agent.apiKeys.map(key => ({
        ...key,
        permissions: JSON.parse(key.permissions || '[]')
      }))
    };

    res.json(formattedAgent);
  } catch (error) {
    console.error('Error fetching agent:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /api/agents - Create new agent
 * This is called by The General when creating agents
 */
router.post('/', async (req, res) => {
  try {
    const {
      name,
      displayName,
      title,
      type = 'individual',
      domain,
      subdomain,
      department,
      rank,
      avatar,
      avatarUrl,
      avatarStyle,
      bio,
      persona,
      systemPrompt,
      status = 'draft',
      capabilities = [],
      model = 'gpt-4-turbo',
      temperature = 0.7,
      maxTokens = 4096,
      requiresAuth = false,
      pricingModel = 'free',
      basePrice,
      version = '1.0.0',
      createdBy,
      createdByAgent,
      tools = [] // Array of tool IDs
    } = req.body;

    // Validate required fields
    if (!name) {
      return res.status(400).json({ error: 'Agent name is required' });
    }
    if (!systemPrompt) {
      return res.status(400).json({ error: 'System prompt is required' });
    }

    // Create agent
    const agent = await prisma.agent.create({
      data: {
        name,
        displayName: displayName || name,
        title,
        type,
        domain,
        subdomain,
        department,
        rank,
        avatar,
        avatarUrl,
        avatarStyle,
        bio,
        persona: persona || '',
        systemPrompt,
        status,
        capabilities: JSON.stringify(capabilities),
        memory: JSON.stringify({}),
        performance: JSON.stringify({}),
        model,
        temperature,
        maxTokens,
        requiresAuth,
        pricingModel,
        basePrice,
        version,
        createdBy,
        createdByAgent
      }
    });

    // Attach tools if provided
    if (tools && tools.length > 0) {
      await Promise.all(
        tools.map(toolId =>
          prisma.agentTool.create({
            data: {
              agentId: agent.id,
              toolId: toolId,
              config: JSON.stringify({})
            }
          })
        )
      );
    }

    // Fetch complete agent with relations
    const completeAgent = await prisma.agent.findUnique({
      where: { id: agent.id },
      include: {
        agentTools: {
          include: {
            tool: true
          }
        }
      }
    });

    // Emit to WebSocket
    const io = req.app.get('io');
    if (io) {
      io.emit('agent-created', completeAgent);
    }

    res.status(201).json({
      ...completeAgent,
      capabilities: JSON.parse(completeAgent.capabilities),
      memory: JSON.parse(completeAgent.memory),
      performance: JSON.parse(completeAgent.performance)
    });
  } catch (error) {
    console.error('Error creating agent:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * PUT /api/agents/:id - Update agent
 */
router.put('/:id', async (req, res) => {
  try {
    const updates = { ...req.body };

    // Convert arrays/objects to JSON strings
    if (updates.capabilities) {
      updates.capabilities = JSON.stringify(updates.capabilities);
    }
    if (updates.memory) {
      updates.memory = JSON.stringify(updates.memory);
    }
    if (updates.performance) {
      updates.performance = JSON.stringify(updates.performance);
    }

    // Remove fields that shouldn't be updated directly
    delete updates.id;
    delete updates.createdAt;
    delete updates.agentTools;
    delete updates.apiKeys;

    const agent = await prisma.agent.update({
      where: { id: req.params.id },
      data: updates,
      include: {
        agentTools: {
          include: {
            tool: true
          }
        }
      }
    });

    // Emit to WebSocket
    const io = req.app.get('io');
    if (io) {
      io.emit('agent-updated', agent);
    }

    res.json({
      ...agent,
      capabilities: JSON.parse(agent.capabilities),
      memory: JSON.parse(agent.memory),
      performance: JSON.parse(agent.performance)
    });
  } catch (error) {
    console.error('Error updating agent:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * DELETE /api/agents/:id - Delete agent
 */
router.delete('/:id', async (req, res) => {
  try {
    await prisma.agent.delete({
      where: { id: req.params.id }
    });

    // Emit to WebSocket
    const io = req.app.get('io');
    if (io) {
      io.emit('agent-deleted', { id: req.params.id });
    }

    res.status(204).send();
  } catch (error) {
    console.error('Error deleting agent:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== AGENT CARD & A2A PROTOCOL ====================

/**
 * GET /api/agents/:id/card - Get A2A Agent Card
 * Returns standardized agent card for Agent-to-Agent protocol
 */
router.get('/:id/card', async (req, res) => {
  try {
    const agent = await prisma.agent.findUnique({
      where: { id: req.params.id },
      include: {
        agentTools: {
          include: {
            tool: true
          }
        }
      }
    });

    if (!agent) {
      return res.status(404).json({ error: 'Agent not found' });
    }

    // Generate A2A Agent Card
    const card = {
      id: agent.id,
      name: agent.name,
      displayName: agent.displayName,
      title: agent.title,
      domain: agent.domain,
      subdomain: agent.subdomain,
      rank: agent.rank,
      avatar: agent.avatar || agent.avatarUrl,
      bio: agent.bio,
      version: agent.version,
      status: agent.status,
      capabilities: JSON.parse(agent.capabilities || '[]'),
      tools: agent.agentTools.map(at => ({
        id: at.tool.id,
        name: at.tool.name,
        type: at.tool.type,
        description: at.tool.description
      })),
      endpoint: `${process.env.BACKEND_URL || 'http://localhost:8112'}/api/agents/${agent.id}/invoke`,
      authentication: {
        required: agent.requiresAuth,
        type: agent.requiresAuth ? 'api-key' : 'none'
      },
      pricing: {
        model: agent.pricingModel,
        basePrice: agent.basePrice,
        currency: 'USD'
      },
      protocol: 'A2A/1.0',
      createdAt: agent.createdAt,
      updatedAt: agent.updatedAt
    };

    res.json(card);
  } catch (error) {
    console.error('Error generating agent card:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== AGENT INVOCATION ====================

/**
 * POST /api/agents/:id/invoke - Invoke agent with a request
 * Used for A2A protocol and direct agent invocation
 */
router.post('/:id/invoke', async (req, res) => {
  try {
    const { message, context, stream = false } = req.body;
    const agentId = req.params.id;

    // Get agent
    const agent = await prisma.agent.findUnique({
      where: { id: agentId },
      include: {
        agentTools: {
          include: {
            tool: true
          }
        }
      }
    });

    if (!agent) {
      return res.status(404).json({ error: 'Agent not found' });
    }

    if (agent.status !== 'active') {
      return res.status(400).json({ error: 'Agent is not active' });
    }

    // Check authentication if required
    if (agent.requiresAuth) {
      const apiKey = req.headers['x-api-key'];
      if (!apiKey) {
        return res.status(401).json({ error: 'API key required' });
      }

      // Validate API key
      const keyPrefix = apiKey.substring(0, 8);
      const keyHash = crypto.createHash('sha256').update(apiKey).digest('hex');

      const validKey = await prisma.agentApiKey.findFirst({
        where: {
          agentId: agentId,
          keyPrefix: keyPrefix,
          keyHash: keyHash,
          isActive: true,
          OR: [
            { expiresAt: null },
            { expiresAt: { gt: new Date() } }
          ]
        }
      });

      if (!validKey) {
        return res.status(403).json({ error: 'Invalid or expired API key' });
      }

      // Update usage stats
      await prisma.agentApiKey.update({
        where: { id: validKey.id },
        data: {
          usageCount: { increment: 1 },
          lastUsedAt: new Date()
        }
      });
    }

    // Prepare messages for LLM
    const litellm = require('../../core/services/litellmProvider');

    const messages = [
      { role: 'system', content: agent.systemPrompt }
    ];

    if (context) {
      messages.push({
        role: 'system',
        content: `Additional Context: ${JSON.stringify(context)}`
      });
    }

    messages.push({ role: 'user', content: message });

    // Store user message
    await prisma.agentMessage.create({
      data: {
        agentId: agent.id,
        role: 'user',
        content: message,
        metadata: JSON.stringify({ context, invocation: true })
      }
    });

    // Update agent status
    await prisma.agent.update({
      where: { id: agent.id },
      data: { status: 'busy' }
    });

    try {
      // Send to LLM
      const response = await litellm.sendMessage(
        agent.model,
        messages,
        {
          temperature: agent.temperature,
          maxTokens: agent.maxTokens
        }
      );

      // Store assistant response
      await prisma.agentMessage.create({
        data: {
          agentId: agent.id,
          role: 'assistant',
          content: response.content,
          metadata: JSON.stringify({
            model: response.model,
            usage: response.usage,
            invocation: true
          })
        }
      });

      // Update performance metrics
      const performance = JSON.parse(agent.performance || '{}');
      performance.totalInvocations = (performance.totalInvocations || 0) + 1;
      performance.totalTokens = (performance.totalTokens || 0) + (response.usage?.total_tokens || 0);
      performance.lastInvocation = new Date().toISOString();

      await prisma.agent.update({
        where: { id: agent.id },
        data: {
          status: 'active',
          performance: JSON.stringify(performance)
        }
      });

      res.json({
        response: response.content,
        usage: response.usage,
        model: response.model,
        agentId: agent.id,
        agentName: agent.name
      });
    } catch (error) {
      // Reset agent status on error
      await prisma.agent.update({
        where: { id: agent.id },
        data: { status: 'active' }
      });
      throw error;
    }
  } catch (error) {
    console.error('Error invoking agent:', error);
    res.status(500).json({ error: error.message });
  }
});

// ==================== API KEY MANAGEMENT ====================

/**
 * POST /api/agents/:id/api-keys - Generate new API key for agent
 */
router.post('/:id/api-keys', async (req, res) => {
  try {
    const { name, permissions = [], rateLimit, expiresAt } = req.body;
    const agentId = req.params.id;

    // Generate API key
    const apiKey = `ub_${crypto.randomBytes(32).toString('hex')}`;
    const keyHash = crypto.createHash('sha256').update(apiKey).digest('hex');
    const keyPrefix = apiKey.substring(0, 8);

    const apiKeyRecord = await prisma.agentApiKey.create({
      data: {
        agentId,
        name,
        keyHash,
        keyPrefix,
        permissions: JSON.stringify(permissions),
        rateLimit,
        expiresAt: expiresAt ? new Date(expiresAt) : null
      }
    });

    res.status(201).json({
      ...apiKeyRecord,
      apiKey: apiKey, // Only returned once on creation
      permissions: JSON.parse(apiKeyRecord.permissions)
    });
  } catch (error) {
    console.error('Error creating API key:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * DELETE /api/agents/:id/api-keys/:keyId - Revoke API key
 */
router.delete('/:id/api-keys/:keyId', async (req, res) => {
  try {
    await prisma.agentApiKey.delete({
      where: {
        id: req.params.keyId,
        agentId: req.params.id
      }
    });

    res.status(204).send();
  } catch (error) {
    console.error('Error deleting API key:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
