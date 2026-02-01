"""
Professional Workflow Test Data

Realistic test scenarios for each of the 18 professional workflows.
Each scenario includes:
- inputs: Realistic professional scenario
- expected_outputs: What a professional would expect
- verification_checks: Automated assertions
"""

from typing import Dict, Any, List

# =============================================================================
# FINANCE & LEGAL WORKFLOWS
# =============================================================================

TEST_MA_DUE_DILIGENCE = {
    "workflow_id": "ma-due-diligence",
    "inputs": {
        "target_company": "TechStartup Inc",
        "acquisition_type": "full",
        "budget_range": "$10M-$50M",
        "strategic_rationale": "Expand into AI/ML market segment",
        "timeline": "90 days",
    },
    "expected_outputs": {
        "company_profile": ["revenue", "employees", "funding_history", "market_position"],
        "financial_analysis": ["revenue_growth", "burn_rate", "valuation_multiple", "financial_ratios"],
        "risk_assessment": ["technology_risk", "key_person_risk", "ip_ownership", "market_risk"],
        "integration_plan": ["timeline", "key_milestones", "cost_estimates", "synergies"],
        "recommendation": ["proceed_or_pass", "valuation_range", "key_conditions"],
    },
    "required_checkpoints": [
        {"after": "risk-assessment", "type": "HUMAN_APPROVAL"},
        {"after": "final-recommendation", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "recommendation", "min_length": 100},
        {"field": "financial_analysis", "contains": ["valuation", "multiple"]},
    ],
}

TEST_TAX_PREP_ASSISTANT = {
    "workflow_id": "tax-prep-assistant",
    "inputs": {
        "tax_year": "2025",
        "entity_type": "LLC",
        "transactions_data": """
            Date,Description,Amount,Category
            2025-01-15,Office Supplies,-$250,Expense
            2025-01-30,Client Payment,$5000,Income
            2025-02-10,Software Subscription,-$99,Expense
            2025-02-28,Client Payment,$7500,Income
            2025-03-05,Business Lunch,-$85,Expense
            2025-03-15,Consulting Revenue,$12000,Income
        """,
        "prior_year_return": "Filed, total income $180,000, deductions $45,000",
    },
    "expected_outputs": {
        "categorized_transactions": ["income", "expenses", "deductible"],
        "deductions_identified": ["home_office", "business_meals", "software"],
        "tax_estimate": ["federal", "state", "self_employment"],
        "filing_checklist": ["forms_needed", "deadlines", "documentation"],
    },
    "required_checkpoints": [
        {"after": "expense-classification", "type": "HUMAN_INPUT"},
        {"after": "filing-preparation", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "deductions_identified", "min_items": 2},
        {"field": "tax_estimate", "contains": ["federal", "liability"]},
    ],
}

TEST_CONTRACT_REVIEW = {
    "workflow_id": "contract-review",
    "inputs": {
        "contract_text": """
            SOFTWARE AS A SERVICE AGREEMENT

            1. TERM: This agreement shall commence on the Effective Date and continue for
            an initial term of three (3) years, automatically renewing for successive
            one (1) year periods unless either party provides ninety (90) days written notice.

            2. FEES: Customer shall pay $50,000 annually, with 10% increase upon each renewal.

            3. LIABILITY: Provider's total liability shall not exceed the fees paid in the
            preceding twelve (12) months. IN NO EVENT SHALL PROVIDER BE LIABLE FOR ANY
            INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES.

            4. TERMINATION: Provider may terminate this Agreement immediately upon Customer's
            breach. Customer may terminate with 30 days notice but shall pay a termination
            fee equal to 50% of remaining contract value.

            5. DATA: Upon termination, Provider shall retain Customer data for 30 days,
            after which data will be permanently deleted.

            6. GOVERNING LAW: This Agreement shall be governed by the laws of Delaware.
        """,
        "contract_type": "SaaS",
        "party_role": "Customer",
        "negotiation_priorities": ["liability_cap", "termination_flexibility", "data_retention"],
    },
    "expected_outputs": {
        "clause_extraction": ["term", "fees", "liability", "termination", "data"],
        "risk_flags": ["auto_renewal", "price_increase", "asymmetric_termination"],
        "negotiation_points": ["liability_cap", "termination_fee", "data_retention_period"],
        "redline_summary": ["proposed_changes", "priority_order"],
    },
    "required_checkpoints": [
        {"after": "risk-identification", "type": "HUMAN_INPUT"},
        {"after": "negotiation-points", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "risk_flags", "min_items": 2},
        {"field": "negotiation_points", "contains": ["termination", "liability"]},
    ],
}

