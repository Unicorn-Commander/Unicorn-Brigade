"""
HR & Sales Professional Workflows

4 high-value workflows for HR and sales professionals:
1. Recruiting Pipeline - End-to-end candidate sourcing, screening, and hiring
2. RFP Proposal Response - Automated RFP response generation
3. Vendor Risk Assessment - Third-party vendor due diligence
4. Employee Onboarding - Comprehensive new hire onboarding automation
"""

from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
)
from app.workflows.team_leads import (
    RESEARCH_TEAM_LEAD,
    SALES_TEAM_LEAD,
    CONTENT_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    FINANCE_TEAM_LEAD,
    DEVOPS_TEAM_LEAD,
)


# =============================================================================
# 1. RECRUITING PIPELINE
# =============================================================================

RECRUITING_PIPELINE = WorkflowDefinition(
    id="recruiting-pipeline",
    name="Recruiting Pipeline Automation",
    description="End-to-end recruiting workflow from job posting to offer letter",
    version="1.0.0",
    tags=["hr", "recruiting", "talent-acquisition"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a recruiting workflow.
Your goal is to efficiently source, screen, and hire the best candidate.
Work with Research and Content teams to find qualified candidates and create compelling materials.""",

    team_leads=[RESEARCH_TEAM_LEAD, SALES_TEAM_LEAD, CONTENT_TEAM_LEAD, LEGAL_TEAM_LEAD],

    required_inputs=["job_title", "job_description", "required_skills", "location", "salary_range"],
    final_outputs=["candidate_shortlist", "interview_guides", "offer_letter", "hiring_recommendation"],

    steps=[
        WorkflowStep(
            id="job-posting",
            name="Create Job Posting",
            description="Draft compelling job description with requirements, benefits, and company culture",
            executor="content-lead",
            inputs={
                "title": "inputs.job_title",
                "description": "inputs.job_description",
                "skills": "inputs.required_skills",
                "location": "inputs.location",
            },
            outputs=["job_posting", "posting_strategy", "target_platforms"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="candidate-sourcing",
            name="Source Candidates",
            description="Search LinkedIn, job boards, and databases for qualified candidates",
            executor="research-lead",
            inputs={
                "job_title": "inputs.job_title",
                "skills": "inputs.required_skills",
                "location": "inputs.location",
            },
            outputs=["candidate_list", "sourcing_channels", "passive_candidates"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="resume-screening",
            name="Screen Resumes",
            description="Evaluate resumes against requirements, rank candidates, identify red flags",
            executor="sales-lead",
            inputs={
                "candidates": "candidate-sourcing.candidate_list",
                "requirements": "inputs.required_skills",
                "job_desc": "job-posting.job_posting",
            },
            outputs=["screened_candidates", "match_scores", "screening_notes"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review top candidates. Approve shortlist for interviews?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="interview-prep",
            name="Prepare Interview Materials",
            description="Create interview guides, technical assessments, and evaluation rubrics",
            executor="content-lead",
            inputs={
                "job_title": "inputs.job_title",
                "skills": "inputs.required_skills",
                "top_candidates": "resume-screening.screened_candidates",
            },
            outputs=["interview_guide", "technical_assessment", "evaluation_rubric"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="offer-prep",
            name="Prepare Offer Package",
            description="Draft offer letter, benefits summary, and employment agreement",
            executor="legal-lead",
            inputs={
                "job_title": "inputs.job_title",
                "salary_range": "inputs.salary_range",
                "location": "inputs.location",
            },
            outputs=["offer_letter_template", "benefits_summary", "employment_agreement"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="hiring-recommendation",
            name="Generate Hiring Recommendation",
            description="Synthesize all findings into hiring recommendation with candidate comparison",
            executor="orchestrator",
            inputs={
                "candidates": "resume-screening.screened_candidates",
                "match_scores": "resume-screening.match_scores",
                "interview_guide": "interview-prep.interview_guide",
                "salary_range": "inputs.salary_range",
            },
            outputs=["hiring_recommendation", "candidate_comparison", "next_steps"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Recruiting materials ready. Approve to proceed with candidate outreach?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 2. RFP PROPOSAL RESPONSE
# =============================================================================

RFP_PROPOSAL_RESPONSE = WorkflowDefinition(
    id="rfp-proposal-response",
    name="RFP Proposal Response Generator",
    description="Automated RFP response with compliance matrix, pricing, and executive summary",
    version="1.0.0",
    tags=["sales", "rfp", "proposal"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an RFP response workflow.
Your goal is to create a winning, compliant proposal that addresses all requirements.
Work with Research, Content, and Sales teams to craft a compelling response.""",

    team_leads=[RESEARCH_TEAM_LEAD, SALES_TEAM_LEAD, CONTENT_TEAM_LEAD, FINANCE_TEAM_LEAD],

    required_inputs=["rfp_document", "client_name", "deadline", "our_capabilities"],
    final_outputs=["proposal_document", "compliance_matrix", "pricing_sheet", "executive_summary"],

    steps=[
        WorkflowStep(
            id="rfp-analysis",
            name="Analyze RFP Requirements",
            description="Extract all requirements, evaluation criteria, submission guidelines, and deadlines",
            executor="research-lead",
            inputs={
                "rfp": "inputs.rfp_document",
                "client": "inputs.client_name",
            },
            outputs=["requirements_list", "evaluation_criteria", "submission_requirements", "key_dates"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="client-research",
            name="Research Client Organization",
            description="Research client's business, pain points, strategic priorities, past vendors",
            executor="research-lead",
            inputs={
                "client": "inputs.client_name",
            },
            outputs=["client_profile", "pain_points", "strategic_priorities", "competitive_intel"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="compliance-matrix",
            name="Create Compliance Matrix",
            description="Map our capabilities to each RFP requirement, identify gaps",
            executor="sales-lead",
            inputs={
                "requirements": "rfp-analysis.requirements_list",
                "capabilities": "inputs.our_capabilities",
            },
            outputs=["compliance_matrix", "capability_gaps", "win_themes"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review compliance matrix and gaps. Proceed with proposal (bid) or decline (no-bid)?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="pricing-strategy",
            name="Develop Pricing Strategy",
            description="Create competitive pricing based on scope, competition, and client budget",
            executor="finance-lead",
            inputs={
                "requirements": "rfp-analysis.requirements_list",
                "client": "client-research.client_profile",
                "competition": "client-research.competitive_intel",
            },
            outputs=["pricing_strategy", "cost_breakdown", "pricing_justification"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="proposal-drafting",
            name="Draft Proposal Document",
            description="Write comprehensive proposal with technical approach, team, timeline",
            executor="content-lead",
            inputs={
                "requirements": "rfp-analysis.requirements_list",
                "compliance": "compliance-matrix.compliance_matrix",
                "win_themes": "compliance-matrix.win_themes",
                "client_insights": "client-research.pain_points",
                "pricing": "pricing-strategy.cost_breakdown",
            },
            outputs=["proposal_draft", "technical_approach", "team_bios", "timeline"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="executive-summary",
            name="Write Executive Summary",
            description="Create compelling 1-2 page executive summary highlighting key differentiators",
            executor="content-lead",
            inputs={
                "client": "client-research.client_profile",
                "win_themes": "compliance-matrix.win_themes",
                "proposal": "proposal-drafting.proposal_draft",
            },
            outputs=["executive_summary", "value_proposition", "call_to_action"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="RFP response complete. Final review before submission?",
            required_approval=True,
        )
    ],
)


# =============================================================================
# 3. VENDOR RISK ASSESSMENT
# =============================================================================

VENDOR_RISK_ASSESSMENT = WorkflowDefinition(
    id="vendor-risk-assessment",
    name="Vendor Risk Assessment Workflow",
    description="Comprehensive third-party vendor due diligence and risk evaluation",
    version="1.0.0",
    tags=["risk-management", "vendor-management", "compliance"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a vendor risk assessment workflow.
Your goal is to evaluate the vendor's financial stability, security posture, and compliance.
Work with Research, Finance, and Legal teams to produce a risk rating and recommendation.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, DEVOPS_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["vendor_name", "service_type", "data_access_level", "contract_value"],
    final_outputs=["risk_rating", "risk_report", "security_assessment", "recommendation"],

    steps=[
        WorkflowStep(
            id="vendor-background",
            name="Vendor Background Research",
            description="Research vendor company info, leadership, ownership, market reputation",
            executor="research-lead",
            inputs={
                "vendor": "inputs.vendor_name",
                "service": "inputs.service_type",
            },
            outputs=["company_profile", "leadership_team", "ownership_structure", "market_reputation"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="financial-health",
            name="Assess Financial Health",
            description="Evaluate vendor financial stability, revenue trends, funding, bankruptcy risk",
            executor="finance-lead",
            inputs={
                "vendor": "inputs.vendor_name",
                "contract_value": "inputs.contract_value",
            },
            outputs=["financial_assessment", "bankruptcy_risk", "continuity_risk"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="security-assessment",
            name="Security & Privacy Assessment",
            description="Evaluate security certifications, data handling, incident history, compliance",
            executor="devops-lead",
            inputs={
                "vendor": "inputs.vendor_name",
                "data_access": "inputs.data_access_level",
            },
            outputs=["security_posture", "certifications", "incident_history", "data_practices"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="legal-compliance",
            name="Legal & Compliance Review",
            description="Review contracts, SLAs, liability terms, regulatory compliance",
            executor="legal-lead",
            inputs={
                "vendor": "inputs.vendor_name",
                "service": "inputs.service_type",
            },
            outputs=["contract_analysis", "sla_review", "liability_assessment", "compliance_status"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="risk-scoring",
            name="Calculate Risk Score",
            description="Synthesize all findings into quantitative risk score and rating",
            executor="orchestrator",
            inputs={
                "financial": "financial-health.financial_assessment",
                "security": "security-assessment.security_posture",
                "legal": "legal-compliance.liability_assessment",
                "data_access": "inputs.data_access_level",
                "contract_value": "inputs.contract_value",
            },
            outputs=["risk_score", "risk_rating", "critical_risks"],
            timeout_seconds=90,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review risk score and critical risks. Approve vendor or require mitigation?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="risk-report",
            name="Generate Risk Report",
            description="Create comprehensive vendor risk report with recommendation",
            executor="content-lead",
            inputs={
                "vendor": "vendor-background.company_profile",
                "risk_score": "risk-scoring.risk_score",
                "financial": "financial-health.financial_assessment",
                "security": "security-assessment.security_posture",
                "legal": "legal-compliance.contract_analysis",
            },
            outputs=["risk_report", "executive_summary", "recommendation", "mitigation_plan"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Vendor risk assessment complete. Approve recommendation?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 4. EMPLOYEE ONBOARDING
# =============================================================================

EMPLOYEE_ONBOARDING = WorkflowDefinition(
    id="employee-onboarding",
    name="Employee Onboarding Automation",
    description="Comprehensive new hire onboarding from offer acceptance to first day productivity",
    version="1.0.0",
    tags=["hr", "onboarding", "employee-experience"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an employee onboarding workflow.
Your goal is to create a seamless onboarding experience for the new hire.
Work with Content, Legal, and DevOps teams to prepare all materials and systems access.""",

    team_leads=[CONTENT_TEAM_LEAD, LEGAL_TEAM_LEAD, DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD],

    required_inputs=["employee_name", "job_title", "department", "start_date", "manager_name"],
    final_outputs=["onboarding_plan", "welcome_package", "training_schedule", "it_provisioning"],

    steps=[
        WorkflowStep(
            id="documentation-prep",
            name="Prepare Employment Documentation",
            description="Generate offer letter, I-9, W-4, benefits enrollment, NDA, employee handbook",
            executor="legal-lead",
            inputs={
                "employee": "inputs.employee_name",
                "title": "inputs.job_title",
                "start_date": "inputs.start_date",
            },
            outputs=["offer_letter", "tax_forms", "benefits_forms", "legal_docs"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="it-provisioning",
            name="IT Systems Provisioning",
            description="Create accounts, email, laptop order, software licenses, access permissions",
            executor="devops-lead",
            inputs={
                "employee": "inputs.employee_name",
                "title": "inputs.job_title",
                "department": "inputs.department",
                "start_date": "inputs.start_date",
            },
            outputs=["user_accounts", "equipment_order", "software_licenses", "access_permissions"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="training-plan",
            name="Create Training Plan",
            description="Design role-specific training curriculum, schedule, milestones for first 90 days",
            executor="content-lead",
            inputs={
                "title": "inputs.job_title",
                "department": "inputs.department",
                "manager": "inputs.manager_name",
            },
            outputs=["training_curriculum", "learning_schedule", "90day_milestones"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="team-prep",
            name="Prepare Team & Workspace",
            description="Notify team, schedule introductions, prepare workspace, order supplies",
            executor="content-lead",
            inputs={
                "employee": "inputs.employee_name",
                "title": "inputs.job_title",
                "department": "inputs.department",
                "start_date": "inputs.start_date",
                "manager": "inputs.manager_name",
            },
            outputs=["team_announcement", "intro_schedule", "workspace_setup", "supply_order"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="role-research",
            name="Research Role & Projects",
            description="Gather info on current projects, team dynamics, key stakeholders, goals",
            executor="research-lead",
            inputs={
                "title": "inputs.job_title",
                "department": "inputs.department",
            },
            outputs=["current_projects", "team_structure", "key_stakeholders", "department_goals"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="welcome-package",
            name="Create Welcome Package",
            description="Compile welcome email, first day agenda, company swag, onboarding portal access",
            executor="content-lead",
            inputs={
                "employee": "inputs.employee_name",
                "title": "inputs.job_title",
                "start_date": "inputs.start_date",
                "training": "training-plan.training_curriculum",
                "team": "team-prep.team_announcement",
                "projects": "role-research.current_projects",
            },
            outputs=["welcome_email", "first_day_agenda", "onboarding_portal", "swag_package"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="onboarding-checklist",
            name="Generate Onboarding Checklist",
            description="Create comprehensive checklist for HR, manager, and employee",
            executor="orchestrator",
            inputs={
                "docs": "documentation-prep.legal_docs",
                "it": "it-provisioning.user_accounts",
                "training": "training-plan.training_curriculum",
                "welcome": "welcome-package.welcome_email",
            },
            outputs=["hr_checklist", "manager_checklist", "employee_checklist", "timeline"],
            timeout_seconds=60,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Onboarding plan ready. Review before employee start date?",
            required_approval=False,
        )
    ],
)


# Aggregate all HR & Sales workflows
ALL_HR_SALES_WORKFLOWS = {
    "recruiting-pipeline": RECRUITING_PIPELINE,
    "rfp-proposal-response": RFP_PROPOSAL_RESPONSE,
    "vendor-risk-assessment": VENDOR_RISK_ASSESSMENT,
    "employee-onboarding": EMPLOYEE_ONBOARDING,
}

__all__ = [
    "RECRUITING_PIPELINE",
    "RFP_PROPOSAL_RESPONSE",
    "VENDOR_RISK_ASSESSMENT",
    "EMPLOYEE_ONBOARDING",
    "ALL_HR_SALES_WORKFLOWS",
]
