#!/bin/bash
# Multi-Agent Workflow Tests for Unicorn Brigade
# Tests collaboration, tool usage, and real problem solving

API_URL="${API_URL:-http://localhost:8100/api/v1}"
AUTH_HEADER="${AUTH_HEADER:-}"

# Helper function for API calls
api_call() {
    local method="$1"
    local endpoint="$2"
    local data="$3"

    if [ -n "$AUTH_HEADER" ]; then
        curl -s -X "$method" "${API_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $AUTH_HEADER" \
            -d "$data"
    else
        curl -s -X "$method" "${API_URL}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "$data"
    fi
}

echo "=========================================="
echo "  UNICORN BRIGADE MULTI-AGENT WORKFLOWS"
echo "=========================================="
echo ""

# ============================================
# WORKFLOW 1: Competitive Intelligence Report
# Agents: Maven (research) → Newton (analysis) → Sterling (email)
# Tools: web_search, calculator, json, email
# ============================================

run_workflow_1() {
    echo "=== WORKFLOW 1: Competitive Intelligence Report ==="
    echo "Chain: LtCol Maven → LtCol Newton → LtCol Sterling"
    echo "Tools: web_search, calculator, json, email"
    echo ""

    # Step 1: Maven researches the market
    echo "[Step 1] LtCol Maven researching AI agent platforms..."
    MAVEN_RESULT=$(api_call POST "/agents/col-market/chat" '{
        "message": "Research the top 3 AI agent platforms in 2026 (CrewAI, AutoGen, LangGraph). For each, find their key differentiators and any public pricing. Use web_search.",
        "stream": false
    }')

    MAVEN_CONTENT=$(echo "$MAVEN_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:600])" 2>/dev/null)
    MAVEN_TOOLS=$(echo "$MAVEN_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r.get('toolCalls',[])))" 2>/dev/null)

    echo "Maven found:"
    echo "$MAVEN_CONTENT"
    echo ""
    echo "Tools used: $MAVEN_TOOLS"
    echo ""

    # Step 2: Newton analyzes the data
    echo "[Step 2] LtCol Newton analyzing competitive data..."
    NEWTON_RESULT=$(api_call POST "/agents/maj-data/chat" "{
        \"message\": \"Based on this market research, calculate a competitive score (1-10) for each platform and rank them: $MAVEN_CONTENT\",
        \"stream\": false
    }")

    NEWTON_CONTENT=$(echo "$NEWTON_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    echo "Newton's analysis:"
    echo "$NEWTON_CONTENT"
    echo ""

    # Step 3: Sterling compiles and could send email
    echo "[Step 3] LtCol Sterling compiling executive summary..."
    STERLING_RESULT=$(api_call POST "/agents/col-finance/chat" "{
        \"message\": \"Create a brief executive summary of this competitive analysis. Keep it to 3 bullet points: $NEWTON_CONTENT\",
        \"stream\": false
    }")

    STERLING_CONTENT=$(echo "$STERLING_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content',''))" 2>/dev/null)
    echo "Sterling's executive summary:"
    echo "$STERLING_CONTENT"
    echo ""

    echo "✅ Workflow 1 Complete!"
    echo ""
}

# ============================================
# WORKFLOW 2: Tech Due Diligence
# Agents: Cipher (security) → Stack (architecture) → Pipeline (deployment)
# Tools: web_search, http_request, shell, json
# ============================================

run_workflow_2() {
    echo "=== WORKFLOW 2: Tech Due Diligence ==="
    echo "Chain: LtCol Cipher → LtCol Stack → LtCol Pipeline"
    echo "Tools: web_search, http_request, shell, json"
    echo ""

    # Step 1: Cipher assesses security
    echo "[Step 1] LtCol Cipher assessing technology security..."
    CIPHER_RESULT=$(api_call POST "/agents/sgt-cyber/chat" '{
        "message": "Search for the latest security best practices for Python FastAPI applications in 2026. What are the top 3 OWASP risks to address?",
        "stream": false
    }')

    CIPHER_CONTENT=$(echo "$CIPHER_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    echo "Cipher's security assessment:"
    echo "$CIPHER_CONTENT"
    echo ""

    # Step 2: Stack reviews architecture
    echo "[Step 2] LtCol Stack reviewing architecture..."
    STACK_RESULT=$(api_call POST "/agents/cpt-fullstack/chat" "{
        \"message\": \"Based on these security concerns, what architectural patterns should we use? Keep it to 3 recommendations: $CIPHER_CONTENT\",
        \"stream\": false
    }")

    STACK_CONTENT=$(echo "$STACK_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    echo "Stack's architecture review:"
    echo "$STACK_CONTENT"
    echo ""

    # Step 3: Pipeline assesses deployment
    echo "[Step 3] LtCol Pipeline assessing deployment..."
    PIPELINE_RESULT=$(api_call POST "/agents/sgt-devops/chat" "{
        \"message\": \"Given this architecture, what Docker/Kubernetes deployment strategy would you recommend? Be specific.\",
        \"stream\": false
    }")

    PIPELINE_CONTENT=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    echo "Pipeline's deployment strategy:"
    echo "$PIPELINE_CONTENT"
    echo ""

    echo "✅ Workflow 2 Complete!"
    echo ""
}

# ============================================
# WORKFLOW 3: Investment Research Pipeline
# Agents: Maven → Sterling → Blackstone → The General (synthesis)
# Tools: web_search, calculator, memory, json
# ============================================

run_workflow_3() {
    echo "=== WORKFLOW 3: Investment Research Pipeline ==="
    echo "Chain: Maven → Sterling → Blackstone → The General"
    echo "Tools: web_search, calculator, memory, json"
    echo ""

    TARGET_COMPANY="${1:-Anthropic}"

    # Step 1: Maven researches company
    echo "[Step 1] LtCol Maven researching $TARGET_COMPANY..."
    MAVEN_RESULT=$(api_call POST "/agents/col-market/chat" "{
        \"message\": \"Research $TARGET_COMPANY - their latest products, recent news, and market position. Use web_search.\",
        \"stream\": false
    }")

    MAVEN_CONTENT=$(echo "$MAVEN_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:600])" 2>/dev/null)
    echo "Maven's research:"
    echo "$MAVEN_CONTENT"
    echo ""

    # Step 2: Sterling analyzes financials
    echo "[Step 2] LtCol Sterling analyzing financials..."
    STERLING_RESULT=$(api_call POST "/agents/col-finance/chat" "{
        \"message\": \"Based on this research, provide a financial analysis. What is their estimated valuation and revenue model? $MAVEN_CONTENT\",
        \"stream\": false
    }")

    STERLING_CONTENT=$(echo "$STERLING_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    echo "Sterling's financial analysis:"
    echo "$STERLING_CONTENT"
    echo ""

    # Step 3: Blackstone checks legal
    echo "[Step 3] LtCol Blackstone reviewing legal/regulatory..."
    BLACKSTONE_RESULT=$(api_call POST "/agents/col-legal/chat" "{
        \"message\": \"What are the key regulatory considerations for investing in an AI company like this? Be brief.\",
        \"stream\": false
    }")

    BLACKSTONE_CONTENT=$(echo "$BLACKSTONE_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:400])" 2>/dev/null)
    echo "Blackstone's legal review:"
    echo "$BLACKSTONE_CONTENT"
    echo ""

    # Step 4: The General synthesizes
    echo "[Step 4] The General synthesizing final recommendation..."
    GENERAL_RESULT=$(api_call POST "/agents/the-general/chat" "{
        \"message\": \"As commanding officer, synthesize these reports into a single investment recommendation (BUY/HOLD/PASS) with 2-3 reasons:

        Market Research: $MAVEN_CONTENT

        Financial Analysis: $STERLING_CONTENT

        Legal Review: $BLACKSTONE_CONTENT\",
        \"stream\": false
    }")

    GENERAL_CONTENT=$(echo "$GENERAL_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content',''))" 2>/dev/null)
    echo "The General's final recommendation:"
    echo "$GENERAL_CONTENT"
    echo ""

    echo "✅ Workflow 3 Complete!"
    echo ""
}

# ============================================
# WORKFLOW 4: Lead Qualification (Your Business!)
# Agents: Holmes → Crawler → Sterling → Email
# Tools: web_search, http_request, calculator, email
# ============================================

run_workflow_4() {
    echo "=== WORKFLOW 4: Lead Qualification Pipeline ==="
    echo "Chain: Holmes (investigate) → Crawler (scrape) → Sterling (score)"
    echo "Tools: web_search, http_request, calculator"
    echo ""

    COMPANY="${1:-Gusto}"

    # Step 1: Holmes investigates
    echo "[Step 1] LtCol Holmes investigating $COMPANY..."
    HOLMES_RESULT=$(api_call POST "/agents/col-investigation/chat" "{
        \"message\": \"Investigate $COMPANY as a potential sales lead. Find: company size, industry, and whether they have a 401k program. Use web_search.\",
        \"stream\": false
    }")

    HOLMES_CONTENT=$(echo "$HOLMES_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:500])" 2>/dev/null)
    HOLMES_TOOLS=$(echo "$HOLMES_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print([t.get('name') for t in r.get('toolCalls',[])])" 2>/dev/null)
    echo "Holmes found:"
    echo "$HOLMES_CONTENT"
    echo "Tools used: $HOLMES_TOOLS"
    echo ""

    # Step 2: Crawler gets more details
    echo "[Step 2] LtCol Crawler gathering additional intel..."
    CRAWLER_RESULT=$(api_call POST "/agents/col-webscrape/chat" "{
        \"message\": \"Based on this lead research, what is the company's annual revenue range and employee count if available? $HOLMES_CONTENT\",
        \"stream\": false
    }")

    CRAWLER_CONTENT=$(echo "$CRAWLER_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content','')[:400])" 2>/dev/null)
    echo "Crawler found:"
    echo "$CRAWLER_CONTENT"
    echo ""

    # Step 3: Sterling scores the lead
    echo "[Step 3] LtCol Sterling scoring lead quality..."
    STERLING_RESULT=$(api_call POST "/agents/col-finance/chat" "{
        \"message\": \"Score this sales lead from 1-100 based on these factors. Consider company size, industry fit, and retirement plan status. Provide the score and 2 reasons:

        Investigation: $HOLMES_CONTENT

        Company Intel: $CRAWLER_CONTENT\",
        \"stream\": false
    }")

    STERLING_CONTENT=$(echo "$STERLING_RESULT" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('content',''))" 2>/dev/null)
    echo "Sterling's lead score:"
    echo "$STERLING_CONTENT"
    echo ""

    echo "✅ Workflow 4 Complete!"
    echo ""
}

# Main execution
case "${1:-all}" in
    1|competitive)
        run_workflow_1
        ;;
    2|tech)
        run_workflow_2
        ;;
    3|investment)
        run_workflow_3 "${2:-Anthropic}"
        ;;
    4|lead)
        run_workflow_4 "${2:-Gusto}"
        ;;
    all)
        echo "Running all workflows..."
        echo ""
        run_workflow_1
        run_workflow_2
        run_workflow_3 "Anthropic"
        run_workflow_4 "Gusto"
        ;;
    *)
        echo "Usage: $0 [1|2|3|4|all] [optional_target]"
        echo ""
        echo "Workflows:"
        echo "  1 | competitive  - Competitive Intelligence Report"
        echo "  2 | tech         - Tech Due Diligence"
        echo "  3 | investment   - Investment Research (target: company name)"
        echo "  4 | lead         - Lead Qualification (target: company name)"
        echo "  all              - Run all workflows"
        ;;
esac
