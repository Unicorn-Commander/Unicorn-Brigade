"""
Domain Team Leads and Workers

This module defines the 3-tier agent hierarchy:
- Orchestrator (The General) - Claude Opus 4.5 / GPT-4o
- Team Leads (gpt-oss-120b) - Domain coordinators, ultra-low cost API models
- Workers (granite-3.3-2b / qwen3-vl-30b-a3b) - Ultra-narrow task executors

Domains:
1. Research - OSINT, data gathering, fact verification
2. Finance - Financial analysis, calculations, projections
3. Content - Writing, editing, SEO, social media
4. Sales - Lead research, outreach, CRM operations
5. DevOps - Monitoring, incident response, deployments
6. Legal - Case analysis, document drafting, FOIA, settlements
7. Medical - Medical analysis, compliance, documentation
8. Investigation - Evidence collection, timeline, pattern detection
"""

from typing import Dict, List, Any
from app.workflows.schema import TeamLeadSpec, WorkerSpec, ModelTier


# =============================================================================
# RESEARCH DOMAIN
# =============================================================================

RESEARCH_WORKERS = [
    WorkerSpec(
        id="web-searcher",
        name="Web Searcher",
        description="Executes web searches and returns structured results",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=500,
        task_prompt="""You are a web search executor. Given a search query, return the key information found.

INPUT: A search query
OUTPUT: JSON with {query, results: [{title, snippet, relevance_score}], summary}

Be concise. Extract only factual information.""",
        input_schema={"query": "string", "num_results": "int"},
        output_schema={"query": "string", "results": "array", "summary": "string"},
        tool="web_search",
        examples=[
            {
                "input": {"query": "Apple Q4 2025 earnings"},
                "output": {"query": "Apple Q4 2025 earnings", "results": [{"title": "Apple Reports Q4", "snippet": "Revenue $95B...", "relevance_score": 0.95}], "summary": "Apple reported $95B revenue in Q4 2025"}
            }
        ]
    ),
    WorkerSpec(
        id="doc-parser",
        name="Document Parser",
        description="Extracts structured data from documents",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.1,
        max_tokens=800,
        task_prompt="""You are a document parser. Extract structured information from the given text.

INPUT: Raw document text
OUTPUT: JSON with {document_type, key_facts: [], entities: [{name, type}], dates: [], numbers: []}

Be precise. Only extract what is explicitly stated.""",
        input_schema={"text": "string", "extract_types": "array"},
        output_schema={"document_type": "string", "key_facts": "array", "entities": "array", "dates": "array", "numbers": "array"},
        examples=[
            {
                "input": {"text": "John Smith, CEO of Acme Corp, announced on March 15 that revenue reached $50M"},
                "output": {"document_type": "announcement", "key_facts": ["Revenue reached $50M"], "entities": [{"name": "John Smith", "type": "person"}, {"name": "Acme Corp", "type": "organization"}], "dates": ["March 15"], "numbers": ["$50M"]}
            }
        ]
    ),
    WorkerSpec(
        id="fact-checker",
        name="Fact Checker",
        description="Verifies claims against known facts",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a fact checker. Given a claim and context, determine if the claim is supported.

INPUT: {claim, context}
OUTPUT: JSON with {claim, verdict: "supported"|"refuted"|"insufficient_evidence", confidence: 0-1, reasoning}

Be objective. Only use provided context.""",
        input_schema={"claim": "string", "context": "string"},
        output_schema={"claim": "string", "verdict": "string", "confidence": "float", "reasoning": "string"},
        examples=[
            {
                "input": {"claim": "Apple revenue was $95B in Q4", "context": "Apple reported quarterly revenue of $95.4 billion"},
                "output": {"claim": "Apple revenue was $95B in Q4", "verdict": "supported", "confidence": 0.95, "reasoning": "Context confirms $95.4B which rounds to $95B"}
            }
        ]
    ),
    WorkerSpec(
        id="summarizer",
        name="Summarizer",
        description="Creates concise summaries of long text",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=600,
        task_prompt="""You are a summarizer. Create a concise summary of the provided text.

INPUT: {text, max_length, focus_on}
OUTPUT: JSON with {summary, key_points: [], word_count}

Be concise. Preserve critical information only.""",
        input_schema={"text": "string", "max_length": "int", "focus_on": "string"},
        output_schema={"summary": "string", "key_points": "array", "word_count": "int"},
        examples=[]
    ),
    WorkerSpec(
        id="source-ranker",
        name="Source Ranker",
        description="Ranks sources by credibility and relevance",
        model="ollama/tinyllama:1.1b",
        temperature=0.1,
        max_tokens=300,
        task_prompt="""You are a source ranker. Rank the given sources by credibility and relevance.

INPUT: {sources: [{name, type, content_preview}], topic}
OUTPUT: JSON with {ranked_sources: [{name, credibility_score: 0-1, relevance_score: 0-1, reasoning}]}

Base rankings on source type (official > news > blog), recency, and topic match.""",
        input_schema={"sources": "array", "topic": "string"},
        output_schema={"ranked_sources": "array"},
        examples=[]
    ),
]

RESEARCH_TEAM_LEAD = TeamLeadSpec(
    id="research-lead",
    name="Research Team Lead",
    domain="research",
    description="Coordinates deep research tasks across multiple sources",
    model="openai/gpt-oss-120b",
    temperature=0.3,
    max_tokens=1500,
    system_prompt="""You are the Research Team Lead. Your job is to coordinate research tasks by delegating to specialized workers.

Your workers:
- web-searcher: Executes web searches
- doc-parser: Extracts structured data from documents
- fact-checker: Verifies claims against evidence
- summarizer: Creates concise summaries
- source-ranker: Ranks sources by credibility

For each research request:
1. Analyze what information is needed
2. Decide which workers to use and in what order
3. Aggregate results into a coherent research report

Always cite sources. Distinguish facts from inferences.""",
    workers=RESEARCH_WORKERS,
    delegation_prompt="""Given the task, determine which workers to delegate to.
Return: {"delegations": [{"worker_id": "...", "task": "...", "priority": 1-5}], "aggregation_strategy": "sequential|parallel|iterative"}"""
)


# =============================================================================
# FINANCE DOMAIN
# =============================================================================

FINANCE_WORKERS = [
    WorkerSpec(
        id="ratio-calculator",
        name="Ratio Calculator",
        description="Calculates financial ratios from numbers",
        model="ollama/qwen2.5-math:1.5b",
        temperature=0.0,
        max_tokens=300,
        task_prompt="""You are a financial ratio calculator. Calculate the requested ratio from the given numbers.

INPUT: {ratio_type, values: {revenue, expenses, assets, liabilities, equity, ...}}
OUTPUT: JSON with {ratio_name, formula, calculation, result, interpretation}

Supported ratios: P/E, ROE, ROA, current_ratio, debt_equity, gross_margin, net_margin, quick_ratio

Be precise with calculations.""",
        input_schema={"ratio_type": "string", "values": "object"},
        output_schema={"ratio_name": "string", "formula": "string", "calculation": "string", "result": "float", "interpretation": "string"},
        tool="calculator",
        examples=[
            {
                "input": {"ratio_type": "P/E", "values": {"price": 150, "earnings_per_share": 6}},
                "output": {"ratio_name": "Price-to-Earnings", "formula": "Price / EPS", "calculation": "150 / 6", "result": 25.0, "interpretation": "P/E of 25 is moderate for tech sector"}
            }
        ]
    ),
    WorkerSpec(
        id="trend-analyzer",
        name="Trend Analyzer",
        description="Identifies trends in time series financial data",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a trend analyzer. Analyze the time series data and identify trends.

INPUT: {data_points: [{date, value}], metric_name}
OUTPUT: JSON with {trend_direction: "up"|"down"|"flat", trend_strength: 0-1, key_changes: [{date, change_type, magnitude}], forecast_next: value}

Focus on significant changes (>5% moves).""",
        input_schema={"data_points": "array", "metric_name": "string"},
        output_schema={"trend_direction": "string", "trend_strength": "float", "key_changes": "array", "forecast_next": "float"},
        examples=[]
    ),
    WorkerSpec(
        id="number-extractor",
        name="Number Extractor",
        description="Extracts financial numbers from text",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.0,
        max_tokens=400,
        task_prompt="""You are a financial number extractor. Extract all financial figures from the text.

INPUT: {text}
OUTPUT: JSON with {numbers: [{value, unit, context, confidence: 0-1}]}

Extract: revenue, profit, expenses, growth rates, prices, quantities, percentages.
Normalize units (K=1000, M=1000000, B=1000000000).""",
        input_schema={"text": "string"},
        output_schema={"numbers": "array"},
        examples=[
            {
                "input": {"text": "Revenue grew 15% to $2.5B while expenses were $1.8B"},
                "output": {"numbers": [{"value": 0.15, "unit": "percent", "context": "revenue growth", "confidence": 1.0}, {"value": 2500000000, "unit": "USD", "context": "revenue", "confidence": 1.0}, {"value": 1800000000, "unit": "USD", "context": "expenses", "confidence": 1.0}]}
            }
        ]
    ),
    WorkerSpec(
        id="risk-scorer",
        name="Risk Scorer",
        description="Assigns risk scores based on financial metrics",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a risk scorer. Evaluate risk level based on financial metrics.

INPUT: {metrics: {debt_ratio, cash_flow, revenue_trend, market_volatility, ...}}
OUTPUT: JSON with {overall_risk: "low"|"medium"|"high"|"critical", risk_score: 0-100, factors: [{factor, contribution, reasoning}]}

Risk factors: leverage, liquidity, market exposure, concentration, regulatory.""",
        input_schema={"metrics": "object"},
        output_schema={"overall_risk": "string", "risk_score": "int", "factors": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="report-formatter",
        name="Report Formatter",
        description="Formats financial data into readable reports",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=600,
        task_prompt="""You are a report formatter. Format financial data into a professional report section.

INPUT: {data, section_type: "executive_summary"|"financial_highlights"|"risk_assessment"|"recommendations"}
OUTPUT: JSON with {formatted_text, bullet_points: [], tables: [{headers, rows}]}

Use clear business language. Highlight key metrics.""",
        input_schema={"data": "object", "section_type": "string"},
        output_schema={"formatted_text": "string", "bullet_points": "array", "tables": "array"},
        examples=[]
    ),
]

FINANCE_TEAM_LEAD = TeamLeadSpec(
    id="finance-lead",
    name="Finance Team Lead",
    domain="finance",
    description="Coordinates financial analysis and reporting",
    model="openai/gpt-oss-120b",
    temperature=0.2,
    max_tokens=1500,
    system_prompt="""You are the Finance Team Lead. Your job is to coordinate financial analysis tasks.

Your workers:
- ratio-calculator: Calculates financial ratios (P/E, ROE, etc.)
- trend-analyzer: Identifies trends in time series data
- number-extractor: Extracts financial figures from text
- risk-scorer: Evaluates risk levels
- report-formatter: Formats data into reports

For each financial analysis request:
1. Determine what analysis is needed
2. Extract relevant numbers first
3. Calculate required ratios and trends
4. Assess risks
5. Format into professional output

Always show your calculations. Highlight key insights.""",
    workers=FINANCE_WORKERS,
    delegation_prompt="""Determine workers needed for financial analysis.
Return: {"delegations": [{"worker_id": "...", "task": "...", "depends_on": ["..."]|null}], "output_format": "report|data|both"}"""
)


# =============================================================================
# CONTENT DOMAIN
# =============================================================================

CONTENT_WORKERS = [
    WorkerSpec(
        id="headline-writer",
        name="Headline Writer",
        description="Writes compelling headlines and titles",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.7,
        max_tokens=200,
        task_prompt="""You are a headline writer. Create compelling headlines for the given content.

INPUT: {topic, tone: "professional"|"casual"|"urgent"|"clickbait", target_length, keywords: []}
OUTPUT: JSON with {headlines: [{text, word_count, includes_keyword: bool}], recommended: index}

Create 3-5 options. Vary structure (question, number, how-to, statement).""",
        input_schema={"topic": "string", "tone": "string", "target_length": "int", "keywords": "array"},
        output_schema={"headlines": "array", "recommended": "int"},
        examples=[
            {
                "input": {"topic": "AI productivity tools", "tone": "professional", "target_length": 10, "keywords": ["AI", "productivity"]},
                "output": {"headlines": [{"text": "5 AI Tools That Will Double Your Productivity", "word_count": 8, "includes_keyword": True}, {"text": "How AI is Transforming Workplace Productivity", "word_count": 6, "includes_keyword": True}], "recommended": 0}
            }
        ]
    ),
    WorkerSpec(
        id="seo-optimizer",
        name="SEO Optimizer",
        description="Optimizes content for search engines",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are an SEO optimizer. Analyze and improve content for search visibility.

INPUT: {content, target_keywords: [], current_meta: {title, description}}
OUTPUT: JSON with {keyword_density: {}, suggestions: [], optimized_meta: {title, description, slug}, score: 0-100}

Focus on: keyword placement, meta tags, readability, structure.""",
        input_schema={"content": "string", "target_keywords": "array", "current_meta": "object"},
        output_schema={"keyword_density": "object", "suggestions": "array", "optimized_meta": "object", "score": "int"},
        examples=[]
    ),
    WorkerSpec(
        id="tone-adjuster",
        name="Tone Adjuster",
        description="Adjusts content tone and style",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.4,
        max_tokens=600,
        task_prompt="""You are a tone adjuster. Rewrite content to match the target tone.

INPUT: {content, current_tone, target_tone: "formal"|"casual"|"friendly"|"authoritative"|"empathetic"}
OUTPUT: JSON with {adjusted_content, changes_made: [], tone_match_score: 0-1}

Preserve meaning. Adjust vocabulary, sentence structure, and phrasing.""",
        input_schema={"content": "string", "current_tone": "string", "target_tone": "string"},
        output_schema={"adjusted_content": "string", "changes_made": "array", "tone_match_score": "float"},
        examples=[]
    ),
    WorkerSpec(
        id="hashtag-generator",
        name="Hashtag Generator",
        description="Generates relevant hashtags for social media",
        model="ollama/tinyllama:1.1b",
        temperature=0.5,
        max_tokens=200,
        task_prompt="""You are a hashtag generator. Create relevant hashtags for social media content.

INPUT: {content, platform: "twitter"|"linkedin"|"instagram", max_hashtags}
OUTPUT: JSON with {hashtags: [{tag, relevance: 0-1, popularity: "high"|"medium"|"niche"}], recommended_count}

Twitter: 2-3 hashtags. LinkedIn: 3-5. Instagram: up to 30.""",
        input_schema={"content": "string", "platform": "string", "max_hashtags": "int"},
        output_schema={"hashtags": "array", "recommended_count": "int"},
        examples=[]
    ),
    WorkerSpec(
        id="grammar-checker",
        name="Grammar Checker",
        description="Checks and corrects grammar errors",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.0,
        max_tokens=500,
        task_prompt="""You are a grammar checker. Find and fix grammar, spelling, and punctuation errors.

INPUT: {text}
OUTPUT: JSON with {corrected_text, errors: [{original, corrected, type, position}], error_count}

Error types: spelling, grammar, punctuation, word_choice, clarity.""",
        input_schema={"text": "string"},
        output_schema={"corrected_text": "string", "errors": "array", "error_count": "int"},
        examples=[]
    ),
]

