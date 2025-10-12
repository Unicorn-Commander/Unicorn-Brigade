const express = require('express');
const router = express.Router();
const multer = require('multer');
const fs = require('fs').promises;
const path = require('path');
const { v4: uuidv4 } = require('uuid');

// Configure multer for file uploads
const upload = multer({
  storage: multer.diskStorage({
    destination: async (req, file, cb) => {
      const userId = req.user?.id || 'anonymous';
      const uploadPath = path.join(process.cwd(), 'uploads', 'medical', userId);

      try {
        await fs.mkdir(uploadPath, { recursive: true });
        cb(null, uploadPath);
      } catch (error) {
        cb(error);
      }
    },
    filename: (req, file, cb) => {
      const uniqueName = `${Date.now()}-${uuidv4()}${path.extname(file.originalname)}`;
      cb(null, uniqueName);
    }
  }),
  limits: {
    fileSize: 50 * 1024 * 1024 // 50MB max file size
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = [
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/gif',
      'text/plain',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];

    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type. Supported types: PDF, Images, Text, Word documents'));
    }
  }
});

/**
 * POST /api/medical/consultation
 * Start a new medical consultation
 */
router.post('/consultation', async (req, res) => {
  try {
    const { message, context } = req.body;
    const userId = req.user?.id || req.body.userId || 'anonymous';

    const orchestrator = req.app.locals.medicalOrchestrator;

    if (!orchestrator) {
      return res.status(503).json({
        error: 'Medical service temporarily unavailable'
      });
    }

    const result = await orchestrator.startConsultation(
      userId,
      message,
      context
    );

    res.json({
      success: true,
      consultationId: result.consultationId,
      response: result.response
    });
  } catch (error) {
    console.error('Consultation error:', error);
    res.status(500).json({
      error: 'Failed to start consultation',
      message: error.message
    });
  }
});

/**
 * POST /api/medical/message
 * Send a message in an existing consultation
 */
router.post('/message', async (req, res) => {
  try {
    const { consultationId, message, context } = req.body;

    const orchestrator = req.app.locals.medicalOrchestrator;

    if (!orchestrator) {
      return res.status(503).json({
        error: 'Medical service temporarily unavailable'
      });
    }

    const response = await orchestrator.processMessage(
      consultationId,
      message,
      context
    );

    res.json({
      success: true,
      response
    });
  } catch (error) {
    console.error('Message error:', error);
    res.status(500).json({
      error: 'Failed to process message',
      message: error.message
    });
  }
});

/**
 * POST /api/medical/document/upload
 * Upload and analyze medical document
 */
router.post('/document/upload', upload.single('document'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        error: 'No document provided'
      });
    }

    const userId = req.user?.id || req.body.userId || 'anonymous';
    const orchestrator = req.app.locals.medicalOrchestrator;

    if (!orchestrator) {
      return res.status(503).json({
        error: 'Medical service temporarily unavailable'
      });
    }

    // Read file content (in production, use Apache Tika or similar)
    const fileContent = await fs.readFile(req.file.path, 'utf8').catch(() => {
      // If text reading fails, return file info
      return `File: ${req.file.originalname}\nType: ${req.file.mimetype}\nSize: ${req.file.size} bytes`;
    });

    // Process document with orchestrator
    const result = await orchestrator.processDocument(
      userId,
      fileContent,
      {
        filename: req.file.originalname,
        type: req.file.mimetype,
        size: req.file.size,
        path: req.file.path
      }
    );

    // Store document reference in database if available
    if (req.app.locals.prisma) {
      try {
        await req.app.locals.prisma.document.create({
          data: {
            id: uuidv4(),
            userId,
            filename: req.file.originalname,
            path: req.file.path,
            type: req.file.mimetype,
            size: req.file.size,
            analysis: result.analysis,
            uploadedAt: new Date()
          }
        });
      } catch (dbError) {
        console.error('Database error:', dbError);
      }
    }

    res.json({
      success: true,
      document: {
        id: req.file.filename,
        name: req.file.originalname,
        size: req.file.size,
        type: req.file.mimetype
      },
      analysis: result.analysis
    });
  } catch (error) {
    console.error('Document upload error:', error);
    res.status(500).json({
      error: 'Failed to process document',
      message: error.message
    });
  }
});

/**
 * GET /api/medical/agents
 * Get available medical agents
 */
router.get('/agents', (req, res) => {
  const orchestrator = req.app.locals.medicalOrchestrator;

  if (!orchestrator) {
    return res.status(503).json({
      error: 'Medical service temporarily unavailable'
    });
  }

  const agents = Object.values(orchestrator.agentRegistry).map(agent => ({
    id: agent.id,
    name: agent.name,
    specialty: agent.specialty,
    avatar: agent.avatar,
    role: agent.role,
    capabilities: agent.capabilities
  }));

  res.json({
    success: true,
    agents
  });
});

