"""
Content & Intelligence Professional Workflows

2 high-value workflows for marketing and customer intelligence:
1. Lead Scoring Flow - Automated lead qualification and prioritization
2. Email Auto-Responder - Intelligent email triage and response drafting
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
    FINANCE_TEAM_LEAD,
)


# =============================================================================
# 1. LEAD SCORING FLOW
# =============================================================================

LEAD_SCORE_FLOW = WorkflowDefinition(
    id="lead-scoring-flow",
    name="Lead Scoring & Qualification Flow",
    description="Automated lead research, scoring, qualification, and sales handoff",
    version="1.0.0",
    tags=["sales", "marketing", "lead-generation"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a lead scoring workflow.
Your goal is to research, score, and qualify leads for sales follow-up.
Work with Research and Sales teams to gather intelligence and prioritize leads.""",

    team_leads=[RESEARCH_TEAM_LEAD, SALES_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["lead_info", "lead_source", "scoring_criteria"],
    final_outputs=["lead_score", "qualification_status", "sales_intelligence", "outreach_plan"],

    steps=[
        WorkflowStep(
            id="lead-enrichment",
            name="Enrich Lead Data",
            description="Gather company info, contact details, social profiles, tech stack",
            executor="research-lead",
            inputs={
                "lead": "inputs.lead_info",
                "source": "inputs.lead_source",
            },
            outputs=["company_profile", "contact_details", "social_profiles", "tech_stack"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="company-research",
            name="Research Company",
            description="Analyze company size, revenue, funding, growth signals, decision makers",
            executor="research-lead",
            inputs={
                "company": "lead-enrichment.company_profile",
            },
            outputs=["company_size", "revenue_estimate", "funding_info", "growth_signals", "decision_makers"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="intent-analysis",
            name="Analyze Buyer Intent",
            description="Assess engagement level, content consumption, product interest signals",
            executor="sales-lead",
            inputs={
                "lead": "inputs.lead_info",
                "source": "inputs.lead_source",
                "company": "company-research.company_size",
            },
            outputs=["engagement_score", "content_interests", "intent_signals", "buying_stage"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="fit-scoring",
            name="Calculate Fit Score",
            description="Score lead against ICP criteria: industry, size, budget, authority",
            executor="sales-lead",
            inputs={
                "company": "company-research.company_profile",
                "revenue": "company-research.revenue_estimate",
                "decision_makers": "company-research.decision_makers",
                "criteria": "inputs.scoring_criteria",
            },
            outputs=["fit_score", "icp_match", "fit_justification"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="budget-qualification",
            name="Qualify Budget",
            description="Estimate budget potential based on company size, revenue, tech spend",
            executor="finance-lead",
            inputs={
                "company": "company-research.company_profile",
                "revenue": "company-research.revenue_estimate",
                "funding": "company-research.funding_info",
            },
            outputs=["budget_estimate", "deal_size_potential", "budget_authority"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="composite-score",
            name="Calculate Composite Lead Score",
            description="Combine fit, intent, and budget scores into final lead score",
            executor="orchestrator",
            inputs={
                "fit_score": "fit-scoring.fit_score",
                "intent_score": "intent-analysis.engagement_score",
                "budget": "budget-qualification.budget_estimate",
            },
            outputs=["final_score", "score_breakdown", "priority_tier"],
            timeout_seconds=30,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review lead score. High-value lead detected - fast-track to sales or continue nurturing?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="sales-intelligence",
            name="Compile Sales Intelligence",
            description="Create comprehensive lead profile with talking points and objection handling",
            executor="content-lead",
            inputs={
                "company": "company-research.company_profile",
                "decision_makers": "company-research.decision_makers",
                "intent": "intent-analysis.intent_signals",
                "score": "composite-score.final_score",
            },
            outputs=["sales_brief", "talking_points", "objection_handling", "competitive_intel"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="outreach-plan",
            name="Create Outreach Plan",
            description="Design personalized outreach strategy with messaging, timing, channel",
            executor="sales-lead",
            inputs={
                "lead": "lead-enrichment.contact_details",
                "company": "company-research.company_profile",
                "intent": "intent-analysis.buying_stage",
                "score": "composite-score.priority_tier",
            },
            outputs=["outreach_strategy", "email_templates", "call_script", "follow_up_sequence"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Lead qualification complete. Approve for sales handoff?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 2. EMAIL AUTO-RESPONDER
# =============================================================================

EMAIL_AUTO_RESPONDER = WorkflowDefinition(
    id="email-auto-responder",
    name="Email Auto-Responder Workflow",
    description="Intelligent email triage, categorization, and automated response drafting",
    version="1.0.0",
    tags=["customer-support", "automation", "communication"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an email auto-response workflow.
Your goal is to triage, categorize, and draft appropriate responses to incoming emails.
Work with Research and Content teams to gather context and create quality responses.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD, SALES_TEAM_LEAD],

    required_inputs=["email_content", "sender_info", "email_subject"],
    final_outputs=["email_category", "urgency_level", "draft_response", "routing_recommendation"],

    steps=[
        WorkflowStep(
            id="email-classification",
            name="Classify Email",
            description="Categorize email type: support, sales, inquiry, complaint, spam, etc.",
            executor="content-lead",
            inputs={
                "email": "inputs.email_content",
                "subject": "inputs.email_subject",
            },
            outputs=["email_type", "primary_topic", "sub_categories"],
            timeout_seconds=30,
        ),
        WorkflowStep(
            id="urgency-assessment",
            name="Assess Urgency",
            description="Determine urgency level and SLA based on content and sender",
            executor="content-lead",
            inputs={
                "email": "inputs.email_content",
                "type": "email-classification.email_type",
                "sender": "inputs.sender_info",
            },
            outputs=["urgency_level", "sla_deadline", "escalation_needed"],
            timeout_seconds=30,
        ),
        WorkflowStep(
            id="sender-research",
            name="Research Sender",
            description="Look up sender history, past interactions, account status, sentiment",
            executor="research-lead",
            inputs={
                "sender": "inputs.sender_info",
            },
            outputs=["sender_history", "past_interactions", "account_status", "relationship_health"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="intent-extraction",
            name="Extract Intent & Entities",
            description="Identify what sender wants: question, request, complaint, feedback",
            executor="content-lead",
            inputs={
                "email": "inputs.email_content",
                "type": "email-classification.email_type",
            },
            outputs=["sender_intent", "key_entities", "questions_asked", "sentiment"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="knowledge-lookup",
            name="Search Knowledge Base",
            description="Find relevant help articles, FAQs, past responses, solutions",
            executor="research-lead",
            inputs={
                "intent": "intent-extraction.sender_intent",
                "topic": "email-classification.primary_topic",
                "questions": "intent-extraction.questions_asked",
            },
            outputs=["relevant_articles", "suggested_solutions", "similar_cases"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="routing-decision",
            name="Determine Routing",
            description="Decide if auto-response is appropriate or needs human routing",
            executor="orchestrator",
            inputs={
                "urgency": "urgency-assessment.urgency_level",
                "type": "email-classification.email_type",
                "sender": "sender-research.relationship_health",
                "knowledge": "knowledge-lookup.relevant_articles",
            },
            outputs=["routing_decision", "assigned_team", "escalation_path"],
            timeout_seconds=30,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="High-value customer or urgent issue detected. Route to human or send auto-response?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="response-drafting",
            name="Draft Response",
            description="Generate personalized, empathetic response addressing sender's needs",
            executor="content-lead",
            inputs={
                "email": "inputs.email_content",
                "sender": "sender-research.sender_history",
                "intent": "intent-extraction.sender_intent",
                "knowledge": "knowledge-lookup.suggested_solutions",
                "sentiment": "intent-extraction.sentiment",
            },
            outputs=["draft_response", "tone_applied", "next_steps_included"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="response-enhancement",
            name="Enhance Response",
            description="Add personalization, relevant links, signature, call-to-action",
            executor="content-lead",
            inputs={
                "draft": "response-drafting.draft_response",
                "sender": "sender-research.sender_history",
                "articles": "knowledge-lookup.relevant_articles",
                "type": "email-classification.email_type",
            },
            outputs=["final_response", "personalization_added", "resources_linked"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="quality-check",
            name="Quality Check Response",
            description="Verify response addresses all questions, appropriate tone, no errors",
            executor="orchestrator",
            inputs={
                "email": "inputs.email_content",
                "response": "response-enhancement.final_response",
                "intent": "intent-extraction.sender_intent",
            },
            outputs=["quality_score", "issues_found", "send_recommendation"],
            timeout_seconds=30,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Draft response ready. Review and approve before sending?",
            required_approval=False,
        )
    ],
)


# Aggregate all Content & Intelligence workflows
ALL_CONTENT_INTEL_WORKFLOWS = {
    "lead-scoring-flow": LEAD_SCORE_FLOW,
    "email-auto-responder": EMAIL_AUTO_RESPONDER,
}

__all__ = [
    "LEAD_SCORE_FLOW",
    "EMAIL_AUTO_RESPONDER",
    "ALL_CONTENT_INTEL_WORKFLOWS",
]
