"""
Monitoring and Alerting API Routes

Provides endpoints for:
- System health monitoring
- Service availability checks
- Alert management
- Metric collection
- Incident tracking
- Webhook configuration
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime
import asyncio
import logging
import os
import time

import httpx
from sqlalchemy import text

from app.db.database import async_session
from app.services.scheduler import get_scheduler
from app.api.system_routes import local_llm_base_url, ops_center_base_url
from app.agents.monitoring_agent import (
    MonitoringAgent,
    AlertSeverity,
    AlertStatus,
    ServiceStatus,
    IncidentStatus,
    CheckType,
    Alert,
    ServiceCheck,
    Incident,
    MetricThreshold,
    WebhookConfig,
)
from app.auth.middleware import require_api_key, require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Global monitoring agent instance (initialized in init_monitoring_routes)
monitoring_agent: Optional[MonitoringAgent] = None


def init_monitoring_routes(
    slack_client=None,
    email_sender=None,
    memory_manager=None,
):
    """Initialize monitoring routes with dependencies"""
    global monitoring_agent
    monitoring_agent = MonitoringAgent(
        memory_manager=memory_manager,
        slack_client=slack_client,
        email_sender=email_sender,
    )
    logger.info("Monitoring routes initialized with MonitoringAgent")


async def shutdown_monitoring_routes():
    """Shutdown monitoring agent and cleanup"""
    global monitoring_agent
    if monitoring_agent:
        await monitoring_agent.close()
        monitoring_agent = None
    logger.info("Monitoring routes shutdown")


def get_monitoring_agent() -> MonitoringAgent:
    """Dependency to get the monitoring agent"""
    if not monitoring_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring agent not initialized"
        )
    return monitoring_agent


# ============== Request/Response Models ==============

class HealthCheckResponse(BaseModel):
    """System health check response"""
    timestamp: str
    platform: str
    hostname: str
    status: str
    metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]] = []
    error: Optional[str] = None


class ServiceCheckRequest(BaseModel):
    """Request to register a service check"""
    name: str = Field(..., description="Unique name for the service check")
    check_type: str = Field("http", description="Type of check: http, tcp, database, redis")
    target: str = Field(..., description="Target URL, host:port, or identifier")
    interval_seconds: int = Field(30, description="Check interval in seconds")
    timeout_seconds: int = Field(10, description="Timeout in seconds")
    expected_status_codes: List[int] = Field([200, 201, 204], description="Expected HTTP status codes")
    expected_body_contains: Optional[str] = Field(None, description="Expected string in response body")
    headers: Dict[str, str] = Field({}, description="HTTP headers to include")
    enabled: bool = Field(True, description="Whether the check is enabled")
    failure_threshold: int = Field(3, description="Failures before alerting")


class ServiceCheckResponse(BaseModel):
    """Service check status response"""
    name: str
    check_type: str
    target: str
    status: str
    latency_ms: float = 0
    timestamp: str
    error: Optional[str] = None
    status_code: Optional[int] = None


class ServiceListResponse(BaseModel):
    """List of service check results"""
    timestamp: str
    services: List[Dict[str, Any]]
    summary: Dict[str, int]


class TriggerCheckRequest(BaseModel):
    """Request to trigger a health check"""
    services: Optional[List[str]] = Field(None, description="Specific services to check")


class TriggerCheckResponse(BaseModel):
    """Response from triggered health check"""
    timestamp: str
    system: Dict[str, Any]
    services: List[Dict[str, Any]]
    service_summary: Optional[Dict[str, int]] = None


class AlertResponse(BaseModel):
    """Alert details response"""
    id: str
    name: str
    message: str
    severity: str
    status: str
    source: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    labels: Dict[str, str] = {}
    created_at: str
    updated_at: str
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    notification_count: int = 0
    fingerprint: str


class AlertListResponse(BaseModel):
    """List of alerts response"""
    alerts: List[Dict[str, Any]]
    count: int


class AlertActionRequest(BaseModel):
    """Request to acknowledge or resolve an alert"""
    user: str = Field(..., description="User performing the action")


class AlertActionResponse(BaseModel):
    """Response from alert action"""
    success: bool
    alert: Optional[Dict[str, Any]] = None
    message: str


class MetricRecordRequest(BaseModel):
    """Request to record a metric"""
    name: str = Field(..., description="Metric name (e.g., 'api.latency.p99')")
    value: float = Field(..., description="Metric value")
    unit: str = Field("", description="Unit of measurement")
    labels: Dict[str, str] = Field({}, description="Additional labels")


class MetricRecordResponse(BaseModel):
    """Response from recording a metric"""
    success: bool
    metric: Dict[str, Any]


class MetricsResponse(BaseModel):
    """Response with metric data"""
    name: Optional[str] = None
    metrics: Any  # Can be dict or list depending on query
    count: int
    baseline: Optional[Dict[str, Any]] = None


class ThresholdRequest(BaseModel):
    """Request to set a threshold"""
    metric_name: str = Field(..., description="Metric name to set threshold for")
    warning_threshold: Optional[float] = Field(None, description="Warning threshold")
    error_threshold: Optional[float] = Field(None, description="Error threshold")
    critical_threshold: Optional[float] = Field(None, description="Critical threshold")
    comparison: str = Field("gt", description="Comparison: gt, lt, eq, gte, lte")
    window_seconds: int = Field(60, description="Evaluation window in seconds")
    min_samples: int = Field(1, description="Minimum samples to trigger")


class ThresholdResponse(BaseModel):
    """Response with threshold data"""
    thresholds: List[Dict[str, Any]]
    count: int


class IncidentRequest(BaseModel):
    """Request to create an incident"""
    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Incident description")
    severity: str = Field("warning", description="Severity: info, warning, error, critical")
    alert_ids: Optional[List[str]] = Field(None, description="Related alert IDs")
    affected_services: Optional[List[str]] = Field(None, description="Affected service names")


class IncidentUpdateRequest(BaseModel):
    """Request to update incident status"""
    status: str = Field(..., description="New status: open, investigating, identified, monitoring, resolved")
    message: str = Field(..., description="Status update message")
    user: Optional[str] = Field(None, description="User making the update")


class IncidentResponse(BaseModel):
    """Response with incident data"""
    incident: Dict[str, Any]


class IncidentListResponse(BaseModel):
    """List of incidents response"""
    incidents: List[Dict[str, Any]]
    count: int


class WebhookRequest(BaseModel):
    """Request to configure a webhook"""
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    method: str = Field("POST", description="HTTP method")
    headers: Dict[str, str] = Field({}, description="HTTP headers")
    enabled: bool = Field(True, description="Whether the webhook is enabled")
    severities: List[str] = Field(["info", "warning", "error", "critical"], description="Alert severities to send")
    retry_count: int = Field(3, description="Number of retries")
    retry_delay_seconds: int = Field(5, description="Delay between retries")


class WebhookResponse(BaseModel):
    """Response with webhook data"""
    webhook: Dict[str, Any]


class WebhookListResponse(BaseModel):
    """List of webhooks response"""
    webhooks: List[Dict[str, Any]]
    count: int


class LogAnalysisRequest(BaseModel):
    """Request to analyze a log line"""
    log_line: str = Field(..., description="Log line to analyze")
    source: Optional[str] = Field(None, description="Source of the log")


class LogAnalysisResponse(BaseModel):
    """Response from log analysis"""
    patterns: List[str]
    severity: Optional[str] = None
    is_new_error: bool
    source: Optional[str] = None
    error_rates: List[Dict[str, Any]]


class AnomalyCheckRequest(BaseModel):
    """Request to check for anomaly"""
    metric_name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Value to check")


class AnomalyCheckResponse(BaseModel):
    """Response from anomaly check"""
    metric_name: str
    value: float
    is_anomaly: bool
    z_score_analysis: Dict[str, Any]
    iqr_analysis: Dict[str, Any]
    baseline: Dict[str, Any]


class MonitoringStatusResponse(BaseModel):
    """Monitoring agent status response"""
    name: str
    status: str
    memory_enabled: bool
    slack_enabled: bool
    scheduled_checks_running: bool
    metrics: Dict[str, int]


# ============== Built-in Platform Service Checks ==============
#
# Real async health probes for the services Brigade actually depends on.
# Every check is short-timeout and never raises: failures come back as an
# "unhealthy" entry with the error in `detail`.

PROBE_TIMEOUT_SECONDS = 2.0


def _elapsed_ms(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 1)


def _err_detail(e: Exception) -> str:
    return (str(e) or type(e).__name__)[:200]


async def _check_database() -> Dict[str, Any]:
    """PostgreSQL liveness: SELECT 1 on the app's async engine."""
    start = time.monotonic()
    try:
        async with async_session() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")), timeout=PROBE_TIMEOUT_SECONDS
            )
        return {
            "name": "database",
            "status": "healthy",
            "latency_ms": _elapsed_ms(start),
            "detail": "PostgreSQL SELECT 1 ok",
        }
    except Exception as e:
        return {
            "name": "database",
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": _err_detail(e),
        }


