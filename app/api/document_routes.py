"""
Document Processing API Routes

Endpoints for uploading and processing documents to extract structured data.
Supports PDF, images (PNG/JPG), and text files.
"""

import json
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agents.document_processor import (
    DocumentProcessor,
    DocumentType,
    INVOICE_TEMPLATE,
    CONTRACT_TEMPLATE,
    RECEIPT_TEMPLATE,
    TEMPLATES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize document processor (will be created on first use)
_document_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Get or create the document processor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


# ============== Request/Response Models ==============


class DocumentProcessRequest(BaseModel):
    """Request model for document processing."""
    doc_type: str = Field(
        default="invoice",
        description="Document type: invoice, contract, receipt, custom"
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional LLM model override (e.g., openai/gpt-4o)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "doc_type": "invoice",
                "model": "openai/gpt-4o"
            }
        }


class CustomExtractionRequest(BaseModel):
    """Request model for custom template extraction."""
    template: Dict[str, Any] = Field(
        ...,
        description="Custom extraction template defining fields to extract"
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional LLM model override"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "template": {
                    "company_name": "string",
                    "total_amount": "number",
                    "items": [{"name": "string", "price": "number"}]
                },
                "model": "openai/gpt-4o"
            }
        }


class ExtractionResponse(BaseModel):
    """Response model for extraction results."""
    success: bool
    document_type: str
    extracted_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "document_type": "invoice",
                "extracted_data": {
                    "vendor_name": "Acme Corp",
                    "invoice_number": "INV-2024-001",
                    "total": 1250.00
                },
                "confidence": 0.92,
                "errors": [],
                "warnings": [],
                "metadata": {
                    "file_name": "invoice.pdf",
                    "file_size": 125000
                }
            }
        }


class TemplateInfo(BaseModel):
    """Template information."""
    name: str
    description: str
    fields: Dict[str, Any]


class TemplatesResponse(BaseModel):
    """Response model for available templates."""
    templates: List[TemplateInfo]


# ============== API Endpoints ==============


@router.post(
    "/process",
    response_model=ExtractionResponse,
    summary="Process document and extract structured data",
    description="""
    Upload and process a document to extract structured data.

    Supported file types:
    - PDF files (.pdf)
    - Images (.png, .jpg, .jpeg, .gif, .webp, .bmp)
    - Text files (.txt, .md, .csv, .json, .xml, .html)

    Document types:
    - invoice: Extract vendor, amounts, line items, etc.
    - contract: Extract parties, terms, dates, etc.
    - receipt: Extract merchant, items, total, etc.
    - custom: Use /extract endpoint with custom template
    """
)
async def process_document(
    file: UploadFile = File(..., description="Document file to process"),
    doc_type: str = Form(default="invoice", description="Document type"),
    model: Optional[str] = Form(default=None, description="Optional model override"),
):
    """Process an uploaded document and extract structured data."""
    # Validate doc_type
    valid_types = ["invoice", "contract", "receipt"]
    if doc_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_type. Must be one of: {', '.join(valid_types)}. Use /extract for custom templates."
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    all_extensions = []
    for exts in DocumentProcessor.SUPPORTED_EXTENSIONS.values():
        all_extensions.extend(exts)

    if file_ext not in all_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(all_extensions)}"
        )

    # Save uploaded file to temp location
    temp_path = None
    try:
        # Create temp file with correct extension
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            prefix=f"doc_{uuid.uuid4().hex[:8]}_"
        ) as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)

        logger.info(f"Processing document: {file.filename} ({len(content)} bytes)")

        # Process document
        processor = get_document_processor()
        result = await processor.process_document(
            file_path=temp_path,
            doc_type=doc_type,
            model=model,
        )

        return ExtractionResponse(
            success=result.success,
            document_type=result.document_type,
            extracted_data=result.extracted_data,
            confidence=result.confidence,
            errors=result.errors,
            warnings=result.warnings,
            metadata={
                **result.metadata,
                "original_filename": file.filename,
            },
        )

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract with custom template",
    description="""
    Upload a document and extract data using a custom template.

    The template defines the fields to extract. Each field can be:
    - A type name: "string", "number", "boolean"
    - An array: ["string"] or [{"field": "type"}]
    - A nested object: {"field": "type"}

    Example template:
    ```json
    {
        "company_name": "string",
        "total_amount": "number",
        "is_paid": "boolean",
        "items": [{"name": "string", "quantity": "number", "price": "number"}]
    }
    ```
    """
)
async def extract_with_template(
    file: UploadFile = File(..., description="Document file to process"),
    template: str = Form(..., description="JSON template defining extraction fields"),
    model: Optional[str] = Form(default=None, description="Optional model override"),
):
    """Extract data from document using a custom template."""
    # Parse template JSON
    try:
        template_dict = json.loads(template)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template JSON: {e}"
        )

    if not isinstance(template_dict, dict) or not template_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template must be a non-empty JSON object"
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    file_ext = os.path.splitext(file.filename)[1].lower()
    all_extensions = []
    for exts in DocumentProcessor.SUPPORTED_EXTENSIONS.values():
        all_extensions.extend(exts)

    if file_ext not in all_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}"
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            prefix=f"doc_{uuid.uuid4().hex[:8]}_"
        ) as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)

        logger.info(f"Custom extraction: {file.filename} with {len(template_dict)} fields")

        processor = get_document_processor()
        result = await processor.process_document(
            file_path=temp_path,
            doc_type="custom",
            template=template_dict,
            model=model,
        )

        return ExtractionResponse(
            success=result.success,
            document_type="custom",
            extracted_data=result.extracted_data,
            confidence=result.confidence,
            errors=result.errors,
            warnings=result.warnings,
            metadata={
                **result.metadata,
                "original_filename": file.filename,
                "template_fields": list(template_dict.keys()),
            },
        )

    except Exception as e:
        logger.error(f"Custom extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@router.get(
    "/templates",
    response_model=TemplatesResponse,
    summary="Get available extraction templates",
    description="Returns the built-in extraction templates for invoice, contract, and receipt document types."
)
async def get_templates():
    """Get available extraction templates."""
    def type_to_str(t) -> str:
        if t == str:
            return "string"
        elif t == int:
            return "integer"
        elif t == float:
            return "number"
        elif t == bool:
            return "boolean"
        elif isinstance(t, list):
            if t and isinstance(t[0], dict):
                return [type_to_str(t[0])]
            return ["string"]
        elif isinstance(t, dict):
            return {k: type_to_str(v) for k, v in t.items()}
        return "string"

    templates = [
        TemplateInfo(
            name="invoice",
            description="Extract invoice data: vendor, amounts, line items, payment terms",
            fields={k: type_to_str(v) for k, v in INVOICE_TEMPLATE.items()},
        ),
        TemplateInfo(
            name="contract",
            description="Extract contract data: parties, terms, dates, obligations",
            fields={k: type_to_str(v) for k, v in CONTRACT_TEMPLATE.items()},
        ),
        TemplateInfo(
            name="receipt",
            description="Extract receipt data: merchant, items, totals, payment method",
            fields={k: type_to_str(v) for k, v in RECEIPT_TEMPLATE.items()},
        ),
    ]

    return TemplatesResponse(templates=templates)


