const express = require('express');
const router = express.Router();
const crypto = require('crypto');
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Encryption settings
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'your-32-character-encryption-key-here!';
const ALGORITHM = 'aes-256-gcm';

// Encrypt API key
function encryptApiKey(apiKey) {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv(ALGORITHM, Buffer.from(ENCRYPTION_KEY.slice(0, 32)), iv);

  let encrypted = cipher.update(apiKey, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const authTag = cipher.getAuthTag();

  return JSON.stringify({
    encrypted: encrypted,
    iv: iv.toString('hex'),
    authTag: authTag.toString('hex')
  });
}

// Decrypt API key
function decryptApiKey(encryptedString) {
  try {
    const encryptedData = JSON.parse(encryptedString);
    const decipher = crypto.createDecipheriv(
      ALGORITHM,
      Buffer.from(ENCRYPTION_KEY.slice(0, 32)),
      Buffer.from(encryptedData.iv, 'hex')
    );

    decipher.setAuthTag(Buffer.from(encryptedData.authTag, 'hex'));

    let decrypted = decipher.update(encryptedData.encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  } catch (error) {
    console.error('Error decrypting API key:', error);
    return null;
  }
}

// Get all providers
router.get('/', async (req, res) => {
  try {
    const providers = await prisma.aIProvider.findMany({
      orderBy: { createdAt: 'desc' }
    });

    // Check if user wants to see decrypted keys
    const showKeys = req.query.showKeys === 'true';

    // Process providers
    const sanitized = providers.map(p => {
      const config = JSON.parse(p.config || '{}');
      let displayKey = '***';

      // If showKeys is true, decrypt and return the actual key
      if (showKeys && p.apiKey) {
        const decryptedKey = decryptApiKey(p.apiKey);
        if (decryptedKey) {
          // Partially mask the key for security (show first 10 and last 4 chars)
          const keyLength = decryptedKey.length;
          if (keyLength > 20) {
            displayKey = decryptedKey.slice(0, 10) + '•'.repeat(keyLength - 14) + decryptedKey.slice(-4);
          } else {
            displayKey = decryptedKey;
          }
        }
      }

      return {
        ...p,
        config,
        apiKey: displayKey,
        hasApiKey: !!p.apiKey
      };
    });

    res.json(sanitized);
  } catch (error) {
    console.error('Error fetching providers:', error);
    res.status(500).json({ error: 'Failed to fetch providers' });
  }
});

// Add new provider
router.post('/', async (req, res) => {
  try {
    const { name, type, endpoint, apiKey, models, settings } = req.body;

    // Encrypt the API key
    const encryptedKey = encryptApiKey(apiKey);

    const provider = await prisma.aIProvider.create({
      data: {
        name,
        type,
        endpoint,
        apiKey: encryptedKey,
        config: JSON.stringify({
          models: models || [],
          settings: settings || {}
        }),
        isActive: true,
        isDefault: false,
        usageStats: JSON.stringify({
          totalRequests: 0,
          totalTokens: 0,
          totalCost: 0
        })
      }
    });

    res.json({
      ...provider,
      config: JSON.parse(provider.config || '{}'),
      apiKey: '***'
    });
  } catch (error) {
    console.error('Error adding provider:', error);
    res.status(500).json({ error: 'Failed to add provider' });
  }
});

// Update provider
router.put('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { name, endpoint, apiKey, models, settings, isActive } = req.body;

    const updateData = {};

    if (name !== undefined) updateData.name = name;
    if (endpoint !== undefined) updateData.endpoint = endpoint;
    if (isActive !== undefined) updateData.isActive = isActive;

    // Update API key if provided
    if (apiKey && apiKey !== '***') {
      updateData.apiKey = encryptApiKey(apiKey);
    }

    // Update config if models or settings provided
    if (models || settings) {
      const existing = await prisma.aIProvider.findUnique({ where: { id } });
      const existingConfig = JSON.parse(existing.config || '{}');

      updateData.config = JSON.stringify({
        models: models || existingConfig.models || [],
        settings: settings || existingConfig.settings || {}
      });
    }

    const provider = await prisma.aIProvider.update({
      where: { id },
      data: updateData
    });

    res.json({
      ...provider,
      config: JSON.parse(provider.config || '{}'),
      apiKey: '***'
    });
  } catch (error) {
    console.error('Error updating provider:', error);
    res.status(500).json({ error: 'Failed to update provider' });
  }
});