TEST_AUDIT_PREPARATION = {
    "workflow_id": "audit-preparation",
    "inputs": {
        "audit_type": "SOC 2 Type II",
        "framework": "AICPA Trust Services Criteria",
        "scope": "Cloud infrastructure and customer data processing",
        "audit_date": "2026-04-15",
        "prior_findings": [
            "Access reviews not performed quarterly",
            "Encryption key rotation not documented",
        ],
    },
    "expected_outputs": {
        "control_documentation": ["access_control", "encryption", "monitoring", "incident_response"],
        "gap_analysis": ["gaps_identified", "severity", "remediation_status"],
        "evidence_package": ["policies", "procedures", "logs", "screenshots"],
        "remediation_plan": ["action_items", "owners", "due_dates"],
    },
    "required_checkpoints": [
        {"after": "gap-analysis", "type": "REVIEW"},
        {"after": "audit-package", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "gap_analysis", "addresses_prior_findings": True},
        {"field": "evidence_package", "min_items": 5},
    ],
}


# =============================================================================
# HR & SALES WORKFLOWS
# =============================================================================

TEST_RECRUITING_PIPELINE = {
    "workflow_id": "recruiting-pipeline",
    "inputs": {
        "job_title": "Senior Software Engineer",
        "department": "Engineering",
        "requirements": [
            "5+ years Python experience",
            "Experience with distributed systems",
            "Strong communication skills",
            "BS in Computer Science or equivalent",
        ],
        "salary_range": "$150,000 - $200,000",
        "hiring_manager": "Jane Smith",
    },
    "expected_outputs": {
        "job_posting": ["title", "description", "requirements", "benefits"],
        "candidate_rankings": ["name", "score", "strengths", "concerns"],
        "interview_materials": ["questions", "rubric", "evaluation_criteria"],
        "offer_recommendation": ["base_salary", "equity", "benefits", "start_date"],
    },
    "required_checkpoints": [
        {"after": "posting-creation", "type": "HUMAN_INPUT"},
        {"after": "candidate-scoring", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "job_posting", "contains": ["Python", "distributed"]},
        {"field": "interview_materials", "min_questions": 5},
    ],
}

TEST_RFP_PROPOSAL_RESPONSE = {
    "workflow_id": "rfp-proposal-response",
    "inputs": {
        "rfp_document": """
            REQUEST FOR PROPOSAL: Enterprise Cloud Migration Services

            REQUIREMENTS:
            1. Must support AWS, Azure, and GCP
            2. 24/7 support availability
            3. SOC 2 Type II certified
            4. Experience with Fortune 500 clients
            5. Fixed price engagement preferred

            EVALUATION CRITERIA:
            - Technical approach (40%)
            - Past performance (30%)
            - Price (20%)
            - Team qualifications (10%)

            SUBMISSION DEADLINE: March 1, 2026
        """,
        "company_capabilities": [
            "AWS Advanced Partner",
            "Azure Gold Partner",
            "SOC 2 Type II certified",
            "50+ enterprise migrations completed",
        ],
        "past_performance": [
            "Migrated Fortune 100 retailer - $5M project",
            "Healthcare system modernization - 18 month engagement",
        ],
        "pricing_guidelines": "Target 25% margin, competitive positioning",
    },
    "expected_outputs": {
        "requirement_matrix": ["requirement", "compliance", "evidence"],
        "compliance_status": ["compliant_count", "gaps", "mitigations"],
        "proposal_draft": ["executive_summary", "technical_approach", "team"],
        "pricing_model": ["base_price", "options", "discounts"],
    },
    "required_checkpoints": [
        {"after": "compliance-matrix", "type": "HUMAN_INPUT"},
        {"after": "proposal-drafting", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "requirement_matrix", "all_requirements_addressed": True},
        {"field": "proposal_draft", "contains": ["AWS", "Azure", "GCP"]},
    ],
}

