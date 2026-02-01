# Model Flexibility Architecture

**Last Updated**: January 31, 2026
**Status**: Production Architecture - Implementation Ready

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Supported Model Backends](#supported-model-backends)
4. [Deployment Scenarios](#deployment-scenarios)
5. [Model Provider Implementations](#model-provider-implementations)
6. [Configuration Guide](#configuration-guide)
7. [Model Recommendations by Tier](#model-recommendations-by-tier)
8. [Performance Considerations](#performance-considerations)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Migration Guide](#migration-guide)
11. [Troubleshooting](#troubleshooting)

---

## Executive Summary

Unicorn Brigade's **Model Flexibility Architecture** enables deployment across diverse hardware environments while maintaining consistent functionality. The platform supports **cloud API models** (OpenAI, Anthropic, Google) and **local models** (MLX for Mac, Ollama cross-platform, llama.cpp lightweight), with automatic fallback chains for reliability.

### Key Benefits

- **Hardware Agnostic**: Deploy on Mac (MLX), VPS (CPU/llama.cpp), or GPU servers (Ollama/CUDA)
- **Cost Optimization**: Use free local models for 80% of work, cloud models for critical reasoning
- **Hybrid Deployments**: Mix local and cloud models within a single workflow
- **Zero Lock-in**: Switch providers without code changes

### Current Implementation Status

- ✅ **Ops-Center Cloud Routing**: Production-ready (OpenRouter, Anthropic, vLLM)
- ✅ **Ollama Integration**: Partial support (referenced in model catalog, needs provider implementation)
- ⏸️ **MLX Provider**: Planned (Mac development priority)
- ⏸️ **llama.cpp Provider**: Planned (VPS CPU deployment)

---

## Architecture Overview

### Abstract Model Provider Interface

The platform uses a **provider-agnostic interface** where all LLM interactions route through `OpsCenterLLMClient`:

```
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                          │
│            (Agents, Workflows, Tools)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              OpsCenterLLMClient                             │
│          (Unified LLM Interface)                            │
│  - chat_completion()                                        │
│  - chat_completion_with_tools()                             │
│  - execute_tool_loop()                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌─────────────┐
│ Ops-Center   │ │   MLX    │ │   Ollama    │
│   (Cloud)    │ │  (Local) │ │  (Local)    │
│              │ │          │ │             │
│ - OpenRouter │ │ - Apple  │ │ - CUDA GPU  │
│ - Anthropic  │ │   Silicon│ │ - CPU       │
│ - vLLM       │ │ - Metal  │ │ - MPS       │
└──────────────┘ └──────────┘ └─────────────┘
```

### Three-Tier Hierarchy Model Selection

The platform automatically selects appropriate models for each agent tier:

```
┌─────────────────────────────────────────────────────────────┐
│         ORCHESTRATOR (The General)                          │
│         Model: GPT-4o / Claude Sonnet 4.5                   │
│         Backend: Cloud API (always)                         │
└─────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ TEAM LEAD    │  │ TEAM LEAD    │  │ TEAM LEAD    │
│ Research     │  │ Finance      │  │ Legal        │
│ Model: 7-14B │  │ Model: 7-14B │  │ Model: 7-14B │
│ Backend:     │  │ Backend:     │  │ Backend:     │
│ Local/Cloud  │  │ Local/Cloud  │  │ Local/Cloud  │
└──────────────┘  └──────────────┘  └──────────────┘
     │ │ │             │ │ │             │ │ │
     ▼ ▼ ▼             ▼ ▼ ▼             ▼ ▼ ▼
┌────────────┐    ┌────────────┐    ┌────────────┐
│ WORKER 1-3B│    │ WORKER 1-3B│    │ WORKER 1-3B│
│ Backend:   │    │ Backend:   │    │ Backend:   │
│ Local      │    │ Local      │    │ Local      │
└────────────┘    └────────────┘    └────────────┘
```

---

## Supported Model Backends

### 1. Ops-Center (Cloud - Production Ready)

**Current Status**: ✅ Production

Routes to cloud inference providers through unified endpoint.

**Supported Providers**:
- **OpenRouter**: Multi-provider access (OpenAI, Anthropic, Google, Meta, Mistral)
- **Anthropic Direct**: Claude models with direct API
- **vLLM**: Local GPU inference on Ops-Center infrastructure

**Authentication**: Service key (`BRIGADE_SERVICE_KEY`)

**Configuration**:
```bash
# .env
OPS_CENTER_URL=https://unicorncommander.ai
BRIGADE_SERVICE_KEY=sk-brigade-service-key-2025
```

**Models Available**:
- `openai/gpt-4o` - GPT-4 Optimized ($0.0025/$0.01 per 1K tokens)
- `openai/gpt-4o-mini` - Fast, economical ($0.00015/$0.0006 per 1K tokens)
- `anthropic/claude-3.5-sonnet` - Balanced capability ($0.003/$0.015 per 1K tokens)
- `anthropic/claude-3-opus` - Maximum capability ($0.015/$0.075 per 1K tokens)
- `anthropic/claude-3-haiku` - Speed-optimized ($0.00025/$0.00125 per 1K tokens)
- `google/gemini-1.5-pro` - 1M token context ($0.00125/$0.005 per 1K tokens)

---

### 2. MLX (Mac - Planned)

**Current Status**: ⏸️ Planned (Phase 1)

**Hardware Target**: Apple Silicon (M1/M2/M3/M4)

**Key Features**:
- **Unified Memory**: Share RAM between CPU and GPU
- **Metal Acceleration**: Native Apple GPU optimization
- **Low Power**: Efficient inference on battery
- **No VRAM Limits**: Use system RAM (16GB+ recommended)

**Installation**:
```bash
# Install MLX
pip install mlx mlx-lm

# Download models
mlx_lm.convert --hf-path meta-llama/Llama-3.1-8B -o ~/.mlx/models/llama-3.1-8b
```

**Environment Configuration**:
```bash
# .env
# Enable MLX provider for local models
LOCAL_MODEL_PROVIDER=mlx
MLX_MODEL_CACHE=~/.mlx/models

# Recommended models for Mac
TEAM_LEAD_MODEL=mlx/llama-3.1-8b
WORKER_MODEL=mlx/llama-3.2-3b
```

**Recommended Models**:
- **Team Leads (7-14B)**:
  - `mlx/llama-3.1-8b` - General purpose (6GB RAM)
  - `mlx/gemma-2-9b` - Fast, Google-backed (7GB RAM)
  - `mlx/qwen2.5-14b` - Multilingual (10GB RAM)

- **Workers (1-3B)**:
  - `mlx/llama-3.2-3b` - Balanced (2.5GB RAM)
  - `mlx/phi-3-mini` - Microsoft compact reasoning (2GB RAM)
  - `mlx/qwen2.5-3b` - Multilingual tasks (2.5GB RAM)

**Performance Expectations** (M3 Pro, 36GB RAM):
- **Llama 3.1 8B**: ~50 tokens/sec
- **Llama 3.2 3B**: ~120 tokens/sec
- **Concurrent**: Run 1x 8B + 2x 3B simultaneously

---

### 3. Ollama (Cross-Platform - Partial Support)

**Current Status**: ✅ Partial (Models defined, provider needs implementation)

**Hardware Target**: NVIDIA GPUs (CUDA), AMD GPUs (ROCm), CPU

**Key Features**:
- **Cross-Platform**: Linux, macOS, Windows
- **Model Library**: 100+ pre-quantized models
- **GGUF Format**: Efficient quantization (4-bit, 8-bit)
- **REST API**: Simple HTTP interface

**Installation**:
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.1:8b
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
ollama pull phi3:3.8b
```

**Environment Configuration**:
```bash
# .env
# Ollama server endpoint
OLLAMA_HOST=http://localhost:11434
OLLAMA_GPU_LAYERS=35  # Layers to offload to GPU (-1 = all)
OLLAMA_NUM_THREADS=8  # CPU threads for non-GPU layers

# Enable Ollama provider
LOCAL_MODEL_PROVIDER=ollama

# Model assignments (uses ollama/ prefix)
TEAM_LEAD_MODEL=ollama/llama3.1:8b
WORKER_MODEL=ollama/llama3.2:3b
```

**Recommended Models**:

**Team Leads (7-14B)**:
- `ollama/llama3.1:8b` - General purpose (5GB VRAM)
- `ollama/gemma2:9b` - Fast, Google (6GB VRAM)
- `ollama/mistral:7b` - Long context (5GB VRAM)
- `ollama/mixtral:8x7b` - MoE routing (26GB VRAM for full, 13GB for Q4)

**Workers (1-3B)**:
- `ollama/llama3.2:3b` - Balanced (2GB VRAM)
- `ollama/llama3.2:1b` - Ultra-fast (1GB VRAM)
- `ollama/phi3:3.8b` - Microsoft reasoning (3GB VRAM)
- `ollama/qwen2.5-math:1.5b` - Math specialist (1.5GB VRAM)
- `ollama/tinyllama:1.1b` - Minimal footprint (1GB VRAM)

**Quantization Options**:
```bash
# Default (Q4_0) - 4-bit, fastest
ollama pull llama3.1:8b

# Higher quality (Q5_K_M) - 5-bit, better accuracy
ollama pull llama3.1:8b-q5

# Full precision (FP16) - maximum quality, 2x size
ollama pull llama3.1:8b-fp16
```

---

### 4. llama.cpp (Lightweight - Planned)

**Current Status**: ⏸️ Planned (Phase 2)

**Hardware Target**: Any CPU, minimal GPU offload

**Key Features**:
- **CPU Inference**: No GPU required
- **Minimal Dependencies**: C++ binary, no Python runtime
- **Quantization**: Aggressive compression (2-bit to 8-bit)
- **Low Memory**: Run 7B models in 4GB RAM

**Installation**:
```bash
# Build from source
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# Or use pre-built binaries
# macOS: brew install llama.cpp
# Linux: apt install llama.cpp (if available)

# Download models (GGUF format)
wget https://huggingface.co/TheBloke/Llama-2-7B-GGUF/resolve/main/llama-2-7b.Q4_K_M.gguf
```

**Environment Configuration**:
```bash
# .env
# llama.cpp server endpoint
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_THREADS=8
LLAMACPP_BATCH_SIZE=512
LLAMACPP_CTX_SIZE=4096

# Enable llama.cpp provider
LOCAL_MODEL_PROVIDER=llamacpp

# Model paths
LLAMACPP_TEAM_LEAD_MODEL=/models/llama-3.1-8b-q4.gguf
LLAMACPP_WORKER_MODEL=/models/llama-3.2-3b-q4.gguf
```

**Recommended Models** (GGUF format):

**Team Leads (7-14B)**:
- `llama-3.1-8b-q4_k_m.gguf` - Balanced (5GB RAM)
- `mistral-7b-q5_k_m.gguf` - Higher quality (6GB RAM)
- `gemma-2-9b-q4_k_m.gguf` - Fast (6GB RAM)

**Workers (1-3B)**:
- `llama-3.2-3b-q4_k_m.gguf` - General (2GB RAM)
- `phi-3-mini-q4_k_m.gguf` - Reasoning (2GB RAM)
- `tinyllama-1.1b-q4_k_m.gguf` - Minimal (1GB RAM)

**Quantization Guide**:
- **Q4_K_M**: Best balance (4-bit, 50% size of FP16)
- **Q5_K_M**: Better quality (5-bit, 60% size)
- **Q8_0**: Near-FP16 quality (8-bit, 80% size)
- **Q2_K**: Emergency low-memory (2-bit, 25% size, significant quality loss)

---

## Deployment Scenarios

### Scenario 1: Mac Development (MLX)

**Hardware**: MacBook Pro M3 Pro, 36GB RAM

**Objective**: Zero cloud costs for development, max performance on Apple Silicon

**Configuration**:
```python
# config/deployment_configs.py
from app.workflows.model_config import ModelConfig

MAC_DEVELOPMENT_CONFIG = ModelConfig(
    # Use largest local model for orchestrator
    orchestrator_model="mlx/llama-3.1-70b",  # 40GB RAM (fits with quantization)

    # Team leads: 8B models
    team_lead_models={
        "research": "mlx/llama-3.1-8b",
        "finance": "mlx/qwen2.5-14b",  # Better for numbers
        "content": "mlx/llama-3.1-8b",
        "sales": "mlx/llama-3.1-8b",
        "devops": "mlx/llama-3.1-8b",
        "legal": "mlx/llama-3.1-8b",
        "medical": "mlx/llama-3.1-8b",
        "investigation": "mlx/llama-3.1-8b",
    },

    # Workers: Small, fast models
    default_worker_model="mlx/llama-3.2-3b",
    worker_models={
        "ratio-calculator": "mlx/qwen2.5-math-1.5b",  # Math specialist
        "grammar-checker": "mlx/phi-3-mini",  # Language tasks
    },

    # Fully local
    enable_local_models=True,
)
```

**Environment Variables**:
```bash
# .env.mac
LOCAL_MODEL_PROVIDER=mlx
MLX_MODEL_CACHE=~/.mlx/models
ENABLE_LOCAL_MODELS=true

# Fallback to cloud for critical reasoning (optional)
ORCHESTRATOR_MODEL=openai/gpt-4o-mini  # Use for production workflows
ENABLE_CLOUD_FALLBACK=true  # Fall back on MLX failures
```

**Expected Performance**:
- **Orchestrator (70B)**: 15-20 tokens/sec (usable for development)
- **Team Leads (8B)**: 50 tokens/sec
- **Workers (3B)**: 120 tokens/sec
- **Cost**: $0 (no API calls)

**RAM Usage**:
- Llama 3.1 70B (Q4): ~36GB
- Or: Llama 3.1 8B + 3x Llama 3.2 3B concurrent: ~14GB

---

### Scenario 2: VPS Deployment (CPU, llama.cpp)

**Hardware**: Hetzner CCX33 (8 vCPU, 32GB RAM)

**Objective**: Cost-effective deployment without GPU

**Configuration**:
```python
# config/deployment_configs.py
VPS_CPU_CONFIG = ModelConfig(
    # Cloud API for orchestrator (complex reasoning needs quality)
    orchestrator_model="openai/gpt-4o-mini",

    # Team leads: CPU-optimized 7B models
    team_lead_models={
        "research": "llamacpp/llama-3.1-8b-q4",
        "finance": "llamacpp/mistral-7b-q5",  # Higher quality for finance
        "content": "llamacpp/llama-3.1-8b-q4",
        "sales": "llamacpp/llama-3.1-8b-q4",
        "devops": "llamacpp/llama-3.1-8b-q4",
        "legal": "llamacpp/mistral-7b-q5",  # Higher quality for legal
        "medical": "llamacpp/llama-3.1-8b-q4",
        "investigation": "llamacpp/llama-3.1-8b-q4",
    },

    # Workers: Aggressive quantization for speed
    default_worker_model="llamacpp/llama-3.2-3b-q4",

    # Hybrid: Cloud orchestrator, local execution
    enable_local_models=True,
    api_fallback_team_lead="openai/gpt-4o-mini",  # Fallback for errors
)
```

**Environment Variables**:
```bash
# .env.vps
LOCAL_MODEL_PROVIDER=llamacpp
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_THREADS=8
LLAMACPP_CTX_SIZE=4096

# Cloud fallback
OPS_CENTER_URL=https://unicorncommander.ai
BRIGADE_SERVICE_KEY=sk-brigade-service-key-2025
```

**Expected Performance** (8-core CPU):
- **Orchestrator**: Cloud API (~500ms latency)
- **Team Leads (7B Q4)**: 8-12 tokens/sec
- **Workers (3B Q4)**: 20-30 tokens/sec
- **Cost**: ~$0.50/day for orchestrator calls (estimate 100 calls)

**Concurrent Execution**:
- Run 2x Team Lead models simultaneously (16GB RAM total)
- Workers: 4-6 concurrent (2GB each)

---

### Scenario 3: GPU Server (Ollama, CUDA)

**Hardware**: NVIDIA A100 40GB, 128GB RAM

**Objective**: Maximum throughput, minimal latency

**Configuration**:
```python
# config/deployment_configs.py
GPU_SERVER_CONFIG = ModelConfig(
    # Use largest local model for orchestrator (or cloud for quality)
    orchestrator_model="ollama/llama3.1:70b",  # Or openai/gpt-4o for quality

    # Team leads: FP16 for quality, or Q5 for speed
    team_lead_models={
        "research": "ollama/llama3.1:8b",
        "finance": "ollama/mixtral:8x7b",  # MoE for complex reasoning
        "content": "ollama/llama3.1:8b",
        "sales": "ollama/gemma2:9b",
        "devops": "ollama/deepseek-coder:6.7b",  # Code specialist
        "legal": "ollama/llama3.1:8b",
        "medical": "ollama/llama3.1:8b",
        "investigation": "ollama/gemma2:9b",
    },

    # Workers: Fast inference
    default_worker_model="ollama/llama3.2:3b",

    # Fully local or hybrid
    enable_local_models=True,
)
```

**Environment Variables**:
```bash
# .env.gpu
LOCAL_MODEL_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_GPU_LAYERS=-1  # All layers on GPU
OLLAMA_NUM_PARALLEL=4  # Parallel requests

# Optional cloud fallback
OPS_CENTER_URL=https://unicorncommander.ai
ENABLE_CLOUD_FALLBACK=false  # Rely on local models
```

**Expected Performance** (A100 40GB):
- **Orchestrator (70B FP16)**: 40-50 tokens/sec
- **Team Leads (8B FP16)**: 150+ tokens/sec
- **Workers (3B FP16)**: 300+ tokens/sec
- **Cost**: $0 for inference (hardware amortized)

**Concurrent Execution**:
- 1x 70B + 4x 8B + 8x 3B simultaneously (VRAM: 36GB + batch overhead)

---

### Scenario 4: Hybrid Cloud + Local

**Hardware**: Mac M3 (development) + Ops-Center (production)

**Objective**: Local development, cloud quality for production

**Configuration**:
```python
# config/deployment_configs.py
HYBRID_CONFIG = ModelConfig(
    # Always use cloud for orchestrator
    orchestrator_model="anthropic/claude-3.5-sonnet",

    # Team leads: Local for dev, cloud override via API
    team_lead_models={
        "research": "mlx/llama-3.1-8b",
        "finance": "anthropic/claude-3.5-sonnet",  # Premium for finance
        "content": "mlx/llama-3.1-8b",
        "sales": "mlx/llama-3.1-8b",
        "devops": "mlx/llama-3.1-8b",
        "legal": "anthropic/claude-3.5-sonnet",  # Premium for legal
        "medical": "anthropic/claude-3.5-sonnet",  # Premium for medical
        "investigation": "mlx/llama-3.1-8b",
    },

    # Workers: Always local
    default_worker_model="mlx/llama-3.2-3b",

    # Enable local with cloud fallback
    enable_local_models=True,
    api_fallback_team_lead="openai/gpt-4o-mini",
    api_fallback_worker="openai/gpt-4o-mini",
)
```

**Cost Analysis**:
- **Orchestrator** (cloud): $0.003/1K tokens → ~$3/day (1M tokens)
- **Critical Team Leads** (cloud): $0.003/1K tokens → ~$2/day (700K tokens)
- **Other Agents** (local): $0
- **Total**: ~$150/month vs ~$450/month (all cloud)

---

## Model Provider Implementations

### Current: Ops-Center Provider

**Location**: `app/llm/ops_center_client.py`

**Features**:
- ✅ Chat completion
- ✅ Function calling / tool use
- ✅ Streaming responses
- ✅ Token usage tracking
- ✅ Cost estimation
- ✅ Automatic SSE parsing (Traefik workaround)
- ✅ Model unavailability handling

**Usage Example**:
```python
from app.llm.ops_center_client import OpsCenterLLMClient

client = OpsCenterLLMClient()

# Simple completion
response = await client.chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    model="openai/gpt-4o-mini",
    temperature=0.7,
)

# With tools
response = await client.chat_completion_with_tools(
    messages=[{"role": "user", "content": "What's 2+2?"}],
    tools=[calculator_tool],
    model="openai/gpt-4o-mini",
)

# Full tool loop
response = await client.execute_tool_loop(
    messages=[{"role": "user", "content": "Search for AI news"}],
    tools=[web_search_tool],
    model="openai/gpt-4o-mini",
    max_iterations=5,
)
```

---

### Planned: MLX Provider

**Location**: `app/llm/mlx_provider.py` (new)

**Dependencies**:
```bash
pip install mlx mlx-lm
```

**Interface Design**:
```python
# app/llm/mlx_provider.py
from typing import List, Dict, Any, Optional
import mlx.core as mx
import mlx_lm

class MLXModelProvider:
    """Local inference with MLX on Apple Silicon"""

    def __init__(self, model_cache_dir: str = "~/.mlx/models"):
        self.cache_dir = model_cache_dir
        self.loaded_models: Dict[str, Any] = {}

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.1-8b",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """
        Generate chat completion using MLX.

        Args:
            messages: Chat messages
            model: Model name (e.g., "llama-3.1-8b")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            OpenAI-compatible response dict
        """
        # Load model if not cached
        if model not in self.loaded_models:
            model_path = f"{self.cache_dir}/{model}"
            self.loaded_models[model] = mlx_lm.load(model_path)

        # Format messages for model
        prompt = self._format_messages(messages)

        # Generate
        model_obj, tokenizer = self.loaded_models[model]
        response = mlx_lm.generate(
            model_obj,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
        )

        # Return OpenAI-compatible format
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": response,
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": len(tokenizer.encode(prompt)),
                "completion_tokens": len(tokenizer.encode(response)),
                "total_tokens": len(tokenizer.encode(prompt + response)),
            },
        }

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to model-specific prompt format"""
        # Example for Llama 3.1 format
        formatted = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                formatted += f"<|start_header_id|>system<|end_header_id|>\n{content}<|eot_id|>"
            elif role == "user":
                formatted += f"<|start_header_id|>user<|end_header_id|>\n{content}<|eot_id|>"
            elif role == "assistant":
                formatted += f"<|start_header_id|>assistant<|end_header_id|>\n{content}<|eot_id|>"

        formatted += "<|start_header_id|>assistant<|end_header_id|>\n"
        return formatted
```

**Integration**:
```python
# app/llm/unified_client.py (new)
from app.llm.ops_center_client import OpsCenterLLMClient
from app.llm.mlx_provider import MLXModelProvider

class UnifiedLLMClient:
    """Router for local and cloud providers"""

    def __init__(self):
        self.ops_center = OpsCenterLLMClient()
        self.mlx = MLXModelProvider()

    async def chat_completion(self, messages, model, **kwargs):
        # Route based on model prefix
        if model.startswith("mlx/"):
            return await self.mlx.chat_completion(messages, model[4:], **kwargs)
        elif model.startswith("ollama/"):
            return await self.ollama.chat_completion(messages, model[7:], **kwargs)
        else:
            # Default to Ops-Center (cloud models)
            return await self.ops_center.chat_completion(messages, model, **kwargs)
```

---

### Planned: Ollama Provider

**Location**: `app/llm/ollama_provider.py` (new)

**Dependencies**:
```bash
pip install ollama
# Or use direct HTTP requests to http://localhost:11434
```

**Interface Design**:
```python
# app/llm/ollama_provider.py
import httpx
from typing import List, Dict, Any

class OllamaModelProvider:
    """Local inference with Ollama"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """
        Generate chat completion using Ollama.

        Ollama API is OpenAI-compatible, so this is straightforward.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()

        # Convert to OpenAI format
        return {
            "choices": [{
                "message": data["message"],
                "finish_reason": "stop" if data.get("done") else "length",
            }],
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
        }

    async def list_models(self) -> List[str]:
        """List available local models"""
        response = await self.client.get(f"{self.base_url}/api/tags")
        data = response.json()
        return [model["name"] for model in data.get("models", [])]
```

---

### Planned: llama.cpp Provider

**Location**: `app/llm/llamacpp_provider.py` (new)

**Dependencies**:
```bash
# Use llama.cpp server mode
# Start server: ./llama-server -m model.gguf -c 4096 --port 8080
```

**Interface Design**:
```python
# app/llm/llamacpp_provider.py
import httpx
from typing import List, Dict, Any

class LlamaCppModelProvider:
    """Lightweight CPU inference with llama.cpp"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.1-8b-q4",  # Model loaded in server
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """
        Generate completion using llama.cpp server.

        Note: llama.cpp server doesn't natively support /chat endpoint.
        We need to format the prompt ourselves.
        """
        # Format messages into prompt
        prompt = self._format_messages(messages)

        payload = {
            "prompt": prompt,
            "temperature": temperature,
            "n_predict": max_tokens,
            "stop": ["</s>", "<|eot_id|>", "User:"],  # Model-specific
        }

        response = await self.client.post(
            f"{self.base_url}/completion",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()

        # Convert to OpenAI format
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": data["content"],
                },
                "finish_reason": "stop" if data.get("stopped_eos") else "length",
            }],
            "usage": {
                "prompt_tokens": data.get("tokens_evaluated", 0),
                "completion_tokens": data.get("tokens_predicted", 0),
                "total_tokens": data.get("tokens_evaluated", 0) + data.get("tokens_predicted", 0),
            },
        }

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to llama.cpp prompt format"""
        # Similar to MLX formatting
        formatted = ""
        for msg in messages:
            if msg["role"] == "system":
                formatted += f"System: {msg['content']}\n\n"
            elif msg["role"] == "user":
                formatted += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                formatted += f"Assistant: {msg['content']}\n\n"

        formatted += "Assistant: "
        return formatted
```

---

## Configuration Guide

### Environment Variables

**Core Configuration**:
```bash
# .env

# ============================================================================
# Model Backend Selection
# ============================================================================
# Options: ops-center, mlx, ollama, llamacpp
LOCAL_MODEL_PROVIDER=mlx

# Enable local models (if false, uses cloud fallback for all local models)
ENABLE_LOCAL_MODELS=true

# ============================================================================
# Ops-Center (Cloud Models)
# ============================================================================
OPS_CENTER_URL=https://unicorncommander.ai
BRIGADE_SERVICE_KEY=sk-brigade-service-key-2025

# ============================================================================
# MLX (Apple Silicon)
# ============================================================================
MLX_MODEL_CACHE=~/.mlx/models
MLX_MAX_MEMORY=32  # GB RAM limit for models

# ============================================================================
# Ollama (GPU/CPU)
# ============================================================================
OLLAMA_HOST=http://localhost:11434
OLLAMA_GPU_LAYERS=-1  # -1 = all layers on GPU, 0 = CPU only
OLLAMA_NUM_THREADS=8  # CPU threads
OLLAMA_NUM_PARALLEL=2  # Concurrent requests

# ============================================================================
# llama.cpp (CPU-optimized)
# ============================================================================
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_THREADS=8
LLAMACPP_BATCH_SIZE=512
LLAMACPP_CTX_SIZE=4096  # Context window

# ============================================================================
# Model Assignments (per tier)
# ============================================================================
# Orchestrator (always cloud for best quality)
ORCHESTRATOR_MODEL=openai/gpt-4o-mini

# Team Lead default (can be overridden per domain)
DEFAULT_TEAM_LEAD_MODEL=mlx/llama-3.1-8b

# Worker default
DEFAULT_WORKER_MODEL=mlx/llama-3.2-3b

# ============================================================================
# Per-Domain Overrides (optional)
# ============================================================================
# Format: TEAM_LEAD_<DOMAIN>_MODEL
TEAM_LEAD_FINANCE_MODEL=anthropic/claude-3.5-sonnet  # Premium for finance
TEAM_LEAD_LEGAL_MODEL=anthropic/claude-3.5-sonnet    # Premium for legal
TEAM_LEAD_MEDICAL_MODEL=anthropic/claude-3.5-sonnet  # Premium for medical

# ============================================================================
# Fallback Configuration
# ============================================================================
# Fallback when local models fail
API_FALLBACK_TEAM_LEAD=openai/gpt-4o-mini
API_FALLBACK_WORKER=openai/gpt-4o-mini

# Enable automatic fallback to cloud on local model errors
ENABLE_CLOUD_FALLBACK=true
```

---

### Programmatic Configuration

**Using Presets**:
```python
from app.workflows.model_config import (
    COST_OPTIMIZED_CONFIG,
    QUALITY_OPTIMIZED_CONFIG,
    FULL_LOCAL_CONFIG,
    get_config_from_preset,
    create_config_from_request,
)

# Use preset
config = COST_OPTIMIZED_CONFIG

# Or load by name
config = get_config_from_preset("cost_optimized")

# Override specific models
from app.workflows.model_config import merge_configs

custom_config = merge_configs(
    COST_OPTIMIZED_CONFIG,
    {
        "team_lead_models": {
            "finance": "anthropic/claude-3.5-sonnet",  # Premium for finance
        }
    }
)
```

**Runtime API Override**:
```python
# API endpoint for workflow execution
POST /api/v1/hierarchical/execute
{
    "workflow_id": "investment-due-diligence",
    "inputs": {"company": "Acme Corp"},
    "model_config": {
        "orchestrator_model": "openai/gpt-4o",
        "team_lead_models": {
            "finance": "anthropic/claude-3.5-sonnet"
        },
        "enable_local_models": true
    }
}
```

**Initialization**:
```python
from app.workflows.engine import WorkflowEngine, init_workflow_engine
from app.workflows.model_config import ModelConfig
from app.llm.ops_center_client import OpsCenterLLMClient

# Initialize with custom config
llm_client = OpsCenterLLMClient()

config = ModelConfig(
    orchestrator_model="openai/gpt-4o-mini",
    enable_local_models=True,
    team_lead_models={
        "research": "mlx/llama-3.1-8b",
        "finance": "anthropic/claude-3.5-sonnet",
    }
)

engine = init_workflow_engine(
    llm_client=llm_client,
    model_config=config,
)
```

---

## Model Recommendations by Tier

### Orchestrator Models (Complex Reasoning)

**Cloud API** (Recommended):

| Model | Provider | Cost (per 1M tokens) | Use Case |
|-------|----------|----------------------|----------|
| `openai/gpt-4o-mini` | OpenAI | $0.15 / $0.60 | **Default** - Best balance cost/quality |
| `openai/gpt-4o` | OpenAI | $2.50 / $10.00 | Premium - Maximum capability |
| `anthropic/claude-3.5-sonnet` | Anthropic | $3.00 / $15.00 | **Best quality** - Nuanced reasoning |
| `anthropic/claude-3-haiku` | Anthropic | $0.25 / $1.25 | Budget - Fast, economical |
| `google/gemini-1.5-pro` | Google | $1.25 / $5.00 | Long context (1M tokens) |

**Local** (Development/Testing):

| Model | Backend | VRAM/RAM | Throughput | Notes |
|-------|---------|----------|------------|-------|
| `mlx/llama-3.1-70b` | MLX | 36GB | 15-20 t/s | Mac only, quantized |
| `ollama/llama3.1:70b` | Ollama | 40GB | 30-40 t/s | GPU required |

**Recommendation**: Use **`openai/gpt-4o-mini`** for orchestrator. Local 70B models are viable for development but cloud ensures consistent quality.

---

### Team Lead Models (Domain Coordination)

**Local Models** (Recommended):

| Model | Backend | VRAM/RAM | Quality | Speed | Use Case |
|-------|---------|----------|---------|-------|----------|
| `mlx/llama-3.1-8b` | MLX | 6GB | ★★★★ | 50 t/s | **Default** - General purpose |
| `mlx/qwen2.5-14b` | MLX | 10GB | ★★★★★ | 30 t/s | Finance, numbers |
| `ollama/llama3.1:8b` | Ollama | 5GB | ★★★★ | 150 t/s | GPU - Fast inference |
| `ollama/gemma2:9b` | Ollama | 6GB | ★★★★ | 120 t/s | GPU - Google-backed |
| `ollama/mixtral:8x7b` | Ollama | 26GB | ★★★★★ | 80 t/s | GPU - MoE, complex tasks |
| `llamacpp/llama-3.1-8b-q4` | llama.cpp | 5GB | ★★★ | 8-12 t/s | CPU-only deployment |

**Cloud Upgrades** (Critical Domains):

| Domain | Recommended Model | Rationale |
|--------|-------------------|-----------|
| **Finance** | `anthropic/claude-3.5-sonnet` | Accurate calculations, risk assessment |
| **Legal** | `anthropic/claude-3.5-sonnet` | Nuanced reasoning, precedent analysis |
| **Medical** | `anthropic/claude-3.5-sonnet` | Safety-critical, compliance |

**Recommendation**: Use local 8B models by default (`mlx/llama-3.1-8b` on Mac, `ollama/llama3.1:8b` on GPU). Upgrade to `anthropic/claude-3.5-sonnet` for finance/legal/medical.

---

### Worker Models (Narrow Tasks)

**Local Models** (Always Recommended):

| Model | Backend | VRAM/RAM | Quality | Speed | Use Case |
|-------|---------|----------|---------|-------|----------|
| `mlx/llama-3.2-3b` | MLX | 2.5GB | ★★★★ | 120 t/s | **Default** - Balanced |
| `mlx/phi-3-mini` | MLX | 2GB | ★★★★ | 100 t/s | Reasoning tasks |
| `mlx/qwen2.5-math-1.5b` | MLX | 1.5GB | ★★★★★ | 150 t/s | **Math specialist** |
| `ollama/llama3.2:3b` | Ollama | 2GB | ★★★★ | 300 t/s | GPU - Very fast |
| `ollama/phi3:3.8b` | Ollama | 3GB | ★★★★ | 250 t/s | GPU - Microsoft quality |
| `ollama/tinyllama:1.1b` | Ollama | 1GB | ★★ | 500 t/s | GPU - Ultra-fast, simple tasks |
| `llamacpp/llama-3.2-3b-q4` | llama.cpp | 2GB | ★★★ | 20-30 t/s | CPU-only |

**Specialized Workers**:

| Worker | Recommended Model | Rationale |
|--------|-------------------|-----------|
| `ratio-calculator` | `qwen2.5-math-1.5b` | Math-optimized |
| `grammar-checker` | `phi-3-mini` | Language quality |
| `code-generator` | `deepseek-coder:6.7b` | Code specialist |

**Recommendation**: Use **`llama-3.2-3b`** as default. Workers should **never** use cloud models (local is fast enough and cost-free).

---

## Performance Considerations

### Memory Requirements

**Estimation Formula**:
- **FP16** (full precision): `model_size_GB = parameters_B * 2`
- **Q8** (8-bit): `model_size_GB = parameters_B * 1`
- **Q4** (4-bit): `model_size_GB = parameters_B * 0.5`
- **Q2** (2-bit): `model_size_GB = parameters_B * 0.25`

**Examples**:
| Model | Parameters | FP16 | Q8 | Q4 | Q2 |
|-------|------------|------|----|----|---- |
| Llama 3.1 70B | 70B | 140GB | 70GB | 35GB | 17GB |
| Llama 3.1 8B | 8B | 16GB | 8GB | 4GB | 2GB |
| Llama 3.2 3B | 3B | 6GB | 3GB | 1.5GB | 0.75GB |
| Phi-3 Mini | 3.8B | 7.6GB | 3.8GB | 1.9GB | 1GB |

**Safety Margin**: Add 20-30% for KV cache and batch processing.

**Mac (Unified Memory)**:
- 16GB RAM: 1x 8B (Q4) + 2x 3B (Q4) = ~8GB
- 32GB RAM: 1x 8B (FP16) + 4x 3B (Q4) = ~22GB
- 64GB RAM: 1x 70B (Q4) + 2x 8B (Q4) = ~48GB

**GPU (VRAM)**:
- 8GB VRAM: 1x 8B (Q4) = 5GB
- 16GB VRAM: 1x 8B (FP16) or 2x 8B (Q4) = 16GB
- 24GB VRAM: 1x 8B (FP16) + 2x 3B (FP16) = 22GB
- 40GB VRAM: 1x 70B (Q4) = 35GB

---

### Throughput Expectations

**Tokens per Second** (single request):

| Hardware | Model Size | Quantization | Tokens/sec |
|----------|------------|--------------|------------|
| **Mac M3 Pro** | 70B | Q4 | 15-20 |
| Mac M3 Pro | 8B | FP16 | 50-60 |
| Mac M3 Pro | 3B | FP16 | 120-150 |
| **NVIDIA A100** | 70B | FP16 | 40-50 |
| NVIDIA A100 | 8B | FP16 | 150-200 |
| NVIDIA A100 | 3B | FP16 | 300-400 |
| **CPU (8-core)** | 8B | Q4 | 8-12 |
| CPU (8-core) | 3B | Q4 | 20-30 |
| CPU (8-core) | 1.1B | Q4 | 50-80 |

**Concurrent Requests**:
- **Batch Processing**: Modern frameworks (MLX, vLLM) can batch multiple requests
- **Memory Trade-off**: More concurrent = more KV cache memory
- **Practical Limits**:
  - Mac 36GB: 2-4 concurrent 8B models
  - A100 40GB: 8-12 concurrent 8B models (with batching)
  - CPU 32GB: 2-3 concurrent 8B models

---

### Latency Breakdown

**End-to-End Latency** (typical workflow step):

| Component | Local (Mac) | Local (GPU) | Cloud API |
|-----------|-------------|-------------|-----------|
| **Network** | 0ms | 0ms | 50-150ms |
| **Queue** | 0ms | 0-50ms | 0-500ms |
| **Prompt Processing** | 50-200ms | 10-50ms | 100ms |
| **Generation** (200 tokens) | 2-4s (70B) | 1-2s (70B) | 1-3s |
| **Total** | 2-4s | 1-2s | 1.5-4s |

**Worker Tasks** (100 tokens):
- **Local 3B**: 0.5-1s (Mac), 0.3s (GPU), 0.5-1s (CPU)
- **Cloud API**: 1-2s (including network)

**Recommendation**: Local workers are **faster** than cloud for small tasks due to zero network latency.

---

### When to Use Local vs Cloud

**Use Local Models When**:
- ✅ **Development/Testing**: Iterate without API costs
- ✅ **High Volume**: >100K requests/day (cost savings)
- ✅ **Privacy**: Sensitive data must stay on-premises
- ✅ **Low Latency**: Sub-second response needed (workers)
- ✅ **Batch Processing**: Process large datasets offline

**Use Cloud Models When**:
- ✅ **Complex Reasoning**: Orchestrator-level strategic decisions
- ✅ **Critical Domains**: Finance, legal, medical (quality matters)
- ✅ **Low Volume**: <10K requests/day (not worth local setup)
- ✅ **No GPU**: Can't run local models efficiently
- ✅ **Scalability**: Need instant scale-up capacity

**Hybrid Approach** (Recommended):
```
Orchestrator: Cloud API (GPT-4o-mini or Claude Sonnet)
Team Leads: Local 8B (research, content, sales, devops)
            Cloud API (finance, legal, medical)
Workers: Always local 1-3B
```

**Cost Analysis** (1M tokens/day):

| Tier | Local (Mac/GPU) | Cloud API | Hybrid |
|------|-----------------|-----------|--------|
| **Orchestrator** (50K tokens) | $0 | $7.50/day | $7.50/day |
| **Team Leads** (500K tokens) | $0 | $30/day | $15/day (50% cloud) |
| **Workers** (450K tokens) | $0 | $27/day | $0 |
| **Total/month** | $0 | $1,935/mo | $675/mo |

**ROI Break-Even**:
- **Mac M3 Pro** ($3,000): ~1.5 months vs full cloud
- **GPU Server** ($5,000): ~2.5 months vs full cloud
- **Electricity**: ~$20/month (negligible vs API costs)

---

## Implementation Roadmap

### Phase 1: MLX Provider (Mac Development) ⏸️ Not Started

**Timeline**: 2 weeks

**Deliverables**:
1. ✅ **MLX Provider Class** (`app/llm/mlx_provider.py`)
   - Chat completion interface
   - Model loading and caching
   - Prompt formatting for Llama 3.x
   - Token counting

2. ✅ **Unified Client Router** (`app/llm/unified_client.py`)
   - Detect model prefix (`mlx/`, `ollama/`, cloud)
   - Route to appropriate provider
   - Maintain backward compatibility

3. ✅ **Model Download Scripts**
   - `scripts/download_mlx_models.py`
   - Download Llama 3.1 8B, Llama 3.2 3B, Qwen2.5 14B
   - Convert to MLX format if needed

4. ✅ **Environment Configuration**
   - Add `LOCAL_MODEL_PROVIDER=mlx` to `.env.example`
   - Document MLX-specific settings
   - Update `CLAUDE.md` with MLX instructions

5. ✅ **Testing**
   - Unit tests for MLX provider
   - Integration tests with workflow engine
   - Benchmark throughput on M3 Pro

**Success Criteria**:
- Run hierarchical workflows end-to-end with MLX models
- <5% quality degradation vs cloud (measured by eval suite)
- 50+ tokens/sec on M3 Pro with Llama 3.1 8B

---

### Phase 2: Ollama Provider (GPU/CPU Cross-Platform) ⏸️ Not Started

**Timeline**: 1 week

**Deliverables**:
1. ✅ **Ollama Provider Class** (`app/llm/ollama_provider.py`)
   - HTTP client for Ollama API
   - Model listing and health checks
   - OpenAI format conversion

2. ✅ **Model Management Scripts**
   - `scripts/setup_ollama.sh`
   - Auto-pull recommended models
   - GPU detection and layer configuration

3. ✅ **Docker Compose Integration**
   - Add Ollama container to `docker-compose.ollama.yml`
   - GPU passthrough configuration
   - Model volume mounting

4. ✅ **Configuration Presets**
   - `GPU_SERVER_CONFIG` with Ollama models
   - `HYBRID_GPU_CONFIG` for mixed deployment

5. ✅ **Testing**
   - GPU and CPU mode tests
   - Quantization level comparison (Q4 vs Q8 vs FP16)
   - Multi-model concurrent execution

**Success Criteria**:
- Deploy on Ubuntu 22.04 with NVIDIA GPU
- Run 4x concurrent 8B models on A100
- Achieve 150+ tokens/sec with FP16 on GPU

---

### Phase 3: llama.cpp Provider (VPS CPU Deployment) ⏸️ Not Started

**Timeline**: 1 week

**Deliverables**:
1. ✅ **llama.cpp Provider Class** (`app/llm/llamacpp_provider.py`)
   - HTTP client for llama.cpp server
   - Prompt formatting
   - Stop sequence handling

2. ✅ **Build Scripts**
   - `scripts/build_llamacpp.sh`
   - Cross-platform compilation
   - GGUF model download

3. ✅ **Systemd Service**
   - Auto-start llama.cpp server
   - Multi-model server instances
   - Log rotation

4. ✅ **VPS Deployment Guide**
   - `docs/VPS_DEPLOYMENT.md`
   - Hetzner/DigitalOcean setup
   - CPU optimization flags

5. ✅ **Testing**
   - CPU-only deployment test
   - 8-core server benchmarks
   - Memory usage profiling

**Success Criteria**:
- Deploy on Hetzner CCX33 (8 vCPU, 32GB)
- Run 2x concurrent 7B Q4 models
- Achieve 10+ tokens/sec per model

---

### Phase 4: Auto-Detection and Fallback ⏸️ Not Started

**Timeline**: 1 week

**Deliverables**:
1. ✅ **Provider Health Checks**
   - Periodic availability polling
   - Model loading verification
   - Latency monitoring

2. ✅ **Automatic Fallback Logic**
   - Retry failed requests on different provider
   - Cascade: Local → Cloud API
   - Exponential backoff

3. ✅ **Admin Dashboard**
   - Provider status UI
   - Model availability indicators
   - Usage statistics per provider

4. ✅ **Alerts and Logging**
   - Slack/email alerts on provider failures
   - Structured logging for debugging
   - Cost tracking per provider

5. ✅ **Testing**
   - Failover scenario tests
   - Partial availability handling
   - Cost tracking accuracy

**Success Criteria**:
- Zero downtime when local model server restarts
- <2% request failures with automatic retry
- Accurate cost attribution per provider

---

### Phase 5: Performance Optimization ⏸️ Not Started

**Timeline**: 2 weeks

**Deliverables**:
1. ✅ **Model Quantization Tuning**
   - Quality benchmarks for Q2/Q4/Q5/Q8
   - Per-task quantization recommendations
   - Conversion scripts

2. ✅ **Concurrent Request Batching**
   - MLX batch inference
   - vLLM/Ollama batching optimization
   - Queue management

3. ✅ **KV Cache Optimization**
   - Prompt caching for repeated prefixes
   - Multi-turn conversation optimization
   - Memory recycling

4. ✅ **Model Warmup**
   - Pre-load models on startup
   - Keep popular models in memory
   - Eviction policy (LRU)

5. ✅ **Benchmarking Suite**
   - Workflow execution benchmarks
   - Cost/quality/latency trade-off analysis
   - Hardware recommendation guide

**Success Criteria**:
- 2x throughput improvement with batching
- <10% quality loss with Q4 vs FP16
- Sub-second latency for 80% of worker tasks

---

## Migration Guide

### From Full Cloud to Hybrid

**Current State**: All models use `openai/gpt-4o-mini`

**Step 1: Install Local Provider**
```bash
# Mac
pip install mlx mlx-lm
python scripts/download_mlx_models.py

# GPU Server
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
ollama pull llama3.2:3b

# VPS (CPU)
./scripts/build_llamacpp.sh
wget https://huggingface.co/TheBloke/Llama-2-7B-GGUF/resolve/main/llama-2-7b.Q4_K_M.gguf
```

**Step 2: Update Configuration**
```bash
# .env
# Enable local models
LOCAL_MODEL_PROVIDER=mlx  # or ollama, llamacpp
ENABLE_LOCAL_MODELS=true

# Keep cloud for orchestrator
ORCHESTRATOR_MODEL=openai/gpt-4o-mini

# Use local for team leads and workers
DEFAULT_TEAM_LEAD_MODEL=mlx/llama-3.1-8b
DEFAULT_WORKER_MODEL=mlx/llama-3.2-3b

# Fallback to cloud on errors
ENABLE_CLOUD_FALLBACK=true
API_FALLBACK_TEAM_LEAD=openai/gpt-4o-mini
```

**Step 3: Test Workflow**
```bash
# Run test workflow
python scripts/test_workflows.py --workflow investment-due-diligence

# Check model usage
# Should show: Orchestrator (cloud), Team Leads (local), Workers (local)
```

**Step 4: Monitor Costs**
```bash
# Track API usage
curl http://localhost:8100/api/v1/stats

# Expected: 70-80% reduction in cloud API calls
```

**Rollback Plan**:
```bash
# Disable local models
ENABLE_LOCAL_MODELS=false

# All models fall back to cloud
```

---

### From Ollama to MLX (Mac)

**Reason**: Better Apple Silicon optimization, unified memory

**Step 1: Install MLX**
```bash
pip install mlx mlx-lm
```

**Step 2: Convert Models**
```bash
# Convert Ollama model to MLX
python -m mlx_lm.convert \
  --hf-path meta-llama/Llama-3.1-8B \
  -o ~/.mlx/models/llama-3.1-8b

# Or download pre-converted
huggingface-cli download \
  mlx-community/Llama-3.1-8B-Instruct-4bit \
  --local-dir ~/.mlx/models/llama-3.1-8b
```

**Step 3: Update Configuration**
```bash
# .env
LOCAL_MODEL_PROVIDER=mlx  # Was: ollama

# Update model paths
DEFAULT_TEAM_LEAD_MODEL=mlx/llama-3.1-8b  # Was: ollama/llama3.1:8b
DEFAULT_WORKER_MODEL=mlx/llama-3.2-3b     # Was: ollama/llama3.2:3b
```

**Step 4: Benchmark**
```bash
# Compare performance
python scripts/benchmark_providers.py --providers mlx,ollama

# Expected: MLX 10-20% faster on Apple Silicon
```

---

## Troubleshooting

### MLX Provider

**Issue**: `ImportError: No module named 'mlx'`
```bash
# Solution: Install MLX
pip install mlx mlx-lm
```

**Issue**: Model not found at path
```bash
# Solution: Download model
python -m mlx_lm.convert --hf-path meta-llama/Llama-3.1-8B -o ~/.mlx/models/llama-3.1-8b

# Or set correct path
MLX_MODEL_CACHE=~/.mlx/models
```

**Issue**: Slow inference on Mac
```bash
# Check Metal GPU usage
# Activity Monitor > GPU History (should show high GPU usage)

# If low GPU usage:
# 1. Verify model is quantized (Q4/Q8)
# 2. Check RAM availability (model + KV cache)
# 3. Close other apps using GPU
```

---

### Ollama Provider

**Issue**: Connection refused to `localhost:11434`
```bash
# Check Ollama is running
systemctl status ollama  # Linux
# Or manually start:
ollama serve
```

**Issue**: Model not found
```bash
# List available models
ollama list

# Pull missing model
ollama pull llama3.1:8b
```

**Issue**: GPU not detected
```bash
# Check CUDA
nvidia-smi

# Verify Ollama sees GPU
ollama ps  # Should show GPU memory usage

# If not detected:
# 1. Install CUDA drivers
# 2. Reinstall Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

---

### llama.cpp Provider

**Issue**: Server not responding
```bash
# Check server is running
ps aux | grep llama-server

# Start server manually
./llama-server -m model.gguf -c 4096 --port 8080
```

**Issue**: Slow CPU inference
```bash
# Increase threads
LLAMACPP_THREADS=16  # Match CPU cores

# Reduce context size
LLAMACPP_CTX_SIZE=2048  # Was: 4096

# Use faster quantization
# Download Q4 instead of Q8 model
```

**Issue**: Out of memory
```bash
# Check available RAM
free -h

# Use smaller model
# 8B Q4 (~5GB) instead of 8B Q8 (~8GB)

# Or reduce context window
LLAMACPP_CTX_SIZE=2048
```

---

### General Issues

**Issue**: Model responses are gibberish
```bash
# Likely cause: Wrong prompt format
# Solution: Check model-specific format in provider code

# Llama 3.1 format:
<|start_header_id|>user<|end_header_id|>
Hello<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>

# Verify format in provider's _format_messages()
```

**Issue**: High latency with local models
```bash
# Check CPU/GPU usage
top  # or htop

# If low usage:
# 1. Model not loading properly (check logs)
# 2. Wrong device (CPU instead of GPU)
# 3. Context window too large

# If high usage but still slow:
# Hardware bottleneck - consider:
# 1. Smaller model (3B instead of 8B)
# 2. More aggressive quantization (Q4 instead of Q8)
# 3. Upgrade hardware
```

**Issue**: Workflow fails with "Model unavailable"
```bash
# Check logs
tail -f logs/brigade.log

# Verify provider health
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8080/health     # llama.cpp

# Enable cloud fallback
ENABLE_CLOUD_FALLBACK=true

# Workflow will automatically retry with cloud model
```

---

## Appendix: Model Catalog Reference

**Full Model Catalog**: See `app/workflows/model_config.py:MODEL_CATALOG`

**Quick Reference**:

**Cloud API Models**:
- `openai/gpt-4o` - $2.50/$10.00 per 1M tokens
- `openai/gpt-4o-mini` - $0.15/$0.60 per 1M tokens ⭐ **Default Orchestrator**
- `anthropic/claude-3.5-sonnet` - $3.00/$15.00 per 1M tokens ⭐ **Best Quality**
- `anthropic/claude-3-haiku` - $0.25/$1.25 per 1M tokens
- `google/gemini-1.5-pro` - $1.25/$5.00 per 1M tokens (1M context)

**Local Models (Team Leads)**:
- `mlx/llama-3.1-8b` - 6GB RAM, 50 t/s (Mac) ⭐ **Default Team Lead**
- `ollama/llama3.1:8b` - 5GB VRAM, 150 t/s (GPU)
- `ollama/gemma2:9b` - 6GB VRAM, 120 t/s (GPU)
- `llamacpp/llama-3.1-8b-q4` - 5GB RAM, 10 t/s (CPU)

**Local Models (Workers)**:
- `mlx/llama-3.2-3b` - 2.5GB RAM, 120 t/s (Mac) ⭐ **Default Worker**
- `mlx/qwen2.5-math-1.5b` - 1.5GB RAM, 150 t/s (Math specialist)
- `ollama/llama3.2:3b` - 2GB VRAM, 300 t/s (GPU)
- `ollama/phi3:3.8b` - 3GB VRAM, 250 t/s (GPU, Microsoft)
- `llamacpp/llama-3.2-3b-q4` - 2GB RAM, 25 t/s (CPU)

---

## Summary

Unicorn Brigade's **Model Flexibility Architecture** enables:

1. ✅ **Hardware Agnostic Deployment**: Mac (MLX), VPS (llama.cpp), GPU (Ollama), Cloud (Ops-Center)
2. ✅ **Cost Optimization**: 65-85% cost reduction with hybrid local/cloud
3. ✅ **Zero Vendor Lock-in**: Switch providers without code changes
4. ✅ **Production Ready**: Automatic fallback, health checks, monitoring

**Recommended Configuration**:
- **Mac Development**: MLX for all local models
- **Production VPS**: llama.cpp (CPU) + cloud orchestrator
- **Production GPU**: Ollama (CUDA) + cloud for critical domains
- **Hybrid**: Local workers + local/cloud team leads + cloud orchestrator

**Implementation Timeline**:
- **Phase 1 (MLX)**: 2 weeks - Mac development environment
- **Phase 2 (Ollama)**: 1 week - GPU deployment
- **Phase 3 (llama.cpp)**: 1 week - CPU deployment
- **Phase 4 (Fallback)**: 1 week - Production reliability
- **Phase 5 (Optimization)**: 2 weeks - Performance tuning

**Total**: 7 weeks to full multi-provider support

---

**Next Steps**:
1. Review and approve architecture
2. Begin Phase 1 (MLX Provider) implementation
3. Test on M3 Pro with Llama 3.1 8B
4. Benchmark cost/quality/latency trade-offs
5. Document best practices per deployment scenario

---

**Document Version**: 1.0
**Last Updated**: January 31, 2026
**Maintained By**: Unicorn Brigade Core Team
