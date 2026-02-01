"""
HuggingFace Integration for Medical AI Models

Provides integration with HuggingFace Inference API for medical AI capabilities:
- Medical text generation (BioMistral, MedAlpaca, PMC-LLaMA)
- Clinical NER (PubMedBERT, BioBERT, ClinicalBERT)
- Medical image classification (RadImageNet, CheXNet, DermNet)
- Medical QA (BioGPT, PubMedQA)
- Feature extraction for medical embeddings

Environment Variables:
    HUGGINGFACE_API_TOKEN: HuggingFace API token for inference API access
"""

import asyncio
import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN", "")
HUGGINGFACE_BASE_URL = "https://api-inference.huggingface.co/models"

# Rate limiting configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 120.0  # seconds for model loading


# =============================================================================
# Medical Model Registry
# =============================================================================

MEDICAL_MODELS = {
    # Text Generation - Medical LLMs
    "BioMistral-7B": "BioMistral/BioMistral-7B",
    "MedAlpaca-13B": "medalpaca/medalpaca-13b",
    "PMC-LLaMA-13B": "axiong/PMC_LLaMA_13B",
    "Meditron-7B": "epfl-llm/meditron-7b",
    "OpenBioLLM-8B": "aaditya/OpenBioLLM-Llama3-8B",

    # Clinical NER - Named Entity Recognition
    "PubMedBERT-NER": "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract",
    "BioBERT-NER": "dmis-lab/biobert-v1.1",
    "ClinicalBERT": "emilyalsentzer/Bio_ClinicalBERT",
    "BioBERT-BC5CDR": "dmis-lab/biobert-base-cased-v1.2-bc5cdr-disease",
    "SciBERT": "allenai/scibert_scivocab_uncased",

    # Medical Image Classification
    "RadImageNet": "StanfordAIMI/RadImageNet",
    "CheXNet": "arnoweng/CheXNet",
    "DermNet": "google/vit-base-patch16-224",  # fine-tuned for dermatology
    "MedCLIP-ViT": "flaviagiammarino/pubmed-clip-vit-base-patch32",
    "BiomedCLIP": "microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",

    # Medical QA
    "BioGPT": "microsoft/biogpt",
    "BioGPT-QA": "microsoft/BioGPT-Large-PubMedQA",
    "PubMedQA": "pubmedqa/pubmedqa-bert",
    "MedQuAD": "medalpaca/medalpaca-7b",

    # Text Classification - Medical
    "BioBERT-ChemProt": "dmis-lab/biobert-base-cased-v1.2-chemprot",
    "PubMedBERT-DDI": "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",

    # Embeddings
    "PubMedBERT-Embeddings": "pritamdeka/S-PubMedBert-MS-MARCO",
    "BioLORD": "FremyCompany/BioLORD-2023-M",
    "MedCPT": "ncbi/MedCPT-Query-Encoder",
}

# Model categories for easy filtering
MODEL_CATEGORIES = {
    "text_generation": [
        "BioMistral-7B", "MedAlpaca-13B", "PMC-LLaMA-13B",
        "Meditron-7B", "OpenBioLLM-8B"
    ],
    "ner": [
        "PubMedBERT-NER", "BioBERT-NER", "ClinicalBERT",
        "BioBERT-BC5CDR", "SciBERT"
    ],
    "image_classification": [
        "RadImageNet", "CheXNet", "DermNet",
        "MedCLIP-ViT", "BiomedCLIP"
    ],
    "question_answering": [
        "BioGPT", "BioGPT-QA", "PubMedQA", "MedQuAD"
    ],
    "text_classification": [
        "BioBERT-ChemProt", "PubMedBERT-DDI"
    ],
    "embeddings": [
        "PubMedBERT-Embeddings", "BioLORD", "MedCPT"
    ],
}

# Modality mappings for medical images
IMAGE_MODALITIES = {
    "xray": ["CheXNet", "RadImageNet"],
    "ct": ["RadImageNet"],
    "mri": ["RadImageNet"],
    "pathology": ["BiomedCLIP", "MedCLIP-ViT"],
    "dermatology": ["DermNet"],
}


# =============================================================================
# Pydantic Models
# =============================================================================

