"""
MLX-based Embeddings Server for Unicorn Brigade

A FastAPI server providing OpenAI-compatible embeddings API using
the nomic-embed-text-v1.5 model with sentence-transformers.

Default Port: 1234 (configurable via EMBEDDINGS_PORT env var)
Endpoint: /v1/embeddings

Usage:
    # Default port 1234
    python server.py

    # Custom port
    EMBEDDINGS_PORT=8234 python server.py
"""

import os
import time
from typing import Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Initialize FastAPI app
app = FastAPI(
    title="MLX Embeddings Server",
    description="OpenAI-compatible embeddings API using nomic-embed-text-v1.5",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model configuration
MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
MODEL_ALIAS = "nomic-embed-text-v1.5"

# Global model instance
model: SentenceTransformer = None


class EmbeddingRequest(BaseModel):
    """Request model for embeddings endpoint."""
    input: Union[str, list[str]]
    model: str = MODEL_ALIAS
    encoding_format: str = "float"  # "float" or "base64"


class EmbeddingData(BaseModel):
    """Individual embedding data in response."""
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingUsage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Response model for embeddings endpoint."""
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage


@app.on_event("startup")
async def load_model():
    """Load the embedding model on startup."""
    global model
    print(f"Loading model: {MODEL_NAME}")
    start_time = time.time()

    # Load with trust_remote_code for nomic models
    model = SentenceTransformer(
        MODEL_NAME,
        trust_remote_code=True,
    )

    # Set prefixes for nomic model (important for performance)
    # "search_document" prefix for documents being indexed
    # "search_query" prefix for queries

    load_time = time.time() - start_time
    print(f"Model loaded in {load_time:.2f}s")
    print(f"Embedding dimension: {model.get_sentence_embedding_dimension()}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "model_loaded": model is not None,
    }


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ALIAS,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "nomic-ai",
            }
        ],
    }


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """
    Create embeddings for the given input text(s).

    OpenAI-compatible endpoint that accepts:
    - Single string input
    - List of strings input

    Returns embeddings in OpenAI response format.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Normalize input to list
    if isinstance(request.input, str):
        texts = [request.input]
    else:
        texts = request.input

    if not texts:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    # Add search_document prefix for better retrieval performance
    # For queries, you'd use "search_query: " prefix
    prefixed_texts = [f"search_document: {text}" for text in texts]

    try:
        # Generate embeddings
        start_time = time.time()
        embeddings = model.encode(
            prefixed_texts,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            show_progress_bar=False,
        )
        inference_time = time.time() - start_time

        # Convert to list format
        embedding_data = []
        for i, emb in enumerate(embeddings):
            embedding_data.append(
                EmbeddingData(
                    embedding=emb.tolist(),
                    index=i,
                )
            )

        # Estimate token count (rough approximation)
        total_chars = sum(len(t) for t in texts)
        estimated_tokens = total_chars // 4  # rough estimate

        print(f"Generated {len(texts)} embeddings in {inference_time:.3f}s")

        return EmbeddingResponse(
            data=embedding_data,
            model=MODEL_ALIAS,
            usage=EmbeddingUsage(
                prompt_tokens=estimated_tokens,
                total_tokens=estimated_tokens,
            ),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")


@app.post("/v1/embeddings/query")
async def create_query_embedding(request: EmbeddingRequest):
    """
    Create embeddings for query text (uses search_query prefix).

    Use this endpoint for embedding search queries, while using
    /v1/embeddings for documents being indexed.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # Normalize input to list
    if isinstance(request.input, str):
        texts = [request.input]
    else:
        texts = request.input

    if not texts:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    # Add search_query prefix for query embeddings
    prefixed_texts = [f"search_query: {text}" for text in texts]

    try:
        embeddings = model.encode(
            prefixed_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        embedding_data = []
        for i, emb in enumerate(embeddings):
            embedding_data.append(
                EmbeddingData(
                    embedding=emb.tolist(),
                    index=i,
                )
            )

        total_chars = sum(len(t) for t in texts)
        estimated_tokens = total_chars // 4

        return EmbeddingResponse(
            data=embedding_data,
            model=MODEL_ALIAS,
            usage=EmbeddingUsage(
                prompt_tokens=estimated_tokens,
                total_tokens=estimated_tokens,
            ),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("EMBEDDINGS_PORT", "1234"))
    print(f"Starting MLX Embeddings Server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
