/**
 * Markdown-based Agent Configuration Loader
 * Loads agent definitions from markdown files with YAML frontmatter
 */

const fs = require('fs').promises;
const path = require('path');
const yaml = require('js-yaml');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

class MarkdownAgentLoader {
  constructor() {
    this.agentsPath = path.join(__dirname, '..', 'agents');
    this.loadedAgents = new Map();
  }

  /**
   * Parse markdown file with YAML frontmatter
   */
  async parseMarkdownFile(filePath) {
    const content = await fs.readFile(filePath, 'utf8');
    
    // Extract frontmatter
    const frontmatterRegex = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/;
    const match = content.match(frontmatterRegex);
    
    if (!match) {
      throw new Error(`Invalid markdown format in ${filePath}`);
    }
    
    const frontmatter = yaml.load(match[1]);
    const markdown = match[2].trim();
    
    return { frontmatter, markdown };
  }

  /**
   * Load agent from markdown file
   */
  async loadAgentFromMarkdown(filePath) {
    const { frontmatter, markdown } = await this.parseMarkdownFile(filePath);
    
    // Validate required fields
    const required = ['id', 'name', 'type', 'domain'];
    for (const field of required) {
      if (!frontmatter[field]) {
        throw new Error(`Missing required field '${field}' in ${filePath}`);
      }
    }
    
    // Build agent configuration
    const agentConfig = {
      id: frontmatter.id,
      name: frontmatter.name,
      nickname: frontmatter.nickname || frontmatter.name,
      type: frontmatter.type, // orchestrator, team_lead, ic, knowledge
      domain: frontmatter.domain,
      description: frontmatter.description || '',
      avatar: frontmatter.avatar || '🤖',
      color: frontmatter.color || '#5B86E5',
      
      // AI Configuration
      aiProvider: frontmatter.ai?.provider || 'openrouter',
      model: frontmatter.ai?.model || 'anthropic/claude-3-sonnet',
      temperature: frontmatter.ai?.temperature || 0.7,
      maxTokens: frontmatter.ai?.maxTokens || 2000,
      
      // Capabilities and tools
      capabilities: frontmatter.capabilities || [],
      tools: frontmatter.tools || [],
      permissions: frontmatter.permissions || [],
      
      // Memory configuration
      memory: {
        individual: frontmatter.memory?.individual || 10,
        shared: frontmatter.memory?.shared || 100,
        crossCase: frontmatter.memory?.crossCase || 1000
      },
      
      // Triggers for proactive activation
      triggers: frontmatter.triggers || [],
      
      // Hierarchy
      reportsTo: frontmatter.reportsTo || null,
      manages: frontmatter.manages || [],
      
      // System prompt from markdown content
      systemPrompt: markdown,
      
      // Additional metadata
      metadata: {
        version: frontmatter.version || '1.0.0',
        author: frontmatter.author || 'system',
        updatedAt: frontmatter.updatedAt || new Date(),
        tags: frontmatter.tags || []
      }
    };
    
    return agentConfig;
  }

