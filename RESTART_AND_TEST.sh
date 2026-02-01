#!/bin/bash
# Quick script to restart API server and test the workflow fix

set -e

echo "========================================="
echo "Workflow Fix - Restart and Test"
echo "========================================="
echo ""

# Step 1: Stop current server
echo "1. Stopping current API server..."
pkill -f "uvicorn app.main:app" || echo "   (No server was running)"
sleep 2

# Step 2: Start server with fixes
echo ""
echo "2. Starting API server with fixes loaded..."
cd "$(dirname "$0")"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload > /tmp/brigade-api.log 2>&1 &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"

# Wait for server to be ready
echo "   Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:8100/api/v1/health > /dev/null; then
    echo "   ✅ Server is running and healthy"
else
    echo "   ❌ Server failed to start. Check /tmp/brigade-api.log"
    exit 1
fi

# Step 3: Run automated tests
echo ""
echo "3. Running automated tests..."
echo ""
python3 test_workflow_fix.py
TEST_RESULT=$?

# Step 4: Show server logs
echo ""
echo "4. Recent server logs:"
echo "----------------------------------------"
tail -30 /tmp/brigade-api.log

# Summary
echo ""
echo "========================================="
echo "Summary"
echo "========================================="
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    echo ""
    echo "Server is ready. You can now:"
    echo "1. Access API at: http://localhost:8100"
    echo "2. View docs at: http://localhost:8100/docs"
    echo "3. Execute workflows via API"
    echo ""
    echo "Example workflow execution:"
    echo "  curl -X POST http://localhost:8100/api/v1/hierarchical/execute \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{
      \"workflow_id\": \"help-desk-triage\",
      \"inputs\": {
        \"ticket_id\": \"TEST-001\",
        \"customer\": \"Test User\",
        \"issue\": \"Cannot access dashboard\",
        \"priority\": \"medium\"
      }
    }'"
else
    echo "❌ TESTS FAILED"
    echo ""
    echo "Check logs for details:"
    echo "  tail -f /tmp/brigade-api.log"
fi

echo ""
echo "Server logs: /tmp/brigade-api.log"
echo "Server PID: $SERVER_PID"
echo ""

exit $TEST_RESULT
