const EventEmitter = require('events');
const { v4: uuidv4 } = require('uuid');
const OpenRouterProvider = require('./openRouterProvider');

/**
 * Medical Agent Orchestrator Service
 * Production-ready service for managing medical AI agents
 * Designed for multi-tenant SaaS deployment
 */
class MedicalAgentOrchestrator extends EventEmitter {
  constructor(inferenceProvider, prisma) {
    super();
    // Store provider and prisma for dynamic provider loading
    this.inferenceProvider = inferenceProvider;
    this.prisma = prisma;
    this.activeConsultations = new Map();
    this.agentRegistry = this.initializeAgents();
  }

  /**
   * Get the active inference provider from database or use default
   */
  async getActiveProvider() {
    if (this.inferenceProvider) {
      return this.inferenceProvider;
    }

    // Try to load from database if we have prisma
    if (this.prisma) {
      try {
        const activeProvider = await this.prisma.aIProvider.findFirst({
          where: { isActive: true }
        });

        if (activeProvider && activeProvider.apiKey) {
          // Decrypt and use the active provider
          const decryptedKey = this.decryptApiKey(activeProvider.apiKey);
          console.log('Active provider found:', activeProvider.type, 'Key decrypted:', !!decryptedKey);

          if (decryptedKey && activeProvider.type === 'openrouter') {
            const provider = new OpenRouterProvider(decryptedKey);
            // Cache it for future use
            this.inferenceProvider = provider;
            return provider;
          }
          // Add other provider types as needed (openai, anthropic, etc.)
        }
      } catch (error) {
        console.error('Error loading provider from database:', error);
      }
    }

    // Default to OpenRouter with env variable if available
    if (process.env.OPENROUTER_API_KEY) {
      console.log('Using OpenRouter API key from environment');
      const provider = new OpenRouterProvider(process.env.OPENROUTER_API_KEY);
      this.inferenceProvider = provider;
      return provider;
    }

    throw new Error('No inference provider configured. Please add an API key in Settings.');
  }

