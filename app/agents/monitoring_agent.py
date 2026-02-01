"""
Monitoring and Alerting Agent

A comprehensive monitoring system that provides:
- System health monitoring (CPU, memory, disk, API latency)
- Service availability checks (HTTP endpoints, database, Redis)
- Anomaly detection using statistical methods
- Log analysis and error pattern detection
- Threshold-based alerting
- Alert routing (Slack, email, webhook)
- Alert suppression and deduplication
- Incident tracking and resolution
- Scheduled health checks
- Custom metric collection

Integrates with the existing Slack integration for alert notifications.
"""

import asyncio
import statistics
import hashlib
import re
import time
import logging
import os
import platform
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import uuid

import httpx

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


# ============== Enums ==============

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class ServiceStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    """Incident status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class CheckType(str, Enum):
    """Health check type"""
    HTTP = "http"
    TCP = "tcp"
    DATABASE = "database"
    REDIS = "redis"
    CUSTOM = "custom"


# ============== Data Classes ==============

@dataclass
class Metric:
    """A collected metric data point"""
    name: str
    value: float
    unit: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class MetricThreshold:
    """Threshold configuration for a metric"""
    metric_name: str
    warning_threshold: Optional[float] = None
    error_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    comparison: str = "gt"  # gt, lt, eq, gte, lte
    window_seconds: int = 60  # Evaluation window
    min_samples: int = 1  # Minimum samples to trigger

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "warning_threshold": self.warning_threshold,
            "error_threshold": self.error_threshold,
            "critical_threshold": self.critical_threshold,
            "comparison": self.comparison,
            "window_seconds": self.window_seconds,
            "min_samples": self.min_samples,
        }


@dataclass
class Alert:
    """An alert triggered by monitoring"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    message: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.ACTIVE
    source: str = ""
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    notification_count: int = 0
    fingerprint: str = ""  # For deduplication

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self._generate_fingerprint()

    def _generate_fingerprint(self) -> str:
        """Generate a unique fingerprint for deduplication"""
        data = f"{self.name}:{self.source}:{self.metric_name}:{':'.join(sorted(f'{k}={v}' for k, v in self.labels.items()))}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "source": self.source,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "notification_count": self.notification_count,
            "fingerprint": self.fingerprint,
        }


@dataclass
class ServiceCheck:
    """Configuration for a service health check"""
    name: str
    check_type: CheckType = CheckType.HTTP
    target: str = ""  # URL, host:port, or custom identifier
    interval_seconds: int = 30
    timeout_seconds: int = 10
    expected_status_codes: List[int] = field(default_factory=lambda: [200, 201, 204])
    expected_body_contains: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    last_check: Optional[datetime] = None
    last_status: ServiceStatus = ServiceStatus.UNKNOWN
    consecutive_failures: int = 0
    failure_threshold: int = 3  # Failures before alerting

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "check_type": self.check_type.value,
            "target": self.target,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "expected_status_codes": self.expected_status_codes,
            "expected_body_contains": self.expected_body_contains,
            "headers": self.headers,
            "enabled": self.enabled,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_status": self.last_status.value,
            "consecutive_failures": self.consecutive_failures,
            "failure_threshold": self.failure_threshold,
        }


@dataclass
class Incident:
    """An incident grouping related alerts"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: IncidentStatus = IncidentStatus.OPEN
    severity: AlertSeverity = AlertSeverity.WARNING
    alert_ids: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)  # Events in the incident
    assigned_to: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None

    def add_event(self, event_type: str, message: str, user: Optional[str] = None):
        """Add an event to the incident timeline"""
        self.timeline.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "message": message,
            "user": user,
        })
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "severity": self.severity.value,
            "alert_ids": self.alert_ids,
            "affected_services": self.affected_services,
            "timeline": self.timeline,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_summary": self.resolution_summary,
        }


@dataclass
class WebhookConfig:
    """Webhook configuration for alert routing"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    url: str = ""
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    severities: List[AlertSeverity] = field(default_factory=lambda: list(AlertSeverity))
    retry_count: int = 3
    retry_delay_seconds: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "headers": {k: v for k, v in self.headers.items() if k.lower() != "authorization"},
            "enabled": self.enabled,
            "severities": [s.value for s in self.severities],
            "retry_count": self.retry_count,
            "retry_delay_seconds": self.retry_delay_seconds,
        }


# ============== Anomaly Detection ==============

