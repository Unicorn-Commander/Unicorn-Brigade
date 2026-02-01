"""
Sales Outreach API Routes

API endpoints for the multi-agent sales outreach system:
- Campaign management
- Lead operations (add, enrich, list)
- Sequence management
- Reply processing
- Meeting booking
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, List, Optional, Any, Annotated
from datetime import datetime
import logging

from app.agents.sales_outreach import (
    SalesOutreachOrchestrator,
    create_sales_orchestrator,
    Lead,
    LeadStatus,
)
from app.auth.middleware import require_api_key, require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sales", tags=["sales"])

# Global orchestrator instance (initialized on startup)
orchestrator: Optional[SalesOutreachOrchestrator] = None


def init_sales_routes(llm_client=None, memory_manager=None):
    """Initialize the sales routes with dependencies"""
    global orchestrator
    orchestrator = create_sales_orchestrator(
        llm_client=llm_client,
        memory_manager=memory_manager,
    )
    logger.info("Sales outreach routes initialized")


def get_orchestrator() -> SalesOutreachOrchestrator:
    """Dependency to get the orchestrator"""
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Sales orchestrator not initialized"
        )
    return orchestrator


# ============== Request/Response Models ==============

class CampaignCreateRequest(BaseModel):
    """Request to create a campaign"""
    name: str = Field(..., description="Campaign name")
    description: str = Field("", description="Campaign description")
    target_persona: str = Field("", description="Target persona description")
    value_proposition: str = Field("", description="Value proposition for the campaign")


class CampaignResponse(BaseModel):
    """Campaign response"""
    id: str
    name: str
    description: str
    target_persona: str
    value_proposition: str
    status: str
    leads_count: int = 0
    sequences_count: int = 0
    created_at: str


class LeadCreateRequest(BaseModel):
    """Request to add a lead"""
    email: EmailStr = Field(..., description="Lead email address")
    first_name: str = Field("", description="First name")
    last_name: str = Field("", description="Last name")
    company: str = Field("", description="Company name")
    title: str = Field("", description="Job title")
    tags: List[str] = Field(default_factory=list, description="Lead tags")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom fields")


class LeadAddToCampaignRequest(BaseModel):
    """Request to add leads to a campaign"""
    leads: List[LeadCreateRequest] = Field(..., description="Leads to add")
    campaign_id: str = Field(..., description="Campaign ID")
    auto_enrich: bool = Field(True, description="Automatically enrich leads")


class LeadEnrichRequest(BaseModel):
    """Request to enrich a lead"""
    lead_id: Optional[str] = Field(None, description="Existing lead ID")
    email: Optional[EmailStr] = Field(None, description="Lead email (if not using lead_id)")
    first_name: Optional[str] = Field("", description="First name")
    last_name: Optional[str] = Field("", description="Last name")
    company: Optional[str] = Field("", description="Company name")
    title: Optional[str] = Field("", description="Job title")


class PersonalizeRequest(BaseModel):
    """Request to personalize a message"""
    lead_id: str = Field(..., description="Lead ID to personalize for")
    template: str = Field(..., description="Email template with {{placeholders}}")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    generate_variants: bool = Field(False, description="Generate A/B test variants")


class SequenceCreateRequest(BaseModel):
    """Request to create a sequence"""
    lead_id: str = Field(..., description="Lead ID")
    campaign_id: str = Field(..., description="Campaign ID")
    sequence_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Sequence configuration"
    )


class SequenceStep(BaseModel):
    """Sequence step definition"""
    type: str = Field("email", description="Step type: email, follow_up, linkedin, call")
    delay_days: int = Field(0, description="Days after previous step")
    template: str = Field("", description="Message template")
    subject: str = Field("", description="Email subject")


class SequenceConfigRequest(BaseModel):
    """Custom sequence configuration"""
    name: str = Field("", description="Sequence name")
    description: str = Field("", description="Sequence description")
    steps: List[SequenceStep] = Field(default_factory=list, description="Sequence steps")
    stop_on_reply: bool = Field(True, description="Stop sequence on reply")
    track_opens: bool = Field(True, description="Track email opens")
    track_clicks: bool = Field(True, description="Track email clicks")


class ReplyProcessRequest(BaseModel):
    """Request to process a reply"""
    lead_id: str = Field(..., description="Lead ID who replied")
    email_subject: str = Field("", description="Reply subject")
    email_body: str = Field(..., description="Reply body content")
    from_address: Optional[str] = Field(None, description="Sender email address")
    received_at: Optional[str] = Field(None, description="When the reply was received")


class MeetingBookRequest(BaseModel):
    """Request to book a meeting"""
    lead_id: str = Field(..., description="Lead ID")
    availability: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Available time slots"
    )


class OutreachExecuteRequest(BaseModel):
    """Request to execute full outreach workflow"""
    lead: LeadCreateRequest = Field(..., description="Lead data")
    campaign_id: str = Field(..., description="Campaign ID")
    template: str = Field(..., description="Email template")
    send_immediately: bool = Field(False, description="Send first email immediately")


# ============== Campaign Endpoints ==============

@router.post("/campaign", response_model=CampaignResponse)
async def create_campaign(
    request: CampaignCreateRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create a new outreach campaign.

    A campaign contains:
    - Target persona and value proposition
    - Associated leads
    - Email sequences
    """
    result = await orch.create_campaign(
        name=request.name,
        description=request.description,
        target_persona=request.target_persona,
        value_proposition=request.value_proposition,
    )

    if result.get("status") != "success":
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create campaign"))

    campaign = result["campaign"]
    return CampaignResponse(
        id=campaign["id"],
        name=campaign["name"],
        description=campaign["description"],
        target_persona=campaign["target_persona"],
        value_proposition=campaign["value_proposition"],
        status=campaign["status"],
        leads_count=len(campaign.get("leads", [])),
        sequences_count=len(campaign.get("sequences", [])),
        created_at=campaign["created_at"],
    )


