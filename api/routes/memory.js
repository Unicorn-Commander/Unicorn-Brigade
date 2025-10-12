const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Store memory
router.post('/', async (req, res) => {
  try {
    const memory = await prisma.memory.create({
      data: req.body
    });
    res.status(201).json(memory);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Search memories
router.post('/search', async (req, res) => {
  try {
    const { query, agentId, type, scope, limit = 10 } = req.body;

    const where = {};
    if (agentId) where.agentId = agentId;
    if (type) where.type = type;
    if (scope) where.scope = scope;

    const memories = await prisma.memory.findMany({
      where,
      orderBy: { lastAccessedAt: 'desc' },
      take: parseInt(limit)
    });

    // Update access stats
    const memoryIds = memories.map(m => m.id);
    await prisma.memory.updateMany({
      where: { id: { in: memoryIds } },
      data: {
        accessCount: { increment: 1 },
        lastAccessedAt: new Date()
      }
    });

    res.json(memories);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;