/**
 * GET /api/medical/consultation/:id
 * Get consultation details
 */
router.get('/consultation/:id', async (req, res) => {
  try {
    const consultationId = req.params.id;
    const userId = req.user?.id || req.query.userId;

    if (!req.app.locals.prisma) {
      return res.status(503).json({
        error: 'Database service unavailable'
      });
    }

    const consultation = await req.app.locals.prisma.consultation.findFirst({
      where: {
        id: consultationId,
        userId
      }
    });

    if (!consultation) {
      return res.status(404).json({
        error: 'Consultation not found'
      });
    }

    res.json({
      success: true,
      consultation
    });
  } catch (error) {
    console.error('Get consultation error:', error);
    res.status(500).json({
      error: 'Failed to retrieve consultation',
      message: error.message
    });
  }
});

/**
 * GET /api/medical/documents
 * Get user's medical documents
 */
router.get('/documents', async (req, res) => {
  try {
    const userId = req.user?.id || req.query.userId || 'anonymous';

    if (!req.app.locals.prisma) {
      // Return empty if no database
      return res.json({
        success: true,
        documents: []
      });
    }

    const documents = await req.app.locals.prisma.document.findMany({
      where: { userId },
      orderBy: { uploadedAt: 'desc' }
    });

    res.json({
      success: true,
      documents
    });
  } catch (error) {
    console.error('Get documents error:', error);
    res.status(500).json({
      error: 'Failed to retrieve documents',
      message: error.message
    });
  }
});

/**
 * POST /api/medical/emergency
 * Handle emergency medical situations
 */
router.post('/emergency', async (req, res) => {
  try {
    const { message, location, contactInfo } = req.body;
    const userId = req.user?.id || req.body.userId || 'emergency-user';

    const orchestrator = req.app.locals.medicalOrchestrator;

    if (!orchestrator) {
      return res.status(503).json({
        error: 'Medical service temporarily unavailable',
        fallback: 'Please call 911 or your local emergency services immediately'
      });
    }

    // Check for emergency
    const emergencyCheck = await orchestrator.checkEmergency(message);

    if (emergencyCheck.isEmergency) {
      // Log emergency
      console.error('EMERGENCY DETECTED:', {
        userId,
        message,
        location,
        contactInfo,
        timestamp: new Date()
      });

      // In production, this could trigger:
      // - SMS/Call to emergency contacts
      // - Alert to medical staff
      // - Location-based emergency services

      res.json({
        success: true,
        emergency: true,
        severity: emergencyCheck.severity,
        recommendation: emergencyCheck.recommendation,
        action: 'SEEK IMMEDIATE MEDICAL ATTENTION',
        emergencyNumber: '911'
      });
    } else {
      res.json({
        success: true,
        emergency: false,
        message: 'No emergency detected. Please use regular consultation for non-urgent matters.'
      });
    }
  } catch (error) {
    console.error('Emergency handler error:', error);
    res.status(500).json({
      error: 'Emergency system error',
      fallback: 'Please call 911 or your local emergency services immediately'
    });
  }
});

/**
 * GET /api/medical/health-metrics
 * Get user's health metrics and trends
 */
router.get('/health-metrics', async (req, res) => {
  try {
    const userId = req.user?.id || req.query.userId || 'anonymous';

    // In production, this would pull from database
    // For now, return structure for frontend
    res.json({
      success: true,
      metrics: {
        vitals: {
          lastUpdated: new Date(),
          bloodPressure: null,
          heartRate: null,
          temperature: null,
          oxygen: null,
          weight: null,
          height: null,
          bmi: null
        },
        labResults: [],
        medications: [],
        conditions: [],
        riskFactors: []
      }
    });
  } catch (error) {
    console.error('Health metrics error:', error);
    res.status(500).json({
      error: 'Failed to retrieve health metrics',
      message: error.message
    });
  }
});

/**
 * POST /api/medical/health-metrics
 * Update health metrics
 */
router.post('/health-metrics', async (req, res) => {
  try {
    const userId = req.user?.id || req.body.userId || 'anonymous';
    const { metrics } = req.body;

    // Store in database if available
    if (req.app.locals.prisma) {
      await req.app.locals.prisma.healthMetrics.upsert({
        where: { userId },
        update: { ...metrics, updatedAt: new Date() },
        create: {
          id: uuidv4(),
          userId,
          ...metrics,
          createdAt: new Date()
        }
      });
    }

    res.json({
      success: true,
      message: 'Health metrics updated successfully'
    });
  } catch (error) {
    console.error('Update metrics error:', error);
    res.status(500).json({
      error: 'Failed to update health metrics',
      message: error.message
    });
  }
});

module.exports = router;