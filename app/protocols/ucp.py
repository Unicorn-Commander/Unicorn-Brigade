"""
UCP (Universal Commerce Protocol) Implementation

Google's standard for commerce and payments in AI agents.
https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/

Key concepts:
- Commerce Sessions: Transactional context for agent interactions
- Payment Intents: Secure payment handling
- Merchant Integration: Connect to payment providers
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class PaymentStatus(str, Enum):
    """Payment status states"""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    """Supported payment methods"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    WALLET = "wallet"
    CRYPTO = "crypto"
    SUBSCRIPTION = "subscription"
    CREDITS = "credits"  # Platform credits


class UCPPaymentIntent(BaseModel):
    """
    Payment Intent for agent-to-agent transactions.

    Used when Unicorn Squad calls paid agents on Unicorn Brigade.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    amount: float
    currency: str = "USD"
    description: str

    # Parties
    payer_id: str  # User or agent paying
    payee_id: str  # Agent receiving payment
    merchant_id: Optional[str] = None

    # Status
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method: Optional[PaymentMethod] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Reference to task/agent invocation
    task_id: Optional[str] = None
    agent_id: Optional[str] = None


class CommerceSession(BaseModel):
    """
    Commerce Session for agent marketplace transactions.

    Tracks a complete purchase flow from discovery to completion.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Session info
    user_id: str
    agent_id: str

    # Pricing
    price_per_call: float = 0.0
    currency: str = "USD"
    calls_made: int = 0
    total_cost: float = 0.0

    # Credits/balance
    user_credits: float = 0.0
    credits_used: float = 0.0

    # Status
    status: str = "active"  # "active", "completed", "expired"
    expires_at: Optional[datetime] = None

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    payments: List[str] = Field(default_factory=list)  # Payment intent IDs


class UCPPayment:
    """
    UCP Payment handler for Unicorn Brigade marketplace.

    Integrates with Ops-Center billing and external payment providers.
    """

    def __init__(
        self,
        ops_center_url: str = "http://ops-center:8084",
        stripe_enabled: bool = False,
    ):
        self.ops_center_url = ops_center_url
        self.stripe_enabled = stripe_enabled

        # In-memory sessions (should use Redis in production)
        self._sessions: Dict[str, CommerceSession] = {}
        self._payments: Dict[str, UCPPaymentIntent] = {}

    async def create_session(
        self,
        user_id: str,
        agent_id: str,
        price_per_call: float = 0.0,
        user_credits: float = 0.0,
    ) -> CommerceSession:
        """
        Create a commerce session for agent usage.

        Called when a user (or Unicorn Squad) starts using a paid agent.
        """
        session = CommerceSession(
            user_id=user_id,
            agent_id=agent_id,
            price_per_call=price_per_call,
            user_credits=user_credits,
        )

        self._sessions[session.id] = session
        logger.info(f"Created commerce session {session.id} for user {user_id}")

        return session

    async def charge_call(
        self,
        session_id: str,
        tokens_used: int = 0,
    ) -> Dict[str, Any]:
        """
        Charge for an agent call within a session.

        Returns the updated session and charge details.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.status != "active":
            return {"error": f"Session is {session.status}"}

        # Calculate cost
        call_cost = session.price_per_call

        # Check if user has credits
        if session.user_credits >= call_cost:
            # Use credits
            session.credits_used += call_cost
            session.user_credits -= call_cost
            payment_method = PaymentMethod.CREDITS
        else:
            # Need to create payment intent
            payment = await self.create_payment_intent(
                amount=call_cost,
                payer_id=session.user_id,
                payee_id=session.agent_id,
                description=f"Agent call in session {session_id}",
            )
            session.payments.append(payment.id)
            payment_method = PaymentMethod.SUBSCRIPTION  # Or appropriate method

        # Update session
        session.calls_made += 1
        session.total_cost += call_cost

        return {
            "session_id": session_id,
            "call_cost": call_cost,
            "total_cost": session.total_cost,
            "calls_made": session.calls_made,
            "credits_remaining": session.user_credits,
            "payment_method": payment_method.value,
        }

    async def create_payment_intent(
        self,
        amount: float,
        payer_id: str,
        payee_id: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UCPPaymentIntent:
        """
        Create a payment intent for agent services.

        This integrates with Ops-Center billing or Stripe.
        """
        payment = UCPPaymentIntent(
            amount=amount,
            payer_id=payer_id,
            payee_id=payee_id,
            description=description,
            metadata=metadata or {},
        )

        self._payments[payment.id] = payment

        # TODO: Integrate with Ops-Center billing
        # await self._create_ops_center_charge(payment)

        # TODO: Or integrate with Stripe
        # if self.stripe_enabled:
        #     await self._create_stripe_intent(payment)

        logger.info(
            f"Created payment intent {payment.id}: "
            f"${amount} from {payer_id} to {payee_id}"
        )

        return payment

    async def capture_payment(self, payment_id: str) -> bool:
        """Capture an authorized payment"""
        payment = self._payments.get(payment_id)
        if not payment:
            return False

        if payment.status != PaymentStatus.AUTHORIZED:
            return False

        payment.status = PaymentStatus.CAPTURED
        payment.updated_at = datetime.utcnow()

        logger.info(f"Captured payment {payment_id}")
        return True

    async def refund_payment(
        self,
        payment_id: str,
        reason: str = "",
    ) -> bool:
        """Refund a captured payment"""
        payment = self._payments.get(payment_id)
        if not payment:
            return False

        if payment.status != PaymentStatus.CAPTURED:
            return False

        payment.status = PaymentStatus.REFUNDED
        payment.updated_at = datetime.utcnow()
        payment.metadata["refund_reason"] = reason

        logger.info(f"Refunded payment {payment_id}: {reason}")
        return True

    def get_session(self, session_id: str) -> Optional[CommerceSession]:
        """Get a commerce session by ID"""
        return self._sessions.get(session_id)

    def get_payment(self, payment_id: str) -> Optional[UCPPaymentIntent]:
        """Get a payment intent by ID"""
        return self._payments.get(payment_id)

    async def get_user_balance(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's credit balance from Ops-Center.

        This integrates with the existing Ops-Center billing system.
        """
        # TODO: Call Ops-Center API
        # For now, return mock data
        return {
            "user_id": user_id,
            "credits": 100.0,
            "currency": "USD",
            "subscription_tier": "pro",
        }

    async def add_credits(
        self,
        user_id: str,
        amount: float,
        source: str = "purchase",
    ) -> bool:
        """Add credits to user account"""
        # TODO: Integrate with Ops-Center
        logger.info(f"Added {amount} credits to user {user_id}")
        return True


# Convenience function for quick billing checks
async def check_can_afford(
    user_id: str,
    agent_price: float,
    ucp: Optional[UCPPayment] = None,
) -> bool:
    """Quick check if user can afford an agent call"""
    if agent_price == 0:
        return True

    ucp = ucp or UCPPayment()
    balance = await ucp.get_user_balance(user_id)
    return balance.get("credits", 0) >= agent_price
