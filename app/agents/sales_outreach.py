"""
Multi-Agent Sales Outreach System

Coordinated agents for:
1. Lead Enrichment - Research prospects via web search
2. Personalization - Craft personalized messages
3. Sequence Management - Multi-step email cadences
4. Response Handling - Process replies and book meetings

Architecture follows the Brigade pattern with specialized agents
coordinated by a SalesOutreachOrchestrator.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import re

from app.agents.base import BaseAgent
from app.llm.ops_center_client import (
    OpsCenterLLMClient,
    ToolDefinition,
    ToolParameter,
    ToolCall,
    ToolResult,
)
from app.llm.builtin_tools import web_search_handler, WEB_SEARCH_TOOL
from app.llm.extended_tools import email_handler, EMAIL_TOOL

logger = logging.getLogger(__name__)


# ============== Data Models ==============

class LeadStatus(Enum):
    """Lead status in the sales pipeline"""
    NEW = "new"
    ENRICHED = "enriched"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING_SCHEDULED = "meeting_scheduled"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"


class SequenceStepType(Enum):
    """Types of sequence steps"""
    EMAIL = "email"
    FOLLOW_UP = "follow_up"
    LINKEDIN = "linkedin"
    CALL = "call"
    TASK = "task"


@dataclass
class Lead:
    """Sales lead with enriched data"""
    id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: str = ""
    status: LeadStatus = LeadStatus.NEW

    # Enrichment data
    company_info: Dict[str, Any] = field(default_factory=dict)
    social_profiles: Dict[str, str] = field(default_factory=dict)
    pain_points: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    recent_news: List[Dict[str, str]] = field(default_factory=list)

    # Personalization data
    personalization_context: Dict[str, Any] = field(default_factory=dict)

    # Sequence tracking
    current_sequence: Optional[str] = None
    sequence_step: int = 0
    last_contacted: Optional[datetime] = None

    # Response tracking
    has_replied: bool = False
    reply_sentiment: Optional[str] = None
    meeting_booked: bool = False

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "title": self.title,
            "status": self.status.value,
            "company_info": self.company_info,
            "social_profiles": self.social_profiles,
            "pain_points": self.pain_points,
            "triggers": self.triggers,
            "recent_news": self.recent_news,
            "personalization_context": self.personalization_context,
            "current_sequence": self.current_sequence,
            "sequence_step": self.sequence_step,
            "last_contacted": self.last_contacted.isoformat() if self.last_contacted else None,
            "has_replied": self.has_replied,
            "reply_sentiment": self.reply_sentiment,
            "meeting_booked": self.meeting_booked,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "custom_fields": self.custom_fields,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        """Create from dictionary"""
        lead = cls(
            id=data.get("id", str(uuid.uuid4())),
            email=data["email"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            company=data.get("company", ""),
            title=data.get("title", ""),
        )
        lead.status = LeadStatus(data.get("status", "new"))
        lead.company_info = data.get("company_info", {})
        lead.social_profiles = data.get("social_profiles", {})
        lead.pain_points = data.get("pain_points", [])
        lead.triggers = data.get("triggers", [])
        lead.recent_news = data.get("recent_news", [])
        lead.personalization_context = data.get("personalization_context", {})
        lead.current_sequence = data.get("current_sequence")
        lead.sequence_step = data.get("sequence_step", 0)
        lead.tags = data.get("tags", [])
        lead.custom_fields = data.get("custom_fields", {})
        return lead


@dataclass
class SequenceStep:
    """A step in an email sequence"""
    id: str
    step_number: int
    type: SequenceStepType
    delay_days: int  # Days after previous step
    template: str
    subject: str
    variant: str = "A"  # For A/B testing

    # Tracking
    sent_count: int = 0
    open_count: int = 0
    click_count: int = 0
    reply_count: int = 0


@dataclass
class EmailSequence:
    """Email outreach sequence"""
    id: str
    name: str
    description: str
    campaign_id: str
    steps: List[SequenceStep] = field(default_factory=list)
    stop_on_reply: bool = True
    track_opens: bool = True
    track_clicks: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "campaign_id": self.campaign_id,
            "steps": [
                {
                    "id": s.id,
                    "step_number": s.step_number,
                    "type": s.type.value,
                    "delay_days": s.delay_days,
                    "template": s.template,
                    "subject": s.subject,
                    "variant": s.variant,
                    "sent_count": s.sent_count,
                    "open_count": s.open_count,
                    "click_count": s.click_count,
                    "reply_count": s.reply_count,
                }
                for s in self.steps
            ],
            "stop_on_reply": self.stop_on_reply,
            "track_opens": self.track_opens,
            "track_clicks": self.track_clicks,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Campaign:
    """Sales outreach campaign"""
    id: str
    name: str
    description: str
    status: str = "active"
    target_persona: str = ""
    value_proposition: str = ""
    sequences: List[str] = field(default_factory=list)  # Sequence IDs
    leads: List[str] = field(default_factory=list)  # Lead IDs
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "target_persona": self.target_persona,
            "value_proposition": self.value_proposition,
            "sequences": self.sequences,
            "leads": self.leads,
            "created_at": self.created_at.isoformat(),
        }


# ============== Specialized Agents ==============

class LeadEnrichmentAgent(BaseAgent):
    """
    Agent specializing in lead research and enrichment.

    Uses web search to:
    - Find company information
    - Identify social profiles
    - Discover pain points and triggers
    - Find recent news and events
    """

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("LeadEnrichmentAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute lead enrichment task"""
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data

        logger.info(f"Enriching lead: {lead.email} at {lead.company}")

        try:
            # Parallel enrichment tasks
            enrichment_tasks = [
                self._enrich_company(lead.company),
                self._find_social_profiles(lead.first_name, lead.last_name, lead.company),
                self._find_recent_news(lead.company),
                self._identify_pain_points(lead.company, lead.title),
            ]

            results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

            # Merge results
            company_info = results[0] if not isinstance(results[0], Exception) else {}
            social_profiles = results[1] if not isinstance(results[1], Exception) else {}
            recent_news = results[2] if not isinstance(results[2], Exception) else []
            pain_points_data = results[3] if not isinstance(results[3], Exception) else {}

            lead.company_info = company_info
            lead.social_profiles = social_profiles
            lead.recent_news = recent_news
            lead.pain_points = pain_points_data.get("pain_points", [])
            lead.triggers = pain_points_data.get("triggers", [])
            lead.status = LeadStatus.ENRICHED
            lead.updated_at = datetime.utcnow()

            return {
                "agent": self.name,
                "status": "completed",
                "lead": lead.to_dict(),
                "enrichment_summary": {
                    "company_found": bool(company_info),
                    "social_profiles_count": len(social_profiles),
                    "news_items": len(recent_news),
                    "pain_points_identified": len(lead.pain_points),
                    "triggers_identified": len(lead.triggers),
                },
            }

        except Exception as e:
            logger.error(f"Lead enrichment error: {e}")
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "lead": lead.to_dict(),
            }

    async def _enrich_company(self, company: str) -> Dict[str, Any]:
        """Research company information"""
        if not company:
            return {}

        # Search for company info
        search_result = await web_search_handler(
            query=f"{company} company overview industry size",
            num_results=3,
        )

        if not search_result.get("success"):
            return {}

        # Use LLM to extract structured data
        search_content = "\n".join([
            f"- {r.get('title', '')}: {r.get('snippet', '')}"
            for r in search_result.get("results", [])
        ])

        extraction_prompt = f"""Based on these search results about {company}, extract company information:

{search_content}

Return a JSON object with:
- industry: The company's industry
- size: Company size (startup/small/medium/large/enterprise)
- description: Brief company description
- founded: Year founded if available
- headquarters: HQ location if available
- key_products: Main products/services

Return ONLY valid JSON, no other text."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": extraction_prompt}],
            model="openai/gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
        )

        content = response["choices"][0]["message"]["content"]

        # Parse JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"description": content}

    async def _find_social_profiles(self, first_name: str, last_name: str, company: str) -> Dict[str, str]:
        """Find social media profiles"""
        if not first_name or not company:
            return {}

        search_result = await web_search_handler(
            query=f"{first_name} {last_name} {company} LinkedIn",
            num_results=3,
        )

        profiles = {}

        if search_result.get("success"):
            for result in search_result.get("results", []):
                url = result.get("url", "")
                if "linkedin.com/in/" in url:
                    profiles["linkedin"] = url
                elif "twitter.com/" in url or "x.com/" in url:
                    profiles["twitter"] = url

        return profiles

    async def _find_recent_news(self, company: str) -> List[Dict[str, str]]:
        """Find recent news about the company"""
        if not company:
            return []

        search_result = await web_search_handler(
            query=f"{company} news announcement 2024 2025",
            num_results=5,
        )

        if not search_result.get("success"):
            return []

        news = []
        for result in search_result.get("results", []):
            news.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
            })

        return news

    async def _identify_pain_points(self, company: str, title: str) -> Dict[str, List[str]]:
        """Identify potential pain points and triggers"""
        if not company:
            return {"pain_points": [], "triggers": []}

        # Search for challenges/pain points
        search_result = await web_search_handler(
            query=f"{company} challenges problems solutions",
            num_results=3,
        )

        if not search_result.get("success"):
            return {"pain_points": [], "triggers": []}

        search_content = "\n".join([
            f"- {r.get('snippet', '')}"
            for r in search_result.get("results", [])
        ])

        analysis_prompt = f"""Based on these insights about {company} and considering a typical {title or 'executive'} role:

