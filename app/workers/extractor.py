"""
Extractor Worker - Structured data extraction from text

Capabilities:
- Entity extraction (names, dates, numbers, etc.)
- JSON/schema extraction from unstructured text
- Table extraction
- Key-value pair extraction
"""

from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from app.workers.base import BaseWorker, WorkerResult, WorkerStatus, WorkerArtifact
import logging
import json
import re

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """You are a precise data extraction specialist. Your task is to:

1. Extract structured data from the provided text
2. Match the exact schema/format requested
3. Handle missing data gracefully (use null, not guesses)
4. Maintain data types (strings, numbers, dates, booleans)

CRITICAL RULES:
- Only extract information explicitly present in the text
- Never infer or guess missing values - use null
- Preserve exact formatting of values (dates, phone numbers, etc.)
- If a field is ambiguous, mark it with a confidence score

Output valid JSON that matches the requested schema exactly."""


class ExtractorWorker(BaseWorker):
    """
    Worker for extracting structured data from unstructured text.

    Produces JSON artifacts matching specified schemas.
    """

    name = "ExtractorWorker"
    description = "Structured data extraction"
    default_timeout = 90  # 1.5 minutes

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Execute extraction task"""
        logger.info(f"{self.name}: Extracting - {task[:100]}...")

        source_text = context.get("text", context.get("source", ""))
        schema = context.get("schema")
        fields = context.get("fields", [])

        if not source_text:
            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.FAILED,
                error="No source text provided in context",
                error_type="ValidationError",
            )

        # Build extraction prompt
        schema_text = self._build_schema_prompt(schema, fields)

        user_prompt = f"""Extraction Task: {task}

Source Text:
---
{source_text}
---

{schema_text}

