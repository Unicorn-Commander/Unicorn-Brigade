"""
Security & Operations Professional Workflows

4 high-value workflows for security and operations teams:
1. SOC Analyst Assistant - Security incident triage and investigation
2. Vulnerability Assessment - Security vulnerability scanning and prioritization
3. Change Management - IT change request review and approval
4. Disaster Recovery Test - DR plan testing and validation
"""

from app.workflows.schema import (
    WorkflowDefinition,
    WorkflowStep,
    Checkpoint,
    CheckpointType,
)
from app.workflows.team_leads import (
    DEVOPS_TEAM_LEAD,
    RESEARCH_TEAM_LEAD,
    CONTENT_TEAM_LEAD,
    LEGAL_TEAM_LEAD,
    INVESTIGATION_TEAM_LEAD,
)


# =============================================================================
# 1. SOC ANALYST ASSISTANT
# =============================================================================

SOC_ANALYST = WorkflowDefinition(
    id="soc-analyst-assistant",
    name="SOC Analyst Assistant",
    description="Automated security incident triage, investigation, and response coordination",
    version="1.0.0",
    tags=["security", "soc", "incident-response"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a security incident response workflow.
Your goal is to quickly triage, investigate, and contain the security incident.
Work with DevOps and Investigation teams to gather evidence and recommend actions.""",

    team_leads=[DEVOPS_TEAM_LEAD, INVESTIGATION_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["alert_type", "alert_source", "affected_systems", "initial_indicators"],
    final_outputs=["incident_report", "severity_rating", "containment_actions", "remediation_plan"],

    steps=[
        WorkflowStep(
            id="alert-triage",
            name="Triage Security Alert",
            description="Analyze alert, determine severity, identify affected systems and data",
            executor="devops-lead",
            inputs={
                "alert_type": "inputs.alert_type",
                "alert_source": "inputs.alert_source",
                "systems": "inputs.affected_systems",
                "indicators": "inputs.initial_indicators",
            },
            outputs=["severity_assessment", "affected_assets", "initial_classification", "triage_notes"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="threat-intelligence",
            name="Gather Threat Intelligence",
            description="Research IOCs, TTPs, threat actor attribution, similar incidents",
            executor="research-lead",
            inputs={
                "alert_type": "inputs.alert_type",
                "indicators": "inputs.initial_indicators",
            },
            outputs=["threat_intel", "ioc_analysis", "ttp_mapping", "attribution"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="evidence-collection",
            name="Collect Evidence",
            description="Gather logs, network captures, memory dumps, forensic artifacts",
            executor="investigation-lead",
            inputs={
                "systems": "alert-triage.affected_assets",
                "alert_type": "inputs.alert_type",
            },
            outputs=["log_analysis", "network_traffic", "forensic_artifacts", "timeline"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="impact-assessment",
            name="Assess Impact",
            description="Determine scope of compromise, data exposure, business impact",
            executor="orchestrator",
            inputs={
                "affected_assets": "alert-triage.affected_assets",
                "evidence": "evidence-collection.log_analysis",
                "threat_intel": "threat-intelligence.threat_intel",
            },
            outputs=["impact_scope", "data_exposure", "business_impact", "affected_users"],
            timeout_seconds=90,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review impact assessment. Escalate to major incident or continue investigation?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="containment-plan",
            name="Develop Containment Plan",
            description="Create specific containment actions to stop the incident from spreading",
            executor="devops-lead",
            inputs={
                "severity": "alert-triage.severity_assessment",
                "impact": "impact-assessment.impact_scope",
                "threat_intel": "threat-intelligence.ttp_mapping",
            },
            outputs=["containment_actions", "isolation_steps", "backup_plan"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="remediation-plan",
            name="Create Remediation Plan",
            description="Develop long-term remediation and hardening recommendations",
            executor="devops-lead",
            inputs={
                "containment": "containment-plan.containment_actions",
                "evidence": "evidence-collection.forensic_artifacts",
                "threat_intel": "threat-intelligence.ttp_mapping",
            },
            outputs=["remediation_steps", "hardening_recommendations", "monitoring_enhancements"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="incident-report",
            name="Generate Incident Report",
            description="Create comprehensive incident report with findings and recommendations",
            executor="content-lead",
            inputs={
                "alert": "inputs.alert_type",
                "severity": "alert-triage.severity_assessment",
                "impact": "impact-assessment.impact_scope",
                "evidence": "evidence-collection.timeline",
                "containment": "containment-plan.containment_actions",
                "remediation": "remediation-plan.remediation_steps",
            },
            outputs=["incident_report", "executive_summary", "lessons_learned"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Incident response complete. Review and approve incident report?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 2. VULNERABILITY ASSESSMENT
# =============================================================================

VULNERABILITY_ASSESSMENT = WorkflowDefinition(
    id="vulnerability-assessment",
    name="Vulnerability Assessment Workflow",
    description="Automated vulnerability scanning, prioritization, and remediation tracking",
    version="1.0.0",
    tags=["security", "vulnerability-management", "risk"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a vulnerability assessment workflow.
Your goal is to identify, prioritize, and track remediation of security vulnerabilities.
Work with DevOps and Research teams to assess risk and create remediation plans.""",

    team_leads=[DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["scan_scope", "asset_inventory", "compliance_framework"],
    final_outputs=["vulnerability_report", "risk_matrix", "remediation_plan", "compliance_gaps"],

    steps=[
        WorkflowStep(
            id="vulnerability-scan",
            name="Execute Vulnerability Scan",
            description="Scan all in-scope systems for vulnerabilities, misconfigurations, exposures",
            executor="devops-lead",
            inputs={
                "scope": "inputs.scan_scope",
                "assets": "inputs.asset_inventory",
            },
            outputs=["scan_results", "vulnerability_list", "affected_systems", "scan_coverage"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="threat-context",
            name="Enrich with Threat Context",
            description="Research CVEs, active exploits, exploit availability, threat actor usage",
            executor="research-lead",
            inputs={
                "vulnerabilities": "vulnerability-scan.vulnerability_list",
            },
            outputs=["cve_details", "exploit_availability", "active_threats", "epss_scores"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="risk-scoring",
            name="Calculate Risk Scores",
            description="Score vulnerabilities using CVSS, EPSS, asset criticality, exposure",
            executor="devops-lead",
            inputs={
                "vulnerabilities": "vulnerability-scan.vulnerability_list",
                "threat_context": "threat-context.exploit_availability",
                "assets": "inputs.asset_inventory",
            },
            outputs=["risk_scores", "criticality_ratings", "prioritized_list"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="compliance-check",
            name="Check Compliance Impact",
            description="Map vulnerabilities to compliance requirements, identify gaps",
            executor="research-lead",
            inputs={
                "vulnerabilities": "vulnerability-scan.vulnerability_list",
                "framework": "inputs.compliance_framework",
            },
            outputs=["compliance_gaps", "control_failures", "audit_impact"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="remediation-planning",
            name="Create Remediation Plan",
            description="Develop remediation timeline, assign owners, track dependencies",
            executor="devops-lead",
            inputs={
                "prioritized_vulns": "risk-scoring.prioritized_list",
                "compliance_gaps": "compliance-check.compliance_gaps",
            },
            outputs=["remediation_plan", "timeline", "resource_requirements", "dependencies"],
            timeout_seconds=120,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review remediation plan and timeline. Approve resource allocation?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="vuln-report",
            name="Generate Vulnerability Report",
            description="Create executive and technical reports with metrics and trends",
            executor="content-lead",
            inputs={
                "scan_results": "vulnerability-scan.scan_results",
                "risk_scores": "risk-scoring.risk_scores",
                "remediation_plan": "remediation-planning.remediation_plan",
                "compliance": "compliance-check.compliance_gaps",
            },
            outputs=["executive_report", "technical_report", "metrics_dashboard", "trend_analysis"],
            timeout_seconds=120,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Vulnerability assessment complete. Approve remediation priorities?",
            required_approval=False,
        )
    ],
)


# =============================================================================
# 3. CHANGE MANAGEMENT
# =============================================================================

CHANGE_MANAGEMENT = WorkflowDefinition(
    id="change-management",
    name="IT Change Management Workflow",
    description="Automated change request review, risk assessment, and approval workflow",
    version="1.0.0",
    tags=["operations", "change-management", "itil"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating an IT change management workflow.
Your goal is to assess the change request, identify risks, and recommend approval/rejection.
Work with DevOps and Research teams to evaluate impact and create implementation plans.""",

    team_leads=[DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD],

    required_inputs=["change_type", "change_description", "requested_by", "target_date", "affected_systems"],
    final_outputs=["change_assessment", "risk_analysis", "implementation_plan", "approval_recommendation"],

    steps=[
        WorkflowStep(
            id="change-classification",
            name="Classify Change Request",
            description="Categorize change (standard/normal/emergency), determine approval level",
            executor="devops-lead",
            inputs={
                "type": "inputs.change_type",
                "description": "inputs.change_description",
                "systems": "inputs.affected_systems",
            },
            outputs=["change_category", "approval_level", "required_reviewers"],
            timeout_seconds=60,
        ),
        WorkflowStep(
            id="impact-analysis",
            name="Analyze Impact",
            description="Assess technical impact, service dependencies, user impact, downtime",
            executor="devops-lead",
            inputs={
                "description": "inputs.change_description",
                "systems": "inputs.affected_systems",
            },
            outputs=["technical_impact", "service_dependencies", "user_impact", "downtime_estimate"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="historical-analysis",
            name="Review Change History",
            description="Research similar past changes, success rate, common issues",
            executor="research-lead",
            inputs={
                "type": "inputs.change_type",
                "systems": "inputs.affected_systems",
            },
            outputs=["similar_changes", "success_rate", "common_issues", "lessons_learned"],
            timeout_seconds=90,
        ),
        WorkflowStep(
            id="risk-assessment",
            name="Assess Change Risk",
            description="Evaluate risk level, identify failure scenarios, assess rollback capability",
            executor="orchestrator",
            inputs={
                "impact": "impact-analysis.technical_impact",
                "dependencies": "impact-analysis.service_dependencies",
                "history": "historical-analysis.common_issues",
            },
            outputs=["risk_level", "failure_scenarios", "rollback_feasibility", "risk_mitigation"],
            timeout_seconds=90,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Review risk assessment. High risk detected - proceed with planning or require additional review?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="implementation-plan",
            name="Create Implementation Plan",
            description="Develop detailed implementation steps, rollback plan, testing plan",
            executor="devops-lead",
            inputs={
                "description": "inputs.change_description",
                "impact": "impact-analysis.technical_impact",
                "risks": "risk-assessment.failure_scenarios",
                "target_date": "inputs.target_date",
            },
            outputs=["implementation_steps", "rollback_plan", "testing_plan", "communication_plan"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="change-approval",
            name="Generate Approval Recommendation",
            description="Synthesize findings into approval recommendation with conditions",
            executor="content-lead",
            inputs={
                "category": "change-classification.change_category",
                "risk": "risk-assessment.risk_level",
                "impact": "impact-analysis.user_impact",
                "plan": "implementation-plan.implementation_steps",
            },
            outputs=["recommendation", "approval_conditions", "change_summary", "cab_presentation"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="Change assessment complete. Approve change for implementation?",
            required_approval=True,
        )
    ],
)


# =============================================================================
# 4. DISASTER RECOVERY TEST
# =============================================================================

DISASTER_RECOVERY_TEST = WorkflowDefinition(
    id="disaster-recovery-test",
    name="Disaster Recovery Test Workflow",
    description="Automated DR plan testing, validation, and gap remediation",
    version="1.0.0",
    tags=["operations", "disaster-recovery", "business-continuity"],

    orchestrator_model="openai/gpt-4o-mini",
    orchestrator_prompt="""You are orchestrating a disaster recovery test workflow.
Your goal is to validate the DR plan, identify gaps, and ensure recovery objectives are achievable.
Work with DevOps and Content teams to execute tests and document results.""",

    team_leads=[DEVOPS_TEAM_LEAD, RESEARCH_TEAM_LEAD, CONTENT_TEAM_LEAD, LEGAL_TEAM_LEAD],

    required_inputs=["dr_plan_version", "test_scope", "rto_target", "rpo_target"],
    final_outputs=["test_results", "gap_analysis", "plan_updates", "compliance_report"],

    steps=[
        WorkflowStep(
            id="test-planning",
            name="Plan DR Test",
            description="Define test scenarios, success criteria, participant roles, timeline",
            executor="devops-lead",
            inputs={
                "plan_version": "inputs.dr_plan_version",
                "scope": "inputs.test_scope",
                "rto": "inputs.rto_target",
                "rpo": "inputs.rpo_target",
            },
            outputs=["test_scenarios", "success_criteria", "participant_roles", "test_timeline"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="pre-test-validation",
            name="Validate Pre-Test Readiness",
            description="Verify backups, check DR site readiness, confirm team availability",
            executor="devops-lead",
            inputs={
                "scope": "inputs.test_scope",
                "scenarios": "test-planning.test_scenarios",
            },
            outputs=["backup_status", "dr_site_status", "team_readiness", "blockers"],
            timeout_seconds=90,
            checkpoints=[
                Checkpoint(
                    type=CheckpointType.HUMAN_APPROVAL,
                    prompt="Pre-test validation complete. Blockers identified - proceed with test or resolve first?",
                    required_approval=True,
                )
            ],
        ),
        WorkflowStep(
            id="failover-test",
            name="Execute Failover Test",
            description="Simulate disaster, initiate failover, measure recovery time",
            executor="devops-lead",
            inputs={
                "scenarios": "test-planning.test_scenarios",
                "dr_site": "pre-test-validation.dr_site_status",
            },
            outputs=["failover_results", "actual_rto", "actual_rpo", "issues_encountered"],
            timeout_seconds=300,
        ),
        WorkflowStep(
            id="validation-testing",
            name="Validate Recovery",
            description="Test application functionality, data integrity, network connectivity",
            executor="devops-lead",
            inputs={
                "failover_results": "failover-test.failover_results",
                "success_criteria": "test-planning.success_criteria",
            },
            outputs=["functionality_test", "data_integrity_test", "connectivity_test", "validation_status"],
            timeout_seconds=180,
        ),
        WorkflowStep(
            id="failback-test",
            name="Test Failback Procedure",
            description="Execute failback to primary site, verify data sync, confirm normal operations",
            executor="devops-lead",
            inputs={
                "failover_results": "failover-test.failover_results",
            },
            outputs=["failback_results", "data_sync_status", "operational_status"],
            timeout_seconds=240,
        ),
        WorkflowStep(
            id="gap-analysis",
            name="Identify Gaps",
            description="Compare actual vs target RTO/RPO, identify plan gaps, document lessons learned",
            executor="orchestrator",
            inputs={
                "actual_rto": "failover-test.actual_rto",
                "actual_rpo": "failover-test.actual_rpo",
                "target_rto": "inputs.rto_target",
                "target_rpo": "inputs.rpo_target",
                "issues": "failover-test.issues_encountered",
                "validation": "validation-testing.validation_status",
            },
            outputs=["gap_analysis", "lessons_learned", "improvement_recommendations"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="plan-updates",
            name="Update DR Plan",
            description="Incorporate findings into updated DR plan and runbooks",
            executor="content-lead",
            inputs={
                "gaps": "gap-analysis.gap_analysis",
                "lessons": "gap-analysis.lessons_learned",
                "plan_version": "inputs.dr_plan_version",
            },
            outputs=["updated_plan", "updated_runbooks", "training_needs"],
            timeout_seconds=120,
        ),
        WorkflowStep(
            id="compliance-report",
            name="Generate Compliance Report",
            description="Create test report for auditors, regulators, and management",
            executor="content-lead",
            inputs={
                "test_results": "failover-test.failover_results",
                "validation": "validation-testing.validation_status",
                "gaps": "gap-analysis.gap_analysis",
                "updates": "plan-updates.updated_plan",
            },
            outputs=["compliance_report", "executive_summary", "audit_evidence"],
            timeout_seconds=90,
        ),
    ],

    checkpoints=[
        Checkpoint(
            type=CheckpointType.HUMAN_APPROVAL,
            prompt="DR test complete. Review results and approve plan updates?",
            required_approval=False,
        )
    ],
)


# Aggregate all Security & Ops workflows
ALL_SECURITY_OPS_WORKFLOWS = {
    "soc-analyst-assistant": SOC_ANALYST,
    "vulnerability-assessment": VULNERABILITY_ASSESSMENT,
    "change-management": CHANGE_MANAGEMENT,
    "disaster-recovery-test": DISASTER_RECOVERY_TEST,
}

__all__ = [
    "SOC_ANALYST",
    "VULNERABILITY_ASSESSMENT",
    "CHANGE_MANAGEMENT",
    "DISASTER_RECOVERY_TEST",
    "ALL_SECURITY_OPS_WORKFLOWS",
]
