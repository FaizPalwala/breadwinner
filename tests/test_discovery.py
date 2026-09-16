"""Unit tests for provider and model discovery."""

from breadwinner.providers.discovery import ProviderDiscovery


def test_mock_provider_discovery():
    status = ProviderDiscovery.check_mock()
    assert status.is_available is True
    assert status.slug == "mock"
    assert len(status.models) == 1


def test_gemini_models_list():
    status = ProviderDiscovery.check_gemini()
    assert status.slug == "gemini"
    model_ids = [m.id for m in status.models]
    assert "gemini-2.5-flash" in model_ids
    assert "gemini-1.5-flash" in model_ids


def test_groq_models_list():
    status = ProviderDiscovery.check_groq()
    assert status.slug == "groq"
    model_ids = [m.id for m in status.models]
    assert "llama-3.3-70b-versatile" in model_ids


def test_switch_model(tmp_path, monkeypatch):
    # Test model switching logic
    monkeypatch.chdir(tmp_path)
    success = ProviderDiscovery.switch_model("mock", "mock-deterministic")
    assert success is True
