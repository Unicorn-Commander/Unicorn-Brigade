# Guardrails Integration Plan for Unicorn Brigade

**Document Version:** 1.0
**Date:** January 30, 2026
**Status:** Research Complete - Ready for Implementation

## Executive Summary

This document outlines the guardrails integration strategy for Unicorn Brigade, focusing on self-hosted solutions that integrate with Ops-Center's LiteLLM proxy layer. After comprehensive research of the current (January 2026) guardrails landscape, we recommend a **layered approach** combining LiteLLM's built-in guardrails with Llama Guard 3 for content moderation and Microsoft Presidio for PII detection.

---

## Table of Contents

1. [Guardrails Landscape Research](#guardrails-landscape-research)
2. [Solution Comparison Matrix](#solution-comparison-matrix)
3. [Recommended Architecture](#recommended-architecture)
4. [Implementation Plan](#implementation-plan)
5. [Configuration Examples](#configuration-examples)
6. [Performance Considerations](#performance-considerations)
7. [Next Steps](#next-steps)

---

## Guardrails Landscape Research

### 1. NVIDIA NeMo Guardrails

**Overview:** Open-source toolkit for adding programmable guardrails to LLM-based conversational systems.

**Latest Features (2025-2026):**
- LangChain 1.x compatibility with content blocks API
- BotThinking events for reasoning trace processing
- In-memory LFU caching for safety models
- LangGraph integration for multi-agent workflows
- GPU acceleration for low-latency performance
- Integration with NemoGuard NIMs (Content Safety, Topic Control, Jailbreak Detection)

**Self-Hosted Capability:** Yes - fully open-source, runs locally

**LiteLLM Integration:** Indirect - works via custom callbacks or as middleware. No native LiteLLM guardrail provider, but can be integrated through custom guardrail implementations.

**Performance:**
- ~0.5 seconds latency with 5 parallel GPU-accelerated guardrails
- 33% improvement in policy violation detection with NIM microservices
- In-memory caching reduces latency for repeated checks

**Types of Guardrails:**
- Input filtering (jailbreak detection, topic control)
- Output filtering (content safety, factuality)
- Topic control (off-topic detection)
- Custom Colang flows for complex policies

**Customization:** High - uses Colang DSL for defining conversation flows and guardrails

**Verdict:** Powerful but complex. Best for organizations needing sophisticated conversational guardrails with GPU infrastructure.

---

### 2. Guardrails AI (guardrails-ai)

**Overview:** Python framework for adding input/output guards with validators from Guardrails Hub.

**Latest Features (2025-2026):**
- 100+ validators in Guardrails Hub
- Native LiteLLM integration
- Structured output validation
- Async support for high concurrency

**Self-Hosted Capability:** Yes - runs as local service or containerized

**LiteLLM Integration:** **Native Support** - First-class integration documented in LiteLLM docs

```yaml
guardrails:
  - guardrail_name: "my-guardrail"
    litellm_params:
      guardrail: guardrails_ai
      guard_name: my_guard
      mode: post_call  # or pre_call, or [pre_call, post_call]
      api_base: "http://guardrails-service:8000"
```

**Performance:**
- Depends on validators used
- Lightweight validators: <50ms overhead
- LLM-based validators: 200-500ms overhead

**Types of Guardrails:**
- PII detection (DetectPII validator)
- Toxicity detection
- Bias detection
- Factuality checking
- Custom validators

**Customization:** High - Python-based validators, easy to create custom ones

**Verdict:** Excellent choice for LiteLLM integration. Moderate complexity with good validator ecosystem.

---

### 3. Llama Guard 3 (Meta)

**Overview:** Specialized content moderation model fine-tuned from Llama 3.1, optimized for safety classification.

**Latest Features (2025-2026):**
- MLCommons standardized hazards taxonomy
- 8-language support
- Tool call safety (code interpreter, search)
- Available in 1B and 8B parameter versions

**Self-Hosted Capability:** Yes - available via:
- Hugging Face (gated access)
- Ollama (`ollama run llama-guard3`)
- vLLM deployment
- LMDeploy, MLC-LLM, TGI

**LiteLLM Integration:** Can be integrated as custom guardrail model:

```yaml
model_list:
  - model_name: llama-guard
    litellm_params:
      model: ollama/llama-guard3
      api_base: http://localhost:11434
```

**Performance (with vLLM):**
- Llama-Guard-3-1B: 0.165s per check, 76% threat detection
- Llama-Guard-3-8B: Higher accuracy, ~0.5-0.8s per check
- Significantly outperforms general-purpose models for safety

**Types of Guardrails:**
- Violence detection
- Hate speech detection
- Sexual content filtering
- Self-harm detection
- Criminal planning detection
- Weapons/dangerous activities

**Customization:** Moderate - can be fine-tuned for custom categories

**Verdict:** Best-in-class for content moderation. Highly recommended as safety layer.

---

### 4. Microsoft Presidio

**Overview:** Open-source PII detection and anonymization framework.

**Latest Features (2025-2026):**
- 40+ built-in PII recognizers
- Custom recognizer support
- Multi-language support
- Image PII detection

**Self-Hosted Capability:** Yes - Docker containers, Kubernetes, Python library

**LiteLLM Integration:** **Native Support** - Built-in Presidio guardrail:

```yaml
guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: pre_call
      presidio_analyzer_api_base: "http://presidio-analyzer:5001"
      presidio_anonymizer_api_base: "http://presidio-anonymizer:5002"
```

**Performance:**
- ~50-100ms per text analysis
- Highly parallelizable
- Low memory footprint

**Types of Guardrails:**
- PII detection (names, emails, phone numbers, SSN, credit cards)
- PHI detection (medical record numbers, health conditions)
- Custom entity detection
- Data anonymization/redaction

**Customization:** High - regex patterns, NER models, custom recognizers

**Verdict:** Essential for PII protection. Highly recommended.

---

### 5. LiteLLM Built-in Guardrails

**Overview:** Native guardrails introduced in v1.79.3 (November 2025).

**Features:**
- Keyword blocking
- Pattern detection (regex)
- PII detection
- Harmful content detection
- Image content analysis

**Self-Hosted Capability:** Yes - part of LiteLLM proxy

**LiteLLM Integration:** Native - configuration only

```yaml
guardrails:
  - guardrail_name: "keyword-guard"
    litellm_params:
      guardrail: keyword
      mode: pre_call
      blocked_keywords: ["hack", "exploit", "bypass"]
```

**Performance:**
- 8ms P95 latency at 1k RPS (for basic checks)
- Minimal overhead for pattern matching

**Types of Guardrails:**
- Keyword filtering
- Regex patterns
- Basic content moderation

**Customization:** Limited - keyword lists and regex patterns

**Verdict:** Good for basic protection with zero additional infrastructure.

---

### 6. Azure AI Content Safety (Containerized)

**Overview:** Microsoft's enterprise content safety service, available in containers.

**Self-Hosted Capability:** Yes - Docker containers with Azure licensing

**LiteLLM Integration:** No native support - requires custom integration

**Performance:**
- ~100-200ms per analysis
- Requires Azure subscription for containers

**Types of Guardrails:**
- Violence, hate, sexual, self-harm detection
- Custom categories
- Severity thresholds

**Customization:** Moderate - custom categories, configurable thresholds

**Verdict:** Good enterprise option but requires Azure subscription. Not ideal for fully self-hosted.

---

### 7. Constitutional AI Patterns

**Overview:** Anthropic's approach to AI alignment through principles/constitutions.

**Self-Hosted Capability:** Yes - via open-source implementations:
- Hugging Face alignment-handbook
- C3AI framework

**LiteLLM Integration:** Can be implemented as custom guardrail using LLM-as-judge

**Implementation:**
```python
# Constitutional AI as post-call guardrail
constitution = """
1. Be helpful, harmless, and honest
2. Never provide instructions for illegal activities
3. Respect user privacy
"""

# Use LLM to evaluate response against constitution
```

**Performance:**
- Additional LLM call: 500ms-2s overhead
- Can be batched/cached for efficiency

**Verdict:** Useful for complex policy enforcement. Higher latency but comprehensive.

---

## Solution Comparison Matrix

| Feature | NeMo Guardrails | Guardrails AI | Llama Guard 3 | Presidio | LiteLLM Built-in |
|---------|-----------------|---------------|---------------|----------|------------------|
| **Self-Hosted** | Yes | Yes | Yes | Yes | Yes |
| **LiteLLM Native** | No | Yes | Custom | Yes | Yes |
| **Latency** | 500ms+ | 50-500ms | 165-800ms | 50-100ms | 8ms |
| **Input Filtering** | Yes | Yes | Yes | Yes | Yes |
| **Output Filtering** | Yes | Yes | Yes | Yes | Limited |
| **PII Detection** | Limited | Yes | No | Excellent | Basic |
| **Content Moderation** | Yes | Yes | Excellent | No | Basic |
| **Topic Control** | Excellent | Limited | No | No | No |
| **Custom Rules** | High | High | Moderate | High | Limited |
| **GPU Required** | Recommended | No | Yes | No | No |
| **Complexity** | High | Moderate | Low | Low | Low |
| **Maintenance** | High | Moderate | Low | Low | Low |

---

## Recommended Architecture

### Tier 1: Essential (Recommended Starting Point)

Deploy on Ops-Center LiteLLM proxy:

```
User Request
    |
    v
[LiteLLM Proxy - Ops-Center]
    |
    +---> [Pre-Call Guardrails]
    |         |
    |         +---> LiteLLM Built-in (keyword blocking, patterns)
    |         +---> Presidio (PII detection/masking)
    |         +---> Llama Guard 3-1B (content safety - fast)
    |
    v
[LLM Provider] (via LiteLLM routing)
    |
    v
[Post-Call Guardrails]
    |
    +---> Llama Guard 3 (output safety)
    +---> Presidio (PII in responses)
    |
    v
User Response
```

### Tier 2: Enhanced (Production Recommended)

Add Guardrails AI for validator ecosystem:

```
[LiteLLM Proxy - Ops-Center]
    |
    +---> [Pre-Call]
    |         +---> LiteLLM Built-in (fast checks)
    |         +---> Presidio (PII)
    |         +---> Guardrails AI (toxicity, bias)
    |         +---> Llama Guard 3-1B (content safety)
    |
    v
[LLM Provider]
    |
    v
[Post-Call]
    |
    +---> Llama Guard 3 (safety)
    +---> Guardrails AI (factuality, relevance)
    +---> Presidio (PII in output)
```

### Tier 3: Enterprise (Full Featured)

Add NeMo Guardrails for complex policies:

```
[LiteLLM Proxy - Ops-Center]
    |
    +---> [NeMo Guardrails Orchestrator]
              |
              +---> Topic Control
              +---> Jailbreak Detection
              +---> Custom Colang Flows
              |
              +---> [Sub-Guardrails]
                    +---> Llama Guard 3
                    +---> Presidio
                    +---> Guardrails AI
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Goal:** Basic guardrails with LiteLLM built-in + Presidio

**Tasks:**
1. Deploy Presidio Analyzer and Anonymizer containers
2. Configure LiteLLM proxy with built-in guardrails
3. Add Presidio integration for PII masking
4. Test with sample requests
5. Monitor latency overhead

**Deliverables:**
- Docker compose overlay for Presidio
- LiteLLM config with basic guardrails
- Test suite for guardrail verification

### Phase 2: Content Safety (Week 3-4)

**Goal:** Add Llama Guard 3 for content moderation

**Tasks:**
1. Deploy Llama Guard 3-1B via Ollama or vLLM
2. Create custom LiteLLM guardrail for Llama Guard
3. Configure pre-call and post-call checks
4. Tune sensitivity thresholds
5. Add monitoring/alerting for blocked content

**Deliverables:**
- Llama Guard service deployment
- Custom guardrail implementation
- Monitoring dashboard

### Phase 3: Advanced Validators (Week 5-6)

**Goal:** Integrate Guardrails AI for comprehensive validation

**Tasks:**
1. Deploy Guardrails AI service
2. Configure validators (toxicity, bias, factuality)
3. Create custom validators for Unicorn Brigade policies
4. Integration testing with agent workflows
5. Performance optimization

**Deliverables:**
- Guardrails AI deployment
- Custom validator library
- Performance benchmarks

### Phase 4: Production Hardening (Week 7-8)

**Goal:** Production-ready guardrails system

**Tasks:**
1. High availability configuration
2. Caching layer for repeated checks
3. Circuit breakers for guardrail failures
4. Comprehensive logging and audit trail
5. Documentation and runbooks

**Deliverables:**
- HA deployment configuration
- Operational runbooks
- Final documentation

---

## Configuration Examples

### LiteLLM Proxy Configuration (`litellm_config.yaml`)

```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY

  - model_name: claude-3-opus
    litellm_params:
      model: anthropic/claude-3-opus-20240229
      api_key: os.environ/ANTHROPIC_API_KEY

  # Llama Guard model for content safety
  - model_name: llama-guard
    litellm_params:
      model: ollama/llama-guard3:1b
      api_base: http://llama-guard:11434

guardrails:
  # Built-in keyword blocking
  - guardrail_name: "keyword-filter"
    litellm_params:
      guardrail: keyword
      mode: pre_call
      blocked_keywords:
        - "jailbreak"
        - "ignore previous instructions"
        - "DAN mode"
      default_on: true

  # Pattern-based filtering
  - guardrail_name: "pattern-filter"
    litellm_params:
      guardrail: regex
      mode: pre_call
      patterns:
        - "(?i)bypass.*safety"
        - "(?i)pretend.*you.*are"
      default_on: true

  # Presidio PII masking
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: [pre_call, post_call]
      presidio_analyzer_api_base: "http://presidio-analyzer:5001"
      presidio_anonymizer_api_base: "http://presidio-anonymizer:5002"
      output_parse_pii: true
      pii_entities_to_detect:
        - PERSON
        - EMAIL_ADDRESS
        - PHONE_NUMBER
        - CREDIT_CARD
        - US_SSN
        - IP_ADDRESS
      default_on: true

  # Guardrails AI validators
  - guardrail_name: "content-validators"
    litellm_params:
      guardrail: guardrails_ai
      guard_name: "unicorn_brigade_guard"
      mode: [pre_call, post_call]
      api_base: "http://guardrails-ai:8000"
      default_on: true

  # Custom Llama Guard content safety
  - guardrail_name: "content-safety"
    litellm_params:
      guardrail: custom
      mode: [pre_call, post_call]
      api_base: "http://llama-guard-service:8080"
      default_on: true

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL

litellm_settings:
  drop_params: true
  set_verbose: false
  callbacks:
    - langfuse
```

### Presidio Configuration

**analyzer-config.yaml:**
```yaml
supported_entities:
  - PERSON
  - EMAIL_ADDRESS
  - PHONE_NUMBER
  - CREDIT_CARD
  - US_SSN
  - US_DRIVER_LICENSE
  - IP_ADDRESS
  - CRYPTO
  - IBAN_CODE
  - MEDICAL_LICENSE

nlp_engine_name: spacy
models:
  - lang_code: en
    model_name: en_core_web_lg

# Custom recognizers for Unicorn Brigade
custom_recognizers:
  - name: API_KEY_RECOGNIZER
    supported_entity: API_KEY
    patterns:
      - name: api_key_pattern
        regex: "(?i)(api[_-]?key|apikey|secret[_-]?key)[\\s]*[=:][\\s]*['\"]?([a-zA-Z0-9_-]{20,})['\"]?"
        score: 0.85
```

### Guardrails AI Guard Definition

**guards/unicorn_brigade_guard.py:**
```python
from guardrails import Guard
from guardrails.hub import (
    DetectPII,
    ToxicLanguage,
    RestrictToTopic,
    ValidLength,
    DetectPromptInjection
)

# Create the guard with validators
unicorn_brigade_guard = Guard(
    name="unicorn_brigade_guard",
    description="Main guard for Unicorn Brigade agent platform"
).use_many(
    # Input validators (pre-call)
    DetectPromptInjection(on_fail="exception"),
    ToxicLanguage(threshold=0.7, on_fail="exception"),

    # Output validators (post-call)
    ValidLength(min=1, max=10000, on_fail="fix"),
    RestrictToTopic(
        valid_topics=[
            "general assistance",
            "coding help",
            "research",
            "analysis",
            "writing",
            "business"
        ],
        invalid_topics=[
            "illegal activities",
            "violence",
            "weapons",
            "explicit content"
        ],
        on_fail="exception"
    )
)
```

### Llama Guard Service

**llama_guard_service.py:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI()

OLLAMA_BASE = "http://llama-guard:11434"

class GuardrailRequest(BaseModel):
    text: str
    check_type: str = "both"  # input, output, both

class GuardrailResponse(BaseModel):
    safe: bool
    category: str | None = None
    explanation: str | None = None

LLAMA_GUARD_PROMPT = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
S1: Violent Crimes
S2: Non-Violent Crimes
S3: Sex-Related Crimes
S4: Child Sexual Exploitation
S5: Defamation
S6: Specialized Advice
S7: Privacy
S8: Intellectual Property
S9: Indiscriminate Weapons
S10: Hate
S11: Suicide & Self-Harm
S12: Sexual Content
S13: Elections
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>
{role}: {content}
<END CONVERSATION>

Provide your safety assessment for {role} in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

@app.post("/check", response_model=GuardrailResponse)
async def check_content(request: GuardrailRequest):
    role = "User" if request.check_type == "input" else "Assistant"

    prompt = LLAMA_GUARD_PROMPT.format(role=role, content=request.text)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": "llama-guard3:1b",
                "prompt": prompt,
                "stream": False
            },
            timeout=30.0
        )

    result = response.json()["response"].strip()

    if result.lower().startswith("safe"):
        return GuardrailResponse(safe=True)
    else:
        lines = result.split("\n")
        category = lines[1] if len(lines) > 1 else "unknown"
        return GuardrailResponse(
            safe=False,
            category=category,
            explanation=f"Content flagged for: {category}"
        )

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Performance Considerations

### Latency Budget

For a typical agent chat request, target total guardrail overhead:

| Guardrail | Pre-call (ms) | Post-call (ms) |
|-----------|---------------|----------------|
| LiteLLM Built-in | 5-10 | 5-10 |
| Presidio | 30-50 | 30-50 |
| Llama Guard 3-1B | 150-200 | 150-200 |
| Guardrails AI (basic) | 20-40 | 20-40 |
| **Total Overhead** | **205-300ms** | **205-300ms** |

### Optimization Strategies

1. **Parallel Execution**: Run independent guardrails in parallel
2. **Caching**: Cache repeated checks (e.g., same user prompts)
3. **Tiered Checking**: Fast checks first, expensive checks only if needed
4. **Async Processing**: For post-call, return response while checking continues
5. **Batching**: Batch multiple checks when possible

### Fallback Strategy

```yaml
guardrails:
  - guardrail_name: "content-safety"
    litellm_params:
      guardrail: custom
      mode: pre_call
      api_base: "http://llama-guard-service:8080"
      timeout: 5  # seconds
      fallback_action: "allow"  # or "block" for high-security
```

---

## Next Steps

1. **Review this document** with the team
2. **Approve Phase 1** implementation scope
3. **Set up development environment** for guardrails testing
4. **Create monitoring dashboards** for guardrail metrics
5. **Define SLOs** for guardrail latency and accuracy

---

## References

- [LiteLLM Guardrails Documentation](https://docs.litellm.ai/docs/proxy/guardrails/quick_start)
- [NVIDIA NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails)
- [Guardrails AI Documentation](https://guardrailsai.com/docs)
- [Llama Guard 3 on Hugging Face](https://huggingface.co/meta-llama/Llama-Guard-3-8B)
- [Microsoft Presidio](https://microsoft.github.io/presidio/)
- [LiteLLM Presidio Integration](https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2)

---

**Document Maintainer:** Unicorn Brigade Team
**Last Updated:** January 30, 2026
