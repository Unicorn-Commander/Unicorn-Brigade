"""
Domain-Specific Professional Workflows

4 specialized workflows for specific professional domains:
1. Real Estate Transaction - Property due diligence and transaction coordination
2. Product Research Assistant - Competitive product analysis and market research
3. Patent Analysis Pipeline - Patent search, analysis, and IP landscape mapping
4. Meeting Assistant - Meeting prep, note-taking, and action item tracking
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
    INVESTIGATION_TEAM_LEAD,
)


# =============================================================================
# 1. REAL ESTATE TRANSACTION
# =============================================================================

REAL_ESTATE_TRANSACTION = WorkflowDefinition(
    id="real-estate-transaction",
    name="Real Estate Transaction Assistant",
    description="Comprehensive property due diligence, market analysis, and transaction coordination",
    version="1.0.0",
    tags=["real-estate", "property", "investment"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a real estate transaction workflow.
Your goal is to perform thorough property due diligence and coordinate the transaction.
Work with Research, Finance, and Legal teams to evaluate the property investment.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, LEGAL_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["property_address", "asking_price", "property_type", "intended_use"],
    final_outputs=["property_analysis", "financial_projection", "legal_review", "investment_recommendation"],

    steps=[
        WorkflowStep(
            id="property-research",
            name="Research Property",
            description="Gather property details, history, tax records, neighborhood data",
            executor="research-lead",
            inputs={
                "address": "inputs.property_address",
                "type": "inputs.property_type",
            },
            outputs=["property_details", "ownership_history", "tax_records", "neighborhood_profile"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="market-analysis",
            name="Market Analysis",
            description="Analyze comparable sales, market trends, appreciation potential",
            executor="research-lead",
            inputs={
                "address": "inputs.property_address",
                "property_type": "inputs.property_type",
            },
            outputs=["comparable_sales", "market_trends", "appreciation_forecast", "market_value"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="financial-analysis",
            name="Financial Analysis",
            description="Calculate cash flow, ROI, cap rate, financing scenarios",
            executor="finance-lead",
            inputs={
                "property": "property-research.property_details",
                "asking_price": "inputs.asking_price",
                "market_value": "market-analysis.market_value",
                "intended_use": "inputs.intended_use",
            },
            outputs=["cash_flow_projection", "roi_analysis", "financing_scenarios", "break_even_analysis"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="legal-review",
            name="Legal Due Diligence",
            description="Review title, liens, zoning, permits, HOA, environmental issues",
            executor="legal-lead",
            inputs={
                "address": "inputs.property_address",
                "property": "property-research.property_details",
                "intended_use": "inputs.intended_use",
            },
            outputs=["title_review", "lien_search", "zoning_analysis", "permit_status", "legal_risks"],
            timeout_seconds=180,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review legal findings. Title issues or liens detected - proceed or negotiate?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="inspection-planning",
            name="Plan Property Inspection",
            description="Create inspection checklist for structural, mechanical, environmental issues",
            executor="content-lead",
            inputs={
                "property": "property-research.property_details",
                "type": "inputs.property_type",
            },
            outputs=["inspection_checklist", "recommended_inspectors", "inspection_priorities"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="negotiation-strategy",
            name="Develop Negotiation Strategy",
            description="Create offer strategy based on market data, comps, and legal findings",
            executor="orchestrator",
            inputs={
                "asking_price": "inputs.asking_price",
                "market_value": "market-analysis.market_value",
                "legal_risks": "legal-review.legal_risks",
                "financials": "financial-analysis.roi_analysis",
            },
            outputs=["offer_recommendation", "negotiation_points", "contingencies"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="transaction-report",
            name="Generate Transaction Report",
            description="Create comprehensive property investment report with recommendation",
            executor="content-lead",
            inputs={
                "property": "property-research.property_details",
                "market": "market-analysis.comparable_sales",
                "financials": "financial-analysis.cash_flow_projection",
                "legal": "legal-review.title_review",
                "offer": "negotiation-strategy.offer_recommendation",
            },
            outputs=["investment_report", "executive_summary", "recommendation", "risk_factors"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Real estate analysis complete. Approve offer strategy?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 2. PRODUCT RESEARCH ASSISTANT
# =============================================================================

PRODUCT_RESEARCH = WorkflowDefinition(
    id="product-research-assistant",
    name="Product Research Assistant",
    description="Competitive product analysis, feature comparison, and market positioning research",
    version="1.0.0",
    tags=["product-management", "market-research", "competitive-analysis"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a product research workflow.
Your goal is to analyze competitive products and identify market opportunities.
Work with Research and Content teams to gather intelligence and create reports.""",

    team_leads=[RESEARCH_TEAM_LEAD, FINANCE_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["product_category", "target_market", "research_objective"],
    final_outputs=["competitive_analysis", "feature_matrix", "market_gaps", "product_recommendations"],

    steps=[
        WorkflowStep(
            id="market-landscape",
            name="Map Market Landscape",
            description="Identify all competitors, market segments, key players, market size",
            executor="research-lead",
            inputs={
                "category": "inputs.product_category",
                "market": "inputs.target_market",
            },
            outputs=["competitor_list", "market_segments", "market_size", "growth_trends"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="competitor-profiling",
            name="Profile Competitors",
            description="Research each competitor's products, pricing, positioning, strengths/weaknesses",
            executor="research-lead",
            inputs={
                "competitors": "market-landscape.competitor_list",
                "category": "inputs.product_category",
            },
            outputs=["competitor_profiles", "pricing_analysis", "positioning_map", "swot_analysis"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="feature-extraction",
            name="Extract Product Features",
            description="Catalog all features, capabilities, integrations across competitive products",
            executor="research-lead",
            inputs={
                "competitors": "competitor-profiling.competitor_profiles",
            },
            outputs=["feature_catalog", "capability_matrix", "integration_map"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="customer-analysis",
            name="Analyze Customer Feedback",
            description="Gather and analyze reviews, ratings, complaints, feature requests",
            executor="research-lead",
            inputs={
                "competitors": "competitor-profiling.competitor_profiles",
            },
            outputs=["review_analysis", "customer_pain_points", "feature_requests", "satisfaction_scores"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="pricing-strategy",
            name="Analyze Pricing Models",
            description="Compare pricing tiers, packaging, discounts, ROI positioning",
            executor="finance-lead",
            inputs={
                "competitors": "competitor-profiling.competitor_profiles",
                "pricing": "competitor-profiling.pricing_analysis",
            },
            outputs=["pricing_models", "value_comparison", "pricing_trends"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="gap-analysis",
            name="Identify Market Gaps",
            description="Find underserved needs, missing features, white space opportunities",
            executor="orchestrator",
            inputs={
                "features": "feature-extraction.feature_catalog",
                "pain_points": "customer-analysis.customer_pain_points",
                "requests": "customer-analysis.feature_requests",
                "positioning": "competitor-profiling.positioning_map",
            },
            outputs=["market_gaps", "unmet_needs", "opportunities", "differentiation_angles"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review identified market gaps and opportunities. Proceed with recommendations?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="research-report",
            name="Generate Research Report",
            description="Create comprehensive product research report with recommendations",
            executor="content-lead",
            inputs={
                "landscape": "market-landscape.market_segments",
                "competitors": "competitor-profiling.competitor_profiles",
                "features": "feature-extraction.capability_matrix",
                "customers": "customer-analysis.review_analysis",
                "gaps": "gap-analysis.market_gaps",
            },
            outputs=["research_report", "feature_matrix", "recommendations", "executive_summary"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Product research complete. Review findings and recommendations?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 3. PATENT ANALYSIS PIPELINE
# =============================================================================

PATENT_ANALYSIS = WorkflowDefinition(
    id="patent-analysis-pipeline",
    name="Patent Analysis Pipeline",
    description="Patent search, prior art analysis, and IP landscape mapping",
    version="1.0.0",
    tags=["legal", "ip", "patents", "research"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a patent analysis workflow.
Your goal is to search for relevant patents, analyze prior art, and map the IP landscape.
Work with Research and Legal teams to conduct thorough patent analysis.""",

    team_leads=[RESEARCH_TEAM_LEAD, LEGAL_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["invention_description", "technology_domain", "geographic_scope"],
    final_outputs=["patent_search_results", "prior_art_analysis", "ip_landscape", "patentability_assessment"],

    steps=[
        WorkflowStep(
            id="patent-search",
            name="Conduct Patent Search",
            description="Search USPTO, EPO, WIPO databases for relevant patents and applications",
            executor="research-lead",
            inputs={
                "invention": "inputs.invention_description",
                "domain": "inputs.technology_domain",
                "scope": "inputs.geographic_scope",
            },
            outputs=["patent_results", "application_results", "search_strategy", "result_count"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="relevance-ranking",
            name="Rank by Relevance",
            description="Score and rank patents by technical similarity, claim overlap, citation impact",
            executor="research-lead",
            inputs={
                "results": "patent-search.patent_results",
                "invention": "inputs.invention_description",
            },
            outputs=["ranked_patents", "relevance_scores", "top_matches"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="claim-analysis",
            name="Analyze Patent Claims",
            description="Extract and analyze claims from top patents, identify blocking claims",
            executor="legal-lead",
            inputs={
                "top_patents": "relevance-ranking.top_matches",
                "invention": "inputs.invention_description",
            },
            outputs=["claim_analysis", "blocking_claims", "design_around_opportunities"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="citation-network",
            name="Map Citation Network",
            description="Analyze forward/backward citations, identify foundational patents, trends",
            executor="research-lead",
            inputs={
                "patents": "relevance-ranking.ranked_patents",
            },
            outputs=["citation_graph", "foundational_patents", "emerging_trends"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="competitive-landscape",
            name="Map Competitive IP Landscape",
            description="Identify patent holders, assignees, filing trends, geographic coverage",
            executor="research-lead",
            inputs={
                "patents": "patent-search.patent_results",
                "domain": "inputs.technology_domain",
            },
            outputs=["assignee_analysis", "filing_trends", "geographic_coverage", "competitor_strategies"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="prior-art-assessment",
            name="Prior Art Assessment",
            description="Evaluate novelty, identify closest prior art, assess patentability",
            executor="legal-lead",
            inputs={
                "invention": "inputs.invention_description",
                "top_patents": "relevance-ranking.top_matches",
                "claims": "claim-analysis.blocking_claims",
            },
            outputs=["novelty_assessment", "closest_prior_art", "patentability_opinion"],
            timeout_seconds=150,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Prior art assessment complete. Blocking patents found - proceed with filing strategy or design around?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="patent-report",
            name="Generate Patent Analysis Report",
            description="Create comprehensive IP report with landscape map and recommendations",
            executor="content-lead",
            inputs={
                "search_results": "patent-search.patent_results",
                "claims": "claim-analysis.claim_analysis",
                "citations": "citation-network.citation_graph",
                "landscape": "competitive-landscape.assignee_analysis",
                "patentability": "prior-art-assessment.patentability_opinion",
            },
            outputs=["patent_report", "ip_landscape_map", "filing_recommendations", "risk_analysis"],
            timeout_seconds=150,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Patent analysis complete. Review report and filing recommendations?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 4. MEETING ASSISTANT
# =============================================================================

MEETING_ASSISTANT = WorkflowDefinition(
    id="meeting-assistant",
    name="Meeting Assistant Workflow",
    description="Automated meeting prep, agenda creation, note-taking, and action item tracking",
    version="1.0.0",
    tags=["productivity", "meetings", "collaboration"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a meeting assistance workflow.
Your goal is to prepare for the meeting, capture notes, and track action items.
Work with Research and Content teams to gather context and create materials.""",

    team_leads=[RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["meeting_title", "meeting_type", "participants", "meeting_objective"],
    final_outputs=["meeting_agenda", "briefing_materials", "meeting_notes", "action_items"],

    steps=[
        WorkflowStep(
            id="participant-research",
            name="Research Participants",
            description="Gather background on attendees, roles, recent activity, interests",
            executor="research-lead",
            inputs={
                "participants": "inputs.participants",
            },
            outputs=["participant_profiles", "org_chart", "recent_activity"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="context-gathering",
            name="Gather Meeting Context",
            description="Research relevant projects, past decisions, related meetings, dependencies",
            executor="research-lead",
            inputs={
                "title": "inputs.meeting_title",
                "objective": "inputs.meeting_objective",
                "participants": "inputs.participants",
            },
            outputs=["project_context", "past_decisions", "related_meetings", "open_questions"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="agenda-creation",
            name="Create Meeting Agenda",
            description="Draft structured agenda with topics, time allocation, discussion questions",
            executor="content-lead",
            inputs={
                "title": "inputs.meeting_title",
                "objective": "inputs.meeting_objective",
                "context": "context-gathering.project_context",
                "questions": "context-gathering.open_questions",
            },
            outputs=["agenda", "discussion_topics", "time_allocation", "discussion_questions"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="briefing-materials",
            name="Prepare Briefing Materials",
            description="Create pre-read materials, data summaries, decision frameworks",
            executor="content-lead",
            inputs={
                "agenda": "agenda-creation.agenda",
                "context": "context-gathering.project_context",
                "participants": "participant-research.participant_profiles",
            },
            outputs=["pre_read_doc", "data_summary", "decision_framework"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Meeting prep complete. Review agenda and briefing materials before sending?",
                    required_approval=True,
                )
            ],
        ),
        # Note: The following steps would be executed AFTER the meeting
        WorkflowStep(
            id="note-structuring",
            name="Structure Meeting Notes",
            description="Organize raw notes into structured format with sections",
            executor="content-lead",
            inputs={
                "agenda": "agenda-creation.agenda",
                "meeting_type": "inputs.meeting_type",
            },
            outputs=["notes_template", "section_headers"],
            timeout_seconds=30,
        ),
        WorkflowStep(
            id="action-extraction",
            name="Extract Action Items",
            description="Identify action items, assign owners, set deadlines, track status",
            executor="content-lead",
            inputs={
                "notes_template": "note-structuring.notes_template",
                "participants": "inputs.participants",
            },
            outputs=["action_items", "owners", "deadlines", "tracking_list"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="meeting-summary",
            name="Generate Meeting Summary",
            description="Create concise meeting summary with decisions, action items, next steps",
            executor="content-lead",
            inputs={
                "title": "inputs.meeting_title",
                "agenda": "agenda-creation.agenda",
                "notes": "note-structuring.notes_template",
                "actions": "action-extraction.action_items",
            },
            outputs=["meeting_summary", "decisions_made", "next_steps", "follow_up_email"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Meeting summary ready. Review and approve before distribution?",
            required_approval=False,
        )
    ],
)


# Aggregate all domain-specific workflows
ALL_DOMAIN_SPECIFIC_WORKFLOWS = {
    "real-estate-transaction": REAL_ESTATE_TRANSACTION,
    "product-research-assistant": PRODUCT_RESEARCH,
    "patent-analysis-pipeline": PATENT_ANALYSIS,
    "meeting-assistant": MEETING_ASSISTANT,
}

__all__ = [
    "REAL_ESTATE_TRANSACTION",
    "PRODUCT_RESEARCH",
    "PATENT_ANALYSIS",
    "MEETING_ASSISTANT",
    "ALL_DOMAIN_SPECIFIC_WORKFLOWS",
]
