
from app.core.reliability import (
    AlertManager,
    ReliabilityDashboardService,
    SLICalculator,
)


def test_sli_slo_calculation_compliant() -> None:
    metrics = {
        "request_count": 100,
        "p95_latency_ms": 450.0,
        "error_counts": {},
    }

    slos = SLICalculator.calculate_slos(metrics)
    assert slos["availability_sli_percent"] == 100.0
    assert slos["slo_status"] == "COMPLIANT"
    assert slos["error_budget_remaining_percent"] == 100.0


def test_sli_slo_calculation_degraded() -> None:
    # 10 errors out of 100 requests (90% availability, degrading SLO)
    metrics = {
        "request_count": 100,
        "p95_latency_ms": 1500.0,  # Exceeds 1000ms SLA target
        "error_counts": {"llm_error": 10},
    }

    slos = SLICalculator.calculate_slos(metrics)
    assert slos["availability_sli_percent"] == 90.0
    assert slos["slo_status"] == "DEGRADED"
    assert slos["error_budget_remaining_percent"] == 0.0


def test_alert_manager_evaluation() -> None:
    metrics_high_error = {
        "request_count": 100,
        "p95_latency_ms": 2500.0,  # Exceeds 2000ms alert threshold
        "error_counts": {"retrieval_error": 10},
    }

    alerts = AlertManager.evaluate_alerts(metrics_high_error, queue_depth=25)
    alert_ids = [a["id"] for a in alerts]

    assert "ALERT_HIGH_ERROR_RATE" in alert_ids
    assert "ALERT_HIGH_LATENCY_P95" in alert_ids
    assert "ALERT_QUEUE_BACKLOG" in alert_ids


def test_reliability_dashboard_payload() -> None:
    payload = ReliabilityDashboardService.get_dashboard_payload()
    assert "timestamp" in payload
    assert "metrics" in payload
    assert "slos" in payload
    assert "active_alerts" in payload
    assert "system_status" in payload


def test_fault_isolation_safeguards() -> None:
    # Evaluating alerts with malformed metrics payload should not crash
    alerts = AlertManager.evaluate_alerts({"invalid": None}) # type: ignore
    assert isinstance(alerts, list)
