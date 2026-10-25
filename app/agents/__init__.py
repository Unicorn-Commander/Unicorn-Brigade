"""Agent module"""

from app.agents.agentic_rag import AgenticRAG, RAGContext, RAGResponse, get_agentic_rag
from app.agents.analysis import AnalysisAgent
from app.agents.base import BaseAgent
from app.agents.code import CodeAgent
from app.agents.code_reviewer import (
    CodeReviewer,
    FileChange,
    ReviewCategory,
    ReviewComment,
    ReviewResult,
    ReviewSeverity,
    create_code_reviewer,
)
from app.agents.content_generator import (
    CONTENT_TEMPLATES,
    CalendarEntry,
    ContentGeneratorAgent,
    ContentResult,
    ContentTone,
    ContentType,
    OutputFormat,
    SEOMetadata,
    create_content_generator,
)
from app.agents.customer_support import (
    CustomerSupportAgent,
    FAQEntry,
    SupportChannel,
    SupportMessage,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)
from app.agents.deep_research import DEEP_RESEARCH_TOOL, DeepResearchAgent, deep_research_handler
from app.agents.document_processor import (
    CONTRACT_TEMPLATE,
    INVOICE_TEMPLATE,
    RECEIPT_TEMPLATE,
    TEMPLATES,
    DocumentProcessor,
    DocumentType,
    ExtractionResult,
    process_document,
)
from app.agents.financial_analysis import (
    CURRENCY_RATES,
    Budget,
    BudgetAlert,
    ExpenseCategory,
    FinancialAnalysisAgent,
    FinancialReport,
    ReportPeriod,
    Transaction,
    TransactionType,
)
from app.agents.financial_analysis import (
    AlertSeverity as FinanceAlertSeverity,
)
from app.agents.monitoring_agent import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AnomalyDetector,
    CheckType,
    Incident,
    IncidentStatus,
    LogAnalyzer,
    Metric,
    MetricThreshold,
    MonitoringAgent,
    ServiceCheck,
    ServiceStatus,
    WebhookConfig,
)
from app.agents.research import ResearchAgent
from app.agents.sales_outreach import (
    Campaign,
    EmailSequence,
    Lead,
    LeadEnrichmentAgent,
    LeadStatus,
    PersonalizationAgent,
    ResponseAgent,
    SalesOutreachOrchestrator,
    SequenceAgent,
    create_sales_orchestrator,
)
from app.agents.text_to_sql import TextToSQLAgent, get_text_to_sql_agent

__all__ = [
    "BaseAgent",
    "ResearchAgent",
    "CodeAgent",
    "AnalysisAgent",
    "TextToSQLAgent",
    "get_text_to_sql_agent",
    "AgenticRAG",
    "get_agentic_rag",
    "RAGContext",
    "RAGResponse",
    "DeepResearchAgent",
    "DEEP_RESEARCH_TOOL",
    "deep_research_handler",
    "CustomerSupportAgent",
    "SupportTicket",
    "TicketStatus",
    "TicketPriority",
    "SupportChannel",
    "SupportMessage",
    "FAQEntry",
    "CodeReviewer",
    "create_code_reviewer",
    "ReviewResult",
    "ReviewComment",
    "ReviewCategory",
    "ReviewSeverity",
    "FileChange",
    "DocumentProcessor",
    "DocumentType",
    "ExtractionResult",
    "INVOICE_TEMPLATE",
    "CONTRACT_TEMPLATE",
    "RECEIPT_TEMPLATE",
    "TEMPLATES",
    "process_document",
    # Sales Outreach
    "SalesOutreachOrchestrator",
    "LeadEnrichmentAgent",
    "PersonalizationAgent",
    "SequenceAgent",
    "ResponseAgent",
    "Lead",
    "LeadStatus",
    "EmailSequence",
    "Campaign",
    "create_sales_orchestrator",
    # Content Generation
    "ContentGeneratorAgent",
    "create_content_generator",
    "ContentType",
    "ContentTone",
    "OutputFormat",
    "ContentResult",
    "CalendarEntry",
    "SEOMetadata",
    "CONTENT_TEMPLATES",
    # Financial Analysis
    "FinancialAnalysisAgent",
    "Transaction",
    "Budget",
    "BudgetAlert",
    "FinancialReport",
    "TransactionType",
    "ExpenseCategory",
    "FinanceAlertSeverity",
    "ReportPeriod",
    "CURRENCY_RATES",
    # Monitoring and Alerting
    "MonitoringAgent",
    "AlertSeverity",
    "AlertStatus",
    "ServiceStatus",
    "IncidentStatus",
    "CheckType",
    "Metric",
    "MetricThreshold",
    "Alert",
    "ServiceCheck",
    "Incident",
    "WebhookConfig",
    "AnomalyDetector",
    "LogAnalyzer",
]

# Crisis Investigation Agents: private to Magic Unicorn's deployment and absent
# from the public build (see app/private_features.py).
from app.private_features import crisis_feature_present

if crisis_feature_present():
    from app.agents.crisis_registration import register_crisis_agents
    from app.agents.evidence_correlator import EvidenceCorrelatorAgent
    from app.agents.gap_analyzer import GapAnalyzerAgent
    from app.agents.timeline_builder import TimelineBuilderAgent

    __all__ += [
        "EvidenceCorrelatorAgent",
        "GapAnalyzerAgent",
        "TimelineBuilderAgent",
        "register_crisis_agents",
    ]
