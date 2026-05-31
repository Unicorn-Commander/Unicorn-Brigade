"""
Pre-defined High-Value Workflow Templates

These workflows demonstrate the 3-tier hierarchy:
Orchestrator → Team Leads → Workers

Each workflow is optimized for:
- Local model execution where possible
- Human checkpoints at critical decision points
- Cost efficiency through tiered model usage
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
    CONTENT_TEAM_LEAD,
    SALES_TEAM_LEAD,
    DEVOPS_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    MEDICAL_TEAM_LEAD,
    INVESTIGATION_TEAM_LEAD,
    CAPTAIN_CAP_TEAM_LEAD,
    CAPTAIN_COURT_TEAM_LEAD,
    CAPTAIN_STACK_TEAM_LEAD,
    CAPTAIN_LAB_TEAM_LEAD,
)

# Import professional workflows (temporarily disabled - checkpoints need fixing)
PROFESSIONAL_WORKFLOWS_AVAILABLE = False
ALL_PROFESSIONAL_WORKFLOWS = {}
# try:
#     from app.workflows.professional import ALL_PROFESSIONAL_WORKFLOWS
#     PROFESSIONAL_WORKFLOWS_AVAILABLE = True
# except ImportError:
#     ALL_PROFESSIONAL_WORKFLOWS = {}
#     PROFESSIONAL_WORKFLOWS_AVAILABLE = False


# =============================================================================
# 1. INVESTMENT DUE DILIGENCE PIPELINE
# =============================================================================

INVESTMENT_DUE_DILIGENCE = WorkflowDefinition(
    id="investment-due-diligence",
    name="Investment Due Diligence",
    description="Comprehensive investment research combining market analysis, financial modeling, and risk assessment",
    version="1.0.0",
    tags=["finance", "research", "investment"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an investment due diligence workflow.
Your goal is to produce a comprehensive investment analysis with actionable recommendations.
Coordinate between Research and Finance teams to gather all necessary data.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["company_name", "investment_thesis", "investment_amount"],
    final_outputs=["research_report", "financial_analysis", "investment_memo", "recommendation"],

    steps=[
        WorkflowStep(
            id="market-research",
            name="Market Research",
            description="Research the company, market, competitors, and recent news",
            executor="research-lead",
            inputs={"topic": "inputs.company_name", "context": "inputs.investment_thesis"},
            outputs=["company_profile", "market_analysis", "competitor_analysis", "news_summary"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="financial-analysis",
            name="Financial Analysis",
            description="Analyze financial statements, calculate key ratios, assess financial health",
            executor="finance-lead",
            inputs={
                "company": "market-research.company_profile",
                "market_data": "market-research.market_analysis",
            },
            outputs=["financial_ratios", "trend_analysis", "risk_assessment", "valuation"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="investment-memo",
            name="Draft Investment Memo",
            description="Create professional investment memo synthesizing all findings",
            executor="content-lead",
            inputs={
                "research": "market-research.company_profile",
                "financials": "financial-analysis.financial_ratios",
                "risks": "financial-analysis.risk_assessment",
                "thesis": "inputs.investment_thesis",
            },
            outputs=["investment_memo", "executive_summary"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="final-recommendation",
            name="Final Recommendation",
            description="Synthesize all findings into a final investment recommendation",
            executor="orchestrator",
            inputs={
                "memo": "investment-memo.investment_memo",
                "valuation": "financial-analysis.valuation",
                "amount": "inputs.investment_amount",
            },
            outputs=["recommendation", "confidence_score", "key_risks", "next_steps"],
            timeout_seconds=60,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-research",
            name="Review Research Findings",
            type=CheckpointType.REVIEW,
            after_step="market-research",
            prompt="Review the market research findings before proceeding to financial analysis",
        ),
        Checkpoint(
            id="approve-recommendation",
            name="Approve Final Recommendation",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="final-recommendation",
            prompt="Review and approve the final investment recommendation",
            options=["Approve", "Reject", "Request Changes"],
        ),
    ],
)


# =============================================================================
# 2. AUTONOMOUS SALES PIPELINE
# =============================================================================

AUTONOMOUS_SALES_PIPELINE = WorkflowDefinition(
    id="autonomous-sales-pipeline",
    name="Autonomous Sales Pipeline",
    description="End-to-end sales workflow from lead research to meeting scheduling",
    version="1.0.0",
    tags=["sales", "research", "outreach"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an autonomous sales pipeline.
Your goal is to research prospects, qualify leads, and generate personalized outreach.""",

    team_leads=[RESEARCH_TEAM_LEAD, SALES_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["prospect_company", "product_context", "ideal_customer_profile"],
    final_outputs=["lead_qualification", "personalized_emails", "meeting_prep", "objection_responses"],

    steps=[
        WorkflowStep(
            id="prospect-research",
            name="Prospect Research",
            description="Research the prospect company, key contacts, and recent activity",
            executor="research-lead",
            inputs={"topic": "inputs.prospect_company"},
            outputs=["company_profile", "key_contacts", "recent_news", "pain_points"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="lead-qualification",
            name="Lead Qualification",
            description="Qualify the lead against ideal customer profile",
            executor="sales-lead",
            inputs={
                "prospect": "prospect-research.company_profile",
                "icp": "inputs.ideal_customer_profile",
            },
            outputs=["qualification_score", "qualification_reasoning", "recommended_approach"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="email-generation",
            name="Generate Outreach Emails",
            description="Create personalized outreach email sequence",
            executor="sales-lead",
            inputs={
                "prospect": "prospect-research.company_profile",
                "contacts": "prospect-research.key_contacts",
                "pain_points": "prospect-research.pain_points",
                "product": "inputs.product_context",
            },
            outputs=["initial_email", "follow_up_1", "follow_up_2", "break_up_email"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="objection-prep",
            name="Prepare Objection Handling",
            description="Prepare responses to likely objections",
            executor="sales-lead",
            inputs={
                "prospect": "prospect-research.company_profile",
                "product": "inputs.product_context",
            },
            outputs=["likely_objections", "objection_responses"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="meeting-prep",
            name="Meeting Preparation",
            description="Prepare briefing for sales meeting",
            executor="sales-lead",
            inputs={
                "prospect": "prospect-research.company_profile",
                "qualification": "lead-qualification.qualification_reasoning",
                "objections": "objection-prep.likely_objections",
            },
            outputs=["meeting_briefing", "talking_points", "questions_to_ask"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-qualification",
            name="Review Lead Qualification",
            type=CheckpointType.GATE,
            after_step="lead-qualification",
            gate_condition="lead-qualification.qualification_score >= 60",
            failure_action="skip",
            prompt="Lead does not meet minimum qualification threshold",
        ),
        Checkpoint(
            id="approve-emails",
            name="Approve Outreach Emails",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="email-generation",
            prompt="Review and approve the personalized email sequence before sending",
            options=["Approve", "Edit", "Reject"],
        ),
    ],
)


# =============================================================================
# 3. INCIDENT RESPONSE & RESOLUTION
# =============================================================================

INCIDENT_RESPONSE = WorkflowDefinition(
    id="incident-response",
    name="Incident Response & Resolution",
    description="Automated incident detection, diagnosis, and resolution workflow",
    version="1.0.0",
    tags=["devops", "incident", "monitoring"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an incident response workflow.
Your goal is to quickly diagnose the issue, execute remediation, and document for postmortem.""",

    team_leads=[DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["incident_description", "affected_services", "severity", "logs"],
    final_outputs=["root_cause", "resolution_steps", "incident_summary", "postmortem"],

    steps=[
        WorkflowStep(
            id="log-analysis",
            name="Log Analysis",
            description="Parse logs and identify error patterns",
            executor="devops-lead",
            inputs={
                "logs": "inputs.logs",
                "services": "inputs.affected_services",
            },
            outputs=["error_patterns", "anomalies", "timeline"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="root-cause-analysis",
            name="Root Cause Analysis",
            description="Research potential causes and identify root cause",
            executor="research-lead",
            inputs={
                "errors": "log-analysis.error_patterns",
                "anomalies": "log-analysis.anomalies",
                "services": "inputs.affected_services",
            },
            outputs=["root_cause_hypothesis", "supporting_evidence", "related_issues"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="resolution-plan",
            name="Resolution Planning",
            description="Determine resolution steps based on runbook or research",
            executor="devops-lead",
            inputs={
                "root_cause": "root-cause-analysis.root_cause_hypothesis",
                "severity": "inputs.severity",
            },
            outputs=["resolution_steps", "rollback_plan", "verification_steps"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="incident-summary",
            name="Create Incident Summary",
            description="Summarize incident for stakeholders",
            executor="devops-lead",
            inputs={
                "timeline": "log-analysis.timeline",
                "root_cause": "root-cause-analysis.root_cause_hypothesis",
                "resolution": "resolution-plan.resolution_steps",
            },
            outputs=["incident_summary", "status_update"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="postmortem",
            name="Draft Postmortem",
            description="Create detailed postmortem document",
            executor="content-lead",
            inputs={
                "summary": "incident-summary.incident_summary",
                "timeline": "log-analysis.timeline",
                "root_cause": "root-cause-analysis.root_cause_hypothesis",
                "resolution": "resolution-plan.resolution_steps",
            },
            outputs=["postmortem_document", "action_items", "prevention_measures"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-resolution",
            name="Approve Resolution Plan",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="resolution-plan",
            prompt="Review and approve the resolution plan before execution",
            options=["Approve", "Modify", "Escalate"],
        ),
    ],
)


# =============================================================================
# 4. CONTENT PRODUCTION FACTORY
# =============================================================================

CONTENT_PRODUCTION = WorkflowDefinition(
    id="content-production",
    name="Content Production Factory",
    description="End-to-end content creation from research to multi-platform publishing",
    version="1.0.0",
    tags=["content", "marketing", "seo"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a content production workflow.
Your goal is to create high-quality, SEO-optimized content across multiple platforms.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["topic", "target_keywords", "target_audience", "content_goals"],
    final_outputs=["blog_post", "social_posts", "seo_metadata", "content_calendar_entry"],

    steps=[
        WorkflowStep(
            id="topic-research",
            name="Topic Research",
            description="Research the topic, gather facts, and identify key angles",
            executor="research-lead",
            inputs={
                "topic": "inputs.topic",
                "keywords": "inputs.target_keywords",
            },
            outputs=["topic_research", "key_facts", "unique_angles", "sources"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="content-outline",
            name="Create Content Outline",
            description="Structure the content with headings, key points, and flow",
            executor="content-lead",
            inputs={
                "research": "topic-research.topic_research",
                "angles": "topic-research.unique_angles",
                "audience": "inputs.target_audience",
            },
            outputs=["outline", "headline_options", "key_messages"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="draft-content",
            name="Draft Blog Post",
            description="Write the full blog post based on outline",
            executor="content-lead",
            inputs={
                "outline": "content-outline.outline",
                "research": "topic-research.key_facts",
                "sources": "topic-research.sources",
                "keywords": "inputs.target_keywords",
            },
            outputs=["blog_draft", "word_count"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="seo-optimization",
            name="SEO Optimization",
            description="Optimize content for search engines",
            executor="content-lead",
            inputs={
                "content": "draft-content.blog_draft",
                "keywords": "inputs.target_keywords",
            },
            outputs=["optimized_content", "seo_metadata", "seo_score"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="social-adaptation",
            name="Create Social Posts",
            description="Adapt content for social media platforms",
            executor="content-lead",
            inputs={
                "content": "seo-optimization.optimized_content",
                "headlines": "content-outline.headline_options",
            },
            outputs=["twitter_posts", "linkedin_post", "instagram_caption"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-outline",
            name="Approve Content Outline",
            type=CheckpointType.HUMAN_INPUT,
            after_step="content-outline",
            prompt="Select the headline and review the outline",
            options=["Approve Outline", "Modify Outline", "Change Direction"],
        ),
        Checkpoint(
            id="final-review",
            name="Final Content Review",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="seo-optimization",
            prompt="Review the final optimized content before publishing",
            options=["Approve", "Request Edits", "Reject"],
        ),
    ],
)


# =============================================================================
# 5. LEGAL CASE ANALYSIS
# =============================================================================

LEGAL_CASE_ANALYSIS = WorkflowDefinition(
    id="legal-case-analysis",
    name="Legal Case Analysis",
    description="Comprehensive legal case analysis with theory development and document drafting",
    version="1.0.0",
    tags=["legal", "analysis", "documents"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a legal case analysis workflow.
Your goal is to analyze the case, develop legal theories, and prepare necessary documents.""",

    team_leads=[LEGAL_TEAM_LEAD, RESEARCH_TEAM_LEAD, INVESTIGATION_TEAM_LEAD],

    required_inputs=["case_facts", "jurisdiction", "case_type", "client_goals"],
    final_outputs=["case_analysis", "legal_theories", "settlement_estimate", "recommended_actions", "draft_documents"],

    steps=[
        WorkflowStep(
            id="fact-investigation",
            name="Fact Investigation",
            description="Organize and analyze case facts, build timeline, map entities",
            executor="investigation-lead",
            inputs={
                "facts": "inputs.case_facts",
            },
            outputs=["organized_facts", "timeline", "entity_map", "fact_gaps"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="legal-research",
            name="Legal Research",
            description="Research applicable law, precedents, and statutes",
            executor="legal-lead",
            inputs={
                "facts": "fact-investigation.organized_facts",
                "jurisdiction": "inputs.jurisdiction",
                "case_type": "inputs.case_type",
            },
            outputs=["applicable_law", "precedents", "legal_theories"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="case-strength",
            name="Assess Case Strength",
            description="Analyze strengths, weaknesses, and potential defenses",
            executor="legal-lead",
            inputs={
                "facts": "fact-investigation.organized_facts",
                "theories": "legal-research.legal_theories",
                "precedents": "legal-research.precedents",
            },
            outputs=["case_strength", "weaknesses", "potential_defenses", "recommendations"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="damages-calculation",
            name="Calculate Damages",
            description="Calculate potential damages and settlement range",
            executor="legal-lead",
            inputs={
                "facts": "fact-investigation.organized_facts",
                "case_strength": "case-strength.case_strength",
                "jurisdiction": "inputs.jurisdiction",
            },
            outputs=["damages_estimate", "settlement_range", "calculation_basis"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="strategy-memo",
            name="Draft Strategy Memo",
            description="Prepare comprehensive case strategy memorandum",
            executor="legal-lead",
            inputs={
                "facts": "fact-investigation.organized_facts",
                "theories": "legal-research.legal_theories",
                "strength": "case-strength.case_strength",
                "damages": "damages-calculation.settlement_range",
                "goals": "inputs.client_goals",
            },
            outputs=["strategy_memo", "recommended_actions", "timeline_to_resolution"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-theories",
            name="Review Legal Theories",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="legal-research",
            prompt="Review and approve the identified legal theories before proceeding",
            options=["Approve", "Add Theory", "Remove Theory", "Modify"],
        ),
        Checkpoint(
            id="approve-strategy",
            name="Approve Case Strategy",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="strategy-memo",
            prompt="Review and approve the recommended case strategy",
            options=["Approve", "Request Changes", "Schedule Discussion"],
        ),
    ],
)


# =============================================================================
# 6. MEDICAL DOCUMENTATION REVIEW
# =============================================================================

MEDICAL_DOCUMENTATION_REVIEW = WorkflowDefinition(
    id="medical-documentation-review",
    name="Medical Documentation Review",
    description="Review and process medical documentation for compliance and completeness",
    version="1.0.0",
    tags=["medical", "compliance", "documentation"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a medical documentation review workflow.
Your goal is to ensure documentation is complete, compliant, and properly coded.
IMPORTANT: This is for documentation review only, not clinical decision-making.""",

    team_leads=[MEDICAL_TEAM_LEAD, RESEARCH_TEAM_LEAD],

    required_inputs=["clinical_notes", "document_type", "intended_use"],
    final_outputs=["documentation_review", "compliance_status", "suggested_codes", "summary"],

    steps=[
        WorkflowStep(
            id="extract-clinical-info",
            name="Extract Clinical Information",
            description="Extract symptoms, diagnoses, medications, and other clinical data",
            executor="medical-lead",
            inputs={
                "notes": "inputs.clinical_notes",
            },
            outputs=["extracted_symptoms", "diagnoses", "medications", "procedures"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="check-drug-interactions",
            name="Check Drug Interactions",
            description="Check for potential drug interactions in medication list",
            executor="medical-lead",
            inputs={
                "medications": "extract-clinical-info.medications",
            },
            outputs=["interaction_report", "warnings", "recommendations"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="suggest-codes",
            name="Suggest ICD Codes",
            description="Suggest appropriate ICD-10 codes for documented conditions",
            executor="medical-lead",
            inputs={
                "diagnoses": "extract-clinical-info.diagnoses",
                "notes": "inputs.clinical_notes",
            },
            outputs=["suggested_codes", "code_rationale", "documentation_gaps"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="compliance-review",
            name="HIPAA Compliance Review",
            description="Review documentation for HIPAA compliance issues",
            executor="medical-lead",
            inputs={
                "notes": "inputs.clinical_notes",
                "document_type": "inputs.document_type",
                "intended_use": "inputs.intended_use",
            },
            outputs=["compliance_status", "phi_identified", "redactions_needed", "recommendations"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="create-summary",
            name="Create Clinical Summary",
            description="Create appropriate clinical summary based on intended use",
            executor="medical-lead",
            inputs={
                "clinical_info": "extract-clinical-info",
                "codes": "suggest-codes.suggested_codes",
                "document_type": "inputs.document_type",
                "intended_use": "inputs.intended_use",
            },
            outputs=["clinical_summary", "key_findings", "follow_up_items"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="provider-review",
            name="Provider Review Required",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="suggest-codes",
            prompt="Suggested codes require provider review and approval",
            options=["Approve Codes", "Modify Codes", "Request Documentation"],
        ),
        Checkpoint(
            id="compliance-approval",
            name="Compliance Approval",
            type=CheckpointType.GATE,
            after_step="compliance-review",
            gate_condition="compliance-review.compliance_status == 'compliant'",
            failure_action="abort",
            prompt="Documentation has compliance issues that must be resolved",
        ),
    ],
)


# =============================================================================
# 7. COMPETITIVE INTELLIGENCE WORKFLOW
# =============================================================================

COMPETITIVE_INTELLIGENCE = WorkflowDefinition(
    id="competitive-intel",
    name="Competitive Intelligence",
    description="Analyze competitors, compare financials, and generate strategic recommendations",
    version="1.0.0",
    tags=["research", "strategy", "analysis"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a competitive intelligence workflow.
Your goal is to analyze competitors, understand their strengths and weaknesses,
compare financial positions, and provide strategic recommendations for market positioning.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["company_name", "competitors", "industry"],
    final_outputs=["competitor_analysis", "market_position", "recommendations"],

    steps=[
        WorkflowStep(
            id="competitor-research",
            name="Competitor Research",
            description="Research each competitor's products, market position, and recent activity",
            executor="research-lead",
            inputs={
                "topic": "inputs.company_name",
                "competitors": "inputs.competitors",
                "industry": "inputs.industry",
            },
            outputs=["competitor_profiles", "product_comparisons", "market_trends", "news_summary"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="financial-comparison",
            name="Financial Comparison",
            description="Compare financial metrics across competitors",
            executor="finance-lead",
            inputs={
                "competitors": "competitor-research.competitor_profiles",
                "industry": "inputs.industry",
            },
            outputs=["financial_metrics", "growth_comparison", "profitability_analysis", "valuation_comparison"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="swot-analysis",
            name="SWOT Analysis",
            description="Generate SWOT analysis for each competitor relative to the company",
            executor="research-lead",
            inputs={
                "company": "inputs.company_name",
                "competitor_profiles": "competitor-research.competitor_profiles",
                "financials": "financial-comparison.financial_metrics",
            },
            outputs=["swot_matrix", "competitive_advantages", "vulnerabilities"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="market-position-assessment",
            name="Market Position Assessment",
            description="Assess relative market positions and competitive dynamics",
            executor="finance-lead",
            inputs={
                "swot": "swot-analysis.swot_matrix",
                "financials": "financial-comparison.financial_metrics",
                "trends": "competitor-research.market_trends",
            },
            outputs=["market_position", "market_share_estimate", "competitive_intensity"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="strategic-report",
            name="Generate Strategic Report",
            description="Create comprehensive competitive intelligence report with recommendations",
            executor="content-lead",
            inputs={
                "company": "inputs.company_name",
                "competitor_profiles": "competitor-research.competitor_profiles",
                "financials": "financial-comparison.financial_metrics",
                "swot": "swot-analysis.swot_matrix",
                "market_position": "market-position-assessment.market_position",
            },
            outputs=["competitor_analysis", "recommendations", "executive_summary"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-competitor-data",
            name="Review Competitor Data",
            type=CheckpointType.REVIEW,
            after_step="competitor-research",
            prompt="Review the competitor research before proceeding to financial analysis",
        ),
        Checkpoint(
            id="approve-recommendations",
            name="Approve Strategic Recommendations",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="strategic-report",
            prompt="Review and approve the strategic recommendations",
            options=["Approve", "Request Changes", "Add Competitors"],
        ),
    ],
)


# =============================================================================
# 8. CUSTOMER SUPPORT ESCALATION WORKFLOW
# =============================================================================

CUSTOMER_SUPPORT_ESCALATION = WorkflowDefinition(
    id="support-escalation",
    name="Customer Support Escalation",
    description="Analyze escalated customer issues, find solutions from similar cases, and draft professional responses",
    version="1.0.0",
    tags=["support", "customer", "escalation"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a customer support escalation workflow.
Your goal is to analyze the customer issue, identify root causes, find similar cases and solutions,
and draft a professional response that resolves the customer's concern.""",

    team_leads=[INVESTIGATION_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["ticket_id", "customer_issue", "priority"],
    final_outputs=["root_cause", "resolution", "response_draft"],

    steps=[
        WorkflowStep(
            id="issue-analysis",
            name="Analyze Customer Issue",
            description="Investigate the customer issue to understand the problem and context",
            executor="investigation-lead",
            inputs={
                "issue": "inputs.customer_issue",
                "ticket_id": "inputs.ticket_id",
            },
            outputs=["issue_summary", "affected_components", "timeline", "customer_sentiment"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="root-cause-investigation",
            name="Root Cause Investigation",
            description="Identify the root cause of the customer issue",
            executor="investigation-lead",
            inputs={
                "issue_summary": "issue-analysis.issue_summary",
                "affected_components": "issue-analysis.affected_components",
            },
            outputs=["root_cause", "contributing_factors", "evidence"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="similar-case-search",
            name="Search Similar Cases",
            description="Find similar cases and their resolutions",
            executor="research-lead",
            inputs={
                "issue": "issue-analysis.issue_summary",
                "root_cause": "root-cause-investigation.root_cause",
            },
            outputs=["similar_cases", "successful_resolutions", "knowledge_base_articles"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="resolution-development",
            name="Develop Resolution",
            description="Develop a resolution based on root cause and similar cases",
            executor="research-lead",
            inputs={
                "root_cause": "root-cause-investigation.root_cause",
                "similar_cases": "similar-case-search.similar_cases",
                "resolutions": "similar-case-search.successful_resolutions",
                "priority": "inputs.priority",
            },
            outputs=["resolution", "resolution_steps", "preventive_measures"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="response-drafting",
            name="Draft Customer Response",
            description="Draft a professional, empathetic response to the customer",
            executor="content-lead",
            inputs={
                "issue": "issue-analysis.issue_summary",
                "sentiment": "issue-analysis.customer_sentiment",
                "root_cause": "root-cause-investigation.root_cause",
                "resolution": "resolution-development.resolution",
                "priority": "inputs.priority",
            },
            outputs=["response_draft", "internal_notes", "follow_up_actions"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-response",
            name="Approve Customer Response",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="response-drafting",
            prompt="Review and approve the customer response before sending",
            options=["Approve", "Edit", "Escalate Further"],
        ),
    ],
)


# =============================================================================
# 9. TECHNICAL DOCUMENTATION WORKFLOW
# =============================================================================

TECHNICAL_DOCUMENTATION = WorkflowDefinition(
    id="tech-docs",
    name="Technical Documentation",
    description="Analyze codebase or API and generate comprehensive technical documentation",
    version="1.0.0",
    tags=["documentation", "technical", "content"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a technical documentation workflow.
Your goal is to analyze the codebase or API, understand its structure and functionality,
and generate clear, comprehensive documentation with examples.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["project_name", "doc_type", "source_code_path"],
    final_outputs=["documentation", "examples", "api_reference"],

    steps=[
        WorkflowStep(
            id="codebase-analysis",
            name="Analyze Codebase/API",
            description="Analyze the codebase structure, API endpoints, and functionality",
            executor="research-lead",
            inputs={
                "project": "inputs.project_name",
                "source_path": "inputs.source_code_path",
                "doc_type": "inputs.doc_type",
            },
            outputs=["structure_analysis", "components", "api_endpoints", "dependencies"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="functionality-mapping",
            name="Map Functionality",
            description="Map out the functionality and data flows",
            executor="research-lead",
            inputs={
                "structure": "codebase-analysis.structure_analysis",
                "components": "codebase-analysis.components",
                "endpoints": "codebase-analysis.api_endpoints",
            },
            outputs=["functionality_map", "data_flows", "integration_points"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="documentation-drafting",
            name="Draft Documentation",
            description="Write comprehensive documentation based on analysis",
            executor="content-lead",
            inputs={
                "project": "inputs.project_name",
                "doc_type": "inputs.doc_type",
                "structure": "codebase-analysis.structure_analysis",
                "functionality": "functionality-mapping.functionality_map",
                "endpoints": "codebase-analysis.api_endpoints",
            },
            outputs=["documentation_draft", "table_of_contents", "getting_started"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="example-generation",
            name="Generate Examples",
            description="Create code examples and usage samples",
            executor="content-lead",
            inputs={
                "endpoints": "codebase-analysis.api_endpoints",
                "functionality": "functionality-mapping.functionality_map",
                "doc_type": "inputs.doc_type",
            },
            outputs=["examples", "code_snippets", "use_cases"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="api-reference-generation",
            name="Generate API Reference",
            description="Create detailed API reference documentation",
            executor="content-lead",
            inputs={
                "endpoints": "codebase-analysis.api_endpoints",
                "data_flows": "functionality-mapping.data_flows",
                "examples": "example-generation.examples",
            },
            outputs=["api_reference", "parameter_docs", "response_schemas"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="documentation-finalization",
            name="Finalize Documentation",
            description="Compile and polish final documentation",
            executor="content-lead",
            inputs={
                "documentation": "documentation-drafting.documentation_draft",
                "examples": "example-generation.examples",
                "api_reference": "api-reference-generation.api_reference",
                "toc": "documentation-drafting.table_of_contents",
            },
            outputs=["documentation", "changelog", "version_notes"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-structure",
            name="Review Documentation Structure",
            type=CheckpointType.HUMAN_INPUT,
            after_step="documentation-drafting",
            prompt="Review the documentation structure and table of contents",
            options=["Approve Structure", "Add Sections", "Reorganize"],
        ),
        Checkpoint(
            id="approve-documentation",
            name="Approve Final Documentation",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="documentation-finalization",
            prompt="Review and approve the final documentation before publishing",
            options=["Approve", "Request Edits", "Add Examples"],
        ),
    ],
)


# =============================================================================
# 10. RISK ASSESSMENT WORKFLOW
# =============================================================================

RISK_ASSESSMENT = WorkflowDefinition(
    id="risk-assessment",
    name="Risk Assessment",
    description="Identify project risks, quantify financial impact, review compliance, and generate comprehensive risk report",
    version="1.0.0",
    tags=["risk", "compliance", "finance"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a comprehensive risk assessment workflow.
Your goal is to identify all potential risks, quantify their financial impact,
ensure regulatory compliance, and produce a detailed risk report with mitigation strategies.""",

    team_leads=[INVESTIGATION_TEAM_LEAD, FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["project_name", "assessment_scope", "risk_categories"],
    final_outputs=["risk_matrix", "mitigation_plan", "compliance_status"],

    steps=[
        WorkflowStep(
            id="risk-identification",
            name="Identify Risks",
            description="Identify and catalog all potential risks within the assessment scope",
            executor="investigation-lead",
            inputs={
                "project": "inputs.project_name",
                "scope": "inputs.assessment_scope",
                "categories": "inputs.risk_categories",
            },
            outputs=["identified_risks", "risk_categories", "risk_sources", "initial_severity"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="risk-analysis",
            name="Analyze Risk Factors",
            description="Analyze risk factors, likelihood, and potential triggers",
            executor="investigation-lead",
            inputs={
                "risks": "risk-identification.identified_risks",
                "severity": "risk-identification.initial_severity",
            },
            outputs=["risk_analysis", "likelihood_assessment", "impact_scenarios", "risk_triggers"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="financial-impact",
            name="Quantify Financial Impact",
            description="Calculate potential financial impact for each risk",
            executor="finance-lead",
            inputs={
                "risks": "risk-identification.identified_risks",
                "analysis": "risk-analysis.risk_analysis",
                "scenarios": "risk-analysis.impact_scenarios",
            },
            outputs=["financial_impact", "cost_estimates", "exposure_analysis", "reserve_recommendations"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="compliance-review",
            name="Compliance Review",
            description="Review risks against regulatory and compliance requirements",
            executor="legal-lead",
            inputs={
                "risks": "risk-identification.identified_risks",
                "scope": "inputs.assessment_scope",
            },
            outputs=["compliance_status", "regulatory_risks", "required_controls", "compliance_gaps"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="mitigation-planning",
            name="Develop Mitigation Strategies",
            description="Develop mitigation strategies for identified risks",
            executor="investigation-lead",
            inputs={
                "risks": "risk-analysis.risk_analysis",
                "financial_impact": "financial-impact.financial_impact",
                "compliance": "compliance-review.compliance_status",
            },
            outputs=["mitigation_strategies", "control_recommendations", "residual_risk"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="risk-matrix-generation",
            name="Generate Risk Matrix",
            description="Create comprehensive risk matrix with all assessments",
            executor="finance-lead",
            inputs={
                "risks": "risk-analysis.risk_analysis",
                "likelihood": "risk-analysis.likelihood_assessment",
                "financial_impact": "financial-impact.financial_impact",
                "mitigation": "mitigation-planning.mitigation_strategies",
            },
            outputs=["risk_matrix", "risk_rankings", "priority_list"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="risk-report-generation",
            name="Generate Risk Report",
            description="Create comprehensive risk assessment report",
            executor="content-lead",
            inputs={
                "project": "inputs.project_name",
                "risk_matrix": "risk-matrix-generation.risk_matrix",
                "financial_impact": "financial-impact.financial_impact",
                "compliance_status": "compliance-review.compliance_status",
                "mitigation_plan": "mitigation-planning.mitigation_strategies",
            },
            outputs=["risk_report", "executive_summary", "action_items"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-identified-risks",
            name="Review Identified Risks",
            type=CheckpointType.HUMAN_INPUT,
            after_step="risk-identification",
            prompt="Review identified risks and add any known risks not detected",
            options=["Approve", "Add Risks", "Modify Categories"],
        ),
        Checkpoint(
            id="review-compliance",
            name="Review Compliance Status",
            type=CheckpointType.GATE,
            after_step="compliance-review",
            gate_condition="compliance-review.compliance_gaps == []",
            failure_action="continue",
            prompt="Compliance gaps detected - review required before proceeding",
        ),
        Checkpoint(
            id="approve-risk-report",
            name="Approve Risk Report",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="risk-report-generation",
            prompt="Review and approve the final risk assessment report",
            options=["Approve", "Request Changes", "Schedule Review Meeting"],
        ),
    ],
)


# =============================================================================
# 11. CODE REVIEW PIPELINE
# =============================================================================

CODE_REVIEW_PIPELINE = WorkflowDefinition(
    id="code-review-pipeline",
    name="Code Review Pipeline",
    description="Comprehensive code review with static analysis, security scanning, and actionable feedback",
    version="1.0.0",
    tags=["code", "review", "security", "devops"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a code review workflow.
Your goal is to produce a comprehensive, actionable code review that improves code quality and security.
Coordinate between Research (for documentation/best practices), DevOps (for analysis), and Content (for report generation).""",

    team_leads=[RESEARCH_TEAM_LEAD, DEVOPS_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["code_diff", "repository_name", "pr_title", "pr_description", "language"],
    final_outputs=["review_report", "security_findings", "improvement_suggestions", "approval_recommendation"],

    steps=[
        WorkflowStep(
            id="parse-diff",
            name="Parse PR/Diff",
            description="Parse the code diff to identify changed files, functions, and scope of changes",
            executor="devops-lead",
            inputs={
                "diff": "inputs.code_diff",
                "language": "inputs.language",
            },
            outputs=["parsed_changes", "files_modified", "functions_changed", "lines_added", "lines_removed"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="static-analysis",
            name="Static Analysis",
            description="Perform static code analysis to identify code quality issues, complexity, and maintainability concerns",
            executor="devops-lead",
            inputs={
                "changes": "parse-diff.parsed_changes",
                "language": "inputs.language",
            },
            outputs=["code_quality_issues", "complexity_metrics", "maintainability_score", "code_smells"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="security-scan",
            name="Security Scan",
            description="Scan for security vulnerabilities, injection risks, and unsafe patterns",
            executor="devops-lead",
            inputs={
                "changes": "parse-diff.parsed_changes",
                "language": "inputs.language",
            },
            outputs=["security_vulnerabilities", "risk_level", "cve_references", "remediation_suggestions"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="best-practices-check",
            name="Best Practices Check",
            description="Research language-specific best practices and compare against the code changes",
            executor="research-lead",
            inputs={
                "language": "inputs.language",
                "code_issues": "static-analysis.code_quality_issues",
                "functions": "parse-diff.functions_changed",
            },
            outputs=["best_practice_violations", "documentation_gaps", "naming_convention_issues", "recommended_patterns"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-review-report",
            name="Generate Review Report",
            description="Compile all findings into a structured, actionable code review report",
            executor="content-lead",
            inputs={
                "pr_title": "inputs.pr_title",
                "pr_description": "inputs.pr_description",
                "parsed_changes": "parse-diff.parsed_changes",
                "quality_issues": "static-analysis.code_quality_issues",
                "security_findings": "security-scan.security_vulnerabilities",
                "best_practices": "best-practices-check.best_practice_violations",
            },
            outputs=["review_report", "inline_comments", "summary", "improvement_suggestions"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="approval-decision",
            name="Approval Decision",
            description="Make final approval recommendation based on all findings",
            executor="orchestrator",
            inputs={
                "security_risk": "security-scan.risk_level",
                "quality_score": "static-analysis.maintainability_score",
                "review_summary": "generate-review-report.summary",
            },
            outputs=["approval_recommendation", "blocking_issues", "required_changes", "optional_improvements"],
            timeout_seconds=60,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-security-findings",
            name="Review Security Findings",
            type=CheckpointType.GATE,
            after_step="security-scan",
            gate_condition="security-scan.risk_level != 'critical'",
            failure_action="abort",
            prompt="Critical security vulnerabilities detected - manual review required before proceeding",
        ),
        Checkpoint(
            id="approve-review-before-posting",
            name="Approve Review Before Posting",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="approval-decision",
            prompt="Review the generated code review before posting to the PR",
            options=["Post Review", "Edit Review", "Request Re-analysis", "Reject"],
        ),
    ],
)


# =============================================================================
# 12. CUSTOMER SUPPORT RESOLUTION
# =============================================================================

CUSTOMER_SUPPORT_RESOLUTION = WorkflowDefinition(
    id="customer-support-resolution",
    name="Customer Support Resolution",
    description="Resolve customer tickets with knowledge base integration and automatic knowledge article creation",
    version="1.0.0",
    tags=["support", "customer", "knowledge", "service"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a customer support resolution workflow.
Your goal is to resolve the customer's issue effectively while updating the knowledge base if this is a new issue.
Coordinate between Research (knowledge base), Content (response drafting), and Sales (customer communication).""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD, SALES_TEAM_LEAD],

    required_inputs=["ticket_id", "customer_name", "customer_email", "issue_description", "product_area", "priority"],
    final_outputs=["resolution", "customer_response", "knowledge_article", "follow_up_actions"],

    steps=[
        WorkflowStep(
            id="classify-ticket",
            name="Classify Ticket",
            description="Classify the ticket by type, urgency, and required expertise",
            executor="research-lead",
            inputs={
                "issue": "inputs.issue_description",
                "product": "inputs.product_area",
                "priority": "inputs.priority",
            },
            outputs=["ticket_category", "urgency_level", "sentiment", "keywords", "required_expertise"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="search-knowledge-base",
            name="Search Knowledge Base",
            description="Search existing knowledge base for relevant articles and past resolutions",
            executor="research-lead",
            inputs={
                "keywords": "classify-ticket.keywords",
                "category": "classify-ticket.ticket_category",
                "issue": "inputs.issue_description",
            },
            outputs=["relevant_articles", "similar_tickets", "known_solutions", "confidence_score"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="draft-response",
            name="Draft Customer Response",
            description="Draft a personalized, empathetic response addressing the customer's issue",
            executor="sales-lead",
            inputs={
                "customer_name": "inputs.customer_name",
                "issue": "inputs.issue_description",
                "sentiment": "classify-ticket.sentiment",
                "solutions": "search-knowledge-base.known_solutions",
                "articles": "search-knowledge-base.relevant_articles",
            },
            outputs=["response_draft", "tone_analysis", "personalization_points", "resolution_steps"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="quality-check",
            name="Quality Check Response",
            description="Review response for accuracy, tone, completeness, and brand voice",
            executor="content-lead",
            inputs={
                "response": "draft-response.response_draft",
                "issue": "inputs.issue_description",
                "sentiment": "classify-ticket.sentiment",
            },
            outputs=["quality_score", "improvements_needed", "final_response", "compliance_check"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="update-knowledge-base",
            name="Update Knowledge Base",
            description="Create or update knowledge article if this is a new issue or has new resolution",
            executor="content-lead",
            inputs={
                "issue": "inputs.issue_description",
                "category": "classify-ticket.ticket_category",
                "resolution": "draft-response.resolution_steps",
                "existing_articles": "search-knowledge-base.relevant_articles",
                "confidence": "search-knowledge-base.confidence_score",
            },
            outputs=["knowledge_article", "article_status", "tags", "related_articles"],
            timeout_seconds=120,
            condition="search-knowledge-base.confidence_score < 0.8",
        ),
        WorkflowStep(
            id="create-follow-up",
            name="Create Follow-up Actions",
            description="Determine any follow-up actions needed after resolution",
            executor="orchestrator",
            inputs={
                "ticket_id": "inputs.ticket_id",
                "category": "classify-ticket.ticket_category",
                "resolution": "draft-response.resolution_steps",
                "quality_score": "quality-check.quality_score",
            },
            outputs=["follow_up_actions", "escalation_needed", "feedback_request", "satisfaction_survey"],
            timeout_seconds=60,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-response-before-sending",
            name="Review Response Before Sending",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="quality-check",
            prompt="Review the customer response before sending. Check for accuracy and appropriate tone.",
            options=["Send Response", "Edit Response", "Escalate to Human Agent", "Request More Info"],
        ),
        Checkpoint(
            id="review-knowledge-article",
            name="Review Knowledge Article",
            type=CheckpointType.REVIEW,
            after_step="update-knowledge-base",
            prompt="Review the new/updated knowledge article for accuracy before publishing",
        ),
    ],
)


# =============================================================================
# 13. COMPETITIVE INTELLIGENCE REPORT
# =============================================================================

COMPETITIVE_INTELLIGENCE_REPORT = WorkflowDefinition(
    id="competitive-intelligence-report",
    name="Competitive Intelligence Report",
    description="Generate comprehensive competitive analysis with market positioning and SWOT analysis",
    version="1.0.0",
    tags=["research", "competitive", "market", "strategy", "analysis"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a competitive intelligence workflow.
Your goal is to produce a comprehensive, actionable competitive analysis report.
Coordinate between Research (data gathering), Finance (market analysis), and Content (report generation).""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["company_name", "industry", "competitors", "focus_areas", "time_period"],
    final_outputs=["competitive_report", "swot_analysis", "market_position_map", "strategic_recommendations"],

    steps=[
        WorkflowStep(
            id="identify-competitors",
            name="Identify and Profile Competitors",
            description="Identify all relevant competitors and create detailed profiles",
            executor="research-lead",
            inputs={
                "company": "inputs.company_name",
                "industry": "inputs.industry",
                "known_competitors": "inputs.competitors",
            },
            outputs=["competitor_profiles", "market_segments", "competitive_landscape", "emerging_players"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="gather-competitor-data",
            name="Gather Competitor Data",
            description="Collect detailed data on each competitor including pricing, products, and market presence",
            executor="research-lead",
            inputs={
                "competitors": "identify-competitors.competitor_profiles",
                "focus_areas": "inputs.focus_areas",
                "time_period": "inputs.time_period",
            },
            outputs=["product_features", "pricing_data", "market_share_estimates", "recent_news", "customer_reviews"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="analyze-market-positioning",
            name="Analyze Market Positioning",
            description="Analyze how each competitor positions themselves in the market",
            executor="finance-lead",
            inputs={
                "competitor_data": "gather-competitor-data.product_features",
                "pricing": "gather-competitor-data.pricing_data",
                "market_share": "gather-competitor-data.market_share_estimates",
                "industry": "inputs.industry",
            },
            outputs=["positioning_analysis", "value_proposition_comparison", "price_performance_matrix", "market_gaps"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="swot-analysis",
            name="SWOT Analysis",
            description="Generate SWOT analysis for the company relative to competitors",
            executor="finance-lead",
            inputs={
                "company": "inputs.company_name",
                "competitor_profiles": "identify-competitors.competitor_profiles",
                "positioning": "analyze-market-positioning.positioning_analysis",
                "market_gaps": "analyze-market-positioning.market_gaps",
            },
            outputs=["strengths", "weaknesses", "opportunities", "threats", "swot_matrix"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-strategic-insights",
            name="Generate Strategic Insights",
            description="Develop strategic insights and recommendations based on analysis",
            executor="finance-lead",
            inputs={
                "swot": "swot-analysis.swot_matrix",
                "positioning": "analyze-market-positioning.positioning_analysis",
                "market_gaps": "analyze-market-positioning.market_gaps",
                "trends": "gather-competitor-data.recent_news",
            },
            outputs=["strategic_insights", "competitive_advantages", "threat_mitigation", "opportunity_capture"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="compile-report",
            name="Compile Intelligence Report",
            description="Compile all findings into a professional, PDF-ready competitive intelligence report",
            executor="content-lead",
            inputs={
                "company": "inputs.company_name",
                "competitor_profiles": "identify-competitors.competitor_profiles",
                "market_data": "gather-competitor-data.product_features",
                "positioning": "analyze-market-positioning.positioning_analysis",
                "swot": "swot-analysis.swot_matrix",
                "insights": "generate-strategic-insights.strategic_insights",
                "recommendations": "generate-strategic-insights.opportunity_capture",
            },
            outputs=["competitive_report", "executive_summary", "detailed_appendix", "visualization_data"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-competitor-list",
            name="Review Competitor List",
            type=CheckpointType.HUMAN_INPUT,
            after_step="identify-competitors",
            prompt="Review identified competitors. Add any missing competitors or remove irrelevant ones.",
            options=["Approve List", "Add Competitors", "Remove Competitors", "Modify Focus"],
        ),
        Checkpoint(
            id="approve-final-report",
            name="Approve Final Report",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="compile-report",
            prompt="Review the competitive intelligence report before distribution",
            options=["Approve for Distribution", "Request Revisions", "Add Analysis", "Reject"],
        ),
    ],
)


# =============================================================================
# 14. AUTOMATED DATA REPORT
# =============================================================================

AUTOMATED_DATA_REPORT = WorkflowDefinition(
    id="automated-data-report",
    name="Automated Data Report",
    description="Generate business metrics dashboards and reports with trend analysis and anomaly detection",
    version="1.0.0",
    tags=["data", "analytics", "reporting", "metrics", "business"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an automated data reporting workflow.
Your goal is to produce a comprehensive business metrics report with visualizations and insights.
Coordinate between Research (data queries), Finance (analysis), and Content (report generation).""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["report_name", "data_sources", "metrics_list", "time_period", "comparison_period", "recipients"],
    final_outputs=["data_report", "visualizations", "anomaly_alerts", "executive_summary"],

    steps=[
        WorkflowStep(
            id="query-data-sources",
            name="Query Data Sources",
            description="Connect to and query all specified data sources for the required metrics",
            executor="research-lead",
            inputs={
                "sources": "inputs.data_sources",
                "metrics": "inputs.metrics_list",
                "time_period": "inputs.time_period",
                "comparison_period": "inputs.comparison_period",
            },
            outputs=["raw_data", "data_quality_report", "missing_data_flags", "source_metadata"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="calculate-metrics",
            name="Calculate Metrics",
            description="Calculate all requested business metrics and KPIs from raw data",
            executor="finance-lead",
            inputs={
                "raw_data": "query-data-sources.raw_data",
                "metrics_list": "inputs.metrics_list",
                "time_period": "inputs.time_period",
            },
            outputs=["calculated_metrics", "period_totals", "averages", "growth_rates", "ratios"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="identify-trends",
            name="Identify Trends and Anomalies",
            description="Analyze data for trends, patterns, and statistical anomalies",
            executor="finance-lead",
            inputs={
                "metrics": "calculate-metrics.calculated_metrics",
                "comparison_period": "inputs.comparison_period",
                "historical_data": "query-data-sources.raw_data",
            },
            outputs=["trends", "anomalies", "seasonality_patterns", "correlation_analysis", "outliers"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="period-comparison",
            name="Period-over-Period Comparison",
            description="Compare current period metrics against previous periods",
            executor="finance-lead",
            inputs={
                "current_metrics": "calculate-metrics.calculated_metrics",
                "comparison_period": "inputs.comparison_period",
                "trends": "identify-trends.trends",
            },
            outputs=["period_comparison", "variance_analysis", "change_percentages", "performance_indicators"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="generate-visualizations",
            name="Generate Visualizations",
            description="Create chart specifications and visualization data for the report",
            executor="content-lead",
            inputs={
                "metrics": "calculate-metrics.calculated_metrics",
                "trends": "identify-trends.trends",
                "comparison": "period-comparison.period_comparison",
            },
            outputs=["chart_specifications", "dashboard_layout", "visualization_data", "color_coding"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-insights",
            name="Generate Insights and Recommendations",
            description="Analyze results and generate actionable business insights",
            executor="finance-lead",
            inputs={
                "metrics": "calculate-metrics.calculated_metrics",
                "trends": "identify-trends.trends",
                "anomalies": "identify-trends.anomalies",
                "comparison": "period-comparison.variance_analysis",
            },
            outputs=["key_insights", "recommendations", "risk_alerts", "opportunity_flags"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="compile-report",
            name="Compile Data Report",
            description="Compile all data, visualizations, and insights into the final report",
            executor="content-lead",
            inputs={
                "report_name": "inputs.report_name",
                "metrics": "calculate-metrics.calculated_metrics",
                "trends": "identify-trends.trends",
                "comparison": "period-comparison.period_comparison",
                "visualizations": "generate-visualizations.chart_specifications",
                "insights": "generate-insights.key_insights",
                "recommendations": "generate-insights.recommendations",
            },
            outputs=["data_report", "executive_summary", "detailed_metrics_table", "appendix"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="prepare-distribution",
            name="Prepare for Distribution",
            description="Prepare report for distribution to specified recipients",
            executor="orchestrator",
            inputs={
                "report": "compile-report.data_report",
                "summary": "compile-report.executive_summary",
                "recipients": "inputs.recipients",
                "anomalies": "identify-trends.anomalies",
            },
            outputs=["distribution_package", "alert_notifications", "delivery_schedule"],
            timeout_seconds=60,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="data-quality-review",
            name="Data Quality Review",
            type=CheckpointType.GATE,
            after_step="query-data-sources",
            gate_condition="query-data-sources.data_quality_report.score >= 0.8",
            failure_action="continue",
            prompt="Data quality below threshold - review missing data and source issues before proceeding",
        ),
        Checkpoint(
            id="anomaly-alert",
            name="Anomaly Alert Review",
            type=CheckpointType.REVIEW,
            after_step="identify-trends",
            prompt="Review detected anomalies and determine if they require immediate attention",
        ),
        Checkpoint(
            id="approve-report-distribution",
            name="Approve Report Distribution",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="prepare-distribution",
            prompt="Review and approve the data report before distribution to recipients",
            options=["Approve and Send", "Edit Report", "Hold Distribution", "Add Recipients"],
        ),
    ],
)


# =============================================================================
# 15. NEWS INTELLIGENCE BRIEFING
# =============================================================================

NEWS_INTELLIGENCE_BRIEFING = WorkflowDefinition(
    id="news-intelligence-briefing",
    name="News Intelligence Briefing",
    description="Generate daily intelligence briefings by aggregating and analyzing news from multiple RSS feeds and web sources",
    version="1.0.0",
    tags=["news", "intelligence", "research", "briefing", "media"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a news intelligence briefing workflow.
Your goal is to produce a comprehensive, actionable daily intelligence briefing for executives.
Aggregate news from multiple sources, identify key themes, and highlight items requiring attention.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["topics", "rss_feeds", "competitors", "time_window_hours"],
    final_outputs=["intelligence_briefing", "key_alerts", "trend_analysis", "recommended_actions"],

    steps=[
        WorkflowStep(
            id="aggregate-rss-feeds",
            name="Aggregate RSS Feeds",
            description="Fetch and parse all configured RSS feeds for recent articles",
            executor="research-lead",
            inputs={
                "feeds": "inputs.rss_feeds",
                "time_window": "inputs.time_window_hours",
            },
            outputs=["feed_articles", "source_counts", "publication_timeline", "feed_health"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="web-search-supplement",
            name="Supplement with Web Search",
            description="Search web for additional coverage on key topics not in RSS feeds",
            executor="research-lead",
            inputs={
                "topics": "inputs.topics",
                "competitors": "inputs.competitors",
                "existing_coverage": "aggregate-rss-feeds.feed_articles",
            },
            outputs=["web_articles", "coverage_gaps", "trending_topics"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="categorize-articles",
            name="Categorize and Prioritize",
            description="Categorize articles by topic, sentiment, and relevance; identify urgent items",
            executor="research-lead",
            inputs={
                "rss_articles": "aggregate-rss-feeds.feed_articles",
                "web_articles": "web-search-supplement.web_articles",
                "topics": "inputs.topics",
                "competitors": "inputs.competitors",
            },
            outputs=["categorized_articles", "priority_items", "sentiment_analysis", "competitor_mentions"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="identify-trends",
            name="Identify Themes and Trends",
            description="Analyze articles to identify emerging themes, trends, and patterns",
            executor="research-lead",
            inputs={
                "articles": "categorize-articles.categorized_articles",
                "sentiment": "categorize-articles.sentiment_analysis",
                "trending": "web-search-supplement.trending_topics",
            },
            outputs=["key_themes", "emerging_trends", "sentiment_shift", "volume_analysis"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-alerts",
            name="Generate Priority Alerts",
            description="Create actionable alerts for high-priority items requiring immediate attention",
            executor="research-lead",
            inputs={
                "priority_items": "categorize-articles.priority_items",
                "competitor_mentions": "categorize-articles.competitor_mentions",
                "sentiment": "categorize-articles.sentiment_analysis",
            },
            outputs=["key_alerts", "alert_severity", "recommended_responses", "stakeholders_to_notify"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="compile-briefing",
            name="Compile Intelligence Briefing",
            description="Create executive-ready intelligence briefing with summaries and recommendations",
            executor="content-lead",
            inputs={
                "articles": "categorize-articles.categorized_articles",
                "themes": "identify-trends.key_themes",
                "trends": "identify-trends.emerging_trends",
                "alerts": "generate-alerts.key_alerts",
                "sentiment": "categorize-articles.sentiment_analysis",
            },
            outputs=["intelligence_briefing", "executive_summary", "detailed_sections", "appendix"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-alerts",
            name="Review Priority Alerts",
            type=CheckpointType.REVIEW,
            after_step="generate-alerts",
            prompt="Review generated alerts before including in final briefing",
        ),
        Checkpoint(
            id="approve-briefing",
            name="Approve Intelligence Briefing",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="compile-briefing",
            prompt="Review and approve the intelligence briefing before distribution",
            options=["Approve and Distribute", "Edit Briefing", "Add Analysis", "Hold Distribution"],
        ),
    ],
)


# =============================================================================
# 16. DATA PROCESSING REPORT
# =============================================================================

DATA_PROCESSING_REPORT = WorkflowDefinition(
    id="data-processing-report",
    name="Data Processing Report",
    description="Process CSV/tabular data files with cleaning, transformation, analysis, and automated report generation",
    version="1.0.0",
    tags=["data", "csv", "analytics", "etl", "reporting"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a data processing and reporting workflow.
Your goal is to process raw data files, perform quality checks and transformations,
generate insightful analysis, and produce a professional report with visualizations.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["data_source", "report_name", "analysis_goals", "output_format"],
    final_outputs=["processed_data", "analysis_report", "visualizations", "data_quality_report"],

    steps=[
        WorkflowStep(
            id="parse-data",
            name="Parse and Validate Data",
            description="Parse the input data file and perform initial validation",
            executor="research-lead",
            inputs={
                "source": "inputs.data_source",
            },
            outputs=["parsed_data", "schema", "row_count", "column_types", "parse_errors"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="data-quality-check",
            name="Data Quality Assessment",
            description="Assess data quality including completeness, accuracy, and consistency",
            executor="research-lead",
            inputs={
                "data": "parse-data.parsed_data",
                "schema": "parse-data.schema",
            },
            outputs=["quality_score", "missing_values", "outliers", "duplicates", "inconsistencies"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="clean-transform",
            name="Clean and Transform Data",
            description="Clean data issues and apply necessary transformations",
            executor="research-lead",
            inputs={
                "data": "parse-data.parsed_data",
                "quality_issues": "data-quality-check.missing_values",
                "outliers": "data-quality-check.outliers",
            },
            outputs=["cleaned_data", "transformations_applied", "records_modified", "records_removed"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="statistical-analysis",
            name="Statistical Analysis",
            description="Perform statistical analysis including descriptive stats, correlations, and distributions",
            executor="finance-lead",
            inputs={
                "data": "clean-transform.cleaned_data",
                "goals": "inputs.analysis_goals",
            },
            outputs=["descriptive_stats", "correlations", "distributions", "aggregations", "key_metrics"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="trend-analysis",
            name="Trend and Pattern Analysis",
            description="Identify trends, patterns, and anomalies in the data",
            executor="finance-lead",
            inputs={
                "data": "clean-transform.cleaned_data",
                "stats": "statistical-analysis.descriptive_stats",
                "goals": "inputs.analysis_goals",
            },
            outputs=["trends", "patterns", "anomalies", "segments", "forecasts"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-insights",
            name="Generate Business Insights",
            description="Derive actionable business insights from the analysis",
            executor="finance-lead",
            inputs={
                "stats": "statistical-analysis.key_metrics",
                "trends": "trend-analysis.trends",
                "patterns": "trend-analysis.patterns",
                "goals": "inputs.analysis_goals",
            },
            outputs=["key_insights", "recommendations", "opportunities", "risks"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="create-visualizations",
            name="Create Visualizations",
            description="Generate chart specifications for data visualization",
            executor="content-lead",
            inputs={
                "data": "clean-transform.cleaned_data",
                "stats": "statistical-analysis.descriptive_stats",
                "trends": "trend-analysis.trends",
                "insights": "generate-insights.key_insights",
            },
            outputs=["chart_specs", "dashboard_layout", "visualization_data"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="compile-report",
            name="Compile Analysis Report",
            description="Compile all findings into a comprehensive report",
            executor="content-lead",
            inputs={
                "report_name": "inputs.report_name",
                "quality_report": "data-quality-check.quality_score",
                "stats": "statistical-analysis.descriptive_stats",
                "insights": "generate-insights.key_insights",
                "recommendations": "generate-insights.recommendations",
                "visualizations": "create-visualizations.chart_specs",
                "format": "inputs.output_format",
            },
            outputs=["analysis_report", "executive_summary", "detailed_findings", "appendix"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="data-quality-gate",
            name="Data Quality Gate",
            type=CheckpointType.GATE,
            after_step="data-quality-check",
            gate_condition="data-quality-check.quality_score >= 0.7",
            failure_action="continue",
            prompt="Data quality below threshold - review issues before proceeding with analysis",
        ),
        Checkpoint(
            id="review-insights",
            name="Review Insights",
            type=CheckpointType.HUMAN_INPUT,
            after_step="generate-insights",
            prompt="Review generated insights and add any domain-specific observations",
            options=["Approve Insights", "Add Insights", "Re-analyze Data", "Change Goals"],
        ),
        Checkpoint(
            id="approve-report",
            name="Approve Final Report",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="compile-report",
            prompt="Review and approve the data analysis report before distribution",
            options=["Approve", "Request Revisions", "Add Analysis", "Reject"],
        ),
    ],
)


# =============================================================================
# 17. GLOBAL CONTENT LOCALIZATION
# =============================================================================

GLOBAL_CONTENT_LOCALIZATION = WorkflowDefinition(
    id="global-content-localization",
    name="Global Content Localization",
    description="Localize content for multiple markets with translation, cultural adaptation, and format localization",
    version="1.0.0",
    tags=["localization", "translation", "content", "international", "marketing"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a global content localization workflow.
Your goal is to adapt content for multiple target markets while maintaining brand voice,
ensuring cultural appropriateness, and localizing formats (dates, currencies, etc.).""",

    team_leads=[CONTENT_TEAM_LEAD, RESEARCH_TEAM_LEAD],

    required_inputs=["source_content", "source_language", "target_markets", "content_type", "brand_guidelines"],
    final_outputs=["localized_content", "cultural_notes", "qa_report", "style_consistency_report"],

    steps=[
        WorkflowStep(
            id="analyze-source",
            name="Analyze Source Content",
            description="Analyze source content for structure, tone, cultural references, and localization requirements",
            executor="content-lead",
            inputs={
                "content": "inputs.source_content",
                "source_language": "inputs.source_language",
                "content_type": "inputs.content_type",
            },
            outputs=["content_analysis", "cultural_references", "idioms", "brand_elements", "format_elements"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="research-markets",
            name="Research Target Markets",
            description="Research cultural nuances, preferences, and sensitivities for each target market",
            executor="research-lead",
            inputs={
                "markets": "inputs.target_markets",
                "cultural_references": "analyze-source.cultural_references",
                "content_type": "inputs.content_type",
            },
            outputs=["market_profiles", "cultural_considerations", "local_preferences", "sensitive_topics"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="create-translation-brief",
            name="Create Translation Brief",
            description="Create translation brief with guidelines for each target market",
            executor="content-lead",
            inputs={
                "content_analysis": "analyze-source.content_analysis",
                "market_profiles": "research-markets.market_profiles",
                "brand_guidelines": "inputs.brand_guidelines",
                "cultural_considerations": "research-markets.cultural_considerations",
            },
            outputs=["translation_briefs", "terminology_glossary", "style_guidelines", "dont_translate_list"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="translate-content",
            name="Translate Content",
            description="Translate content to each target language following the translation brief",
            executor="content-lead",
            inputs={
                "content": "inputs.source_content",
                "target_markets": "inputs.target_markets",
                "briefs": "create-translation-brief.translation_briefs",
                "glossary": "create-translation-brief.terminology_glossary",
            },
            outputs=["raw_translations", "translation_notes", "uncertain_terms"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="cultural-adaptation",
            name="Cultural Adaptation",
            description="Adapt translated content for cultural appropriateness and local preferences",
            executor="content-lead",
            inputs={
                "translations": "translate-content.raw_translations",
                "market_profiles": "research-markets.market_profiles",
                "sensitive_topics": "research-markets.sensitive_topics",
                "cultural_considerations": "research-markets.cultural_considerations",
            },
            outputs=["adapted_content", "adaptations_made", "cultural_notes", "risk_flags"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="format-localization",
            name="Format Localization",
            description="Localize formats including dates, currencies, numbers, and addresses",
            executor="content-lead",
            inputs={
                "content": "cultural-adaptation.adapted_content",
                "target_markets": "inputs.target_markets",
                "format_elements": "analyze-source.format_elements",
            },
            outputs=["formatted_content", "format_changes", "locale_settings"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="quality-assurance",
            name="Quality Assurance",
            description="Review localized content for accuracy, consistency, and brand alignment",
            executor="content-lead",
            inputs={
                "source": "inputs.source_content",
                "localized": "format-localization.formatted_content",
                "brand_guidelines": "inputs.brand_guidelines",
                "glossary": "create-translation-brief.terminology_glossary",
            },
            outputs=["qa_report", "issues_found", "style_consistency_score", "recommendations"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="finalize-deliverables",
            name="Finalize Deliverables",
            description="Prepare final localized content deliverables for each market",
            executor="content-lead",
            inputs={
                "content": "format-localization.formatted_content",
                "qa_report": "quality-assurance.qa_report",
                "cultural_notes": "cultural-adaptation.cultural_notes",
                "markets": "inputs.target_markets",
            },
            outputs=["localized_content", "delivery_package", "implementation_notes", "review_summary"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-translation-brief",
            name="Approve Translation Brief",
            type=CheckpointType.HUMAN_INPUT,
            after_step="create-translation-brief",
            prompt="Review translation guidelines and terminology before proceeding",
            options=["Approve Guidelines", "Modify Glossary", "Add Instructions", "Revise Brief"],
        ),
        Checkpoint(
            id="review-cultural-adaptation",
            name="Review Cultural Adaptation",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="cultural-adaptation",
            prompt="Review cultural adaptations for appropriateness and risk flags",
            options=["Approve Adaptations", "Request Changes", "Flag for Expert Review", "Reject"],
        ),
        Checkpoint(
            id="final-approval",
            name="Final Localization Approval",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="quality-assurance",
            prompt="Review QA report and approve localized content for delivery",
            options=["Approve All Markets", "Approve Select Markets", "Request Revisions", "Reject"],
        ),
    ],
)


# =============================================================================
# 18. HELP DESK TRIAGE & RESOLUTION
# =============================================================================

HELP_DESK_TRIAGE = WorkflowDefinition(
    id="help-desk-triage",
    name="Help Desk Triage & Resolution",
    description="Automated help desk ticket triage, knowledge base search, and resolution with escalation",
    version="1.0.0",
    tags=["support", "helpdesk", "triage", "automation"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a help desk triage and resolution workflow.
Your goal is to analyze incoming support tickets, attempt automated resolution using knowledge base,
check system logs if needed, and escalate only when necessary. Target: 40-50% auto-resolution rate.""",

    team_leads=[INVESTIGATION_TEAM_LEAD, RESEARCH_TEAM_LEAD, DEVOPS_TEAM_LEAD],

    required_inputs=["ticket_id", "ticket_description", "user_email", "priority", "category"],
    final_outputs=["resolution_status", "response", "knowledge_article_used", "escalation_needed"],

    steps=[
        WorkflowStep(
            id="analyze-ticket",
            name="Analyze Ticket",
            description="Parse ticket to understand the issue, extract key details, and classify urgency",
            executor="investigation-lead",
            inputs={
                "ticket": "inputs.ticket_description",
                "category": "inputs.category",
                "priority": "inputs.priority",
            },
            outputs=["issue_summary", "key_symptoms", "affected_component", "urgency_level", "ticket_complexity"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="search-knowledge-base",
            name="Search Knowledge Base",
            description="Search existing knowledge base articles for similar issues and solutions",
            executor="research-lead",
            inputs={
                "issue": "analyze-ticket.issue_summary",
                "symptoms": "analyze-ticket.key_symptoms",
                "component": "analyze-ticket.affected_component",
            },
            outputs=["matching_articles", "solution_steps", "confidence_score", "similar_tickets"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="attempt-resolution",
            name="Attempt Auto-Resolution",
            description="Generate resolution based on knowledge base findings and verify applicability",
            executor="investigation-lead",
            inputs={
                "issue": "analyze-ticket.issue_summary",
                "solutions": "search-knowledge-base.solution_steps",
                "articles": "search-knowledge-base.matching_articles",
                "confidence": "search-knowledge-base.confidence_score",
            },
            outputs=["resolution_steps", "resolution_confidence", "user_instructions", "verification_needed"],
            timeout_seconds=120,
            condition="search-knowledge-base.confidence_score >= 0.6",
        ),
        WorkflowStep(
            id="check-system-logs",
            name="Check System Logs",
            description="If knowledge base has low confidence, check system logs for errors or anomalies",
            executor="devops-lead",
            inputs={
                "component": "analyze-ticket.affected_component",
                "symptoms": "analyze-ticket.key_symptoms",
                "ticket_id": "inputs.ticket_id",
            },
            outputs=["log_findings", "error_patterns", "root_cause_hypothesis", "system_status"],
            timeout_seconds=150,
            condition="search-knowledge-base.confidence_score < 0.6",
        ),
        WorkflowStep(
            id="escalation-decision",
            name="Escalation Decision",
            description="Decide whether to auto-resolve or escalate to human agent",
            executor="orchestrator",
            inputs={
                "complexity": "analyze-ticket.ticket_complexity",
                "resolution_confidence": "attempt-resolution.resolution_confidence",
                "log_findings": "check-system-logs.log_findings",
                "priority": "inputs.priority",
            },
            outputs=["escalate", "escalation_reason", "assigned_tier", "estimated_resolution_time"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="generate-response",
            name="Generate Customer Response",
            description="Draft response to customer with resolution or escalation notice",
            executor="research-lead",
            inputs={
                "issue": "analyze-ticket.issue_summary",
                "resolution": "attempt-resolution.user_instructions",
                "escalate": "escalation-decision.escalate",
                "user_email": "inputs.user_email",
            },
            outputs=["response_draft", "follow_up_actions", "sla_deadline"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="verify-auto-resolution",
            name="Verify Auto-Resolution",
            type=CheckpointType.GATE,
            after_step="attempt-resolution",
            gate_condition="attempt-resolution.resolution_confidence >= 0.75",
            failure_action="continue",
            prompt="Resolution confidence below threshold - may need human review",
        ),
        Checkpoint(
            id="approve-response",
            name="Approve Customer Response",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="generate-response",
            prompt="Review and approve the response before sending to customer",
            options=["Send Response", "Edit Response", "Escalate to L2", "Request More Info"],
        ),
    ],
)


# =============================================================================
# 19. RFP RESPONSE GENERATION
# =============================================================================

RFP_RESPONSE_GENERATION = WorkflowDefinition(
    id="rfp-response",
    name="RFP Response Generation",
    description="Automated RFP response generation with requirement extraction, proposal drafting, pricing, and compliance review",
    version="1.0.0",
    tags=["sales", "rfp", "proposal", "compliance"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an RFP response generation workflow.
Your goal is to produce a comprehensive, compliant, competitive proposal in 70% less time than manual process.
Coordinate between Research (requirements), Sales (past proposals), Content (drafting), Finance (pricing), and Legal (compliance).""",

    team_leads=[RESEARCH_TEAM_LEAD, SALES_TEAM_LEAD, CONTENT_TEAM_LEAD, FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD],

    required_inputs=["rfp_document", "client_name", "deadline", "target_price_range"],
    final_outputs=["rfp_response_document", "executive_summary", "pricing_proposal", "compliance_checklist"],

    steps=[
        WorkflowStep(
            id="extract-requirements",
            name="Extract RFP Requirements",
            description="Parse RFP document to extract all requirements, evaluation criteria, and submission guidelines",
            executor="research-lead",
            inputs={
                "rfp": "inputs.rfp_document",
                "client": "inputs.client_name",
            },
            outputs=["requirements_list", "evaluation_criteria", "mandatory_sections", "submission_deadline", "technical_specs"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="retrieve-past-proposals",
            name="Retrieve Past Proposals",
            description="Search for similar past proposals and winning responses to reuse content",
            executor="sales-lead",
            inputs={
                "requirements": "extract-requirements.requirements_list",
                "client": "inputs.client_name",
                "industry": "extract-requirements.technical_specs",
            },
            outputs=["similar_proposals", "winning_sections", "reusable_content", "case_studies"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="draft-technical-response",
            name="Draft Technical Response",
            description="Draft technical sections addressing each requirement with evidence",
            executor="content-lead",
            inputs={
                "requirements": "extract-requirements.requirements_list",
                "past_content": "retrieve-past-proposals.reusable_content",
                "specs": "extract-requirements.technical_specs",
            },
            outputs=["technical_sections", "requirement_mapping", "evidence_citations", "gap_analysis"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="generate-pricing",
            name="Generate Pricing Proposal",
            description="Create detailed pricing based on requirements and target range",
            executor="finance-lead",
            inputs={
                "requirements": "extract-requirements.requirements_list",
                "target_range": "inputs.target_price_range",
                "specs": "extract-requirements.technical_specs",
            },
            outputs=["pricing_breakdown", "total_cost", "payment_terms", "discount_options", "cost_justification"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="draft-executive-summary",
            name="Draft Executive Summary",
            description="Create compelling executive summary highlighting value proposition",
            executor="sales-lead",
            inputs={
                "client": "inputs.client_name",
                "requirements": "extract-requirements.requirements_list",
                "technical_response": "draft-technical-response.technical_sections",
                "pricing": "generate-pricing.total_cost",
                "case_studies": "retrieve-past-proposals.case_studies",
            },
            outputs=["executive_summary", "value_proposition", "differentiation_points", "success_stories"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="compliance-review",
            name="Compliance Review",
            description="Review proposal for compliance with RFP requirements and legal constraints",
            executor="legal-lead",
            inputs={
                "rfp_requirements": "extract-requirements.mandatory_sections",
                "response": "draft-technical-response.technical_sections",
                "pricing": "generate-pricing.pricing_breakdown",
            },
            outputs=["compliance_status", "missing_sections", "legal_risks", "required_disclaimers"],
            timeout_seconds=150,
        ),
        WorkflowStep(
            id="compile-document",
            name="Compile Final Document",
            description="Assemble all sections into final RFP response document with formatting",
            executor="content-lead",
            inputs={
                "executive_summary": "draft-executive-summary.executive_summary",
                "technical_sections": "draft-technical-response.technical_sections",
                "pricing": "generate-pricing.pricing_breakdown",
                "compliance": "compliance-review.compliance_status",
                "mandatory_sections": "extract-requirements.mandatory_sections",
            },
            outputs=["rfp_response_document", "table_of_contents", "appendices", "formatting_notes"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-requirements",
            name="Review Extracted Requirements",
            type=CheckpointType.HUMAN_INPUT,
            after_step="extract-requirements",
            prompt="Review extracted requirements and add any missing items or clarifications",
            options=["Approve Requirements", "Add Requirements", "Request Clarification", "Flag Constraints"],
        ),
        Checkpoint(
            id="approve-pricing",
            name="Approve Pricing Proposal",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="generate-pricing",
            prompt="Review and approve pricing before including in final proposal",
            options=["Approve Pricing", "Adjust Pricing", "Request Discount Authority", "Reject"],
        ),
        Checkpoint(
            id="compliance-gate",
            name="Compliance Gate",
            type=CheckpointType.GATE,
            after_step="compliance-review",
            gate_condition="compliance-review.missing_sections == []",
            failure_action="abort",
            prompt="Compliance issues detected - missing mandatory sections must be addressed",
        ),
        Checkpoint(
            id="final-approval",
            name="Executive Review & Approval",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="compile-document",
            prompt="Final executive review of complete RFP response before submission",
            options=["Approve for Submission", "Request Revisions", "Schedule Review Meeting", "Decline RFP"],
        ),
    ],
)


# =============================================================================
# 20. API INTEGRATION AUTOMATION
# =============================================================================

API_INTEGRATION_AUTOMATION = WorkflowDefinition(
    id="api-integration-automation",
    name="API Integration Automation",
    description="No-code API integration workflow - discover endpoints, test, generate integration code",
    version="1.0.0",
    tags=["devops", "automation", "integration"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an API integration automation workflow.
Your goal is to analyze API documentation, test endpoints, and generate production-ready integration code.""",

    team_leads=[DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["api_documentation_url", "integration_requirements", "target_platform"],
    final_outputs=["api_analysis", "integration_code", "test_results", "documentation"],

    steps=[
        WorkflowStep(
            id="api-discovery",
            name="API Discovery & Analysis",
            description="Analyze API documentation and identify available endpoints",
            executor="research-lead",
            inputs={
                "documentation_url": "inputs.api_documentation_url",
                "requirements": "inputs.integration_requirements",
            },
            outputs=["api_endpoints", "authentication_methods", "rate_limits", "data_models"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="endpoint-testing",
            name="Endpoint Testing & Validation",
            description="Test API endpoints and validate responses",
            executor="devops-lead",
            inputs={
                "endpoints": "api-discovery.api_endpoints",
                "auth_methods": "api-discovery.authentication_methods",
            },
            outputs=["test_results", "response_schemas", "error_scenarios"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="code-generation",
            name="Integration Code Generation",
            description="Generate production-ready integration code",
            executor="devops-lead",
            inputs={
                "endpoints": "api-discovery.api_endpoints",
                "schemas": "endpoint-testing.response_schemas",
                "platform": "inputs.target_platform",
            },
            outputs=["integration_code", "error_handling", "retry_logic"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="create-documentation",
            name="Create Integration Documentation",
            description="Generate comprehensive integration documentation",
            executor="content-lead",
            inputs={
                "api_analysis": "api-discovery.api_endpoints",
                "code": "code-generation.integration_code",
                "test_results": "endpoint-testing.test_results",
            },
            outputs=["setup_guide", "usage_examples", "troubleshooting"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-endpoints",
            name="Approve API Endpoints",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="api-discovery",
            prompt="Review discovered API endpoints and authentication methods",
            options=["Approve", "Modify Selection", "Request Additional Research"],
        ),
        Checkpoint(
            id="validate-code",
            name="Validate Generated Code",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="code-generation",
            prompt="Review generated integration code before deployment",
            options=["Approve for Deployment", "Request Modifications", "Run Additional Tests"],
        ),
    ],
)


# =============================================================================
# 21. CONTRACT ANALYSIS & RISK EXTRACTION
# =============================================================================

CONTRACT_ANALYSIS = WorkflowDefinition(
    id="contract-analysis",
    name="Contract Analysis & Risk Extraction",
    description="Analyze contracts, extract key terms, identify risks, generate summary",
    version="1.0.0",
    tags=["legal", "compliance", "risk"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a contract analysis workflow.
Your goal is to extract key terms, identify risks, verify compliance, and provide actionable recommendations.""",

    team_leads=[LEGAL_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["contract_document", "contract_type", "jurisdiction"],
    final_outputs=["key_terms", "risk_assessment", "compliance_report", "executive_summary"],

    steps=[
        WorkflowStep(
            id="clause-extraction",
            name="Document Ingestion & Clause Extraction",
            description="Parse contract and extract all clauses and key terms",
            executor="legal-lead",
            inputs={
                "document": "inputs.contract_document",
                "contract_type": "inputs.contract_type",
            },
            outputs=["clauses", "parties", "dates", "financial_terms", "obligations"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="risk-identification",
            name="Risk Identification & Assessment",
            description="Identify legal risks, unfavorable terms, and red flags",
            executor="legal-lead",
            inputs={
                "clauses": "clause-extraction.clauses",
                "obligations": "clause-extraction.obligations",
                "contract_type": "inputs.contract_type",
            },
            outputs=["risk_items", "risk_severity", "liability_exposure", "termination_risks"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="compliance-verification",
            name="Compliance Verification",
            description="Verify compliance with regulations and internal policies",
            executor="legal-lead",
            inputs={
                "clauses": "clause-extraction.clauses",
                "jurisdiction": "inputs.jurisdiction",
            },
            outputs=["compliance_status", "missing_clauses", "regulatory_concerns"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="research-precedents",
            name="Research Precedents & Benchmarks",
            description="Research similar contracts and industry standards",
            executor="research-lead",
            inputs={
                "contract_type": "inputs.contract_type",
                "key_terms": "clause-extraction.financial_terms",
            },
            outputs=["market_benchmarks", "precedents", "best_practices"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="generate-summary",
            name="Generate Summary Report",
            description="Create executive summary with recommendations",
            executor="content-lead",
            inputs={
                "key_terms": "clause-extraction.clauses",
                "risks": "risk-identification.risk_items",
                "compliance": "compliance-verification.compliance_status",
                "benchmarks": "research-precedents.market_benchmarks",
            },
            outputs=["executive_summary", "recommendations", "negotiation_points"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-risks",
            name="Review Risk Assessment",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="risk-identification",
            prompt="Review identified risks and severity ratings",
            options=["Approve", "Escalate High Risks", "Request Additional Analysis"],
        ),
        Checkpoint(
            id="approve-summary",
            name="Approve Summary & Recommendations",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="generate-summary",
            prompt="Review final contract analysis and recommendations",
            options=["Approve", "Request Revisions", "Schedule Review Meeting"],
        ),
    ],
)


# =============================================================================
# 22. MEETING INTELLIGENCE WORKFLOW
# =============================================================================

MEETING_INTELLIGENCE = WorkflowDefinition(
    id="meeting-intelligence",
    name="Meeting Intelligence Workflow",
    description="Process meeting transcripts, extract decisions, assign action items, generate summaries",
    version="1.0.0",
    tags=["productivity", "knowledge", "collaboration"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a meeting intelligence workflow.
Your goal is to extract actionable insights, decisions, and action items from meeting transcripts.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["meeting_transcript", "meeting_title", "attendees"],
    final_outputs=["meeting_summary", "action_items", "decisions", "follow_ups"],

    steps=[
        WorkflowStep(
            id="transcript-processing",
            name="Transcript Processing & Speaker Identification",
            description="Process transcript and identify speakers and topics",
            executor="research-lead",
            inputs={
                "transcript": "inputs.meeting_transcript",
                "attendees": "inputs.attendees",
            },
            outputs=["processed_transcript", "speaker_segments", "topics_discussed"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="extract-action-items",
            name="Action Item Extraction with Assignees",
            description="Identify all action items and assign to attendees",
            executor="research-lead",
            inputs={
                "transcript": "transcript-processing.processed_transcript",
                "speakers": "transcript-processing.speaker_segments",
                "attendees": "inputs.attendees",
            },
            outputs=["action_items", "assignees", "due_dates", "priorities"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="track-decisions",
            name="Decision Tracking & Documentation",
            description="Extract decisions made and their context",
            executor="content-lead",
            inputs={
                "transcript": "transcript-processing.processed_transcript",
                "topics": "transcript-processing.topics_discussed",
            },
            outputs=["decisions", "decision_context", "decision_makers", "rationale"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="generate-summary",
            name="Generate Meeting Summary",
            description="Create comprehensive meeting summary and notes",
            executor="content-lead",
            inputs={
                "transcript": "transcript-processing.processed_transcript",
                "topics": "transcript-processing.topics_discussed",
                "decisions": "track-decisions.decisions",
                "actions": "extract-action-items.action_items",
                "meeting_title": "inputs.meeting_title",
            },
            outputs=["summary", "key_points", "discussion_notes"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="schedule-followups",
            name="Follow-up Scheduling & Reminders",
            description="Create follow-up tasks and schedule reminders",
            executor="content-lead",
            inputs={
                "action_items": "extract-action-items.action_items",
                "due_dates": "extract-action-items.due_dates",
                "assignees": "extract-action-items.assignees",
            },
            outputs=["calendar_events", "reminders", "follow_up_meetings"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="verify-action-items",
            name="Verify Action Items & Assignees",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="extract-action-items",
            prompt="Review extracted action items and verify assignees",
            options=["Approve", "Modify Assignees", "Add Items", "Adjust Due Dates"],
        ),
    ],
)


# =============================================================================
# 23. RESEARCH LITERATURE REVIEW
# =============================================================================

RESEARCH_LITERATURE_REVIEW = WorkflowDefinition(
    id="research-literature-review",
    name="Research Literature Review",
    description="Systematic literature review - search, analyze, synthesize research papers",
    version="1.0.0",
    tags=["research", "analysis", "academic"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a systematic literature review workflow.
Your goal is to identify, analyze, and synthesize relevant research papers on a given topic.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["research_topic", "search_keywords", "date_range", "minimum_papers"],
    final_outputs=["paper_list", "synthesis_report", "gap_analysis", "citations"],

    steps=[
        WorkflowStep(
            id="query-formulation",
            name="Search Query Formulation & Paper Discovery",
            description="Formulate search queries and discover relevant papers",
            executor="research-lead",
            inputs={
                "topic": "inputs.research_topic",
                "keywords": "inputs.search_keywords",
                "date_range": "inputs.date_range",
            },
            outputs=["search_queries", "papers_found", "databases_searched"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="paper-screening",
            name="Paper Screening & Relevance Filtering",
            description="Screen papers and filter by relevance criteria",
            executor="research-lead",
            inputs={
                "papers": "query-formulation.papers_found",
                "topic": "inputs.research_topic",
                "minimum_count": "inputs.minimum_papers",
            },
            outputs=["relevant_papers", "excluded_papers", "screening_criteria"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="full-text-analysis",
            name="Full-Text Analysis & Extraction",
            description="Analyze full text of selected papers and extract key information",
            executor="research-lead",
            inputs={
                "papers": "paper-screening.relevant_papers",
            },
            outputs=["extracted_findings", "methodologies", "key_results", "citations"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="synthesis",
            name="Synthesis & Gap Analysis",
            description="Synthesize findings and identify research gaps",
            executor="content-lead",
            inputs={
                "findings": "full-text-analysis.extracted_findings",
                "methodologies": "full-text-analysis.methodologies",
                "papers": "paper-screening.relevant_papers",
                "topic": "inputs.research_topic",
            },
            outputs=["synthesis", "themes", "research_gaps", "future_directions"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="generate-report",
            name="Report Generation with Citations",
            description="Generate comprehensive literature review report",
            executor="content-lead",
            inputs={
                "synthesis": "synthesis.synthesis",
                "gaps": "synthesis.research_gaps",
                "papers": "paper-screening.relevant_papers",
                "citations": "full-text-analysis.citations",
            },
            outputs=["literature_review", "bibliography", "summary_table"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-screening",
            name="Review Paper Screening Results",
            type=CheckpointType.REVIEW,
            after_step="paper-screening",
            prompt="Review the list of papers selected for full analysis",
        ),
        Checkpoint(
            id="approve-synthesis",
            name="Approve Synthesis & Gap Analysis",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="synthesis",
            prompt="Review the synthesis and identified research gaps",
            options=["Approve", "Request Additional Papers", "Revise Analysis"],
        ),
    ],
)


# =============================================================================
# 24. MULTI-CHANNEL CONTENT DISTRIBUTION
# =============================================================================

CONTENT_DISTRIBUTION = WorkflowDefinition(
    id="content-distribution",
    name="Multi-Channel Content Distribution",
    description="Repurpose content for multiple channels (blog, social, email, video scripts)",
    version="1.0.0",
    tags=["content", "marketing", "distribution"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a multi-channel content distribution workflow.
Your goal is to repurpose a single piece of content for maximum reach across all channels.""",

    team_leads=[CONTENT_TEAM_LEAD, SALES_TEAM_LEAD],

    required_inputs=["source_content", "target_channels", "target_audiences", "brand_guidelines"],
    final_outputs=["blog_post", "social_posts", "email_campaign", "video_scripts", "distribution_schedule"],

    steps=[
        WorkflowStep(
            id="content-analysis",
            name="Content Analysis & Key Message Extraction",
            description="Analyze source content and extract key messages",
            executor="content-lead",
            inputs={
                "content": "inputs.source_content",
                "guidelines": "inputs.brand_guidelines",
            },
            outputs=["key_messages", "themes", "quotes", "statistics"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="platform-adaptation",
            name="Platform-Specific Adaptation",
            description="Adapt content for each target platform",
            executor="content-lead",
            inputs={
                "key_messages": "content-analysis.key_messages",
                "channels": "inputs.target_channels",
                "guidelines": "inputs.brand_guidelines",
            },
            outputs=["blog_version", "linkedin_posts", "twitter_threads", "instagram_captions", "video_scripts"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="audience-targeting",
            name="Audience Targeting & Personalization",
            description="Personalize content for different audience segments",
            executor="sales-lead",
            inputs={
                "adapted_content": "platform-adaptation.blog_version",
                "audiences": "inputs.target_audiences",
            },
            outputs=["audience_segments", "personalized_messages", "targeting_parameters"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="distribution-scheduling",
            name="Distribution Scheduling & Tracking",
            description="Create distribution schedule and tracking plan",
            executor="sales-lead",
            inputs={
                "content": "platform-adaptation.linkedin_posts",
                "channels": "inputs.target_channels",
                "segments": "audience-targeting.audience_segments",
            },
            outputs=["distribution_calendar", "posting_times", "tracking_links", "metrics_plan"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="approve-adaptations",
            name="Approve Platform Adaptations",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="platform-adaptation",
            prompt="Review content adapted for each platform",
            options=["Approve All", "Approve Selected", "Request Revisions"],
        ),
        Checkpoint(
            id="approve-schedule",
            name="Approve Distribution Schedule",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="distribution-scheduling",
            prompt="Review and approve the content distribution schedule",
            options=["Approve", "Adjust Timing", "Modify Channels"],
        ),
    ],
)


# =============================================================================
# 25. COMPLIANCE AUDIT TRAIL
# =============================================================================

COMPLIANCE_AUDIT = WorkflowDefinition(
    id="compliance-audit",
    name="Compliance Audit Trail",
    description="Automated compliance checking, violation detection, audit trail generation",
    version="1.0.0",
    tags=["compliance", "legal", "audit"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a compliance audit workflow.
Your goal is to check systems and processes for compliance violations and generate comprehensive audit trails.""",

    team_leads=[LEGAL_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["compliance_framework", "audit_scope", "systems_to_audit"],
    final_outputs=["compliance_status", "violations_found", "remediation_plan", "audit_report"],

    steps=[
        WorkflowStep(
            id="requirement-gathering",
            name="Compliance Requirement Gathering",
            description="Gather all applicable compliance requirements",
            executor="legal-lead",
            inputs={
                "framework": "inputs.compliance_framework",
                "scope": "inputs.audit_scope",
            },
            outputs=["requirements", "controls", "documentation_needed", "testing_procedures"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="system-audit",
            name="System/Process Audit",
            description="Audit systems and processes against requirements",
            executor="research-lead",
            inputs={
                "requirements": "requirement-gathering.requirements",
                "systems": "inputs.systems_to_audit",
                "controls": "requirement-gathering.controls",
            },
            outputs=["audit_findings", "control_effectiveness", "evidence_collected"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="violation-detection",
            name="Violation Detection & Documentation",
            description="Identify compliance violations and document details",
            executor="legal-lead",
            inputs={
                "findings": "system-audit.audit_findings",
                "requirements": "requirement-gathering.requirements",
                "controls": "system-audit.control_effectiveness",
            },
            outputs=["violations", "severity_ratings", "root_causes", "affected_areas"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="remediation-recommendations",
            name="Remediation Recommendations",
            description="Provide recommendations to address violations",
            executor="legal-lead",
            inputs={
                "violations": "violation-detection.violations",
                "root_causes": "violation-detection.root_causes",
            },
            outputs=["remediation_steps", "priority_order", "implementation_timeline", "responsible_parties"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="generate-audit-report",
            name="Audit Report Generation",
            description="Generate comprehensive audit report with findings",
            executor="content-lead",
            inputs={
                "requirements": "requirement-gathering.requirements",
                "findings": "system-audit.audit_findings",
                "violations": "violation-detection.violations",
                "remediation": "remediation-recommendations.remediation_steps",
            },
            outputs=["audit_report", "executive_summary", "compliance_scorecard"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-violations",
            name="Review Detected Violations",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="violation-detection",
            prompt="Review detected compliance violations and severity ratings",
            options=["Approve", "Adjust Severity", "Request Additional Investigation"],
        ),
        Checkpoint(
            id="approve-remediation",
            name="Approve Remediation Plan",
            type=CheckpointType.HUMAN_APPROVAL,
            after_step="remediation-recommendations",
            prompt="Review and approve remediation plan and timeline",
            options=["Approve", "Modify Priorities", "Allocate Resources", "Schedule Implementation"],
        ),
    ],
)


# =============================================================================
# WORKFLOW REGISTRY
# =============================================================================

# =============================================================================
# 27. MAJIKS ECOSYSTEM RESEARCH MONITOR (Maj. Recon)
# =============================================================================
# Spec: Research/Majiks-Ecosystem-Research/10-pitch-deck-assets/brigade-monitor-agent-spec.md
# 3-tier hierarchy: Maj. Recon (orchestrator) → 4 Captains (team leads) → 5 shared workers.
# Cap/Court/Stack/Lab scans run in parallel (no inter-dependencies between them);
# the synthesis step depends on all four.

MAJIKS_RESEARCH_MONITOR = WorkflowDefinition(
    id="majiks-research-monitor",
    name="Majiks Ecosystem Research Monitor",
    description=(
        "Maj. Recon orchestrates 4 Captain Team Leads (Cap, Court, Stack, Lab) to refresh "
        "the Majiks AI-music research catalog, populate FalkorDB, and fire tripwire alerts "
        "on material changes. Default monthly cadence; weekly during the Sony v. Suno "
        "summary-judgment window (Dec 2026 – Feb 2027)."
    ),
    version="1.0.0",
    tags=["research", "majiks", "monitoring", "intelligence", "ai-music"],

    orchestrator_model="openai/gpt-4o",
    orchestrator_prompt="""You are Maj. Recon — Major in charge of reconnaissance for the Majiks ecosystem.

Your mission, every cycle:
1. Decide scope. Default: full refresh across all 4 Captain domains. If `inputs.run_mode == "tripwire-check"`, scope only to tripwire rules. If `inputs.run_mode == "domain:X"`, scope only to that one Captain.
2. Dispatch the 4 Captains in parallel (Cap, Court, Stack, Lab). Each scans its domain and returns: new findings, change classifications (cosmetic/material/tripwire), suggested graph upserts, and tripwire candidates.
3. Synthesize the 4 Captain reports into a single diff document for the month — group by domain, highlight tripwires at the top.
4. Decide which tripwires actually fire (Captains nominate; you confirm). Tripwire rules:
   - any new RIAA case docket entry (Cpt. Court)
   - any AI-music funding round announcement >$10M (Cpt. Cap)
   - any new ACE-Step / Suno / Udio version release (Cpt. Stack)
   - any new academic paper matching kids+music OR music+therapy (Cpt. Lab)
   - any cited stat moving >25% in headline-stats.md (any Captain)
5. Emit four artifacts:
   - diff report at Research/Majiks-Ecosystem-Research/00-index/monthly-updates/YYYY-MM.md
   - FalkorDB upserts via majiks-grafwrite (one MonitorRun node per cycle, with provenance edges)
   - tripwire alerts dispatched to Slack + email (only if any fired)
   - regenerated headline-stats.md if any cited stat changed >5%
6. Write a (MonitorRun) node into FalkorDB with the run summary and link it back to every node touched this cycle.

You do NOT modify EXECUTIVE-SUMMARY.md autonomously — flag suggested edits in the diff report for human review.""",

    team_leads=[
        CAPTAIN_CAP_TEAM_LEAD,
        CAPTAIN_COURT_TEAM_LEAD,
        CAPTAIN_STACK_TEAM_LEAD,
        CAPTAIN_LAB_TEAM_LEAD,
    ],

    required_inputs=["run_mode", "as_of_date", "previous_run_summary"],
    final_outputs=[
        "diff_report_path",
        "graph_deltas",
        "tripwires_fired",
        "stat_sheet_changes",
        "monitor_run_id",
    ],

    steps=[
        WorkflowStep(
            id="cap-scan",
            name="Capital & Funding Scan",
            description="Cpt. Cap scans new rounds, ARR moves, market sizing refreshes, analyst report drops",
            executor="captain-cap",
            inputs={
                "run_mode": "inputs.run_mode",
                "as_of_date": "inputs.as_of_date",
                "previous_state": "inputs.previous_run_summary",
            },
            outputs=["funding_findings", "cap_tripwire_candidates", "cap_graph_deltas"],
            timeout_seconds=900,
        ),
        WorkflowStep(
            id="court-scan",
            name="Industry & Litigation Scan",
            description="Cpt. Court scans RIAA dockets, regulatory moves, label-AI deals, settlements",
            executor="captain-court",
            inputs={
                "run_mode": "inputs.run_mode",
                "as_of_date": "inputs.as_of_date",
                "previous_state": "inputs.previous_run_summary",
            },
            outputs=["litigation_findings", "court_tripwire_candidates", "court_graph_deltas"],
            timeout_seconds=900,
        ),
        WorkflowStep(
            id="stack-scan",
            name="Tech & Product Scan",
            description="Cpt. Stack scans Suno/Udio/ACE-Step versions, HF/GitHub trends, competitor launches",
            executor="captain-stack",
            inputs={
                "run_mode": "inputs.run_mode",
                "as_of_date": "inputs.as_of_date",
                "previous_state": "inputs.previous_run_summary",
            },
            outputs=["tech_findings", "stack_tripwire_candidates", "stack_graph_deltas"],
            timeout_seconds=900,
        ),
        WorkflowStep(
            id="lab-scan",
            name="Academic & Clinical Scan",
            description="Cpt. Lab scans new peer-reviewed studies, Cochrane updates, FDA clearances",
            executor="captain-lab",
            inputs={
                "run_mode": "inputs.run_mode",
                "as_of_date": "inputs.as_of_date",
                "previous_state": "inputs.previous_run_summary",
            },
            outputs=["academic_findings", "lab_tripwire_candidates", "lab_graph_deltas"],
            timeout_seconds=900,
        ),
        WorkflowStep(
            id="synthesize",
            name="Synthesize Captain reports + decide tripwires",
            description="Maj. Recon merges all 4 Captain reports into the monthly diff and confirms which tripwires fire",
            executor="orchestrator",
            inputs={
                "cap": "cap-scan.funding_findings",
                "court": "court-scan.litigation_findings",
                "stack": "stack-scan.tech_findings",
                "lab": "lab-scan.academic_findings",
                "cap_tripwires": "cap-scan.cap_tripwire_candidates",
                "court_tripwires": "court-scan.court_tripwire_candidates",
                "stack_tripwires": "stack-scan.stack_tripwire_candidates",
                "lab_tripwires": "lab-scan.lab_tripwire_candidates",
                "as_of_date": "inputs.as_of_date",
            },
            outputs=["diff_report_markdown", "tripwires_fired", "stat_sheet_changes"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="emit-artifacts",
            name="Write artifacts (markdown + FalkorDB + alerts)",
            description="Persist diff report to repo, write graph deltas + MonitorRun node, dispatch alerts if any tripwire fired",
            executor="orchestrator",
            inputs={
                "diff_report_markdown": "synthesize.diff_report_markdown",
                "tripwires_fired": "synthesize.tripwires_fired",
                "stat_sheet_changes": "synthesize.stat_sheet_changes",
                "cap_graph_deltas": "cap-scan.cap_graph_deltas",
                "court_graph_deltas": "court-scan.court_graph_deltas",
                "stack_graph_deltas": "stack-scan.stack_graph_deltas",
                "lab_graph_deltas": "lab-scan.lab_graph_deltas",
                "as_of_date": "inputs.as_of_date",
            },
            outputs=["diff_report_path", "graph_deltas", "monitor_run_id"],
            timeout_seconds=180,
        ),
    ],

    checkpoints=[
        Checkpoint(
            id="review-tripwires",
            name="Review tripwires before alert dispatch",
            type=CheckpointType.REVIEW,
            after_step="synthesize",
            prompt="Review the tripwires Maj. Recon nominated to fire. Confirm Slack/email dispatch.",
        ),
    ],
)


ALL_WORKFLOWS = {
    # Original templates (Jan 2026)
    "investment-due-diligence": INVESTMENT_DUE_DILIGENCE,
    "autonomous-sales-pipeline": AUTONOMOUS_SALES_PIPELINE,
    "incident-response": INCIDENT_RESPONSE,
    "content-production": CONTENT_PRODUCTION,
    "legal-case-analysis": LEGAL_CASE_ANALYSIS,
    "medical-documentation-review": MEDICAL_DOCUMENTATION_REVIEW,
    "competitive-intel": COMPETITIVE_INTELLIGENCE,
    "support-escalation": CUSTOMER_SUPPORT_ESCALATION,
    "tech-docs": TECHNICAL_DOCUMENTATION,
    "risk-assessment": RISK_ASSESSMENT,
    "code-review-pipeline": CODE_REVIEW_PIPELINE,
    "customer-support-resolution": CUSTOMER_SUPPORT_RESOLUTION,
    "competitive-intelligence-report": COMPETITIVE_INTELLIGENCE_REPORT,
    "automated-data-report": AUTOMATED_DATA_REPORT,
    "news-intelligence-briefing": NEWS_INTELLIGENCE_BRIEFING,
    "data-processing-report": DATA_PROCESSING_REPORT,
    "global-content-localization": GLOBAL_CONTENT_LOCALIZATION,
    # Phase 1 Priority Workflows (Jan 31, 2026)
    "help-desk-triage": HELP_DESK_TRIAGE,
    "rfp-response": RFP_RESPONSE_GENERATION,
    # Template Expansion Workflows (Jan 31, 2026)
    "api-integration-automation": API_INTEGRATION_AUTOMATION,
    "contract-analysis": CONTRACT_ANALYSIS,
    "meeting-intelligence": MEETING_INTELLIGENCE,
    "research-literature-review": RESEARCH_LITERATURE_REVIEW,
    "content-distribution": CONTENT_DISTRIBUTION,
    "compliance-audit": COMPLIANCE_AUDIT,
    # Majiks Research Monitor — Maj. Recon (May 2026)
    "majiks-research-monitor": MAJIKS_RESEARCH_MONITOR,
    # Professional workflows (Jan 31, 2026) - 18 high-value professional workflows
    **ALL_PROFESSIONAL_WORKFLOWS,
}


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """Get workflow by ID"""
    return ALL_WORKFLOWS.get(workflow_id)


def list_workflows() -> list:
    """List all available workflows"""
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "tags": w.tags,
            "required_inputs": w.required_inputs,
            "step_count": len(w.steps),
            "checkpoint_count": len(w.checkpoints),
        }
        for w in ALL_WORKFLOWS.values()
    ]


def get_workflows_by_tag(tag: str) -> list:
    """Get workflows by tag"""
    return [w for w in ALL_WORKFLOWS.values() if tag in w.tags]


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Existing workflows
    "INVESTMENT_DUE_DILIGENCE",
    "AUTONOMOUS_SALES_PIPELINE",
    "INCIDENT_RESPONSE",
    "CONTENT_PRODUCTION",
    "LEGAL_CASE_ANALYSIS",
    "MEDICAL_DOCUMENTATION_REVIEW",
    "COMPETITIVE_INTELLIGENCE",
    "CUSTOMER_SUPPORT_ESCALATION",
    "TECHNICAL_DOCUMENTATION",
    "RISK_ASSESSMENT",
    # New workflows (Jan 2026) - Code/Support/Analytics
    "CODE_REVIEW_PIPELINE",
    "CUSTOMER_SUPPORT_RESOLUTION",
    "COMPETITIVE_INTELLIGENCE_REPORT",
    "AUTOMATED_DATA_REPORT",
    # New workflows (Jan 2026) - Business tools integration
    "NEWS_INTELLIGENCE_BRIEFING",
    "DATA_PROCESSING_REPORT",
    "GLOBAL_CONTENT_LOCALIZATION",
    # Phase 1 Priority Workflows (Jan 31, 2026)
    "HELP_DESK_TRIAGE",
    "RFP_RESPONSE_GENERATION",
    # Template Expansion Workflows (Jan 31, 2026)
    "API_INTEGRATION_AUTOMATION",
    "CONTRACT_ANALYSIS",
    "MEETING_INTELLIGENCE",
    "RESEARCH_LITERATURE_REVIEW",
    "CONTENT_DISTRIBUTION",
    "COMPLIANCE_AUDIT",
    # Majiks Research Monitor (May 2026)
    "MAJIKS_RESEARCH_MONITOR",
    # Registry and helpers
    "ALL_WORKFLOWS",
    "get_workflow",
    "list_workflows",
    "get_workflows_by_tag",
]
