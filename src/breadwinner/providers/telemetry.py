"""AI Telemetry and Cost Tracking for Breadwinner.

Tracks every LLM call, token usage, latency, error status, and estimated USD cost.
Logs to ~/.breadwinner/logs/ai_calls.jsonl with thread-safe append.
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from breadwinner.config import settings

# Per 1,000,000 tokens (USD)
PRICING_CATALOG: Dict[str, Tuple[float, float]] = {
    # Gemini
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Anthropic
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    # Groq / OpenRouter
    "llama-3.3-70b": (0.59, 0.79),
    "llama-3.1-8b": (0.05, 0.08),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    # Local endpoints
    "ollama": (0.0, 0.0),
    "lmstudio": (0.0, 0.0),
    "local": (0.0, 0.0),
}


def estimate_call_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated USD cost based on model name and token counts."""
    model_lower = model_name.lower()
    rates = (0.0, 0.0)

    for prefix, (prompt_rate, comp_rate) in PRICING_CATALOG.items():
        if prefix in model_lower:
            rates = (prompt_rate, comp_rate)
            break

    prompt_cost = (prompt_tokens / 1_000_000.0) * rates[0]
    comp_cost = (completion_tokens / 1_000_000.0) * rates[1]
    return round(prompt_cost + comp_cost, 6)


@dataclass
class AICallRecord:
    timestamp: str
    provider: str
    model: str
    duration_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    status: str  # "success" or "error"
    status_code: Optional[int] = None
    error_message: Optional[str] = None


class AITelemetryTracker:
    """Thread-safe telemetry tracker recording AI calls, tokens, latency, and estimated cost."""

    def __init__(self, log_path: Optional[Path] = None):
        if log_path is not None:
            self.log_path = log_path
        else:
            base_dir = Path.home() / ".breadwinner" / "logs"
            self.log_path = base_dir / "ai_calls.jsonl"

        self._session_records: List[AICallRecord] = []

    def record_call(
        self,
        provider: str,
        model: str,
        duration_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        status: str = "success",
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> AICallRecord:
        """Record an AI API call and persist to JSONL log."""
        total_tokens = prompt_tokens + completion_tokens
        cost = estimate_call_cost(model, prompt_tokens, completion_tokens)
        ts = datetime.now(timezone.utc).isoformat()

        rec = AICallRecord(
            timestamp=ts,
            provider=provider,
            model=model,
            duration_ms=round(duration_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            status=status,
            status_code=status_code,
            error_message=error_message,
        )

        self._session_records.append(rec)
        self._append_to_file(rec)
        return rec

    def _append_to_file(self, rec: AICallRecord) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec)) + "\n")
        except Exception:
            # Telemetry logging should never crash the main application
            pass

    def get_session_summary(self) -> Dict[str, Any]:
        """Aggregate telemetry statistics for the current running session."""
        total = len(self._session_records)
        successes = sum(1 for r in self._session_records if r.status == "success")
        failures = sum(1 for r in self._session_records if r.status == "error")
        total_prompt_tokens = sum(r.prompt_tokens for r in self._session_records)
        total_completion_tokens = sum(r.completion_tokens for r in self._session_records)
        total_tokens = sum(r.total_tokens for r in self._session_records)
        total_cost = sum(r.estimated_cost_usd for r in self._session_records)
        avg_latency = (
            sum(r.duration_ms for r in self._session_records) / total
            if total > 0
            else 0.0
        )

        return {
            "total_calls": total,
            "successful_calls": successes,
            "failed_calls": failures,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_duration_ms": round(avg_latency, 1),
            "log_path": str(self.log_path),
        }

    def get_recent_calls(self, limit: int = 10) -> List[AICallRecord]:
        return self._session_records[-limit:]

    def reset_session(self) -> None:
        """Reset session records (useful for test isolation)."""
        self._session_records.clear()


_GLOBAL_TELEMETRY: Optional[AITelemetryTracker] = None


def get_telemetry_tracker() -> AITelemetryTracker:
    """Return the global AITelemetryTracker singleton."""
    global _GLOBAL_TELEMETRY
    if _GLOBAL_TELEMETRY is None:
        _GLOBAL_TELEMETRY = AITelemetryTracker()
    return _GLOBAL_TELEMETRY
