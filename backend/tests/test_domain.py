from app.domain.models import Telemetry, Threshold, Severity, evaluate_thresholds

def test_threshold_decisions_warning_critical_and_normal():
    thresholds = [Threshold("temperature", 50, 70)]
    assert evaluate_thresholds(Telemetry(temperature=45, humidity=40, vibration_rate=0, vibration_edges=0, current_rms=0), thresholds)[0][1].severity is None
    assert evaluate_thresholds(Telemetry(temperature=60, humidity=40, vibration_rate=0, vibration_edges=0, current_rms=0), thresholds)[0][1].severity == Severity.WARNING
    assert evaluate_thresholds(Telemetry(temperature=75, humidity=40, vibration_rate=0, vibration_edges=0, current_rms=0), thresholds)[0][1].severity == Severity.CRITICAL
