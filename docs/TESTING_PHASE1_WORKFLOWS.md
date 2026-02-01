# Testing Guide: Phase 1 Workflows
## Help Desk Triage & RFP Response Generation

---

## Prerequisites

1. **Backend Running**:
   ```bash
   cd /Volumes/Studio\ Storage/Development/Unicorn-Brigade
   source venv/bin/activate
   uvicorn app.main:app --reload --port 8100
   ```

2. **Database Initialized**:
   ```bash
   # Workflows are defined in code, no DB migration needed
   # But ensure PostgreSQL is running
   docker-compose up -d postgres
   ```

---

## Test 1: Help Desk Triage & Resolution

### Scenario A: High Confidence KB Match (Auto-Resolution Path)

**Test Case**: Common authentication issue with known solution

```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "help-desk-triage",
    "inputs": {
      "ticket_id": "DESK-12345",
      "ticket_description": "User cannot login to application. Error message: 'Invalid credentials' even after resetting password. Chrome browser, Windows 10.",
      "user_email": "john.smith@acme.com",
      "priority": "high",
      "category": "authentication"
    },
    "async_execution": false
  }'
```

**Expected Flow**:
1. ✅ Step 1: Analyze Ticket → Identifies auth issue, high urgency
2. ✅ Step 2: Search Knowledge Base → Finds KB article with 0.85 confidence
3. ✅ Step 3: Attempt Resolution → Generates resolution (browser cache clear)
4. ⏭️ Step 4: Check System Logs → **SKIPPED** (confidence >= 0.6)
5. ✅ Step 5: Escalation Decision → Decides auto-resolve (confidence 0.85)
6. ✅ Step 6: Generate Response → Drafts user-friendly resolution
7. 🛑 **CHECKPOINT**: Verify Auto-Resolution (GATE) → **PASS** (confidence >= 0.75)
8. 🛑 **CHECKPOINT**: Approve Response → **HUMAN** required

**Expected Result**:
```json
{
  "state": "waiting_checkpoint",
  "current_step": "generate-response",
  "pending_checkpoint": "approve-response",
  "outputs": {
    "analyze-ticket": {
      "issue_summary": "Login failure after password reset",
      "urgency_level": "high",
      "ticket_complexity": "low"
    },
    "search-knowledge-base": {
      "confidence_score": 0.85,
      "solution_steps": ["Clear browser cache", "Try incognito mode"]
    },
    "attempt-resolution": {
      "resolution_confidence": 0.85
    }
  }
}
```

---

### Scenario B: Low Confidence KB Match (System Logs Path)

**Test Case**: Unusual error requiring log analysis

```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "help-desk-triage",
    "inputs": {
      "ticket_id": "DESK-67890",
      "ticket_description": "API calls returning 503 errors intermittently. Started 2 hours ago. Affects multiple customers in EU region.",
      "user_email": "ops-team@acme.com",
      "priority": "critical",
      "category": "system_outage"
    },
    "async_execution": false
  }'
```

**Expected Flow**:
1. ✅ Step 1: Analyze Ticket → Identifies system outage, critical priority
2. ✅ Step 2: Search Knowledge Base → Low confidence (0.45) - no exact match
3. ⏭️ Step 3: Attempt Resolution → **SKIPPED** (confidence < 0.6)
4. ✅ Step 4: Check System Logs → Analyzes logs, finds connection pool exhaustion
5. ✅ Step 5: Escalation Decision → Escalates to L2 (critical + no KB match)
6. ✅ Step 6: Generate Response → Drafts escalation notice
7. 🛑 **CHECKPOINT**: Verify Auto-Resolution (GATE) → **N/A** (resolution skipped)
8. 🛑 **CHECKPOINT**: Approve Response → **HUMAN** required

**Expected Result**: Escalation to human engineer with log analysis

---

## Test 2: RFP Response Generation

### Scenario: Mid-Size Enterprise RFP

**Test Case**: Cloud infrastructure RFP from mid-market customer

```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "rfp-response",
    "inputs": {
      "rfp_document": "RFP for Cloud Infrastructure Services\n\nClient: Acme Manufacturing Corp\nProject: Migrate 200-user on-premise infrastructure to cloud\n\nRequirements:\n1. High availability (99.9% uptime SLA)\n2. Data residency in US\n3. SOC2 Type II compliance\n4. Migration support and training\n5. 24/7 support\n6. Cost breakdown for 1, 2, 3 year contracts\n\nEvaluation Criteria:\n- Technical capability (40%)\n- Cost (30%)\n- Experience (20%)\n- Support (10%)\n\nSubmission Deadline: March 15, 2026\nDecision Date: April 1, 2026",
      "client_name": "Acme Manufacturing Corp",
      "deadline": "2026-03-15",
      "target_price_range": "$150K-$200K per year"
    },
    "async_execution": false
  }'
```

**Expected Flow**:
1. ✅ Step 1: Extract Requirements → Parses RFP, identifies 6 requirements, 4 criteria
2. 🛑 **CHECKPOINT**: Review Requirements → **HUMAN** can add missing items
   - Response: `{"action": "approve", "additional_requirements": []}`
3. ✅ Step 2: Retrieve Past Proposals → Finds 3 similar cloud migration proposals
4. ✅ Step 3: Draft Technical Response → Addresses each requirement with evidence
5. ✅ Step 4: Generate Pricing → Creates tiered pricing ($175K, $165K, $155K for 1/2/3yr)
6. 🛑 **CHECKPOINT**: Approve Pricing → **HUMAN** approval required
   - Response: `{"action": "approve", "pricing_adjustments": {}}`