TEST_VENDOR_RISK_ASSESSMENT = {
    "workflow_id": "vendor-risk-assessment",
    "inputs": {
        "vendor_name": "CloudSecure Inc",
        "service_category": "Cloud Security Monitoring",
        "criticality_level": "High",
        "existing_documentation": [
            "SOC 2 Type II Report (2025)",
            "Security questionnaire responses",
        ],
    },
    "expected_outputs": {
        "vendor_profile": ["company_info", "financials", "reputation", "references"],
        "security_findings": ["controls", "vulnerabilities", "certifications"],
        "compliance_status": ["gdpr", "ccpa", "hipaa", "pci"],
        "risk_score": ["overall", "by_category", "trend"],
        "recommendations": ["approve", "conditions", "monitoring"],
    },
    "required_checkpoints": [
        {"after": "security-assessment", "type": "REVIEW"},
        {"after": "risk-scoring", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "risk_score", "is_numeric": True},
        {"field": "security_findings", "contains": ["SOC 2"]},
    ],
}

TEST_EMPLOYEE_ONBOARDING = {
    "workflow_id": "employee-onboarding",
    "inputs": {
        "employee_name": "Alex Johnson",
        "role": "Software Engineer",
        "department": "Engineering",
        "start_date": "2026-02-15",
        "manager": "Sarah Chen",
        "equipment_needs": ["MacBook Pro 16", "Monitor", "Keyboard", "Mouse"],
    },
    "expected_outputs": {
        "onboarding_checklist": ["pre_start", "day_one", "week_one", "month_one"],
        "access_requests": ["systems", "tools", "repositories", "permissions"],
        "training_plan": ["required", "recommended", "schedule"],
        "welcome_package": ["welcome_letter", "org_chart", "buddy_info"],
    },
    "required_checkpoints": [
        {"after": "checklist-generation", "type": "HUMAN_INPUT"},
        {"after": "training-plan", "type": "REVIEW"},
    ],
    "quality_checks": [
        {"field": "onboarding_checklist", "min_items": 10},
        {"field": "access_requests", "contains": ["GitHub", "Slack"]},
    ],
}


# =============================================================================
# SECURITY & OPS WORKFLOWS
# =============================================================================

TEST_SOC_ANALYST = {
    "workflow_id": "soc-analyst",
    "inputs": {
        "alert_data": {
            "alert_id": "SEC-2026-001234",
            "type": "Suspicious Login",
            "source_ip": "185.220.101.45",
            "target_user": "admin@company.com",
            "timestamp": "2026-01-30T14:32:00Z",
            "failed_attempts": 50,
        },
        "source_system": "Azure AD",
        "initial_severity": "Medium",
        "affected_assets": ["Azure AD", "O365", "Corporate VPN"],
    },
    "expected_outputs": {
        "threat_analysis": ["indicators", "tactics", "threat_actor_profile"],
        "scope_assessment": ["affected_systems", "lateral_movement", "data_access"],
        "incident_classification": ["severity", "category", "confidence"],
        "response_actions": ["immediate", "short_term", "long_term"],
        "incident_report": ["timeline", "impact", "recommendations"],
    },
    "required_checkpoints": [
        {"after": "classification", "type": "GATE", "condition": "not_critical"},
        {"after": "response-playbook", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "threat_analysis", "contains": ["IOC", "TTP"]},
        {"field": "response_actions", "min_items": 3},
    ],
}

TEST_VULNERABILITY_ASSESSMENT = {
    "workflow_id": "vulnerability-assessment",
    "inputs": {
        "scan_results": [
            {"cve": "CVE-2024-21762", "severity": "Critical", "host": "web-prod-01", "port": 443},
            {"cve": "CVE-2024-3400", "severity": "Critical", "host": "fw-ext-01", "port": 443},
            {"cve": "CVE-2024-6387", "severity": "High", "host": "ssh-bastion", "port": 22},
        ],
        "asset_inventory": {
            "web-prod-01": {"type": "Web Server", "criticality": "High"},
            "fw-ext-01": {"type": "Firewall", "criticality": "Critical"},
            "ssh-bastion": {"type": "Bastion", "criticality": "High"},
        },
        "business_criticality_map": {"web-prod-01": 9, "fw-ext-01": 10, "ssh-bastion": 8},
        "patch_windows": {"emergency": "4 hours", "critical": "24 hours", "high": "7 days"},
    },
    "expected_outputs": {
        "vulnerability_list": ["cve", "description", "affected_systems"],
        "severity_scores": ["cvss", "business_impact", "exploitability"],
        "remediation_priorities": ["priority_order", "justification"],
        "remediation_plan": ["actions", "owners", "timeline"],
    },
    "required_checkpoints": [
        {"after": "severity-scoring", "type": "REVIEW"},
        {"after": "remediation-plan", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "severity_scores", "critical_vulns_first": True},
        {"field": "remediation_plan", "has_timeline": True},
    ],
}

