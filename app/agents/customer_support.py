"""
Customer Support Agent with multi-channel support and escalation.

This agent handles incoming support requests from various channels (email, chat),
searches a knowledge base for relevant answers, generates helpful responses,
and escalates to humans when confidence is low.

Key features:
- Multi-channel support (email, chat, web)
- Knowledge base integration (Qdrant/mem0 for FAQs, FalkorDB for entity relationships)
- Confidence-based escalation
- Conversation history tracking
- FAQ management via API
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging
import re

from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


class SupportChannel(str, Enum):
    """Supported communication channels"""
    EMAIL = "email"
    CHAT = "chat"
    WEB = "web"
    SLACK = "slack"
    API = "api"


class TicketStatus(str, Enum):
    """Support ticket status"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_CUSTOMER = "awaiting_customer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Support ticket priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class SupportMessage:
    """A message in a support conversation"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    role: str = "user"  # "user", "agent", "system"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    channel: str = "chat"
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp.isoformat(),
            "channel": self.channel,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class SupportTicket:
    """A support ticket tracking a customer interaction"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    customer_email: Optional[str] = None
    subject: str = ""
    channel: SupportChannel = SupportChannel.CHAT
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    messages: List[SupportMessage] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_email": self.customer_email,
            "subject": self.subject,
            "channel": self.channel.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "messages": [m.to_dict() for m in self.messages],
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "escalation_reason": self.escalation_reason,
            "assigned_to": self.assigned_to,
            "resolution_attempts": self.resolution_attempts,
            "metadata": self.metadata,
        }

    def add_message(self, content: str, role: str = "user", **kwargs) -> SupportMessage:
        """Add a message to the ticket"""
        message = SupportMessage(
            content=content,
            role=role,
            channel=self.channel.value,
            **kwargs
        )
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        return message


@dataclass
class FAQEntry:
    """A FAQ entry in the knowledge base"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    answer: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class CustomerSupportAgent(BaseAgent):
    """
    AI-powered Customer Support Agent with multi-channel support.

    Features:
    - Handle requests from email, chat, web, and API channels
    - Search knowledge base for relevant FAQ entries
    - Generate helpful, contextual responses
    - Escalate to human agents when confidence is low
    - Track full conversation history
    - Support adding new FAQ entries dynamically
    """

    # Escalation thresholds
    CONFIDENCE_THRESHOLD = 0.6  # Below this, suggest escalation
    MAX_RESOLUTION_ATTEMPTS = 3  # After this many attempts, escalate

    # Keywords that trigger immediate escalation
    ESCALATION_KEYWORDS = [
        "speak to human", "talk to human", "human agent", "real person",
        "manager", "supervisor", "escalate", "complaint", "lawyer",
        "legal action", "sue", "refund", "cancel", "frustrated",
        "angry", "unacceptable", "terrible", "worst"
    ]

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        knowledge_graph_manager=None,  # FalkorDB integration
    ):
        super().__init__("CustomerSupportAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.knowledge_graph_manager = knowledge_graph_manager

        # In-memory ticket storage (replace with DB in production)
        self._tickets: Dict[str, SupportTicket] = {}
        self._faqs: Dict[str, FAQEntry] = {}

        # System prompt for the support agent
        self.system_prompt = """You are a helpful and professional customer support agent for Unicorn Brigade.

Your responsibilities:
1. Answer customer questions accurately and helpfully
2. Be empathetic and understanding of customer concerns
3. Use the knowledge base information when available
4. Acknowledge when you don't know something
5. Provide clear next steps when appropriate

Guidelines:
- Be professional but friendly
- Keep responses concise but complete
- If unsure, say so honestly
- Never make up information
- Suggest escalation to a human if the issue is complex or the customer is frustrated

