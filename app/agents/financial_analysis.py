"""
Financial Analysis Agent with budget tracking and expense analysis.

This agent handles financial operations including:
- Budget tracking and spend analysis
- Expense categorization using LLM
- Financial forecasting based on historical data
- Budget alerts when thresholds exceeded
- Cost-cutting opportunity identification
- Report generation (daily/weekly/monthly summaries)
- Multi-currency support

Key features:
- In-memory storage (with optional PostgreSQL integration)
- LLM-powered expense categorization
- Configurable budget thresholds and alerts
- Historical data analysis for forecasting
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import uuid
import logging
import statistics
from zoneinfo import ZoneInfo

from app.agents.base import BaseAgent
from app.core.timezones import BUSINESS_TIMEZONE
from app.llm.ops_center_client import OpsCenterLLMClient
from app.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

BUSINESS_ZONE = ZoneInfo(BUSINESS_TIMEZONE)


def _now_utc() -> datetime:
    """Return the current instant as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def _normalize_legacy_utc(value: datetime) -> datetime:
    """Normalize a stored datetime, treating legacy naive values as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_query_bound(value: str, *, end: bool = False) -> datetime:
    """Parse a query bound into an aware UTC instant.

    A bare date names a New York business day.  An end-date bound advances to
    the next local midnight so callers can use a half-open interval.
    Other naive datetimes are New York wall time; aware values retain their
    represented instant while being normalized to UTC for comparison.
    """
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BUSINESS_ZONE)
        return parsed.astimezone(timezone.utc)

    local_bound = parsed_date.replace(tzinfo=BUSINESS_ZONE)
    if end:
        local_bound += timedelta(days=1)
    return local_bound.astimezone(timezone.utc)


def _parse_business_datetime(value: str) -> datetime:
    """Parse a newly supplied transaction time as an aware UTC instant."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BUSINESS_ZONE)
    return parsed.astimezone(timezone.utc)


class TransactionType(str, Enum):
    """Types of financial transactions"""
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    REFUND = "refund"


class ExpenseCategory(str, Enum):
    """Standard expense categories"""
    PAYROLL = "payroll"
    MARKETING = "marketing"
    SOFTWARE = "software"
    INFRASTRUCTURE = "infrastructure"
    TRAVEL = "travel"
    OFFICE = "office"
    UTILITIES = "utilities"
    PROFESSIONAL_SERVICES = "professional_services"
    EQUIPMENT = "equipment"
    TRAINING = "training"
    INSURANCE = "insurance"
    TAXES = "taxes"
    SUBSCRIPTIONS = "subscriptions"
    MEALS_ENTERTAINMENT = "meals_entertainment"
    SHIPPING = "shipping"
    MISCELLANEOUS = "miscellaneous"
    UNCATEGORIZED = "uncategorized"


class AlertSeverity(str, Enum):
    """Budget alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReportPeriod(str, Enum):
    """Report time periods"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# Currency exchange rates (simplified - in production, use real-time API)
CURRENCY_RATES = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
    "CAD": 0.74,
    "AUD": 0.65,
    "CHF": 1.12,
    "CNY": 0.14,
    "INR": 0.012,
    "MXN": 0.059,
}


@dataclass
class Transaction:
    """A financial transaction record"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    amount: Decimal = Decimal("0.00")
    currency: str = "USD"
    transaction_type: TransactionType = TransactionType.EXPENSE
    category: ExpenseCategory = ExpenseCategory.UNCATEGORIZED
    description: str = ""
    vendor: Optional[str] = None
    date: datetime = field(default_factory=_now_utc)
    created_at: datetime = field(default_factory=_now_utc)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: str = "system"
    account_id: Optional[str] = None
    confidence: float = 1.0  # Confidence in categorization

    def __post_init__(self):
        self.date = _normalize_legacy_utc(self.date)
        self.created_at = _normalize_legacy_utc(self.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "amount": float(self.amount),
            "currency": self.currency,
            "transaction_type": self.transaction_type.value,
            "category": self.category.value,
            "description": self.description,
            "vendor": self.vendor,
            "date": self.date.isoformat(),
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "confidence": self.confidence,
        }

    def to_usd(self) -> Decimal:
        """Convert amount to USD"""
        rate = CURRENCY_RATES.get(self.currency, 1.0)
        return self.amount * Decimal(str(rate))


@dataclass
class Budget:
    """A budget definition for a category or total"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: Optional[ExpenseCategory] = None  # None means total budget
    amount: Decimal = Decimal("0.00")
    currency: str = "USD"
    period: ReportPeriod = ReportPeriod.MONTHLY
    alert_threshold: float = 0.8  # Alert at 80% by default
    critical_threshold: float = 0.95  # Critical at 95%
    start_date: datetime = field(default_factory=_now_utc)
    end_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    user_id: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.start_date = _normalize_legacy_utc(self.start_date)
        if self.end_date is not None:
            self.end_date = _normalize_legacy_utc(self.end_date)
        self.created_at = _normalize_legacy_utc(self.created_at)
        self.updated_at = _normalize_legacy_utc(self.updated_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value if self.category else None,
            "amount": float(self.amount),
            "currency": self.currency,
            "period": self.period.value,
            "alert_threshold": self.alert_threshold,
            "critical_threshold": self.critical_threshold,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id,
            "metadata": self.metadata,
        }


