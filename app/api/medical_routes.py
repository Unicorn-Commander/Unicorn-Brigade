"""
Medical AI API Routes

API endpoints for medical AI analysis using HuggingFace models:
- Medical entity extraction (symptoms, medications, conditions)
- Medical image analysis (X-ray, CT, MRI, pathology)
- Drug interaction checking
- Clinical note summarization
- ICD-10 code generation
- Medical question answering
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Annotated, Dict, List, Optional, Any
from enum import Enum
import logging

from app.integrations.huggingface import (
    HuggingFaceClient,
    MedicalAnalyzer,
    get_huggingface_client,
    get_medical_analyzer,
    list_medical_models,
    is_enabled,
    MEDICAL_MODELS,
    MODEL_CATEGORIES,
    IMAGE_MODALITIES,
    HuggingFaceError,
    HuggingFaceAPIError,
    HuggingFaceRateLimitError,
)
from app.auth.middleware import require_api_key, require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/medical", tags=["medical"])

# Global instances (initialized on startup)
hf_client: Optional[HuggingFaceClient] = None
medical_analyzer: Optional[MedicalAnalyzer] = None


def init_medical_routes():
    """Initialize medical routes with HuggingFace client."""
    global hf_client, medical_analyzer
    hf_client = get_huggingface_client()
    medical_analyzer = get_medical_analyzer()
    logger.info("Medical AI routes initialized")


async def shutdown_medical_routes():
    """Cleanup medical routes resources."""
    global hf_client, medical_analyzer
    if medical_analyzer:
        await medical_analyzer.close()
    elif hf_client:
        await hf_client.close()
    hf_client = None
    medical_analyzer = None
    logger.info("Medical AI routes shutdown complete")


def get_analyzer() -> MedicalAnalyzer:
    """Dependency to get the medical analyzer."""
    if not medical_analyzer:
        raise HTTPException(
            status_code=503,
            detail="Medical analyzer not initialized. Check HUGGINGFACE_API_TOKEN configuration."
        )
    return medical_analyzer


# =============================================================================
# Request/Response Models
# =============================================================================

class ImageModalityEnum(str, Enum):
    """Supported medical image modalities"""
    xray = "xray"
    ct = "ct"
    mri = "mri"
    pathology = "pathology"
    dermatology = "dermatology"


class ExtractEntitiesRequest(BaseModel):
    """Request to extract medical entities from text"""
    text: str = Field(
        ...,
        description="Clinical text to analyze",
        min_length=1,
        max_length=10000,
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override (e.g., 'ClinicalBERT', 'PubMedBERT-NER')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Patient presents with chest pain and shortness of breath. Currently taking metformin 500mg and lisinopril 10mg daily.",
                "model": None
            }
        }


class SummarizeNotesRequest(BaseModel):
    """Request to summarize clinical notes"""
    notes: str = Field(
        ...,
        description="Clinical notes to summarize",
        min_length=1,
        max_length=50000,
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override"
    )
    max_length: int = Field(
        256,
        ge=50,
        le=1024,
        description="Maximum summary length in tokens"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "notes": "Chief Complaint: 45-year-old male presents with 2-day history of progressive chest pain...",
                "max_length": 256
            }
        }


class DrugInteractionsRequest(BaseModel):
    """Request to check drug interactions"""
    medications: List[str] = Field(
        ...,
        description="List of medication names to check",
        min_length=2,
        max_length=20,
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "medications": ["metformin", "lisinopril", "aspirin", "atorvastatin"]
            }
        }


class ICDCodesRequest(BaseModel):
    """Request to generate ICD-10 codes"""
    diagnosis: str = Field(
        ...,
        description="Diagnosis text to code",
        min_length=1,
        max_length=2000,
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override"
    )
    max_codes: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of codes to return"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "diagnosis": "Type 2 diabetes mellitus with peripheral neuropathy",
                "max_codes": 5
            }
        }


class MedicalQuestionRequest(BaseModel):
    """Request to answer a medical question"""
    question: str = Field(
        ...,
        description="Medical question to answer",
        min_length=1,
        max_length=1000,
    )
    context: Optional[str] = Field(
        None,
        description="Optional context passage for QA models"
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the first-line treatments for hypertension?",
                "context": None
            }
        }


class TextGenerationRequest(BaseModel):
    """Request for medical text generation"""
    prompt: str = Field(
        ...,
        description="Input prompt",
        min_length=1,
        max_length=4000,
    )
    model: str = Field(
        "BioMistral-7B",
        description="Model to use for generation"
    )
    max_new_tokens: int = Field(
        256,
        ge=10,
        le=2048,
        description="Maximum tokens to generate"
    )
    temperature: float = Field(
        0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Explain the pathophysiology of Type 2 diabetes:",
                "model": "BioMistral-7B",
                "max_new_tokens": 256,
                "temperature": 0.7
            }
        }


class EmbeddingsRequest(BaseModel):
    """Request for medical text embeddings"""
    texts: List[str] = Field(
        ...,
        description="Texts to embed",
        min_length=1,
        max_length=100,
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "texts": [
                    "Patient presents with acute chest pain",
                    "Cardiac catheterization recommended"
                ]
            }
        }


# =============================================================================
# Response Models
# =============================================================================

class EntityExtractionResponse(BaseModel):
    """Response for entity extraction"""
    success: bool
    entities: Dict[str, List[Dict[str, Any]]]
    model: Optional[str] = None
    error: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    """Response for image analysis"""
    success: bool
    modality: str
    findings: List[Dict[str, Any]]
    recommendations: List[str]
    confidence: float
    model: Optional[str] = None
    error: Optional[str] = None


class DrugInteractionsResponse(BaseModel):
    """Response for drug interaction check"""
    success: bool
    medications: List[str]
    interactions: List[Dict[str, Any]]
    model: Optional[str] = None
    error: Optional[str] = None


class ICDCodesResponse(BaseModel):
    """Response for ICD code generation"""
    success: bool
    diagnosis: str
    codes: List[Dict[str, Any]]
    model: Optional[str] = None
    error: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response for clinical note summary"""
    success: bool
    summary: str
    model: Optional[str] = None
    error: Optional[str] = None


