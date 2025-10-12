/**
 * Proactive Agent Triggering Service
 * Monitors events and conditions to automatically activate agents
 */

const EventEmitter = require('events');
const { PrismaClient } = require('@prisma/client');
const agentOrchestrator = require('./agentOrchestrator');

const prisma = new PrismaClient();

class AgentTriggerService extends EventEmitter {
  constructor() {
    super();
    this.triggers = new Map(); // agentId -> trigger conditions
    this.activeMonitors = new Map(); // monitorId -> monitor details
    this.eventQueue = [];
    this.isProcessing = false;
    
    // Start event processor
    this.startEventProcessor();
  }

  /**
   * Register a trigger condition for an agent
   */
  registerTrigger(agentId, triggerConfig) {
    const triggerId = `${agentId}_${Date.now()}`;
    
    const trigger = {
      id: triggerId,
      agentId,
      name: triggerConfig.name,
      description: triggerConfig.description,
      conditions: triggerConfig.conditions || [],
      events: triggerConfig.events || [],
      schedule: triggerConfig.schedule || null,
      action: triggerConfig.action || 'activate',
      priority: triggerConfig.priority || 5,
      enabled: triggerConfig.enabled !== false,
      metadata: triggerConfig.metadata || {}
    };

    if (!this.triggers.has(agentId)) {
      this.triggers.set(agentId, []);
    }
    
    this.triggers.get(agentId).push(trigger);
    
    // Set up event listeners for this trigger
    this.setupEventListeners(trigger);
    
    // Set up scheduled triggers if needed
    if (trigger.schedule) {
      this.setupScheduledTrigger(trigger);
    }
    
    console.log(`Registered trigger ${triggerId} for agent ${agentId}`);
    return triggerId;
  }

  /**
   * Setup event listeners for trigger events
   */
  setupEventListeners(trigger) {
    trigger.events.forEach(eventPattern => {
      this.on(eventPattern, (eventData) => {
        if (trigger.enabled && this.evaluateConditions(trigger.conditions, eventData)) {
          this.queueAgentActivation(trigger.agentId, trigger, eventData);
        }
      });
    });
  }

  /**
   * Setup scheduled triggers (cron-like)
   */
  setupScheduledTrigger(trigger) {
    // Simple interval-based scheduling
    const scheduleMap = {
      'every_hour': 3600000,
      'every_day': 86400000,
      'every_30_minutes': 1800000,
      'every_5_minutes': 300000
    };
    
    const interval = scheduleMap[trigger.schedule] || 3600000;
    
    const monitorId = setInterval(() => {
      if (trigger.enabled) {
        this.queueAgentActivation(trigger.agentId, trigger, { 
          type: 'scheduled',
          schedule: trigger.schedule 
        });
      }
    }, interval);
    
    this.activeMonitors.set(trigger.id, {
      type: 'schedule',
      interval: monitorId
    });
  }

  /**
   * Evaluate trigger conditions
   */
  evaluateConditions(conditions, eventData) {
    if (!conditions || conditions.length === 0) return true;
    
    return conditions.every(condition => {
      switch (condition.type) {
        case 'keyword':
          return this.evaluateKeywordCondition(condition, eventData);
        case 'threshold':
          return this.evaluateThresholdCondition(condition, eventData);
        case 'pattern':
          return this.evaluatePatternCondition(condition, eventData);
        case 'entity':
          return this.evaluateEntityCondition(condition, eventData);
        case 'time':
          return this.evaluateTimeCondition(condition, eventData);
        default:
          return true;
      }
    });
  }

  /**
   * Keyword-based condition evaluation
   */
  evaluateKeywordCondition(condition, eventData) {
    const text = JSON.stringify(eventData).toLowerCase();
    const keywords = condition.keywords || [];
    const matchType = condition.matchType || 'any';
    
    if (matchType === 'all') {
      return keywords.every(keyword => text.includes(keyword.toLowerCase()));
    } else {
      return keywords.some(keyword => text.includes(keyword.toLowerCase()));
    }
  }

  /**
   * Threshold-based condition evaluation
   */
  evaluateThresholdCondition(condition, eventData) {
    const value = this.getNestedValue(eventData, condition.field);
    const threshold = condition.threshold;
    const operator = condition.operator || 'gte';
    
    switch (operator) {
      case 'gt': return value > threshold;
      case 'gte': return value >= threshold;
      case 'lt': return value < threshold;
      case 'lte': return value <= threshold;
      case 'eq': return value === threshold;
      default: return false;
    }
  }

