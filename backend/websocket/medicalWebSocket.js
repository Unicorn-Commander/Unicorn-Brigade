const socketIO = require('socket.io');

/**
 * Medical WebSocket Service
 * Real-time communication for medical agent interactions
 */
class MedicalWebSocketService {
  constructor(server, medicalOrchestrator, authService) {
    this.io = socketIO(server, {
      cors: {
        origin: process.env.FRONTEND_URL || 'http://localhost:8113',
        methods: ['GET', 'POST'],
        credentials: true
      },
      path: '/medical-ws/'
    });

    this.orchestrator = medicalOrchestrator;
    this.authService = authService;
    this.userSessions = new Map();

    this.initialize();
  }

  initialize() {
    // Authentication middleware
    this.io.use(async (socket, next) => {
      try {
        const token = socket.handshake.auth.token;

        if (process.env.NODE_ENV === 'development' && !token) {
          // Allow unauthenticated in dev mode
          socket.userId = 'dev-user';
          return next();
        }

        if (!token) {
          return next(new Error('Authentication required'));
        }

        // Verify token with your auth service
        const user = await this.authService.verifyToken(token);
        socket.userId = user.id;
        socket.userEmail = user.email;
        next();
      } catch (err) {
        next(new Error('Authentication failed'));
      }
    });

    // Connection handling
    this.io.on('connection', (socket) => {
      console.log(`Medical WebSocket connected: ${socket.id} (User: ${socket.userId})`);

      // Store user session
      this.userSessions.set(socket.userId, socket.id);

      // Join user's private room
      socket.join(`user:${socket.userId}`);

      // Handle consultation start
      socket.on('consultation:start', async (data) => {
        try {
          const result = await this.orchestrator.startConsultation(
            socket.userId,
            data.message,
            data.context
          );

          socket.emit('consultation:started', {
            consultationId: result.consultationId,
            response: result.response
          });

          // Join consultation room for updates
          socket.join(`consultation:${result.consultationId}`);
        } catch (error) {
          socket.emit('error', {
            message: 'Failed to start consultation',
            error: error.message
          });
        }
      });

      // Handle messages
      socket.on('message:send', async (data) => {
        try {
          const response = await this.orchestrator.processMessage(
            data.consultationId,
            data.message,
            data.context
          );

          socket.emit('message:response', {
            consultationId: data.consultationId,
            response
          });
        } catch (error) {
          socket.emit('error', {
            message: 'Failed to process message',
            error: error.message
          });
        }
      });

      // Handle document upload
      socket.on('document:upload', async (data) => {
        try {
          socket.emit('document:processing', {
            status: 'started',
            filename: data.filename
          });

          const result = await this.orchestrator.processDocument(
            socket.userId,
            data.content,
            {
              filename: data.filename,
              type: data.type,
              size: data.size
            }
          );

          socket.emit('document:analyzed', {
            consultationId: result.consultationId,
            analysis: result.analysis,
            filename: data.filename
          });
        } catch (error) {
          socket.emit('error', {
            message: 'Failed to process document',
            error: error.message
          });
        }
      });

      // Handle consultation end
      socket.on('consultation:end', async (data) => {
        try {
          await this.orchestrator.endConsultation(data.consultationId);

          socket.leave(`consultation:${data.consultationId}`);
          socket.emit('consultation:ended', {
            consultationId: data.consultationId
          });
        } catch (error) {
          socket.emit('error', {
            message: 'Failed to end consultation',
            error: error.message
          });
        }
      });

      // Handle disconnect
      socket.on('disconnect', () => {
        console.log(`Medical WebSocket disconnected: ${socket.id}`);
        this.userSessions.delete(socket.userId);
      });
    });

    // Listen to orchestrator events and forward to clients
    this.setupOrchestratorListeners();
  }

  /**
   * Setup listeners for orchestrator events
   */
  setupOrchestratorListeners() {
    // Agent thinking event
    this.orchestrator.on('agent:thinking', (data) => {
      this.emitToConsultation(data.consultationId, 'agent:thinking', {
        agentId: data.agentId,
        agentName: data.agentName,
        timestamp: new Date()
      });
    });

    // Agent response event
    this.orchestrator.on('agent:responded', (data) => {
      this.emitToConsultation(data.consultationId, 'agent:responded', {
        agentId: data.agentId,
        agentName: data.agentName,
        hasFindings: data.hasFindings,
        timestamp: new Date()
      });
    });

    // Findings discovered
    this.orchestrator.on('findings:discovered', (data) => {
      this.emitToConsultation(data.consultationId, 'findings:discovered', {
        findings: data.findings,
        timestamp: new Date()
      });
    });

    // Emergency detected
    this.orchestrator.on('emergency:detected', (data) => {
      this.emitToConsultation(data.consultationId, 'emergency:detected', {
        severity: data.severity,
        message: data.message,
        timestamp: new Date()
      });
    });

    // Document processing
    this.orchestrator.on('document:processing', (data) => {
      this.emitToUser(data.userId, 'document:processing', {
        status: 'analyzing',
        documentName: data.documentName,
        timestamp: new Date()
      });
    });

    // Document analyzed
    this.orchestrator.on('document:analyzed', (data) => {
      this.emitToConsultation(data.consultationId, 'document:analyzed', {
        findings: data.findings,
        recommendations: data.recommendations,
        timestamp: new Date()
      });
    });

    // Agent routing
    this.orchestrator.on('agents:routing', (data) => {
      this.emitToConsultation(data.consultationId, 'agents:routing', {
        specialists: data.specialists,
        reason: data.reason,
        timestamp: new Date()
      });
    });
  }

  /**
   * Emit to all sockets in a consultation room
   */
  emitToConsultation(consultationId, event, data) {
    this.io.to(`consultation:${consultationId}`).emit(event, data);
  }

  /**
   * Emit to a specific user
   */
  emitToUser(userId, event, data) {
    this.io.to(`user:${userId}`).emit(event, data);
  }

  /**
   * Broadcast system message
   */
  broadcastSystemMessage(message) {
    this.io.emit('system:message', {
      message,
      timestamp: new Date()
    });
  }

  /**
   * Get active consultations count
   */
  getActiveConsultationsCount() {
    return this.orchestrator.activeConsultations.size;
  }

  /**
   * Get connected users count
   */
  getConnectedUsersCount() {
    return this.userSessions.size;
  }
}

module.exports = MedicalWebSocketService;