class MedicalQuestionResponse(BaseModel):
    """Response for medical question"""
    success: bool
    answer: str
    confidence: float
    model: Optional[str] = None
    error: Optional[str] = None


class ModelsResponse(BaseModel):
    """Response for listing available models"""
    models: Dict[str, str]
    categories: Dict[str, List[str]]
    modalities: Dict[str, List[str]]
    count: int
    enabled: bool


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/health")
async def medical_health_check():
    """
    Health check for medical AI service.

    Returns the status of the HuggingFace integration and available features.
    """
    return {
        "status": "healthy" if is_enabled() else "degraded",
        "huggingface_configured": is_enabled(),
        "available_models": len(MEDICAL_MODELS),
        "available_categories": list(MODEL_CATEGORIES.keys()),
        "supported_modalities": list(IMAGE_MODALITIES.keys()),
    }


@router.get("/models", response_model=ModelsResponse)
async def list_available_models(
    category: Optional[str] = None,
):
    """
    List available medical AI models.

    Optionally filter by category:
    - text_generation: BioMistral, MedAlpaca, etc.
    - ner: PubMedBERT, BioBERT, ClinicalBERT
    - image_classification: CheXNet, RadImageNet, DermNet
    - question_answering: BioGPT, PubMedQA
    - embeddings: PubMedBERT-Embeddings, BioLORD
    """
    models_info = list_medical_models(category)
    return ModelsResponse(
        models=models_info["models"],
        categories=models_info["categories"],
        modalities=models_info["modalities"],
        count=models_info["count"],
        enabled=is_enabled(),
    )