  /**
   * Pattern-based condition evaluation
   */
  evaluatePatternCondition(condition, eventData) {
    const text = JSON.stringify(eventData);
    const pattern = new RegExp(condition.pattern, condition.flags || 'i');
    return pattern.test(text);
  }

  /**
   * Entity-based condition evaluation
   */
  evaluateEntityCondition(condition, eventData) {
    const entities = eventData.entities || [];
    const targetType = condition.entityType;
    const targetName = condition.entityName;
    
    return entities.some(entity => {
      const typeMatch = !targetType || entity.type === targetType;
      const nameMatch = !targetName || entity.name.includes(targetName);
      return typeMatch && nameMatch;
    });
  }

  /**
   * Time-based condition evaluation
   */
  evaluateTimeCondition(condition, eventData) {
    const now = new Date();
    const hour = now.getHours();
    const dayOfWeek = now.getDay();
    
    if (condition.hours && !condition.hours.includes(hour)) {
      return false;
    }
    
    if (condition.daysOfWeek && !condition.daysOfWeek.includes(dayOfWeek)) {
      return false;
    }
    
    return true;
  }

  /**
   * Queue agent activation
   */
  queueAgentActivation(agentId, trigger, eventData) {
    this.eventQueue.push({
      agentId,
      trigger,
      eventData,
      timestamp: new Date(),
      priority: trigger.priority
    });
    
    // Sort by priority
    this.eventQueue.sort((a, b) => b.priority - a.priority);
    
    // Process queue
    this.processEventQueue();
  }

  /**
   * Process queued agent activations
   */
  async processEventQueue() {
    if (this.isProcessing || this.eventQueue.length === 0) return;
    
    this.isProcessing = true;
    
    while (this.eventQueue.length > 0) {
      const event = this.eventQueue.shift();
      
      try {
        await this.activateAgent(event.agentId, event.trigger, event.eventData);
      } catch (error) {
        console.error(`Error activating agent ${event.agentId}:`, error);
      }
    }
    
    this.isProcessing = false;
  }

  /**
   * Activate an agent based on trigger
   */
  async activateAgent(agentId, trigger, eventData) {
    console.log(`Activating agent ${agentId} via trigger ${trigger.name}`);
    
    // Build activation context
    const context = {
      trigger: trigger.name,
      triggerType: trigger.action,
      eventData,
      timestamp: new Date(),
      metadata: trigger.metadata
    };
    
    // Generate prompt based on trigger action
    const prompt = this.generateActivationPrompt(trigger, eventData);
    
    try {
      // Initialize agent if needed
      await agentOrchestrator.initializeAgent(agentId);
      
      // Send activation message
      const result = await agentOrchestrator.processMessage(
        agentId,
        'system', // System-triggered
        prompt,
        context
      );
      
      // Log activation
      await this.logActivation(agentId, trigger, eventData, result);
      
      // Emit activation event
      this.emit('agent:activated', {
        agentId,
        trigger: trigger.name,
        result
      });
      
      return result;
    } catch (error) {
      console.error(`Failed to activate agent ${agentId}:`, error);
      throw error;
    }
  }

  /**
   * Generate activation prompt based on trigger
   */
  generateActivationPrompt(trigger, eventData) {
    const basePrompt = trigger.metadata.prompt || 'You have been activated to handle the following situation:';
    
    const contextInfo = {
      trigger: trigger.name,
      description: trigger.description,
      eventType: eventData.type || 'unknown',
      timestamp: new Date().toISOString()
    };
    
    return `${basePrompt}

Trigger: ${trigger.name}
Description: ${trigger.description}
Event Data: ${JSON.stringify(eventData, null, 2)}

Please analyze this situation and take appropriate action based on your capabilities.`;
  }

  /**
   * Log agent activation
   */
  async logActivation(agentId, trigger, eventData, result) {
    try {
      await prisma.activityLog.create({
        data: {
          userId: agentId,
          action: `agent:triggered:${trigger.name}`,
          details: {
            trigger: trigger.name,
            triggerType: trigger.action,
            eventData,
            success: true,
            responsePreview: result.agentMessage?.content?.substring(0, 200)
          }
        }
      });
    } catch (error) {
      console.error('Failed to log activation:', error);
    }
  }

