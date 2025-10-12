const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Get workflows
router.get('/', async (req, res) => {
  try {
    const workflows = await prisma.workflow.findMany({
      where: { isActive: true },
      orderBy: { createdAt: 'desc' }
    });
    res.json(workflows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create workflow
router.post('/', async (req, res) => {
  try {
    const workflow = await prisma.workflow.create({
      data: {
        ...req.body,
        definition: JSON.stringify(req.body.definition),
        triggers: JSON.stringify(req.body.triggers || [])
      }
    });
    res.status(201).json(workflow);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Execute workflow
router.post('/:id/execute', async (req, res) => {
  try {
    const workflow = await prisma.workflow.findUnique({
      where: { id: req.params.id }
    });

    if (!workflow) {
      return res.status(404).json({ error: 'Workflow not found' });
    }

    // Update run stats
    await prisma.workflow.update({
      where: { id: workflow.id },
      data: {
        runCount: { increment: 1 },
        lastRunAt: new Date()
      }
    });

    // Execute workflow through orchestrator
    const agentOrchestrator = require('../../core/services/agentOrchestrator');
    const result = await agentOrchestrator.executeWorkflow(workflow, req.body);

    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;