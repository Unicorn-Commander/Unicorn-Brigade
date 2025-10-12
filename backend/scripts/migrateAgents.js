// Agent Migration Script - Convert Markdown Agents to Database Format
// Preserves independence while standardizing structure

const fs = require('fs').promises;
const path = require('path');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

// Domain-specific avatars/icons
const domainAvatars = {
  financial: '💰',
  legal: '⚖️',
  investigation: '🔍',
  technology: '💻',
  intelligence: '🕵️',
  orchestration: '🎯',
  crisis: '🚨'
};

// Agent type mapping based on folder structure
const agentTypeMapping = {
  'the_colonel': 'orchestrator',
  'team_lead': 'team_lead',
  'default': 'individual'
};

// Enhanced persona templates for agents missing detailed personas
const personaEnhancements = {
  forensic_accountant: `You are a Certified Fraud Examiner (CFE) and CPA with 15+ years of experience in financial investigations. You've worked on high-profile cases including corporate embezzlement, money laundering, and tax fraud. Your expertise includes forensic data analytics, asset tracing, and expert witness testimony. You maintain meticulous documentation and follow strict chain-of-custody procedures.`,

  detective_sherlock: `You are a master investigator with 20+ years of experience in criminal and civil investigations. Trained in advanced interrogation techniques, evidence collection, and criminal psychology. You've solved complex cases ranging from missing persons to corporate espionage. Your deductive reasoning and attention to detail are unparalleled.`,

  analyst_sterling: `You are a senior intelligence analyst with experience in both government and private sector. Specialized in pattern recognition, threat assessment, and predictive analysis. You've worked with classified intelligence and have expertise in geopolitical analysis, counter-intelligence, and strategic planning.`,

  osint_oracle: `You are an Open Source Intelligence specialist with deep expertise in digital investigations. Proficient in advanced search techniques, social media analysis, dark web research, and digital footprint analysis. You've supported law enforcement, corporate security, and journalistic investigations.`,

  contract_analyzer: `You are a contract law specialist with J.D. from Harvard Law and 18+ years of experience. You've reviewed thousands of contracts across industries including technology, real estate, and M&A. Expert in identifying risks, negotiating terms, and ensuring regulatory compliance.`,

  penetration_tester: `You are a Certified Ethical Hacker (CEH) and OSCP with 12+ years in offensive security. You've conducted penetration tests for Fortune 500 companies and government agencies. Expert in network exploitation, web application testing, and social engineering.`
};

async function loadMarkdownAgent(agentPath) {
  try {
    const configPath = path.join(agentPath, 'config.json');
    const promptPath = path.join(agentPath, 'system_prompt.md');
    const toolsPath = path.join(agentPath, 'tools.json');

    // Load config
    const configContent = await fs.readFile(configPath, 'utf-8');
    const config = JSON.parse(configContent);

    // Load system prompt
    let systemPrompt = '';
    try {
      systemPrompt = await fs.readFile(promptPath, 'utf-8');
    } catch (e) {
      console.log(`No system_prompt.md for ${agentPath}`);
    }

    // Load tools
    let tools = [];
    try {
      const toolsContent = await fs.readFile(toolsPath, 'utf-8');
      const toolsData = JSON.parse(toolsContent);
      tools = toolsData.tools || [];
    } catch (e) {
      console.log(`No tools.json for ${agentPath}`);
    }

    // Extract agent info from path and config
    const pathParts = agentPath.split(path.sep);
    const agentFolder = pathParts[pathParts.length - 1];
    const domain = pathParts[pathParts.length - 2];

    // Generate proper name from folder name
    const agentName = agentFolder
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

    // Extract capabilities from system prompt
    let capabilities = [];
    const capMatch = systemPrompt.match(/\*\*Capabilities:\*\*([\s\S]*?)(\*\*|$)/);
    if (capMatch) {
      capabilities = capMatch[1]
        .split('\n')
        .filter(line => line.trim().startsWith('-'))
        .map(line => line.replace(/^-\s*/, '').trim())
        .filter(cap => cap.length > 0);
    }

    // Determine agent type
    const agentType = agentTypeMapping[agentFolder] || agentTypeMapping.default;

    // Get or generate persona
    let persona = '';
    if (personaEnhancements[agentFolder]) {
      persona = personaEnhancements[agentFolder];
    } else {
      // Extract from system prompt if available
      const personaMatch = systemPrompt.match(/You are (.*?)\./);
      if (personaMatch) {
        persona = `You are ${personaMatch[1]}. ${systemPrompt.split('.').slice(1, 3).join('.')}`;
      }
    }

    // Determine avatar
    const avatar = domainAvatars[domain] || '🤖';

    return {
      name: config.agent_name || agentName,
      type: agentType,
      domain: domain,
      avatar: avatar,
      persona: persona,
      systemPrompt: systemPrompt,
      tools: JSON.stringify(tools),
      capabilities: JSON.stringify(capabilities),
      status: 'active',
      memory: JSON.stringify({}),
      performance: JSON.stringify({
        tasksCompleted: 0,
        successRate: 100,
        avgResponseTime: 0
      })
    };
  } catch (error) {
    console.error(`Error loading agent from ${agentPath}:`, error);
    return null;
  }
}

