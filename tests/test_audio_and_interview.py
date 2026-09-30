"""Tests for audio voice transcription and adaptive interview questioning."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from breadwinner.core.models import CandidateProfile, WorkExperience, Project
from breadwinner.core.interview import generate_adaptive_questions
from breadwinner.core.audio import AudioTranscriber, AudioRecorder, AudioBackendInfo


def test_audio_backend_detection():
    backend_info = AudioTranscriber.detect_backend()
    assert isinstance(backend_info, AudioBackendInfo)
    assert backend_info.name in (
        "mlx-whisper", "faster-whisper", "whisper", "groq-whisper",
        "openai-whisper", "gemini-audio", "mock", "none"
    )


def test_audio_transcriber_mock():
    dummy_wav = Path("./test_dummy.wav")
    with patch.object(Path, "exists", return_value=True):
        t = AudioTranscriber(backend_override="mock")
        text = t.transcribe(dummy_wav)
        assert "Kubernetes" in text
        assert "latency" in text


def test_audio_recorder_availability():
    avail = AudioRecorder.is_available()
    assert isinstance(avail, bool)


def test_generate_adaptive_questions_deterministic():
    profile = CandidateProfile(
        full_name="Jane Doe",
        title="Backend Engineer",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Software Engineer",
                bullets=["Helped maintain services and wrote API endpoints."]
            )
        ],
        projects=[
            Project(
                name="CacheMesh",
                description="Distributed caching layer.",
                tech_stack=["Go", "Redis"]
            )
        ]
    )
    qs = generate_adaptive_questions(profile)
    assert 2 <= len(qs) <= 6
    ids = [q["id"] for q in qs]
    assert any("metric_gap" in q_id for q_id in ids)
    assert any("Acme" in q["prompt"] or "Acme" in q["title"] for q in qs)
    assert any("proj_arch" in q_id for q_id in ids)
    assert any("CacheMesh" in q["prompt"] or "CacheMesh" in q["title"] for q in qs)


def test_discover_groq_whisper_model_fallback():
    m = AudioTranscriber.discover_groq_whisper_model(api_key=None)
    assert "whisper" in m.lower()


def test_discover_groq_whisper_model_mocked(monkeypatch):
    import requests
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"id": "whisper-large-v3"},
            {"id": "whisper-large-v3-turbo"},
            {"id": "llama-3.3-70b-versatile"}
        ]
    }
    monkeypatch.setattr(requests, "get", lambda *a, **k: mock_resp)
    chosen = AudioTranscriber.discover_groq_whisper_model(api_key="dummy_key")
    assert chosen == "whisper-large-v3-turbo"