async def _check_falkordb() -> Dict[str, Any]:
    """FalkorDB liveness: RESP PING over a raw TCP connection."""
    host = os.getenv("FALKORDB_HOST", "unicorn-falkordb")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD") or None
    target = f"{host}:{port}"
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=PROBE_TIMEOUT_SECONDS
        )
        try:
            reply = b""
            if password:
                # requirepass is set on unicorn-falkordb (2026-09-02): AUTH first,
                # otherwise PING answers -NOAUTH and the probe reads "degraded".
                writer.write(f"AUTH {password}\r\n".encode())
                await asyncio.wait_for(writer.drain(), timeout=PROBE_TIMEOUT_SECONDS)
                reply = await asyncio.wait_for(
                    reader.read(64), timeout=PROBE_TIMEOUT_SECONDS
                )
            if not password or reply.startswith(b"+OK"):
                writer.write(b"PING\r\n")
                await asyncio.wait_for(writer.drain(), timeout=PROBE_TIMEOUT_SECONDS)
                reply = await asyncio.wait_for(
                    reader.read(32), timeout=PROBE_TIMEOUT_SECONDS
                )
        finally:
            writer.close()
        if reply.startswith(b"+PONG"):
            status_str, detail = "healthy", f"{target} PING ok"
        elif reply:
            # e.g. -NOAUTH: the server answered, so it's up but not fully probeable
            status_str = "degraded"
            detail = f"{target} replied: {reply[:32].decode(errors='replace').strip()}"
        else:
            status_str, detail = "degraded", f"{target} connected, empty PING reply"
        return {
            "name": "falkordb",
            "status": status_str,
            "latency_ms": _elapsed_ms(start),
            "detail": detail,
        }
    except Exception as e:
        return {
            "name": "falkordb",
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": f"{target} {_err_detail(e)}",
        }