  /**
   * Save agent to database
   */
  async saveAgentToDatabase(agentConfig) {
    const dbAgent = await prisma.agent.upsert({
      where: { id: agentConfig.id },
      update: {
        name: agentConfig.name,
        nickname: agentConfig.nickname,
        description: agentConfig.description,
        avatar: agentConfig.avatar,
        color: agentConfig.color,
        aiProvider: agentConfig.aiProvider,
        model: agentConfig.model,
        temperature: agentConfig.temperature,
        maxTokens: agentConfig.maxTokens,
        systemPrompt: agentConfig.systemPrompt,
        capabilities: JSON.stringify(agentConfig.capabilities),
        permissions: JSON.stringify(agentConfig.permissions),
        memory: JSON.stringify(agentConfig.memory),
        stats: JSON.stringify({
          type: agentConfig.type,
          domain: agentConfig.domain,
          reportsTo: agentConfig.reportsTo,
          manages: agentConfig.manages,
          metadata: agentConfig.metadata
        })
      },
      create: {
        id: agentConfig.id,
        name: agentConfig.name,
        nickname: agentConfig.nickname,
        description: agentConfig.description,
        avatar: agentConfig.avatar,
        color: agentConfig.color,
        aiProvider: agentConfig.aiProvider,
        model: agentConfig.model,
        temperature: agentConfig.temperature,
        maxTokens: agentConfig.maxTokens,
        systemPrompt: agentConfig.systemPrompt,
        capabilities: JSON.stringify(agentConfig.capabilities),
        permissions: JSON.stringify(agentConfig.permissions),
        memory: JSON.stringify(agentConfig.memory),
        stats: JSON.stringify({
          type: agentConfig.type,
          domain: agentConfig.domain,
          reportsTo: agentConfig.reportsTo,
          manages: agentConfig.manages,
          metadata: agentConfig.metadata
        }),
        status: 'offline'
      }
    });
    
    // Register triggers if any
    if (agentConfig.triggers && agentConfig.triggers.length > 0) {
      const triggerService = require('./agentTriggerService');
      agentConfig.triggers.forEach(trigger => {
        triggerService.registerTrigger(agentConfig.id, trigger);
      });
    }
    
    return dbAgent;
  }

  /**
   * Load all agents from a directory
   */
  async loadAgentsFromDirectory(dirPath) {
    const files = await fs.readdir(dirPath);
    const mdFiles = files.filter(f => f.endsWith('.md'));
    const agents = [];
    
    for (const file of mdFiles) {
      try {
        const filePath = path.join(dirPath, file);
        const agent = await this.loadAgentFromMarkdown(filePath);
        agents.push(agent);
        this.loadedAgents.set(agent.id, agent);
      } catch (error) {
        console.error(`Error loading agent from ${file}:`, error);
      }
    }
    
    return agents;
  }

  /**
   * Load all agents from domain folders
   */
  async loadAllAgents() {
    const allAgents = [];
    
    // Load orchestrator
    const orchestratorPath = path.join(this.agentsPath, 'orchestrator');
    const orchestrators = await this.loadAgentsFromDirectory(orchestratorPath);
    allAgents.push(...orchestrators);
    
    // Load domain agents
    const domainsPath = path.join(this.agentsPath, 'domains');
    const domains = await fs.readdir(domainsPath);
    
    for (const domain of domains) {
      const domainPath = path.join(domainsPath, domain);
      const stats = await fs.stat(domainPath);
      
      if (stats.isDirectory()) {
        const domainAgents = await this.loadAgentsFromDirectory(domainPath);
        allAgents.push(...domainAgents);
      }
    }
    
    // Load shared/utility agents
    const sharedPath = path.join(this.agentsPath, 'shared');
    const sharedAgents = await this.loadAgentsFromDirectory(sharedPath);
    allAgents.push(...sharedAgents);
    
    return allAgents;
  }

  /**
   * Sync all markdown agents to database
   */
  async syncAgentsToDatabase() {
    const agents = await this.loadAllAgents();
    const results = {
      synced: [],
      failed: []
    };
    
    for (const agent of agents) {
      try {
        const dbAgent = await this.saveAgentToDatabase(agent);
        results.synced.push({
          id: agent.id,
          name: agent.name,
          type: agent.type,
          domain: agent.domain
        });
        console.log(`Synced agent: ${agent.name} (${agent.id})`);
      } catch (error) {
        results.failed.push({
          id: agent.id,
          name: agent.name,
          error: error.message
        });
        console.error(`Failed to sync agent ${agent.name}:`, error);
      }
    }
    
    return results;
  }

