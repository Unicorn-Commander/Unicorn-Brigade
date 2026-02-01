"""
Document Processing Agent for extracting structured data from documents.

Supports:
- PDF files (via vision-capable LLMs)
- Images (PNG, JPG, JPEG)
- Text files (TXT, MD, CSV, JSON)

Uses LLM vision capabilities for image/PDF processing and returns
structured JSON with extracted fields based on document type.
"""

import base64
import json
import logging
import mimetypes
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from enum import Enum

from app.agents.base import BaseAgent
from app.llm import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types for extraction."""
    INVOICE = "invoice"
    CONTRACT = "contract"
    RECEIPT = "receipt"
    CUSTOM = "custom"


# ============== Extraction Templates ==============

INVOICE_TEMPLATE = {
    "vendor_name": str,
    "invoice_number": str,
    "date": str,
    "line_items": [{"description": str, "quantity": int, "amount": float}],
    "subtotal": float,
    "tax": float,
    "total": float,
    "payment_terms": str,
    "due_date": str,
    "billing_address": str,
    "currency": str,
}

CONTRACT_TEMPLATE = {
    "contract_title": str,
    "parties": [{"name": str, "role": str, "address": str}],
    "effective_date": str,
    "termination_date": str,
    "contract_value": float,
    "payment_schedule": str,
    "key_terms": [str],
    "obligations": [{"party": str, "obligation": str}],
    "termination_clauses": [str],
    "governing_law": str,
    "signatures": [{"name": str, "title": str, "date": str}],
}

RECEIPT_TEMPLATE = {
    "merchant_name": str,
    "merchant_address": str,
    "receipt_number": str,
    "date": str,
    "time": str,
    "items": [{"name": str, "quantity": int, "unit_price": float, "total": float}],
    "subtotal": float,
    "tax": float,
    "total": float,
    "payment_method": str,
    "last_four_digits": str,
}

TEMPLATES = {
    DocumentType.INVOICE: INVOICE_TEMPLATE,
    DocumentType.CONTRACT: CONTRACT_TEMPLATE,
    DocumentType.RECEIPT: RECEIPT_TEMPLATE,
}


@dataclass
class ExtractionResult:
    """Result of document extraction."""
    success: bool
    document_type: str
    extracted_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    raw_text: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "document_type": self.document_type,
            "extracted_data": self.extracted_data,
            "confidence": self.confidence,
            "raw_text": self.raw_text,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class DocumentProcessor(BaseAgent):
    """
    Document Processing Agent for extracting structured data from documents.

    Uses vision-capable LLMs for image/PDF processing and text analysis
    for plain text documents. Returns structured JSON based on document type.
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        "image": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
        "pdf": [".pdf"],
        "text": [".txt", ".md", ".csv", ".json", ".xml", ".html"],
    }

    # Vision-capable models (prefer these for image/PDF)
    VISION_MODELS = [
        "openai/gpt-4o",
        "openai/gpt-4-vision-preview",
        "anthropic/claude-3-opus-20240229",
        "anthropic/claude-3-sonnet-20240229",
        "anthropic/claude-3-haiku-20240307",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-vision",
        "google/gemini-1.5-pro",
    ]

    def __init__(
        self,
        name: str = "document-processor",
        memory_manager=None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        default_model: str = "openai/gpt-4o",
    ):
        """
        Initialize the Document Processor.

        Args:
            name: Agent name
            memory_manager: Optional memory manager for context
            llm_client: OpsCenterLLMClient instance (created if not provided)
            default_model: Default vision-capable model to use
        """
        super().__init__(name, memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.default_model = default_model
        logger.info(f"DocumentProcessor initialized with model: {default_model}")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute document processing task.

        Args:
            task: Task dictionary with:
                - file_path: Path to document
                - doc_type: Document type (invoice, contract, receipt, custom)
                - template: Optional custom template for extraction

        Returns:
            Extraction result dictionary
        """
        file_path = task.get("file_path")
        doc_type = task.get("doc_type", "invoice")
        template = task.get("template")

        if not file_path:
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=["file_path is required"],
            ).to_dict()

        try:
            result = await self.process_document(
                file_path=file_path,
                doc_type=doc_type,
                template=template,
            )
            return result.to_dict()
        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[str(e)],
            ).to_dict()

    async def process_document(
        self,
        file_path: str,
        doc_type: str = "invoice",
        template: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Main entry point for document processing.

        Args:
            file_path: Path to the document file
            doc_type: Type of document (invoice, contract, receipt, custom)
            template: Custom extraction template (required for custom type)
            model: Optional model override

        Returns:
            ExtractionResult with extracted data
        """
        # Validate file exists
        if not os.path.exists(file_path):
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[f"File not found: {file_path}"],
            )

        # Get file info
        file_ext = Path(file_path).suffix.lower()
        file_size = os.path.getsize(file_path)
        file_name = Path(file_path).name

        logger.info(f"Processing document: {file_name} ({file_ext}, {file_size} bytes)")

        # Determine file category
        file_category = self._get_file_category(file_ext)
        if not file_category:
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[f"Unsupported file type: {file_ext}"],
                metadata={"file_name": file_name, "file_extension": file_ext},
            )

        # Get extraction template
        extraction_template = template
        if not extraction_template and doc_type != DocumentType.CUSTOM:
            try:
                extraction_template = TEMPLATES.get(DocumentType(doc_type))
            except ValueError:
                pass

        if not extraction_template:
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[f"No template available for document type: {doc_type}. Provide a custom template."],
            )

        # Read and process content based on file type
        try:
            if file_category == "text":
                content = await self._read_text_file(file_path)
                result = await self._extract_from_text(
                    content=content,
                    doc_type=doc_type,
                    template=extraction_template,
                    model=model,
                )
            else:
                # Image or PDF - use vision
                content = await self._read_binary_file(file_path)
                result = await self._extract_from_vision(
                    content=content,
                    file_ext=file_ext,
                    doc_type=doc_type,
                    template=extraction_template,
                    model=model,
                )

            # Add metadata
            result.metadata.update({
                "file_name": file_name,
                "file_extension": file_ext,
                "file_size": file_size,
                "file_category": file_category,
            })

            return result

        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[str(e)],
                metadata={"file_name": file_name, "file_extension": file_ext},
            )

    async def extract_invoice(
        self,
        content: Union[str, bytes],
        is_image: bool = False,
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract invoice fields from content.

        Args:
            content: Text content or image bytes
            is_image: Whether content is image bytes
            model: Optional model override

        Returns:
            ExtractionResult with invoice data
        """
        if is_image:
            return await self._extract_from_vision(
                content=content,
                file_ext=".png",  # Assume PNG for raw bytes
                doc_type="invoice",
                template=INVOICE_TEMPLATE,
                model=model,
            )
        return await self._extract_from_text(
            content=content,
            doc_type="invoice",
            template=INVOICE_TEMPLATE,
            model=model,
        )

    async def extract_contract(
        self,
        content: Union[str, bytes],
        is_image: bool = False,
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract contract fields from content.

        Args:
            content: Text content or image bytes
            is_image: Whether content is image bytes
            model: Optional model override

        Returns:
            ExtractionResult with contract data
        """
        if is_image:
            return await self._extract_from_vision(
                content=content,
                file_ext=".png",
                doc_type="contract",
                template=CONTRACT_TEMPLATE,
                model=model,
            )
        return await self._extract_from_text(
            content=content,
            doc_type="contract",
            template=CONTRACT_TEMPLATE,
            model=model,
        )

    async def extract_custom(
        self,
        content: Union[str, bytes],
        template: Dict[str, Any],
        is_image: bool = False,
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract fields using a custom template.

        Args:
            content: Text content or image bytes
            template: Custom extraction template
            is_image: Whether content is image bytes
            model: Optional model override

        Returns:
            ExtractionResult with extracted data
        """
        if is_image:
            return await self._extract_from_vision(
                content=content,
                file_ext=".png",
                doc_type="custom",
                template=template,
                model=model,
            )
        return await self._extract_from_text(
            content=content,
            doc_type="custom",
            template=template,
            model=model,
        )

    def _get_file_category(self, file_ext: str) -> Optional[str]:
        """Get the category of a file based on its extension."""
        for category, extensions in self.SUPPORTED_EXTENSIONS.items():
            if file_ext in extensions:
                return category
        return None

    async def _read_text_file(self, file_path: str) -> str:
        """Read a text file and return its content."""
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        # Fallback: read as bytes and decode with errors ignored
        with open(file_path, "rb") as f:
            return f.read().decode("utf-8", errors="ignore")

    async def _read_binary_file(self, file_path: str) -> bytes:
        """Read a binary file and return its content."""
        with open(file_path, "rb") as f:
            return f.read()

    def _template_to_json_schema(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a simple template to a JSON schema description."""
        def type_to_str(t: Any) -> str:
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
                    inner_fields = {k: type_to_str(v) for k, v in t[0].items()}
                    return f"array of objects with fields: {inner_fields}"
                return "array of " + type_to_str(t[0]) if t else "array"
            elif isinstance(t, dict):
                return {k: type_to_str(v) for k, v in t.items()}
            return "string"

        return {k: type_to_str(v) for k, v in template.items()}

    def _build_extraction_prompt(
        self,
        doc_type: str,
        template: Dict[str, Any],
    ) -> str:
        """Build the extraction prompt for the LLM."""
        schema_desc = self._template_to_json_schema(template)
        schema_json = json.dumps(schema_desc, indent=2)

        return f"""You are a document extraction specialist. Analyze the provided document and extract structured data.

DOCUMENT TYPE: {doc_type}

EXTRACTION SCHEMA:
{schema_json}

INSTRUCTIONS:
1. Carefully analyze the document content (text or image)
2. Extract ALL fields defined in the schema
3. Use null for fields that cannot be found or are not applicable
4. For arrays, extract all relevant items
5. For dates, use ISO 8601 format (YYYY-MM-DD)
6. For currency amounts, use numeric values without currency symbols
7. Be precise and accurate - only extract information that is clearly present

RESPONSE FORMAT:
Return ONLY valid JSON matching the schema. Do not include any explanation or markdown.
The response must be parseable by json.loads().

Example response structure:
{{
  "field1": "value1",
  "field2": 123.45,
  "array_field": [
    {{"nested": "value"}}
  ]
}}

Now analyze the document and extract the data:"""

    async def _extract_from_text(
        self,
        content: str,
        doc_type: str,
        template: Dict[str, Any],
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """Extract data from text content using LLM."""
        prompt = self._build_extraction_prompt(doc_type, template)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Document content:\n\n{content}"},
        ]

        try:
            response = await self.llm_client.chat_completion(
                messages=messages,
                model=model or self.default_model,
                temperature=0.1,  # Low temperature for structured extraction
                max_tokens=4000,
            )

            response_content = self.llm_client.get_response_content(response)

            # Parse JSON from response
            extracted_data = self._parse_json_response(response_content)

            if extracted_data is None:
                return ExtractionResult(
                    success=False,
                    document_type=doc_type,
                    raw_text=content[:2000],
                    errors=["Failed to parse extraction response as JSON"],
                    warnings=[f"Raw response: {response_content[:500]}"],
                )

            # Calculate confidence based on field coverage
            confidence = self._calculate_confidence(extracted_data, template)

            return ExtractionResult(
                success=True,
                document_type=doc_type,
                extracted_data=extracted_data,
                confidence=confidence,
                raw_text=content[:2000],
            )

        except Exception as e:
            logger.error(f"Text extraction error: {e}")
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                raw_text=content[:2000],
                errors=[str(e)],
            )

    async def _extract_from_vision(
        self,
        content: bytes,
        file_ext: str,
        doc_type: str,
        template: Dict[str, Any],
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """Extract data from image/PDF using vision-capable LLM."""
        # Encode image to base64
        base64_content = base64.b64encode(content).decode("utf-8")

        # Determine MIME type
        mime_type = mimetypes.guess_type(f"file{file_ext}")[0] or "image/png"
        if file_ext == ".pdf":
            mime_type = "application/pdf"

        prompt = self._build_extraction_prompt(doc_type, template)

        # Build vision message with image
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please analyze this document image and extract the structured data:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_content}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        vision_model = model or self.default_model

        # Ensure we're using a vision-capable model
        if not any(vm in vision_model for vm in ["gpt-4o", "gpt-4-vision", "claude-3", "gemini"]):
            logger.warning(f"Model {vision_model} may not support vision. Switching to gpt-4o")
            vision_model = "openai/gpt-4o"

        try:
            response = await self.llm_client.chat_completion(
                messages=messages,
                model=vision_model,
                temperature=0.1,
                max_tokens=4000,
            )

            response_content = self.llm_client.get_response_content(response)

            # Parse JSON from response
            extracted_data = self._parse_json_response(response_content)

            if extracted_data is None:
                return ExtractionResult(
                    success=False,
                    document_type=doc_type,
                    errors=["Failed to parse extraction response as JSON"],
                    warnings=[f"Raw response: {response_content[:500]}"],
                    metadata={"model_used": vision_model},
                )

            # Calculate confidence
            confidence = self._calculate_confidence(extracted_data, template)

            return ExtractionResult(
                success=True,
                document_type=doc_type,
                extracted_data=extracted_data,
                confidence=confidence,
                metadata={"model_used": vision_model},
            )

        except Exception as e:
            logger.error(f"Vision extraction error: {e}")
            return ExtractionResult(
                success=False,
                document_type=doc_type,
                errors=[str(e)],
                metadata={"model_used": vision_model},
            )

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Clean up response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # Try direct JSON parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in response
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return {"items": json.loads(response[start:end])}
        except json.JSONDecodeError:
            pass

        logger.warning(f"Could not parse JSON from response: {response[:200]}...")
        return None

    def _calculate_confidence(
        self,
        extracted_data: Dict[str, Any],
        template: Dict[str, Any],
    ) -> float:
        """Calculate confidence score based on field coverage."""
        if not extracted_data or not template:
            return 0.0

        template_fields = set(template.keys())
        extracted_fields = set(extracted_data.keys())

        # Count non-null fields that match template
        matched_fields = 0
        for field in template_fields:
            if field in extracted_data:
                value = extracted_data[field]
                if value is not None and value != "" and value != []:
                    matched_fields += 1

        if not template_fields:
            return 1.0

        return matched_fields / len(template_fields)

    async def close(self):
        """Clean up resources."""
        if self.llm_client:
            await self.llm_client.close()


# ============== Convenience Functions ==============

async def process_document(
    file_path: str,
    doc_type: str = "invoice",
    template: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function for one-off document processing.

    Args:
        file_path: Path to document
        doc_type: Document type (invoice, contract, receipt, custom)
        template: Optional custom template

    Returns:
        Extraction result dictionary
    """
    processor = DocumentProcessor()
    try:
        result = await processor.process_document(
            file_path=file_path,
            doc_type=doc_type,
            template=template,
        )
        return result.to_dict()
    finally:
        await processor.close()


# Export templates for external use
__all__ = [
    "DocumentProcessor",
    "DocumentType",
    "ExtractionResult",
    "INVOICE_TEMPLATE",
    "CONTRACT_TEMPLATE",
    "RECEIPT_TEMPLATE",
    "TEMPLATES",
    "process_document",
]
