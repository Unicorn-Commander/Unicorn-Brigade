#!/bin/bash
# Demo: Creating an Agent with The General

BASE_URL="http://localhost:8112/api/agent-builder"
SESSION_ID="demo-$(date +%s)"

echo "════════════════════════════════════════════════"
echo "🦄 UNICORN BRIGADE - AGENT CREATION DEMO"
echo "════════════════════════════════════════════════"
echo ""

# Step 1: Initial Request
echo "Step 1: Requesting a medical triage agent..."
echo ""

RESPONSE_1=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"I need to build a medical triage agent for emergency rooms. It should assess patient urgency and route them appropriately.\",
    \"sessionId\": \"$SESSION_ID\"
  }")

echo "The General responds:"
echo "$RESPONSE_1" | jq -r '.message' | head -c 800
echo ""
echo "..."
echo ""

# Step 2: Provide specifications
echo "Step 2: Providing detailed specifications..."
echo ""

RESPONSE_2=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"It's for emergency rooms. Primary tasks: symptom assessment, urgency determination (immediate, urgent, standard), patient routing. Target audience is ER nurses and intake staff. Should be professional but compassionate tone.\",
    \"sessionId\": \"$SESSION_ID\"
  }")

echo "The General responds:"
echo "$RESPONSE_2" | jq -r '.message' | head -c 800
echo ""
echo "..."
echo ""

# Step 3: Approve creation
echo "Step 3: Reviewing and approving the design..."
echo ""

RESPONSE_3=$(curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"This looks perfect! Please proceed with creating the agent. Use GPT-4 for the model.\",
    \"sessionId\": \"$SESSION_ID\"
  }")

echo "The General responds:"
echo "$RESPONSE_3" | jq -r '.message'
echo ""

# Check if agent was created
if echo "$RESPONSE_3" | jq -e '.agentCreated' > /dev/null 2>&1; then
  AGENT_ID=$(echo "$RESPONSE_3" | jq -r '.agentId')
  echo ""
  echo "✅ Agent Created Successfully!"
  echo "   Agent ID: $AGENT_ID"
  echo ""
  echo "View the agent:"
  echo "  http://localhost:8113/agent/$AGENT_ID"
  echo ""
fi

echo "════════════════════════════════════════════════"
echo "🎯 TRY IT YOURSELF"
echo "════════════════════════════════════════════════"
echo ""
echo "Open the chat interface:"
echo "  http://localhost:8113/builder-chat"
echo ""
echo "Or use the API:"
echo "  curl -X POST $BASE_URL/chat \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"message\": \"Your request here\", \"sessionId\": \"your-session\"}'"
echo ""
echo "════════════════════════════════════════════════"
