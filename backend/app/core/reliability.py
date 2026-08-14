import logging
import os
import shutil
import time
from typing import Any

from app.core.config import get_settings
from app.core.observability import default_metrics_collector

logger = logging.getLogger("ai_research_assistant.reliability")


class AlertManager:
    """Evaluates system telemetry and triggers operational alerts based on configurable thresholds."""

    @staticmethod
    def evaluate_alerts(metrics_summary: dict[str, Any], queue_depth: int = 0) -> list[dict[str, Any]]:
        """Evaluate operational health metrics and return active alert items."""
        alerts = []
        req_count = metrics_summary.get("request_count", 0)
        p95_lat = metrics_summary.get("p95_latency_ms", 0.0)
        errors = metrics_summary.get("error_counts", {})
        total_errors = sum(errors.values())

        # 1. High Error Rate Alert
        if req_count > 10:
            error_rate = (total_errors / req_count) * 100
            if error_rate > 5.0:
                alerts.append({
                    "id": "ALERT_HIGH_ERROR_RATE",
                    "severity": "CRITICAL",
                    "title": "High API Error Rate Detected",
                    "message": f"API error rate is {round(error_rate, 2)}% exceeding 5% threshold.",
                    "timestamp": time.time(),
                })

        # 2. High Latency Alert
        if p95_lat > 2000.0:
            alerts.append({
                "id": "ALERT_HIGH_LATENCY_P95",
                "severity": "WARNING",
                "title": "High P95 Response Latency",
                "message": f"P95 latency is {p95_lat}ms exceeding 2000ms SLA target.",
                "timestamp": time.time(),
            })

        # 3. Queue Backlog Alert
        if queue_depth > 20:
            alerts.append({
                "id": "ALERT_QUEUE_BACKLOG",
                "severity": "WARNING",
                "title": "Background Worker Queue Backlog",
                "message": f"Queue depth is {queue_depth} jobs exceeding max threshold of 20.",
                "timestamp": time.time(),
            })

        # 4. Storage Space Alert
        try:
            settings = get_settings()
            storage_path = settings.STORAGE_PATH
            if os.path.exists(storage_path):
                total, used, free = shutil.disk_usage(storage_path)
                free_pct = (free / total) * 100
                if free_pct < 10.0:
                    alerts.append({
                        "id": "ALERT_STORAGE_LOW",
                        "severity": "CRITICAL",
                        "title": "Low Storage Space Remaining",
                        "message": f"Free storage is down to {round(free_pct, 1)}%.",
                        "timestamp": time.time(),
                    })
        except Exception as e:
            logger.warning(f"Disk storage check failed: {e}")

        return alerts


class SLICalculator:
    """Calculates Service Level Indicators (SLIs) and Service Level Objectives (SLOs)."""

    @staticmethod
    def calculate_slos(metrics_summary: dict[str, Any]) -> dict[str, Any]:
        """Compute system availability SLO, latency compliance, and remaining error budget."""
        req_count = metrics_summary.get("request_count", 0)
        errors = metrics_summary.get("error_counts", {})
        total_errors = sum(errors.values())

        if req_count == 0:
            return {
                "availability_sli_percent": 100.0,
                "availability_slo_target_percent": 99.5,
                "latency_p95_ms": 0.0,
                "latency_slo_target_ms": 1000.0,
                "error_budget_remaining_percent": 100.0,
                "slo_status": "COMPLIANT",
            }

        successful_requests = max(0, req_count - total_errors)
        availability_pct = round((successful_requests / req_count) * 100, 2)
        p95_lat = metrics_summary.get("p95_latency_ms", 0.0)

        # Target SLO: 99.5% availability, P95 < 1000ms
        availability_slo = 99.5
        latency_slo = 1000.0

        # Calculate remaining error budget (0.5% allowed error margin)
        allowed_error_pct = 100.0 - availability_slo
        actual_error_pct = 100.0 - availability_pct
        error_budget_remaining = max(0.0, round(((allowed_error_pct - actual_error_pct) / allowed_error_pct) * 100, 2))

        is_compliant = availability_pct >= availability_slo and p95_lat <= latency_slo

        return {
            "availability_sli_percent": availability_pct,
            "availability_slo_target_percent": availability_slo,
            "latency_p95_ms": p95_lat,
            "latency_slo_target_ms": latency_slo,
            "error_budget_remaining_percent": error_budget_remaining,
            "slo_status": "COMPLIANT" if is_compliant else "DEGRADED",
        }


class ReliabilityDashboardService:
    """Assembles live operational telemetry into executive reliability dashboard data."""

    @classmethod
    def get_dashboard_payload(cls) -> dict[str, Any]:
        """Assemble metrics, alerts, SLIs/SLOs, and component health for dashboard display."""
        metrics_summary = default_metrics_collector.get_summary()
        alerts = AlertManager.evaluate_alerts(metrics_summary)
        slos = SLICalculator.calculate_slos(metrics_summary)

        return {
            "timestamp": time.time(),
            "metrics": metrics_summary,
            "slos": slos,
            "active_alerts": alerts,
            "alert_count": len(alerts),
            "system_status": "HEALTHY" if not any(a["severity"] == "CRITICAL" for a in alerts) else "DEGRADED",
        }
