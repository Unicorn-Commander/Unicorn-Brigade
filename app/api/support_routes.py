"""
Customer Support API Routes

Provides endpoints for:
- Creating and managing support tickets
- Sending messages to tickets
- FAQ management
- Knowledge base search
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.agents.customer_support import (
    CustomerSupportAgent,
    SupportTicket,
    TicketStatus,
    TicketPriority,
    SupportChannel,
    FAQEntry,
)
from app.memory.manager import MemoryManager
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["support"])

# Global support agent instance (initialized in init_support_routes)
support_agent: Optional[CustomerSupportAgent] = None


def init_support_routes(
    memory_manager: Optional[MemoryManager] = None,
    llm_client: Optional[OpsCenterLLMClient] = None,
    knowledge_graph_manager=None,
):
    """Initialize support routes with dependencies"""
    global support_agent
    support_agent = CustomerSupportAgent(
        memory_manager=memory_manager,
        llm_client=llm_client,
        knowledge_graph_manager=knowledge_graph_manager,
    )
    logger.info("Support routes initialized with CustomerSupportAgent")


def get_support_agent() -> CustomerSupportAgent:
    """Dependency to get the support agent"""
    if not support_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Support agent not initialized"
        )
    return support_agent


# ---- Request/Response Models ----

class CreateTicketRequest(BaseModel):
    """Request to create a new support ticket"""
    message: str = Field(..., description="Initial message/question from the customer")
    customer_id: Optional[str] = Field("anonymous", description="Customer identifier")
    customer_email: Optional[str] = Field(None, description="Customer email address")
    subject: Optional[str] = Field(None, description="Ticket subject")
    channel: str = Field("chat", description="Communication channel (email, chat, web, slack, api)")
    priority: Optional[str] = Field("medium", description="Ticket priority (low, medium, high, urgent)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CreateTicketResponse(BaseModel):
    """Response from creating a ticket"""
    ticket_id: str
    status: str
    response: str
    confidence: float
    escalated: bool
    escalation_reason: Optional[str] = None
    channel: str
    kb_hits: int = 0
    created_at: str


class SendMessageRequest(BaseModel):
    """Request to send a message to an existing ticket"""
    message: str = Field(..., description="Message content")
    customer_id: Optional[str] = Field("anonymous", description="Customer identifier (for verification)")


class SendMessageResponse(BaseModel):
    """Response from sending a message"""
    ticket_id: str
    response: str
    confidence: float
    escalated: bool
    escalation_reason: Optional[str] = None
    kb_hits: int = 0


class TicketListResponse(BaseModel):
    """Response with list of tickets"""
    tickets: List[Dict[str, Any]]
    count: int
    filters: Dict[str, Any]


class TicketDetailResponse(BaseModel):
    """Response with ticket details"""
    ticket: Dict[str, Any]


class UpdateTicketStatusRequest(BaseModel):
    """Request to update ticket status"""
    status: str = Field(..., description="New status (open, in_progress, awaiting_customer, escalated, resolved, closed)")
    resolution_note: Optional[str] = Field(None, description="Note about resolution")


class AddFAQRequest(BaseModel):
    """Request to add a new FAQ entry"""
    question: str = Field(..., description="The FAQ question")
    answer: str = Field(..., description="The FAQ answer")
    category: str = Field("general", description="FAQ category")
    tags: Optional[List[str]] = Field(None, description="Tags for search")


class FAQResponse(BaseModel):
    """Response with FAQ entry"""
    id: str
    question: str
    answer: str
    category: str
    tags: List[str]
    created_at: str
    updated_at: str


class FAQListResponse(BaseModel):
    """Response with list of FAQs"""
    faqs: List[Dict[str, Any]]
    count: int


class FAQSearchRequest(BaseModel):
    """Request to search FAQs"""
    query: str = Field(..., description="Search query")
    category: Optional[str] = Field(None, description="Filter by category")
    limit: int = Field(10, description="Maximum results")


class FAQSearchResponse(BaseModel):
    """Response from FAQ search"""
    results: List[Dict[str, Any]]
    count: int
    query: str


class SupportStatusResponse(BaseModel):
    """Response with support agent status"""
    status: str
    agent_name: str
    memory_enabled: bool
    knowledge_graph_enabled: bool
    metrics: Dict[str, int]
    thresholds: Dict[str, float]


# ---- Ticket Endpoints ----

@router.post("/ticket", response_model=CreateTicketResponse)
async def create_support_ticket(
    request: CreateTicketRequest,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Create a new support ticket and get an initial response.

    This endpoint:
    1. Creates a new ticket with the provided message
    2. Searches the knowledge base for relevant information
    3. Generates a helpful response
    4. Automatically escalates if needed

    Returns the ticket ID and AI-generated response.
    """
    try:
        context = {
            "customer_id": request.customer_id,
            "customer_email": request.customer_email,
            "subject": request.subject or request.message[:100],
            "priority": request.priority,
            "metadata": request.metadata or {},
        }

        result = await agent.handle_request(
            message=request.message,
            channel=request.channel,
            context=context,
        )

        # Get the created ticket for additional details
        ticket = agent.get_ticket(result["ticket_id"])

        return CreateTicketResponse(
            ticket_id=result["ticket_id"],
            status=ticket.status.value if ticket else "open",
            response=result["response"],
            confidence=result["confidence"],
            escalated=result["escalated"],
            escalation_reason=result.get("escalation_reason"),
            channel=result["channel"],
            kb_hits=result.get("kb_hits", 0),
            created_at=ticket.created_at.isoformat() if ticket else datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error creating support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/message", response_model=SendMessageResponse)
async def send_message_to_ticket(
    request: SendMessageRequest,
    ticket_id: str = Query(..., description="Ticket ID to send message to"),
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Send a follow-up message to an existing ticket.

    The agent will:
    1. Add the message to the ticket history
    2. Consider previous conversation context
    3. Search knowledge base
    4. Generate a contextual response
    """
    ticket = agent.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket not found: {ticket_id}"
        )

    try:
        result = await agent.handle_request(
            message=request.message,
            channel=ticket.channel.value,
            context={
                "ticket_id": ticket_id,
                "customer_id": request.customer_id,
            },
        )

        return SendMessageResponse(
            ticket_id=result["ticket_id"],
            response=result["response"],
            confidence=result["confidence"],
            escalated=result["escalated"],
            escalation_reason=result.get("escalation_reason"),
            kb_hits=result.get("kb_hits", 0),
        )

    except Exception as e:
        logger.error(f"Error sending message to ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    limit: int = Query(50, description="Maximum tickets to return"),
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    List support tickets with optional filters.

    Filters:
    - status: Filter by ticket status (open, in_progress, escalated, resolved, closed)
    - customer_id: Filter by customer
    - limit: Maximum results (default 50)
    """
    try:
        status_enum = None
        if status_filter:
            try:
                status_enum = TicketStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Valid values: {[s.value for s in TicketStatus]}"
                )

        tickets = agent.list_tickets(
            status=status_enum,
            customer_id=customer_id,
            limit=limit,
        )

        return TicketListResponse(
            tickets=[t.to_dict() for t in tickets],
            count=len(tickets),
            filters={
                "status": status_filter,
                "customer_id": customer_id,
                "limit": limit,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/ticket/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: str,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """Get details of a specific ticket including full message history."""
    ticket = agent.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket not found: {ticket_id}"
        )

    return TicketDetailResponse(ticket=ticket.to_dict())


@router.put("/ticket/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    request: UpdateTicketStatusRequest,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Update the status of a ticket.

    Use this to manually:
    - Mark tickets as resolved
    - Close tickets
    - Reopen tickets
    - Change priority
    """
    try:
        status_enum = TicketStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {request.status}. Valid values: {[s.value for s in TicketStatus]}"
        )

    ticket = agent.update_ticket_status(
        ticket_id=ticket_id,
        status=status_enum,
        resolution_note=request.resolution_note,
    )

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket not found: {ticket_id}"
        )

    return {
        "message": f"Ticket status updated to {request.status}",
        "ticket": ticket.to_dict(),
    }


@router.post("/ticket/{ticket_id}/escalate")
async def escalate_ticket(
    ticket_id: str,
    reason: str = Query(..., description="Reason for escalation"),
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Manually escalate a ticket to human agents.

    Use when:
    - Customer requests human assistance
    - Issue is too complex for AI
    - Sensitive situation requiring human judgment
    """
    ticket = agent.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket not found: {ticket_id}"
        )

    result = await agent.escalate(ticket_id=ticket_id, reason=reason)

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Failed to escalate ticket")
        )

    return result


# ---- FAQ Endpoints ----

@router.post("/faq", response_model=FAQResponse)
async def add_faq_entry(
    request: AddFAQRequest,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Add a new FAQ entry to the knowledge base.

    The FAQ will be:
    1. Stored locally for quick access
    2. Indexed in memory (Qdrant) for semantic search
    3. Added to knowledge graph for relationship queries
    """
    try:
        faq = await agent.add_faq(
            question=request.question,
            answer=request.answer,
            category=request.category,
            tags=request.tags,
        )

        return FAQResponse(
            id=faq.id,
            question=faq.question,
            answer=faq.answer,
            category=faq.category,
            tags=faq.tags,
            created_at=faq.created_at.isoformat(),
            updated_at=faq.updated_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error adding FAQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/faq", response_model=FAQListResponse)
async def list_faqs(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, description="Maximum FAQs to return"),
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """List FAQ entries with optional category filter."""
    faqs = agent.list_faqs(category=category, limit=limit)

    return FAQListResponse(
        faqs=[f.to_dict() for f in faqs],
        count=len(faqs),
    )


@router.get("/faq/search", response_model=FAQSearchResponse)
async def search_faqs(
    query: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, description="Maximum results"),
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """
    Search FAQs using semantic search.

    This searches:
    1. Local FAQ entries (text matching)
    2. Memory store (Qdrant semantic search)
    3. Knowledge graph (entity relationships)

    Results are ranked by relevance score.
    """
    try:
        # Use the agent's knowledge base search
        results = await agent.search_knowledge_base(query)

        # Filter by category if specified
        if category:
            results = [r for r in results if r.get("category") == category]

        return FAQSearchResponse(
            results=results[:limit],
            count=len(results[:limit]),
            query=query,
        )

    except Exception as e:
        logger.error(f"Error searching FAQs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/faq/{faq_id}", response_model=FAQResponse)
async def get_faq(
    faq_id: str,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """Get a specific FAQ entry by ID."""
    faq = agent.get_faq(faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ not found: {faq_id}"
        )

    return FAQResponse(
        id=faq.id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        tags=faq.tags,
        created_at=faq.created_at.isoformat(),
        updated_at=faq.updated_at.isoformat(),
    )


@router.delete("/faq/{faq_id}")
async def delete_faq(
    faq_id: str,
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """Delete a FAQ entry."""
    success = agent.delete_faq(faq_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FAQ not found: {faq_id}"
        )

    return {"message": f"FAQ {faq_id} deleted successfully"}


# ---- Status Endpoint ----

@router.get("/status", response_model=SupportStatusResponse)
async def get_support_status(
    agent: CustomerSupportAgent = Depends(get_support_agent),
):
    """Get status of the support agent and metrics."""
    status_info = agent.get_status()

    return SupportStatusResponse(
        status=status_info["status"],
        agent_name=status_info["name"],
        memory_enabled=status_info["memory_enabled"],
        knowledge_graph_enabled=status_info["knowledge_graph_enabled"],
        metrics=status_info["metrics"],
        thresholds=status_info["thresholds"],
    )