{search_content}

Identify:
1. Pain points they might be experiencing
2. Triggers that might make them interested in new solutions

Return a JSON object with:
- pain_points: list of 3-5 specific pain points
- triggers: list of 3-5 potential triggers

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": analysis_prompt}],
            model="openai/gpt-4o-mini",
            temperature=0.4,
            max_tokens=400,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"pain_points": [], "triggers": []}


class PersonalizationAgent(BaseAgent):
    """
    Agent specializing in crafting personalized messages.

    Uses enrichment data to:
    - Create company-specific references
    - Reference recent news/events
    - Tailor value props to role
    - Support A/B testing variants
    """

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("PersonalizationAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute personalization task"""
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data
        template = task.get("template", "")
        context = task.get("context", {})
        generate_variants = task.get("generate_variants", False)

        logger.info(f"Personalizing message for: {lead.email}")

        try:
            # Build personalization context
            personalization_data = self._build_personalization_context(lead, context)

            # Generate personalized message
            message = await self._personalize_message(
                template=template,
                lead=lead,
                context=personalization_data,
            )

            result = {
                "agent": self.name,
                "status": "completed",
                "lead_id": lead.id,
                "subject": message.get("subject", ""),
                "body": message.get("body", ""),
                "personalization_tokens": message.get("tokens_used", []),
            }

            # Generate A/B variants if requested
            if generate_variants:
                variant_b = await self._generate_variant(message, lead)
                result["variant_a"] = {
                    "subject": message.get("subject"),
                    "body": message.get("body"),
                }
                result["variant_b"] = variant_b

            return result

        except Exception as e:
            logger.error(f"Personalization error: {e}")
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
            }

    def _build_personalization_context(self, lead: Lead, extra_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for personalization"""
        context = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": f"{lead.first_name} {lead.last_name}".strip(),
            "company": lead.company,
            "title": lead.title,
            "email": lead.email,
        }

        # Add company info
        if lead.company_info:
            context["industry"] = lead.company_info.get("industry", "")
            context["company_description"] = lead.company_info.get("description", "")
            context["company_size"] = lead.company_info.get("size", "")

        # Add recent news for ice breakers
        if lead.recent_news:
            context["recent_news"] = lead.recent_news[0].get("title", "")
            context["news_snippet"] = lead.recent_news[0].get("snippet", "")

        # Add pain points
        if lead.pain_points:
            context["main_pain_point"] = lead.pain_points[0]
            context["pain_points"] = lead.pain_points

        # Add triggers
        if lead.triggers:
            context["main_trigger"] = lead.triggers[0]
            context["triggers"] = lead.triggers

        # Merge extra context
        context.update(extra_context)

        return context

    async def _personalize_message(
        self,
        template: str,
        lead: Lead,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate personalized message using LLM"""

        # Build prompt for personalization
        prompt = f"""You are an expert sales copywriter. Personalize the following email template for this prospect.

PROSPECT INFORMATION:
- Name: {context.get('full_name', 'the recipient')}
- Title: {context.get('title', 'N/A')}
- Company: {context.get('company', 'N/A')}
- Industry: {context.get('industry', 'N/A')}
- Company Description: {context.get('company_description', 'N/A')}
- Recent News: {context.get('recent_news', 'N/A')}
- Main Pain Point: {context.get('main_pain_point', 'N/A')}

EMAIL TEMPLATE:
{template}

Instructions:
1. Replace placeholders with personalized content
2. Add a personalized opening referencing their company or recent news
3. Connect the value proposition to their specific pain points
4. Keep the tone professional but conversational
5. Keep the email concise (under 150 words for the body)

Return a JSON object with:
- subject: The personalized subject line
- body: The personalized email body
- tokens_used: List of personalization tokens you used (e.g., ["company_name", "recent_news"])

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-4o",  # Use better model for writing
            temperature=0.7,
            max_tokens=800,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Fallback: return raw content
        return {
            "subject": "Following up",
            "body": content,
            "tokens_used": [],
        }

    async def _generate_variant(
        self,
        original: Dict[str, Any],
        lead: Lead,
    ) -> Dict[str, Any]:
        """Generate A/B test variant"""

        prompt = f"""You are an expert sales copywriter. Create an alternative version (Variant B) of this email for A/B testing.

ORIGINAL EMAIL:
Subject: {original.get('subject', '')}
Body: {original.get('body', '')}

PROSPECT:
- Name: {lead.first_name} {lead.last_name}
- Company: {lead.company}
- Title: {lead.title}

Create a variant that:
1. Uses a different angle or hook
2. Has a different subject line style (e.g., question vs statement)
3. Maintains the same core value proposition
4. Tests a different call-to-action

Return a JSON object with:
- subject: The variant subject line
- body: The variant email body

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-4o",
            temperature=0.8,  # Higher creativity for variants
            max_tokens=600,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"subject": original.get("subject"), "body": original.get("body")}


