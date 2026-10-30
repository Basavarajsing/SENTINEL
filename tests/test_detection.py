from config import MAX_EVENTS, MAX_SIMULATION_SECONDS
from detector import TrafficDetector
from mitigation import MitigationEngine, TokenBucket, TemporaryBlockList
from simulator import TrafficSimulator


def event(source: str, timestamp: float, legitimate: bool = True) -> dict:
    return {"source_id": source, "timestamp": timestamp, "legitimate": legitimate}


def test_normal_traffic_is_not_suspicious():
    detector = TrafficDetector(source_threshold=4, global_threshold=20)
    result = detector.inspect(event("user-1", 0.0))
    assert result.suspicious is False


def test_source_threshold_detection_explains_reason():
    detector = TrafficDetector(source_threshold=3, global_threshold=20)
    detector.inspect(event("synthetic-bot-1", 0.0, False))
    detector.inspect(event("synthetic-bot-1", 0.5, False))
    result = detector.inspect(event("synthetic-bot-1", 1.0, False))
    assert result.suspicious is True
    assert "source rate" in result.reason


def test_token_bucket_rate_limits():
    bucket = TokenBucket(capacity=2, refill_per_second=0)
    assert bucket.allow(0) is True
    assert bucket.allow(0) is True
    assert bucket.allow(0) is False


def test_temporary_block_expires():
    block_list = TemporaryBlockList(duration_seconds=2)
    block_list.block("bot", 10)
    assert block_list.is_blocked("bot", 11) is True
    assert block_list.is_blocked("bot", 12.1) is False


def test_mitigation_blocks_suspicious_source():
    detector = TrafficDetector(source_threshold=1)
    mitigation = MitigationEngine()
    result = detector.inspect(event("bot", 0, False))
    decision = mitigation.apply(result)
    assert result.suspicious is True
    assert decision.allowed is False


def test_simulator_respects_hard_limits_and_reset():
    simulator = TrafficSimulator()
    simulator.start("excessive")
    simulator._process_events(MAX_EVENTS + 50, 1)
    assert simulator.state.total == MAX_EVENTS
    assert simulator.state.elapsed <= MAX_SIMULATION_SECONDS
    simulator.reset()
    assert simulator.state.total == 0
    assert simulator.state.elapsed == 0
    assert simulator.state.history == []


def test_flask_starts_with_loopback_configuration():
    from app import app

    assert app.test_client().get("/").status_code == 200


def test_health_endpoint_and_security_headers():
    from app import app

    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
