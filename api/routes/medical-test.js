const express = require('express');
const router = express.Router();
const OpenRouterProvider = require('../../backend/services/openRouterProvider');

/**
 * Test endpoint to verify OpenRouter integration
 */
router.post('/test-openrouter', async (req, res) => {
  try {
    const { apiKey, message = 'Hello, Dr. Glitter Mane!' } = req.body;

    // Initialize OpenRouter with the provided key
    const provider = new OpenRouterProvider(apiKey);

    // Test with a simple medical prompt
    const response = await provider.complete({
      messages: [
        {
          role: 'system',
          content: 'You are Dr. Glitter Mane, a friendly and knowledgeable medical AI assistant.'
        },
        {
          role: 'user',
          content: message
        }
      ],
      model: 'default',
      temperature: 0.7,
      max_tokens: 500
    });

    res.json({
      success: true,
      message: 'OpenRouter test successful!',
      response: response.content,
      model: response.model,
      usage: response.usage
    });

  } catch (error) {
    console.error('OpenRouter test failed:', error);
    res.status(500).json({
      success: false,
      error: error.message,
      hint: 'Make sure you have a valid OpenRouter API key'
    });
  }
});

/**
 * Test medical orchestrator with real AI
 */
router.post('/test-consultation', async (req, res) => {
  try {
    const { apiKey, symptoms } = req.body;

    if (!apiKey) {
      return res.status(400).json({
        success: false,
        error: 'API key required for testing'
      });
    }

    // Get orchestrator from app locals
    const orchestrator = req.app.locals.medicalOrchestrator;

    if (!orchestrator) {
      return res.status(503).json({
        success: false,
        error: 'Medical orchestrator not initialized'
      });
    }

    // Set the API key for this test
    orchestrator.inferenceProvider = new OpenRouterProvider(apiKey);

    // Start a test consultation
    const result = await orchestrator.startConsultation(
      'test-user',
      symptoms || 'I have a headache and feel tired',
      { test: true }
    );

    res.json({
      success: true,
      consultationId: result.consultationId,
      response: result.response
    });

  } catch (error) {
    console.error('Consultation test failed:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

module.exports = router;