@router.post("/extract-entities", response_model=EntityExtractionResponse)
async def extract_medical_entities(
    request: ExtractEntitiesRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Extract medical entities from clinical text.

    Identifies and categorizes:
    - Symptoms and signs
    - Medications and dosages
    - Medical conditions and diagnoses
    - Procedures and treatments
    - Anatomical locations

    Models:
    - ClinicalBERT (default)
    - PubMedBERT-NER
    - BioBERT-NER
    """
    try:
        result = await analyzer.extract_medical_entities(
            clinical_text=request.text,
            model=request.model,
        )

        return EntityExtractionResponse(
            success=result.get("success", False),
            entities=result.get("entities", {}),
            model=result.get("model"),
            error=result.get("error"),
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Entity extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_medical_image(
    file: UploadFile = File(..., description="Medical image file (JPEG, PNG)"),
    modality: ImageModalityEnum = Form(
        ImageModalityEnum.xray,
        description="Image modality"
    ),
    model: Optional[str] = Form(None, description="Optional model override"),
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Analyze a medical image.

    Supports modalities:
    - xray: Chest X-rays, skeletal imaging (CheXNet, RadImageNet)
    - ct: CT scans (RadImageNet)
    - mri: MRI images (RadImageNet)
    - pathology: Histopathology slides (BiomedCLIP, MedCLIP)
    - dermatology: Skin lesion images (DermNet)

    Returns findings with confidence scores and recommendations.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image (JPEG, PNG, etc.)"
        )

    # Read image bytes
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read image: {str(e)}"
        )

    try:
        result = await analyzer.analyze_radiology_image(
            image_bytes=image_bytes,
            modality=modality.value,
            model=model,
        )

        return ImageAnalysisResponse(
            success=result.get("success", False),
            modality=result.get("modality", modality.value),
            findings=result.get("findings", []),
            recommendations=result.get("recommendations", []),
            confidence=result.get("confidence", 0.0),
            model=result.get("model"),
            error=result.get("error"),
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_clinical_notes(
    request: SummarizeNotesRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Summarize clinical documentation.

    Generates a concise summary preserving key medical information:
    - Chief complaints and symptoms
    - Diagnoses and assessments
    - Treatment plans
    - Key findings and results
    """
    try:
        summary = await analyzer.summarize_clinical_notes(
            notes=request.notes,
            model=request.model,
            max_length=request.max_length,
        )

        if summary.startswith("Error"):
            return SummaryResponse(
                success=False,
                summary="",
                error=summary,
            )

        return SummaryResponse(
            success=True,
            summary=summary,
            model=request.model or "BioMistral-7B",
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Summarization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drug-interactions", response_model=DrugInteractionsResponse)
async def check_drug_interactions(
    request: DrugInteractionsRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Check for potential drug interactions.

    Analyzes a list of medications for potential interactions,
    including severity levels and clinical recommendations.

    Requires at least 2 medications to check interactions.
    """
    try:
        result = await analyzer.get_drug_interactions(
            medications=request.medications,
            model=request.model,
        )

        return DrugInteractionsResponse(
            success=result.get("success", False),
            medications=result.get("medications", request.medications),
            interactions=result.get("interactions", []),
            model=result.get("model"),
            error=result.get("error"),
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Drug interaction check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/icd-codes", response_model=ICDCodesResponse)
async def generate_icd_codes(
    request: ICDCodesRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Suggest ICD-10 codes for diagnoses.

    Analyzes diagnosis text and suggests appropriate ICD-10 codes
    with confidence scores. Useful for medical coding assistance.
    """
    try:
        codes = await analyzer.generate_icd_codes(
            diagnosis_text=request.diagnosis,
            model=request.model,
            max_codes=request.max_codes,
        )

        return ICDCodesResponse(
            success=True,
            diagnosis=request.diagnosis,
            codes=codes,
            model=request.model or "BioMistral-7B",
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"ICD code generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/question", response_model=MedicalQuestionResponse)
async def answer_medical_question(
    request: MedicalQuestionRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Answer a medical question.

    Can answer:
    - Open-ended medical questions (using text generation)
    - Context-based questions (using QA models with provided context)

    Provides answer with confidence score.
    """
    try:
        result = await analyzer.answer_medical_question(
            question=request.question,
            context=request.context,
            model=request.model,
        )

        return MedicalQuestionResponse(
            success=result.get("success", False),
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.0),
            model=result.get("model"),
            error=result.get("error"),
        )

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Medical QA error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_medical_text(
    request: TextGenerationRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate medical text using medical LLMs.

    Available models:
    - BioMistral-7B (default)
    - MedAlpaca-13B
    - PMC-LLaMA-13B
    - Meditron-7B
    - OpenBioLLM-8B
    """
    try:
        result = await analyzer.hf.text_generation(
            model=request.model,
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
        )

        return {
            "success": True,
            "generated_text": result,
            "model": request.model,
        }

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Text generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings")
async def get_medical_embeddings(
    request: EmbeddingsRequest,
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate medical text embeddings.

    Useful for:
    - Semantic search in medical documents
    - Similarity matching between clinical texts
    - RAG (Retrieval Augmented Generation) applications

    Available models:
    - PubMedBERT-Embeddings (default)
    - BioLORD
    - MedCPT
    """
    try:
        result = await analyzer.get_medical_embeddings(
            texts=request.texts,
            model=request.model,
        )

        return result

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify")
async def classify_medical_text(
    text: str = Form(..., description="Text to classify"),
    model: str = Form("BioBERT-ChemProt", description="Classification model"),
    analyzer: MedicalAnalyzer = Depends(get_analyzer),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Classify medical text.

    Available models:
    - BioBERT-ChemProt: Chemical-protein relations
    - PubMedBERT-DDI: Drug-drug interactions
    """
    try:
        result = await analyzer.hf.text_classification(model, text)

        return {
            "success": True,
            "classifications": result,
            "model": model,
        }

    except HuggingFaceRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    except HuggingFaceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
