"""
Llama Guard Service - FastAPI wrapper for content safety checks

This service provides a REST API for checking content safety using Llama Guard 3.
It integrates with Ollama for model inference and supports both input and output
content checking.

Endpoints:
- POST /check - Check content for safety violations
- POST /check/batch - Check multiple texts in batch
- GET /health - Health check
- GET /categories - List supported safety categories
"""

import os
import logging
import hashlib
from typing import Optional
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://llama-guard:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-guard3:1b")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30"))

# Setup logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Llama Guard Service",
    description="Content safety checking service using Llama Guard 3",
    version="1.0.0"
)


class CheckType(str, Enum):
    INPUT = "input"    # Check user input
    OUTPUT = "output"  # Check model output
    BOTH = "both"      # Check as both (for unknown source)


class SafetyCategory(str, Enum):
    S1 = "S1: Violent Crimes"
    S2 = "S2: Non-Violent Crimes"
    S3 = "S3: Sex-Related Crimes"
    S4 = "S4: Child Sexual Exploitation"
    S5 = "S5: Defamation"
    S6 = "S6: Specialized Advice"
    S7 = "S7: Privacy"
    S8 = "S8: Intellectual Property"
    S9 = "S9: Indiscriminate Weapons"
    S10 = "S10: Hate"
    S11 = "S11: Suicide & Self-Harm"
    S12 = "S12: Sexual Content"
    S13 = "S13: Elections"


class GuardrailRequest(BaseModel):
    """Request model for content safety check"""
    text: str = Field(..., description="Text content to check", min_length=1)
    check_type: CheckType = Field(
        default=CheckType.INPUT,
        description="Type of check: input (user message), output (model response), or both"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for context tracking"
    )


class GuardrailResponse(BaseModel):
    """Response model for content safety check"""
    safe: bool = Field(..., description="Whether the content is safe")
    category: Optional[str] = Field(
        default=None,
        description="Violated category if unsafe"
    )
    categories: list[str] = Field(
        default_factory=list,
        description="All violated categories if multiple"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Explanation of the safety assessment"
    )
    check_type: str = Field(..., description="Type of check performed")
    model: str = Field(..., description="Model used for checking")


class BatchRequest(BaseModel):
    """Request model for batch content safety check"""
    items: list[GuardrailRequest] = Field(
        ...,
        description="List of content items to check",
        min_length=1,
        max_length=50
    )


class BatchResponse(BaseModel):
    """Response model for batch content safety check"""
    results: list[GuardrailResponse]
    total: int
    safe_count: int
    unsafe_count: int


# Llama Guard prompt template
LLAMA_GUARD_PROMPT = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
S1: Violent Crimes
AI models should not create content that enables, encourages, or excuses the commission of violent crimes.

S2: Non-Violent Crimes
AI models should not create content that enables, encourages, or excuses the commission of non-violent crimes.

S3: Sex-Related Crimes
AI models should not create content that enables, encourages, or excuses the commission of sex-related crimes.

S4: Child Sexual Exploitation
AI models should not create content that depicts child sexual exploitation.

S5: Defamation
AI models should not create content that is defamatory against a real person.

S6: Specialized Advice
AI models should not create content that contains specialized financial, medical, or legal advice.

S7: Privacy
AI models should not create content that contains sensitive, personal information about private individuals.

S8: Intellectual Property
AI models should not create content that violates the intellectual property rights of third parties.

S9: Indiscriminate Weapons
AI models should not create content that enables the creation of weapons capable of mass casualties.

S10: Hate
AI models should not create content that is hateful toward people on the basis of their protected characteristics.

S11: Suicide & Self-Harm
AI models should not create content that enables, encourages, or excuses acts of intentional self-harm.

S12: Sexual Content
AI models should not create depictions of nude adults or content that contains erotic descriptions or explicit depictions of sex acts.

S13: Elections
AI models should not create content that contain factually incorrect information about electoral systems and processes.
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>
{role}: {content}
<END CONVERSATION>

Provide your safety assessment for {role} in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""


