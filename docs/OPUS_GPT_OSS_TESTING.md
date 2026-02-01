# Testing Guide: Claude Opus 4.5 + gpt-oss-120b

## Configuration Overview

### Test Configuration: `opus_test`
**Best of both worlds: Premium orchestration + Budget execution**

- **Orchestrator**: Claude Opus 4.5 ($15/$75 per 1M tokens)
  - Handles complex strategic planning
  - Coordinates multi-agent workflows
  - Makes high-level decisions

- **Team Leads** (Most Domains): gpt-oss-120b ($0.039/$0.19 per 1M tokens)
  - Research, Finance, Content, Sales, DevOps, Investigation
  - **385× cheaper than Opus** for execution
  - **50× cheaper than Sonnet** for execution

- **Team Leads** (Critical Domains): Claude Sonnet 4.5 ($3/$15 per 1M tokens)
  - Legal, Medical (domains requiring highest accuracy)
  - Fallback for any domain where gpt-oss-120b underperforms

- **Workers**: gpt-oss-20b ($0.02/$0.1 per 1M tokens)
  - **750× cheaper than Opus**
  - **150× cheaper than Sonnet**

### Comparison Configuration: `sonnet_test`
**All-Claude baseline for quality comparison**

- **Orchestrator**: Claude Opus 4.5
- **Team Leads**: Claude Sonnet 4.5 (all domains)
- **Workers**: Claude Sonnet 4.5

---

## Optimization Parameters

### gpt-oss-120b Optimizations

**Default Parameters** (defined in `app/workflows/model_params.py`):
```python
temperature: 0.7        # Balanced creativity/consistency
max_tokens: 4000        # Use more of the 131K context
top_p: 0.9             # Slightly focused sampling
frequency_penalty: 0.1  # Reduce repetition
presence_penalty: 0.1   # Encourage topic diversity
```

**Domain-Specific System Prompts**:
Each domain (Research, Finance, Content, Sales, DevOps, Legal, Medical, Investigation) has a custom system prompt that:
- Defines the team lead's role and responsibilities
- Lists available workers and their capabilities
- Provides guidelines for quality output
- Sets appropriate tone and style

---

## Running Comparison Tests

### Quick Test Script
```bash
chmod +x /tmp/test_opus_vs_gptoss.sh
/tmp/test_opus_vs_gptoss.sh
```

This will:
1. Run Content Production workflow with `opus_test` config
2. Run same workflow with `sonnet_test` config
3. Compare cost, speed, and completion status
4. Save detailed results for quality review

### Manual Testing

#### Test A: Opus + gpt-oss-120b
```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "workflow_id": "content-production",
    "inputs": {
      "topic": "AI Agent Orchestration",
      "target_keywords": "agents, llm, hierarchical",
      "target_audience": "Engineers",
      "content_goals": "Educational"
    },
    "model_config": {
      "orchestrator_model": "anthropic/claude-opus-4.5",
      "team_lead_models": {
        "research": "openai/gpt-oss-120b",
        "content": "openai/gpt-oss-120b"
      },
      "default_worker_model": "openai/gpt-oss-20b",
      "enable_local_models": false
    }
  }'
```

#### Test B: Opus + Sonnet (Baseline)
```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "workflow_id": "content-production",
    "inputs": {
      "topic": "AI Agent Orchestration",
      "target_keywords": "agents, llm, hierarchical",
      "target_audience": "Engineers",
      "content_goals": "Educational"
    },
    "model_config": {
      "orchestrator_model": "anthropic/claude-opus-4.5",
      "team_lead_models": {
        "research": "anthropic/claude-sonnet-4.5",
        "content": "anthropic/claude-sonnet-4.5"
      },
      "default_worker_model": "anthropic/claude-sonnet-4.5",
      "enable_local_models": false
    }
  }'
```

---

## Recommended Workflows to Test

### 1. Content Production (Test Creative Writing)
```json
{
  "workflow_id": "content-production",
  "inputs": {
    "topic": "AI Agent Patterns",
    "target_keywords": "agents, orchestration",
    "target_audience": "Developers",
    "content_goals": "Educational"
  }
}
```
**Tests**: Research quality, writing quality, SEO optimization

### 2. Investment Due Diligence (Test Analysis)
```json
{
  "workflow_id": "investment-due-diligence",
  "inputs": {
    "company_name": "Anthropic",
    "investment_thesis": "Leading AI safety research",
    "investment_amount": "10000000"
  }
}
```
**Tests**: Research depth, financial analysis, risk assessment

### 3. Code Review Pipeline (Test Technical Understanding)
```json
{
  "workflow_id": "code-review-pipeline",
  "inputs": {
    "code_diff": "def process(data):\n    return eval(data)",
    "repository_name": "test-repo",
    "pr_title": "Add data processing",
    "pr_description": "New feature",
    "language": "python"
  }
}
```
**Tests**: Code understanding, security analysis, best practices

### 4. Meeting Intelligence (Test Summarization)
```json
{
  "workflow_id": "meeting-intelligence",
  "inputs": {
    "meeting_transcript": "Full meeting transcript here...",
    "meeting_title": "Q1 Planning",
    "attendees": "Team members"
  }
}
```
**Tests**: Comprehension, action item extraction, summarization

---

## Optimizing gpt-oss-120b Performance

### If Quality Is Lower Than Expected:

#### 1. Adjust Temperature
```python
# In app/workflows/model_params.py
GPT_OSS_120B_PARAMS = ModelParameters(
    temperature=0.8,  # Increase for more creativity
    # or
    temperature=0.5,  # Decrease for more consistency
    ...
)
```

