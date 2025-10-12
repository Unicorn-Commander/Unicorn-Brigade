#!/bin/bash

API_BASE="http://localhost:8112/api"
FRONTEND_BASE="http://localhost:8113"

echo "🧪 Unicorn Brigade - Agent Builder System Tests"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_count=0
pass_count=0
fail_count=0

function run_test() {
    test_count=$((test_count + 1))
    test_name=$1
    command=$2

    echo -n "Test $test_count: $test_name... "

    response=$(eval $command 2>&1)
    status=$?

    if [ $status -eq 0 ] && [[ ! $response =~ "error" ]] && [[ ! $response =~ "Error" ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "   Response: $response"
        fail_count=$((fail_count + 1))
        return 1
    fi
}

echo "🔍 Testing Backend Services..."
echo ""

# Test 1: Health Check
run_test "Health check" "curl -s $API_BASE/../health | grep operational"

# Test 2: Agent Builder Info
run_test "Agent builder service info" "curl -s $API_BASE/agent-builder/info | grep 'Agent Builder Service'"

# Test 3: The General Status
run_test "The General status" "curl -s $API_BASE/agent-builder/info | grep -i general"

# Test 4: List Agents
run_test "List agents endpoint" "curl -s $API_BASE/agents-new | grep agents"

# Test 5: Get Domains
run_test "Get domains endpoint" "curl -s $API_BASE/agents-new/domains | grep domains"

echo ""
echo "🤖 Testing Agent Creation..."
echo ""

# Create a test agent
TEST_AGENT_DATA='{
  "name": "Test Agent",
  "displayName": "Test Agent",
  "title": "Test Specialist",
  "domain": "testing",
  "rank": "Private",
  "bio": "A test agent for system validation",
  "systemPrompt": "You are a test agent.",
  "model": "gpt-4-turbo",
  "temperature": 0.7,
  "maxTokens": 2048,
  "status": "draft",
  "capabilities": ["testing", "validation"]
}'

# Test 6: Create Agent
echo -n "Test $((test_count + 1)): Create test agent... "
test_count=$((test_count + 1))

create_response=$(curl -s -X POST "$API_BASE/agents-new" \
  -H "Content-Type: application/json" \
  -d "$TEST_AGENT_DATA")

if [[ $create_response =~ "id" ]] && [[ $create_response =~ "Test Agent" ]]; then
    echo -e "${GREEN}✓ PASS${NC}"
    pass_count=$((pass_count + 1))

    # Extract agent ID for further tests
    TEST_AGENT_ID=$(echo $create_response | grep -o '"id":"[^"]*' | cut -d'"' -f4)
    echo "   Created agent ID: $TEST_AGENT_ID"

    # Test 7: Get Agent Details
    run_test "Get agent details" "curl -s $API_BASE/agents-new/$TEST_AGENT_ID | grep 'Test Agent'"

    # Test 8: Get Agent Card (A2A Protocol)
    run_test "Get A2A agent card" "curl -s $API_BASE/agents-new/$TEST_AGENT_ID/card | grep protocol"

    # Test 9: Update Agent
    echo -n "Test $((test_count + 1)): Update agent... "
    test_count=$((test_count + 1))

    update_response=$(curl -s -X PUT "$API_BASE/agents-new/$TEST_AGENT_ID" \
      -H "Content-Type: application/json" \
      -d '{"bio": "Updated bio for testing"}')

    if [[ $update_response =~ "Updated bio" ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}✗ FAIL${NC}"
        fail_count=$((fail_count + 1))
    fi

    # Test 10: Delete Agent
    echo -n "Test $((test_count + 1)): Delete agent... "
    test_count=$((test_count + 1))

    delete_status=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$API_BASE/agents-new/$TEST_AGENT_ID")

    if [ "$delete_status" = "204" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}✗ FAIL${NC}"
        echo "   HTTP Status: $delete_status"
        fail_count=$((fail_count + 1))
    fi
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "   Response: $create_response"
    fail_count=$((fail_count + 1))
fi

echo ""
echo "🌐 Testing Frontend Availability..."
echo ""

# Test Frontend Routes
run_test "Frontend home page" "curl -s -o /dev/null -w '%{http_code}' $FRONTEND_BASE | grep -E '200|304'"
run_test "Agent builder chat page" "curl -s -o /dev/null -w '%{http_code}' $FRONTEND_BASE/builder-chat | grep -E '200|304'"
run_test "Agent library page" "curl -s -o /dev/null -w '%{http_code}' $FRONTEND_BASE/library | grep -E '200|304'"

echo ""
echo "================================================"
echo "📊 Test Results"
echo "================================================"
echo -e "Total Tests:  $test_count"
echo -e "Passed:       ${GREEN}$pass_count${NC}"
echo -e "Failed:       ${RED}$fail_count${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "🚀 System is ready to use!"
    echo ""
    echo "Access the application:"
    echo "  • The General Chat: $FRONTEND_BASE/builder-chat"
    echo "  • Agent Library:    $FRONTEND_BASE/library"
    echo "  • API Docs:         See AGENT_BUILDER_SETUP.md"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Ensure backend is running: npm run dev"
    echo "  2. Ensure frontend is running: cd frontend && npm run dev"
    echo "  3. Check logs for errors"
    echo "  4. Verify database migrations: npm run migrate"
    echo "  5. Check .env configuration"
    exit 1
fi
