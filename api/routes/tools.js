const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const agentToolsService = require('../../core/services/agentToolsService');

// Get all tools
router.get('/', async (req, res) => {
  try {
    const { type, isActive } = req.query;

    const where = {};
    if (type) where.type = type;
    if (isActive !== undefined) where.isActive = isActive === 'true';

    const tools = await prisma.tool.findMany({ where });
    res.json(tools);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Execute tool
router.post('/:id/execute', async (req, res) => {
  try {
    const tool = await prisma.tool.findUnique({
      where: { id: req.params.id }
    });

    if (!tool) {
      return res.status(404).json({ error: 'Tool not found' });
    }

    const result = await agentToolsService.executeTool({
      toolId: tool.id,
      toolName: tool.name,
      parameters: req.body
    });

    // Update usage stats
    await prisma.tool.update({
      where: { id: tool.id },
      data: {
        usageCount: { increment: 1 },
        lastUsedAt: new Date()
      }
    });

    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;