class MedicalEntity(BaseModel):
    """Extracted medical entity"""
    text: str = Field(..., description="Entity text")
    type: str = Field(..., description="Entity type (symptom, medication, condition, etc.)")
    start: int = Field(0, description="Start character position")
    end: int = Field(0, description="End character position")
    confidence: float = Field(0.0, description="Confidence score")


class DrugInteraction(BaseModel):
    """Drug interaction information"""
    drug1: str = Field(..., description="First drug name")
    drug2: str = Field(..., description="Second drug name")
    interaction_type: str = Field(..., description="Type of interaction")
    severity: str = Field(..., description="Severity level (mild, moderate, severe)")
    description: str = Field("", description="Description of the interaction")


class ICDCode(BaseModel):
    """ICD-10 code suggestion"""
    code: str = Field(..., description="ICD-10 code")
    description: str = Field(..., description="Code description")
    confidence: float = Field(0.0, description="Confidence score")


class ImageAnalysisResult(BaseModel):
    """Medical image analysis result"""
    findings: List[Dict[str, Any]] = Field(default_factory=list, description="Detected findings")
    modality: str = Field("", description="Detected modality")
    confidence: float = Field(0.0, description="Overall confidence")
    recommendations: List[str] = Field(default_factory=list, description="Follow-up recommendations")


# =============================================================================
# HuggingFace Client
# =============================================================================

