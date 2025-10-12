const express = require('express');
const router = express.Router();
const { PrismaClient } = require('@prisma/client');
const crypto = require('crypto');

const prisma = new PrismaClient();

// Encryption settings (same as providers)
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'your-32-character-encryption-key-here!';
const ALGORITHM = 'aes-256-gcm';

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

// Get active provider
async function getActiveProvider() {
  const provider = await prisma.aIProvider.findFirst({
    where: {
      isActive: true
    },
    orderBy: {
      isDefault: 'desc'
    }
  });

  if (!provider) {
    throw new Error('No active AI provider found');
  }

  const apiKey = decryptApiKey(provider.apiKey);
  if (!apiKey) {
    throw new Error('Failed to decrypt provider API key');
  }

  const config = JSON.parse(provider.config || '{}');

  return {
    ...provider,
    apiKey,
    config
  };
}

// Chat completion endpoint
router.post('/completions', async (req, res) => {
  try {
    const { messages, model, agentId, temperature = 0.7, maxTokens = 1000 } = req.body;

    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array is required' });
    }

    // Get active provider
    const provider = await getActiveProvider();

    // Determine model to use
    const selectedModel = model || provider.config.settings?.defaultModel || provider.config.models?.[0];

    if (!selectedModel) {
      return res.status(400).json({ error: 'No model available' });
    }

    console.log(`Using ${provider.type} provider with model: ${selectedModel}`);

    let response;

    switch (provider.type) {
      case 'openrouter':
        response = await callOpenRouter(provider, messages, selectedModel, temperature, maxTokens);
        break;
      case 'openai':
        response = await callOpenAI(provider, messages, selectedModel, temperature, maxTokens);
        break;
      case 'anthropic':
        response = await callAnthropic(provider, messages, selectedModel, temperature, maxTokens);
        break;
      default:
        return res.status(400).json({ error: `Unsupported provider type: ${provider.type}` });
    }

    // Save to agent message history if agentId provided
    if (agentId && response.content) {
      try {
        await prisma.agentMessage.create({
          data: {
            agentId: String(agentId),
            role: 'assistant',
            content: response.content,
            metadata: JSON.stringify({
              model: selectedModel,
              provider: provider.type,
              tokens: response.usage
            })
          }
        });

        // Also save user message
        const userMessage = messages[messages.length - 1];
        if (userMessage && userMessage.role === 'user') {
          await prisma.agentMessage.create({
            data: {
              agentId: String(agentId),
              role: 'user',
              content: userMessage.content,
              metadata: JSON.stringify({
                model: selectedModel,
                provider: provider.type
              })
            }
          });
        }
      } catch (error) {
        console.log(`Note: Could not save conversation for agentId ${agentId} - agent may not exist in database`);
      }
    }

    // Update provider usage stats
    await updateProviderStats(provider.id, response.usage);

    res.json({
      content: response.content,
      model: selectedModel,
      provider: provider.type,
      usage: response.usage
    });

  } catch (error) {
    console.error('Chat completion error:', error);
    res.status(500).json({
      error: 'Failed to generate response',
      details: error.message
    });
  }
});

// OpenRouter API call
async function callOpenRouter(provider, messages, model, temperature, maxTokens) {
  const response = await fetch(`${provider.endpoint}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${provider.apiKey}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'http://localhost:8113',
      'X-Title': 'Unicorn Command & Control'
    },
    body: JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
      stream: false
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenRouter API error: ${error}`);
  }

  const data = await response.json();

  return {
    content: data.choices[0].message.content,
    usage: data.usage
  };
}

// OpenAI API call
async function callOpenAI(provider, messages, model, temperature, maxTokens) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${provider.apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      messages,
      temperature,
      max_tokens: maxTokens
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenAI API error: ${error}`);
  }

  const data = await response.json();

  return {
    content: data.choices[0].message.content,
    usage: data.usage
  };
}

// Anthropic API call
async function callAnthropic(provider, messages, model, temperature, maxTokens) {
  // Convert OpenAI format to Anthropic format
  const anthropicMessages = messages.filter(m => m.role !== 'system').map(m => ({
    role: m.role === 'assistant' ? 'assistant' : 'user',
    content: m.content
  }));

  const systemMessage = messages.find(m => m.role === 'system')?.content || '';

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': provider.apiKey,
      'Content-Type': 'application/json',
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model,
      messages: anthropicMessages,
      system: systemMessage,
      max_tokens: maxTokens,
      temperature
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Anthropic API error: ${error}`);
  }

  const data = await response.json();

  return {
    content: data.content[0].text,
    usage: data.usage
  };
}

// Update provider usage statistics
async function updateProviderStats(providerId, usage) {
  try {
    const provider = await prisma.aIProvider.findUnique({
      where: { id: providerId }
    });

    if (!provider) return;

    const currentStats = JSON.parse(provider.usageStats || '{}');
    const updatedStats = {
      totalRequests: (currentStats.totalRequests || 0) + 1,
      totalTokens: (currentStats.totalTokens || 0) + (usage?.total_tokens || 0),
      totalCost: (currentStats.totalCost || 0) + (usage?.estimated_cost || 0)
    };

    await prisma.aIProvider.update({
      where: { id: providerId },
      data: {
        usageStats: JSON.stringify(updatedStats),
        lastUsedAt: new Date()
      }
    });
  } catch (error) {
    console.error('Failed to update provider stats:', error);
  }
}

// Get available models from active provider
router.get('/models', async (req, res) => {
  try {
    const provider = await getActiveProvider();

    res.json({
      models: provider.config.models || [],
      defaultModel: provider.config.settings?.defaultModel,
      provider: provider.type
    });
  } catch (error) {
    console.error('Error fetching models:', error);
    res.status(500).json({ error: 'Failed to fetch models' });
  }
});

module.exports = router;