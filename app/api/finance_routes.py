"""
Financial Analysis API Routes

Provides endpoints for:
- Recording and listing transactions
- Budget management and monitoring
- Spend analysis and forecasting
- Report generation
- Budget alerts
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.agents.financial_analysis import (
    FinancialAnalysisAgent,
    Transaction,
    Budget,
    BudgetAlert,
    FinancialReport,
    TransactionType,
    ExpenseCategory,
    AlertSeverity,
    ReportPeriod,
    CURRENCY_RATES,
)
from app.memory.manager import MemoryManager
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/finance", tags=["finance"])

# Global finance agent instance (initialized in init_finance_routes)
finance_agent: Optional[FinancialAnalysisAgent] = None


def init_finance_routes(
    memory_manager: Optional[MemoryManager] = None,
    llm_client: Optional[OpsCenterLLMClient] = None,
):
    """Initialize finance routes with dependencies"""
    global finance_agent
    finance_agent = FinancialAnalysisAgent(
        memory_manager=memory_manager,
        llm_client=llm_client,
    )
    logger.info("Finance routes initialized with FinancialAnalysisAgent")


def get_finance_agent() -> FinancialAnalysisAgent:
    """Dependency to get the finance agent"""
    if not finance_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Finance agent not initialized"
        )
    return finance_agent


# ---- Request/Response Models ----

class RecordTransactionRequest(BaseModel):
    """Request to record a new transaction"""
    amount: float = Field(..., description="Transaction amount", gt=0)
    description: str = Field(..., description="Transaction description", min_length=1)
    transaction_type: str = Field("expense", description="Type: expense, income, transfer, refund")
    currency: str = Field("USD", description="Currency code (USD, EUR, GBP, etc.)")
    vendor: Optional[str] = Field(None, description="Vendor name")
    category: Optional[str] = Field(None, description="Expense category (auto-detected if not provided)")
    date: Optional[str] = Field(None, description="Transaction date (ISO format, defaults to now)")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering")
    user_id: str = Field("system", description="User identifier")
    account_id: Optional[str] = Field(None, description="Account identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RecordTransactionResponse(BaseModel):
    """Response from recording a transaction"""
    success: bool
    transaction: Dict[str, Any]
    auto_categorized: bool
    category_confidence: float


class TransactionListResponse(BaseModel):
    """Response with list of transactions"""
    transactions: List[Dict[str, Any]]
    count: int
    filters: Dict[str, Any]


class TransactionDetailResponse(BaseModel):
    """Response with transaction details"""
    transaction: Dict[str, Any]


class SetBudgetRequest(BaseModel):
    """Request to set a budget"""
    name: str = Field(..., description="Budget name", min_length=1)
    amount: float = Field(..., description="Budget amount", gt=0)
    category: Optional[str] = Field(None, description="Expense category (None for total budget)")
    period: str = Field("monthly", description="Budget period: daily, weekly, monthly, quarterly, yearly")
    currency: str = Field("USD", description="Currency code")
    alert_threshold: float = Field(0.8, description="Warning threshold (0-1)", ge=0, le=1)
    critical_threshold: float = Field(0.95, description="Critical threshold (0-1)", ge=0, le=1)
    start_date: Optional[str] = Field(None, description="Budget start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Budget end date (ISO format)")
    user_id: str = Field("system", description="User identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SetBudgetResponse(BaseModel):
    """Response from setting a budget"""
    success: bool
    budget: Dict[str, Any]


class BudgetStatusResponse(BaseModel):
    """Response with budget status"""
    budgets: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    total_budgets: int
    budgets_over_threshold: int


class SpendAnalysisResponse(BaseModel):
    """Response with spend analysis"""
    period: Dict[str, Any]
    summary: Dict[str, Any]
    by_category: Dict[str, float]
    category_percentages: Dict[str, float]
    top_vendors: List[Dict[str, Any]]
    currency: str


class ForecastResponse(BaseModel):
    """Response with financial forecast"""
    historical_summary: Dict[str, Any]
    forecasts: List[Dict[str, Any]]
    currency: str
    period_type: str
    methodology: str


class CostCuttingResponse(BaseModel):
    """Response with cost-cutting recommendations"""
    recommendations: List[str]
    analysis_summary: Optional[Dict[str, Any]] = None
    currency: str


class GenerateReportRequest(BaseModel):
    """Request to generate a financial report"""
    period: str = Field("monthly", description="Report period: daily, weekly, monthly, quarterly, yearly")
    start_date: Optional[str] = Field(None, description="Report start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Report end date (ISO format)")
    user_id: Optional[str] = Field(None, description="Filter by user")
    currency: str = Field("USD", description="Output currency")
    include_recommendations: bool = Field(True, description="Include cost-cutting recommendations")


class GenerateReportResponse(BaseModel):
    """Response with generated report"""
    success: bool
    report: Dict[str, Any]


class AlertListResponse(BaseModel):
    """Response with list of alerts"""
    alerts: List[Dict[str, Any]]
    count: int


class FinanceStatusResponse(BaseModel):
    """Response with finance agent status"""
    name: str
    status: str
    memory_enabled: bool
    metrics: Dict[str, int]
    supported_currencies: List[str]
    expense_categories: List[str]


# ---- Transaction Endpoints ----

@router.post("/transactions", response_model=RecordTransactionResponse)
async def record_transaction(
    request: RecordTransactionRequest,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Record a new financial transaction.

    If category is not provided, the agent will automatically categorize
    the expense using LLM analysis of the description and vendor.

    Supported currencies: USD, EUR, GBP, JPY, CAD, AUD, CHF, CNY, INR, MXN
    """
    try:
        result = await agent.record_transaction(
            amount=request.amount,
            description=request.description,
            transaction_type=request.transaction_type,
            currency=request.currency,
            vendor=request.vendor,
            category=request.category,
            date=request.date,
            tags=request.tags,
            user_id=request.user_id,
            account_id=request.account_id,
            metadata=request.metadata,
        )

        return RecordTransactionResponse(**result)

    except Exception as e:
        logger.error(f"Error recording transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    transaction_type: Optional[str] = Query(None, description="Filter by type (expense, income, etc.)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    vendor: Optional[str] = Query(None, description="Filter by vendor (partial match)"),
    min_amount: Optional[float] = Query(None, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, description="Maximum amount"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    limit: int = Query(100, description="Maximum transactions to return", le=1000),
    offset: int = Query(0, description="Offset for pagination"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    List transactions with optional filters.

    Supports filtering by user, category, type, date range, vendor, amount range,
    and currency. Results are sorted by date descending.
    """
    try:
        transactions = agent.list_transactions(
            user_id=user_id,
            category=category,
            transaction_type=transaction_type,
            start_date=start_date,
            end_date=end_date,
            vendor=vendor,
            min_amount=min_amount,
            max_amount=max_amount,
            currency=currency,
            limit=limit,
            offset=offset,
        )

        return TransactionListResponse(
            transactions=[t.to_dict() for t in transactions],
            count=len(transactions),
            filters={
                "user_id": user_id,
                "category": category,
                "transaction_type": transaction_type,
                "start_date": start_date,
                "end_date": end_date,
                "vendor": vendor,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "currency": currency,
                "limit": limit,
                "offset": offset,
            },
        )

    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/transactions/{transaction_id}", response_model=TransactionDetailResponse)
async def get_transaction(
    transaction_id: str,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """Get details of a specific transaction by ID."""
    transaction = agent.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction not found: {transaction_id}"
        )

    return TransactionDetailResponse(transaction=transaction.to_dict())


# ---- Analysis Endpoints ----

@router.get("/analysis", response_model=SpendAnalysisResponse)
async def get_spend_analysis(
    start_date: Optional[str] = Query(None, description="Analysis start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Analysis end date (ISO format)"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    currency: str = Query("USD", description="Output currency"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Get comprehensive spend analysis for a period.

    Includes:
    - Total income and expenses
    - Net cash flow
    - Breakdown by category with percentages
    - Top vendors by spend
    - Daily average expense

    Defaults to last 30 days if dates not specified.
    """
    try:
        result = await agent.get_spend_analysis(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            currency=currency,
        )

        return SpendAnalysisResponse(**result)

    except Exception as e:
        logger.error(f"Error getting spend analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    periods_ahead: int = Query(3, description="Number of periods to forecast", ge=1, le=12),
    period_type: str = Query("monthly", description="Period type: daily, weekly, monthly"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    currency: str = Query("USD", description="Output currency"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Generate financial forecast based on historical data.

    Uses simple linear regression with moving average analysis.
    Requires at least 2 periods of historical data for forecasting.

    Returns predicted expenses with confidence intervals.
    """
    try:
        result = await agent.get_forecast(
            periods_ahead=periods_ahead,
            period_type=period_type,
            user_id=user_id,
            currency=currency,
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        return ForecastResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting forecast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cost-cutting")
async def get_cost_cutting_opportunities(
    user_id: Optional[str] = Query(None, description="Filter by user"),
    currency: str = Query("USD", description="Output currency"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Identify cost-cutting opportunities using AI analysis.

    Analyzes spending patterns and provides specific, actionable
    recommendations for reducing costs.
    """
    try:
        result = await agent.identify_cost_cutting_opportunities(
            user_id=user_id,
            currency=currency,
        )

        return result

    except Exception as e:
        logger.error(f"Error identifying cost-cutting opportunities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ---- Budget Endpoints ----

@router.post("/budget", response_model=SetBudgetResponse)
async def set_budget(
    request: SetBudgetRequest,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Set a budget limit for a category or total spend.

    If category is not specified, creates a total budget that tracks
    all expenses. Budget alerts are triggered when spending exceeds
    the configured thresholds.

    Available categories: payroll, marketing, software, infrastructure,
    travel, office, utilities, professional_services, equipment, training,
    insurance, taxes, subscriptions, meals_entertainment, shipping, miscellaneous
    """
    try:
        result = agent.set_budget(
            name=request.name,
            amount=request.amount,
            category=request.category,
            period=request.period,
            currency=request.currency,
            alert_threshold=request.alert_threshold,
            critical_threshold=request.critical_threshold,
            start_date=request.start_date,
            end_date=request.end_date,
            user_id=request.user_id,
            metadata=request.metadata,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to set budget")
            )

        return SetBudgetResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting budget: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/budget/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    user_id: Optional[str] = Query(None, description="Filter by user"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Check status of all budgets and get current spending vs limits.

    Returns:
    - Current spend for each budget
    - Remaining budget
    - Percentage used
    - Any new alerts for exceeded thresholds
    """
    try:
        result = await agent.check_budget_status(user_id=user_id)
        return BudgetStatusResponse(**result)

    except Exception as e:
        logger.error(f"Error checking budget status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/budgets")
async def list_budgets(
    user_id: Optional[str] = Query(None, description="Filter by user"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """List all budgets."""
    budgets = agent.list_budgets(user_id=user_id)
    return {
        "budgets": [b.to_dict() for b in budgets],
        "count": len(budgets),
    }


@router.get("/budgets/{budget_id}")
async def get_budget(
    budget_id: str,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """Get a specific budget by ID."""
    budget = agent.get_budget(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget not found: {budget_id}"
        )

    return {"budget": budget.to_dict()}


# ---- Alert Endpoints ----

@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, critical)"),
    limit: int = Query(50, description="Maximum alerts to return"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Get budget alerts.

    Alerts are created when spending exceeds budget thresholds.
    Can filter by acknowledged status and severity level.
    """
    try:
        alerts = agent.get_alerts(
            acknowledged=acknowledged,
            severity=severity,
            limit=limit,
        )

        return AlertListResponse(
            alerts=[a.to_dict() for a in alerts],
            count=len(alerts),
        )

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """Acknowledge a budget alert."""
    alert = agent.acknowledge_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )

    return {
        "message": "Alert acknowledged",
        "alert": alert.to_dict(),
    }


# ---- Report Endpoints ----

@router.get("/report", response_model=GenerateReportResponse)
async def generate_report(
    period: str = Query("monthly", description="Report period: daily, weekly, monthly, quarterly, yearly"),
    start_date: Optional[str] = Query(None, description="Report start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Report end date (ISO format)"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    currency: str = Query("USD", description="Output currency"),
    include_recommendations: bool = Query(True, description="Include cost-cutting recommendations"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """
    Generate a comprehensive financial report.

    Includes:
    - Income and expense summary
    - Category breakdown
    - Budget status
    - Spending trends
    - Top vendors
    - Cost-cutting recommendations (optional)

    Reports are stored and can be retrieved later by ID.
    """
    try:
        result = await agent.generate_report(
            period=period,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            currency=currency,
            include_recommendations=include_recommendations,
        )

        return GenerateReportResponse(**result)

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/reports")
async def list_reports(
    limit: int = Query(10, description="Maximum reports to return"),
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """List recent financial reports."""
    reports = agent.list_reports(limit=limit)
    return {
        "reports": [r.to_dict() for r in reports],
        "count": len(reports),
    }


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """Get a specific report by ID."""
    report = agent.get_report(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}"
        )

    return {"report": report.to_dict()}


# ---- Status Endpoint ----

@router.get("/status", response_model=FinanceStatusResponse)
async def get_finance_status(
    agent: FinancialAnalysisAgent = Depends(get_finance_agent),
):
    """Get status of the finance agent and metrics."""
    status_info = agent.get_status()
    return FinanceStatusResponse(**status_info)


# ---- Reference Data Endpoints ----

@router.get("/categories")
async def list_categories():
    """List all available expense categories."""
    return {
        "categories": [
            {"value": c.value, "name": c.name.replace("_", " ").title()}
            for c in ExpenseCategory
        ],
    }


@router.get("/currencies")
async def list_currencies():
    """List all supported currencies with exchange rates."""
    return {
        "currencies": [
            {"code": code, "rate_to_usd": rate}
            for code, rate in CURRENCY_RATES.items()
        ],
        "base_currency": "USD",
    }


@router.get("/transaction-types")
async def list_transaction_types():
    """List all transaction types."""
    return {
        "types": [
            {"value": t.value, "name": t.name.replace("_", " ").title()}
            for t in TransactionType
        ],
    }