class HuggingFaceClient:
    """
    Async client for HuggingFace Inference API with medical model support.

    Features:
    - Async HTTP calls with httpx
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Model loading wait
    - Support for various inference tasks
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the HuggingFace client.

        Args:
            api_token: HuggingFace API token (falls back to env var)
        """
        self.api_token = api_token or HUGGINGFACE_API_TOKEN
        self.base_url = HUGGINGFACE_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_token:
            logger.warning(
                "HUGGINGFACE_API_TOKEN not set. "
                "Some models may not be accessible or rate-limited."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT),
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def _make_request(
        self,
        model: str,
        payload: Dict[str, Any],
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make an API request with retry logic.

        Args:
            model: Model ID (short name or full HuggingFace path)
            payload: Request payload
            retry_count: Current retry attempt

        Returns:
            API response as dict

        Raises:
            HuggingFaceError: On API errors after retries exhausted
        """
        # Resolve model name to full path
        model_path = MEDICAL_MODELS.get(model, model)
        url = f"{self.base_url}/{model_path}"

        client = await self._get_client()

        try:
            response = await client.post(url, json=payload)

            # Handle model loading
            if response.status_code == 503:
                data = response.json()
                if "estimated_time" in data:
                    wait_time = min(data["estimated_time"], 60)
                    logger.info(f"Model {model} loading, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(model, payload, retry_count)

            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    logger.warning(f"Rate limited, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await self._make_request(model, payload, retry_count + 1)
                raise HuggingFaceRateLimitError("Rate limit exceeded after retries")

            # Handle other errors
            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
                raise HuggingFaceAPIError(
                    f"API error ({response.status_code}): {error_msg}"
                )

            return response.json()

        except httpx.TimeoutException:
            if retry_count < MAX_RETRIES:
                logger.warning(f"Request timeout, retrying ({retry_count + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(RETRY_DELAY)
                return await self._make_request(model, payload, retry_count + 1)
            raise HuggingFaceTimeoutError("Request timed out after retries")
        except httpx.RequestError as e:
            raise HuggingFaceConnectionError(f"Connection error: {str(e)}")

    async def text_generation(
        self,
        model: str,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.95,
        do_sample: bool = True,
        **kwargs,
    ) -> str:
        """
        Generate text using medical language models.

        Args:
            model: Model name (e.g., "BioMistral-7B", "MedAlpaca-13B")
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            do_sample: Whether to use sampling
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": do_sample,
                "return_full_text": False,
                **kwargs,
            },
        }

        result = await self._make_request(model, payload)

        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "")
        return ""

    async def text_classification(
        self,
        model: str,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Classify text using medical classification models.

        Args:
            model: Model name (e.g., "BioBERT-ChemProt")
            text: Text to classify

        Returns:
            List of classification results with labels and scores
        """
        payload = {"inputs": text}
        result = await self._make_request(model, payload)

        # Normalize result format
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], list):
                return result[0]
            return result
        return [result]

    async def token_classification(
        self,
        model: str,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Perform token classification (NER) using medical models.

        Args:
            model: Model name (e.g., "PubMedBERT-NER", "BioBERT-NER")
            text: Text for entity extraction

        Returns:
            List of entities with word, entity_group, score, start, end
        """
        payload = {"inputs": text}
        result = await self._make_request(model, payload)

        if isinstance(result, list):
            return result
        return [result]

    async def image_classification(
        self,
        model: str,
        image_bytes: bytes,
    ) -> List[Dict[str, Any]]:
        """
        Classify medical images.

        Args:
            model: Model name (e.g., "CheXNet", "RadImageNet")
            image_bytes: Raw image bytes

        Returns:
            List of classifications with labels and scores
        """
        # For image models, we send base64-encoded data
        model_path = MEDICAL_MODELS.get(model, model)
        url = f"{self.base_url}/{model_path}"

        client = await self._get_client()

        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        response = await client.post(
            url,
            content=image_bytes,
            headers=headers,
        )

        if response.status_code != 200:
            raise HuggingFaceAPIError(f"Image classification failed: {response.text}")

        result = response.json()
        if isinstance(result, list):
            return result
        return [result]

    async def feature_extraction(
        self,
        model: str,
        text: str,
    ) -> List[float]:
        """
        Extract embeddings from medical text.

        Args:
            model: Model name (e.g., "PubMedBERT-Embeddings", "BioLORD")
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        payload = {"inputs": text}
        result = await self._make_request(model, payload)

        # Handle different response formats
        if isinstance(result, list):
            if len(result) > 0:
                if isinstance(result[0], list):
                    # Sentence embeddings - average over tokens
                    return [sum(x) / len(result) for x in zip(*result)]
                return result
        return []

    async def question_answering(
        self,
        model: str,
        question: str,
        context: str,
    ) -> Dict[str, Any]:
        """
        Answer questions based on medical context.

        Args:
            model: Model name (e.g., "BioGPT-QA", "PubMedQA")
            question: Question to answer
            context: Context passage

        Returns:
            Answer with score and span information
        """
        payload = {
            "inputs": {
                "question": question,
                "context": context,
            }
        }

        result = await self._make_request(model, payload)
        return result if isinstance(result, dict) else {"answer": str(result)}

    async def fill_mask(
        self,
        model: str,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Fill masked tokens in medical text.

        Args:
            model: Model name (e.g., "PubMedBERT-NER", "BioBERT-NER")
            text: Text with [MASK] token

        Returns:
            List of suggestions with tokens and scores
        """
        payload = {"inputs": text}
        result = await self._make_request(model, payload)

        if isinstance(result, list):
            return result
        return [result]

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# =============================================================================
# Medical Analyzer - High-Level Interface
# =============================================================================

class MedicalAnalyzer:
    """
    High-level interface for common medical AI tasks.

    Provides convenient methods for:
    - Medical entity extraction (symptoms, medications, conditions)
    - Radiology image analysis
    - Drug interaction checking
    - Clinical note summarization
    - ICD-10 code suggestion
    """

    def __init__(self, hf_client: Optional[HuggingFaceClient] = None):
        """
        Initialize the Medical Analyzer.

        Args:
            hf_client: Optional HuggingFace client instance
        """
        self.hf = hf_client or HuggingFaceClient()

        # Default models for each task
        self.default_models = {
            "ner": "ClinicalBERT",
            "text_generation": "BioMistral-7B",
            "image_classification": "CheXNet",
            "embeddings": "PubMedBERT-Embeddings",
            "qa": "BioGPT-QA",
        }

    async def extract_medical_entities(
        self,
        clinical_text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract medical entities from clinical text.

        Identifies:
        - Symptoms and signs
        - Medications and dosages
        - Medical conditions and diagnoses
        - Procedures and treatments
        - Anatomical locations

        Args:
            clinical_text: Clinical narrative text
            model: Optional model override

        Returns:
            Dict with categorized entities
        """
        model = model or self.default_models["ner"]

        try:
            # Get raw NER results
            entities = await self.hf.token_classification(model, clinical_text)

            # Categorize entities
            categorized = {
                "symptoms": [],
                "medications": [],
                "conditions": [],
                "procedures": [],
                "anatomy": [],
                "other": [],
            }

            for entity in entities:
                entity_obj = MedicalEntity(
                    text=entity.get("word", ""),
                    type=entity.get("entity_group", entity.get("entity", "UNKNOWN")),
                    start=entity.get("start", 0),
                    end=entity.get("end", 0),
                    confidence=entity.get("score", 0.0),
                )

                # Map entity types to categories
                entity_type = entity_obj.type.upper()
                if any(t in entity_type for t in ["SIGN", "SYMPTOM", "FINDING"]):
                    categorized["symptoms"].append(entity_obj.model_dump())
                elif any(t in entity_type for t in ["DRUG", "MED", "CHEM"]):
                    categorized["medications"].append(entity_obj.model_dump())
                elif any(t in entity_type for t in ["DISEASE", "CONDITION", "DIAGNOSIS"]):
                    categorized["conditions"].append(entity_obj.model_dump())
                elif any(t in entity_type for t in ["PROCEDURE", "TREATMENT"]):
                    categorized["procedures"].append(entity_obj.model_dump())
                elif any(t in entity_type for t in ["ANAT", "BODY", "ORGAN"]):
                    categorized["anatomy"].append(entity_obj.model_dump())
                else:
                    categorized["other"].append(entity_obj.model_dump())

            return {
                "success": True,
                "entities": categorized,
                "raw_entities": entities,
                "model": model,
            }

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "entities": {},
            }

    async def analyze_radiology_image(
        self,
        image_bytes: bytes,
        modality: str = "xray",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a medical image.

        Supports modalities:
        - xray: Chest X-rays, skeletal X-rays
        - ct: CT scans
        - mri: MRI images
        - pathology: Histopathology slides
        - dermatology: Skin lesion images

        Args:
            image_bytes: Raw image data
            modality: Image modality
            model: Optional model override

        Returns:
            Analysis results with findings and recommendations
        """
        # Select appropriate model for modality
        if model is None:
            modality_models = IMAGE_MODALITIES.get(modality, ["RadImageNet"])
            model = modality_models[0]

        try:
            # Get classification results
            results = await self.hf.image_classification(model, image_bytes)

            # Process findings
            findings = []
            for result in results[:10]:  # Top 10 findings
                findings.append({
                    "label": result.get("label", ""),
                    "score": result.get("score", 0.0),
                    "is_significant": result.get("score", 0) > 0.5,
                })

            # Generate recommendations based on findings
            recommendations = []
            for finding in findings:
                if finding["is_significant"]:
                    if "normal" not in finding["label"].lower():
                        recommendations.append(
                            f"Consider clinical correlation for: {finding['label']}"
                        )

            return {
                "success": True,
                "modality": modality,
                "model": model,
                "findings": findings,
                "recommendations": recommendations or ["No significant findings detected"],
                "confidence": findings[0]["score"] if findings else 0.0,
            }

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "findings": [],
            }

    async def get_drug_interactions(
        self,
        medications: List[str],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check for potential drug interactions.

        Uses NLP models to identify potential interactions between
        the provided list of medications.

        Args:
            medications: List of medication names
            model: Optional model override

        Returns:
            Dict with interaction information
        """
        model = model or self.default_models["text_generation"]

        if len(medications) < 2:
            return {
                "success": True,
                "interactions": [],
                "message": "Need at least 2 medications to check interactions",
            }

        try:
            # Create prompt for drug interaction analysis
            med_list = ", ".join(medications)
            prompt = f"""Analyze potential drug interactions between the following medications:
{med_list}

For each potential interaction, provide:
1. The two drugs involved
2. Type of interaction (pharmacokinetic/pharmacodynamic)
3. Severity (mild/moderate/severe)
4. Brief clinical recommendation

Response format:
INTERACTION: [drug1] + [drug2]
TYPE: [type]
SEVERITY: [severity]
RECOMMENDATION: [recommendation]
---"""

            # Generate analysis
            response = await self.hf.text_generation(
                model,
                prompt,
                max_new_tokens=512,
                temperature=0.3,
            )

            # Parse interactions from response
            interactions = self._parse_drug_interactions(response, medications)

            return {
                "success": True,
                "medications": medications,
                "interactions": interactions,
                "model": model,
                "raw_response": response,
            }

        except Exception as e:
            logger.error(f"Drug interaction check failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "interactions": [],
            }

    def _parse_drug_interactions(
        self,
        response: str,
        medications: List[str],
    ) -> List[Dict[str, Any]]:
        """Parse drug interactions from model response."""
        interactions = []

        # Simple parsing - look for interaction patterns
        blocks = response.split("---")
        for block in blocks:
            if "INTERACTION:" in block:
                interaction = {}
                for line in block.strip().split("\n"):
                    if line.startswith("INTERACTION:"):
                        drugs = line.replace("INTERACTION:", "").strip()
                        parts = drugs.split("+")
                        if len(parts) >= 2:
                            interaction["drug1"] = parts[0].strip()
                            interaction["drug2"] = parts[1].strip()
                    elif line.startswith("TYPE:"):
                        interaction["interaction_type"] = line.replace("TYPE:", "").strip()
                    elif line.startswith("SEVERITY:"):
                        interaction["severity"] = line.replace("SEVERITY:", "").strip().lower()
                    elif line.startswith("RECOMMENDATION:"):
                        interaction["description"] = line.replace("RECOMMENDATION:", "").strip()

                if "drug1" in interaction and "drug2" in interaction:
                    interactions.append(interaction)

        return interactions

    async def summarize_clinical_notes(
        self,
        notes: str,
        model: Optional[str] = None,
        max_length: int = 256,
    ) -> str:
        """
        Summarize clinical documentation.

        Generates a concise summary of clinical notes while preserving
        key medical information.

        Args:
            notes: Clinical notes text
            model: Optional model override
            max_length: Maximum summary length in tokens

        Returns:
            Summarized clinical notes
        """
        model = model or self.default_models["text_generation"]

        try:
            prompt = f"""Summarize the following clinical notes, preserving key medical findings, diagnoses, and treatment plans:

Clinical Notes:
{notes}

Summary:"""

            summary = await self.hf.text_generation(
                model,
                prompt,
                max_new_tokens=max_length,
                temperature=0.3,
            )

            return summary.strip()

        except Exception as e:
            logger.error(f"Clinical summary failed: {e}")
            return f"Error generating summary: {str(e)}"

    async def generate_icd_codes(
        self,
        diagnosis_text: str,
        model: Optional[str] = None,
        max_codes: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Suggest ICD-10 codes for diagnoses.

        Analyzes diagnosis text and suggests appropriate ICD-10 codes
        with confidence scores.

        Args:
            diagnosis_text: Diagnosis description
            model: Optional model override
            max_codes: Maximum number of codes to return

        Returns:
            List of ICD code suggestions
        """
        model = model or self.default_models["text_generation"]

        try:
            prompt = f"""Given the following diagnosis, suggest the most appropriate ICD-10 codes:

Diagnosis: {diagnosis_text}

Provide up to {max_codes} ICD-10 codes in order of relevance. Format each as:
CODE: [code] - [description]

ICD-10 Codes:"""

            response = await self.hf.text_generation(
                model,
                prompt,
                max_new_tokens=256,
                temperature=0.2,
            )

            # Parse ICD codes from response
            codes = self._parse_icd_codes(response)

            return codes[:max_codes]

        except Exception as e:
            logger.error(f"ICD code generation failed: {e}")
            return []

    def _parse_icd_codes(self, response: str) -> List[Dict[str, Any]]:
        """Parse ICD codes from model response."""
        codes = []

        # Pattern to match ICD-10 codes (e.g., E11.9, J18.9, M54.5)
        pattern = r"([A-Z]\d{2}\.?\d*)\s*[-:]\s*(.+?)(?=\n|$)"
        matches = re.findall(pattern, response, re.IGNORECASE)

        for i, (code, description) in enumerate(matches):
            codes.append({
                "code": code.upper(),
                "description": description.strip(),
                "confidence": max(0.9 - (i * 0.1), 0.5),  # Decreasing confidence
            })

        return codes

    async def answer_medical_question(
        self,
        question: str,
        context: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Answer a medical question.

        Args:
            question: Medical question
            context: Optional context passage
            model: Optional model override

        Returns:
            Answer with confidence and sources
        """
        model = model or self.default_models["qa"]

        try:
            if context:
                # Use QA model with context
                result = await self.hf.question_answering(model, question, context)
                return {
                    "success": True,
                    "answer": result.get("answer", ""),
                    "confidence": result.get("score", 0.0),
                    "model": model,
                }
            else:
                # Use text generation for open-ended questions
                prompt = f"""Medical Question: {question}

Provide a clear, accurate medical answer based on current clinical guidelines:

Answer:"""

                answer = await self.hf.text_generation(
                    self.default_models["text_generation"],
                    prompt,
                    max_new_tokens=256,
                    temperature=0.3,
                )

                return {
                    "success": True,
                    "answer": answer.strip(),
                    "confidence": 0.7,  # Default confidence for generated answers
                    "model": self.default_models["text_generation"],
                }

        except Exception as e:
            logger.error(f"Medical QA failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "answer": "",
            }

    async def get_medical_embeddings(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate medical text embeddings.

        Useful for semantic search, similarity matching, and RAG.

        Args:
            texts: Single text or list of texts
            model: Optional model override

        Returns:
            Embeddings and metadata
        """
        model = model or self.default_models["embeddings"]

        if isinstance(texts, str):
            texts = [texts]

        try:
            embeddings = []
            for text in texts:
                embedding = await self.hf.feature_extraction(model, text)
                embeddings.append(embedding)

            return {
                "success": True,
                "embeddings": embeddings,
                "dimension": len(embeddings[0]) if embeddings else 0,
                "model": model,
            }

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "embeddings": [],
            }

    async def close(self):
        """Close underlying clients."""
        await self.hf.close()


# =============================================================================
# Custom Exceptions
# =============================================================================

class HuggingFaceError(Exception):
    """Base exception for HuggingFace errors."""
    pass


class HuggingFaceAPIError(HuggingFaceError):
    """API-related errors."""
    pass


class HuggingFaceRateLimitError(HuggingFaceError):
    """Rate limiting errors."""
    pass


class HuggingFaceTimeoutError(HuggingFaceError):
    """Timeout errors."""
    pass


class HuggingFaceConnectionError(HuggingFaceError):
    """Connection errors."""
    pass


# =============================================================================
# Module-Level Utilities
# =============================================================================

# Singleton client instance
_hf_client: Optional[HuggingFaceClient] = None
_medical_analyzer: Optional[MedicalAnalyzer] = None


def get_huggingface_client() -> HuggingFaceClient:
    """Get or create the singleton HuggingFace client."""
    global _hf_client
    if _hf_client is None:
        _hf_client = HuggingFaceClient()
    return _hf_client


def get_medical_analyzer() -> MedicalAnalyzer:
    """Get or create the singleton Medical Analyzer."""
    global _medical_analyzer
    if _medical_analyzer is None:
        _medical_analyzer = MedicalAnalyzer(get_huggingface_client())
    return _medical_analyzer


async def close_clients():
    """Close all singleton clients."""
    global _hf_client, _medical_analyzer
    if _medical_analyzer:
        await _medical_analyzer.close()
        _medical_analyzer = None
    if _hf_client:
        await _hf_client.close()
        _hf_client = None


def list_medical_models(category: Optional[str] = None) -> Dict[str, Any]:
    """
    List available medical models.

    Args:
        category: Optional category filter (text_generation, ner, etc.)

    Returns:
        Dict with model information
    """
    if category:
        model_names = MODEL_CATEGORIES.get(category, [])
        models = {name: MEDICAL_MODELS[name] for name in model_names if name in MEDICAL_MODELS}
    else:
        models = MEDICAL_MODELS.copy()

    return {
        "models": models,
        "categories": MODEL_CATEGORIES,
        "modalities": IMAGE_MODALITIES,
        "count": len(models),
    }


def is_enabled() -> bool:
    """Check if HuggingFace integration is configured."""
    return bool(HUGGINGFACE_API_TOKEN)