async def _check_http_service(name: str, url: str) -> Dict[str, Any]:
    """Generic HTTP GET liveness check (any response < 500 counts as up)."""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
        ok = resp.status_code < 500
        return {
            "name": name,
            "status": "healthy" if ok else "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": f"{url} → HTTP {resp.status_code}",
        }
    except Exception as e:
        return {
            "name": name,
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": f"{url} → {_err_detail(e)}",
        }


async def _check_scheduler() -> Dict[str, Any]:
    """Brigade scheduler state: APScheduler running + registered job count."""
    start = time.monotonic()
    try:
        sched = get_scheduler()
        engine = getattr(sched, "scheduler", None) if sched else None
        if engine is not None and engine.running:
            jobs = len(engine.get_jobs())
            return {
                "name": "scheduler",
                "status": "healthy",
                "latency_ms": _elapsed_ms(start),
                "detail": f"APScheduler running, {jobs} scheduled job(s)",
            }
        return {
            "name": "scheduler",
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": "Brigade scheduler not running",
        }
    except Exception as e:
        return {
            "name": "scheduler",
            "status": "unhealthy",
            "latency_ms": _elapsed_ms(start),
            "detail": _err_detail(e),
        }


async def _platform_service_checks() -> List[Dict[str, Any]]:
    """Run all built-in checks concurrently. Never raises."""
    checks = [_check_database()]
    if os.getenv("FALKORDB_ENABLED", "false").lower() == "true":
        checks.append(_check_falkordb())
    checks.append(
        _check_http_service("qdrant", os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/"))
    )
    checks.append(_check_http_service("ops-center-llm", f"{ops_center_base_url()}/health"))
    checks.append(_check_http_service("local-llm-router", f"{local_llm_base_url()}/v1/models"))
    if os.getenv("LANGFUSE_ENABLED", "false").lower() == "true":
        checks.append(
            _check_http_service("langfuse", os.getenv("LANGFUSE_HOST", "http://localhost:3000").rstrip("/"))
        )
    checks.append(_check_scheduler())

    results = await asyncio.gather(*checks, return_exceptions=True)
    services: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            services.append({
                "name": "unknown",
                "status": "unhealthy",
                "latency_ms": 0,
                "detail": _err_detail(result),
            })
        else:
            services.append(result)
    return services


# ============== Health Endpoints ==============

@router.get("/health", response_model=HealthCheckResponse)
async def get_system_health(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
):
    """
    Get system health status.

    Returns current CPU, memory, disk usage and overall health status.
    Automatically records metrics and checks thresholds.
    """
    try:
        health = await agent.get_system_health()
        return HealthCheckResponse(**health)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/services", response_model=ServiceListResponse)
async def get_services_status(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get real health status of the platform's core services.

    Runs live async checks (database, FalkorDB, Qdrant, Ops-Center LLM,
    local LLM router, Langfuse, Brigade scheduler — each with a short
    timeout) and merges in any checks registered on the MonitoringAgent.
    Never raises: failures are reported per-service as "unhealthy".
    """
    services = await _platform_service_checks()

    # Merge in user-registered MonitoringAgent checks, if the agent is up.
    if monitoring_agent is not None:
        try:
            registered = await monitoring_agent.check_all_services()
            services.extend(registered.get("services", []))
        except Exception as e:
            logger.warning(f"MonitoringAgent service checks failed: {e}")

    summary = {"healthy": 0, "unhealthy": 0, "degraded": 0, "unknown": 0}
    for svc in services:
        status_str = svc.get("status", "unknown")
        summary[status_str if status_str in summary else "unknown"] += 1

    return ServiceListResponse(
        timestamp=datetime.utcnow().isoformat(),
        services=services,
        summary=summary,
    )


@router.post("/check", response_model=TriggerCheckResponse)
async def trigger_health_check(
    request: TriggerCheckRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Trigger an immediate health check.

    Optionally specify specific services to check.
    """
    try:
        result = await agent.trigger_health_check(services=request.services)
        return TriggerCheckResponse(**result)
    except Exception as e:
        logger.error(f"Error triggering health check: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============== Service Check Management ==============

@router.post("/services/register")
async def register_service_check(
    request: ServiceCheckRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Register a new service health check.

    The service will be periodically checked based on the configured interval.
    """
    try:
        check_type = CheckType(request.check_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid check type: {request.check_type}. Valid: {[c.value for c in CheckType]}"
        )

    check = ServiceCheck(
        name=request.name,
        check_type=check_type,
        target=request.target,
        interval_seconds=request.interval_seconds,
        timeout_seconds=request.timeout_seconds,
        expected_status_codes=request.expected_status_codes,
        expected_body_contains=request.expected_body_contains,
        headers=request.headers,
        enabled=request.enabled,
        failure_threshold=request.failure_threshold,
    )

    result = agent.register_service_check(check)
    return {"message": f"Service check '{request.name}' registered", "check": result.to_dict()}


@router.get("/services/list")
async def list_service_checks(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all registered service checks."""
    return {"checks": agent.list_service_checks(), "count": len(agent.list_service_checks())}


@router.delete("/services/{name}")
async def remove_service_check(
    name: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Remove a service check."""
    if agent.remove_service_check(name):
        return {"message": f"Service check '{name}' removed"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Service check not found: {name}"
    )


@router.post("/services/{name}/check", response_model=ServiceCheckResponse)
async def check_single_service(
    name: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Check a specific service immediately."""
    result = await agent.check_service(name)
    if "error" in result and result.get("status") is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"]
        )
    return ServiceCheckResponse(**result)


# ============== Alert Endpoints ==============

@router.get("/alerts", response_model=AlertListResponse)
async def list_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all active alerts.

    Optionally filter by severity level.
    """
    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}. Valid: {[s.value for s in AlertSeverity]}"
            )

    alerts = agent.get_active_alerts(severity=severity_enum)
    return AlertListResponse(alerts=alerts, count=len(alerts))


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get details of a specific alert."""
    alert = agent.get_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )
    return {"alert": alert.to_dict()}


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertActionResponse)
async def acknowledge_alert(
    alert_id: str,
    request: AlertActionRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Acknowledge an active alert.

    Acknowledged alerts remain visible but indicate someone is handling the issue.
    """
    alert = agent.acknowledge_alert(alert_id, request.user)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )

    return AlertActionResponse(
        success=True,
        alert=alert.to_dict(),
        message=f"Alert acknowledged by {request.user}"
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertActionResponse)
async def resolve_alert(
    alert_id: str,
    request: AlertActionRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Resolve an alert.

    Resolved alerts are marked as fixed and will not generate new notifications.
    """
    alert = agent.resolve_alert(alert_id, request.user)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )

    return AlertActionResponse(
        success=True,
        alert=alert.to_dict(),
        message=f"Alert resolved by {request.user}"
    )


# ============== Metric Endpoints ==============

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    name: Optional[str] = Query(None, description="Filter by metric name"),
    limit: int = Query(100, description="Maximum metrics to return"),
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get collected metrics.

    Returns metric data with baseline statistics for anomaly detection.
    """
    result = agent.get_metrics(name=name, limit=limit)
    return MetricsResponse(**result)


@router.post("/metrics/record", response_model=MetricRecordResponse)
async def record_metric(
    request: MetricRecordRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Record a custom metric value.

    The metric will be stored and checked against configured thresholds.
    """
    try:
        metric = await agent.record_metric(
            name=request.name,
            value=request.value,
            unit=request.unit,
            labels=request.labels,
        )
        return MetricRecordResponse(success=True, metric=metric.to_dict())
    except Exception as e:
        logger.error(f"Error recording metric: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/metrics/anomaly", response_model=AnomalyCheckResponse)
async def check_metric_anomaly(
    request: AnomalyCheckRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Check if a metric value is anomalous.

    Uses Z-score and IQR statistical methods for detection.
    """
    try:
        result = await agent.check_anomaly(request.metric_name, request.value)
        return AnomalyCheckResponse(**result)
    except Exception as e:
        logger.error(f"Error checking anomaly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============== Threshold Endpoints ==============

@router.post("/thresholds")
async def set_threshold(
    request: ThresholdRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Set or update alert thresholds for a metric.

    Metrics exceeding thresholds will generate alerts.
    """
    threshold = MetricThreshold(
        metric_name=request.metric_name,
        warning_threshold=request.warning_threshold,
        error_threshold=request.error_threshold,
        critical_threshold=request.critical_threshold,
        comparison=request.comparison,
        window_seconds=request.window_seconds,
        min_samples=request.min_samples,
    )

    result = agent.set_threshold(threshold)
    return {"message": f"Threshold set for {request.metric_name}", "threshold": result.to_dict()}


@router.get("/thresholds", response_model=ThresholdResponse)
async def list_thresholds(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all configured thresholds."""
    thresholds = agent.list_thresholds()
    return ThresholdResponse(thresholds=thresholds, count=len(thresholds))


@router.delete("/thresholds/{metric_name}")
async def remove_threshold(
    metric_name: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Remove a threshold configuration."""
    if agent.remove_threshold(metric_name):
        return {"message": f"Threshold removed for {metric_name}"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Threshold not found: {metric_name}"
    )


# ============== Incident Endpoints ==============

@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List all incidents.

    Optionally filter by incident status.
    """
    status_enum = None
    if status_filter:
        try:
            status_enum = IncidentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Valid: {[s.value for s in IncidentStatus]}"
            )

    incidents = agent.list_incidents(status=status_enum)
    return IncidentListResponse(incidents=incidents, count=len(incidents))


@router.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    request: IncidentRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create a new incident.

    Incidents group related alerts and track resolution progress.
    """
    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity: {request.severity}. Valid: {[s.value for s in AlertSeverity]}"
        )

    incident = agent.create_incident(
        title=request.title,
        description=request.description,
        severity=severity,
        alert_ids=request.alert_ids,
        affected_services=request.affected_services,
    )

    return IncidentResponse(incident=incident.to_dict())


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get details of a specific incident."""
    incident = agent.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}"
        )
    return IncidentResponse(incident=incident.to_dict())


@router.put("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    request: IncidentUpdateRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Update incident status.

    Tracks status changes in the incident timeline.
    """
    try:
        status_enum = IncidentStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {request.status}. Valid: {[s.value for s in IncidentStatus]}"
        )

    incident = agent.update_incident_status(
        incident_id=incident_id,
        status=status_enum,
        message=request.message,
        user=request.user,
    )

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}"
        )

    return {"message": f"Incident status updated to {request.status}", "incident": incident.to_dict()}


