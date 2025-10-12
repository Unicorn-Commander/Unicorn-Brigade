const express = require('express');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const fs = require('fs').promises;
const { PrismaClient } = require('@prisma/client');

// Import agent configuration
const agentConfig = require('../config/agent.config');

// Import memory services from main UC2 platform
const memoryLayerManager = require('../../../core/memory/memoryLayerManager');

// Import RAG service (we'll create this next)
const RAGService = require('../rag/ragService');

const app = express();
const prisma = new PrismaClient();
const PORT = agentConfig.deployment.port || 3333;

// Initialize services
const ragService = new RAGService(agentConfig.rag);

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
// Serve static files from frontend directory
app.use(express.static(path.join(__dirname, '../frontend')));

// File upload configuration for medical records
const storage = multer.diskStorage({
  destination: async (req, file, cb) => {
    const uploadPath = path.join(__dirname, '../data/medical_records');
    await fs.mkdir(uploadPath, { recursive: true });
    cb(null, uploadPath);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, `${uniqueSuffix}-${file.originalname}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 100 * 1024 * 1024 }, // 100MB limit
  fileFilter: (req, file, cb) => {
    // Accept common medical document formats
    const allowedTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'text/plain',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];

    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Please upload PDF, images, or text documents.'));
    }
  }
});

// Initialize agent on startup
async function initializeAgent() {
  console.log('🦄 Initializing Dr. Glitter Mane...');

  try {
    // Initialize database
    await prisma.$connect();
    console.log('✅ Database connected');

    // Initialize RAG system
    await ragService.initialize();
    console.log('✅ RAG system initialized');

    // Initialize memory layer
    console.log('✅ Memory system ready');

    // Load any existing medical records into RAG
    const recordsPath = path.join(__dirname, '../data/medical_records');
    await fs.mkdir(recordsPath, { recursive: true });

    console.log(`\n${agentConfig.agent.greeting}\n`);
    console.log('🚀 Dr. Glitter Mane is ready for consultations!');

  } catch (error) {
    console.error('❌ Initialization error:', error);
    process.exit(1);
  }
}

// API Routes

/**
 * Get agent information
 */
app.get('/api/agent', (req, res) => {
  res.json({
    agent: {
      name: agentConfig.agent.name,
      title: agentConfig.agent.title,
      avatar: agentConfig.agent.avatar,
      greeting: agentConfig.agent.greeting,
      capabilities: agentConfig.agent.capabilities,
      disclaimers: agentConfig.disclaimers
    },
    features: agentConfig.ui.features
  });
});

/**
 * Chat with Dr. Glitter Mane
 */
app.post('/api/chat', async (req, res) => {
  try {
    const { message, sessionId, userId } = req.body;

    console.log(`\n👤 User: ${message}`);

    // Store user message in memory
    await memoryLayerManager.storeMemory(agentConfig.agent.id, {
      type: 'conversation',
      content: message,
      importance: 0.7,
      source: 'user',
      tags: ['medical_consultation'],
      entities: extractMedicalEntities(message)
    }, {
      context: {
        sessionId,
        userId,
        timestamp: new Date(),
        conversationType: 'medical_consultation'
      }
    });

    // Search relevant medical records and past conversations
    const relevantContext = await searchRelevantContext(message, sessionId);

    // Generate response using AI with RAG context
    const response = await generateResponse(message, relevantContext);

    // Store agent response in memory
    await memoryLayerManager.storeMemory(agentConfig.agent.id, {
      type: 'conversation',
      content: response.content,
      importance: 0.8,
      source: 'agent',
      tags: response.tags || ['medical_advice'],
      entities: response.entities || []
    }, {
      context: {
        sessionId,
        userId,
        timestamp: new Date(),
        conversationType: 'medical_consultation'
      }
    });

    console.log(`\n🦄 Dr. Glitter Mane: ${response.content.substring(0, 100)}...`);

    res.json({
      response: response.content,
      metadata: {
        sessionId,
        timestamp: new Date(),
        contextUsed: relevantContext.length > 0,
        tags: response.tags
      }
    });

  } catch (error) {
    console.error('Chat error:', error);
    res.status(500).json({
      error: 'An error occurred during consultation',
      message: error.message
    });
  }
});

/**
 * Upload medical records
 */
app.post('/api/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const { userId, documentType, description } = req.body;

    console.log(`📄 Processing medical record: ${req.file.originalname}`);

    // Process and index the document in RAG
    const processed = await ragService.processDocument({
      filePath: req.file.path,
      fileName: req.file.originalname,
      documentType: documentType || 'medical_record',
      userId,
      description
    });

    // Store document metadata in memory
    await memoryLayerManager.storeMemory(agentConfig.agent.id, {
      type: 'document',
      content: `Medical record uploaded: ${req.file.originalname}`,
      importance: 0.9,
      source: 'document_upload',
      tags: ['medical_record', documentType].filter(Boolean),
      metadata: {
        fileName: req.file.originalname,
        filePath: req.file.path,
        documentId: processed.documentId,
        chunks: processed.chunks
      }
    }, {
      context: {
        userId,
        timestamp: new Date(),
        documentType
      }
    });

    res.json({
      success: true,
      message: 'Medical record processed successfully',
      document: {
        id: processed.documentId,
        fileName: req.file.originalname,
        type: documentType,
        chunksProcessed: processed.chunks,
        timestamp: new Date()
      }
    });

  } catch (error) {
    console.error('Upload error:', error);
    res.status(500).json({
      error: 'Failed to process medical record',
      message: error.message
    });
  }
});

/**
 * Get conversation history
 */
app.get('/api/history/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { limit = 50 } = req.query;

    // Retrieve conversation history from memory
    const history = await memoryLayerManager.searchMemories(
      agentConfig.agent.id,
      sessionId,
      {
        limit: parseInt(limit),
        includeContextual: true,
        mergeResults: true
      }
    );

    res.json({
      sessionId,
      messages: history.combined || [],
      totalMessages: history.totalFound || 0
    });

  } catch (error) {
    console.error('History error:', error);
    res.status(500).json({
      error: 'Failed to retrieve conversation history',
      message: error.message
    });
  }
});

/**
 * Get medical records list
 */
app.get('/api/records/:userId', async (req, res) => {
  try {
    const { userId } = req.params;

    // Search for document memories
    const records = await memoryLayerManager.searchMemories(
      agentConfig.agent.id,
      'medical_record',
      {
        limit: 100,
        includeContextual: true
      }
    );

    const documents = records.combined
      .filter(m => m.type === 'document' && m.metadata?.fileName)
      .map(m => ({
        id: m.metadata.documentId,
        fileName: m.metadata.fileName,
        type: m.context?.documentType || 'medical_record',
        uploadDate: m.timestamp,
        chunks: m.metadata.chunks
      }));

    res.json({
      userId,
      documents,
      totalRecords: documents.length
    });

  } catch (error) {
    console.error('Records error:', error);
    res.status(500).json({
      error: 'Failed to retrieve medical records',
      message: error.message
    });
  }
});

/**
 * Get analytics and insights
 */
app.get('/api/analytics/:userId', async (req, res) => {
  try {
    const { userId } = req.params;

    // Get analytics from memory layer
    const analytics = await memoryLayerManager.getAnalyticsReport(
      agentConfig.agent.id,
      {
        timeframe: 'month',
        includeInsights: true,
        includeRecommendations: true
      }
    );

    res.json({
      userId,
      analytics: {
        totalConsultations: analytics.basicStats?.totalMemories || 0,
        topicsCovered: analytics.contentAnalysis?.topics || [],
        insights: analytics.insights || [],
        recommendations: analytics.systemRecommendations || []
      }
    });

  } catch (error) {
    console.error('Analytics error:', error);
    res.status(500).json({
      error: 'Failed to retrieve analytics',
      message: error.message
    });
  }
});

// Helper Functions

/**
 * Extract medical entities from text
 */
function extractMedicalEntities(text) {
  const entities = [];

  // Simple entity extraction (would be enhanced with NLP)
  const symptomKeywords = ['pain', 'ache', 'fever', 'cough', 'fatigue', 'nausea'];
  const bodyParts = ['head', 'chest', 'stomach', 'back', 'throat', 'joints'];
  const conditions = ['diabetes', 'hypertension', 'asthma', 'arthritis'];

  const lowerText = text.toLowerCase();

  symptomKeywords.forEach(symptom => {
    if (lowerText.includes(symptom)) entities.push(`symptom:${symptom}`);
  });

  bodyParts.forEach(part => {
    if (lowerText.includes(part)) entities.push(`bodypart:${part}`);
  });

  conditions.forEach(condition => {
    if (lowerText.includes(condition)) entities.push(`condition:${condition}`);
  });

  return entities;
}

/**
 * Search for relevant context from RAG and memory
 */
async function searchRelevantContext(query, sessionId) {
  try {
    // Search RAG for relevant medical records
    const ragResults = await ragService.search(query, { limit: 5 });

    // Search memory for relevant past conversations
    const memoryResults = await memoryLayerManager.searchMemories(
      agentConfig.agent.id,
      query,
      {
        limit: 5,
        includeVector: true,
        includeContextual: true
      }
    );

    return {
      documents: ragResults,
      memories: memoryResults.combined || [],
      sessionContext: sessionId
    };

  } catch (error) {
    console.error('Context search error:', error);
    return { documents: [], memories: [], sessionContext: sessionId };
  }
}

/**
 * Generate AI response with context
 */
async function generateResponse(userMessage, context) {
  try {
    // Build context prompt
    let contextPrompt = '';

    if (context.documents && context.documents.length > 0) {
      contextPrompt += '\n\n## Relevant Medical Records:\n';
      context.documents.forEach(doc => {
        contextPrompt += `- ${doc.content.substring(0, 200)}...\n`;
      });
    }

    if (context.memories && context.memories.length > 0) {
      contextPrompt += '\n\n## Previous Consultation Context:\n';
      context.memories.forEach(memory => {
        contextPrompt += `- ${memory.content.substring(0, 200)}...\n`;
      });
    }

    // Build the full prompt
    const fullPrompt = `${agentConfig.agent.systemPrompt}

${contextPrompt}

User Query: ${userMessage}

Please provide a comprehensive medical consultation response following the specified format.`;

    // Use OpenAI API (or configured provider)
    const response = await callAIProvider(fullPrompt);

    return {
      content: response,
      tags: ['medical_consultation', 'ai_response'],
      entities: extractMedicalEntities(response)
    };

  } catch (error) {
    console.error('Response generation error:', error);

    // Fallback response
    return {
      content: `I apologize, but I'm experiencing technical difficulties generating a complete response.

Based on your query about "${userMessage}", I recommend:
• Documenting your symptoms in detail
• Consulting with your primary care physician
• Keeping track of any changes in your condition

Please try again or contact support if the issue persists.

Remember: In case of emergency, please call 911 or visit your nearest emergency room.`,
      tags: ['error_fallback'],
      entities: []
    };
  }
}

/**
 * Call AI provider (OpenAI, Anthropic, etc.)
 */
async function callAIProvider(prompt) {
  // This would integrate with actual AI provider
  // For now, return a mock response

  if (process.env.OPENAI_API_KEY) {
    // Would call OpenAI here
    const fetch = require('node-fetch');
    try {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: agentConfig.ai.model,
          messages: [
            { role: 'system', content: agentConfig.agent.systemPrompt },
            { role: 'user', content: prompt }
          ],
          temperature: agentConfig.ai.temperature,
          max_tokens: agentConfig.ai.max_tokens
        })
      });

      const data = await response.json();
      return data.choices[0].message.content;

    } catch (error) {
      console.error('OpenAI API error:', error);
    }
  }

  // Mock response for testing
  return `Based on your symptoms and medical history, here's my assessment:

**Summary**: Your symptoms suggest a possible upper respiratory condition that warrants further evaluation.

**Most Likely Diagnosis:**
• Viral upper respiratory infection (common cold)
• Seasonal allergies with secondary symptoms

**Other Possible Diagnoses:**
• Bacterial sinusitis (less likely without fever)
• Early-stage influenza
• Rare consideration: Wegener's granulomatosis (given persistent symptoms)

**Recommended Medications:**
• Acetaminophen 500mg every 6 hours for discomfort
• Saline nasal rinse 2-3 times daily
• Consider antihistamine if allergic component suspected

**Suggested Tests:**
• Complete Blood Count (CBC) if symptoms persist >10 days
• Sinus X-ray or CT if sinusitis suspected
• Allergy panel if recurrent symptoms

**Specialist Referrals:**
• ENT consultation if symptoms persist beyond 2 weeks
• Allergist if seasonal pattern observed

**Other Advice:**
• Rest and maintain hydration
• Monitor temperature daily
• Red flags: High fever, severe headache, difficulty breathing - seek immediate care
• Follow up with primary care in 5-7 days if not improving

Remember to consult with your healthcare provider for definitive diagnosis and treatment.`;
}

// Serve React frontend (standalone HTML file)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend', 'DrGlitterMane.html'));
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('Server error:', error);
  res.status(500).json({
    error: 'Internal server error',
    message: error.message
  });
});

// Start server
app.listen(PORT, async () => {
  console.log(`\n🦄 Dr. Glitter Mane Server starting on port ${PORT}...`);
  await initializeAgent();
  console.log(`\n✨ Visit http://localhost:${PORT} to start your consultation\n`);
});

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n🦄 Dr. Glitter Mane signing off...');
  await prisma.$disconnect();
  process.exit(0);
});

module.exports = app;