CONTENT_TEAM_LEAD = TeamLeadSpec(
    id="content-lead",
    name="Content Team Lead",
    domain="content",
    description="Coordinates content creation and optimization",
    model="openai/gpt-oss-120b",
    temperature=0.4,
    max_tokens=1500,
    system_prompt="""You are the Content Team Lead. Your job is to coordinate content creation and optimization.

Your workers:
- headline-writer: Creates compelling headlines
- seo-optimizer: Optimizes for search engines
- tone-adjuster: Adjusts content tone
- hashtag-generator: Creates social media hashtags
- grammar-checker: Fixes grammar and spelling

For each content request:
1. Understand the target audience and platform
2. Generate or adjust content as needed
3. Optimize for SEO if applicable
4. Check grammar and polish
5. Add appropriate metadata

Balance creativity with clarity. Match brand voice.""",
    workers=CONTENT_WORKERS,
    delegation_prompt="""Determine content workflow.
Return: {"delegations": [{"worker_id": "...", "task": "..."}], "content_type": "blog|social|email|marketing", "requires_review": bool}"""
)


# =============================================================================
# SALES DOMAIN
# =============================================================================

SALES_WORKERS = [
    WorkerSpec(
        id="lead-qualifier",
        name="Lead Qualifier",
        description="Qualifies leads based on criteria",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a lead qualifier. Score leads based on qualification criteria.

INPUT: {lead: {company, size, industry, budget, timeline, need}, criteria: {ideal_company_size, target_industries, min_budget}}
OUTPUT: JSON with {score: 0-100, qualification: "hot"|"warm"|"cold"|"disqualified", factors: [{criterion, score, reasoning}], recommended_action}

BANT: Budget, Authority, Need, Timeline.""",
        input_schema={"lead": "object", "criteria": "object"},
        output_schema={"score": "int", "qualification": "string", "factors": "array", "recommended_action": "string"},
        examples=[]
    ),
    WorkerSpec(
        id="company-profiler",
        name="Company Profiler",
        description="Creates company profiles from data",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=500,
        task_prompt="""You are a company profiler. Create a concise company profile from available data.

INPUT: {company_name, data: {website_content, news, social, financials}}
OUTPUT: JSON with {profile: {name, industry, size, description, key_people: [], recent_news: [], pain_points: [], opportunities: []}}

Focus on sales-relevant insights.""",
        input_schema={"company_name": "string", "data": "object"},
        output_schema={"profile": "object"},
        examples=[]
    ),
    WorkerSpec(
        id="email-personalizer",
        name="Email Personalizer",
        description="Personalizes email templates",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.5,
        max_tokens=400,
        task_prompt="""You are an email personalizer. Customize email templates for specific prospects.

INPUT: {template, prospect: {name, company, role, pain_points, recent_activity}}
OUTPUT: JSON with {personalized_email: {subject, body}, personalization_points: [], estimated_engagement_score: 0-1}

Add specific references. Keep professional but personal.""",
        input_schema={"template": "string", "prospect": "object"},
        output_schema={"personalized_email": "object", "personalization_points": "array", "estimated_engagement_score": "float"},
        examples=[]
    ),
    WorkerSpec(
        id="objection-handler",
        name="Objection Handler",
        description="Generates responses to sales objections",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.3,
        max_tokens=400,
        task_prompt="""You are an objection handler. Generate responses to common sales objections.

INPUT: {objection, context: {product, prospect_industry, conversation_history}}
OUTPUT: JSON with {responses: [{approach: "acknowledge"|"reframe"|"evidence"|"question", response, effectiveness: 0-1}], recommended: index}

Common objections: price, timing, competitor, need, authority.""",
        input_schema={"objection": "string", "context": "object"},
        output_schema={"responses": "array", "recommended": "int"},
        examples=[]
    ),
    WorkerSpec(
        id="meeting-prepper",
        name="Meeting Prepper",
        description="Prepares briefings for sales meetings",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.2,
        max_tokens=600,
        task_prompt="""You are a meeting prepper. Create a briefing for an upcoming sales meeting.

INPUT: {prospect: {company, contacts, history}, meeting_type: "discovery"|"demo"|"negotiation"|"close", previous_interactions: []}
OUTPUT: JSON with {briefing: {key_facts, talking_points: [], questions_to_ask: [], potential_objections: [], goals: []}, prep_time_estimate}

Focus on actionable intelligence.""",
        input_schema={"prospect": "object", "meeting_type": "string", "previous_interactions": "array"},
        output_schema={"briefing": "object", "prep_time_estimate": "string"},
        examples=[]
    ),
]

SALES_TEAM_LEAD = TeamLeadSpec(
    id="sales-lead",
    name="Sales Team Lead",
    domain="sales",
    description="Coordinates sales intelligence and outreach",
    model="openai/gpt-oss-120b",
    temperature=0.3,
    max_tokens=1500,
    system_prompt="""You are the Sales Team Lead. Your job is to coordinate sales intelligence and outreach activities.

Your workers:
- lead-qualifier: Scores and qualifies leads
- company-profiler: Creates company profiles
- email-personalizer: Customizes outreach emails
- objection-handler: Handles sales objections
- meeting-prepper: Prepares meeting briefings

For each sales task:
1. Gather intelligence on the prospect/company
2. Qualify the opportunity
3. Personalize outreach as needed
4. Prepare for objections
5. Create actionable recommendations

Focus on value-based selling. Be consultative, not pushy.""",
    workers=SALES_WORKERS,
    delegation_prompt="""Determine sales workflow.
Return: {"delegations": [{"worker_id": "...", "task": "..."}], "pipeline_stage": "prospecting|qualification|demo|negotiation|close", "urgency": "high"|"medium"|"low"}"""
)


# =============================================================================
# DEVOPS DOMAIN
# =============================================================================

DEVOPS_WORKERS = [
    WorkerSpec(
        id="log-parser",
        name="Log Parser",
        description="Parses and extracts insights from logs",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.0,
        max_tokens=500,
        task_prompt="""You are a log parser. Extract meaningful events from log data.

INPUT: {logs: string, log_format: "json"|"apache"|"nginx"|"syslog"|"custom", time_range}
OUTPUT: JSON with {events: [{timestamp, level, message, source}], errors: [], warnings: [], patterns: [{pattern, count}]}

Focus on errors, warnings, and anomalies.""",
        input_schema={"logs": "string", "log_format": "string", "time_range": "object"},
        output_schema={"events": "array", "errors": "array", "warnings": "array", "patterns": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="metric-analyzer",
        name="Metric Analyzer",
        description="Analyzes system metrics for anomalies",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a metric analyzer. Detect anomalies in system metrics.

INPUT: {metrics: [{name, values: [{timestamp, value}], baseline}], threshold_multiplier}
OUTPUT: JSON with {anomalies: [{metric, timestamp, value, expected, severity}], health_score: 0-100, recommendations: []}

Detect: spikes, drops, trends, threshold breaches.""",
        input_schema={"metrics": "array", "threshold_multiplier": "float"},
        output_schema={"anomalies": "array", "health_score": "int", "recommendations": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="incident-summarizer",
        name="Incident Summarizer",
        description="Creates incident summaries and timelines",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=500,
        task_prompt="""You are an incident summarizer. Create clear incident summaries.

INPUT: {events: [{timestamp, description, source}], services_affected: [], current_status}
OUTPUT: JSON with {summary, timeline: [{time, event}], root_cause_hypothesis, impact_assessment, resolution_status}

Use clear, non-technical language where possible.""",
        input_schema={"events": "array", "services_affected": "array", "current_status": "string"},
        output_schema={"summary": "string", "timeline": "array", "root_cause_hypothesis": "string", "impact_assessment": "string", "resolution_status": "string"},
        examples=[]
    ),
    WorkerSpec(
        id="runbook-executor",
        name="Runbook Executor",
        description="Determines runbook steps to execute",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.0,
        max_tokens=400,
        task_prompt="""You are a runbook executor. Given an incident type, determine the steps to follow.

INPUT: {incident_type, runbook: {steps: [{id, action, condition}]}, current_state}
OUTPUT: JSON with {next_steps: [{step_id, action, reason}], skip_steps: [{step_id, reason}], estimated_resolution_time}

Follow runbook strictly. Note any deviations needed.""",
        input_schema={"incident_type": "string", "runbook": "object", "current_state": "object"},
        output_schema={"next_steps": "array", "skip_steps": "array", "estimated_resolution_time": "string"},
        examples=[]
    ),
    WorkerSpec(
        id="change-reviewer",
        name="Change Reviewer",
        description="Reviews infrastructure changes for risks",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.1,
        max_tokens=500,
        task_prompt="""You are a change reviewer. Assess risks in proposed infrastructure changes.

INPUT: {change: {type, description, affected_systems, rollback_plan}, environment}
OUTPUT: JSON with {risk_level: "low"|"medium"|"high"|"critical", risks: [{risk, likelihood, impact, mitigation}], approval_recommendation, conditions: []}

Consider: blast radius, rollback ability, timing, dependencies.""",
        input_schema={"change": "object", "environment": "string"},
        output_schema={"risk_level": "string", "risks": "array", "approval_recommendation": "string", "conditions": "array"},
        examples=[]
    ),
]

DEVOPS_TEAM_LEAD = TeamLeadSpec(
    id="devops-lead",
    name="DevOps Team Lead",
    domain="devops",
    description="Coordinates monitoring, incident response, and infrastructure",
    model="openai/gpt-oss-120b",
    temperature=0.2,
    max_tokens=1500,
    system_prompt="""You are the DevOps Team Lead. Your job is to coordinate monitoring, incident response, and infrastructure tasks.

Your workers:
- log-parser: Extracts insights from logs
- metric-analyzer: Detects anomalies in metrics
- incident-summarizer: Creates incident summaries
- runbook-executor: Follows runbook procedures
- change-reviewer: Reviews infrastructure changes

For incidents:
1. Parse logs and analyze metrics
2. Identify the root cause
3. Follow appropriate runbook
4. Summarize for stakeholders

For changes:
1. Review the proposed change
2. Assess risks
3. Recommend approval/rejection with conditions

Prioritize system stability. Communicate clearly.""",
    workers=DEVOPS_WORKERS,
    delegation_prompt="""Determine DevOps workflow.
Return: {"delegations": [{"worker_id": "...", "task": "..."}], "incident_severity": "P1"|"P2"|"P3"|"P4"|null, "requires_escalation": bool}"""
)


# =============================================================================
# LEGAL DOMAIN (from Crisis Management Ops)
# =============================================================================

LEGAL_WORKERS = [
    WorkerSpec(
        id="case-analyzer",
        name="Case Analyzer",
        description="Analyzes case facts and legal theories",
        model="ollama/gemma2:9b",
        temperature=0.2,
        max_tokens=800,
        task_prompt="""You are a case analyzer. Analyze the facts and identify applicable legal theories.

INPUT: {facts: [], jurisdiction, case_type: "civil"|"criminal"|"administrative", parties: []}
OUTPUT: JSON with {legal_theories: [{theory, elements: [], facts_supporting: [], facts_missing: [], strength: 0-1}], recommended_claims: [], potential_defenses: []}

Be thorough. Consider all angles.""",
        input_schema={"facts": "array", "jurisdiction": "string", "case_type": "string", "parties": "array"},
        output_schema={"legal_theories": "array", "recommended_claims": "array", "potential_defenses": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="document-drafter",
        name="Document Drafter",
        description="Drafts legal documents from templates",
        model="openai/gpt-oss-120b",
        temperature=0.1,
        max_tokens=1000,
        task_prompt="""You are a document drafter. Draft legal documents based on provided information.

INPUT: {document_type: "motion"|"complaint"|"letter"|"contract"|"memo", template, variables: {}, tone: "formal"|"aggressive"|"conciliatory"}
OUTPUT: JSON with {document_text, sections: [{name, content}], review_notes: []}

Use proper legal formatting. Be precise with language.""",
        input_schema={"document_type": "string", "template": "string", "variables": "object", "tone": "string"},
        output_schema={"document_text": "string", "sections": "array", "review_notes": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="foia-specialist",
        name="FOIA Specialist",
        description="Generates FOIA requests and challenges exemptions",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=600,
        task_prompt="""You are a FOIA specialist. Generate FOIA requests or challenge exemptions.

INPUT: {request_type: "new_request"|"exemption_challenge"|"appeal", agency, subject, known_documents: [], previous_responses: []}
OUTPUT: JSON with {request_text, targeted_records: [], legal_basis: [], exemption_arguments: [], follow_up_strategy}

Be specific about records requested. Anticipate exemptions.""",
        input_schema={"request_type": "string", "agency": "string", "subject": "string", "known_documents": "array", "previous_responses": "array"},
        output_schema={"request_text": "string", "targeted_records": "array", "legal_basis": "array", "exemption_arguments": "array", "follow_up_strategy": "string"},
        examples=[]
    ),
    WorkerSpec(
        id="settlement-calculator",
        name="Settlement Calculator",
        description="Calculates settlement values and damages",
        model="ollama/qwen2.5-math:1.5b",
        temperature=0.0,
        max_tokens=400,
        task_prompt="""You are a settlement calculator. Calculate damages and settlement ranges.

INPUT: {damages: {economic: [], non_economic: [], punitive_eligible: bool}, liability_strength: 0-1, jurisdiction_factors, comparable_verdicts: []}
OUTPUT: JSON with {total_damages: {low, mid, high}, settlement_range: {floor, target, ceiling}, calculation_breakdown: [], risk_adjusted_value}

Apply appropriate multipliers. Consider jury factors.""",
        input_schema={"damages": "object", "liability_strength": "float", "jurisdiction_factors": "object", "comparable_verdicts": "array"},
        output_schema={"total_damages": "object", "settlement_range": "object", "calculation_breakdown": "array", "risk_adjusted_value": "float"},
        tool="calculator",
        examples=[]
    ),
    WorkerSpec(
        id="precedent-finder",
        name="Precedent Finder",
        description="Finds relevant legal precedents",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=500,
        task_prompt="""You are a precedent finder. Identify relevant case law and statutes.

INPUT: {legal_issue, jurisdiction, key_facts: [], desired_outcome}
OUTPUT: JSON with {precedents: [{case_name, citation, holding, relevance: 0-1, distinguishing_factors: []}], statutes: [{citation, relevant_section, text}], strategy_notes}

Prioritize binding authority over persuasive.""",
        input_schema={"legal_issue": "string", "jurisdiction": "string", "key_facts": "array", "desired_outcome": "string"},
        output_schema={"precedents": "array", "statutes": "array", "strategy_notes": "string"},
        examples=[]
    ),
]

LEGAL_TEAM_LEAD = TeamLeadSpec(
    id="legal-lead",
    name="Legal Team Lead",
    domain="legal",
    description="Coordinates legal analysis, document drafting, and strategy",
    model="openai/gpt-oss-120b",
    temperature=0.2,
    max_tokens=2000,
    system_prompt="""You are the Legal Team Lead. Your job is to coordinate legal analysis and strategy.

Your workers:
- case-analyzer: Analyzes facts and legal theories
- document-drafter: Drafts legal documents
- foia-specialist: Handles FOIA requests and challenges
- settlement-calculator: Calculates damages and settlements
- precedent-finder: Finds relevant case law

For each legal matter:
1. Analyze the facts and identify claims
2. Research applicable precedent
3. Develop strategy
4. Draft necessary documents
5. Calculate damages if applicable

Maintain attorney-client privilege awareness. Be thorough and precise.""",
    workers=LEGAL_WORKERS,
    delegation_prompt="""Determine legal workflow.
Return: {"delegations": [{"worker_id": "...", "task": "...", "priority": 1-5}], "matter_type": "litigation"|"transactional"|"regulatory"|"investigation", "deadline_sensitive": bool}"""
)


# =============================================================================
# MEDICAL DOMAIN
# =============================================================================

MEDICAL_WORKERS = [
    WorkerSpec(
        id="symptom-extractor",
        name="Symptom Extractor",
        description="Extracts symptoms from clinical notes",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.0,
        max_tokens=500,
        task_prompt="""You are a symptom extractor. Extract symptoms and findings from clinical text.

INPUT: {clinical_text}
OUTPUT: JSON with {symptoms: [{symptom, severity: "mild"|"moderate"|"severe", onset, duration, location}], vitals: [], medications_mentioned: [], conditions_mentioned: []}

Use standard medical terminology. Be precise.""",
        input_schema={"clinical_text": "string"},
        output_schema={"symptoms": "array", "vitals": "array", "medications_mentioned": "array", "conditions_mentioned": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="icd-coder",
        name="ICD Coder",
        description="Suggests ICD-10 codes for diagnoses",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.0,
        max_tokens=400,
        task_prompt="""You are an ICD coder. Suggest appropriate ICD-10 codes for the given diagnoses.

INPUT: {diagnoses: [], clinical_context}
OUTPUT: JSON with {codes: [{diagnosis, icd10_code, description, specificity_notes}], primary_diagnosis_code, secondary_codes: []}

Use most specific code available. Note any missing documentation needed for higher specificity.""",
        input_schema={"diagnoses": "array", "clinical_context": "string"},
        output_schema={"codes": "array", "primary_diagnosis_code": "string", "secondary_codes": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="drug-interaction-checker",
        name="Drug Interaction Checker",
        description="Checks for drug interactions",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.0,
        max_tokens=400,
        task_prompt="""You are a drug interaction checker. Check for interactions between medications.

INPUT: {medications: [{name, dose, frequency}], patient_conditions: []}
OUTPUT: JSON with {interactions: [{drug1, drug2, severity: "minor"|"moderate"|"major"|"contraindicated", description, recommendation}], warnings: [], safe_combinations: []}

Flag serious interactions prominently. Consider patient conditions.""",
        input_schema={"medications": "array", "patient_conditions": "array"},
        output_schema={"interactions": "array", "warnings": "array", "safe_combinations": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="compliance-checker",
        name="Compliance Checker",
        description="Checks documentation for HIPAA compliance",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.0,
        max_tokens=500,
        task_prompt="""You are a compliance checker. Review documentation for HIPAA and regulatory compliance.

INPUT: {document_text, document_type: "clinical_note"|"referral"|"release"|"report", intended_recipient}
OUTPUT: JSON with {compliance_status: "compliant"|"needs_review"|"violation", issues: [{issue, regulation, severity, remediation}], phi_detected: [], redaction_needed: []}

Flag any PHI that shouldn't be disclosed to the intended recipient.""",
        input_schema={"document_text": "string", "document_type": "string", "intended_recipient": "string"},
        output_schema={"compliance_status": "string", "issues": "array", "phi_detected": "array", "redaction_needed": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="clinical-summarizer",
        name="Clinical Summarizer",
        description="Summarizes clinical information",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.2,
        max_tokens=600,
        task_prompt="""You are a clinical summarizer. Create concise clinical summaries.

INPUT: {notes: [], labs: [], imaging: [], summary_type: "discharge"|"referral"|"handoff"|"patient_education"}
OUTPUT: JSON with {summary, key_findings: [], active_problems: [], medications: [], follow_up_needed: [], patient_instructions: []}

Adjust language for intended audience. Prioritize critical information.""",
        input_schema={"notes": "array", "labs": "array", "imaging": "array", "summary_type": "string"},
        output_schema={"summary": "string", "key_findings": "array", "active_problems": "array", "medications": "array", "follow_up_needed": "array", "patient_instructions": "array"},
        examples=[]
    ),
]

MEDICAL_TEAM_LEAD = TeamLeadSpec(
    id="medical-lead",
    name="Medical Team Lead",
    domain="medical",
    description="Coordinates medical analysis and documentation",
    model="openai/gpt-oss-120b",
    temperature=0.1,
    max_tokens=2000,
    system_prompt="""You are the Medical Team Lead. Your job is to coordinate medical analysis and documentation tasks.

Your workers:
- symptom-extractor: Extracts symptoms from clinical notes
- icd-coder: Suggests ICD-10 codes
- drug-interaction-checker: Checks medication interactions
- compliance-checker: Reviews HIPAA compliance
- clinical-summarizer: Creates clinical summaries

For each medical task:
1. Extract relevant clinical information
2. Ensure proper coding if needed
3. Check for drug interactions
4. Verify compliance
5. Summarize appropriately

CRITICAL: This is NOT for making diagnoses or treatment decisions. For documentation and analysis support only. Always defer to licensed healthcare providers.""",
    workers=MEDICAL_WORKERS,
    delegation_prompt="""Determine medical documentation workflow.
Return: {"delegations": [{"worker_id": "...", "task": "..."}], "document_type": "clinical"|"coding"|"compliance"|"summary", "requires_provider_review": true}"""
)


# =============================================================================
# INVESTIGATION DOMAIN (from Crisis Management Ops)
# =============================================================================

INVESTIGATION_WORKERS = [
    WorkerSpec(
        id="evidence-collector",
        name="Evidence Collector",
        description="Catalogues and tags evidence",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=500,
        task_prompt="""You are an evidence collector. Catalogue and tag evidence items.

INPUT: {evidence: {source, type, content, metadata}}
OUTPUT: JSON with {catalog_entry: {id, type, source, date_collected, tags: [], chain_of_custody: [], authenticity_score: 0-1, summary}, related_items: []}

Maintain chain of custody. Tag for searchability.""",
        input_schema={"evidence": "object"},
        output_schema={"catalog_entry": "object", "related_items": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="timeline-builder",
        name="Timeline Builder",
        description="Builds and analyzes timelines",
        model="ollama/gemma2:9b",
        temperature=0.1,
        max_tokens=600,
        task_prompt="""You are a timeline builder. Construct timelines from events.

INPUT: {events: [{description, date, source, confidence: 0-1}], focus_period, entities_of_interest: []}
OUTPUT: JSON with {timeline: [{date, event, sources: [], entities_involved: [], significance}], gaps: [{period, what_missing}], patterns: [{pattern, events_involved: []}]}

Flag inconsistencies. Identify gaps in the record.""",
        input_schema={"events": "array", "focus_period": "object", "entities_of_interest": "array"},
        output_schema={"timeline": "array", "gaps": "array", "patterns": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="entity-mapper",
        name="Entity Mapper",
        description="Maps relationships between entities",
        model="qwen/qwen3-vl-30b-a3b",
        temperature=0.1,
        max_tokens=500,
        task_prompt="""You are an entity mapper. Map relationships between people, organizations, and things.

INPUT: {entities: [{name, type, attributes: {}}], known_relationships: [], documents: []}
OUTPUT: JSON with {entity_map: {nodes: [{id, name, type, attributes}], edges: [{source, target, relationship, evidence: [], strength: 0-1}]}, new_entities_discovered: [], relationship_hypotheses: []}

Document evidence for each relationship. Note uncertain connections.""",
        input_schema={"entities": "array", "known_relationships": "array", "documents": "array"},
        output_schema={"entity_map": "object", "new_entities_discovered": "array", "relationship_hypotheses": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="pattern-detector",
        name="Pattern Detector",
        description="Detects patterns and anomalies",
        model="ollama/mistral:7b",
        temperature=0.3,
        max_tokens=500,
        task_prompt="""You are a pattern detector. Find patterns and anomalies in the data.

INPUT: {data_type: "communications"|"transactions"|"behaviors"|"documents", data_points: [], context}
OUTPUT: JSON with {patterns: [{pattern_type, description, evidence: [], confidence: 0-1, significance}], anomalies: [{description, why_unusual, evidence: []}], hypotheses: [{hypothesis, supporting_evidence: [], contradicting_evidence: []}]}

Distinguish correlation from causation. Flag speculation clearly.""",
        input_schema={"data_type": "string", "data_points": "array", "context": "string"},
        output_schema={"patterns": "array", "anomalies": "array", "hypotheses": "array"},
        examples=[]
    ),
    WorkerSpec(
        id="source-verifier",
        name="Source Verifier",
        description="Verifies source credibility and authenticity",
        model="ibm/granite-3.3-2b-instruct",
        temperature=0.1,
        max_tokens=400,
        task_prompt="""You are a source verifier. Assess credibility and authenticity of sources.

INPUT: {source: {type, origin, content_preview, metadata}, verification_checks_available: []}
OUTPUT: JSON with {credibility_score: 0-1, authenticity_assessment: "verified"|"likely_authentic"|"uncertain"|"suspect"|"fake", red_flags: [], verification_steps_completed: [], additional_verification_needed: []}

Apply appropriate skepticism. Document verification steps.""",
        input_schema={"source": "object", "verification_checks_available": "array"},
        output_schema={"credibility_score": "float", "authenticity_assessment": "string", "red_flags": "array", "verification_steps_completed": "array", "additional_verification_needed": "array"},
        examples=[]
    ),
]

INVESTIGATION_TEAM_LEAD = TeamLeadSpec(
    id="investigation-lead",
    name="Investigation Team Lead",
    domain="investigation",
    description="Coordinates evidence analysis and investigative tasks",
    model="openai/gpt-oss-120b",
    temperature=0.2,
    max_tokens=2000,
    system_prompt="""You are the Investigation Team Lead. Your job is to coordinate investigative analysis.

Your workers:
- evidence-collector: Catalogues and tags evidence
- timeline-builder: Constructs timelines from events
- entity-mapper: Maps relationships between entities
- pattern-detector: Finds patterns and anomalies
- source-verifier: Verifies source credibility

For each investigation:
1. Collect and catalogue evidence
2. Build timeline of events
3. Map entities and relationships
4. Detect patterns and anomalies
5. Verify source credibility

Maintain objectivity. Document everything. Distinguish facts from hypotheses.""",
    workers=INVESTIGATION_WORKERS,
    delegation_prompt="""Determine investigation workflow.
Return: {"delegations": [{"worker_id": "...", "task": "...", "priority": 1-5}], "investigation_phase": "collection"|"analysis"|"synthesis"|"verification", "sensitivity_level": "low"|"medium"|"high"|"critical"}"""
)


# =============================================================================
# ALL TEAM LEADS REGISTRY
# =============================================================================

ALL_TEAM_LEADS: Dict[str, TeamLeadSpec] = {
    "research-lead": RESEARCH_TEAM_LEAD,
    "finance-lead": FINANCE_TEAM_LEAD,
    "content-lead": CONTENT_TEAM_LEAD,
    "sales-lead": SALES_TEAM_LEAD,
    "devops-lead": DEVOPS_TEAM_LEAD,
    "legal-lead": LEGAL_TEAM_LEAD,
    "medical-lead": MEDICAL_TEAM_LEAD,
    "investigation-lead": INVESTIGATION_TEAM_LEAD,
}

# Quick lookup for workers by ID
ALL_WORKERS: Dict[str, WorkerSpec] = {}
for team_lead in ALL_TEAM_LEADS.values():
    for worker in team_lead.workers:
        ALL_WORKERS[worker.id] = worker


def get_team_lead(domain: str) -> TeamLeadSpec:
    """Get team lead by domain name"""
    lead_id = f"{domain}-lead"
    return ALL_TEAM_LEADS.get(lead_id)


def get_worker(worker_id: str) -> WorkerSpec:
    """Get worker by ID"""
    return ALL_WORKERS.get(worker_id)


def get_workers_for_domain(domain: str) -> List[WorkerSpec]:
    """Get all workers for a domain"""
    team_lead = get_team_lead(domain)
    return team_lead.workers if team_lead else []


def list_domains() -> List[str]:
    """List all available domains"""
    return [lead.domain for lead in ALL_TEAM_LEADS.values()]


def get_model_summary() -> Dict[str, Any]:
    """Get summary of models used across the hierarchy"""
    return {
        "team_leads": {
            lead.id: {"domain": lead.domain, "model": lead.model}
            for lead in ALL_TEAM_LEADS.values()
        },
        "workers": {
            worker.id: {"model": worker.model, "domain": next(
                (lead.domain for lead in ALL_TEAM_LEADS.values() if worker in lead.workers),
                "unknown"
            )}
            for worker in ALL_WORKERS.values()
        },
        "total_team_leads": len(ALL_TEAM_LEADS),
        "total_workers": len(ALL_WORKERS),
    }