@router.post("/incidents/{incident_id}/alerts/{alert_id}")
async def add_alert_to_incident(
    incident_id: str,
    alert_id: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Add an alert to an existing incident."""
    incident = agent.add_incident_alert(incident_id, alert_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}"
        )
    return {"message": f"Alert {alert_id} added to incident", "incident": incident.to_dict()}


# ============== Webhook Endpoints ==============

@router.post("/webhook", response_model=WebhookResponse)
async def configure_webhook(
    request: WebhookRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Configure an alert webhook.

    Alerts matching the configured severities will be sent to the webhook URL.
    """
    try:
        severities = [AlertSeverity(s) for s in request.severities]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity: {e}. Valid: {[s.value for s in AlertSeverity]}"
        )

    webhook = WebhookConfig(
        name=request.name,
        url=request.url,
        method=request.method,
        headers=request.headers,
        enabled=request.enabled,
        severities=severities,
        retry_count=request.retry_count,
        retry_delay_seconds=request.retry_delay_seconds,
    )

    result = agent.register_webhook(webhook)
    return WebhookResponse(webhook=result.to_dict())


@router.get("/webhooks", response_model=WebhookListResponse)
async def list_webhooks(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all configured webhooks."""
    webhooks = agent.list_webhooks()
    return WebhookListResponse(webhooks=webhooks, count=len(webhooks))


@router.delete("/webhooks/{webhook_id}")
async def remove_webhook(
    webhook_id: str,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Remove a webhook configuration."""
    if agent.remove_webhook(webhook_id):
        return {"message": f"Webhook {webhook_id} removed"}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Webhook not found: {webhook_id}"
    )


