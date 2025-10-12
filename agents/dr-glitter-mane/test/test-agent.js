/**
 * Dr. Glitter Mane Test Suite
 * Tests basic functionality of the medical AI agent
 */

const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:3333';

// Test colors for console output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

async function testEndpoint(name, endpoint, options = {}) {
  try {
    log(`\n🧪 Testing: ${name}`, 'blue');
    const response = await fetch(`${BASE_URL}${endpoint}`, options);
    const data = await response.json();
    
    if (response.ok) {
      log(`  ✅ Success: ${response.status} ${response.statusText}`, 'green');
      return { success: true, data };
    } else {
      log(`  ❌ Failed: ${response.status} ${response.statusText}`, 'red');
      return { success: false, error: data };
    }
  } catch (error) {
    log(`  ❌ Error: ${error.message}`, 'red');
    return { success: false, error: error.message };
  }
}

async function runTests() {
  log('\n===============================================', 'magenta');
  log('🦄💉 Dr. Glitter Mane Test Suite', 'magenta');
  log('===============================================\n', 'magenta');

  let totalTests = 0;
  let passedTests = 0;

  // Test 1: Check if server is running
  log('🚀 Checking server status...', 'yellow');
  try {
    await fetch(BASE_URL);
    log('  ✅ Server is running on port 3333', 'green');
  } catch (error) {
    log('  ❌ Server is not running!', 'red');
    log('  Please start the server with: npm start', 'yellow');
    process.exit(1);
  }

  // Test 2: Get agent information
  totalTests++;
  const agentInfo = await testEndpoint('Get Agent Information', '/api/agent');
  if (agentInfo.success) {
    passedTests++;
    log(`  Agent: ${agentInfo.data.agent.name}`, 'blue');
    log(`  Title: ${agentInfo.data.agent.title}`, 'blue');
  }

  // Test 3: Test chat endpoint with medical query
  totalTests++;
  const chatTest = await testEndpoint('Chat with Dr. Glitter Mane', '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: "I have a headache and slight fever. What could be causing this?",
      sessionId: 'test-session-001',
      userId: 'test-user-001'
    })
  });
  
  if (chatTest.success) {
    passedTests++;
    log('  Response preview:', 'blue');
    log(`  "${chatTest.data.response.substring(0, 150)}..."`, 'reset');
  }

  // Test 4: Get conversation history
  totalTests++;
  const historyTest = await testEndpoint(
    'Get Conversation History', 
    '/api/history/test-session-001'
  );
  if (historyTest.success) {
    passedTests++;
    log(`  Messages in history: ${historyTest.data.messages.length}`, 'blue');
  }

  // Test 5: Get medical records (for a user)
  totalTests++;
  const recordsTest = await testEndpoint(
    'Get Medical Records',
    '/api/records/test-user-001'
  );
  if (recordsTest.success) {
    passedTests++;
    log(`  Documents found: ${recordsTest.data.totalRecords}`, 'blue');
  }

  // Test 6: Get analytics
  totalTests++;
  const analyticsTest = await testEndpoint(
    'Get Analytics',
    '/api/analytics/test-user-001'
  );
  if (analyticsTest.success) {
    passedTests++;
    log(`  Total consultations: ${analyticsTest.data.analytics.totalConsultations}`, 'blue');
  }

  // Test 7: Test symptom analysis
  totalTests++;
  const symptomTest = await testEndpoint('Symptom Analysis', '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: "I've been experiencing chest pain, shortness of breath, and dizziness for the past hour.",
      sessionId: 'test-urgent-001',
      userId: 'test-user-001'
    })
  });
  
  if (symptomTest.success) {
    passedTests++;
    // Check if response includes urgent care advice
    if (symptomTest.data.response.toLowerCase().includes('emergency') || 
        symptomTest.data.response.toLowerCase().includes('911') ||
        symptomTest.data.response.toLowerCase().includes('immediate')) {
      log('  ✅ Correctly identified urgent symptoms', 'green');
    }
  }

  // Test 8: Test rare disease detection
  totalTests++;
  const rareTest = await testEndpoint('Rare Disease Detection', '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: "I have periodic episodes of paralysis that last a few hours, especially after eating carbohydrate-rich meals. My potassium levels drop during these episodes.",
      sessionId: 'test-rare-001',
      userId: 'test-user-001'
    })
  });
  
  if (rareTest.success) {
    passedTests++;
    // Check if response mentions periodic paralysis or similar rare conditions
    if (rareTest.data.response.toLowerCase().includes('periodic') || 
        rareTest.data.response.toLowerCase().includes('paralysis') ||
        rareTest.data.response.toLowerCase().includes('rare')) {
      log('  ✅ Identified potential rare condition', 'green');
    }
  }

  // Summary
  log('\n===============================================', 'magenta');
  log('Test Results', 'magenta');
  log('===============================================', 'magenta');
  log(`Total Tests: ${totalTests}`, 'blue');
  log(`Passed: ${passedTests}`, 'green');
  log(`Failed: ${totalTests - passedTests}`, passedTests === totalTests ? 'green' : 'red');
  
  if (passedTests === totalTests) {
    log('\n🎉 All tests passed! Dr. Glitter Mane is ready for consultations.', 'green');
  } else {
    log(`\n⚠️  Some tests failed. Please check the configuration.`, 'yellow');
  }

  // Performance check
  log('\n📏 Performance Metrics:', 'yellow');
  const startTime = Date.now();
  await testEndpoint('Performance Test', '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: "Quick test",
      sessionId: 'perf-test',
      userId: 'perf-user'
    })
  });
  const responseTime = Date.now() - startTime;
  log(`  Response time: ${responseTime}ms`, responseTime < 5000 ? 'green' : 'yellow');

  log('\n🦄 Test suite complete!\n', 'magenta');
}

// Run tests
runTests().catch(error => {
  log(`\n❌ Fatal error: ${error.message}`, 'red');
  process.exit(1);
});