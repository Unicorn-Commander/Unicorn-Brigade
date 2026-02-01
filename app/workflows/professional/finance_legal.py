"""
Finance & Legal Professional Workflows

4 high-value workflows for finance and legal professionals:
1. M&A Due Diligence - Comprehensive acquisition target analysis
2. Tax Preparation Assistant - Tax return preparation and optimization
3. Contract Review Pipeline - Legal contract analysis and risk assessment
4. Audit Preparation - Financial audit readiness workflow
"""

from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
)
from app.workflows.team_leads import (
    RESEARCH_TEAM_LEAD,
    FINANCE_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    CONTENT_TEAM_LEAD,
)


# =============================================================================
# 1. M&A DUE DILIGENCE
# =============================================================================

MA_DUE_DILIGENCE = WorkflowDefinition(
    id="ma-due-diligence",
    name="M&A Due Diligence Pipeline",
    description="Comprehensive acquisition target analysis including financial, legal, and operational due diligence",
    version="1.0.0",
    tags=["finance", "legal", "ma", "due-diligence"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an M&A due diligence workflow.
Your goal is to produce a comprehensive analysis of the acquisition target.
Coordinate between Finance, Legal, and Research teams to identify all risks and opportunities.""",

    team_leads=[FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["target_company", "deal_size", "industry", "transaction_type"],
    final_outputs=["financial_analysis", "legal_review", "risk_assessment", "deal_memo", "recommendation"],

    steps=[
        WorkflowStep(
            id="company-research",
            name="Target Company Research",
            description="Research company background, management, market position, competitors",
            executor="research-lead",
            inputs={"topic": "inputs.target_company", "industry": "inputs.industry"},
            outputs=["company_profile", "management_analysis", "market_position", "competitive_landscape"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="financial-dd",
            name="Financial Due Diligence",
            description="Analyze financial statements, revenue quality, working capital, debt structure",
            executor="finance-lead",
            inputs={
                "company": "company-research.company_profile",
                "deal_size": "inputs.deal_size",
            },
            outputs=["financial_health", "revenue_analysis", "working_capital_report", "debt_analysis", "valuation"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="legal-dd",
            name="Legal Due Diligence",
            description="Review corporate structure, contracts, litigation, IP, regulatory compliance",
            executor="legal-lead",
            inputs={
                "company": "company-research.company_profile",
                "transaction_type": "inputs.transaction_type",
            },
            outputs=["legal_structure", "contract_review", "litigation_risks", "ip_analysis", "compliance_assessment"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="risk-assessment",
            name="Integrated Risk Assessment",
            description="Synthesize financial, legal, and operational risks",
            executor="orchestrator",
            inputs={
                "financial": "financial-dd.financial_health",
                "legal": "legal-dd.litigation_risks",
                "market": "company-research.competitive_landscape",
            },
            outputs=["risk_matrix", "deal_breakers", "mitigation_strategies"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review identified risks. Should we proceed with drafting the deal memo?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="deal-memo",
            name="Draft Deal Memo",
            description="Create comprehensive deal memo with recommendation",
            executor="content-lead",
            inputs={
                "company": "company-research.company_profile",
                "financials": "financial-dd.valuation",
                "legal": "legal-dd.legal_structure",
                "risks": "risk-assessment.risk_matrix",
                "deal_size": "inputs.deal_size",
            },
            outputs=["deal_memo", "executive_summary", "recommendation"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="M&A Due Diligence complete. Review final deal memo and recommendation.",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 2. TAX PREPARATION ASSISTANT
# =============================================================================

TAX_PREP_ASSISTANT = WorkflowDefinition(
    id="tax-prep-assistant",
    name="Tax Preparation Assistant",
    description="Automated tax return preparation, deduction optimization, and compliance verification",
    version="1.0.0",
    tags=["finance", "tax", "compliance"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a tax preparation workflow.
Your goal is to prepare an accurate tax return, maximize deductions, and ensure compliance.
Work with Finance team to gather data and calculate optimal tax strategy.""",

    team_leads=[FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["taxpayer_name", "tax_year", "income_sources", "jurisdiction"],
    final_outputs=["tax_return_draft", "deduction_summary", "tax_liability", "filing_checklist"],

    steps=[
        WorkflowStep(
            id="data-gathering",
            name="Gather Tax Documents",
            description="Collect and organize income, deductions, credits, and supporting documents",
            executor="finance-lead",
            inputs={
                "taxpayer": "inputs.taxpayer_name",
                "income_sources": "inputs.income_sources",
                "year": "inputs.tax_year",
            },
            outputs=["income_summary", "deduction_list", "credit_list", "document_inventory"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="deduction-optimization",
            name="Optimize Deductions & Credits",
            description="Identify all eligible deductions and credits, compare itemized vs standard",
            executor="finance-lead",
            inputs={
                "deductions": "data-gathering.deduction_list",
                "credits": "data-gathering.credit_list",
                "jurisdiction": "inputs.jurisdiction",
            },
            outputs=["optimized_deductions", "tax_strategy", "savings_estimate"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review tax strategy and deduction plan. Approve to proceed with calculations?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="tax-calculation",
            name="Calculate Tax Liability",
            description="Compute federal and state tax liability with all deductions applied",
            executor="finance-lead",
            inputs={
                "income": "data-gathering.income_summary",
                "deductions": "deduction-optimization.optimized_deductions",
                "year": "inputs.tax_year",
            },
            outputs=["federal_tax", "state_tax", "total_liability", "refund_or_payment"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="compliance-check",
            name="Compliance Verification",
            description="Verify all requirements, check for audit triggers, ensure documentation",
            executor="legal-lead",
            inputs={
                "return_data": "tax-calculation.total_liability",
                "deductions": "deduction-optimization.optimized_deductions",
                "jurisdiction": "inputs.jurisdiction",
            },
            outputs=["compliance_report", "audit_risk_assessment", "required_attachments"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="return-draft",
            name="Draft Tax Return",
            description="Generate complete tax return with all schedules and supporting documentation",
            executor="content-lead",
            inputs={
                "income": "data-gathering.income_summary",
                "deductions": "deduction-optimization.optimized_deductions",
                "liability": "tax-calculation.total_liability",
                "compliance": "compliance-check.compliance_report",
            },
            outputs=["tax_return_draft", "filing_checklist", "payment_instructions"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Tax return prepared. Review all calculations before filing.",
            required_approval=True,
        )
    ],
)


# =============================================================================
# 3. CONTRACT REVIEW PIPELINE
# =============================================================================

CONTRACT_REVIEW = WorkflowDefinition(
    id="contract-review",
    name="Contract Review Pipeline",
    description="Automated legal contract analysis, risk identification, and redline suggestions",
    version="1.0.0",
    tags=["legal", "contracts", "risk-management"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a contract review workflow.
Your goal is to identify legal risks, unfavorable terms, and provide redline recommendations.
Work with Legal team to perform thorough analysis.""",

    team_leads=[LEGAL_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["contract_type", "counterparty", "contract_text", "our_position"],
    final_outputs=["risk_analysis", "redline_suggestions", "negotiation_points", "review_memo"],

    steps=[
        WorkflowStep(
            id="contract-extraction",
            name="Extract Key Terms",
            description="Extract and categorize all key contractual terms, obligations, and dates",
            executor="legal-lead",
            inputs={
                "contract": "inputs.contract_text",
                "type": "inputs.contract_type",
            },
            outputs=["key_terms", "obligations_matrix", "critical_dates", "payment_terms"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="counterparty-research",
            name="Research Counterparty",
            description="Research counterparty background, litigation history, financial stability",
            executor="research-lead",
            inputs={
                "counterparty": "inputs.counterparty",
            },
            outputs=["counterparty_profile", "litigation_history", "financial_health", "reputation_assessment"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="risk-identification",
            name="Identify Legal Risks",
            description="Analyze contract for unfavorable terms, liability exposure, termination clauses",
            executor="legal-lead",
            inputs={
                "terms": "contract-extraction.key_terms",
                "obligations": "contract-extraction.obligations_matrix",
                "counterparty": "counterparty-research.counterparty_profile",
                "our_position": "inputs.our_position",
            },
            outputs=["risk_register", "liability_analysis", "termination_risks", "indemnity_review"],
            timeout_seconds=180,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review identified risks. Proceed with redline recommendations?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="redline-recommendations",
            name="Generate Redline Suggestions",
            description="Create specific redline suggestions to mitigate identified risks",
            executor="legal-lead",
            inputs={
                "risks": "risk-identification.risk_register",
                "terms": "contract-extraction.key_terms",
            },
            outputs=["redline_suggestions", "negotiation_priorities", "fallback_positions"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="review-memo",
            name="Draft Review Memo",
            description="Create comprehensive contract review memo with recommendations",
            executor="content-lead",
            inputs={
                "risks": "risk-identification.risk_register",
                "redlines": "redline-recommendations.redline_suggestions",
                "counterparty": "counterparty-research.counterparty_profile",
                "contract_type": "inputs.contract_type",
            },
            outputs=["review_memo", "executive_summary", "action_items"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Contract review complete. Approve recommendations before negotiation?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 4. AUDIT PREPARATION
# =============================================================================

AUDIT_PREPARATION = WorkflowDefinition(
    id="audit-preparation",
    name="Audit Preparation Workflow",
    description="Prepare for financial audit - document gathering, reconciliation, control testing",
    version="1.0.0",
    tags=["finance", "audit", "compliance"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an audit preparation workflow.
Your goal is to ensure the company is fully prepared for the upcoming audit.
Work with Finance and Legal teams to gather documentation and test controls.""",

    team_leads=[FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["audit_type", "audit_period", "auditor_firm", "prior_year_issues"],
    final_outputs=["audit_readiness_report", "document_package", "control_testing_results", "issue_remediation"],

    steps=[
        WorkflowStep(
            id="scope-planning",
            name="Define Audit Scope",
            description="Determine audit scope, key areas, materiality thresholds, timeline",
            executor="finance-lead",
            inputs={
                "audit_type": "inputs.audit_type",
                "period": "inputs.audit_period",
                "prior_issues": "inputs.prior_year_issues",
            },
            outputs=["audit_scope", "key_areas", "materiality_thresholds", "preparation_timeline"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="document-gathering",
            name="Gather Audit Documentation",
            description="Collect all required financial records, supporting documentation, reconciliations",
            executor="finance-lead",
            inputs={
                "scope": "scope-planning.audit_scope",
                "key_areas": "scope-planning.key_areas",
                "period": "inputs.audit_period",
            },
            outputs=["financial_statements", "general_ledger", "reconciliations", "supporting_docs"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="control-testing",
            name="Test Internal Controls",
            description="Test and document internal controls, identify control deficiencies",
            executor="finance-lead",
            inputs={
                "scope": "scope-planning.audit_scope",
                "period": "inputs.audit_period",
            },
            outputs=["control_test_results", "deficiencies", "remediation_plan"],
            timeout_seconds=180,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review control testing results and deficiencies. Approve remediation plan?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="compliance-review",
            name="Regulatory Compliance Review",
            description="Verify compliance with accounting standards, regulations, and policies",
            executor="legal-lead",
            inputs={
                "financial_statements": "document-gathering.financial_statements",
                "audit_type": "inputs.audit_type",
            },
            outputs=["compliance_assessment", "standards_checklist", "policy_adherence"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="pbc-list",
            name="Prepare PBC List",
            description="Create comprehensive Provided by Client (PBC) list with all documents",
            executor="content-lead",
            inputs={
                "scope": "scope-planning.audit_scope",
                "documents": "document-gathering.supporting_docs",
                "controls": "control-testing.control_test_results",
                "compliance": "compliance-review.compliance_assessment",
            },
            outputs=["pbc_list", "document_index", "audit_readiness_report"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="issue-remediation",
            name="Remediate Prior Issues",
            description="Address all prior year audit findings and implement corrective actions",
            executor="orchestrator",
            inputs={
                "prior_issues": "inputs.prior_year_issues",
                "deficiencies": "control-testing.deficiencies",
                "compliance": "compliance-review.compliance_assessment",
            },
            outputs=["remediation_status", "corrective_actions", "evidence_of_correction"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Audit preparation complete. Review readiness report before auditor arrival.",
            required_approval=True,
        )
    ],
)


# Aggregate all finance & legal workflows
ALL_FINANCE_LEGAL_WORKFLOWS = {
    "ma-due-diligence": MA_DUE_DILIGENCE,
    "tax-prep-assistant": TAX_PREP_ASSISTANT,
    "contract-review": CONTRACT_REVIEW,
    "audit-preparation": AUDIT_PREPARATION,
}

__all__ = [
    "MA_DUE_DILIGENCE",
    "TAX_PREP_ASSISTANT",
    "CONTRACT_REVIEW",
    "AUDIT_PREPARATION",
    "ALL_FINANCE_LEGAL_WORKFLOWS",
]