  /**
   * Emit event that may trigger agents
   */
  emitTriggerEvent(eventType, eventData) {
    this.emit(eventType, eventData);
  }

  /**
   * Get nested value from object
   */
  getNestedValue(obj, path) {
    return path.split('.').reduce((curr, prop) => curr?.[prop], obj);
  }

  /**
   * Start event processor
   */
  startEventProcessor() {
    // Process queue every second
    setInterval(() => {
      if (this.eventQueue.length > 0) {
        this.processEventQueue();
      }
    }, 1000);
  }

  /**
   * Common trigger patterns for crisis management
   */
  getCommonTriggers() {
    return {
      urgentKeywords: {
        name: 'Urgent Keywords Detection',
        description: 'Activates when urgent/critical keywords are detected',
        events: ['message:received', 'document:uploaded'],
        conditions: [{
          type: 'keyword',
          keywords: ['urgent', 'critical', 'emergency', 'immediate', 'asap', 'fraud', 'threat'],
          matchType: 'any'
        }]
      },
      
      newEvidence: {
        name: 'New Evidence Upload',
        description: 'Activates when new evidence is uploaded to a case',
        events: ['document:uploaded', 'evidence:added'],
        conditions: [{
          type: 'pattern',
          pattern: 'evidence|proof|document|recording|screenshot',
          flags: 'i'
        }]
      },
      
      legalDeadline: {
        name: 'Legal Deadline Approaching',
        description: 'Activates when legal deadlines are near',
        events: ['deadline:approaching', 'calendar:update'],
        conditions: [{
          type: 'threshold',
          field: 'daysUntilDeadline',
          threshold: 3,
          operator: 'lte'
        }]
      },
      
      highValueEntity: {
        name: 'High Value Entity Detected',
        description: 'Activates when important entities are mentioned',
        events: ['entity:detected', 'message:received'],
        conditions: [{
          type: 'entity',
          entityType: 'person',
          importance: 'high'
        }]
      },
      
      dailyBriefing: {
        name: 'Daily Briefing',
        description: 'Generates daily status report',
        schedule: 'every_day',
        conditions: [{
          type: 'time',
          hours: [9], // 9 AM
          daysOfWeek: [1, 2, 3, 4, 5] // Weekdays
        }]
      }
    };
  }

  /**
   * Register common triggers for an agent
   */
  registerCommonTriggers(agentId, triggerNames = []) {
    const commonTriggers = this.getCommonTriggers();
    const registered = [];
    
    triggerNames.forEach(name => {
      if (commonTriggers[name]) {
        const triggerId = this.registerTrigger(agentId, commonTriggers[name]);
        registered.push({ name, triggerId });
      }
    });
    
    return registered;
  }

  /**
   * Disable/enable triggers for an agent
   */
  setTriggerState(agentId, enabled) {
    const triggers = this.triggers.get(agentId) || [];
    triggers.forEach(trigger => {
      trigger.enabled = enabled;
    });
  }

  /**
   * Remove all triggers for an agent
   */
  removeTriggers(agentId) {
    const triggers = this.triggers.get(agentId) || [];
    
    // Clear scheduled monitors
    triggers.forEach(trigger => {
      if (this.activeMonitors.has(trigger.id)) {
        const monitor = this.activeMonitors.get(trigger.id);
        if (monitor.type === 'schedule') {
          clearInterval(monitor.interval);
        }
        this.activeMonitors.delete(trigger.id);
      }
    });
    
    // Remove all event listeners for this agent
    this.removeAllListeners();
    
    // Clear triggers
    this.triggers.delete(agentId);
  }

  /**
   * Get trigger statistics
   */
  getTriggerStats() {
    const stats = {
      totalTriggers: 0,
      enabledTriggers: 0,
      agentsWithTriggers: this.triggers.size,
      activeMonitors: this.activeMonitors.size,
      queuedEvents: this.eventQueue.length,
      triggersByAgent: {}
    };
    
    for (const [agentId, triggers] of this.triggers) {
      stats.totalTriggers += triggers.length;
      stats.enabledTriggers += triggers.filter(t => t.enabled).length;
      stats.triggersByAgent[agentId] = {
        total: triggers.length,
        enabled: triggers.filter(t => t.enabled).length,
        triggers: triggers.map(t => ({
          name: t.name,
          enabled: t.enabled,
          priority: t.priority
        }))
      };
    }
    
    return stats;
  }
}

// Export singleton instance
module.exports = new AgentTriggerService();