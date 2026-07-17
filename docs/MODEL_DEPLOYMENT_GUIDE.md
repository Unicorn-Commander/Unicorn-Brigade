# Model Deployment Guide - Hardware-Optimized Configurations

## Your Hardware Options

### 1. Dual Tesla P40 (48GB VRAM Total)
- **VRAM**: 2× 24GB = 48GB
- **Best For**: Running 70B models with quantization
- **Recommended**: Mix of large local models + API fallback

### 2. Ryzen AI 395+ (128GB RAM + XDNA2 NPU)
- **RAM**: 128GB unified memory
- **NPU**: XDNA2 for AI acceleration
- **Best For**: Running huge models on CPU/NPU
- **Recommended**: Full local deployment with 70B+ models

### 3. OpenRouter API (Testing Phase)
- **Cost**: Ultra-low ($0.02-0.19 per 1M tokens)
- **Best For**: Testing before local deployment
- **Recommended**: Validate workflows before GPU setup

---

## Available Model Configurations

### Preset 1: `openrouter_budget` (Test First!)
**Ultra-low cost testing with OpenRouter gpt-oss models**

- **Orchestrator**: `openai/gpt-4o-mini` ($0.15/$0.6 per 1M tokens)
- **Team Leads**: `openai/gpt-oss-120b` ($0.039/$0.19 per 1M tokens)
- **Workers**: `openai/gpt-oss-20b` ($0.02/$0.1 per 1M tokens)
- **DevOps Lead**: `qwen/qwen3-coder-flash` ($0.3/$1.5 per 1M tokens)

**Cost Example**: Meeting Intelligence workflow = ~$0.003 (0.3¢)

**Usage**:
```bash
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "workflow_id": "meeting-intelligence",
    "inputs": {...},
    "model_config": {
      "orchestrator_model": "openai/gpt-4o-mini",
      "team_lead_models": {
        "research": "openai/gpt-oss-120b",
        "finance": "openai/gpt-oss-120b",
        "content": "openai/gpt-oss-120b",
        "devops": "qwen/qwen3-coder-flash"
      },
      "default_worker_model": "openai/gpt-oss-20b",
      "enable_local_models": false
    }
  }'
```

---

### Preset 2: `tesla_p40` (Dual Tesla P40 Setup)
**Optimized for 48GB VRAM with 70B models**

- **Orchestrator**: `openai/gpt-4o-mini` (API - strategic reasoning)
- **Premium Team Leads**: `ollama/llama3.1:70b` (Research, Legal)
  - Requires ~40GB VRAM with 4-bit quantization
  - Can run 1 at a time across both GPUs
- **Standard Team Leads**: `ollama/llama3.1:8b` / `ollama/mistral:7b`
  - Fits comfortably in 24GB
  - Can run multiple concurrently
- **Workers**: `ollama/llama3.2:3b` (fast, minimal VRAM)

**Setup**:
```bash
# On Tesla P40 server
ollama pull llama3.1:70b-q4_K_M  # ~40GB quantized
ollama pull llama3.1:8b
ollama pull mistral:7b
ollama pull llama3.2:3b
ollama pull deepseek-coder:6.7b
ollama pull mixtral:8x7b-q4_K_M  # ~26GB quantized
```

**Concurrent Load**:
- GPU 0: Llama 3.1 70B (40GB)
- GPU 1: Mixtral 8x7B (26GB) or 3× Llama 3.1 8B workers

---

### Preset 3: `ryzen_ai` (Ryzen AI 395+ Setup)
**Full local deployment with 128GB RAM**

- **Orchestrator**: `ollama/llama3.1:70b`
- **Team Leads**: Mix of 70B and 8B models
- **Workers**: `ollama/llama3.2:3b`

**Advantages**:
- Can load multiple 70B models simultaneously
- No VRAM constraints
- XDNA2 NPU acceleration for inference

**Setup**:
```bash
# Install Ollama for AMD
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.1:70b
ollama pull mixtral:8x7b
ollama pull llama3.1:8b
ollama pull llama3.2:3b
```

**AMD ROCm Support** (if using GPU):
```bash
# Install ROCm for AMD GPUs
wget https://repo.radeon.com/amdgpu-install/latest/ubuntu/focal/amdgpu-install_*.deb
sudo dpkg -i amdgpu-install_*.deb
sudo amdgpu-install --usecase=rocm
```

---

## Model Catalog - OpenRouter Options

### Team Lead Models (7B-120B)

| Model | Input Cost | Output Cost | Context | Best For |
|-------|-----------|-------------|---------|----------|
| **openai/gpt-oss-120b** | $0.039/1M | $0.19/1M | 131K | General purpose, excellent value |
| **qwen/qwen3-vl-30b-a3b** | $0.15/1M | $0.6/1M | 262K | Multimodal, large context |
| **qwen/qwen3-coder-plus** | $1/1M | $5/1M | 128K | Premium code generation |
| **openai/gpt-4o-mini** | $150/1M | $600/1M | 128K | Fallback orchestrator |

### Worker Models (1B-20B)

| Model | Input Cost | Output Cost | Context | Best For |
|-------|-----------|-------------|---------|----------|
| **openai/gpt-oss-20b** | $0.02/1M | $0.1/1M | 131K | Ultra-cheap workers |
| **qwen/qwen3-coder-flash** | $0.3/1M | $1.5/1M | 128K | Fast code tasks |
| **openai/gpt-oss-safeguard-20b** | $0.075/1M | $0.3/1M | 131K | Safety filtering |

---

## Recommended Deployment Strategy

