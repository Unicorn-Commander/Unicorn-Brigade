#!/bin/bash
# MCP Server Registry Test Script
# Tests high-value MCP servers to verify the MCPClient refactor

API_BASE="http://localhost:8100/api/v1/mcp/registry"
RESULTS_FILE="mcp_test_results.json"

echo "{"
echo '  "test_start": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",'
echo '  "servers_tested": ['

# Array of servers to test
SERVERS=(
    "github:Baseline"
    "slack:Baseline"
    "postgres:Baseline"
    "playwright:Baseline"
    "brave-search:Baseline"
    "memory:Baseline"
    "fetch:Baseline"
    "stripe:Phase1"
    "linear:Phase1"
    "airtable:Phase2"
    "vercel:Phase2"
)

FIRST=true

for SERVER_INFO in "${SERVERS[@]}"; do
    IFS=: read -r SERVER CATEGORY <<< "$SERVER_INFO"

    # Add comma separator
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        echo "    ,"
    fi

    echo "    {"
    echo "      \"server\": \"$SERVER\","
    echo "      \"category\": \"$CATEGORY\","

    # Start timer
    START_TIME=$(date +%s)

    # Start the server
    echo "      \"startup\": {" >&2
    echo "Testing $SERVER ($CATEGORY)..." >&2

    START_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/servers/$SERVER/start" 2>&1)
    HTTP_CODE=$(echo "$START_RESPONSE" | tail -n1)
    START_BODY=$(echo "$START_RESPONSE" | head -n-1)

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo "        \"status_code\": $HTTP_CODE,"
    echo "        \"duration_seconds\": $DURATION,"

    if [ "$HTTP_CODE" = "200" ]; then
        echo "        \"success\": true"
        echo "      },"

        # Wait a moment for server to initialize
        sleep 2

        # Get server details
        DETAILS=$(curl -s "$API_BASE/servers/$SERVER")

        echo "      \"details\": $DETAILS"

        echo "✓ $SERVER started successfully in ${DURATION}s" >&2
    else
        echo "        \"success\": false,"
        echo "        \"error\": $(echo "$START_BODY" | jq -Rs .)"
        echo "      },"
        echo "      \"details\": null"

        echo "✗ $SERVER failed: HTTP $HTTP_CODE" >&2
    fi

    echo -n "    }"
done

echo ""
echo "  ],"
echo '  "test_end": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"'
echo "}"