// Delete provider
router.delete('/:id', async (req, res) => {
  try {
    await prisma.aIProvider.delete({
      where: { id: req.params.id }
    });
    res.json({ success: true });
  } catch (error) {
    console.error('Error deleting provider:', error);
    res.status(500).json({ error: 'Failed to delete provider' });
  }
});

// Test provider connection
router.post('/:id/test', async (req, res) => {
  try {
    const provider = await prisma.aIProvider.findUnique({
      where: { id: req.params.id }
    });

    if (!provider) {
      return res.status(404).json({ error: 'Provider not found' });
    }

    const apiKey = decryptApiKey(provider.apiKey);
    if (!apiKey) {
      return res.status(500).json({ error: 'Failed to decrypt API key' });
    }

    // Test based on provider type
    let testResult = { success: false, message: 'Unknown provider type' };

    switch (provider.type) {
      case 'openrouter':
        testResult = await testOpenRouter(apiKey, provider.endpoint);
        break;
      case 'openai':
        testResult = await testOpenAI(apiKey);
        break;
      case 'anthropic':
        testResult = await testAnthropic(apiKey);
        break;
      case 'google':
        testResult = await testGoogleAI(apiKey);
        break;
      case 'ollama':
        testResult = await testOllama(provider.endpoint);
        break;
    }

    // Update last used timestamp if test successful
    if (testResult.success) {
      await prisma.aIProvider.update({
        where: { id: req.params.id },
        data: { lastUsedAt: new Date() }
      });
    }

    res.json(testResult);
  } catch (error) {
    console.error('Error testing provider:', error);
    res.status(500).json({ error: 'Failed to test provider', details: error.message });
  }
});

// Quick setup for OpenRouter
router.post('/quick-setup/openrouter', async (req, res) => {
  try {
    const { apiKey, name = 'OpenRouter Main' } = req.body;

    if (!apiKey) {
      return res.status(400).json({ error: 'API key is required' });
    }

    // Test the API key first
    const testResult = await testOpenRouter(apiKey, 'https://openrouter.ai/api/v1');

    if (!testResult.success) {
      return res.status(400).json({ error: 'Invalid API key', details: testResult.message });
    }

    // Check if provider already exists
    const existingProvider = await prisma.aIProvider.findFirst({
      where: {
        type: 'openrouter',
        name: name
      }
    });

    if (existingProvider) {
      // Update existing provider
      const provider = await prisma.aIProvider.update({
        where: { id: existingProvider.id },
        data: {
          apiKey: encryptApiKey(apiKey),
          endpoint: 'https://openrouter.ai/api/v1',
          config: JSON.stringify({
            models: testResult.models || [
              'claude-3-opus-20240229',
              'claude-3-sonnet-20240229',
              'gpt-4-turbo-preview',
              'gpt-3.5-turbo',
              'mistral-large',
              'llama-3-70b-instruct'
            ],
            settings: {
              defaultModel: 'claude-3-sonnet-20240229',
              maxTokens: 4096,
              temperature: 0.7
            }
          }),
          isActive: true,
          lastUsedAt: new Date()
        }
      });

      return res.json({
        success: true,
        provider: {
          ...provider,
          config: JSON.parse(provider.config || '{}'),
          apiKey: '***'
        },
        models: testResult.models,
        message: 'OpenRouter updated successfully!'
      });
    }

    // Create new provider
    const provider = await prisma.aIProvider.create({
      data: {
        name,
        type: 'openrouter',
        endpoint: 'https://openrouter.ai/api/v1',
        apiKey: encryptApiKey(apiKey),
        config: JSON.stringify({
          models: testResult.models || [
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'gpt-4-turbo-preview',
            'gpt-3.5-turbo',
            'mistral-large',
            'llama-3-70b-instruct'
          ],
          settings: {
            defaultModel: 'claude-3-sonnet-20240229',
            maxTokens: 4096,
            temperature: 0.7
          }
        }),
        isActive: true,
        isDefault: true, // Make it default if it's the first one
        usageStats: JSON.stringify({
          totalRequests: 0,
          totalTokens: 0,
          totalCost: 0
        }),
        lastUsedAt: new Date()
      }
    });

    res.json({
      success: true,
      provider: {
        ...provider,
        config: JSON.parse(provider.config || '{}'),
        apiKey: '***'
      },
      models: testResult.models,
      message: 'OpenRouter configured successfully!'
    });
  } catch (error) {
    console.error('Error in quick setup:', error);
    res.status(500).json({ error: 'Failed to setup OpenRouter', details: error.message });
  }
});

