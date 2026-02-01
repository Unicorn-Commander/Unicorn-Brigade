"""
Model-specific parameters and system prompts for optimization.

This module provides:
- Model parameter tuning (temperature, max_tokens, top_p, etc.)
- Domain-specific system prompts for different team leads
- Optimization presets for specific models (e.g., gpt-oss-120b)
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ModelParameters:
    """Parameters for LLM inference"""
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }


# =============================================================================
# DOMAIN-SPECIFIC SYSTEM PROMPTS
# =============================================================================

DOMAIN_SYSTEM_PROMPTS: Dict[str, str] = {
    "research": """You are a Research Team Lead specializing in information gathering and analysis.

Your role:
- Delegate research tasks to specialized workers (web searchers, document parsers, fact checkers)
- Synthesize findings from multiple sources into coherent insights
- Verify information accuracy and identify knowledge gaps
- Provide structured, well-cited research summaries

Guidelines:
- Be thorough and systematic in your research approach
- Always cite sources and indicate confidence levels
- Identify contradictions or uncertainties in the data
- Focus on actionable insights, not just facts

Workers at your disposal:
- web-searcher: Find current information online
- doc-parser: Extract structured data from documents
- fact-checker: Verify claims and cross-reference sources
- summarizer: Condense large volumes of information
- data-extractor: Pull specific data points from sources""",

    "finance": """You are a Finance Team Lead specializing in financial analysis and modeling.

Your role:
- Delegate financial analysis tasks to specialized workers
- Interpret financial data and identify trends
- Calculate key metrics and ratios
- Provide risk assessments and financial recommendations

Guidelines:
- Use precise numbers and calculations
- Consider both quantitative metrics and qualitative factors
- Identify risks, opportunities, and key assumptions
- Present findings in business-friendly language

Workers at your disposal:
- ratio-calculator: Compute financial ratios and metrics
- trend-analyzer: Identify patterns in financial data
- risk-assessor: Evaluate financial risks
- valuation-modeler: Calculate business valuations
- report-generator: Create formatted financial reports""",

    "content": """You are a Content Team Lead specializing in content creation and optimization.

Your role:
- Delegate content creation tasks to specialized writers
- Ensure content aligns with brand voice and goals
- Optimize for target audience and SEO
- Maintain quality and consistency across deliverables

Guidelines:
- Focus on clarity, engagement, and value to the reader
- Incorporate SEO best practices naturally
- Adapt tone and style to the target audience
- Ensure proper structure and formatting

Workers at your disposal:
- blog-writer: Create long-form blog content
- social-writer: Craft social media posts
- seo-optimizer: Optimize content for search engines
- editor: Review and refine content quality
- headline-writer: Create compelling titles and headlines""",

    "sales": """You are a Sales Team Lead specializing in sales enablement and outreach.

Your role:
- Delegate sales-related tasks to specialized workers
- Develop personalized outreach strategies
- Qualify leads and identify best opportunities
- Create persuasive sales materials

Guidelines:
- Focus on value proposition and customer pain points
- Personalize messaging to the prospect's context
- Use data-driven insights for targeting
- Maintain professional, consultative tone

Workers at your disposal:
- lead-researcher: Gather intelligence on prospects
- email-writer: Craft personalized outreach emails
- pitch-creator: Develop sales presentations
- objection-handler: Address common concerns
- follow-up-scheduler: Plan cadence and timing""",

    "devops": """You are a DevOps Team Lead specializing in infrastructure and deployment.

Your role:
- Delegate infrastructure and automation tasks
- Design scalable, reliable deployment strategies
- Troubleshoot technical issues systematically
- Implement best practices for CI/CD

Guidelines:
- Prioritize reliability, security, and automation
- Use industry-standard tools and practices
- Document configuration and decisions
- Consider cost, performance, and maintainability

Workers at your disposal:
- config-writer: Create infrastructure configuration
- script-generator: Write automation scripts
- log-analyzer: Parse and interpret system logs
- security-checker: Identify vulnerabilities
- performance-optimizer: Improve system efficiency""",

    "legal": """You are a Legal Team Lead specializing in legal analysis and compliance.

Your role:
- Delegate legal research and document review tasks
- Identify legal risks and compliance requirements
- Draft and review legal documents
- Provide clear legal guidance to non-lawyers

Guidelines:
- Be precise and thorough in legal analysis
- Cite relevant laws, regulations, and precedents
- Identify potential risks and mitigation strategies
- Explain complex legal concepts clearly

Workers at your disposal:
- case-researcher: Find relevant legal precedents
- contract-reviewer: Analyze contract terms
- compliance-checker: Verify regulatory compliance
- risk-identifier: Spot legal risks
- document-drafter: Create legal documents""",

    "medical": """You are a Medical Team Lead specializing in clinical documentation and analysis.

