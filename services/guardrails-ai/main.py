"""
Guardrails AI Service - Validator service for LiteLLM integration

This service provides a REST API for validating LLM inputs and outputs
using the Guardrails AI framework and validators from the Guardrails Hub.

Endpoints:
- POST /validate - Validate content against configured guards
- POST /validate/input - Validate input (pre-call)
- POST /validate/output - Validate output (post-call)
- GET /guards - List available guards
- GET /health - Health check
"""

import os
import logging
from typing import Optional, Any
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configuration
LOG_LEVEL = os.getenv("GUARDRAILS_LOG_LEVEL", "INFO")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Setup logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Guardrails AI Service",
    description="Content validation service using Guardrails AI validators",
    version="1.0.0"
)


class ValidationMode(str, Enum):
    PRE_CALL = "pre_call"
    POST_CALL = "post_call"


class ValidationRequest(BaseModel):
    """Request model for content validation"""
    text: str = Field(..., description="Text content to validate", min_length=1)
    guard_name: str = Field(
        default="default",
        description="Name of the guard to use"
    )
    mode: ValidationMode = Field(
        default=ValidationMode.PRE_CALL,
        description="Validation mode: pre_call or post_call"
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Optional metadata for context"
    )


class ValidationResult(BaseModel):
    """Result of a single validator"""
    validator: str
    passed: bool
    message: Optional[str] = None
    details: Optional[dict] = None


class ValidationResponse(BaseModel):
    """Response model for content validation"""
    valid: bool = Field(..., description="Whether the content passed all validators")
    results: list[ValidationResult] = Field(
        default_factory=list,
        description="Results from individual validators"
    )
    guard_name: str = Field(..., description="Name of the guard used")
    mode: str = Field(..., description="Validation mode used")
    rewritten_text: Optional[str] = Field(
        default=None,
        description="Rewritten text if any validator made corrections"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if validation failed to run"
    )


# Define guards with validators
# Note: In production, these would be loaded from configuration files

def create_input_guard():
    """Create guard for input validation (pre-call)"""
    try:
        from guardrails import Guard
        from guardrails.hub import DetectPII, ToxicLanguage, ProfanityFree

        return Guard(
            name="input_guard",
            description="Validates user input before sending to LLM"
        ).use_many(
            DetectPII(
                pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"],
                on_fail="fix"  # Mask PII rather than reject
            ),
            ToxicLanguage(
                threshold=0.7,
                on_fail="exception"
            ),
            ProfanityFree(on_fail="fix"),
        )
    except ImportError as e:
        logger.warning(f"Could not create input guard: {e}")
        return None


def create_output_guard():
    """Create guard for output validation (post-call)"""
    try:
        from guardrails import Guard
        from guardrails.hub import DetectPII, ValidLength

        return Guard(
            name="output_guard",
            description="Validates LLM output before returning to user"
        ).use_many(
            DetectPII(
                pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"],
                on_fail="fix"
            ),
            ValidLength(
                min=1,
                max=10000,
                on_fail="fix"
            ),
        )
    except ImportError as e:
        logger.warning(f"Could not create output guard: {e}")
        return None


def create_strict_guard():
    """Create strict guard that rejects any violations"""
    try:
        from guardrails import Guard
        from guardrails.hub import DetectPII, ToxicLanguage

        return Guard(
            name="strict_guard",
            description="Strict validation - rejects any violations"
        ).use_many(
            DetectPII(
                pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN", "PERSON"],
                on_fail="exception"
            ),
            ToxicLanguage(
                threshold=0.5,  # Lower threshold = stricter
                on_fail="exception"
            ),
        )
    except ImportError as e:
        logger.warning(f"Could not create strict guard: {e}")
        return None


# Initialize guards
GUARDS = {}

def initialize_guards():
    """Initialize all guards on startup"""
    global GUARDS

    input_guard = create_input_guard()
    if input_guard:
        GUARDS["input"] = input_guard
        GUARDS["default"] = input_guard

    output_guard = create_output_guard()
    if output_guard:
        GUARDS["output"] = output_guard

    strict_guard = create_strict_guard()
    if strict_guard:
        GUARDS["strict"] = strict_guard

    logger.info(f"Initialized {len(GUARDS)} guards: {list(GUARDS.keys())}")


@app.on_event("startup")
async def startup_event():
    """Initialize guards on startup"""
    initialize_guards()