  /**
   * Decrypt API key (matching the encryption in providers route)
   */
  decryptApiKey(encryptedString) {
    const crypto = require('crypto');
    const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'your-32-character-encryption-key-here!';
    const ALGORITHM = 'aes-256-gcm';

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

  /**
   * Initialize medical specialist agents
   * These are configurable and can be loaded from database
   */
  initializeAgents() {
    return {
      dr_glitter_mane: {
        id: 'dr_glitter_mane',
        name: 'Dr. Glitter Mane',
        role: 'primary_care_orchestrator',
        specialty: 'Primary Care & Orchestration',
        avatar: '🦄💉',
        systemPrompt: `You are Dr. Glitter Mane, an AI clinical maestro and primary care orchestrator.
Your role is to:
1. Provide initial assessment of patient concerns
2. Analyze uploaded medical documents
3. Identify which specialists should be consulted
4. Synthesize recommendations from multiple specialists
5. Create comprehensive care plans

Always be empathetic, thorough, and evidence-based.
When you identify concerning symptoms, immediately flag them for specialist review.
Format your responses with clear sections and actionable recommendations.`,
        capabilities: ['diagnosis', 'triage', 'orchestration', 'synthesis'],
        model: process.env.MEDICAL_PRIMARY_MODEL || 'medical_primary'
      },

      cardio: {
        id: 'cardio',
        name: 'Dr. Cardio Thunder',
        role: 'specialist',
        specialty: 'Cardiology',
        avatar: '❤️⚡',
        systemPrompt: `You are Dr. Cardio Thunder, a specialized cardiology AI.
Focus on:
- Cardiovascular risk assessment
- Blood pressure management
- Cholesterol and lipid analysis
- Heart rhythm disorders
- Cardiac imaging interpretation
Provide specific, actionable cardiac care recommendations.`,
        capabilities: ['cardiac_diagnosis', 'ecg_interpretation', 'risk_assessment'],
        triggerKeywords: ['chest pain', 'heart', 'blood pressure', 'cholesterol', 'palpitations'],
        model: process.env.MEDICAL_SPECIALIST_MODEL || 'medical_specialist'
      },

      neuro: {
        id: 'neuro',
        name: 'Dr. Neuro Sparkle',
        role: 'specialist',
        specialty: 'Neurology',
        avatar: '🧠✨',
        systemPrompt: `You are Dr. Neuro Sparkle, a specialized neurology AI.
Focus on:
- Headache and migraine assessment
- Neurological symptoms evaluation
- Cognitive concerns
- Movement disorders
- Seizure disorders
Provide detailed neurological assessments and treatment plans.`,
        capabilities: ['neurological_assessment', 'cognitive_evaluation'],
        triggerKeywords: ['headache', 'dizzy', 'seizure', 'numbness', 'memory', 'confusion'],
        model: process.env.MEDICAL_SPECIALIST_MODEL || 'medical_specialist'
      },

      endo: {
        id: 'endo',
        name: 'Dr. Endo Balance',
        role: 'specialist',
        specialty: 'Endocrinology',
        avatar: '🧬⚖️',
        systemPrompt: `You are Dr. Endo Balance, a specialized endocrinology AI.
Focus on:
- Diabetes management
- Thyroid disorders
- Metabolic conditions
- Hormone imbalances
- Weight management
Provide metabolic assessments and endocrine care plans.`,
        capabilities: ['metabolic_assessment', 'diabetes_management'],
        triggerKeywords: ['diabetes', 'glucose', 'thyroid', 'weight', 'hormone', 'A1c'],
        model: process.env.MEDICAL_SPECIALIST_MODEL || 'medical_specialist'
      },

      emergency: {
        id: 'emergency',
        name: 'Dr. Emergency Flash',
        role: 'specialist',
        specialty: 'Emergency Medicine',
        avatar: '🚨⚡',
        systemPrompt: `You are Dr. Emergency Flash, a specialized emergency medicine AI.
CRITICAL: Identify emergency symptoms immediately.
Red flags requiring immediate care:
- Chest pain with shortness of breath
- Sudden severe headache
- Signs of stroke (FAST)
- Severe allergic reactions
- Uncontrolled bleeding
Always err on the side of caution for emergency symptoms.`,
        capabilities: ['emergency_triage', 'critical_assessment'],
        triggerKeywords: ['emergency', 'urgent', 'severe', 'sudden', 'acute', 'can\'t breathe'],
        priority: 'high',
        model: process.env.MEDICAL_EMERGENCY_MODEL || 'medical_emergency'
      }
    };
  }

  /**
   * Start a new consultation
   */
  async startConsultation(userId, message, context = {}) {
    const consultationId = uuidv4();

    const consultation = {
      id: consultationId,
      userId,
      startTime: new Date(),
      messages: [],
      findings: [],
      recommendations: [],
      activeAgents: new Set(['dr_glitter_mane']),
      status: 'active'
    };

    this.activeConsultations.set(consultationId, consultation);

    // Emit start event for WebSocket
    this.emit('consultation:started', {
      consultationId,
      userId,
      timestamp: consultation.startTime
    });

    // Process initial message
    const response = await this.processMessage(consultationId, message, context);

    return {
      consultationId,
      response
    };
  }

  /**
   * Process a message within a consultation
   */
  async processMessage(consultationId, message, context = {}) {
    const consultation = this.activeConsultations.get(consultationId);
    if (!consultation) {
      throw new Error('Consultation not found');
    }

    // Store message
    consultation.messages.push({
      role: 'user',
      content: message,
      timestamp: new Date()
    });

    // Check for emergency keywords first
    const emergencyCheck = await this.checkEmergency(message);
    if (emergencyCheck.isEmergency) {
      return await this.handleEmergency(consultationId, message, emergencyCheck);
    }

    // Determine which specialists to involve
    const specialists = this.identifyRequiredSpecialists(message, context);

    // Add specialists to active agents
    specialists.forEach(s => consultation.activeAgents.add(s));

    // Emit routing event
    this.emit('agents:routing', {
      consultationId,
      specialists,
      reason: 'Keyword and context analysis'
    });

    // Get responses from all relevant agents
    const agentResponses = await this.getAgentResponses(
      consultationId,
      message,
      context,
      Array.from(consultation.activeAgents)
    );

    // Synthesize responses
    const synthesis = await this.synthesizeResponses(agentResponses, context);

    // Store in consultation
    consultation.messages.push({
      role: 'assistant',
      content: synthesis.content,
      agents: synthesis.contributingAgents,
      timestamp: new Date()
    });

    // Update findings if any
    if (synthesis.findings) {
      consultation.findings.push(...synthesis.findings);

      // Emit findings for UI update
      this.emit('findings:discovered', {
        consultationId,
        findings: synthesis.findings
      });
    }

    // Save to database if user is authenticated
    if (consultation.userId && this.prisma) {
      await this.saveConsultation(consultation);
    }

    return synthesis;
  }

  /**
   * Check for emergency symptoms
   */
  async checkEmergency(message) {
    const emergencyKeywords = [
      'chest pain', 'can\'t breathe', 'severe pain', 'unconscious',
      'stroke', 'heart attack', 'bleeding heavily', 'seizure'
    ];

    const lowerMessage = message.toLowerCase();
    const hasEmergencyKeyword = emergencyKeywords.some(kw => lowerMessage.includes(kw));

    if (!hasEmergencyKeyword) {
      return { isEmergency: false };
    }

    // Use emergency agent for assessment
    const emergencyAgent = this.agentRegistry.emergency;
    const assessment = await this.callAgent(emergencyAgent, message, {
      mode: 'emergency_assessment'
    });

    return {
      isEmergency: true,
      severity: assessment.severity || 'high',
      recommendation: assessment.recommendation
    };
  }

  /**
   * Handle emergency situations
   */
  async handleEmergency(consultationId, message, emergencyCheck) {
    this.emit('emergency:detected', {
      consultationId,
      severity: emergencyCheck.severity,
      message
    });

    const emergencyResponse = {
      content: `⚠️ **EMERGENCY ASSESSMENT REQUIRED**\n\n${emergencyCheck.recommendation}`,
      priority: 'emergency',
      action: 'seek_immediate_care',
      agents: ['emergency']
    };

    // Log emergency
    console.error('EMERGENCY DETECTED:', {
      consultationId,
      timestamp: new Date(),
      severity: emergencyCheck.severity
    });

    return emergencyResponse;
  }

  /**
   * Identify which specialists should be consulted
   */
  identifyRequiredSpecialists(message, context) {
    const specialists = [];
    const lowerMessage = message.toLowerCase();

    // Check each specialist's trigger keywords
    Object.values(this.agentRegistry).forEach(agent => {
      if (agent.role === 'specialist' && agent.triggerKeywords) {
        const triggered = agent.triggerKeywords.some(keyword =>
          lowerMessage.includes(keyword)
        );

        if (triggered) {
          specialists.push(agent.id);
        }
      }
    });

    // Check document context for relevant specialists
    if (context.documents) {
      context.documents.forEach(doc => {
        if (doc.type === 'lab' && doc.content) {
          // Check for specific lab values
          if (doc.content.includes('cholesterol') || doc.content.includes('lipid')) {
            specialists.push('cardio');
          }
          if (doc.content.includes('glucose') || doc.content.includes('A1c')) {
            specialists.push('endo');
          }
        }
      });
    }

    return [...new Set(specialists)]; // Remove duplicates
  }

  /**
   * Get responses from multiple agents in parallel
   */
  async getAgentResponses(consultationId, message, context, agentIds) {
    const responses = await Promise.all(
      agentIds.map(async (agentId) => {
        const agent = this.agentRegistry[agentId];
        if (!agent) return null;

        // Emit thinking event
        this.emit('agent:thinking', {
          consultationId,
          agentId,
          agentName: agent.name
        });

        try {
          const response = await this.callAgent(agent, message, context);

          // Emit response event
          this.emit('agent:responded', {
            consultationId,
            agentId,
            agentName: agent.name,
            hasFindings: !!response.findings
          });

          return {
            agentId,
            agentName: agent.name,
            response
          };
        } catch (error) {
          console.error(`Agent ${agentId} error:`, error);
          return {
            agentId,
            agentName: agent.name,
            response: {
              content: 'Unable to provide assessment at this time.',
              error: true
            }
          };
        }
      })
    );

    return responses.filter(r => r !== null);
  }

  /**
   * Call a specific agent with the inference provider
   */
  async callAgent(agent, message, context) {
    // Get the active provider (from database or default)
    const provider = await this.getActiveProvider();

    // Build the prompt with agent's system prompt and context
    const messages = [
      {
        role: 'system',
        content: agent.systemPrompt
      }
    ];

    // Add context if available
    if (context.patientHistory) {
      messages.push({
        role: 'system',
        content: `Patient History: ${JSON.stringify(context.patientHistory)}`
      });
    }

    if (context.documents) {
      messages.push({
        role: 'system',
        content: `Medical Documents: ${context.documents.map(d => d.summary || d.content).join('\n')}`
      });
    }

    // Add the user message
    messages.push({
      role: 'user',
      content: message
    });

    // Call the inference provider
    const response = await provider.complete({
      messages,
      model: agent.model,
      temperature: 0.7,
      max_tokens: 1000
    });

    // Parse response for structured data
    const parsedResponse = this.parseAgentResponse(response.content);

    return {
      content: response.content,
      findings: parsedResponse.findings,
      recommendations: parsedResponse.recommendations,
      referrals: parsedResponse.referrals
    };
  }

  /**
   * Parse agent response for structured data
   */
  parseAgentResponse(content) {
    const findings = [];
    const recommendations = [];
    const referrals = [];

    // Look for structured markers in the response
    const lines = content.split('\n');
    let currentSection = null;

    lines.forEach(line => {
      if (line.includes('Finding:') || line.includes('Diagnosis:')) {
        findings.push(line.replace(/^.*?(Finding:|Diagnosis:)\s*/i, ''));
      }
      if (line.includes('Recommend:') || line.includes('Recommendation:')) {
        recommendations.push(line.replace(/^.*?(Recommend:|Recommendation:)\s*/i, ''));
      }
      if (line.includes('Refer:') || line.includes('Referral:')) {
        referrals.push(line.replace(/^.*?(Refer:|Referral:)\s*/i, ''));
      }
    });

    return { findings, recommendations, referrals };
  }

  /**
   * Synthesize responses from multiple agents
   */
  async synthesizeResponses(agentResponses, context) {
    if (agentResponses.length === 1) {
      // Single agent response
      return {
        content: agentResponses[0].response.content,
        contributingAgents: [agentResponses[0].agentId],
        findings: agentResponses[0].response.findings,
        recommendations: agentResponses[0].response.recommendations
      };
    }

    // Multiple agents - use primary care orchestrator to synthesize
    const orchestrator = this.agentRegistry.dr_glitter_mane;

    const synthesisPrompt = `As the primary care orchestrator, synthesize these specialist assessments into a comprehensive response:

${agentResponses.map(r => `**${r.agentName}:**\n${r.response.content}`).join('\n\n')}

Provide a unified assessment with:
1. Key findings
2. Prioritized recommendations
3. Follow-up care plan`;

    const synthesis = await this.callAgent(orchestrator, synthesisPrompt, context);

    // Collect all findings and recommendations
    const allFindings = [];
    const allRecommendations = [];

    agentResponses.forEach(r => {
      if (r.response.findings) allFindings.push(...r.response.findings);
      if (r.response.recommendations) allRecommendations.push(...r.response.recommendations);
    });

    return {
      content: synthesis.content,
      contributingAgents: agentResponses.map(r => r.agentId),
      findings: allFindings,
      recommendations: allRecommendations
    };
  }

  /**
   * Process uploaded document
   */
  async processDocument(userId, document, metadata = {}) {
    const consultationId = uuidv4();

    this.emit('document:processing', {
      consultationId,
      documentName: metadata.filename,
      userId
    });

    // Create a consultation for document analysis
    const consultation = {
      id: consultationId,
      userId,
      startTime: new Date(),
      type: 'document_analysis',
      document: metadata,
      status: 'analyzing'
    };

    this.activeConsultations.set(consultationId, consultation);

    // Analyze with primary care orchestrator first
    const initialAnalysis = await this.callAgent(
      this.agentRegistry.dr_glitter_mane,
      `Analyze this medical document and identify key findings:\n\n${document}`,
      { documentType: metadata.type }
    );

    // Determine which specialists should review
    const requiredSpecialists = this.identifyRequiredSpecialists(
      initialAnalysis.content,
      { documents: [{ content: document, type: metadata.type }] }
    );

    // Get specialist reviews in parallel
    const specialistReviews = await this.getAgentResponses(
      consultationId,
      `Review this medical document for your specialty:\n\n${document}`,
      { documentType: metadata.type },
      requiredSpecialists
    );

    // Synthesize all reviews
    const synthesis = await this.synthesizeResponses(
      [
        {
          agentId: 'dr_glitter_mane',
          agentName: 'Dr. Glitter Mane',
          response: initialAnalysis
        },
        ...specialistReviews
      ],
      { documentType: metadata.type }
    );

    // Update consultation
    consultation.status = 'complete';
    consultation.analysis = synthesis;

    this.emit('document:analyzed', {
      consultationId,
      findings: synthesis.findings,
      recommendations: synthesis.recommendations
    });

    return {
      consultationId,
      analysis: synthesis
    };
  }

  /**
   * Save consultation to database
   */
  async saveConsultation(consultation) {
    try {
      await this.prisma.consultation.upsert({
        where: { id: consultation.id },
        update: {
          messages: consultation.messages,
          findings: consultation.findings,
          recommendations: consultation.recommendations,
          status: consultation.status
        },
        create: {
          id: consultation.id,
          userId: consultation.userId,
          messages: consultation.messages,
          findings: consultation.findings,
          recommendations: consultation.recommendations,
          status: consultation.status,
          startTime: consultation.startTime
        }
      });
    } catch (error) {
      console.error('Error saving consultation:', error);
    }
  }

  /**
   * End a consultation
   */
  async endConsultation(consultationId) {
    const consultation = this.activeConsultations.get(consultationId);
    if (consultation) {
      consultation.status = 'complete';
      consultation.endTime = new Date();

      await this.saveConsultation(consultation);

      this.emit('consultation:ended', {
        consultationId,
        duration: consultation.endTime - consultation.startTime
      });

      this.activeConsultations.delete(consultationId);
    }
  }
}

module.exports = MedicalAgentOrchestrator;