@router.get(
    "/supported-types",
    summary="Get supported file types",
    description="Returns the list of supported file extensions for document processing."
)
async def get_supported_types():
    """Get supported file types for document processing."""
    return {
        "file_categories": {
            "image": {
                "extensions": DocumentProcessor.SUPPORTED_EXTENSIONS["image"],
                "description": "Image files processed using vision-capable LLMs",
            },
            "pdf": {
                "extensions": DocumentProcessor.SUPPORTED_EXTENSIONS["pdf"],
                "description": "PDF files processed using vision-capable LLMs",
            },
            "text": {
                "extensions": DocumentProcessor.SUPPORTED_EXTENSIONS["text"],
                "description": "Text files processed using standard LLM text analysis",
            },
        },
        "document_types": [
            {"name": "invoice", "description": "Invoices and billing documents"},
            {"name": "contract", "description": "Legal contracts and agreements"},
            {"name": "receipt", "description": "Purchase receipts and transaction records"},
            {"name": "custom", "description": "Custom extraction using user-provided template"},
        ],
    }


@router.post(
    "/analyze",
    summary="Analyze document without extraction",
    description="""
    Analyze a document and return general information without extracting specific fields.
    Useful for determining document type before extraction.
    """
)
async def analyze_document(
    file: UploadFile = File(..., description="Document file to analyze"),
    model: Optional[str] = Form(default=None, description="Optional model override"),
):
    """Analyze a document and return general information."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    file_ext = os.path.splitext(file.filename)[1].lower()
    all_extensions = []
    for exts in DocumentProcessor.SUPPORTED_EXTENSIONS.values():
        all_extensions.extend(exts)

    if file_ext not in all_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}"
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            prefix=f"analyze_{uuid.uuid4().hex[:8]}_"
        ) as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)

        # Create a simple analysis template
        analysis_template = {
            "document_type": str,
            "document_category": str,
            "primary_language": str,
            "summary": str,
            "key_entities": [str],
            "key_dates": [str],
            "key_amounts": [str],
            "recommended_extraction_type": str,
        }

        processor = get_document_processor()
        result = await processor.process_document(
            file_path=temp_path,
            doc_type="custom",
            template=analysis_template,
            model=model,
        )

        return {
            "success": result.success,
            "analysis": result.extracted_data,
            "errors": result.errors,
            "metadata": {
                **result.metadata,
                "original_filename": file.filename,
            },
        }

    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")
