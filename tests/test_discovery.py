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
    assert "gemini-2.0-flash" in model_ids
    assert "gemini-1.5-flash" in model_ids


def test_fetch_models_for_provider():
    gemini_models = ProviderDiscovery.fetch_models_for_provider("gemini")
    assert any(m[1] == "gemini-2.0-flash" for m in gemini_models)
    groq_models = ProviderDiscovery.fetch_models_for_provider("groq")
    assert any(m[1] == "llama-3.3-70b-versatile" for m in groq_models)


def test_deepseek_models_list():
    status = ProviderDiscovery.check_deepseek()
    assert status.slug == "deepseek"
    model_ids = [m.id for m in status.models]
    assert "deepseek-chat" in model_ids
    assert "deepseek-reasoner" in model_ids


def test_groq_models_list():
    status = ProviderDiscovery.check_groq()
    assert status.slug == "groq"
    model_ids = [m.id for m in status.models]
    assert "llama-3.3-70b-versatile" in model_ids



def test_openrouter_models_list():
    status = ProviderDiscovery.check_openrouter()
    assert status.slug == "openrouter"
    model_ids = [m.id for m in status.models]
    assert "anthropic/claude-3.7-sonnet" in model_ids
    assert "openai/gpt-4o" in model_ids


def test_anthropic_models_list():
    status = ProviderDiscovery.check_anthropic()
    assert status.slug == "anthropic"
    model_ids = [m.id for m in status.models]
    assert "claude-3-7-sonnet-20250219" in model_ids
    assert "claude-3-5-sonnet-20241022" in model_ids


def test_openai_models_list():
    status = ProviderDiscovery.check_openai()
    assert status.slug == "openai"
    model_ids = [m.id for m in status.models]
    assert "gpt-4o" in model_ids
    assert "o3-mini" in model_ids


def test_mistral_models_list():
    status = ProviderDiscovery.check_mistral()
    assert status.slug == "mistral"
    model_ids = [m.id for m in status.models]
    assert "mistral-large-latest" in model_ids
    assert "codestral-latest" in model_ids


def test_discover_all_contains_ten_providers():
    all_statuses = ProviderDiscovery.discover_all()
    slugs = [s.slug for s in all_statuses]
    expected = [
        "gemini", "openrouter", "anthropic", "openai",
        "deepseek", "groq", "mistral", "lmstudio", "ollama", "mock"
    ]
    for exp in expected:
        assert exp in slugs


def test_switch_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ProviderDiscovery.switch_model("mock", "mock-deterministic") is True
    assert ProviderDiscovery.switch_model("anthropic", "claude-3-7-sonnet-20250219") is True
    assert ProviderDiscovery.switch_model("openrouter", "anthropic/claude-3.7-sonnet") is True