async def check_with_llama_guard(text: str, check_type: CheckType) -> GuardrailResponse:
    """
    Check content safety using Llama Guard via Ollama.

    Args:
        text: Content to check
        check_type: Whether this is user input or model output

    Returns:
        GuardrailResponse with safety assessment
    """
    role = "User" if check_type == CheckType.INPUT else "Assistant"

    prompt = LLAMA_GUARD_PROMPT.format(role=role, content=text)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,  # Deterministic for safety
                        "num_predict": 100,  # Short response expected
                    }
                },
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()

        result = response.json()
        output = result.get("response", "").strip()

        logger.debug(f"Llama Guard response: {output}")

        # Parse the response
        lines = output.split("\n")
        first_line = lines[0].lower().strip() if lines else ""

        if first_line.startswith("safe"):
            return GuardrailResponse(
                safe=True,
                check_type=check_type.value,
                model=MODEL_NAME
            )
        elif first_line.startswith("unsafe"):
            # Extract categories from second line
            categories = []
            if len(lines) > 1:
                cat_line = lines[1].strip()
                # Parse categories like "S1, S10" or "S1: Violent Crimes, S10: Hate"
                for cat in cat_line.split(","):
                    cat = cat.strip()
                    # Extract just the category code (S1, S2, etc.)
                    if cat.startswith("S"):
                        cat_code = cat.split(":")[0].strip()
                        categories.append(cat_code)

            return GuardrailResponse(
                safe=False,
                category=categories[0] if categories else "unknown",
                categories=categories,
                explanation=f"Content flagged for safety violations: {', '.join(categories) if categories else 'unspecified'}",
                check_type=check_type.value,
                model=MODEL_NAME
            )
        else:
            # Unexpected response format - log and treat as potentially unsafe
            logger.warning(f"Unexpected Llama Guard response format: {output}")
            return GuardrailResponse(
                safe=False,
                category="parse_error",
                explanation=f"Could not parse safety response: {output[:100]}",
                check_type=check_type.value,
                model=MODEL_NAME
            )

    except httpx.TimeoutException:
        logger.error("Timeout waiting for Llama Guard response")
        raise HTTPException(status_code=504, detail="Safety check timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama HTTP error: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama service error: {e}")
    except Exception as e:
        logger.error(f"Error checking content: {e}")
        raise HTTPException(status_code=500, detail=f"Safety check error: {str(e)}")


@app.post("/check", response_model=GuardrailResponse)
async def check_content(request: GuardrailRequest) -> GuardrailResponse:
    """
    Check content for safety violations.

    This endpoint analyzes text content using Llama Guard 3 and returns
    a safety assessment indicating whether the content is safe or unsafe,
    along with any violated categories.
    """
    logger.info(f"Checking content (type={request.check_type}): {request.text[:100]}...")

    if request.check_type == CheckType.BOTH:
        # Check as both input and output, return unsafe if either fails
        input_result = await check_with_llama_guard(request.text, CheckType.INPUT)
        if not input_result.safe:
            return input_result

        output_result = await check_with_llama_guard(request.text, CheckType.OUTPUT)
        return output_result
    else:
        return await check_with_llama_guard(request.text, request.check_type)


@app.post("/check/batch", response_model=BatchResponse)
async def check_content_batch(request: BatchRequest) -> BatchResponse:
    """
    Check multiple content items for safety violations.

    This endpoint processes multiple texts in sequence and returns
    aggregated results. Useful for checking conversation history.
    """
    results = []
    safe_count = 0
    unsafe_count = 0

    for item in request.items:
        result = await check_content(item)
        results.append(result)
        if result.safe:
            safe_count += 1
        else:
            unsafe_count += 1

    return BatchResponse(
        results=results,
        total=len(results),
        safe_count=safe_count,
        unsafe_count=unsafe_count
    )


@app.get("/categories")
async def list_categories() -> dict:
    """List all supported safety categories."""
    return {
        "categories": [
            {"code": "S1", "name": "Violent Crimes", "description": "Content enabling violent crimes"},
            {"code": "S2", "name": "Non-Violent Crimes", "description": "Content enabling non-violent crimes"},
            {"code": "S3", "name": "Sex-Related Crimes", "description": "Content enabling sex-related crimes"},
            {"code": "S4", "name": "Child Sexual Exploitation", "description": "CSAM content"},
            {"code": "S5", "name": "Defamation", "description": "Defamatory content about real people"},
            {"code": "S6", "name": "Specialized Advice", "description": "Unqualified financial/medical/legal advice"},
            {"code": "S7", "name": "Privacy", "description": "Content revealing private information"},
            {"code": "S8", "name": "Intellectual Property", "description": "IP violations"},
            {"code": "S9", "name": "Indiscriminate Weapons", "description": "WMD creation content"},
            {"code": "S10", "name": "Hate", "description": "Hateful content based on protected characteristics"},
            {"code": "S11", "name": "Suicide & Self-Harm", "description": "Self-harm enabling content"},
            {"code": "S12", "name": "Sexual Content", "description": "Explicit sexual content"},
            {"code": "S13", "name": "Elections", "description": "Election misinformation"},
        ],
        "model": MODEL_NAME
    }


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Verifies both this service and the underlying Ollama service are healthy.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_BASE_URL}/api/tags",
                timeout=5.0
            )
            response.raise_for_status()

            # Check if our model is loaded
            tags = response.json()
            models = [m.get("name", "") for m in tags.get("models", [])]
            model_loaded = any(MODEL_NAME in m for m in models)

            return {
                "status": "healthy" if model_loaded else "degraded",
                "ollama": "connected",
                "model": MODEL_NAME,
                "model_loaded": model_loaded,
                "available_models": models
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "ollama": "disconnected",
            "error": str(e)
        }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Llama Guard Service",
        "version": "1.0.0",
        "model": MODEL_NAME,
        "endpoints": {
            "check": "POST /check - Check single content",
            "batch": "POST /check/batch - Check multiple contents",
            "categories": "GET /categories - List safety categories",
            "health": "GET /health - Health check"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
