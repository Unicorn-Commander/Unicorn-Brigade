const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Get all agents
router.get('/', async (req, res) => {
  try {
    const { domain, type, status } = req.query;

    const where = {};
    if (domain) where.domain = domain;
    if (type) where.type = type;
    if (status) where.status = status;

    const agents = await prisma.agent.findMany({
      where,
      orderBy: { createdAt: 'desc' }
    });

    res.json(agents);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get specific agent
router.get('/:id', async (req, res) => {
  try {
    const agent = await prisma.agent.findUnique({
      where: { id: req.params.id },
      include: {
        messages: { take: 10, orderBy: { createdAt: 'desc' } },
        tasks: { take: 10, orderBy: { createdAt: 'desc' } }
      }
    });

    if (!agent) {
      return res.status(404).json({ error: 'Agent not found' });
    }

    res.json(agent);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create new agent
router.post('/', async (req, res) => {
  try {
    const agent = await prisma.agent.create({
      data: {
        ...req.body,
        tools: JSON.stringify(req.body.tools || []),
        capabilities: JSON.stringify(req.body.capabilities || []),
        memory: JSON.stringify(req.body.memory || {})
      }
    });

    // Emit to WebSocket
    const io = req.app.get('io');
    if (io) {
      io.emit('agent-created', agent);
    }

    res.status(201).json(agent);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update agent
router.put('/:id', async (req, res) => {
  try {
    const updates = { ...req.body };
    if (updates.tools) updates.tools = JSON.stringify(updates.tools);
    if (updates.capabilities) updates.capabilities = JSON.stringify(updates.capabilities);
    if (updates.memory) updates.memory = JSON.stringify(updates.memory);

    const agent = await prisma.agent.update({
      where: { id: req.params.id },
      data: updates
    });

    res.json(agent);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Delete agent
router.delete('/:id', async (req, res) => {
  try {
    await prisma.agent.delete({
      where: { id: req.params.id }
    });

    res.status(204).send();
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Chat with agent
router.post('/:id/chat', async (req, res) => {
  try {
    const { message } = req.body;
    const agentId = req.params.id;

    // Store user message
    await prisma.agentMessage.create({
      data: {
        agentId,
        role: 'user',
        content: message
      }
    });

    // Process through agent orchestrator
    const agentOrchestrator = require('../../core/services/agentOrchestrator');
    const response = await agentOrchestrator.processAgentMessage(agentId, message);

    // Store agent response
    await prisma.agentMessage.create({
      data: {
        agentId,
        role: 'assistant',
        content: response.content,
        metadata: JSON.stringify(response.metadata || {})
      }
    });

    res.json(response);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get agent messages
router.get('/:id/messages', async (req, res) => {
  try {
    const { limit = 50, offset = 0 } = req.query;

    const messages = await prisma.agentMessage.findMany({
      where: { agentId: req.params.id },
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit),
      skip: parseInt(offset)
    });

    res.json(messages);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get agent tasks
router.get('/:id/tasks', async (req, res) => {
  try {
    const { status, limit = 50 } = req.query;

    const where = { agentId: req.params.id };
    if (status) where.status = status;

    const tasks = await prisma.agentTask.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit)
    });

    res.json(tasks);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;