TEST_CHANGE_MANAGEMENT = {
    "workflow_id": "change-management",
    "inputs": {
        "change_request": {
            "title": "Database Version Upgrade",
            "description": "Upgrade PostgreSQL from 14 to 16",
            "justification": "Performance improvements and security patches",
        },
        "change_type": "Major",
        "affected_systems": ["prod-db-primary", "prod-db-replica", "analytics-db"],
        "proposed_schedule": "2026-02-01 02:00 UTC (Maintenance Window)",
        "change_owner": "Database Team",
    },
    "expected_outputs": {
        "impact_analysis": ["services_affected", "downtime_estimate", "dependencies"],
        "risk_assessment": ["risks", "likelihood", "impact", "mitigations"],
        "rollback_plan": ["steps", "triggers", "duration"],
        "cab_documentation": ["change_record", "approvals", "communication_plan"],
        "approval_checklist": ["prerequisites", "sign_offs"],
    },
    "required_checkpoints": [
        {"after": "risk-evaluation", "type": "HUMAN_APPROVAL"},
        {"after": "change-documentation", "type": "REVIEW"},
    ],
    "quality_checks": [
        {"field": "rollback_plan", "has_steps": True},
        {"field": "impact_analysis", "contains": ["downtime", "dependencies"]},
    ],
}

TEST_DISASTER_RECOVERY_TEST = {
    "workflow_id": "disaster-recovery-test",
    "inputs": {
        "dr_plan": {
            "name": "Primary Data Center Failover",
            "last_tested": "2025-06-15",
            "systems": ["Web Tier", "App Tier", "Database Tier"],
        },
        "systems_in_scope": ["web-cluster", "app-cluster", "db-cluster"],
        "test_type": "Tabletop with partial failover",
        "rto_targets": {"web": "15 min", "app": "30 min", "db": "1 hour"},
        "rpo_targets": {"web": "0", "app": "0", "db": "5 min"},
    },
    "expected_outputs": {
        "test_scenario": ["steps", "success_criteria", "participants"],
        "test_results": ["actual_rto", "actual_rpo", "issues_found"],
        "gap_analysis": ["target_vs_actual", "root_causes"],
        "improvement_recommendations": ["actions", "priorities", "owners"],
    },
    "required_checkpoints": [
        {"after": "test-scenario", "type": "HUMAN_APPROVAL"},
        {"after": "gap-analysis", "type": "HUMAN_INPUT"},
    ],
    "quality_checks": [
        {"field": "test_results", "has_metrics": True},
        {"field": "gap_analysis", "compares_targets": True},
    ],
}


# =============================================================================
# DOMAIN-SPECIFIC WORKFLOWS
# =============================================================================

TEST_REAL_ESTATE_TRANSACTION = {
    "workflow_id": "real-estate-transaction",
    "inputs": {
        "property_address": "123 Oak Street, Austin, TX 78701",
        "transaction_type": "Purchase",
        "buyer_info": {"name": "John Smith", "financing": "Conventional Mortgage"},
        "seller_info": {"name": "ABC Properties LLC"},
        "target_close_date": "2026-03-15",
    },
    "expected_outputs": {
        "property_analysis": ["lot_size", "zoning", "tax_history", "improvements"],
        "market_valuation": ["comparable_sales", "price_per_sqft", "market_trend"],
        "title_report": ["ownership_history", "liens", "encumbrances", "easements"],
        "closing_checklist": ["documents", "contingencies", "deadlines"],
        "transaction_summary": ["key_terms", "timeline", "responsibilities"],
    },
    "required_checkpoints": [
        {"after": "comparable-sales", "type": "HUMAN_INPUT"},
        {"after": "closing-preparation", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "market_valuation", "has_comparables": True},
        {"field": "title_report", "checks_liens": True},
    ],
}