Extract the data and return valid JSON."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.1,  # Very low for extraction accuracy
                max_tokens=2000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            # Parse JSON from response
            extracted_data = self._parse_json_response(content)

            # Validate against schema if provided
            validation_result = self._validate_extraction(extracted_data, schema, fields)

            artifacts = [
                self.create_artifact(
                    name="extracted_data",
                    content=extracted_data,
                    artifact_type="json",
                    metadata={"validation": validation_result},
                ),
            ]

            # Add raw response
            artifacts.append(
                self.create_artifact(
                    name="raw_response",
                    content=content,
                    artifact_type="text",
                )
            )

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=json.dumps(extracted_data, indent=2) if extracted_data else content,
                artifacts=artifacts,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                model_used=response.get("model"),
                provider=response.get("provider"),
            )

        except Exception as e:
            logger.error(f"{self.name}: Extraction failed - {e}")
            raise

    def _build_schema_prompt(
        self,
        schema: Optional[Dict[str, Any]],
        fields: List[str],
    ) -> str:
        """Build schema description for prompt"""
        if schema:
            return f"Extract data matching this JSON schema:\n```json\n{json.dumps(schema, indent=2)}\n```"

        if fields:
            field_list = "\n".join(f"- {field}" for field in fields)
            return f"Extract these fields:\n{field_list}"

        return "Extract all relevant structured data as JSON."

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response"""
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to parse entire content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in content
        brace_match = re.search(r'\{[\s\S]*\}', content)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        # Try to find JSON array
        bracket_match = re.search(r'\[[\s\S]*\]', content)
        if bracket_match:
            try:
                return json.loads(bracket_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _validate_extraction(
        self,
        data: Optional[Dict[str, Any]],
        schema: Optional[Dict[str, Any]],
        fields: List[str],
    ) -> Dict[str, Any]:
        """Validate extracted data against schema/fields"""
        if data is None:
            return {
                "valid": False,
                "error": "Failed to parse JSON from response",
            }

        if schema:
            # Basic schema validation
            required = schema.get("required", [])
            missing = [f for f in required if f not in data]
            if missing:
                return {
                    "valid": False,
                    "missing_required": missing,
                }

        if fields:
            # Check if requested fields are present
            present = [f for f in fields if f in data]
            missing = [f for f in fields if f not in data]
            return {
                "valid": len(missing) == 0,
                "fields_present": present,
                "fields_missing": missing,
                "completeness": len(present) / len(fields) if fields else 1.0,
            }

        return {"valid": True}

    async def extract_to_model(
        self,
        text: str,
        model_class: Type[BaseModel],
        user_id: str = "system",
        llm_model: str = "default",
    ) -> WorkerResult:
        """
        Extract data to a Pydantic model.

        Convenience method for typed extraction.
        """
        # Generate schema from Pydantic model
        schema = model_class.model_json_schema()

        return await self.execute(
            task=f"Extract data matching the {model_class.__name__} schema",
            context={
                "text": text,
                "schema": schema,
            },
            user_id=user_id,
            model=llm_model,
        )


class TableExtractor(ExtractorWorker):
    """
    Specialized extractor for tabular data.

    Extracts tables from text into structured formats.
    """

    name = "TableExtractor"
    description = "Table data extraction"

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Extract tabular data"""
        source_text = context.get("text", context.get("source", ""))
        headers = context.get("headers", [])

        table_prompt = """You extract tabular data from text. Rules:
1. Identify rows and columns in the data
2. Output as JSON array of objects
3. Use consistent keys for columns
4. Handle merged cells and irregular formatting

Return: {"headers": [...], "rows": [{...}, {...}]}"""

        header_hint = ""
        if headers:
            header_hint = f"\nExpected columns: {', '.join(headers)}"

        user_prompt = f"""Extract table data from this text:{header_hint}

Text:
---
{source_text}
---

Return the data as a JSON object with 'headers' and 'rows'."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": table_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.1,
                max_tokens=2500,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            table_data = self._parse_json_response(content)

            artifacts = [
                self.create_artifact(
                    name="table_data",
                    content=table_data,
                    artifact_type="table",
                    metadata={
                        "row_count": len(table_data.get("rows", [])) if table_data else 0,
                    },
                ),
            ]

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=json.dumps(table_data, indent=2) if table_data else content,
                artifacts=artifacts,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                model_used=response.get("model"),
                provider=response.get("provider"),
            )

        except Exception as e:
            logger.error(f"{self.name}: Table extraction failed - {e}")
            raise


class EntityExtractor(ExtractorWorker):
    """
    Specialized extractor for named entities.

    Extracts people, organizations, locations, dates, etc.
    """

    name = "EntityExtractor"
    description = "Named entity extraction"

    ENTITY_TYPES = [
        "PERSON",
        "ORGANIZATION",
        "LOCATION",
        "DATE",
        "TIME",
        "MONEY",
        "PERCENT",
        "EMAIL",
        "PHONE",
        "URL",
    ]

    async def _execute_impl(
        self,
        task: str,
        context: Dict[str, Any],
        user_id: str,
        model: str,
    ) -> WorkerResult:
        """Extract named entities"""
        source_text = context.get("text", context.get("source", ""))
        entity_types = context.get("entity_types", self.ENTITY_TYPES)

        entity_prompt = f"""You extract named entities from text. Entity types:
{', '.join(entity_types)}

Rules:
1. Extract all instances of each entity type
2. Include the exact text and normalized form
3. Include position/context when possible
4. Group by entity type

Return JSON: {{"entities": {{"TYPE": [{{"text": "...", "normalized": "..."}}]}}}}"""

        user_prompt = f"""Extract named entities from this text:

---
{source_text}
---

Return all {', '.join(entity_types)} entities found."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": entity_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.1,
                max_tokens=2000,
                user_id=user_id,
            )

            content = response["content"]
            usage = response.get("usage", {})

            entity_data = self._parse_json_response(content)

            # Count entities
            entity_counts = {}
            if entity_data and "entities" in entity_data:
                for etype, entities in entity_data["entities"].items():
                    entity_counts[etype] = len(entities) if isinstance(entities, list) else 0

            artifacts = [
                self.create_artifact(
                    name="entities",
                    content=entity_data,
                    artifact_type="json",
                    metadata={"counts": entity_counts},
                ),
            ]

            return WorkerResult(
                worker_name=self.name,
                status=WorkerStatus.COMPLETED,
                output=json.dumps(entity_data, indent=2) if entity_data else content,
                artifacts=artifacts,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                model_used=response.get("model"),
                provider=response.get("provider"),
            )

        except Exception as e:
            logger.error(f"{self.name}: Entity extraction failed - {e}")
            raise
