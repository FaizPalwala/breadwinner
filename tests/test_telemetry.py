"""Unit tests for AI Telemetry and Cost Tracking module."""

import json
from pathlib import Path
import pytest
from breadwinner.providers.telemetry import (
    AITelemetryTracker,
    estimate_call_cost,
    get_telemetry_tracker,
    PRICING_CATALOG,
)


def test_estimate_call_cost():
    # Gemini Flash: 1,000,000 prompt = $0.10, 1,000,000 completion = $0.40
    cost = estimate_call_cost("gemini-2.0-flash", 1000, 500)
    # prompt: (1000/1e6)*0.10 = 0.0001
    # comp: (500/1e6)*0.40 = 0.0002
    assert cost == pytest.approx(0.0003, rel=1e-3)

    # Local Ollama or unknown local model is free
    cost_local = estimate_call_cost("ollama/llama3", 5000, 2000)
    assert cost_local == 0.0

    # Claude 3.5 Sonnet: $3.00/1M prompt, $15.00/1M completion
    cost_claude = estimate_call_cost("claude-3-5-sonnet", 2000, 1000)
    # (2000/1e6)*3.00 = 0.006
    # (1000/1e6)*15.00 = 0.015
    assert cost_claude == pytest.approx(0.021, rel=1e-3)


def test_telemetry_tracker_records_and_persists(tmp_path):
    log_file = tmp_path / "test_ai_calls.jsonl"
    tracker = AITelemetryTracker(log_path=log_file)

    rec1 = tracker.record_call(
        provider="gemini",
        model="gemini-2.0-flash",
        duration_ms=450.5,
        prompt_tokens=1200,
        completion_tokens=400,
        status="success",
        status_code=200,
    )
    assert rec1.status == "success"
    assert rec1.total_tokens == 1600
    assert rec1.estimated_cost_usd > 0

    rec2 = tracker.record_call(
        provider="gemini",
        model="gemini-2.0-flash",
        duration_ms=120.0,
        status="error",
        status_code=500,
        error_message="500 Internal Server Error",
    )
    assert rec2.status == "error"
    assert rec2.status_code == 500

    # Verify session summary
    summary = tracker.get_session_summary()
    assert summary["total_calls"] == 2
    assert summary["successful_calls"] == 1
    assert summary["failed_calls"] == 1
    assert summary["total_tokens"] == 1600
    assert summary["prompt_tokens"] == 1200
    assert summary["completion_tokens"] == 400

    # Verify file persistence
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    data1 = json.loads(lines[0])
    assert data1["provider"] == "gemini"
    assert data1["model"] == "gemini-2.0-flash"
    assert data1["status"] == "success"

    data2 = json.loads(lines[1])
    assert data2["status"] == "error"
    assert data2["status_code"] == 500


def test_telemetry_singleton():
    tracker = get_telemetry_tracker()
    assert tracker is not None
    assert isinstance(tracker, AITelemetryTracker)