#### 2. Increase Context Usage
```python
max_tokens=6000,  # Use more tokens for detailed outputs
```

#### 3. Enhance System Prompts
Edit domain prompts in `app/workflows/model_params.py`:
```python
DOMAIN_SYSTEM_PROMPTS["research"] = """
You are a Research Team Lead with expertise in...
[Add more specific instructions, examples, or constraints]
"""
```

#### 4. Adjust Sampling Parameters
```python
top_p=0.95,              # Wider sampling (more diverse)
frequency_penalty=0.2,   # Stronger repetition reduction
presence_penalty=0.15,   # Encourage more topic exploration
```

#### 5. Use Fallback Models for Specific Domains
If gpt-oss-120b underperforms in specific domains:
```python
OPUS_TEST_CONFIG = ModelConfig(
    team_lead_models={
        "research": "openai/gpt-oss-120b",  # Good
        "finance": "openai/gpt-oss-120b",   # Good
        "content": "anthropic/claude-sonnet-4.5",  # Use Claude if needed
        "legal": "anthropic/claude-sonnet-4.5",    # Already using Claude
        ...
    }
)
```

---

## Cost Analysis

### Example: Content Production Workflow (5 steps)

**Configuration A: opus_test (Opus + gpt-oss-120b)**
- Orchestrator (Opus): ~$0.05
- Team Leads (gpt-oss-120b): ~$0.002
- Workers (gpt-oss-20b): ~$0.0006
- **Total: ~$0.053** (5.3¢)

**Configuration B: sonnet_test (Opus + Sonnet)**
- Orchestrator (Opus): ~$0.05
- Team Leads (Sonnet): ~$0.012
- Workers (Sonnet): ~$0.006
- **Total: ~$0.068** (6.8¢)

**Savings: ~22% with gpt-oss-120b**

### Example: Investment Due Diligence (4 steps, 2 checkpoints)

**Configuration A: opus_test**
- Orchestrator: ~$0.08
- Team Leads: ~$0.003
- Workers: ~$0.001
- **Total: ~$0.084** (8.4¢)

**Configuration B: sonnet_test**
- Orchestrator: ~$0.08
- Team Leads: ~$0.024
- Workers: ~$0.012
- **Total: ~$0.116** (11.6¢)

**Savings: ~28% with gpt-oss-120b**

---

## Quality Evaluation Criteria

### What to Check in Test Results:

#### 1. Completeness
- Are all required outputs present?
- Did workflows complete without errors?
- Are there any missing sections?

#### 2. Accuracy
- Is factual information correct?
- Are calculations accurate?
- Are citations and sources valid?

#### 3. Coherence
- Does the output flow logically?
- Are transitions smooth?
- Is the structure clear?

#### 4. Depth
- Is analysis sufficiently deep?
- Are insights meaningful?
- Are recommendations actionable?

#### 5. Style
- Is tone appropriate for audience?
- Is language clear and professional?
- Is formatting consistent?

---

## Decision Framework

### Use `opus_test` (Opus + gpt-oss-120b) if:
✓ Quality is **≥90%** of sonnet_test baseline
✓ Cost savings are significant (20-30%)
✓ Workflows complete successfully
✓ Output meets business requirements

### Use `sonnet_test` (Opus + Sonnet) if:
✓ Quality difference is noticeable
✓ Critical domains (Legal, Medical) need highest accuracy
✓ Cost is less important than quality
✓ Client-facing or high-stakes outputs

### Hybrid Approach (Recommended):
✓ Use opus_test for most workflows
✓ Use sonnet_test for critical domains (Legal, Medical, Finance)
✓ Adjust per domain based on testing results

---

## Next Steps

1. **Run Comparison Tests** (This Weekend)
   ```bash
   /tmp/test_opus_vs_gptoss.sh
   ```

2. **Review Results**
   - Check `/tmp/test_opus_gptoss_result.json`
   - Check `/tmp/test_opus_sonnet_result.json`
   - Compare quality manually

3. **Optimize as Needed**
   - Adjust parameters in `model_params.py`
   - Enhance domain prompts
   - Configure fallback models

4. **Deploy to Production**
   - Use opus_test for general workflows
   - Use sonnet_test for critical workflows
   - Monitor quality and cost over time

5. **Transition to Local Models** (Phase 2)
   - Once happy with gpt-oss-120b, deploy to Tesla P40
   - Replace gpt-oss-120b with local Llama 3.1 70B
   - Keep Opus orchestrator for strategic planning

---

## Parameter Tuning Reference

| Parameter | Lower Value | Higher Value | Use Case |
|-----------|-------------|--------------|----------|
| **temperature** | 0.3-0.5 | 0.8-1.0 | Low: Factual, High: Creative |
| **max_tokens** | 1000-2000 | 4000-8000 | Low: Summaries, High: Articles |
| **top_p** | 0.7-0.8 | 0.95-1.0 | Low: Focused, High: Diverse |
| **frequency_penalty** | 0.0 | 0.3-0.5 | Reduce repetition |
| **presence_penalty** | 0.0 | 0.3-0.5 | Encourage new topics |

---

**Last Updated**: January 31, 2026
**Configuration Files**:
- `app/workflows/model_config.py` - Model configurations
- `app/workflows/model_params.py` - Parameters and prompts
- `/tmp/test_opus_vs_gptoss.sh` - Testing script