TEST_PRODUCT_RESEARCH = {
    "workflow_id": "product-research",
    "inputs": {
        "product_concept": "AI-powered code review tool for enterprise",
        "target_market": "Enterprise software development teams",
        "budget": "$500,000 for initial development",
        "launch_timeline": "Q3 2026",
        "success_metrics": ["1000 enterprise customers in year 1", "NPS > 50"],
    },
    "expected_outputs": {
        "market_analysis": ["tam", "sam", "som", "growth_rate", "trends"],
        "competitive_matrix": ["competitors", "features", "pricing", "gaps"],
        "positioning_statement": ["target", "differentiator", "value_prop"],
        "pricing_model": ["tiers", "price_points", "revenue_projections"],
        "gtm_plan": ["channels", "messaging", "launch_activities"],
    },
    "required_checkpoints": [
        {"after": "competitive-landscape", "type": "HUMAN_INPUT"},
        {"after": "go-to-market", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "market_analysis", "contains": ["TAM", "SAM"]},
        {"field": "pricing_model", "has_tiers": True},
    ],
}

TEST_PATENT_ANALYSIS = {
    "workflow_id": "patent-analysis",
    "inputs": {
        "invention_description": "Method for using transformer models to generate secure code with automatic vulnerability detection",
        "technology_field": "Software Security / Artificial Intelligence",
        "known_patents": ["US11234567", "US10987654"],
        "competitor_patents": ["Microsoft", "Google", "GitHub"],
    },
    "expected_outputs": {
        "prior_art_findings": ["patents", "publications", "products"],
        "claim_analysis": ["independent_claims", "dependent_claims", "scope"],
        "fto_assessment": ["freedom_to_operate", "risk_level", "blocking_patents"],
        "infringement_risks": ["patents_at_risk", "claim_coverage", "defenses"],
        "recommendation": ["patentability", "design_arounds", "licensing_options"],
    },
    "required_checkpoints": [
        {"after": "prior-art-search", "type": "REVIEW"},
        {"after": "infringement-assessment", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "prior_art_findings", "min_items": 3},
        {"field": "fto_assessment", "has_risk_level": True},
    ],
}

TEST_MEETING_ASSISTANT = {
    "workflow_id": "meeting-assistant",
    "inputs": {
        "meeting_transcript": """
            [00:00] Sarah: Let's start the product planning meeting. First item is the Q2 roadmap.
            [00:15] Mike: I think we should prioritize the API refactor. It's blocking three teams.
            [00:45] Sarah: Agreed. Mike, can you own that? Target completion by end of March.
            [01:00] Mike: Yes, I'll have a detailed plan by Friday.
            [01:15] Lisa: We also need to decide on the pricing changes. Finance wants input by Feb 15.
            [01:30] Sarah: Let's schedule a separate meeting for that. Lisa, can you set it up?
            [01:45] Lisa: Will do. I'll send invites today.
            [02:00] Sarah: Great. Any other items? No? Then we're done. Thanks everyone.
        """,
        "meeting_type": "Product Planning",
        "attendees": ["Sarah Chen", "Mike Johnson", "Lisa Park"],
        "meeting_date": "2026-01-30",
        "context": "Q2 planning cycle",
    },
    "expected_outputs": {
        "action_items": ["task", "owner", "deadline"],
        "decisions_log": ["decision", "rationale", "stakeholders"],
        "meeting_summary": ["key_points", "outcomes", "next_steps"],
        "follow_up_tasks": ["task", "assignee", "due_date"],
    },
    "required_checkpoints": [
        {"after": "action-extraction", "type": "REVIEW"},
        {"after": "summary-generation", "type": "HUMAN_INPUT"},
    ],
    "quality_checks": [
        {"field": "action_items", "min_items": 2},
        {"field": "action_items", "has_owners": True},
    ],
}


# =============================================================================
# CONTENT & INTELLIGENCE WORKFLOWS
# =============================================================================

TEST_LEAD_SCORE_FLOW = {
    "workflow_id": "lead-score-flow",
    "inputs": {
        "lead_data": {
            "company": "Acme Corporation",
            "contact": "Jane Doe",
            "title": "VP of Engineering",
            "email": "jane.doe@acme.com",
            "company_size": 500,
            "industry": "Technology",
        },
        "icp_criteria": {
            "target_industries": ["Technology", "Finance", "Healthcare"],
            "min_company_size": 100,
            "target_titles": ["VP", "Director", "Head of"],
            "budget_indicator": "Series B+",
        },
        "engagement_history": [
            {"type": "webinar", "date": "2026-01-15"},
            {"type": "demo_request", "date": "2026-01-25"},
            {"type": "pricing_page", "date": "2026-01-28"},
        ],
        "scoring_model": "BANT + Engagement",
    },
    "expected_outputs": {
        "enriched_lead": ["company_data", "contact_data", "tech_stack"],
        "behavioral_score": ["engagement_level", "intent_signals", "recency"],
        "fit_score": ["icp_match", "scoring_breakdown"],
        "priority_level": ["tier", "recommended_actions", "next_steps"],
        "recommended_actions": ["action", "urgency", "talk_track"],
    },
    "required_checkpoints": [
        {"after": "fit-scoring", "type": "REVIEW"},
        {"after": "priority-assignment", "type": "GATE", "condition": "score >= 60"},
    ],
    "quality_checks": [
        {"field": "fit_score", "is_numeric": True},
        {"field": "recommended_actions", "min_items": 1},
    ],
}