@router.get("/campaigns")
async def list_campaigns(
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all campaigns"""
    campaigns = await orch.list_campaigns()
    return {"campaigns": campaigns, "count": len(campaigns)}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get a specific campaign"""
    campaign = await orch.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}")
    return campaign


# ============== Lead Endpoints ==============

@router.post("/leads")
async def add_leads_to_campaign(
    request: LeadAddToCampaignRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Add leads to a campaign.

    Optionally enriches leads automatically using web search.
    """
    results = []
    errors = []

    for lead in request.leads:
        try:
            result = await orch.add_lead_to_campaign(
                lead=lead.model_dump(),
                campaign_id=request.campaign_id,
                auto_enrich=request.auto_enrich,
            )

            if result.get("status") == "success":
                results.append(result["lead"])
            else:
                errors.append({
                    "email": lead.email,
                    "error": result.get("error", "Unknown error"),
                })
        except Exception as e:
            errors.append({
                "email": lead.email,
                "error": str(e),
            })

    return {
        "added": len(results),
        "errors": len(errors),
        "leads": results,
        "error_details": errors if errors else None,
    }


@router.get("/leads")
async def list_leads(
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List leads, optionally filtered by campaign or status"""
    leads = await orch.list_leads(campaign_id=campaign_id)

    # Filter by status if provided
    if status:
        leads = [l for l in leads if l.get("status") == status]

    return {"leads": leads, "count": len(leads)}


@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get a specific lead"""
    lead = await orch.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")
    return lead


@router.post("/enrich")
async def enrich_lead(
    request: LeadEnrichRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Enrich lead data using web search.

    Discovers:
    - Company information
    - Social profiles (LinkedIn, Twitter)
    - Recent news
    - Pain points and triggers
    """
    # Get existing lead or create new one
    if request.lead_id:
        lead = await orch.get_lead(request.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead not found: {request.lead_id}")
    else:
        if not request.email:
            raise HTTPException(status_code=400, detail="Either lead_id or email is required")
        lead = {
            "email": request.email,
            "first_name": request.first_name or "",
            "last_name": request.last_name or "",
            "company": request.company or "",
            "title": request.title or "",
        }

    result = await orch.enrich_lead(lead)

    if result.get("status") != "completed":
        raise HTTPException(status_code=500, detail=result.get("error", "Enrichment failed"))

    return {
        "lead": result["lead"],
        "enrichment_summary": result.get("enrichment_summary"),
    }


# ============== Personalization Endpoints ==============

@router.post("/personalize")
async def personalize_message(
    request: PersonalizeRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate a personalized email message.

    Uses lead enrichment data to create personalized content
    with company-specific references, recent news mentions, etc.
    """
    lead = await orch.get_lead(request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {request.lead_id}")

    result = await orch.personalize_message(
        lead=lead,
        template=request.template,
        context=request.context,
        generate_variants=request.generate_variants,
    )

    if result.get("status") != "completed":
        raise HTTPException(status_code=500, detail=result.get("error", "Personalization failed"))

    return result


# ============== Sequence Endpoints ==============

@router.get("/sequences")
async def list_sequences(
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all active sequences"""
    sequences = await orch.list_sequences()
    return {"sequences": sequences, "count": len(sequences)}


@router.post("/sequences")
async def create_sequence(
    request: SequenceCreateRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create an email sequence for a lead.

    Default sequence:
    - Step 1: Initial email (Day 0)
    - Step 2: Follow-up 1 (Day 3)
    - Step 3: Follow-up 2 (Day 7)
    """
    lead = await orch.get_lead(request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {request.lead_id}")

    campaign = await orch.get_campaign(request.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign not found: {request.campaign_id}")

    result = await orch.create_sequence(
        lead=lead,
        campaign=campaign,
        sequence_config=request.sequence_config,
    )

    if result.get("status") != "completed":
        raise HTTPException(status_code=500, detail=result.get("error", "Sequence creation failed"))

    return result


@router.get("/sequences/pending")
async def get_pending_actions(
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get all pending sequence actions that are due for execution"""
    result = await orch.get_pending_sequence_actions()
    return result


@router.post("/sequences/{lead_id}/advance")
async def advance_sequence(
    lead_id: str,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Advance a lead to the next step in their sequence"""
    result = await orch.advance_sequence(lead_id)
    return result


@router.post("/sequences/{lead_id}/stop")
async def stop_sequence(
    lead_id: str,
    reason: str = "manual",
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Stop a sequence for a lead"""
    result = await orch.stop_sequence(lead_id, reason)
    return result


# ============== Reply Processing Endpoints ==============

@router.post("/reply")
async def process_reply(
    request: ReplyProcessRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Process an incoming email reply.

    Analyzes the reply for:
    - Intent (interested, not interested, question, etc.)
    - Sentiment
    - Questions/objections
    - Meeting availability

    Returns recommended actions and suggested response.
    """
    lead = await orch.get_lead(request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {request.lead_id}")

    email = {
        "subject": request.email_subject,
        "body": request.email_body,
        "from": request.from_address,
        "received_at": request.received_at,
    }

    result = await orch.process_reply(email=email, lead=lead)

    if result.get("status") != "completed":
        raise HTTPException(status_code=500, detail=result.get("error", "Reply processing failed"))

    return result


# ============== Meeting Endpoints ==============

@router.post("/meeting")
async def book_meeting(
    request: MeetingBookRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate a meeting booking email.

    Creates a professional email with proposed time slots.
    """
    lead = await orch.get_lead(request.lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead not found: {request.lead_id}")

    result = await orch.book_meeting(
        lead=lead,
        availability=request.availability,
    )

    if result.get("status") != "completed":
        raise HTTPException(status_code=500, detail=result.get("error", "Meeting booking failed"))

    return result


# ============== Full Workflow Endpoints ==============

@router.post("/outreach/execute")
async def execute_outreach(
    request: OutreachExecuteRequest,
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Execute a complete outreach workflow:

    1. Enrich the lead (company info, social profiles, pain points)
    2. Personalize the message
    3. Create email sequence
    4. Optionally send first email

    This is the recommended way to start outreach to a new lead.
    """
    result = await orch.execute_outreach(
        lead=request.lead.model_dump(),
        campaign_id=request.campaign_id,
        template=request.template,
        send_immediately=request.send_immediately,
    )

    if result.get("status") != "success":
        raise HTTPException(status_code=500, detail=result.get("error", "Outreach execution failed"))

    return result


# ============== Statistics Endpoints ==============

@router.get("/stats")
async def get_stats(
    orch: SalesOutreachOrchestrator = Depends(get_orchestrator),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get sales outreach statistics"""
    return orch.get_stats()


# ============== Health Check ==============

@router.get("/health")
async def health_check():
    """Health check for sales module"""
    return {
        "status": "healthy" if orchestrator else "not_initialized",
        "module": "sales_outreach",
        "agents": [
            "LeadEnrichmentAgent",
            "PersonalizationAgent",
            "SequenceAgent",
            "ResponseAgent",
        ] if orchestrator else [],
    }
