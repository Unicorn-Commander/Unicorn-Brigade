// Unicorn Command & Control - Main Server
const express = require('express');
const cors = require('cors');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');
require('dotenv').config();

// Initialize Express
const app = express();
const server = http.createServer(app);

// Initialize Socket.io for real-time communication
const io = new Server(server, {
  cors: {
    origin: process.env.FRONTEND_URL || 'http://localhost:8112',
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    credentials: true
  }
});

// Middleware
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:8112',
  credentials: true
}));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Static files for agent personas and tools
app.use('/agents', express.static(path.join(__dirname, 'agents')));
app.use('/tools', express.static(path.join(__dirname, 'tools')));

// Core Services (Archived - moved to new architecture)
// const agentOrchestrator = require('./core/services/agentOrchestrator'); // Archived
// const markdownAgentLoader = require('./core/services/markdownAgentLoader');
// const agentTriggerService = require('./core/services/agentTriggerService'); // Depends on agentOrchestrator
// const agentToolsService = require('./core/services/agentToolsService');
// const domainKnowledgeService = require('./core/services/domainKnowledgeService');
// For new architecture, see: core/services/litellmProvider, mem0Provider, langfuseProvider

// Medical Services
const MedicalAgentOrchestrator = require('./backend/services/medicalAgentOrchestrator');
const MedicalWebSocketService = require('./backend/websocket/medicalWebSocket');

// Database
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Initialize Services
let medicalOrchestrator;
let medicalWebSocketService;

async function initializeServices() {
  console.log('🦄 Initializing Unicorn Brigade...');

  try {
    // NOTE: Legacy services commented out - moved to new architecture
    // See: core/services/litellmProvider, mem0Provider, langfuseProvider
    // and api/routes/chat-new.js for examples

    // Initialize medical orchestrator with prisma for database access
    medicalOrchestrator = new MedicalAgentOrchestrator(null, prisma);
    console.log('✅ Medical orchestrator initialized');

    // Store orchestrator and prisma in app locals for route access
    app.locals.medicalOrchestrator = medicalOrchestrator;
    app.locals.prisma = prisma;

    // Initialize medical WebSocket service
    medicalWebSocketService = new MedicalWebSocketService(server, medicalOrchestrator, { verifyToken: async () => ({ id: 'dev-user' }) });
    console.log('✅ Medical WebSocket service initialized');

    console.log('🚀 Core services initialized!');
    console.log('💡 For agent chat, use: POST /api/chat-new/message');
  } catch (error) {
    console.error('❌ Service initialization failed:', error);
    process.exit(1);
  }
}

// API Routes
// Legacy routes (depend on archived services) - use chat-new for new architecture
// app.use('/api/agents', require('./api/routes/agents'));
// app.use('/api/orchestration', require('./api/routes/orchestration'));
// app.use('/api/memory', require('./api/routes/memory'));
// app.use('/api/tools', require('./api/routes/tools'));
// app.use('/api/workflows', require('./api/routes/workflows'));
// app.use('/api/providers', require('./api/routes/providers'));
// app.use('/api/chat', require('./api/routes/chat'));
app.use('/api/auth', require('./api/routes/auth'));
app.use('/api/medical', require('./backend/routes/medical'));
app.use('/api/medical-test', require('./api/routes/medical-test'));

// New architecture routes
// Note: chat-new requires Mem0 which needs Python integration or HTTP API
// app.use('/api/chat-new', require('./api/routes/chat-new'));

// Agent Builder System - Unicorn Brigade
app.use('/api/agents-new', require('./api/routes/agents-new'));
app.use('/api/agent-builder', require('./api/routes/agent-builder'));