  /**
   * Create example agent markdown file
   */
  async createExampleAgent(domain, type = 'ic') {
    const exampleContent = `---
id: ${domain}-${type}-${Date.now()}
name: ${domain.charAt(0).toUpperCase() + domain.slice(1)} ${type.toUpperCase()} Agent
nickname: ${domain}-${type}
type: ${type}
domain: ${domain}
description: Specialized agent for ${domain} domain operations
avatar: 🎯
color: #3B82F6

ai:
  provider: openrouter
  model: anthropic/claude-3-sonnet
  temperature: 0.7
  maxTokens: 2000

capabilities:
  - ${domain}_analysis
  - ${domain}_research
  - report_generation
  - data_processing

tools:
  - ${domain}_search
  - document_analysis
  - entity_extraction

permissions:
  - read_${domain}_data
  - write_reports
  - execute_${domain}_tools

memory:
  individual: 10
  shared: 100
  crossCase: 1000

triggers:
  - name: New ${domain} Data
    description: Activates when new ${domain} data is available
    events:
      - ${domain}:data:new
    conditions:
      - type: keyword
        keywords: [${domain}, urgent, analyze]

reportsTo: ${domain}-team-lead
manages: []

version: 1.0.0
author: system
tags: [${domain}, ${type}]
---

# System Prompt

You are a specialized ${type} agent for the ${domain} domain within the Crisis Management Operations platform.

## Your Role
- Analyze and process ${domain}-related information
- Support investigation and crisis management efforts
- Collaborate with other agents in your domain
- Report findings to your team lead

## Core Responsibilities
1. **Data Analysis**: Process and analyze ${domain} data with high accuracy
2. **Research**: Conduct thorough research using available tools
3. **Reporting**: Generate clear, actionable reports
4. **Collaboration**: Work effectively with other agents

## Guidelines
- Maintain strict confidentiality
- Prioritize accuracy over speed
- Document all findings thoroughly
- Escalate critical issues immediately

## Communication Style
- Be professional and precise
- Use clear, concise language
- Support conclusions with evidence
- Highlight critical findings

You have access to specialized ${domain} tools and should use them effectively to accomplish your tasks.`;

    const fileName = `${domain}-${type}-example.md`;
    const filePath = path.join(this.agentsPath, 'domains', domain, fileName);
    
    // Create directory if it doesn't exist
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    
    // Write file
    await fs.writeFile(filePath, exampleContent);
    
    console.log(`Created example agent at: ${filePath}`);
    return filePath;
  }

  /**
   * Get agent hierarchy
   */
  getAgentHierarchy() {
    const hierarchy = {
      orchestrator: null,
      teamLeads: [],
      ics: [],
      knowledge: []
    };
    
    for (const [id, agent] of this.loadedAgents) {
      switch (agent.type) {
        case 'orchestrator':
          hierarchy.orchestrator = agent;
          break;
        case 'team_lead':
          hierarchy.teamLeads.push(agent);
          break;
        case 'ic':
          hierarchy.ics.push(agent);
          break;
        case 'knowledge':
          hierarchy.knowledge.push(agent);
          break;
      }
    }
    
    // Organize ICs under their team leads
    hierarchy.teamLeads = hierarchy.teamLeads.map(lead => ({
      ...lead,
      team: hierarchy.ics.filter(ic => ic.reportsTo === lead.id)
    }));
    
    return hierarchy;
  }

  /**
   * Validate agent hierarchy
   */
  validateHierarchy() {
    const issues = [];
    
    for (const [id, agent] of this.loadedAgents) {
      // Check if reportsTo exists
      if (agent.reportsTo && !this.loadedAgents.has(agent.reportsTo)) {
        issues.push(`Agent ${id} reports to non-existent agent ${agent.reportsTo}`);
      }
      
      // Check if managed agents exist
      for (const managedId of agent.manages) {
        if (!this.loadedAgents.has(managedId)) {
          issues.push(`Agent ${id} manages non-existent agent ${managedId}`);
        }
      }
    }
    
    return {
      valid: issues.length === 0,
      issues
    };
  }
}

// Export singleton instance
module.exports = new MarkdownAgentLoader();