class SequenceAgent(BaseAgent):
    """
    Agent for managing email sequences and cadences.

    Handles:
    - Multi-step email sequences
    - Configurable delays
    - Stop on reply
    - Tracking (opens/clicks)
    """

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("SequenceAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

        # In-memory sequence storage (would be database in production)
        self._sequences: Dict[str, EmailSequence] = {}
        self._lead_sequences: Dict[str, Dict[str, Any]] = {}  # lead_id -> sequence state

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sequence management task"""
        operation = task.get("operation", "create")

        if operation == "create":
            return await self._create_sequence(task)
        elif operation == "add_lead":
            return await self._add_lead_to_sequence(task)
        elif operation == "advance":
            return await self._advance_sequence(task)
        elif operation == "stop":
            return await self._stop_sequence(task)
        elif operation == "get_next_actions":
            return await self._get_next_actions(task)
        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

    async def _create_sequence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new email sequence"""
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data
        campaign = task.get("campaign", {})

        # Default sequence structure
        sequence_config = task.get("sequence_config", {})

        sequence_id = str(uuid.uuid4())

        # Build default sequence steps
        default_steps = [
            SequenceStep(
                id=f"{sequence_id}-step-1",
                step_number=1,
                type=SequenceStepType.EMAIL,
                delay_days=0,  # Send immediately
                template=sequence_config.get("initial_template", "Hi {{first_name}}, I noticed {{company}} and wanted to reach out..."),
                subject=sequence_config.get("initial_subject", "Quick question about {{company}}"),
            ),
            SequenceStep(
                id=f"{sequence_id}-step-2",
                step_number=2,
                type=SequenceStepType.FOLLOW_UP,
                delay_days=3,  # 3 days after step 1
                template=sequence_config.get("followup_1_template", "Hi {{first_name}}, I wanted to follow up on my previous email..."),
                subject=sequence_config.get("followup_1_subject", "Re: Quick question about {{company}}"),
            ),
            SequenceStep(
                id=f"{sequence_id}-step-3",
                step_number=3,
                type=SequenceStepType.FOLLOW_UP,
                delay_days=7,  # 7 days after step 2
                template=sequence_config.get("followup_2_template", "Hi {{first_name}}, I understand you're busy. Just wanted to share one more thought..."),
                subject=sequence_config.get("followup_2_subject", "One more thought for {{company}}"),
            ),
        ]

        # Override with custom steps if provided
        custom_steps = sequence_config.get("steps", [])
        if custom_steps:
            default_steps = [
                SequenceStep(
                    id=f"{sequence_id}-step-{i+1}",
                    step_number=i + 1,
                    type=SequenceStepType(s.get("type", "email")),
                    delay_days=s.get("delay_days", i * 3),
                    template=s.get("template", ""),
                    subject=s.get("subject", ""),
                    variant=s.get("variant", "A"),
                )
                for i, s in enumerate(custom_steps)
            ]

        sequence = EmailSequence(
            id=sequence_id,
            name=sequence_config.get("name", f"Sequence for {lead.company}"),
            description=sequence_config.get("description", ""),
            campaign_id=campaign.get("id", ""),
            steps=default_steps,
            stop_on_reply=sequence_config.get("stop_on_reply", True),
            track_opens=sequence_config.get("track_opens", True),
            track_clicks=sequence_config.get("track_clicks", True),
        )

        self._sequences[sequence_id] = sequence

        # Initialize lead sequence state
        self._lead_sequences[lead.id] = {
            "sequence_id": sequence_id,
            "current_step": 0,
            "started_at": datetime.utcnow().isoformat(),
            "next_action_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        lead.current_sequence = sequence_id
        lead.sequence_step = 0

        logger.info(f"Created sequence {sequence_id} for lead {lead.id}")

        return {
            "agent": self.name,
            "status": "completed",
            "sequence": sequence.to_dict(),
            "lead": lead.to_dict(),
            "next_action": {
                "step": 1,
                "type": "email",
                "scheduled_at": datetime.utcnow().isoformat(),
            },
        }

    async def _add_lead_to_sequence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Add a lead to an existing sequence"""
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data
        sequence_id = task.get("sequence_id")

        if sequence_id not in self._sequences:
            return {"status": "error", "error": f"Sequence not found: {sequence_id}"}

        self._lead_sequences[lead.id] = {
            "sequence_id": sequence_id,
            "current_step": 0,
            "started_at": datetime.utcnow().isoformat(),
            "next_action_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        lead.current_sequence = sequence_id
        lead.sequence_step = 0

        return {
            "agent": self.name,
            "status": "completed",
            "lead": lead.to_dict(),
            "sequence_id": sequence_id,
        }

    async def _advance_sequence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Advance a lead to the next sequence step"""
        lead_id = task.get("lead_id")

        if lead_id not in self._lead_sequences:
            return {"status": "error", "error": f"Lead not in sequence: {lead_id}"}

        lead_state = self._lead_sequences[lead_id]
        sequence_id = lead_state["sequence_id"]
        sequence = self._sequences.get(sequence_id)

        if not sequence:
            return {"status": "error", "error": f"Sequence not found: {sequence_id}"}

        current_step = lead_state["current_step"]

        # Check if there's a next step
        if current_step >= len(sequence.steps):
            lead_state["status"] = "completed"
            return {
                "agent": self.name,
                "status": "completed",
                "sequence_status": "completed",
                "message": "Sequence completed - no more steps",
            }

        # Get next step
        next_step = sequence.steps[current_step]

        # Calculate next action time
        next_action_at = datetime.utcnow() + timedelta(days=next_step.delay_days)

        lead_state["current_step"] = current_step + 1
        lead_state["next_action_at"] = next_action_at.isoformat()

        return {
            "agent": self.name,
            "status": "completed",
            "current_step": current_step + 1,
            "next_step": {
                "step_number": next_step.step_number,
                "type": next_step.type.value,
                "template": next_step.template,
                "subject": next_step.subject,
                "scheduled_at": next_action_at.isoformat(),
            },
        }

    async def _stop_sequence(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Stop a sequence for a lead (e.g., on reply)"""
        lead_id = task.get("lead_id")
        reason = task.get("reason", "manual_stop")

        if lead_id not in self._lead_sequences:
            return {"status": "error", "error": f"Lead not in sequence: {lead_id}"}

        lead_state = self._lead_sequences[lead_id]
        lead_state["status"] = "stopped"
        lead_state["stopped_at"] = datetime.utcnow().isoformat()
        lead_state["stop_reason"] = reason

        logger.info(f"Stopped sequence for lead {lead_id}: {reason}")

        return {
            "agent": self.name,
            "status": "completed",
            "sequence_status": "stopped",
            "reason": reason,
        }

    async def _get_next_actions(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Get all pending sequence actions"""
        now = datetime.utcnow()

        pending_actions = []

        for lead_id, state in self._lead_sequences.items():
            if state["status"] != "active":
                continue

            next_action_at = datetime.fromisoformat(state["next_action_at"])

            if next_action_at <= now:
                sequence = self._sequences.get(state["sequence_id"])
                if sequence and state["current_step"] < len(sequence.steps):
                    step = sequence.steps[state["current_step"]]
                    pending_actions.append({
                        "lead_id": lead_id,
                        "sequence_id": state["sequence_id"],
                        "step": step.step_number,
                        "type": step.type.value,
                        "template": step.template,
                        "subject": step.subject,
                        "scheduled_at": state["next_action_at"],
                    })

        return {
            "agent": self.name,
            "status": "completed",
            "pending_actions": pending_actions,
            "count": len(pending_actions),
        }

    def get_sequence(self, sequence_id: str) -> Optional[EmailSequence]:
        """Get a sequence by ID"""
        return self._sequences.get(sequence_id)

    def list_sequences(self) -> List[Dict[str, Any]]:
        """List all sequences"""
        return [s.to_dict() for s in self._sequences.values()]


class ResponseAgent(BaseAgent):
    """
    Agent for handling email replies and booking meetings.

    Handles:
    - Reply classification (interested, not interested, question, etc.)
    - Sentiment analysis
    - Meeting scheduling
    - Conversation tracking
    """

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("ResponseAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute response handling task"""
        operation = task.get("operation", "process_reply")

        if operation == "process_reply":
            return await self._process_reply(task)
        elif operation == "book_meeting":
            return await self._book_meeting(task)
        elif operation == "generate_reply":
            return await self._generate_reply(task)
        else:
            return {"status": "error", "error": f"Unknown operation: {operation}"}

    async def _process_reply(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming email reply"""
        email = task.get("email", {})
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data

        email_body = email.get("body", "")
        email_subject = email.get("subject", "")

        logger.info(f"Processing reply from: {lead.email}")

        # Analyze the reply
        analysis = await self._analyze_reply(email_body, email_subject, lead)

        lead.has_replied = True
        lead.reply_sentiment = analysis.get("sentiment")
        lead.updated_at = datetime.utcnow()

        # Update status based on analysis
        intent = analysis.get("intent", "unknown")
        if intent == "interested":
            lead.status = LeadStatus.REPLIED
        elif intent == "meeting_request":
            lead.status = LeadStatus.MEETING_SCHEDULED
        elif intent == "not_interested":
            lead.status = LeadStatus.DISQUALIFIED
        else:
            lead.status = LeadStatus.REPLIED

        result = {
            "agent": self.name,
            "status": "completed",
            "lead": lead.to_dict(),
            "analysis": analysis,
            "recommended_action": self._get_recommended_action(analysis),
        }

        # Generate suggested response if positive
        if analysis.get("sentiment") in ["positive", "neutral"] and intent not in ["not_interested", "unsubscribe"]:
            suggested = await self._generate_suggested_response(email_body, lead, analysis)
            result["suggested_response"] = suggested

        return result

    async def _analyze_reply(
        self,
        email_body: str,
        email_subject: str,
        lead: Lead,
    ) -> Dict[str, Any]:
        """Analyze the content and intent of a reply"""

        prompt = f"""Analyze this email reply from a sales prospect.

FROM: {lead.first_name} {lead.last_name} ({lead.title} at {lead.company})
SUBJECT: {email_subject}
BODY:
{email_body}

Classify the reply with:
1. intent: The main intent (interested, not_interested, question, objection, meeting_request, unsubscribe, out_of_office, other)
2. sentiment: Overall sentiment (positive, neutral, negative)
3. urgency: How urgent is a response (high, medium, low)
4. key_points: List of key points from the email
5. objections: Any objections raised
6. questions: Any questions asked
7. availability_mentioned: If they mentioned times for a meeting (true/false)
8. availability_details: Specific times if mentioned

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {
            "intent": "unknown",
            "sentiment": "neutral",
            "urgency": "medium",
            "key_points": [],
            "objections": [],
            "questions": [],
            "availability_mentioned": False,
        }

    def _get_recommended_action(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get recommended next action based on reply analysis"""
        intent = analysis.get("intent", "unknown")
        sentiment = analysis.get("sentiment", "neutral")

        actions = {
            "interested": {
                "action": "schedule_meeting",
                "priority": "high",
                "message": "Lead is interested - schedule a meeting ASAP",
            },
            "meeting_request": {
                "action": "send_calendar_link",
                "priority": "high",
                "message": "Lead wants to meet - send calendar availability",
            },
            "question": {
                "action": "answer_question",
                "priority": "high",
                "message": "Lead has questions - respond with answers",
            },
            "objection": {
                "action": "handle_objection",
                "priority": "medium",
                "message": "Lead raised objection - address concerns",
            },
            "not_interested": {
                "action": "remove_from_sequence",
                "priority": "low",
                "message": "Lead not interested - stop sequence, note for future",
            },
            "unsubscribe": {
                "action": "unsubscribe",
                "priority": "high",
                "message": "Lead requested unsubscribe - comply immediately",
            },
            "out_of_office": {
                "action": "reschedule",
                "priority": "low",
                "message": "Lead is OOO - reschedule follow-up",
            },
        }

        return actions.get(intent, {
            "action": "review",
            "priority": "medium",
            "message": "Review reply and determine next steps",
        })

    async def _generate_suggested_response(
        self,
        original_reply: str,
        lead: Lead,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a suggested response to the reply"""

        prompt = f"""Generate a professional response to this prospect's reply.

PROSPECT: {lead.first_name} {lead.last_name} ({lead.title} at {lead.company})

THEIR REPLY:
{original_reply}

ANALYSIS:
- Intent: {analysis.get('intent')}
- Sentiment: {analysis.get('sentiment')}
- Questions: {analysis.get('questions', [])}
- Objections: {analysis.get('objections', [])}

Write a helpful, professional response that:
1. Acknowledges their reply
2. Answers any questions
3. Addresses any objections
4. Moves toward scheduling a meeting (if appropriate)
5. Keeps a conversational, helpful tone

Return a JSON object with:
- subject: Response subject line
- body: Response body
- includes_calendar_link: Whether to include a calendar link (true/false)

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-4o",
            temperature=0.7,
            max_tokens=600,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"subject": "Re: ", "body": content}

    async def _book_meeting(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Book a meeting with a lead"""
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data
        availability = task.get("availability", {})

        # In production, this would integrate with calendar APIs
        # For now, we'll generate a response with meeting options

        prompt = f"""Create a professional email to book a meeting with this prospect.

PROSPECT: {lead.first_name} {lead.last_name} ({lead.title} at {lead.company})

AVAILABLE TIMES:
{json.dumps(availability, indent=2) if availability else "Please suggest 2-3 time slots this week."}

Write an email that:
1. Thanks them for their interest
2. Proposes specific meeting times
3. Mentions the meeting will be 30 minutes
4. Includes a Zoom/call option
5. Is warm and professional

Return a JSON object with:
- subject: Email subject
- body: Email body

Return ONLY valid JSON."""

        response = await self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-4o-mini",
            temperature=0.7,
            max_tokens=400,
        )

        content = response["choices"][0]["message"]["content"]

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                meeting_email = json.loads(json_match.group())

                lead.meeting_booked = True
                lead.status = LeadStatus.MEETING_SCHEDULED
                lead.updated_at = datetime.utcnow()

                return {
                    "agent": self.name,
                    "status": "completed",
                    "lead": lead.to_dict(),
                    "meeting_email": meeting_email,
                }
        except json.JSONDecodeError:
            pass

        return {
            "agent": self.name,
            "status": "error",
            "error": "Failed to generate meeting email",
        }

    async def _generate_reply(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a reply for manual approval"""
        email = task.get("email", {})
        lead_data = task.get("lead", {})
        lead = Lead.from_dict(lead_data) if isinstance(lead_data, dict) else lead_data
        context = task.get("context", {})

        # First analyze the incoming email
        analysis = await self._analyze_reply(
            email.get("body", ""),
            email.get("subject", ""),
            lead,
        )

        # Generate response
        suggested = await self._generate_suggested_response(
            email.get("body", ""),
            lead,
            analysis,
        )

        return {
            "agent": self.name,
            "status": "completed",
            "analysis": analysis,
            "suggested_response": suggested,
            "lead": lead.to_dict(),
        }


# ============== Main Orchestrator ==============

class SalesOutreachOrchestrator:
    """
    Main orchestrator for the multi-agent sales outreach system.

    Coordinates:
    - LeadEnrichmentAgent - Research prospects
    - PersonalizationAgent - Craft personalized messages
    - SequenceAgent - Manage email sequences
    - ResponseAgent - Handle replies and book meetings
    """

    def __init__(self, memory_manager=None, llm_client=None):
        self.memory_manager = memory_manager
        self.llm_client = llm_client or OpsCenterLLMClient()

        # Initialize specialized agents
        self.enrichment_agent = LeadEnrichmentAgent(memory_manager, llm_client)
        self.personalization_agent = PersonalizationAgent(memory_manager, llm_client)
        self.sequence_agent = SequenceAgent(memory_manager, llm_client)
        self.response_agent = ResponseAgent(memory_manager, llm_client)

        # In-memory storage (would be database in production)
        self._campaigns: Dict[str, Campaign] = {}
        self._leads: Dict[str, Lead] = {}

        logger.info("SalesOutreachOrchestrator initialized with 4 agents")

    # ============== Campaign Management ==============

    async def create_campaign(
        self,
        name: str,
        description: str,
        target_persona: str = "",
        value_proposition: str = "",
    ) -> Dict[str, Any]:
        """Create a new outreach campaign"""
        campaign_id = str(uuid.uuid4())

        campaign = Campaign(
            id=campaign_id,
            name=name,
            description=description,
            target_persona=target_persona,
            value_proposition=value_proposition,
        )

        self._campaigns[campaign_id] = campaign

        logger.info(f"Created campaign: {name} ({campaign_id})")

        return {
            "status": "success",
            "campaign": campaign.to_dict(),
        }

    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get a campaign by ID"""
        campaign = self._campaigns.get(campaign_id)
        if campaign:
            return campaign.to_dict()
        return None

    async def list_campaigns(self) -> List[Dict[str, Any]]:
        """List all campaigns"""
        return [c.to_dict() for c in self._campaigns.values()]

    # ============== Lead Operations ==============

    async def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Research and enrich lead data.

        Uses web search to find:
        - Company information
        - LinkedIn/social profiles
        - Recent news
        - Pain points and triggers

        Args:
            lead: Lead data dictionary with at minimum: email, company

        Returns:
            Enriched lead data
        """
        # Convert to Lead object if needed
        if isinstance(lead, dict):
            if "id" not in lead:
                lead["id"] = str(uuid.uuid4())
            lead_obj = Lead.from_dict(lead)
        else:
            lead_obj = lead

        # Execute enrichment
        result = await self.enrichment_agent.execute({"lead": lead_obj.to_dict()})

        # Store lead
        if result.get("status") == "completed":
            enriched_lead = Lead.from_dict(result["lead"])
            self._leads[enriched_lead.id] = enriched_lead

        return result

    async def add_lead_to_campaign(
        self,
        lead: Dict[str, Any],
        campaign_id: str,
        auto_enrich: bool = True,
    ) -> Dict[str, Any]:
        """Add a lead to a campaign"""
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return {"status": "error", "error": f"Campaign not found: {campaign_id}"}

        # Create lead if needed
        if isinstance(lead, dict):
            if "id" not in lead:
                lead["id"] = str(uuid.uuid4())
            lead_obj = Lead.from_dict(lead)
        else:
            lead_obj = lead

        # Enrich if requested
        if auto_enrich:
            enrichment_result = await self.enrich_lead(lead_obj.to_dict())
            if enrichment_result.get("status") == "completed":
                lead_obj = Lead.from_dict(enrichment_result["lead"])

        # Add to campaign
        campaign.leads.append(lead_obj.id)
        self._leads[lead_obj.id] = lead_obj

        return {
            "status": "success",
            "lead": lead_obj.to_dict(),
            "campaign_id": campaign_id,
            "enriched": auto_enrich,
        }

    async def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get a lead by ID"""
        lead = self._leads.get(lead_id)
        if lead:
            return lead.to_dict()
        return None

    async def list_leads(self, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List leads, optionally filtered by campaign"""
        if campaign_id:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                return []
            return [
                self._leads[lid].to_dict()
                for lid in campaign.leads
                if lid in self._leads
            ]
        return [l.to_dict() for l in self._leads.values()]

    # ============== Personalization ==============

    async def personalize_message(
        self,
        lead: Dict[str, Any],
        template: str,
        context: Optional[Dict[str, Any]] = None,
        generate_variants: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a personalized email message.

        Uses lead enrichment data to create:
        - Company-specific references
        - Recent news/event mentions
        - Role-specific value propositions
        - A/B test variants (optional)

        Args:
            lead: Lead data (enriched preferred)
            template: Email template with {{placeholders}}
            context: Additional context for personalization
            generate_variants: Whether to generate A/B variants

        Returns:
            Personalized message(s)
        """
        return await self.personalization_agent.execute({
            "lead": lead,
            "template": template,
            "context": context or {},
            "generate_variants": generate_variants,
        })

    # ============== Sequence Management ==============

    async def create_sequence(
        self,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
        sequence_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Set up an email sequence for a lead.

        Creates a multi-step email cadence with:
        - Configurable delays (default: Day 0, Day 3, Day 7)
        - Stop on reply
        - Tracking support

        Args:
            lead: Lead data
            campaign: Campaign data
            sequence_config: Optional sequence configuration

        Returns:
            Created sequence with scheduled steps
        """
        return await self.sequence_agent.execute({
            "operation": "create",
            "lead": lead,
            "campaign": campaign,
            "sequence_config": sequence_config or {},
        })

    async def get_pending_sequence_actions(self) -> Dict[str, Any]:
        """Get all pending sequence actions that are due"""
        return await self.sequence_agent.execute({
            "operation": "get_next_actions",
        })

    async def advance_sequence(self, lead_id: str) -> Dict[str, Any]:
        """Advance a lead to the next sequence step"""
        return await self.sequence_agent.execute({
            "operation": "advance",
            "lead_id": lead_id,
        })

    async def stop_sequence(self, lead_id: str, reason: str = "manual") -> Dict[str, Any]:
        """Stop a sequence for a lead"""
        return await self.sequence_agent.execute({
            "operation": "stop",
            "lead_id": lead_id,
            "reason": reason,
        })

    async def list_sequences(self) -> List[Dict[str, Any]]:
        """List all sequences"""
        return self.sequence_agent.list_sequences()

    # ============== Reply Processing ==============

    async def process_reply(
        self,
        email: Dict[str, Any],
        lead: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an incoming email reply.

        Analyzes the reply for:
        - Intent (interested, not interested, question, etc.)
        - Sentiment
        - Questions/objections to address
        - Meeting availability

        Args:
            email: Email data with subject and body
            lead: Lead data

        Returns:
            Analysis and recommended actions
        """
        result = await self.response_agent.execute({
            "operation": "process_reply",
            "email": email,
            "lead": lead,
        })

        # If reply received, stop the sequence
        if result.get("status") == "completed":
            lead_id = lead.get("id")
            if lead_id:
                sequence = self.sequence_agent._lead_sequences.get(lead_id)
                if sequence and sequence.get("status") == "active":
                    await self.stop_sequence(lead_id, reason="reply_received")

        return result

    # ============== Meeting Booking ==============

    async def book_meeting(
        self,
        lead: Dict[str, Any],
        availability: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a meeting with a lead.

        Generates a meeting request email with:
        - Proposed time slots
        - Meeting duration
        - Video call link

        Args:
            lead: Lead data
            availability: Available time slots

        Returns:
            Meeting email and booking confirmation
        """
        return await self.response_agent.execute({
            "operation": "book_meeting",
            "lead": lead,
            "availability": availability or {},
        })

    # ============== Email Sending ==============

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        lead_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using the configured email provider.

        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            lead_id: Optional lead ID for tracking

        Returns:
            Send result
        """
        result = await email_handler(
            to=to,
            subject=subject,
            body=body,
            operation="send",
        )

        # Update lead tracking if provided
        if lead_id and lead_id in self._leads:
            lead = self._leads[lead_id]
            lead.last_contacted = datetime.utcnow()
            lead.status = LeadStatus.CONTACTED
            lead.updated_at = datetime.utcnow()

        return result

    # ============== Full Workflow ==============

    async def execute_outreach(
        self,
        lead: Dict[str, Any],
        campaign_id: str,
        template: str,
        send_immediately: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a full outreach workflow:
        1. Enrich the lead
        2. Personalize the message
        3. Create sequence
        4. Optionally send first email

        Args:
            lead: Lead data
            campaign_id: Campaign ID
            template: Email template
            send_immediately: Whether to send the first email immediately

        Returns:
            Full workflow result
        """
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return {"status": "error", "error": f"Campaign not found: {campaign_id}"}

        workflow_result = {
            "lead_id": lead.get("id", str(uuid.uuid4())),
            "campaign_id": campaign_id,
            "steps": [],
        }

        # Step 1: Enrich
        logger.info("Step 1: Enriching lead")
        enrichment = await self.enrich_lead(lead)
        workflow_result["steps"].append({
            "step": "enrichment",
            "status": enrichment.get("status"),
            "summary": enrichment.get("enrichment_summary"),
        })

        if enrichment.get("status") != "completed":
            workflow_result["status"] = "error"
            workflow_result["error"] = "Enrichment failed"
            return workflow_result

        enriched_lead = enrichment["lead"]

        # Step 2: Personalize
        logger.info("Step 2: Personalizing message")
        personalization = await self.personalize_message(
            lead=enriched_lead,
            template=template,
            context={"value_proposition": campaign.value_proposition},
            generate_variants=True,
        )
        workflow_result["steps"].append({
            "step": "personalization",
            "status": personalization.get("status"),
        })

        if personalization.get("status") != "completed":
            workflow_result["status"] = "error"
            workflow_result["error"] = "Personalization failed"
            return workflow_result

        # Step 3: Create sequence
        logger.info("Step 3: Creating sequence")
        sequence = await self.create_sequence(
            lead=enriched_lead,
            campaign=campaign.to_dict(),
            sequence_config={
                "initial_template": template,
                "initial_subject": personalization.get("subject", "Quick question"),
            },
        )
        workflow_result["steps"].append({
            "step": "sequence_creation",
            "status": sequence.get("status"),
            "sequence_id": sequence.get("sequence", {}).get("id"),
        })

        # Step 4: Optionally send first email
        if send_immediately:
            logger.info("Step 4: Sending first email")
            send_result = await self.send_email(
                to=enriched_lead["email"],
                subject=personalization.get("subject", ""),
                body=personalization.get("body", ""),
                lead_id=enriched_lead["id"],
            )
            workflow_result["steps"].append({
                "step": "send_email",
                "status": "success" if send_result.get("success") else "error",
            })

        workflow_result["status"] = "success"
        workflow_result["lead"] = enriched_lead
        workflow_result["personalized_message"] = {
            "subject": personalization.get("subject"),
            "body": personalization.get("body"),
            "variants": {
                "a": personalization.get("variant_a"),
                "b": personalization.get("variant_b"),
            },
        }

        return workflow_result

    # ============== Statistics ==============

    def get_stats(self) -> Dict[str, Any]:
        """Get outreach statistics"""
        leads = list(self._leads.values())

        status_counts = {}
        for lead in leads:
            status = lead.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_campaigns": len(self._campaigns),
            "total_leads": len(leads),
            "total_sequences": len(self.sequence_agent._sequences),
            "lead_status_breakdown": status_counts,
            "replied_count": sum(1 for l in leads if l.has_replied),
            "meetings_booked": sum(1 for l in leads if l.meeting_booked),
        }


# ============== Factory Function ==============

def create_sales_orchestrator(
    memory_manager=None,
    llm_client=None,
) -> SalesOutreachOrchestrator:
    """
    Create a configured SalesOutreachOrchestrator instance.

    Args:
        memory_manager: Optional memory manager for conversation history
        llm_client: Optional pre-configured LLM client

    Returns:
        Configured orchestrator
    """
    return SalesOutreachOrchestrator(
        memory_manager=memory_manager,
        llm_client=llm_client,
    )