async function migrateAgents() {
  console.log('🚀 Starting Agent Migration...\n');

  const agentsDir = path.join(__dirname, '../../agents/domains');

  try {
    // Get all domains
    const domains = await fs.readdir(agentsDir);

    let totalAgents = 0;
    let migratedAgents = 0;
    let failedAgents = 0;

    for (const domain of domains) {
      const domainPath = path.join(agentsDir, domain);
      const stats = await fs.stat(domainPath);

      if (!stats.isDirectory()) continue;

      console.log(`\n📁 Processing domain: ${domain}`);

      // Handle nested structure for technology domain
      if (domain === 'technology') {
        const subDomains = await fs.readdir(domainPath);
        for (const subDomain of subDomains) {
          const subDomainPath = path.join(domainPath, subDomain);
          const subStats = await fs.stat(subDomainPath);

          if (!subStats.isDirectory()) continue;

          const agents = await fs.readdir(subDomainPath);
          for (const agent of agents) {
            const agentPath = path.join(subDomainPath, agent);
            const agentStats = await fs.stat(agentPath);

            if (!agentStats.isDirectory()) continue;

            totalAgents++;
            const agentData = await loadMarkdownAgent(agentPath);

            if (agentData) {
              try {
                // Check if agent already exists
                const existing = await prisma.agent.findFirst({
                  where: {
                    name: agentData.name,
                    domain: domain
                  }
                });

                if (existing) {
                  // Update existing agent
                  await prisma.agent.update({
                    where: { id: existing.id },
                    data: agentData
                  });
                  console.log(`  ✅ Updated: ${agentData.name}`);
                } else {
                  // Create new agent
                  await prisma.agent.create({
                    data: agentData
                  });
                  console.log(`  ✅ Created: ${agentData.name}`);
                }
                migratedAgents++;
              } catch (dbError) {
                console.error(`  ❌ Failed to save ${agentData.name}:`, dbError.message);
                failedAgents++;
              }
            } else {
              failedAgents++;
            }
          }
        }
      } else {
        // Handle regular domains
        const agents = await fs.readdir(domainPath);
        for (const agent of agents) {
          const agentPath = path.join(domainPath, agent);
          const agentStats = await fs.stat(agentPath);

          if (!agentStats.isDirectory()) continue;

          totalAgents++;
          const agentData = await loadMarkdownAgent(agentPath);

          if (agentData) {
            try {
              // Check if agent already exists
              const existing = await prisma.agent.findFirst({
                where: {
                  name: agentData.name,
                  domain: domain
                }
              });

              if (existing) {
                // Update existing agent
                await prisma.agent.update({
                  where: { id: existing.id },
                  data: agentData
                });
                console.log(`  ✅ Updated: ${agentData.name}`);
              } else {
                // Create new agent
                await prisma.agent.create({
                  data: agentData
                });
                console.log(`  ✅ Created: ${agentData.name}`);
              }
              migratedAgents++;
            } catch (dbError) {
              console.error(`  ❌ Failed to save ${agentData.name}:`, dbError.message);
              failedAgents++;
            }
          } else {
            failedAgents++;
          }
        }
      }
    }

    // Summary
    console.log('\n' + '='.repeat(50));
    console.log('📊 Migration Summary:');
    console.log('='.repeat(50));
    console.log(`Total Agents Found: ${totalAgents}`);
    console.log(`Successfully Migrated: ${migratedAgents}`);
    console.log(`Failed: ${failedAgents}`);
    console.log(`Success Rate: ${((migratedAgents/totalAgents) * 100).toFixed(1)}%`);
    console.log('='.repeat(50));

    // Create sample orchestration to demonstrate relationships
    if (migratedAgents > 0) {
      console.log('\n🎭 Creating sample orchestration...');

      const colonel = await prisma.agent.findFirst({
        where: { name: { contains: 'Colonel' } }
      });

      if (colonel) {
        const financialAgents = await prisma.agent.findMany({
          where: { domain: 'financial' },
          take: 3
        });

        const legalAgents = await prisma.agent.findMany({
          where: { domain: 'legal' },
          take: 3
        });

        if (financialAgents.length > 0 || legalAgents.length > 0) {
          const orchestration = await prisma.orchestration.create({
            data: {
              name: 'Multi-Domain Investigation',
              orchestratorId: colonel.id,
              type: 'investigation',
              status: 'planning',
              config: JSON.stringify({
                objective: 'Coordinate financial and legal analysis',
                phases: ['discovery', 'analysis', 'reporting'],
                timeline: '2 weeks'
              }),
              participants: {
                connect: [...financialAgents, ...legalAgents].map(a => ({ id: a.id }))
              }
            }
          });

          console.log(`✅ Created sample orchestration with ${financialAgents.length + legalAgents.length} participants`);
        }
      }
    }

    console.log('\n✨ Migration complete!');

  } catch (error) {
    console.error('Migration failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

// Run migration
migrateAgents().catch(console.error);

// Export for testing
module.exports = { loadMarkdownAgent, migrateAgents };