TEST_EMAIL_AUTO_RESPONDER = {
    "workflow_id": "email-auto-responder",
    "inputs": {
        "email_content": """
            Subject: Urgent - Production System Down

            Hi Support,

            Our production system has been down for the past 30 minutes. We're seeing
            errors when trying to access the dashboard and our customers are complaining.

            Can someone please look into this ASAP? This is affecting our business.

            Thanks,
            John Smith
            CTO, BigCorp Inc
        """,
        "sender_info": {
            "name": "John Smith",
            "email": "john@bigcorp.com",
            "company": "BigCorp Inc",
            "tier": "Enterprise",
        },
        "email_type": "Support Request",
        "knowledge_base_context": [
            "Production issues should be escalated to on-call",
            "Enterprise customers have SLA of 15 min response",
        ],
    },
    "expected_outputs": {
        "email_classification": ["intent", "urgency", "sentiment", "category"],
        "response_draft": ["greeting", "acknowledgment", "next_steps", "closing"],
        "suggested_actions": ["escalation", "ticket_creation", "follow_up"],
        "quality_score": ["accuracy", "tone", "completeness"],
    },
    "required_checkpoints": [
        {"after": "email-classification", "type": "GATE", "condition": "urgency != critical"},
        {"after": "quality-review", "type": "HUMAN_APPROVAL"},
    ],
    "quality_checks": [
        {"field": "email_classification", "urgency": "critical"},
        {"field": "response_draft", "acknowledges_urgency": True},
    ],
}


# =============================================================================
# TEST DATA REGISTRY
# =============================================================================

ALL_TEST_DATA: Dict[str, Dict[str, Any]] = {
    # Finance & Legal
    "ma-due-diligence": TEST_MA_DUE_DILIGENCE,
    "tax-prep-assistant": TEST_TAX_PREP_ASSISTANT,
    "contract-review": TEST_CONTRACT_REVIEW,
    "audit-preparation": TEST_AUDIT_PREPARATION,
    # HR & Sales
    "recruiting-pipeline": TEST_RECRUITING_PIPELINE,
    "rfp-proposal-response": TEST_RFP_PROPOSAL_RESPONSE,
    "vendor-risk-assessment": TEST_VENDOR_RISK_ASSESSMENT,
    "employee-onboarding": TEST_EMPLOYEE_ONBOARDING,
    # Security & Ops
    "soc-analyst": TEST_SOC_ANALYST,
    "vulnerability-assessment": TEST_VULNERABILITY_ASSESSMENT,
    "change-management": TEST_CHANGE_MANAGEMENT,
    "disaster-recovery-test": TEST_DISASTER_RECOVERY_TEST,
    # Domain-Specific
    "real-estate-transaction": TEST_REAL_ESTATE_TRANSACTION,
    "product-research": TEST_PRODUCT_RESEARCH,
    "patent-analysis": TEST_PATENT_ANALYSIS,
    "meeting-assistant": TEST_MEETING_ASSISTANT,
    # Content & Intelligence
    "lead-score-flow": TEST_LEAD_SCORE_FLOW,
    "email-auto-responder": TEST_EMAIL_AUTO_RESPONDER,
}


def get_test_data(workflow_id: str) -> Dict[str, Any]:
    """Get test data for a specific workflow."""
    return ALL_TEST_DATA.get(workflow_id)


def list_test_workflows() -> List[str]:
    """List all workflows with test data."""
    return list(ALL_TEST_DATA.keys())


def get_test_inputs(workflow_id: str) -> Dict[str, Any]:
    """Get just the inputs for a workflow test."""
    data = ALL_TEST_DATA.get(workflow_id)
    return data.get("inputs") if data else None