7. ✅ Step 5: Draft Executive Summary → Highlights differentiation, case studies
8. ✅ Step 6: Compliance Review → Checks all mandatory sections present
9. 🛑 **CHECKPOINT**: Compliance Gate → **GATE** (auto-check for missing sections)
   - Expected: **PASS** (all sections present)
10. ✅ Step 7: Compile Document → Assembles final proposal with formatting
11. 🛑 **CHECKPOINT**: Final Approval → **HUMAN** executive review
    - Response: `{"action": "approve_for_submission"}`

**Expected Result**:
```json
{
  "state": "completed",
  "outputs": {
    "extract-requirements": {
      "requirements_list": ["99.9% uptime SLA", "US data residency", "SOC2", "Migration support", "24/7 support", "Multi-year pricing"],
      "evaluation_criteria": {"technical": 0.4, "cost": 0.3, "experience": 0.2, "support": 0.1},
      "mandatory_sections": ["technical_response", "pricing", "experience", "support_plan"],
      "submission_deadline": "2026-03-15"
    },
    "generate-pricing": {
      "total_cost": "$175,000/year",
      "pricing_breakdown": {
        "1_year": "$175,000",
        "2_year": "$165,000/year",
        "3_year": "$155,000/year"
      }
    },
    "compile-document": {
      "rfp_response_document": "...",
      "table_of_contents": ["Executive Summary", "Technical Response", "Pricing", "Case Studies", "Support Plan"]
    }
  },
  "total_cost": 2.35,
  "total_tokens": 15420
}
```

---

## Responding to Checkpoints

### Get Pending Checkpoint

```bash
curl -X GET http://localhost:8100/api/v1/hierarchical/executions/{execution_id}
```

Response will show `"state": "waiting_checkpoint"` and `"pending_checkpoint": "checkpoint-id"`

### Respond to Checkpoint

```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/executions/{execution_id}/checkpoint \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": "approve-response",
    "response": {
      "action": "Send Response",
      "modifications": {}
    }
  }'
```

**Checkpoint Response Options**:

Help Desk - `approve-response`:
- `"Send Response"`
- `"Edit Response"` (provide modifications)
- `"Escalate to L2"`
- `"Request More Info"`

RFP - `review-requirements`:
- `"Approve Requirements"`
- `"Add Requirements"` (provide additional_requirements)

RFP - `approve-pricing`:
- `"Approve Pricing"`
- `"Adjust Pricing"` (provide pricing_adjustments)

RFP - `final-approval`:
- `"Approve for Submission"`
- `"Request Revisions"` (provide revision_notes)

---

## Monitoring Execution

### List All Executions

```bash
curl -X GET http://localhost:8100/api/v1/hierarchical/executions
```

### Get Specific Execution

```bash
curl -X GET http://localhost:8100/api/v1/hierarchical/executions/{execution_id}
```

### Filter by Workflow

```bash
curl -X GET "http://localhost:8100/api/v1/hierarchical/executions?workflow_id=help-desk-triage&state=completed"
```

---

## Expected Performance Metrics

### Help Desk Triage

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Total Time** | 3-8 minutes | From ticket submission to response ready |
| **KB Search** | < 2 minutes | Step 2 completion |
| **Auto-Resolution Rate** | 40-50% | Percentage of tickets resolved without escalation |
| **Gate Pass Rate** | 60-70% | Percentage passing resolution_confidence >= 0.75 |

### RFP Response

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Total Time** | 45-90 minutes | From RFP upload to final document |
| **Requirements Extraction** | < 5 minutes | Step 1 completion |
| **Compliance Pass Rate** | 95%+ | Percentage passing compliance gate |
| **Time Savings vs Manual** | 70% | Reduction from typical 5-8 hour manual process |

---

## Troubleshooting

### Common Issues

**Issue**: Workflow stuck in "waiting_checkpoint"
- **Cause**: Checkpoint not responded to
- **Fix**: Submit checkpoint response via `/checkpoint` endpoint

**Issue**: Step execution timeout
- **Cause**: LLM taking too long (complex RFP, large document)
- **Fix**: Increase `timeout_seconds` in workflow definition or use `async_execution: true`

**Issue**: Low confidence scores in Help Desk
- **Cause**: Knowledge base empty or ticket unlike past issues
- **Fix**: This is expected for novel issues - workflow will route to system logs

**Issue**: Compliance gate failing in RFP
- **Cause**: Missing mandatory sections from RFP requirements
- **Fix**: Human review at `review-requirements` checkpoint to ensure all sections identified

---

## Success Criteria

### Help Desk Triage
✅ Auto-resolves 40%+ of test tickets
✅ Correctly escalates critical issues
✅ Response quality acceptable to human reviewer
✅ Completes in < 10 minutes

### RFP Response
✅ Extracts all requirements from test RFPs
✅ Generates compliant proposal passing all gates
✅ Pricing within target range
✅ Completes in < 2 hours
✅ Executive approval rate > 80%

---

## Next Steps After Testing

1. **Load Testing**: Test with 10+ concurrent executions
2. **Quality Assessment**: Human review of 20 auto-resolutions / RFP responses
3. **Integration**: Connect to real ticketing system / CRM for RFPs
4. **Monitoring**: Set up Langfuse traces for quality tracking
5. **Optimization**: Adjust confidence thresholds based on success rates

---

**Created**: January 31, 2026
**Workflows**: help-desk-triage, rfp-response
**Status**: Ready for testing