@dataclass
class BudgetAlert:
    """A budget alert notification"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    budget_id: str = ""
    budget_name: str = ""
    category: Optional[ExpenseCategory] = None
    severity: AlertSeverity = AlertSeverity.WARNING
    message: str = ""
    current_spend: Decimal = Decimal("0.00")
    budget_amount: Decimal = Decimal("0.00")
    percentage_used: float = 0.0
    created_at: datetime = field(default_factory=_now_utc)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.created_at = _normalize_legacy_utc(self.created_at)
        if self.acknowledged_at is not None:
            self.acknowledged_at = _normalize_legacy_utc(self.acknowledged_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "budget_id": self.budget_id,
            "budget_name": self.budget_name,
            "category": self.category.value if self.category else None,
            "severity": self.severity.value,
            "message": self.message,
            "current_spend": float(self.current_spend),
            "budget_amount": float(self.budget_amount),
            "percentage_used": self.percentage_used,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "metadata": self.metadata,
        }


@dataclass
class FinancialReport:
    """A financial report summary"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    period: ReportPeriod = ReportPeriod.MONTHLY
    start_date: datetime = field(default_factory=_now_utc)
    end_date: datetime = field(default_factory=_now_utc)
    total_income: Decimal = Decimal("0.00")
    total_expenses: Decimal = Decimal("0.00")
    net_flow: Decimal = Decimal("0.00")
    by_category: Dict[str, Decimal] = field(default_factory=dict)
    transaction_count: int = 0
    currency: str = "USD"
    top_vendors: List[Dict[str, Any]] = field(default_factory=list)
    budget_status: List[Dict[str, Any]] = field(default_factory=list)
    trends: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_now_utc)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.start_date = _normalize_legacy_utc(self.start_date)
        self.end_date = _normalize_legacy_utc(self.end_date)
        self.generated_at = _normalize_legacy_utc(self.generated_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "period": self.period.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_income": float(self.total_income),
            "total_expenses": float(self.total_expenses),
            "net_flow": float(self.net_flow),
            "by_category": {k: float(v) for k, v in self.by_category.items()},
            "transaction_count": self.transaction_count,
            "currency": self.currency,
            "top_vendors": self.top_vendors,
            "budget_status": self.budget_status,
            "trends": self.trends,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }


class FinancialAnalysisAgent(BaseAgent):
    """
    AI-powered Financial Analysis Agent.

    Features:
    - Record and track transactions
    - Automatically categorize expenses using LLM
    - Set and monitor budgets with alerts
    - Generate financial forecasts
    - Identify cost-cutting opportunities
    - Generate comprehensive financial reports
    - Multi-currency support
    """

    # Category keywords for simple matching (fallback)
    CATEGORY_KEYWORDS = {
        ExpenseCategory.PAYROLL: ["salary", "wages", "payroll", "bonus", "commission"],
        ExpenseCategory.MARKETING: ["marketing", "advertising", "ads", "campaign", "promotion", "social media"],
        ExpenseCategory.SOFTWARE: ["software", "saas", "license", "subscription", "app", "platform"],
        ExpenseCategory.INFRASTRUCTURE: ["aws", "azure", "gcp", "cloud", "hosting", "server", "infrastructure"],
        ExpenseCategory.TRAVEL: ["flight", "hotel", "airfare", "lodging", "uber", "lyft", "taxi", "travel"],
        ExpenseCategory.OFFICE: ["office", "furniture", "supplies", "desk", "chair"],
        ExpenseCategory.UTILITIES: ["electric", "gas", "water", "internet", "phone", "utility"],
        ExpenseCategory.PROFESSIONAL_SERVICES: ["legal", "accounting", "consulting", "attorney", "cpa"],
        ExpenseCategory.EQUIPMENT: ["equipment", "hardware", "computer", "laptop", "monitor"],
        ExpenseCategory.TRAINING: ["training", "course", "education", "conference", "workshop"],
        ExpenseCategory.INSURANCE: ["insurance", "liability", "coverage"],
        ExpenseCategory.TAXES: ["tax", "irs", "state tax", "property tax"],
        ExpenseCategory.SUBSCRIPTIONS: ["subscription", "monthly", "annual plan"],
        ExpenseCategory.MEALS_ENTERTAINMENT: ["meal", "lunch", "dinner", "restaurant", "catering", "entertainment"],
        ExpenseCategory.SHIPPING: ["shipping", "freight", "delivery", "postage", "fedex", "ups"],
    }

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        llm_client: Optional[OpsCenterLLMClient] = None,
    ):
        super().__init__("FinancialAnalysisAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

        # In-memory storage (replace with DB in production)
        self._transactions: Dict[str, Transaction] = {}
        self._budgets: Dict[str, Budget] = {}
        self._alerts: Dict[str, BudgetAlert] = {}
        self._reports: Dict[str, FinancialReport] = {}

        # System prompt for expense categorization
        self.categorization_prompt = """You are a financial analyst assistant. Categorize the following expense transaction into one of these categories:

Categories:
- payroll: Salaries, wages, bonuses, commissions
- marketing: Advertising, campaigns, social media, promotions
- software: SaaS, licenses, software subscriptions
- infrastructure: Cloud services (AWS, Azure, GCP), hosting, servers
- travel: Flights, hotels, transportation
- office: Office supplies, furniture
- utilities: Electricity, internet, phone
- professional_services: Legal, accounting, consulting
- equipment: Hardware, computers, monitors
- training: Courses, conferences, workshops
- insurance: Business insurance, liability
- taxes: Tax payments
- subscriptions: General subscriptions
- meals_entertainment: Meals, restaurants, entertainment
- shipping: Shipping, freight, delivery
- miscellaneous: Other expenses that don't fit elsewhere
- uncategorized: Cannot determine category

Transaction:
Description: {description}
Vendor: {vendor}
Amount: {amount} {currency}

Respond with ONLY the category name (lowercase, with underscores). Example: professional_services"""

        # System prompt for cost-cutting analysis
        self.cost_cutting_prompt = """You are a financial analyst. Analyze the following spending data and identify cost-cutting opportunities.

Spending Summary:
{spending_summary}

Top Vendors:
{top_vendors}

Recent Trends:
{trends}

Provide 3-5 specific, actionable recommendations for reducing costs. Be specific about which categories or vendors to focus on and estimate potential savings where possible.

Format your response as a numbered list:
1. [Recommendation]
2. [Recommendation]
..."""

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a financial analysis task from the workflow engine.

        Args:
            task: Task dictionary with operation type and parameters

        Returns:
            Task result with analysis results
        """
        logger.info(f"FinancialAnalysisAgent executing task: {task.get('task_id')}")

        try:
            operation = task.get("operation", "analyze")
            params = task.get("params", {})

            if operation == "record_transaction":
                result = await self.record_transaction(**params)
            elif operation == "analyze":
                result = await self.get_spend_analysis(**params)
            elif operation == "forecast":
                result = await self.get_forecast(**params)
            elif operation == "generate_report":
                result = await self.generate_report(**params)
            elif operation == "check_budgets":
                result = await self.check_budget_status()
            else:
                result = {"error": f"Unknown operation: {operation}"}

            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": result,
            }

        except Exception as e:
            logger.error(f"FinancialAnalysisAgent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
            }

    # ---- Transaction Management ----

    async def record_transaction(
        self,
        amount: float,
        description: str,
        transaction_type: str = "expense",
        currency: str = "USD",
        vendor: Optional[str] = None,
        category: Optional[str] = None,
        date: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: str = "system",
        account_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a new financial transaction.

        If category is not provided, uses LLM to categorize automatically.

        Args:
            amount: Transaction amount
            description: Description of the transaction
            transaction_type: Type (expense, income, transfer, refund)
            currency: Currency code (USD, EUR, etc.)
            vendor: Vendor name
            category: Expense category (optional, will auto-categorize if not provided)
            date: Transaction date (ISO format, defaults to now)
            tags: List of tags
            user_id: User identifier
            account_id: Account identifier
            metadata: Additional metadata

        Returns:
            Created transaction details
        """
        # Parse transaction type
        try:
            tx_type = TransactionType(transaction_type.lower())
        except ValueError:
            tx_type = TransactionType.EXPENSE

        # Parse date
        tx_date = _parse_business_datetime(date) if date else _now_utc()

        # Auto-categorize if not provided
        confidence = 1.0
        if category:
            try:
                tx_category = ExpenseCategory(category.lower())
            except ValueError:
                tx_category = ExpenseCategory.UNCATEGORIZED
        else:
            # Use LLM to categorize
            categorization = await self._categorize_expense(description, vendor, amount, currency)
            tx_category = categorization["category"]
            confidence = categorization["confidence"]

        # Create transaction
        transaction = Transaction(
            amount=Decimal(str(amount)),
            currency=currency.upper(),
            transaction_type=tx_type,
            category=tx_category,
            description=description,
            vendor=vendor,
            date=tx_date,
            tags=tags or [],
            metadata=metadata or {},
            user_id=user_id,
            account_id=account_id,
            confidence=confidence,
        )

        self._transactions[transaction.id] = transaction

        # Check budget alerts
        if tx_type == TransactionType.EXPENSE:
            await self._check_budget_alerts(tx_category)

        # Store in memory for learning
        await self._store_transaction_memory(transaction)

        logger.info(f"Recorded transaction: {transaction.id} - {description} ({tx_category.value})")

        return {
            "success": True,
            "transaction": transaction.to_dict(),
            "auto_categorized": category is None,
            "category_confidence": confidence,
        }

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get a transaction by ID"""
        return self._transactions.get(transaction_id)

    def list_transactions(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        vendor: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        currency: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Transaction]:
        """List transactions with filters"""
        transactions = list(self._transactions.values())

        # Apply filters
        if user_id:
            transactions = [t for t in transactions if t.user_id == user_id]
        if category:
            try:
                cat = ExpenseCategory(category.lower())
                transactions = [t for t in transactions if t.category == cat]
            except ValueError:
                pass
        if transaction_type:
            try:
                tx_type = TransactionType(transaction_type.lower())
                transactions = [t for t in transactions if t.transaction_type == tx_type]
            except ValueError:
                pass
        if start_date:
            start = _parse_query_bound(start_date)
            transactions = [
                t for t in transactions if self._transaction_date_utc(t) >= start
            ]
        if end_date:
            end = _parse_query_bound(end_date, end=True)
            transactions = [
                t for t in transactions if self._transaction_date_utc(t) < end
            ]
        if vendor:
            vendor_lower = vendor.lower()
            transactions = [t for t in transactions if t.vendor and vendor_lower in t.vendor.lower()]
        if min_amount is not None:
            transactions = [t for t in transactions if float(t.amount) >= min_amount]
        if max_amount is not None:
            transactions = [t for t in transactions if float(t.amount) <= max_amount]
        if currency:
            transactions = [t for t in transactions if t.currency == currency.upper()]

        # Sort by date descending
        transactions.sort(key=self._transaction_date_utc, reverse=True)

        # Apply pagination
        return transactions[offset:offset + limit]

    # ---- Budget Management ----

    def set_budget(
        self,
        name: str,
        amount: float,
        category: Optional[str] = None,
        period: str = "monthly",
        currency: str = "USD",
        alert_threshold: float = 0.8,
        critical_threshold: float = 0.95,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Set a budget limit for a category or total spend.

        Args:
            name: Budget name
            amount: Budget amount
            category: Expense category (None for total budget)
            period: Budget period (daily, weekly, monthly, quarterly, yearly)
            currency: Currency code
            alert_threshold: Percentage to trigger warning (0-1)
            critical_threshold: Percentage to trigger critical alert (0-1)
            start_date: Budget start date (ISO format)
            end_date: Budget end date (ISO format, optional)
            user_id: User identifier
            metadata: Additional metadata

        Returns:
            Created budget details
        """
        # Parse category
        budget_category = None
        if category:
            try:
                budget_category = ExpenseCategory(category.lower())
            except ValueError:
                return {"success": False, "error": f"Invalid category: {category}"}

        # Parse period
        try:
            budget_period = ReportPeriod(period.lower())
        except ValueError:
            budget_period = ReportPeriod.MONTHLY

        # Parse dates
        start = _parse_query_bound(start_date) if start_date else _now_utc()
        end = _parse_query_bound(end_date, end=True) if end_date else None

        budget = Budget(
            name=name,
            category=budget_category,
            amount=Decimal(str(amount)),
            currency=currency.upper(),
            period=budget_period,
            alert_threshold=alert_threshold,
            critical_threshold=critical_threshold,
            start_date=start,
            end_date=end,
            user_id=user_id,
            metadata=metadata or {},
        )

        self._budgets[budget.id] = budget
        logger.info(f"Set budget: {budget.id} - {name} ({amount} {currency})")

        return {
            "success": True,
            "budget": budget.to_dict(),
        }

    def get_budget(self, budget_id: str) -> Optional[Budget]:
        """Get a budget by ID"""
        return self._budgets.get(budget_id)

    def list_budgets(self, user_id: Optional[str] = None) -> List[Budget]:
        """List all budgets"""
        budgets = list(self._budgets.values())
        if user_id:
            budgets = [b for b in budgets if b.user_id == user_id]
        return budgets

    async def check_budget_status(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check status of all budgets and return current spending vs limits.

        Returns:
            Budget status for all budgets with alerts
        """
        budgets = self.list_budgets(user_id)
        status_list = []
        new_alerts = []

        for budget in budgets:
            # Calculate period dates
            period_start, period_end = self._get_period_dates(budget.period, budget.start_date)

            # Get transactions for this period
            if budget.category:
                transactions = [
                    t for t in self._transactions.values()
                    if t.category == budget.category
                    and t.transaction_type == TransactionType.EXPENSE
                    and period_start <= self._transaction_date_utc(t) < period_end
                ]
            else:
                transactions = [
                    t for t in self._transactions.values()
                    if t.transaction_type == TransactionType.EXPENSE
                    and period_start <= self._transaction_date_utc(t) < period_end
                ]

            # Calculate total spend (convert to budget currency)
            total_spend = Decimal("0.00")
            for tx in transactions:
                # Convert to USD first, then to budget currency
                usd_amount = tx.to_usd()
                budget_rate = CURRENCY_RATES.get(budget.currency, 1.0)
                total_spend += usd_amount / Decimal(str(budget_rate))

            # Calculate percentage
            percentage = float(total_spend / budget.amount) if budget.amount > 0 else 0.0

            # Determine severity
            if percentage >= budget.critical_threshold:
                severity = AlertSeverity.CRITICAL
            elif percentage >= budget.alert_threshold:
                severity = AlertSeverity.WARNING
            else:
                severity = AlertSeverity.INFO

            status = {
                "budget_id": budget.id,
                "budget_name": budget.name,
                "category": budget.category.value if budget.category else "total",
                "budget_amount": float(budget.amount),
                "current_spend": float(total_spend),
                "remaining": float(budget.amount - total_spend),
                "percentage_used": round(percentage * 100, 2),
                "period": budget.period.value,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "currency": budget.currency,
                "status": "ok" if severity == AlertSeverity.INFO else severity.value,
            }
            status_list.append(status)

            # Create alert if threshold exceeded
            if severity != AlertSeverity.INFO:
                alert = BudgetAlert(
                    budget_id=budget.id,
                    budget_name=budget.name,
                    category=budget.category,
                    severity=severity,
                    message=f"Budget '{budget.name}' is at {round(percentage * 100, 1)}% ({total_spend:.2f}/{budget.amount:.2f} {budget.currency})",
                    current_spend=total_spend,
                    budget_amount=budget.amount,
                    percentage_used=percentage,
                )
                self._alerts[alert.id] = alert
                new_alerts.append(alert.to_dict())

        return {
            "budgets": status_list,
            "alerts": new_alerts,
            "total_budgets": len(budgets),
            "budgets_over_threshold": len(new_alerts),
        }

    # ---- Analysis & Forecasting ----

    async def get_spend_analysis(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Get comprehensive spend analysis for a period.

        Args:
            start_date: Analysis start date (ISO format)
            end_date: Analysis end date (ISO format)
            user_id: Filter by user
            currency: Output currency

        Returns:
            Spend analysis with breakdowns and insights
        """
        # Default to last 30 days
        end = _parse_query_bound(end_date, end=True) if end_date else _now_utc()
        start = _parse_query_bound(start_date) if start_date else end - timedelta(days=30)

        # Get transactions
        transactions = [
            t for t in self._transactions.values()
            if start <= self._transaction_date_utc(t) < end
        ]
        if user_id:
            transactions = [t for t in transactions if t.user_id == user_id]

        # Convert to target currency
        target_rate = CURRENCY_RATES.get(currency.upper(), 1.0)

        # Calculate totals
        total_income = Decimal("0.00")
        total_expenses = Decimal("0.00")
        by_category: Dict[str, Decimal] = {}
        by_vendor: Dict[str, Decimal] = {}

        for tx in transactions:
            # Convert amount
            usd_amount = tx.to_usd()
            converted = usd_amount / Decimal(str(target_rate))

            if tx.transaction_type == TransactionType.INCOME:
                total_income += converted
            elif tx.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER]:
                total_expenses += converted

                # By category
                cat_key = tx.category.value
                by_category[cat_key] = by_category.get(cat_key, Decimal("0.00")) + converted

                # By vendor
                if tx.vendor:
                    by_vendor[tx.vendor] = by_vendor.get(tx.vendor, Decimal("0.00")) + converted

        # Calculate averages and percentages
        category_percentages = {}
        for cat, amount in by_category.items():
            if total_expenses > 0:
                category_percentages[cat] = round(float(amount / total_expenses) * 100, 2)

        # Top vendors
        top_vendors = sorted(
            [{"vendor": v, "amount": float(a)} for v, a in by_vendor.items()],
            key=lambda x: x["amount"],
            reverse=True
        )[:10]

        # Daily average
        days = max((end - start).days, 1)
        daily_avg = float(total_expenses / days)

        return {
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "days": days,
            },
            "summary": {
                "total_income": float(total_income),
                "total_expenses": float(total_expenses),
                "net_flow": float(total_income - total_expenses),
                "transaction_count": len(transactions),
                "daily_average_expense": round(daily_avg, 2),
            },
            "by_category": {k: float(v) for k, v in by_category.items()},
            "category_percentages": category_percentages,
            "top_vendors": top_vendors,
            "currency": currency.upper(),
        }

    async def get_forecast(
        self,
        periods_ahead: int = 3,
        period_type: str = "monthly",
        user_id: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Generate financial forecast based on historical data.

        Uses simple moving average and trend analysis.

        Args:
            periods_ahead: Number of periods to forecast
            period_type: Period type (daily, weekly, monthly)
            user_id: Filter by user
            currency: Output currency

        Returns:
            Forecast with predicted spending
        """
        # Get historical data
        period = ReportPeriod(period_type.lower())
        target_rate = CURRENCY_RATES.get(currency.upper(), 1.0)

        # Collect historical period totals
        historical_totals = []
        now = _now_utc()

        # Get last 12 periods of data
        for i in range(12, 0, -1):
            period_start, period_end = self._get_period_dates(
                period,
                now - timedelta(days=i * self._get_period_days(period))
            )

            period_total = Decimal("0.00")
            for tx in self._transactions.values():
                if (tx.transaction_type == TransactionType.EXPENSE and
                    period_start <= self._transaction_date_utc(tx) < period_end):
                    if user_id is None or tx.user_id == user_id:
                        usd_amount = tx.to_usd()
                        period_total += usd_amount / Decimal(str(target_rate))

            if period_total > 0:
                historical_totals.append({
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "total": float(period_total),
                })

        if len(historical_totals) < 2:
            return {
                "error": "Insufficient historical data for forecasting",
                "minimum_periods_required": 2,
                "current_periods": len(historical_totals),
            }

        # Calculate statistics
        totals = [h["total"] for h in historical_totals]
        avg = statistics.mean(totals)
        std_dev = statistics.stdev(totals) if len(totals) > 1 else 0

        # Simple trend (linear regression)
        n = len(totals)
        sum_x = sum(range(n))
        sum_y = sum(totals)
        sum_xy = sum(i * totals[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n

        # Generate forecasts
        forecasts = []
        for i in range(periods_ahead):
            forecast_period = n + i
            predicted = intercept + slope * forecast_period

            # Apply some bounds (no negative, max 2x average)
            predicted = max(0, min(predicted, avg * 2))

            period_start, period_end = self._get_period_dates(
                period,
                now + timedelta(days=i * self._get_period_days(period))
            )

            forecasts.append({
                "period": i + 1,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "predicted_expense": round(predicted, 2),
                "confidence_low": round(predicted - std_dev, 2),
                "confidence_high": round(predicted + std_dev, 2),
            })

        # Trend description
        if slope > avg * 0.05:
            trend = "increasing"
        elif slope < -avg * 0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "historical_summary": {
                "periods_analyzed": len(historical_totals),
                "average_spend": round(avg, 2),
                "std_deviation": round(std_dev, 2),
                "trend": trend,
                "trend_slope": round(slope, 2),
            },
            "forecasts": forecasts,
            "currency": currency.upper(),
            "period_type": period_type,
            "methodology": "Simple linear regression with moving average",
        }

    async def identify_cost_cutting_opportunities(
        self,
        user_id: Optional[str] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Identify cost-cutting opportunities using LLM analysis.

        Returns:
            List of recommendations for cost reduction
        """
        # Get recent spend analysis
        analysis = await self.get_spend_analysis(user_id=user_id, currency=currency)

        if analysis["summary"]["transaction_count"] < 5:
            return {
                "recommendations": ["Insufficient transaction data for analysis. Record more transactions to get personalized recommendations."],
                "data_quality": "insufficient",
            }

        # Prepare data for LLM
        spending_summary = f"""
Total Expenses: {analysis['summary']['total_expenses']} {currency}
Daily Average: {analysis['summary']['daily_average_expense']} {currency}
Categories:
"""
        for cat, amount in sorted(analysis["by_category"].items(), key=lambda x: x[1], reverse=True):
            pct = analysis["category_percentages"].get(cat, 0)
            spending_summary += f"  - {cat}: {amount} {currency} ({pct}%)\n"

        top_vendors = "\n".join([
            f"  - {v['vendor']}: {v['amount']} {currency}"
            for v in analysis["top_vendors"][:5]
        ])

        # Get forecast for trends
        forecast = await self.get_forecast(user_id=user_id, currency=currency)
        trends = f"Trend: {forecast.get('historical_summary', {}).get('trend', 'unknown')}"

        try:
            prompt = self.cost_cutting_prompt.format(
                spending_summary=spending_summary,
                top_vendors=top_vendors,
                trends=trends,
            )

            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.5,
            )

            recommendations_text = response["choices"][0]["message"]["content"]

            # Parse recommendations
            recommendations = [
                line.strip().lstrip("0123456789.-) ")
                for line in recommendations_text.split("\n")
                if line.strip() and any(c.isalpha() for c in line)
            ]

            return {
                "recommendations": recommendations[:5],  # Limit to 5
                "analysis_summary": {
                    "total_expenses": analysis["summary"]["total_expenses"],
                    "top_categories": list(analysis["by_category"].keys())[:3],
                    "top_vendors": [v["vendor"] for v in analysis["top_vendors"][:3]],
                    "trend": forecast.get("historical_summary", {}).get("trend", "unknown"),
                },
                "currency": currency,
            }

        except Exception as e:
            logger.error(f"Error generating cost-cutting recommendations: {e}")
            return {
                "recommendations": [
                    "Review top spending categories for potential optimizations",
                    "Negotiate with high-spend vendors for better rates",
                    "Identify and eliminate unused subscriptions",
                ],
                "error": str(e),
            }

    # ---- Reports ----

    async def generate_report(
        self,
        period: str = "monthly",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
        currency: str = "USD",
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive financial report.

        Args:
            period: Report period (daily, weekly, monthly, quarterly, yearly)
            start_date: Report start date (ISO format)
            end_date: Report end date (ISO format)
            user_id: Filter by user
            currency: Output currency
            include_recommendations: Include cost-cutting recommendations

        Returns:
            Complete financial report
        """
        # Parse period
        try:
            report_period = ReportPeriod(period.lower())
        except ValueError:
            report_period = ReportPeriod.MONTHLY

        # Calculate dates
        now = _now_utc()
        if start_date and end_date:
            start = _parse_query_bound(start_date)
            end = _parse_query_bound(end_date, end=True)
        else:
            start, end = self._get_period_dates(report_period, now)

        # Get analysis
        analysis = await self.get_spend_analysis(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            user_id=user_id,
            currency=currency,
        )

        # Get budget status
        budget_status = await self.check_budget_status(user_id)

        # Get forecast
        forecast = await self.get_forecast(
            periods_ahead=1,
            period_type=period,
            user_id=user_id,
            currency=currency,
        )

        # Get recommendations if requested
        recommendations = []
        if include_recommendations:
            cost_cutting = await self.identify_cost_cutting_opportunities(user_id, currency)
            recommendations = cost_cutting.get("recommendations", [])

        # Create report
        report = FinancialReport(
            period=report_period,
            start_date=start,
            end_date=end,
            total_income=Decimal(str(analysis["summary"]["total_income"])),
            total_expenses=Decimal(str(analysis["summary"]["total_expenses"])),
            net_flow=Decimal(str(analysis["summary"]["net_flow"])),
            by_category={k: Decimal(str(v)) for k, v in analysis["by_category"].items()},
            transaction_count=analysis["summary"]["transaction_count"],
            currency=currency,
            top_vendors=analysis["top_vendors"],
            budget_status=budget_status["budgets"],
            trends=forecast.get("historical_summary", {}),
            recommendations=recommendations,
        )

        self._reports[report.id] = report

        return {
            "success": True,
            "report": report.to_dict(),
        }

    def get_report(self, report_id: str) -> Optional[FinancialReport]:
        """Get a report by ID"""
        return self._reports.get(report_id)

    def list_reports(self, limit: int = 10) -> List[FinancialReport]:
        """List recent reports"""
        reports = list(self._reports.values())
        reports.sort(key=lambda r: _normalize_legacy_utc(r.generated_at), reverse=True)
        return reports[:limit]

    # ---- Alerts ----

    def get_alerts(
        self,
        acknowledged: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[BudgetAlert]:
        """Get budget alerts with filters"""
        alerts = list(self._alerts.values())

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        if severity:
            try:
                sev = AlertSeverity(severity.lower())
                alerts = [a for a in alerts if a.severity == sev]
            except ValueError:
                pass

        alerts.sort(key=lambda a: _normalize_legacy_utc(a.created_at), reverse=True)
        return alerts[:limit]

    def acknowledge_alert(self, alert_id: str) -> Optional[BudgetAlert]:
        """Acknowledge a budget alert"""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = _now_utc()
        return alert

    # ---- Helper Methods ----

    async def _categorize_expense(
        self,
        description: str,
        vendor: Optional[str],
        amount: float,
        currency: str,
    ) -> Dict[str, Any]:
        """Categorize an expense using LLM"""
        # First try keyword matching
        desc_lower = description.lower()
        vendor_lower = (vendor or "").lower()
        combined = f"{desc_lower} {vendor_lower}"

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return {"category": category, "confidence": 0.9}

        # Use LLM for complex cases
        try:
            prompt = self.categorization_prompt.format(
                description=description,
                vendor=vendor or "Unknown",
                amount=amount,
                currency=currency,
            )

            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.1,
            )

            category_str = response["choices"][0]["message"]["content"].strip().lower()

            try:
                return {"category": ExpenseCategory(category_str), "confidence": 0.85}
            except ValueError:
                return {"category": ExpenseCategory.UNCATEGORIZED, "confidence": 0.5}

        except Exception as e:
            logger.warning(f"Error categorizing expense: {e}")
            return {"category": ExpenseCategory.UNCATEGORIZED, "confidence": 0.3}

    async def _check_budget_alerts(self, category: ExpenseCategory) -> None:
        """Check if any budgets need alerts after a transaction"""
        # Trigger async budget check
        await self.check_budget_status()

    @staticmethod
    def _transaction_date_utc(transaction: Transaction) -> datetime:
        """Return and retain a transaction's normalized UTC timestamp."""
        transaction.date = _normalize_legacy_utc(transaction.date)
        return transaction.date

    def _get_period_dates(self, period: ReportPeriod, reference: datetime) -> tuple:
        """Get half-open UTC bounds for a New York calendar period."""
        reference_local = _normalize_legacy_utc(reference).astimezone(BUSINESS_ZONE)

        if period == ReportPeriod.DAILY:
            start = reference_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == ReportPeriod.WEEKLY:
            start = reference_local - timedelta(days=reference_local.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == ReportPeriod.MONTHLY:
            start = reference_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if reference_local.month == 12:
                end = start.replace(year=reference_local.year + 1, month=1)
            else:
                end = start.replace(month=reference_local.month + 1)
        elif period == ReportPeriod.QUARTERLY:
            quarter = (reference_local.month - 1) // 3
            start = reference_local.replace(
                month=quarter * 3 + 1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            if quarter == 3:
                end = start.replace(year=reference_local.year + 1, month=1)
            else:
                end = start.replace(month=(quarter + 1) * 3 + 1)
        else:  # YEARLY
            start = reference_local.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end = start.replace(year=reference_local.year + 1)

        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    def _get_period_days(self, period: ReportPeriod) -> int:
        """Get approximate days in a period"""
        return {
            ReportPeriod.DAILY: 1,
            ReportPeriod.WEEKLY: 7,
            ReportPeriod.MONTHLY: 30,
            ReportPeriod.QUARTERLY: 90,
            ReportPeriod.YEARLY: 365,
        }.get(period, 30)

    async def _store_transaction_memory(self, transaction: Transaction) -> None:
        """Store transaction in memory for learning"""
        if not self.memory_manager:
            return

        try:
            await self.memory_manager.store(
                user_id=transaction.user_id,
                agent_id="FinancialAnalysisAgent",
                messages=[{
                    "role": "assistant",
                    "content": f"Transaction: {transaction.description} - {transaction.amount} {transaction.currency} ({transaction.category.value})"
                }],
                metadata={
                    "type": "transaction",
                    "transaction_id": transaction.id,
                    "category": transaction.category.value,
                    "amount": float(transaction.amount),
                    "currency": transaction.currency,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to store transaction memory: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get agent status with financial metrics"""
        total_transactions = len(self._transactions)
        total_budgets = len(self._budgets)
        active_alerts = len([a for a in self._alerts.values() if not a.acknowledged])

        return {
            "name": self.name,
            "status": "ready",
            "memory_enabled": self.memory_manager is not None,
            "metrics": {
                "total_transactions": total_transactions,
                "total_budgets": total_budgets,
                "active_alerts": active_alerts,
                "reports_generated": len(self._reports),
            },
            "supported_currencies": list(CURRENCY_RATES.keys()),
            "expense_categories": [c.value for c in ExpenseCategory],
        }
