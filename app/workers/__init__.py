"""
Workers Module for Unicorn Brigade Workflow Engine

Workers are bounded, single-purpose execution units with:
- Timeout enforcement
- Typed artifact production
- Escalation capability
- Standard result format

Available Workers:
- ResearchWorker: Information gathering and synthesis
- DeepResearchWorker: Multi-pass comprehensive research
- CodeWorker: Code generation, review, and refactoring
- ExtractorWorker: Structured data extraction
- TableExtractor: Tabular data extraction
- EntityExtractor: Named entity extraction
- ReportWorker: Report and document generation
- SummaryWorker: Quick summary generation
- DigestWorker: Daily/weekly digest creation
- OpsWorker: System operations and integrations
- DatabaseWorker: Database query execution
"""

from app.workers.base import (
    BaseWorker,
    WorkerResult,
    WorkerStatus,
    WorkerArtifact,
)

from app.workers.research import (
    ResearchWorker,
    DeepResearchWorker,
)

from app.workers.code import (
    CodeWorker,
)

from app.workers.extractor import (
    ExtractorWorker,
    TableExtractor,
    EntityExtractor,
)

from app.workers.report import (
    ReportWorker,
    ReportType,
    SummaryWorker,
    DigestWorker,
)

from app.workers.ops import (
    OpsWorker,
    DatabaseWorker,
)


# Worker registry for dynamic lookup
WORKER_REGISTRY = {
    "research": ResearchWorker,
    "deep_research": DeepResearchWorker,
    "code": CodeWorker,
    "extractor": ExtractorWorker,
    "table_extractor": TableExtractor,
    "entity_extractor": EntityExtractor,
    "report": ReportWorker,
    "summary": SummaryWorker,
    "digest": DigestWorker,
    "ops": OpsWorker,
    "database": DatabaseWorker,
}


def get_worker(worker_type: str, **kwargs) -> BaseWorker:
    """
    Factory function to get a worker instance by type.

    Args:
        worker_type: The type of worker (e.g., "research", "code")
        **kwargs: Arguments to pass to worker constructor

    Returns:
        BaseWorker instance

    Raises:
        ValueError: If worker type is not found
    """
    worker_class = WORKER_REGISTRY.get(worker_type.lower())
    if not worker_class:
        raise ValueError(
            f"Unknown worker type: {worker_type}. "
            f"Available: {list(WORKER_REGISTRY.keys())}"
        )
    return worker_class(**kwargs)


def list_workers() -> list:
    """Get list of available worker types with descriptions"""
    return [
        {
            "type": name,
            "name": cls.name,
            "description": cls.description,
            "timeout": cls.default_timeout,
        }
        for name, cls in WORKER_REGISTRY.items()
    ]


__all__ = [
    # Base
    "BaseWorker",
    "WorkerResult",
    "WorkerStatus",
    "WorkerArtifact",
    # Research
    "ResearchWorker",
    "DeepResearchWorker",
    # Code
    "CodeWorker",
    # Extraction
    "ExtractorWorker",
    "TableExtractor",
    "EntityExtractor",
    # Report
    "ReportWorker",
    "ReportType",
    "SummaryWorker",
    "DigestWorker",
    # Ops
    "OpsWorker",
    "DatabaseWorker",
    # Registry
    "WORKER_REGISTRY",
    "get_worker",
    "list_workers",
]