// Test functions for each provider
async function testOpenRouter(apiKey, endpoint) {
  try {
    const response = await fetch(`${endpoint}/models`, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      const data = await response.json();
      const models = data.data?.map(m => m.id) || [];
      return {
        success: true,
        message: `Connected! Found ${models.length} models available.`,
        models: models.slice(0, 50) // Return first 50 models
      };
    } else {
      const error = await response.text();
      return { success: false, message: `Connection failed: ${error}` };
    }
  } catch (error) {
    return { success: false, message: `Connection error: ${error.message}` };
  }
}

async function testOpenAI(apiKey) {
  try {
    const response = await fetch('https://api.openai.com/v1/models', {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      const data = await response.json();
      const models = data.data?.map(m => m.id) || [];
      return {
        success: true,
        message: `Connected! Found ${models.length} models.`,
        models: models.filter(m => m.includes('gpt'))
      };
    } else {
      return { success: false, message: 'Invalid API key or connection failed' };
    }
  } catch (error) {
    return { success: false, message: `Connection error: ${error.message}` };
  }
}

async function testAnthropic(apiKey) {
  try {
    // Anthropic doesn't have a models endpoint, so we'll do a minimal completion
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-sonnet-20240229',
        messages: [{role: 'user', content: 'Hi'}],
        max_tokens: 1
      })
    });

    if (response.ok || response.status === 400) { // 400 might mean quota but key is valid
      return {
        success: true,
        message: 'Connected to Anthropic!',
        models: [
          'claude-3-opus-20240229',
          'claude-3-sonnet-20240229',
          'claude-3-haiku-20240307',
          'claude-2.1',
          'claude-2.0',
          'claude-instant-1.2'
        ]
      };
    } else {
      return { success: false, message: 'Invalid API key or connection failed' };
    }
  } catch (error) {
    return { success: false, message: `Connection error: ${error.message}` };
  }
}

async function testGoogleAI(apiKey) {
  try {
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);

    if (response.ok) {
      const data = await response.json();
      const models = data.models?.map(m => m.name) || [];
      return {
        success: true,
        message: `Connected! Found ${models.length} models.`,
        models
      };
    } else {
      return { success: false, message: 'Invalid API key or connection failed' };
    }
  } catch (error) {
    return { success: false, message: `Connection error: ${error.message}` };
  }
}

async function testOllama(endpoint) {
  try {
    const response = await fetch(`${endpoint}/api/tags`);

    if (response.ok) {
      const data = await response.json();
      const models = data.models?.map(m => m.name) || [];
      return {
        success: true,
        message: `Connected! Found ${models.length} models.`,
        models
      };
    } else {
      return { success: false, message: 'Cannot connect to Ollama. Is it running?' };
    }
  } catch (error) {
    return { success: false, message: `Connection error: ${error.message}` };
  }
}

module.exports = router;