async def validate_with_guard(
    text: str,
    guard_name: str,
    mode: ValidationMode
) -> ValidationResponse:
    """
    Validate text using the specified guard.

    Args:
        text: Content to validate
        guard_name: Name of the guard to use
        mode: Pre-call or post-call validation

    Returns:
        ValidationResponse with results
    """
    # Select guard based on mode if using default
    actual_guard_name = guard_name
    if guard_name == "default":
        if mode == ValidationMode.PRE_CALL:
            actual_guard_name = "input"
        else:
            actual_guard_name = "output"

    if actual_guard_name not in GUARDS:
        # Fallback to any available guard
        if GUARDS:
            actual_guard_name = list(GUARDS.keys())[0]
            logger.warning(f"Guard '{guard_name}' not found, using '{actual_guard_name}'")
        else:
            return ValidationResponse(
                valid=True,  # Fail open if no guards available
                guard_name=guard_name,
                mode=mode.value,
                error="No guards available"
            )

    guard = GUARDS[actual_guard_name]

    try:
        # Run validation
        result = guard.validate(text)

        # Process results
        validation_results = []
        all_passed = True

        # Check if validation passed
        if hasattr(result, 'validation_passed'):
            all_passed = result.validation_passed
        elif hasattr(result, 'validated_output'):
            all_passed = result.validated_output is not None

        # Get rewritten text if available
        rewritten = None
        if hasattr(result, 'validated_output') and result.validated_output != text:
            rewritten = result.validated_output

        # Extract individual validator results if available
        if hasattr(result, 'validation_summaries'):
            for summary in result.validation_summaries:
                validation_results.append(ValidationResult(
                    validator=summary.validator_name if hasattr(summary, 'validator_name') else "unknown",
                    passed=summary.passed if hasattr(summary, 'passed') else True,
                    message=str(summary.failure_reason) if hasattr(summary, 'failure_reason') else None
                ))

        return ValidationResponse(
            valid=all_passed,
            results=validation_results,
            guard_name=actual_guard_name,
            mode=mode.value,
            rewritten_text=rewritten
        )

    except Exception as e:
        logger.error(f"Validation error: {e}")

        # Check if this is a validation failure (expected) or an error (unexpected)
        error_str = str(e).lower()
        if "validation failed" in error_str or "toxic" in error_str:
            return ValidationResponse(
                valid=False,
                results=[ValidationResult(
                    validator="guard",
                    passed=False,
                    message=str(e)
                )],
                guard_name=actual_guard_name,
                mode=mode.value
            )
        else:
            # Unexpected error - log and fail open
            return ValidationResponse(
                valid=True,
                guard_name=actual_guard_name,
                mode=mode.value,
                error=f"Validation error: {str(e)}"
            )


@app.post("/validate", response_model=ValidationResponse)
async def validate_content(request: ValidationRequest) -> ValidationResponse:
    """
    Validate content against configured guards.

    This endpoint validates text using Guardrails AI validators and returns
    whether the content passed validation, along with any corrections made.
    """
    logger.info(f"Validating content (guard={request.guard_name}, mode={request.mode})")

    return await validate_with_guard(
        text=request.text,
        guard_name=request.guard_name,
        mode=request.mode
    )


@app.post("/validate/input", response_model=ValidationResponse)
async def validate_input(request: ValidationRequest) -> ValidationResponse:
    """
    Validate input content (pre-call).

    Convenience endpoint that always uses pre_call mode.
    """
    request.mode = ValidationMode.PRE_CALL
    return await validate_content(request)


@app.post("/validate/output", response_model=ValidationResponse)
async def validate_output(request: ValidationRequest) -> ValidationResponse:
    """
    Validate output content (post-call).

    Convenience endpoint that always uses post_call mode.
    """
    request.mode = ValidationMode.POST_CALL
    return await validate_content(request)


@app.get("/guards")
async def list_guards() -> dict:
    """List all available guards and their validators."""
    guards_info = {}

    for name, guard in GUARDS.items():
        validators = []
        if hasattr(guard, 'validators'):
            for v in guard.validators:
                validators.append({
                    "name": v.__class__.__name__ if hasattr(v, '__class__') else str(v),
                    "on_fail": getattr(v, 'on_fail', 'unknown')
                })

        guards_info[name] = {
            "name": name,
            "description": guard.description if hasattr(guard, 'description') else "",
            "validators": validators
        }

    return {
        "guards": guards_info,
        "count": len(GUARDS)
    }


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns service status and available guards.
    """
    return {
        "status": "healthy" if GUARDS else "degraded",
        "guards_available": len(GUARDS),
        "guard_names": list(GUARDS.keys())
    }


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Guardrails AI Service",
        "version": "1.0.0",
        "guards": list(GUARDS.keys()),
        "endpoints": {
            "validate": "POST /validate - Validate content",
            "validate_input": "POST /validate/input - Validate input (pre-call)",
            "validate_output": "POST /validate/output - Validate output (post-call)",
            "guards": "GET /guards - List available guards",
            "health": "GET /health - Health check"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
