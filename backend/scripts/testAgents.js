// Test script to verify migrated agents
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function testAgents() {
  try {
    console.log('🔍 Testing migrated agents...\n');

    // Count total agents
    const totalAgents = await prisma.agent.count();
    console.log(`✅ Total agents in database: ${totalAgents}`);

    // Get agents by domain
    const domains = ['financial', 'legal', 'investigation', 'technology', 'orchestration', 'intelligence', 'crisis'];

    console.log('\n📊 Agents by domain:');
    for (const domain of domains) {
      const count = await prisma.agent.count({
        where: { domain }
      });
      if (count > 0) {
        console.log(`  ${domain}: ${count} agents`);
      }
    }

    // Get some sample agents
    console.log('\n🎯 Sample agents:');
    const sampleAgents = await prisma.agent.findMany({
      take: 5,
      select: {
        name: true,
        type: true,
        domain: true,
        avatar: true,
        status: true
      }
    });

    sampleAgents.forEach(agent => {
      console.log(`  ${agent.avatar} ${agent.name} (${agent.type}) - ${agent.domain} - ${agent.status}`);
    });

    // Check for The Colonel
    const colonel = await prisma.agent.findFirst({
      where: { name: { contains: 'Colonel' } }
    });

    if (colonel) {
      console.log('\n🎖️ The Colonel found:');
      console.log(`  Name: ${colonel.name}`);
      console.log(`  Type: ${colonel.type}`);
      console.log(`  Domain: ${colonel.domain}`);
      console.log(`  Status: ${colonel.status}`);

      // Parse and display capabilities
      const capabilities = JSON.parse(colonel.capabilities || '[]');
      if (capabilities.length > 0) {
        console.log('  Capabilities:');
        capabilities.slice(0, 3).forEach(cap => {
          console.log(`    - ${cap}`);
        });
      }
    }

    // Check orchestrations
    const orchestrations = await prisma.orchestration.count();
    console.log(`\n🎭 Orchestrations: ${orchestrations}`);

    if (orchestrations > 0) {
      const firstOrch = await prisma.orchestration.findFirst({
        include: {
          orchestrator: true,
          participants: true
        }
      });

      console.log(`  Sample orchestration: ${firstOrch.name}`);
      console.log(`  Orchestrator: ${firstOrch.orchestrator.name}`);
      console.log(`  Participants: ${firstOrch.participants.length} agents`);
    }

    console.log('\n✨ Agent migration test complete!');

  } catch (error) {
    console.error('❌ Test failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

testAgents();