class AnomalyDetector:
    """
    Statistical anomaly detection using Z-score and IQR methods.
    Maintains a rolling window of metric values for baseline calculation.
    """

    def __init__(self, window_size: int = 100, z_threshold: float = 3.0):
        """
        Initialize the anomaly detector.

        Args:
            window_size: Number of data points to keep in the rolling window
            z_threshold: Z-score threshold for anomaly detection
        """
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._windows: Dict[str, deque] = {}  # metric_name -> values

    def add_value(self, metric_name: str, value: float) -> None:
        """Add a value to the rolling window"""
        if metric_name not in self._windows:
            self._windows[metric_name] = deque(maxlen=self.window_size)
        self._windows[metric_name].append(value)

    def is_anomaly(self, metric_name: str, value: float) -> Dict[str, Any]:
        """
        Check if a value is anomalous using Z-score.

        Returns:
            Dict with is_anomaly, z_score, mean, std_dev
        """
        if metric_name not in self._windows or len(self._windows[metric_name]) < 10:
            return {
                "is_anomaly": False,
                "reason": "Insufficient data for baseline",
                "z_score": None,
                "mean": None,
                "std_dev": None,
            }

        values = list(self._windows[metric_name])
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0

        if std_dev == 0:
            return {
                "is_anomaly": False,
                "reason": "Zero standard deviation",
                "z_score": 0,
                "mean": mean,
                "std_dev": 0,
            }

        z_score = (value - mean) / std_dev
        is_anomaly = abs(z_score) > self.z_threshold

        return {
            "is_anomaly": is_anomaly,
            "reason": f"Z-score {z_score:.2f} exceeds threshold {self.z_threshold}" if is_anomaly else None,
            "z_score": round(z_score, 2),
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2),
        }

    def detect_iqr_anomaly(self, metric_name: str, value: float) -> Dict[str, Any]:
        """
        Check if a value is anomalous using IQR method.
        More robust to outliers than Z-score.
        """
        if metric_name not in self._windows or len(self._windows[metric_name]) < 10:
            return {
                "is_anomaly": False,
                "reason": "Insufficient data for baseline",
            }

        values = sorted(self._windows[metric_name])
        n = len(values)
        q1 = values[n // 4]
        q3 = values[(3 * n) // 4]
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        is_anomaly = value < lower_bound or value > upper_bound

        return {
            "is_anomaly": is_anomaly,
            "reason": f"Value {value} outside IQR bounds [{lower_bound:.2f}, {upper_bound:.2f}]" if is_anomaly else None,
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
        }

    def get_baseline_stats(self, metric_name: str) -> Dict[str, Any]:
        """Get baseline statistics for a metric"""
        if metric_name not in self._windows or len(self._windows[metric_name]) < 2:
            return {"error": "Insufficient data"}

        values = list(self._windows[metric_name])
        return {
            "count": len(values),
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 2),
            "std_dev": round(statistics.stdev(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
        }


# ============== Log Analyzer ==============

class LogAnalyzer:
    """
    Analyzes logs for error patterns and anomalies.
    Detects recurring errors, sudden spikes, and new error types.
    """

    # Common error patterns
    ERROR_PATTERNS = [
        (re.compile(r'error', re.IGNORECASE), "error"),
        (re.compile(r'exception', re.IGNORECASE), "exception"),
        (re.compile(r'fail(ed|ure)?', re.IGNORECASE), "failure"),
        (re.compile(r'timeout', re.IGNORECASE), "timeout"),
        (re.compile(r'connection refused', re.IGNORECASE), "connection_refused"),
        (re.compile(r'out of memory', re.IGNORECASE), "oom"),
        (re.compile(r'disk full', re.IGNORECASE), "disk_full"),
        (re.compile(r'permission denied', re.IGNORECASE), "permission_denied"),
        (re.compile(r'not found', re.IGNORECASE), "not_found"),
        (re.compile(r'unauthorized', re.IGNORECASE), "unauthorized"),
    ]

    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes
        self._error_counts: Dict[str, deque] = {}  # pattern -> (timestamp, count) pairs
        self._seen_messages: deque = deque(maxlen=1000)

    def analyze_log_line(self, line: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Analyze a single log line for error patterns.

        Returns:
            Dict with detected patterns and severity
        """
        timestamp = timestamp or datetime.utcnow()
        detected_patterns = []

        for pattern, name in self.ERROR_PATTERNS:
            if pattern.search(line):
                detected_patterns.append(name)
                self._increment_pattern(name, timestamp)

        # Check if this is a new unique error
        line_hash = hashlib.sha256(line.encode()).hexdigest()[:16]
        is_new_error = line_hash not in self._seen_messages
        self._seen_messages.append(line_hash)

        severity = AlertSeverity.INFO
        if "oom" in detected_patterns or "disk_full" in detected_patterns:
            severity = AlertSeverity.CRITICAL
        elif "exception" in detected_patterns or "failure" in detected_patterns:
            severity = AlertSeverity.ERROR
        elif detected_patterns:
            severity = AlertSeverity.WARNING

        return {
            "patterns": detected_patterns,
            "severity": severity.value if detected_patterns else None,
            "is_new_error": is_new_error and bool(detected_patterns),
            "line_hash": line_hash,
        }

    def _increment_pattern(self, pattern: str, timestamp: datetime):
        """Increment the count for a pattern"""
        if pattern not in self._error_counts:
            self._error_counts[pattern] = deque(maxlen=1000)
        self._error_counts[pattern].append((timestamp, 1))

    def get_error_rate(self, pattern: str, window_minutes: Optional[int] = None) -> Dict[str, Any]:
        """Get the error rate for a pattern in the time window"""
        window = window_minutes or self.window_minutes
        cutoff = datetime.utcnow() - timedelta(minutes=window)

        if pattern not in self._error_counts:
            return {"pattern": pattern, "count": 0, "rate_per_minute": 0.0}

        count = sum(1 for ts, _ in self._error_counts[pattern] if ts > cutoff)
        rate = count / window if window > 0 else 0

        return {
            "pattern": pattern,
            "count": count,
            "rate_per_minute": round(rate, 2),
            "window_minutes": window,
        }

    def get_all_error_rates(self) -> List[Dict[str, Any]]:
        """Get error rates for all detected patterns"""
        return [self.get_error_rate(p) for p in self._error_counts.keys()]

    def detect_error_spike(self, pattern: str, spike_threshold: float = 3.0) -> Dict[str, Any]:
        """
        Detect if there's a spike in errors compared to baseline.

        Args:
            pattern: Error pattern name
            spike_threshold: Multiplier over baseline to consider a spike
        """
        if pattern not in self._error_counts:
            return {"is_spike": False, "reason": "Pattern not found"}

        cutoff_recent = datetime.utcnow() - timedelta(minutes=5)
        cutoff_baseline = datetime.utcnow() - timedelta(minutes=30)

        recent_count = sum(1 for ts, _ in self._error_counts[pattern] if ts > cutoff_recent)
        baseline_count = sum(1 for ts, _ in self._error_counts[pattern] if cutoff_baseline < ts <= cutoff_recent)

        baseline_rate = baseline_count / 25 if baseline_count > 0 else 0.1  # 25 minutes baseline
        recent_rate = recent_count / 5

        is_spike = recent_rate > baseline_rate * spike_threshold

        return {
            "is_spike": is_spike,
            "recent_rate": round(recent_rate, 2),
            "baseline_rate": round(baseline_rate, 2),
            "multiplier": round(recent_rate / baseline_rate, 2) if baseline_rate > 0 else 0,
            "threshold": spike_threshold,
        }


# ============== MonitoringAgent ==============

class MonitoringAgent(BaseAgent):
    """
    Comprehensive Monitoring and Alerting Agent.

    Features:
    - System health monitoring (CPU, memory, disk, network)
    - Service availability checks (HTTP, TCP, database, Redis)
    - Anomaly detection using Z-score and IQR methods
    - Log analysis and error pattern detection
    - Threshold-based alerting with multiple severity levels
    - Alert routing to Slack, email, and webhooks
    - Alert suppression and deduplication
    - Incident management and tracking
    - Scheduled background health checks
    - Custom metric collection and querying
    """

    # Default alert suppression window (seconds)
    DEFAULT_SUPPRESSION_WINDOW = 300  # 5 minutes

    def __init__(
        self,
        memory_manager=None,
        slack_client=None,
        email_sender=None,
    ):
        super().__init__("MonitoringAgent", memory_manager)
        self.slack_client = slack_client
        self.email_sender = email_sender

        # Storage
        self._metrics: Dict[str, deque] = {}  # metric_name -> deque of Metric objects
        self._thresholds: Dict[str, MetricThreshold] = {}
        self._alerts: Dict[str, Alert] = {}  # alert_id -> Alert
        self._service_checks: Dict[str, ServiceCheck] = {}
        self._incidents: Dict[str, Incident] = {}
        self._webhooks: Dict[str, WebhookConfig] = {}

        # Alert deduplication: fingerprint -> last_alert_time
        self._alert_fingerprints: Dict[str, datetime] = {}

        # Components
        self.anomaly_detector = AnomalyDetector()
        self.log_analyzer = LogAnalyzer()

        # Background task control
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

        # HTTP client for service checks and webhooks
        self._http_client: Optional[httpx.AsyncClient] = None

        # Set up default thresholds
        self._setup_default_thresholds()

        logger.info("MonitoringAgent initialized")

    def _setup_default_thresholds(self):
        """Set up default metric thresholds"""
        default_thresholds = [
            MetricThreshold(
                metric_name="system.cpu.percent",
                warning_threshold=70,
                error_threshold=85,
                critical_threshold=95,
                comparison="gt",
            ),
            MetricThreshold(
                metric_name="system.memory.percent",
                warning_threshold=75,
                error_threshold=85,
                critical_threshold=95,
                comparison="gt",
            ),
            MetricThreshold(
                metric_name="system.disk.percent",
                warning_threshold=80,
                error_threshold=90,
                critical_threshold=95,
                comparison="gt",
            ),
            MetricThreshold(
                metric_name="api.latency.p99",
                warning_threshold=1000,  # ms
                error_threshold=3000,
                critical_threshold=5000,
                comparison="gt",
            ),
        ]

        for threshold in default_thresholds:
            self._thresholds[threshold.metric_name] = threshold

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        """Clean up resources"""
        await self.stop_scheduled_checks()
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # ============== BaseAgent Methods ==============

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a monitoring task"""
        logger.info(f"MonitoringAgent executing task: {task.get('task_id')}")

        try:
            action = task.get("action", "health_check")

            if action == "health_check":
                result = await self.get_system_health()
            elif action == "check_services":
                result = await self.check_all_services()
            elif action == "get_alerts":
                result = self.get_active_alerts()
            elif action == "get_metrics":
                metric_name = task.get("metric_name")
                result = self.get_metrics(metric_name)
            else:
                result = {"error": f"Unknown action: {action}"}

            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": result,
            }

        except Exception as e:
            logger.error(f"MonitoringAgent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        active_alerts = len([a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE])
        open_incidents = len([i for i in self._incidents.values() if i.status not in [IncidentStatus.RESOLVED]])

        return {
            "name": self.name,
            "status": "ready",
            "memory_enabled": self.memory_manager is not None,
            "slack_enabled": self.slack_client is not None,
            "scheduled_checks_running": self._running,
            "metrics": {
                "total_metrics": len(self._metrics),
                "active_alerts": active_alerts,
                "open_incidents": open_incidents,
                "service_checks": len(self._service_checks),
                "thresholds_configured": len(self._thresholds),
                "webhooks_configured": len(self._webhooks),
            },
        }

    # ============== System Health ==============

    async def get_system_health(self) -> Dict[str, Any]:
        """
        Collect system health metrics: CPU, memory, disk, network.

        Returns:
            Dict with current system metrics and overall health status
        """
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": platform.system(),
            "hostname": platform.node(),
            "status": ServiceStatus.HEALTHY.value,
            "metrics": {},
            "alerts": [],
        }

        if not PSUTIL_AVAILABLE:
            health_data["status"] = ServiceStatus.UNKNOWN.value
            health_data["error"] = "psutil not available"
            return health_data

        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            health_data["metrics"]["cpu"] = {
                "percent": cpu_percent,
                "count": psutil.cpu_count(),
                "load_avg": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None,
            }
            await self.record_metric("system.cpu.percent", cpu_percent, "%")

            # Memory
            memory = psutil.virtual_memory()
            health_data["metrics"]["memory"] = {
                "percent": memory.percent,
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
            }
            await self.record_metric("system.memory.percent", memory.percent, "%")

            # Disk
            disk = psutil.disk_usage("/")
            health_data["metrics"]["disk"] = {
                "percent": disk.percent,
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
            }
            await self.record_metric("system.disk.percent", disk.percent, "%")

            # Network (if available)
            try:
                net_io = psutil.net_io_counters()
                health_data["metrics"]["network"] = {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "errors_in": net_io.errin,
                    "errors_out": net_io.errout,
                }
            except Exception:
                pass

            # Determine overall status based on metrics
            worst_status = ServiceStatus.HEALTHY
            for metric_name, value in [
                ("system.cpu.percent", cpu_percent),
                ("system.memory.percent", memory.percent),
                ("system.disk.percent", disk.percent),
            ]:
                threshold = self._thresholds.get(metric_name)
                if threshold:
                    if threshold.critical_threshold and value >= threshold.critical_threshold:
                        worst_status = ServiceStatus.UNHEALTHY
                        health_data["alerts"].append({
                            "metric": metric_name,
                            "severity": "critical",
                            "value": value,
                            "threshold": threshold.critical_threshold,
                        })
                    elif threshold.error_threshold and value >= threshold.error_threshold:
                        if worst_status != ServiceStatus.UNHEALTHY:
                            worst_status = ServiceStatus.DEGRADED
                        health_data["alerts"].append({
                            "metric": metric_name,
                            "severity": "error",
                            "value": value,
                            "threshold": threshold.error_threshold,
                        })

            health_data["status"] = worst_status.value

        except Exception as e:
            logger.error(f"Error collecting system health: {e}")
            health_data["status"] = ServiceStatus.UNKNOWN.value
            health_data["error"] = str(e)

        return health_data

    # ============== Service Checks ==============

    def register_service_check(self, check: ServiceCheck) -> ServiceCheck:
        """Register a new service health check"""
        self._service_checks[check.name] = check
        logger.info(f"Registered service check: {check.name} ({check.check_type.value})")
        return check

    def get_service_check(self, name: str) -> Optional[ServiceCheck]:
        """Get a service check by name"""
        return self._service_checks.get(name)

    def list_service_checks(self) -> List[Dict[str, Any]]:
        """List all registered service checks"""
        return [check.to_dict() for check in self._service_checks.values()]

    def remove_service_check(self, name: str) -> bool:
        """Remove a service check"""
        if name in self._service_checks:
            del self._service_checks[name]
            return True
        return False

    async def check_service(self, name: str) -> Dict[str, Any]:
        """
        Execute a single service check.

        Returns:
            Dict with check result, latency, and any errors
        """
        check = self._service_checks.get(name)
        if not check:
            return {"error": f"Service check not found: {name}"}

        if not check.enabled:
            return {"status": "disabled", "name": name}

        start_time = time.time()
        result = {
            "name": name,
            "check_type": check.check_type.value,
            "target": check.target,
            "timestamp": datetime.utcnow().isoformat(),
            "status": ServiceStatus.UNKNOWN.value,
            "latency_ms": 0,
            "error": None,
        }

        try:
            if check.check_type == CheckType.HTTP:
                result = await self._check_http(check, result, start_time)
            elif check.check_type == CheckType.TCP:
                result = await self._check_tcp(check, result, start_time)
            elif check.check_type == CheckType.DATABASE:
                result = await self._check_database(check, result, start_time)
            elif check.check_type == CheckType.REDIS:
                result = await self._check_redis(check, result, start_time)
            else:
                result["error"] = f"Unsupported check type: {check.check_type}"

        except Exception as e:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = str(e)
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        # Update check state
        check.last_check = datetime.utcnow()
        old_status = check.last_status

        if result["status"] == ServiceStatus.HEALTHY.value:
            check.last_status = ServiceStatus.HEALTHY
            check.consecutive_failures = 0
        else:
            check.consecutive_failures += 1
            if check.consecutive_failures >= check.failure_threshold:
                check.last_status = ServiceStatus.UNHEALTHY
                # Generate alert
                if old_status != ServiceStatus.UNHEALTHY:
                    await self._create_service_alert(check, result)
            else:
                check.last_status = ServiceStatus.DEGRADED

        # Record latency metric
        await self.record_metric(
            f"service.{name}.latency",
            result["latency_ms"],
            "ms",
            {"service": name, "check_type": check.check_type.value}
        )

        return result

    async def _check_http(self, check: ServiceCheck, result: Dict, start_time: float) -> Dict[str, Any]:
        """Perform HTTP health check"""
        client = await self._get_http_client()

        try:
            response = await client.get(
                check.target,
                headers=check.headers,
                timeout=check.timeout_seconds,
            )

            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)
            result["status_code"] = response.status_code

            if response.status_code in check.expected_status_codes:
                if check.expected_body_contains:
                    body = response.text
                    if check.expected_body_contains in body:
                        result["status"] = ServiceStatus.HEALTHY.value
                    else:
                        result["status"] = ServiceStatus.UNHEALTHY.value
                        result["error"] = "Expected body content not found"
                else:
                    result["status"] = ServiceStatus.HEALTHY.value
            else:
                result["status"] = ServiceStatus.UNHEALTHY.value
                result["error"] = f"Unexpected status code: {response.status_code}"

        except httpx.TimeoutException:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = "Request timed out"
            result["latency_ms"] = check.timeout_seconds * 1000

        return result

    async def _check_tcp(self, check: ServiceCheck, result: Dict, start_time: float) -> Dict[str, Any]:
        """Perform TCP connectivity check"""
        try:
            host, port = check.target.rsplit(":", 1)
            port = int(port)

            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=check.timeout_seconds
            )
            writer.close()
            await writer.wait_closed()

            result["status"] = ServiceStatus.HEALTHY.value
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        except asyncio.TimeoutError:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = "Connection timed out"
            result["latency_ms"] = check.timeout_seconds * 1000
        except Exception as e:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = str(e)
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        return result

    async def _check_database(self, check: ServiceCheck, result: Dict, start_time: float) -> Dict[str, Any]:
        """Perform database connectivity check (PostgreSQL)"""
        try:
            # Import here to avoid dependency issues
            from app.db.database import engine

            async with engine.connect() as conn:
                await conn.execute("SELECT 1")

            result["status"] = ServiceStatus.HEALTHY.value
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = str(e)
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        return result

    async def _check_redis(self, check: ServiceCheck, result: Dict, start_time: float) -> Dict[str, Any]:
        """Perform Redis connectivity check"""
        try:
            import redis.asyncio as redis

            host, port = check.target.rsplit(":", 1)
            client = redis.Redis(host=host, port=int(port), decode_responses=True)
            await client.ping()
            await client.close()

            result["status"] = ServiceStatus.HEALTHY.value
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result["status"] = ServiceStatus.UNHEALTHY.value
            result["error"] = str(e)
            result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        return result

    async def check_all_services(self) -> Dict[str, Any]:
        """Check all registered services concurrently"""
        if not self._service_checks:
            return {"services": [], "summary": {"healthy": 0, "unhealthy": 0, "degraded": 0}}

        tasks = [self.check_service(name) for name in self._service_checks.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        services = []
        summary = {"healthy": 0, "unhealthy": 0, "degraded": 0, "unknown": 0}

        for result in results:
            if isinstance(result, Exception):
                services.append({"error": str(result), "status": ServiceStatus.UNKNOWN.value})
                summary["unknown"] += 1
            else:
                services.append(result)
                status = result.get("status", "unknown")
                if status in summary:
                    summary[status] += 1

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": services,
            "summary": summary,
        }

    async def _create_service_alert(self, check: ServiceCheck, result: Dict):
        """Create an alert for a failed service check"""
        alert = Alert(
            name=f"Service Unhealthy: {check.name}",
            message=f"Service {check.name} is unhealthy after {check.consecutive_failures} consecutive failures. Error: {result.get('error', 'Unknown')}",
            severity=AlertSeverity.ERROR,
            source="service_check",
            labels={"service": check.name, "check_type": check.check_type.value},
        )
        await self.create_alert(alert)

    # ============== Metrics ==============

    async def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, str]] = None
    ) -> Metric:
        """
        Record a metric value.

        Args:
            name: Metric name (e.g., "system.cpu.percent")
            value: Metric value
            unit: Unit of measurement
            labels: Additional labels/dimensions

        Returns:
            The recorded Metric object
        """
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            labels=labels or {},
        )

        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=1000)

        self._metrics[name].append(metric)

        # Add to anomaly detector baseline
        self.anomaly_detector.add_value(name, value)

        # Check threshold
        await self._check_threshold(metric)

        return metric

    def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get recorded metrics.

        Args:
            name: Filter by metric name
            since: Filter by timestamp
            limit: Maximum metrics to return per name

        Returns:
            Dict with metric data
        """
        if name:
            if name not in self._metrics:
                return {"metrics": [], "count": 0}

            metrics = list(self._metrics[name])
            if since:
                metrics = [m for m in metrics if m.timestamp > since]

            return {
                "name": name,
                "metrics": [m.to_dict() for m in metrics[-limit:]],
                "count": len(metrics),
                "baseline": self.anomaly_detector.get_baseline_stats(name),
            }

        # Return summary of all metrics
        result = {"metrics": {}, "count": 0}
        for metric_name, values in self._metrics.items():
            if values:
                latest = values[-1]
                result["metrics"][metric_name] = {
                    "latest_value": latest.value,
                    "latest_timestamp": latest.timestamp.isoformat(),
                    "unit": latest.unit,
                    "count": len(values),
                }
                result["count"] += len(values)

        return result

    async def _check_threshold(self, metric: Metric):
        """Check if a metric exceeds configured thresholds"""
        threshold = self._thresholds.get(metric.name)
        if not threshold:
            return

        value = metric.value
        comparison = threshold.comparison

        severity = None
        threshold_value = None

        # Check thresholds from most severe to least
        if threshold.critical_threshold is not None:
            if self._compare(value, threshold.critical_threshold, comparison):
                severity = AlertSeverity.CRITICAL
                threshold_value = threshold.critical_threshold

        if severity is None and threshold.error_threshold is not None:
            if self._compare(value, threshold.error_threshold, comparison):
                severity = AlertSeverity.ERROR
                threshold_value = threshold.error_threshold

        if severity is None and threshold.warning_threshold is not None:
            if self._compare(value, threshold.warning_threshold, comparison):
                severity = AlertSeverity.WARNING
                threshold_value = threshold.warning_threshold

        if severity:
            alert = Alert(
                name=f"Threshold Exceeded: {metric.name}",
                message=f"Metric {metric.name} is {value}{metric.unit} (threshold: {threshold_value}{metric.unit})",
                severity=severity,
                source="threshold",
                metric_name=metric.name,
                metric_value=value,
                threshold_value=threshold_value,
                labels=metric.labels,
            )
            await self.create_alert(alert)

    def _compare(self, value: float, threshold: float, comparison: str) -> bool:
        """Compare value against threshold"""
        if comparison == "gt":
            return value > threshold
        elif comparison == "gte":
            return value >= threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "lte":
            return value <= threshold
        elif comparison == "eq":
            return value == threshold
        return False

    # ============== Thresholds ==============

    def set_threshold(self, threshold: MetricThreshold) -> MetricThreshold:
        """Set or update a metric threshold"""
        self._thresholds[threshold.metric_name] = threshold
        logger.info(f"Threshold set for {threshold.metric_name}")
        return threshold

    def get_threshold(self, metric_name: str) -> Optional[MetricThreshold]:
        """Get threshold for a metric"""
        return self._thresholds.get(metric_name)

    def list_thresholds(self) -> List[Dict[str, Any]]:
        """List all configured thresholds"""
        return [t.to_dict() for t in self._thresholds.values()]

    def remove_threshold(self, metric_name: str) -> bool:
        """Remove a threshold"""
        if metric_name in self._thresholds:
            del self._thresholds[metric_name]
            return True
        return False

    # ============== Alerting ==============

    async def create_alert(self, alert: Alert) -> Alert:
        """
        Create a new alert with deduplication.

        Alerts with the same fingerprint within the suppression window
        will be deduplicated.
        """
        # Check for deduplication
        if alert.fingerprint in self._alert_fingerprints:
            last_time = self._alert_fingerprints[alert.fingerprint]
            if datetime.utcnow() - last_time < timedelta(seconds=self.DEFAULT_SUPPRESSION_WINDOW):
                logger.debug(f"Alert suppressed (deduplicated): {alert.name}")
                # Update existing alert count
                for existing in self._alerts.values():
                    if existing.fingerprint == alert.fingerprint and existing.status == AlertStatus.ACTIVE:
                        existing.notification_count += 1
                        existing.updated_at = datetime.utcnow()
                        return existing
                return alert

        # Store alert
        self._alerts[alert.id] = alert
        self._alert_fingerprints[alert.fingerprint] = datetime.utcnow()

        logger.info(f"Alert created: {alert.name} ({alert.severity.value})")

        # Route notifications
        await self._route_alert(alert)

        return alert

    async def _route_alert(self, alert: Alert):
        """Route alert to configured channels"""
        # Slack notification
        if self.slack_client:
            try:
                await self._send_slack_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send Slack alert: {e}")

        # Webhook notifications
        for webhook in self._webhooks.values():
            if webhook.enabled and alert.severity in webhook.severities:
                try:
                    await self._send_webhook_alert(webhook, alert)
                except Exception as e:
                    logger.error(f"Failed to send webhook alert to {webhook.name}: {e}")

        alert.notification_count += 1

    async def _send_slack_alert(self, alert: Alert):
        """Send alert notification to Slack"""
        if not self.slack_client:
            return

        # Color based on severity
        color = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.ERROR: "#ff6600",
            AlertSeverity.CRITICAL: "#ff0000",
        }.get(alert.severity, "#808080")

        emoji = {
            AlertSeverity.INFO: ":information_source:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.ERROR: ":x:",
            AlertSeverity.CRITICAL: ":rotating_light:",
        }.get(alert.severity, ":bell:")

        channel = os.getenv("SLACK_ALERTS_CHANNEL", "#alerts")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert.severity.value.upper()}: {alert.name}",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": alert.message,
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Source:* {alert.source} | *ID:* `{alert.id[:8]}` | *Time:* {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]

        if alert.metric_value is not None:
            blocks.insert(2, {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Metric:* {alert.metric_name}"},
                    {"type": "mrkdwn", "text": f"*Value:* {alert.metric_value}"},
                    {"type": "mrkdwn", "text": f"*Threshold:* {alert.threshold_value}"},
                ]
            })

        await self.slack_client.send_message(
            channel=channel,
            text=f"{alert.severity.value.upper()}: {alert.name}",
            blocks=blocks,
        )

    async def _send_webhook_alert(self, webhook: WebhookConfig, alert: Alert):
        """Send alert to webhook endpoint"""
        client = await self._get_http_client()

        payload = {
            "alert": alert.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "unicorn-brigade-monitoring",
        }

        for attempt in range(webhook.retry_count):
            try:
                response = await client.request(
                    method=webhook.method,
                    url=webhook.url,
                    json=payload,
                    headers=webhook.headers,
                    timeout=10.0,
                )

                if response.status_code < 400:
                    logger.info(f"Webhook alert sent to {webhook.name}")
                    return

            except Exception as e:
                logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")

            if attempt < webhook.retry_count - 1:
                await asyncio.sleep(webhook.retry_delay_seconds)

        logger.error(f"Failed to send webhook alert to {webhook.name} after {webhook.retry_count} attempts")

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        alerts = [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return [a.to_dict() for a in alerts]

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID"""
        return self._alerts.get(alert_id)

    def acknowledge_alert(self, alert_id: str, user: str) -> Optional[Alert]:
        """Acknowledge an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user
        alert.updated_at = datetime.utcnow()

        logger.info(f"Alert {alert_id} acknowledged by {user}")
        return alert

    def resolve_alert(self, alert_id: str, user: str) -> Optional[Alert]:
        """Resolve an alert"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user
        alert.updated_at = datetime.utcnow()

        logger.info(f"Alert {alert_id} resolved by {user}")
        return alert

    # ============== Incidents ==============

    def create_incident(
        self,
        title: str,
        description: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        alert_ids: Optional[List[str]] = None,
        affected_services: Optional[List[str]] = None,
    ) -> Incident:
        """Create a new incident"""
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            alert_ids=alert_ids or [],
            affected_services=affected_services or [],
        )

        incident.add_event("created", f"Incident created: {title}")
        self._incidents[incident.id] = incident

        logger.info(f"Incident created: {incident.id} - {title}")
        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID"""
        return self._incidents.get(incident_id)

    def list_incidents(self, status: Optional[IncidentStatus] = None) -> List[Dict[str, Any]]:
        """List all incidents"""
        incidents = list(self._incidents.values())

        if status:
            incidents = [i for i in incidents if i.status == status]

        incidents.sort(key=lambda i: i.created_at, reverse=True)
        return [i.to_dict() for i in incidents]

    def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        message: str,
        user: Optional[str] = None
    ) -> Optional[Incident]:
        """Update incident status"""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        old_status = incident.status
        incident.status = status
        incident.updated_at = datetime.utcnow()
        incident.add_event("status_change", f"Status changed from {old_status.value} to {status.value}: {message}", user)

        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.utcnow()
            incident.resolution_summary = message

        logger.info(f"Incident {incident_id} status updated to {status.value}")
        return incident

    def add_incident_alert(self, incident_id: str, alert_id: str) -> Optional[Incident]:
        """Add an alert to an incident"""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        if alert_id not in incident.alert_ids:
            incident.alert_ids.append(alert_id)
            incident.add_event("alert_added", f"Alert {alert_id} added to incident")

        return incident

    # ============== Webhooks ==============

    def register_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        """Register a new webhook"""
        self._webhooks[webhook.id] = webhook
        logger.info(f"Webhook registered: {webhook.name}")
        return webhook

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get a webhook by ID"""
        return self._webhooks.get(webhook_id)

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all webhooks"""
        return [w.to_dict() for w in self._webhooks.values()]

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook"""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            return True
        return False

    # ============== Anomaly Detection ==============

    async def check_anomaly(self, metric_name: str, value: float) -> Dict[str, Any]:
        """
        Check if a value is anomalous for a metric.

        Uses both Z-score and IQR methods.

        Args:
            metric_name: Name of the metric
            value: Value to check

        Returns:
            Dict with anomaly detection results
        """
        z_result = self.anomaly_detector.is_anomaly(metric_name, value)
        iqr_result = self.anomaly_detector.detect_iqr_anomaly(metric_name, value)

        is_anomaly = z_result["is_anomaly"] or iqr_result["is_anomaly"]

        if is_anomaly:
            # Create an alert for the anomaly
            alert = Alert(
                name=f"Anomaly Detected: {metric_name}",
                message=f"Anomalous value {value} detected for {metric_name}. Z-score: {z_result.get('z_score')}, IQR: {iqr_result.get('is_anomaly')}",
                severity=AlertSeverity.WARNING,
                source="anomaly_detection",
                metric_name=metric_name,
                metric_value=value,
            )
            await self.create_alert(alert)

        return {
            "metric_name": metric_name,
            "value": value,
            "is_anomaly": is_anomaly,
            "z_score_analysis": z_result,
            "iqr_analysis": iqr_result,
            "baseline": self.anomaly_detector.get_baseline_stats(metric_name),
        }

    # ============== Log Analysis ==============

    async def analyze_log(self, log_line: str, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a log line for error patterns.

        Args:
            log_line: The log line to analyze
            source: Source of the log (e.g., "api", "worker")

        Returns:
            Dict with analysis results
        """
        result = self.log_analyzer.analyze_log_line(log_line)

        if result["patterns"] and result["is_new_error"]:
            # Create alert for new error type
            alert = Alert(
                name="New Error Pattern Detected",
                message=f"New error pattern in logs: {result['patterns']}. Log: {log_line[:200]}",
                severity=AlertSeverity(result["severity"]) if result["severity"] else AlertSeverity.WARNING,
                source=f"log_analysis:{source}" if source else "log_analysis",
                labels={"patterns": ",".join(result["patterns"])},
            )
            await self.create_alert(alert)

        # Check for error spikes
        for pattern in result["patterns"]:
            spike = self.log_analyzer.detect_error_spike(pattern)
            if spike["is_spike"]:
                alert = Alert(
                    name=f"Error Spike: {pattern}",
                    message=f"Error rate spike detected for '{pattern}': {spike['multiplier']}x baseline",
                    severity=AlertSeverity.ERROR,
                    source="log_analysis",
                    labels={"pattern": pattern},
                )
                await self.create_alert(alert)

        result["source"] = source
        result["error_rates"] = self.log_analyzer.get_all_error_rates()

        return result

    def get_error_rates(self) -> List[Dict[str, Any]]:
        """Get current error rates for all detected patterns"""
        return self.log_analyzer.get_all_error_rates()

    # ============== Scheduled Checks ==============

    async def start_scheduled_checks(self, interval_seconds: int = 30):
        """
        Start background scheduled health checks.

        Args:
            interval_seconds: Interval between check cycles
        """
        if self._running:
            logger.warning("Scheduled checks already running")
            return

        self._running = True
        self._check_task = asyncio.create_task(self._scheduled_check_loop(interval_seconds))
        logger.info(f"Started scheduled checks (interval: {interval_seconds}s)")

    async def stop_scheduled_checks(self):
        """Stop background scheduled checks"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
        logger.info("Stopped scheduled checks")

    async def _scheduled_check_loop(self, interval_seconds: int):
        """Background loop for scheduled checks"""
        while self._running:
            try:
                # Collect system health
                await self.get_system_health()

                # Check all services
                for name, check in self._service_checks.items():
                    if check.enabled:
                        # Only check if enough time has passed
                        if check.last_check is None or \
                           (datetime.utcnow() - check.last_check).seconds >= check.interval_seconds:
                            await self.check_service(name)

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduled check loop: {e}")
                await asyncio.sleep(interval_seconds)

    # ============== Trigger Health Check ==============

    async def trigger_health_check(self, services: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Trigger an immediate health check.

        Args:
            services: Optional list of specific services to check

        Returns:
            Dict with health check results
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": await self.get_system_health(),
            "services": [],
        }

        if services:
            for service_name in services:
                result = await self.check_service(service_name)
                results["services"].append(result)
        else:
            all_services = await self.check_all_services()
            results["services"] = all_services.get("services", [])
            results["service_summary"] = all_services.get("summary", {})

        return results