// Root landing page
app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Unicorn Brigade</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 50px;
          text-align: center;
        }
        .container {
          max-width: 800px;
          margin: 0 auto;
          background: rgba(255, 255, 255, 0.1);
          backdrop-filter: blur(10px);
          border-radius: 20px;
          padding: 40px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        h1 { font-size: 3em; margin: 0; }
        .unicorn { font-size: 4em; margin: 20px 0; }
        .status {
          background: rgba(76, 175, 80, 0.3);
          padding: 10px 20px;
          border-radius: 10px;
          display: inline-block;
          margin: 20px 0;
        }
        .links {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
          margin-top: 30px;
        }
        .link {
          background: rgba(255, 255, 255, 0.2);
          padding: 15px;
          border-radius: 10px;
          text-decoration: none;
          color: white;
          transition: all 0.3s;
        }
        .link:hover {
          background: rgba(255, 255, 255, 0.3);
          transform: translateY(-2px);
        }
        .info { margin-top: 30px; font-size: 0.9em; opacity: 0.8; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="unicorn">🦄⚔️</div>
        <h1>Unicorn Brigade</h1>
        <p>AI Agent Infrastructure Platform</p>
        <div class="status">✅ OPERATIONAL</div>

        <div class="links">
          <a href="/health" class="link">📊 Health Status</a>
          <a href="/api/medical" class="link">🏥 Medical Services</a>
          <a href="/command" class="link">🎮 Command Center</a>
          <a href="/analytics" class="link">📈 Analytics</a>
          <a href="/builder" class="link">🤖 Agent Builder</a>
        </div>

        <div class="info">
          <p><strong>Part of Magic Unicorn Unconventional Technology & Stuff Inc.</strong></p>
          <p>37 Enterprise Tools • Mem0 Memory • LiteLLM Multi-Provider • Langfuse Observability</p>
          <p>Works with UC-1 Hardware Appliance & Ops-Center Management Console</p>
        </div>
      </div>
    </body>
    </html>
  `);
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'operational',
    service: 'Unicorn Brigade',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// WebSocket Events
io.on('connection', (socket) => {
  console.log(`🔌 Client connected: ${socket.id}`);

  // Join agent-specific rooms
  socket.on('join-agent', (agentId) => {
    socket.join(`agent-${agentId}`);
    console.log(`Client ${socket.id} joined agent room: ${agentId}`);
  });

  // Handle orchestration requests
  socket.on('orchestrate', async (data) => {
    try {
      // TODO: Implement with new LangGraph orchestration
      socket.emit('orchestration-error', { error: 'Orchestration moved to new architecture - use chat-new API' });
    } catch (error) {
      socket.emit('orchestration-error', { error: error.message });
    }
  });

  // Handle direct agent communication
  socket.on('agent-message', async (data) => {
    try {
      // TODO: Implement with new architecture (see api/routes/chat-new.js)
      socket.emit('agent-error', { error: 'Agent messaging moved to new architecture - use chat-new API' });
    } catch (error) {
      socket.emit('agent-error', { error: error.message });
    }
  });

  // Handle tool execution
  socket.on('execute-tool', async (data) => {
    try {
      // TODO: Implement with new architecture
      socket.emit('tool-error', { error: 'Tool execution moved to new architecture' });
    } catch (error) {
      socket.emit('tool-error', { error: error.message });
    }
  });

  socket.on('disconnect', () => {
    console.log(`🔌 Client disconnected: ${socket.id}`);
  });
});

// Error handling
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal server error',
    stack: process.env.NODE_ENV === 'development' ? err.stack : undefined
  });
});

// Start server
const PORT = process.env.PORT || 8112;

async function startServer() {
  await initializeServices();

  server.listen(PORT, () => {
    console.log('════════════════════════════════════════════════');
    console.log('🦄 UNICORN BRIGADE - OPERATIONAL ⚔️');
    console.log('════════════════════════════════════════════════');
    console.log(`📡 Server: http://localhost:${PORT}`);
    console.log(`🎮 Command Center: http://localhost:${PORT}/command`);
    console.log(`📊 Analytics: http://localhost:${PORT}/analytics`);
    console.log(`🤖 Agent Builder: http://localhost:${PORT}/builder`);
    console.log(`🆕 New Chat API: http://localhost:${PORT}/api/chat-new/health`);
    console.log('════════════════════════════════════════════════');
  });
}

// Handle graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 Received SIGTERM, shutting down gracefully...');
  server.close(() => {
    console.log('👋 Server closed');
    process.exit(0);
  });
});

// Start the server
startServer().catch(console.error);

module.exports = { app, io };