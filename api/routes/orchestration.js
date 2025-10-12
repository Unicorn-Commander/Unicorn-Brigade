const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const agentOrchestrator = require('../../core/services/agentOrchestrator');

// Start new orchestration
router.post('/start', async (req, res) => {
  try {
    const { name, type, orchestratorId, participantIds, config } = req.body;

    // Create orchestration record
    const orchestration = await prisma.orchestration.create({
      data: {
        name,
        type,
        orchestratorId,
        config: JSON.stringify(config || {}),
        status: 'executing'
      }
    });

    // Start async orchestration
    agentOrchestrator.startOrchestration({
      orchestrationId: orchestration.id,
      participantIds,
      config
    });

    res.status(201).json(orchestration);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get orchestration status
router.get('/:id', async (req, res) => {
  try {
    const orchestration = await prisma.orchestration.findUnique({
      where: { id: req.params.id },
      include: {
        orchestrator: true,
        participants: true,
        tasks: true
      }
    });

    if (!orchestration) {
      return res.status(404).json({ error: 'Orchestration not found' });
    }

    res.json(orchestration);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// List orchestrations
router.get('/', async (req, res) => {
  try {
    const { status, type, limit = 50 } = req.query;

    const where = {};
    if (status) where.status = status;
    if (type) where.type = type;

    const orchestrations = await prisma.orchestration.findMany({
      where,
      include: { orchestrator: true },
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit)
    });

    res.json(orchestrations);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Cancel orchestration
router.post('/:id/cancel', async (req, res) => {
  try {
    const orchestration = await prisma.orchestration.update({
      where: { id: req.params.id },
      data: { status: 'cancelled' }
    });

    // Cancel all related tasks
    await prisma.agentTask.updateMany({
      where: {
        orchestrationId: req.params.id,
        status: { in: ['pending', 'in_progress'] }
      },
      data: { status: 'cancelled' }
    });

    res.json(orchestration);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;