### Phase 1: Test with OpenRouter (Week 1)
1. Use `openrouter_budget` preset
2. Test all 25 workflow templates
3. Benchmark quality and cost
4. Identify which Team Leads need premium models

**Cost**: ~$5-20 for comprehensive testing

### Phase 2: Deploy to Tesla P40s (Week 2)
1. Pull quantized 70B models to Tesla P40 server
2. Use `tesla_p40` preset
3. Keep orchestrator on API (gpt-4o-mini)
4. Run Team Leads on GPU, Workers on CPU

**Setup**:
```bash
# SSH to Tesla P40 server
ssh user@tesla-server

# Install Ollama with CUDA support
curl -fsSL https://ollama.com/install.sh | sh
export CUDA_VISIBLE_DEVICES=0,1  # Both P40s

# Pull models
ollama pull llama3.1:70b-q4_K_M
ollama pull llama3.1:8b
ollama pull llama3.2:3b
ollama pull deepseek-coder:6.7b
ollama pull mixtral:8x7b-q4_K_M

# Set Ollama to use both GPUs
OLLAMA_NUM_GPU=2 ollama serve
```

### Phase 3: Add Ryzen AI Server (Optional)
1. Use Ryzen AI for CPU-heavy workflows
2. Run multiple 70B models simultaneously
3. Offload from GPUs for parallel execution

---

## Environment Configuration

### Update .env for OpenRouter Testing
```bash
# In /Volumes/Studio Storage/Development/Unicorn-Brigade/.env

# Enable OpenRouter routing via Ops-Center
OPS_CENTER_URL=https://unicorncommander.ai
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000

# Set default workflow config
DEFAULT_WORKFLOW_PRESET=openrouter_budget
```

### Update .env for Tesla P40 Production
```bash
# Point to Tesla P40 Ollama server
OLLAMA_BASE_URL=http://tesla-p40-server:11434

# Set default to local models
DEFAULT_WORKFLOW_PRESET=tesla_p40
```

---

## Testing Commands

### List All Available Presets
```bash
curl -H "X-API-Key: YOUR_KEY" \
  http://localhost:8100/api/v1/hierarchical/models | python3 -m json.tool
```

### Test with Specific Configuration
```bash
# OpenRouter Budget
curl -X POST http://localhost:8100/api/v1/hierarchical/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "workflow_id": "content-production",
    "inputs": {
      "topic": "AI Agent Orchestration",
      "target_keywords": "agents, llm, orchestration",
      "target_audience": "Developers",
      "content_goals": "Educational"
    },
    "model_config": {
      "orchestrator_model": "openai/gpt-4o-mini",
      "team_lead_models": {
        "research": "openai/gpt-oss-120b",
        "content": "openai/gpt-oss-120b"
      },
      "default_worker_model": "openai/gpt-oss-20b",
      "enable_local_models": false
    }
  }'
```

---

## Cost Comparison

### Example: Investment Due Diligence Workflow (4 steps, 2 checkpoints)

**OpenRouter Budget**:
- Orchestrator (gpt-4o-mini): 2× $0.00015/1K = ~$0.002
- Team Leads (gpt-oss-120b): 4× $0.000039/1K = ~$0.0002
- Workers (gpt-oss-20b): 12× $0.00002/1K = ~$0.0003
- **Total**: ~$0.0025 (0.25¢)

**Tesla P40 Local**:
- Orchestrator (gpt-4o-mini): ~$0.002
- Team Leads (local): $0
- Workers (local): $0
- **Total**: ~$0.002 (0.2¢)

**Full API (OpenAI)**:
- Orchestrator (gpt-4o): 2× $0.0025/1K = ~$0.05
- Team Leads (gpt-4o-mini): 4× $0.00015/1K = ~$0.006
- Workers (gpt-4o-mini): 12× $0.00015/1K = ~$0.018
- **Total**: ~$0.074 (7.4¢)

**Savings**: Tesla P40 is **37× cheaper** than full API!

---

## Hardware Recommendations

### For Your Use Case (Testing → Production)

1. **Start**: `openrouter_budget` on current Mac
   - Test all workflows
   - Find which need premium models
   - Total cost: ~$10-30

2. **Deploy**: `tesla_p40` on dual P40 server
   - Run 70B models for critical domains (Legal, Medical, Research)
   - Run 8B models for general domains
   - Cost: ~99% reduction vs API

3. **Scale**: Add `ryzen_ai` for parallel execution
   - Handle multiple concurrent workflows
   - CPU-based inference with NPU acceleration
   - Zero marginal cost per inference

---

## Model Performance Tiers

### Orchestrator (The General)
- **Best**: GPT-4o, Claude Opus ($$$)
- **Good**: GPT-4o-mini, Claude Sonnet ($$)
- **Local**: Llama 3.1 70B ($, requires 48GB VRAM)

### Team Leads (Domain Experts)
- **Best**: GPT-4o-mini, Claude Haiku ($$)
- **Budget**: OpenRouter gpt-oss-120b ($)
- **Local**: Llama 3.1 8B, Mistral 7B (free)

### Workers (Specialists)
- **Budget**: OpenRouter gpt-oss-20b ($)
- **Local**: Llama 3.2 3B, Phi-3 3.8B (free)

---

## Next Steps

1. **Immediate**: Test with `openrouter_budget` configuration
2. **Week 1**: Run all 25 workflows, collect metrics
3. **Week 2**: Set up Ollama on Tesla P40 server
4. **Week 3**: Deploy to production with `tesla_p40` preset
5. **Future**: Add Ryzen AI server for additional capacity

---

**Last Updated**: January 31, 2026
**Status**: Configuration complete, ready for testing
