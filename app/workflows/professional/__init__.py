"""
Professional Workflows Module

High-value professional workflows organized by domain:
- Finance & Legal (4): M&A Due Diligence, Tax Prep, Contract Review, Audit Preparation
- HR & Sales (4): Recruiting Pipeline, RFP Response, Vendor Risk, Employee Onboarding
- Security & Ops (4): SOC Analyst, Vulnerability Assessment, Change Management, DR Test
- Domain-Specific (4): Real Estate, Product Research, Patent Analysis, Meeting Assistant
- Content & Intelligence (2): Lead Scoring, Email Auto-Responder

Total: 18 professional workflows
"""

from app.workflows.professional.finance_legal import (
    MA_DUE_DILIGENCE,
    TAX_PREP_ASSISTANT,
    CONTRACT_REVIEW,
    AUDIT_PREPARATION,
    ALL_FINANCE_LEGAL_WORKFLOWS,
)

from app.workflows.professional.hr_sales import (
    RECRUITING_PIPELINE,
    RFP_PROPOSAL_RESPONSE,
    VENDOR_RISK_ASSESSMENT,
    EMPLOYEE_ONBOARDING,
    ALL_HR_SALES_WORKFLOWS,
)

from app.workflows.professional.security_ops import (
    SOC_ANALYST,
    VULNERABILITY_ASSESSMENT,
    CHANGE_MANAGEMENT,
    DISASTER_RECOVERY_TEST,
    ALL_SECURITY_OPS_WORKFLOWS,
)

from app.workflows.professional.domain_specific import (
    REAL_ESTATE_TRANSACTION,
    PRODUCT_RESEARCH,
    PATENT_ANALYSIS,
    MEETING_ASSISTANT,
    ALL_DOMAIN_SPECIFIC_WORKFLOWS,
)

from app.workflows.professional.content_intel import (
    LEAD_SCORE_FLOW,
    EMAIL_AUTO_RESPONDER,
    ALL_CONTENT_INTEL_WORKFLOWS,
)

# Aggregate all professional workflows
ALL_PROFESSIONAL_WORKFLOWS = {
    **ALL_FINANCE_LEGAL_WORKFLOWS,
    **ALL_HR_SALES_WORKFLOWS,
    **ALL_SECURITY_OPS_WORKFLOWS,
    **ALL_DOMAIN_SPECIFIC_WORKFLOWS,
    **ALL_CONTENT_INTEL_WORKFLOWS,
}

__all__ = [
    # Finance & Legal
    "MA_DUE_DILIGENCE",
    "TAX_PREP_ASSISTANT",
    "CONTRACT_REVIEW",
    "AUDIT_PREPARATION",
    "ALL_FINANCE_LEGAL_WORKFLOWS",
    # HR & Sales
    "RECRUITING_PIPELINE",
    "RFP_PROPOSAL_RESPONSE",
    "VENDOR_RISK_ASSESSMENT",
    "EMPLOYEE_ONBOARDING",
    "ALL_HR_SALES_WORKFLOWS",
    # Security & Ops
    "SOC_ANALYST",
    "VULNERABILITY_ASSESSMENT",
    "CHANGE_MANAGEMENT",
    "DISASTER_RECOVERY_TEST",
    "ALL_SECURITY_OPS_WORKFLOWS",
    # Domain-Specific
    "REAL_ESTATE_TRANSACTION",
    "PRODUCT_RESEARCH",
    "PATENT_ANALYSIS",
    "MEETING_ASSISTANT",
    "ALL_DOMAIN_SPECIFIC_WORKFLOWS",
    # Content & Intelligence
    "LEAD_SCORE_FLOW",
    "EMAIL_AUTO_RESPONDER",
    "ALL_CONTENT_INTEL_WORKFLOWS",
    # Aggregate
    "ALL_PROFESSIONAL_WORKFLOWS",
]