# ============== Log Analysis Endpoints ==============

@router.post("/logs/analyze", response_model=LogAnalysisResponse)
async def analyze_log_line(
    request: LogAnalysisRequest,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Analyze a log line for error patterns.

    Detects error types, tracks rates, and identifies new error patterns.
    """
    try:
        result = await agent.analyze_log(request.log_line, request.source)
        return LogAnalysisResponse(**result)
    except Exception as e:
        logger.error(f"Error analyzing log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/logs/error-rates")
async def get_error_rates(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get current error rates for all detected patterns."""
    return {"error_rates": agent.get_error_rates()}


# ============== Scheduled Checks ==============

@router.post("/scheduled/start")
async def start_scheduled_checks(
    interval_seconds: int = Query(30, description="Interval between check cycles"),
    background_tasks: BackgroundTasks = None,
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Start background scheduled health checks.

    Checks will run periodically until stopped.
    """
    await agent.start_scheduled_checks(interval_seconds=interval_seconds)
    return {"message": f"Scheduled checks started (interval: {interval_seconds}s)"}


@router.post("/scheduled/stop")
async def stop_scheduled_checks(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """Stop background scheduled health checks."""
    await agent.stop_scheduled_checks()
    return {"message": "Scheduled checks stopped"}


# ============== Status Endpoint ==============

@router.get("/status", response_model=MonitoringStatusResponse)
async def get_monitoring_status(
    agent: MonitoringAgent = Depends(get_monitoring_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get status of the monitoring agent and metrics."""
    status_info = agent.get_status()
    return MonitoringStatusResponse(**status_info)
