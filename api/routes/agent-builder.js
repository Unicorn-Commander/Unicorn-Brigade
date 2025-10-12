const express = require('express');
const router = express.Router();
const agentBuilderService = require('../../core/services/agentBuilderService');
const { v4: uuidv4 } = require('uuid');

/**
 * POST /api/agent-builder/chat - Chat with The General
 */
router.post('/chat', async (req, res) => {
  try {
    const { message, sessionId, userId } = req.body;

    if (!message) {
      return res.status(400).json({ error: 'Message is required' });
    }

    // Generate session ID if not provided
    const actualSessionId = sessionId || uuidv4();

    // Chat with The General
    const response = await agentBuilderService.chat(
      actualSessionId,
      message,
      { userId }
    );

    res.json(response);
  } catch (error) {
    console.error('Error in agent builder chat:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * POST /api/agent-builder/create - Create agent from configuration
 */
router.post('/create', async (req, res) => {
  try {
    const { config, userId } = req.body;

    if (!config) {
      return res.status(400).json({ error: 'Agent configuration is required' });
    }

    // Create agent
    const agent = await agentBuilderService.createAgent(config, userId);

    res.status(201).json(agent);
  } catch (error) {
    console.error('Error creating agent:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/agent-builder/session/:sessionId - Get conversation history
 */
router.get('/session/:sessionId', async (req, res) => {
  try {
    const history = agentBuilderService.getHistory(req.params.sessionId);
    res.json({ history });
  } catch (error) {
    console.error('Error fetching session history:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * DELETE /api/agent-builder/session/:sessionId - Clear conversation history
 */
router.delete('/session/:sessionId', async (req, res) => {
  try {
    agentBuilderService.clearSession(req.params.sessionId);
    res.status(204).send();
  } catch (error) {
    console.error('Error clearing session:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * GET /api/agent-builder/info - Get service information
 */
router.get('/info', async (req, res) => {
  try {
    const info = agentBuilderService.getInfo();
    res.json(info);
  } catch (error) {
    console.error('Error fetching service info:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