Format your responses clearly and use bullet points when listing multiple items."""

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a support task from the workflow engine.

        Args:
            task: Task dictionary with message, channel, and context

        Returns:
            Task result with response and status
        """
        logger.info(f"CustomerSupportAgent executing task: {task.get('task_id')}")

        try:
            message = task.get("task", task.get("message", ""))
            channel = task.get("channel", "chat")
            context = task.get("context", {})

            result = await self.handle_request(
                message=message,
                channel=channel,
                context=context
            )

            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": result,
                "tokens": result.get("tokens", {"input": 0, "output": 0, "total": 0}),
            }

        except Exception as e:
            logger.error(f"CustomerSupportAgent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
                "tokens": {"input": 0, "output": 0, "total": 0},
            }

    async def handle_request(
        self,
        message: str,
        channel: str = "chat",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main handler for incoming support requests.

        Args:
            message: The customer's message
            channel: Communication channel (email, chat, web, etc.)
            context: Additional context (ticket_id, customer_id, etc.)

        Returns:
            Dict with response, confidence, escalation status, and metadata
        """
        context = context or {}
        ticket_id = context.get("ticket_id")
        customer_id = context.get("customer_id", "anonymous")

        # Get or create ticket
        ticket = self._get_or_create_ticket(
            ticket_id=ticket_id,
            customer_id=customer_id,
            channel=channel,
            subject=context.get("subject", message[:100])
        )

        # Add customer message to ticket
        ticket.add_message(content=message, role="user")
        ticket.resolution_attempts += 1

        # Check for immediate escalation keywords
        if self._contains_escalation_keywords(message):
            escalation_result = await self.escalate(
                ticket_id=ticket.id,
                reason="Customer requested human assistance or expressed strong dissatisfaction"
            )
            return {
                "ticket_id": ticket.id,
                "response": "I understand you'd like to speak with a human agent. I'm escalating your request now. A support team member will be with you shortly.",
                "escalated": True,
                "escalation_reason": escalation_result.get("reason"),
                "confidence": 1.0,
                "channel": channel,
            }

        # Search knowledge base for relevant information
        kb_results = await self.search_knowledge_base(message)

        # Generate response with KB context
        response_result = await self.generate_response(
            query=message,
            context=self._build_response_context(ticket, kb_results)
        )

        response_text = response_result.get("response", "")
        confidence = response_result.get("confidence", 0.5)

        # Check if escalation is needed
        escalation_check = self.should_escalate(response_text, confidence, ticket)

        if escalation_check["should_escalate"]:
            # Add agent response with escalation notice
            ticket.add_message(
                content=response_text,
                role="agent",
                confidence=confidence
            )

            escalation_result = await self.escalate(
                ticket_id=ticket.id,
                reason=escalation_check["reason"]
            )

            return {
                "ticket_id": ticket.id,
                "response": response_text + "\n\n---\n*I'm also escalating this to a human agent to ensure you get the best assistance.*",
                "escalated": True,
                "escalation_reason": escalation_result.get("reason"),
                "confidence": confidence,
                "channel": channel,
                "kb_hits": len(kb_results),
                "tokens": response_result.get("tokens", {}),
            }

        # Add successful agent response
        ticket.add_message(
            content=response_text,
            role="agent",
            confidence=confidence
        )

        # Store in memory for learning
        await self._store_interaction_memory(ticket, message, response_text)

        return {
            "ticket_id": ticket.id,
            "response": response_text,
            "escalated": False,
            "confidence": confidence,
            "channel": channel,
            "kb_hits": len(kb_results),
            "tokens": response_result.get("tokens", {}),
        }

    async def search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant FAQ entries.

        Uses both:
        1. mem0/Qdrant for semantic search of FAQ content
        2. FalkorDB for entity relationship queries

        Args:
            query: The search query

        Returns:
            List of relevant knowledge base entries
        """
        results = []

        # 1. Search FAQ memory via mem0/Qdrant
        if self.memory_manager:
            try:
                memories = await self.memory_manager.retrieve(
                    user_id="faq_system",
                    query=query,
                    agent_id="CustomerSupportAgent",
                    limit=5
                )
                for memory in memories:
                    results.append({
                        "source": "faq_memory",
                        "content": memory.get("memory", ""),
                        "score": memory.get("score", 0.5),
                        "metadata": memory.get("metadata", {}),
                    })
            except Exception as e:
                logger.warning(f"FAQ memory search failed: {e}")

        # 2. Search in-memory FAQs (simple text matching)
        query_lower = query.lower()
        for faq in self._faqs.values():
            if (query_lower in faq.question.lower() or
                any(tag in query_lower for tag in faq.tags)):
                results.append({
                    "source": "faq_local",
                    "content": f"Q: {faq.question}\nA: {faq.answer}",
                    "score": 0.8,
                    "category": faq.category,
                })

        # 3. Search knowledge graph for entity relationships
        if self.knowledge_graph_manager:
            try:
                # Extract potential entities from query
                entities = await self._extract_entities_from_query(query)
                for entity in entities:
                    graph_results = await self.knowledge_graph_manager.query_related(
                        entity_name=entity,
                        max_depth=2,
                        use_global=True
                    )
                    if graph_results.get("success") and graph_results.get("related"):
                        for related in graph_results["related"][:3]:
                            results.append({
                                "source": "knowledge_graph",
                                "content": f"Related to {entity}: {related['name']} ({related['type']})",
                                "score": 0.7 - (related.get("distance", 1) * 0.1),
                                "entity": entity,
                            })
            except Exception as e:
                logger.warning(f"Knowledge graph search failed: {e}")

        # Sort by score and limit
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:10]

    async def generate_response(
        self,
        query: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Generate a helpful response using the LLM.

        Args:
            query: The customer's question
            context: Contextual information (conversation history, KB hits)

        Returns:
            Dict with response text, confidence score, and token usage
        """
        try:
            user_prompt = f"""Customer Question: {query}

{context}

Please provide a helpful, accurate response to the customer's question.
After your response, on a new line, rate your confidence (0.0-1.0) in format: CONFIDENCE: X.X"""

            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="default",
                temperature=0.3,  # Lower for more consistent support responses
            )

            full_response = response["choices"][0]["message"]["content"]

            # Parse confidence from response
            confidence = 0.7  # Default
            response_text = full_response

            if "CONFIDENCE:" in full_response:
                parts = full_response.rsplit("CONFIDENCE:", 1)
                response_text = parts[0].strip()
                try:
                    confidence = float(parts[1].strip()[:3])
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    pass

            tokens = {
                "input": response["usage"]["prompt_tokens"],
                "output": response["usage"]["completion_tokens"],
                "total": response["usage"]["total_tokens"],
            }

            return {
                "response": response_text,
                "confidence": confidence,
                "tokens": tokens,
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                "response": "I apologize, but I'm having trouble processing your request right now. Let me connect you with a human agent who can help.",
                "confidence": 0.0,
                "tokens": {"input": 0, "output": 0, "total": 0},
            }

    def should_escalate(
        self,
        response: str,
        confidence: float,
        ticket: Optional[SupportTicket] = None
    ) -> Dict[str, Any]:
        """
        Determine if the request should be escalated to a human.

        Escalation triggers:
        1. Confidence score below threshold (0.6)
        2. Maximum resolution attempts exceeded (3)
        3. Response contains uncertainty indicators

        Args:
            response: The generated response
            confidence: Confidence score (0-1)
            ticket: The support ticket (for attempt tracking)

        Returns:
            Dict with should_escalate boolean and reason
        """
        reasons = []

        # Check confidence threshold
        if confidence < self.CONFIDENCE_THRESHOLD:
            reasons.append(f"Low confidence ({confidence:.2f} < {self.CONFIDENCE_THRESHOLD})")

        # Check resolution attempts
        if ticket and ticket.resolution_attempts >= self.MAX_RESOLUTION_ATTEMPTS:
            reasons.append(f"Maximum resolution attempts reached ({ticket.resolution_attempts})")

        # Check for uncertainty in response
        uncertainty_phrases = [
            "i'm not sure", "i don't know", "i cannot help",
            "beyond my capabilities", "please contact", "human agent"
        ]
        response_lower = response.lower()
        for phrase in uncertainty_phrases:
            if phrase in response_lower:
                reasons.append(f"Response indicates uncertainty: '{phrase}'")
                break

        should_escalate = len(reasons) > 0

        return {
            "should_escalate": should_escalate,
            "reason": "; ".join(reasons) if reasons else None,
            "confidence": confidence,
            "resolution_attempts": ticket.resolution_attempts if ticket else 0,
        }

    async def escalate(
        self,
        ticket_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate a ticket to a human agent.

        Args:
            ticket_id: ID of the ticket to escalate
            reason: Reason for escalation

        Returns:
            Dict with escalation status and details
        """
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket not found: {ticket_id}",
            }

        ticket.status = TicketStatus.ESCALATED
        ticket.escalated_at = datetime.utcnow()
        ticket.escalation_reason = reason
        ticket.updated_at = datetime.utcnow()

        # Add system message about escalation
        ticket.add_message(
            content=f"Ticket escalated to human agent. Reason: {reason}",
            role="system"
        )

        logger.info(f"Ticket {ticket_id} escalated: {reason}")

        # In production, this would:
        # 1. Notify human agents via Slack/email
        # 2. Add to escalation queue
        # 3. Send customer notification

        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": TicketStatus.ESCALATED.value,
            "reason": reason,
            "escalated_at": ticket.escalated_at.isoformat(),
        }

    # ---- Ticket Management ----

    def _get_or_create_ticket(
        self,
        ticket_id: Optional[str],
        customer_id: str,
        channel: str,
        subject: str
    ) -> SupportTicket:
        """Get existing ticket or create a new one"""
        if ticket_id and ticket_id in self._tickets:
            return self._tickets[ticket_id]

        ticket = SupportTicket(
            id=ticket_id or str(uuid.uuid4()),
            customer_id=customer_id,
            channel=SupportChannel(channel) if channel in [c.value for c in SupportChannel] else SupportChannel.CHAT,
            subject=subject,
        )
        self._tickets[ticket.id] = ticket
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[SupportTicket]:
        """Get a ticket by ID"""
        return self._tickets.get(ticket_id)

    def list_tickets(
        self,
        status: Optional[TicketStatus] = None,
        customer_id: Optional[str] = None,
        limit: int = 50
    ) -> List[SupportTicket]:
        """List tickets with optional filters"""
        tickets = list(self._tickets.values())

        if status:
            tickets = [t for t in tickets if t.status == status]
        if customer_id:
            tickets = [t for t in tickets if t.customer_id == customer_id]

        # Sort by updated_at descending
        tickets.sort(key=lambda t: t.updated_at, reverse=True)
        return tickets[:limit]

    def update_ticket_status(
        self,
        ticket_id: str,
        status: TicketStatus,
        resolution_note: Optional[str] = None
    ) -> Optional[SupportTicket]:
        """Update ticket status"""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.status = status
        ticket.updated_at = datetime.utcnow()

        if status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()
            if resolution_note:
                ticket.add_message(content=resolution_note, role="system")

        return ticket

    # ---- FAQ Management ----

    async def add_faq(
        self,
        question: str,
        answer: str,
        category: str = "general",
        tags: Optional[List[str]] = None
    ) -> FAQEntry:
        """
        Add a new FAQ entry to the knowledge base.

        Args:
            question: The FAQ question
            answer: The FAQ answer
            category: Category for organization
            tags: Tags for search

        Returns:
            The created FAQEntry
        """
        faq = FAQEntry(
            question=question,
            answer=answer,
            category=category,
            tags=tags or [],
        )
        self._faqs[faq.id] = faq

        # Store in memory for semantic search
        if self.memory_manager:
            try:
                await self.memory_manager.store(
                    user_id="faq_system",
                    agent_id="CustomerSupportAgent",
                    messages=[{
                        "role": "assistant",
                        "content": f"FAQ - Question: {question}\nAnswer: {answer}"
                    }],
                    metadata={
                        "type": "faq",
                        "faq_id": faq.id,
                        "category": category,
                        "tags": tags or [],
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to store FAQ in memory: {e}")

        # Store in knowledge graph if available
        if self.knowledge_graph_manager:
            try:
                await self.knowledge_graph_manager.store_entity(
                    name=f"FAQ: {question[:50]}",
                    entity_type="FAQ",
                    properties={
                        "faq_id": faq.id,
                        "question": question,
                        "answer": answer,
                        "category": category,
                    },
                    agent_id="support-agent"
                )
            except Exception as e:
                logger.warning(f"Failed to store FAQ in knowledge graph: {e}")

        logger.info(f"Added FAQ: {faq.id} - {question[:50]}...")
        return faq

    def get_faq(self, faq_id: str) -> Optional[FAQEntry]:
        """Get a FAQ by ID"""
        return self._faqs.get(faq_id)

    def list_faqs(
        self,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[FAQEntry]:
        """List FAQs with optional category filter"""
        faqs = list(self._faqs.values())

        if category:
            faqs = [f for f in faqs if f.category == category]

        faqs.sort(key=lambda f: f.updated_at, reverse=True)
        return faqs[:limit]

    def delete_faq(self, faq_id: str) -> bool:
        """Delete a FAQ"""
        if faq_id in self._faqs:
            del self._faqs[faq_id]
            return True
        return False

    # ---- Helper Methods ----

    def _contains_escalation_keywords(self, message: str) -> bool:
        """Check if message contains escalation trigger keywords"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.ESCALATION_KEYWORDS)

    def _build_response_context(
        self,
        ticket: SupportTicket,
        kb_results: List[Dict[str, Any]]
    ) -> str:
        """Build context string for response generation"""
        context_parts = []

        # Add conversation history (last 5 messages)
        if ticket.messages:
            context_parts.append("Previous conversation:")
            for msg in ticket.messages[-5:]:
                role_label = "Customer" if msg.role == "user" else "Agent"
                context_parts.append(f"  {role_label}: {msg.content[:200]}")

        # Add knowledge base results
        if kb_results:
            context_parts.append("\nRelevant knowledge base information:")
            for i, result in enumerate(kb_results[:3], 1):
                context_parts.append(f"  {i}. {result.get('content', '')[:300]}")

        return "\n".join(context_parts)

    async def _extract_entities_from_query(self, query: str) -> List[str]:
        """Extract potential entity names from a query for graph search"""
        # Simple extraction - look for capitalized words and quoted strings
        entities = []

        # Find quoted strings
        quoted = re.findall(r'"([^"]+)"', query)
        entities.extend(quoted)

        # Find capitalized words (potential proper nouns)
        words = query.split()
        for word in words:
            clean_word = word.strip(".,!?;:")
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                entities.append(clean_word)

        return list(set(entities))[:5]

    async def _store_interaction_memory(
        self,
        ticket: SupportTicket,
        query: str,
        response: str
    ) -> None:
        """Store successful interaction in memory for learning"""
        if not self.memory_manager:
            return

        try:
            await self.memory_manager.store(
                user_id=ticket.customer_id,
                agent_id="CustomerSupportAgent",
                messages=[
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response}
                ],
                metadata={
                    "ticket_id": ticket.id,
                    "channel": ticket.channel.value,
                    "type": "support_interaction",
                }
            )
        except Exception as e:
            logger.warning(f"Failed to store interaction memory: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get agent status with support metrics"""
        total_tickets = len(self._tickets)
        open_tickets = len([t for t in self._tickets.values() if t.status == TicketStatus.OPEN])
        escalated_tickets = len([t for t in self._tickets.values() if t.status == TicketStatus.ESCALATED])

        return {
            "name": self.name,
            "status": "ready",
            "memory_enabled": self.memory_manager is not None,
            "knowledge_graph_enabled": self.knowledge_graph_manager is not None,
            "metrics": {
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "escalated_tickets": escalated_tickets,
                "faqs_count": len(self._faqs),
            },
            "thresholds": {
                "confidence_threshold": self.CONFIDENCE_THRESHOLD,
                "max_resolution_attempts": self.MAX_RESOLUTION_ATTEMPTS,
            },
        }
