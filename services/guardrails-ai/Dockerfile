# Guardrails AI Service - Validator service for LiteLLM integration
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    guardrails-ai==0.5.15 \
    fastapi==0.115.0 \
    uvicorn[standard]==0.31.0 \
    pydantic==2.9.2 \
    httpx==0.27.2 \
    openai==1.51.0 \
    redis==5.0.8

# Install common validators from Guardrails Hub
RUN guardrails hub install hub://guardrails/detect_pii --quiet || true && \
    guardrails hub install hub://guardrails/toxic_language --quiet || true && \
    guardrails hub install hub://guardrails/profanity_free --quiet || true && \
    guardrails hub install hub://guardrails/valid_length --quiet || true

# Copy service code
COPY main.py .
COPY guards/ /app/guards/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