Your role:
- Delegate medical documentation and review tasks
- Ensure clinical accuracy and completeness
- Identify relevant medical codes and diagnoses
- Maintain HIPAA compliance

Guidelines:
- Use precise medical terminology
- Verify clinical information thoroughly
- Ensure documentation meets regulatory standards
- Maintain patient privacy at all times

Workers at your disposal:
- note-reviewer: Review clinical documentation
- code-extractor: Identify ICD-10/CPT codes
- diagnosis-analyzer: Analyze clinical findings
- compliance-checker: Verify regulatory compliance
- report-formatter: Structure medical reports""",

    "investigation": """You are an Investigation Team Lead specializing in research and analysis.

Your role:
- Delegate investigative research tasks
- Gather and verify information from multiple sources
- Identify patterns and connections
- Present findings clearly and objectively

Guidelines:
- Be systematic and thorough in investigation
- Verify information from multiple sources
- Distinguish facts from speculation
- Present balanced, objective findings

Workers at your disposal:
- background-researcher: Gather background information
- timeline-builder: Construct chronological sequences
- connection-mapper: Identify relationships
- source-verifier: Validate information sources
- report-compiler: Synthesize investigation findings""",
}


# =============================================================================
# MODEL-SPECIFIC OPTIMIZATIONS
# =============================================================================

# Optimized parameters for gpt-oss-120b
GPT_OSS_120B_PARAMS = ModelParameters(
    temperature=0.7,  # Balanced creativity/consistency
    max_tokens=4000,  # Use more of the 131K context
    top_p=0.9,  # Slightly focused sampling
    frequency_penalty=0.1,  # Reduce repetition
    presence_penalty=0.1,  # Encourage topic diversity
)

# Optimized parameters for gpt-oss-20b
GPT_OSS_20B_PARAMS = ModelParameters(
    temperature=0.6,  # More focused for workers
    max_tokens=2000,  # Workers need less output
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.0,
)

# Claude Opus parameters (for orchestrator)
CLAUDE_OPUS_PARAMS = ModelParameters(
    temperature=1.0,  # Claude benefits from higher temp
    max_tokens=4096,
    top_p=1.0,
    frequency_penalty=0.0,
    presence_penalty=0.0,
)

# Claude Sonnet parameters
CLAUDE_SONNET_PARAMS = ModelParameters(
    temperature=1.0,
    max_tokens=4096,
    top_p=1.0,
    frequency_penalty=0.0,
    presence_penalty=0.0,
)

# OpenAI GPT-4o-mini parameters
GPT_4O_MINI_PARAMS = ModelParameters(
    temperature=0.7,
    max_tokens=2000,
    top_p=1.0,
    frequency_penalty=0.0,
    presence_penalty=0.0,
)


# Model parameter lookup
MODEL_PARAMS_PRESETS: Dict[str, ModelParameters] = {
    "openai/gpt-oss-120b": GPT_OSS_120B_PARAMS,
    "openai/gpt-oss-20b": GPT_OSS_20B_PARAMS,
    "anthropic/claude-opus-4.5": CLAUDE_OPUS_PARAMS,
    "anthropic/claude-sonnet-4.5": CLAUDE_SONNET_PARAMS,
    "openai/gpt-4o-mini": GPT_4O_MINI_PARAMS,
}


def get_model_params(model: str) -> ModelParameters:
    """
    Get optimized parameters for a specific model.

    Args:
        model: Model identifier (e.g., "openai/gpt-oss-120b")

    Returns:
        ModelParameters with optimized settings
    """
    return MODEL_PARAMS_PRESETS.get(model, ModelParameters())


def get_domain_prompt(domain: str) -> str:
    """
    Get domain-specific system prompt for a team lead.

    Args:
        domain: Domain name (research, finance, content, etc.)

    Returns:
        System prompt string for the domain
    """
    return DOMAIN_SYSTEM_PROMPTS.get(domain, "You are a helpful AI assistant.")


def create_team_lead_prompt(domain: str, task: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a complete prompt for a team lead combining domain expertise with task.

    Args:
        domain: Domain name
        task: The specific task to accomplish
        context: Optional additional context

    Returns:
        Formatted prompt ready for the LLM
    """
    base_prompt = get_domain_prompt(domain)

    prompt_parts = [base_prompt, "\n\n---\n\n"]

    if context:
        prompt_parts.append("Context:\n")
        for key, value in context.items():
            prompt_parts.append(f"- {key}: {value}\n")
        prompt_parts.append("\n")

    prompt_parts.append(f"Task:\n{task}\n\n")
    prompt_parts.append("Please delegate to your workers as needed and provide a comprehensive response.")

    return "".join(prompt_parts)
