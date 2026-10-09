"""Unit tests for ADR-002 Stage 3 Ingredient Discovery Modal."""

import pytest
from breadwinner.ui.discovery import discover_all_ingredients, IngredientDiscoveryModal
from textual.app import App, ComposeResult


def test_discover_all_ingredients_url(monkeypatch):
    from breadwinner.core.ingestor import UniversalIngestor
    monkeypatch.setattr(
        UniversalIngestor,
        "discover_portfolio_routes",
        lambda base_url, timeout=4: [
            (f"{base_url}/resume.pdf", "resume_pdf", "Resume PDF"),
            (f"{base_url}/about", "about", "About Me"),
            (f"{base_url}/projects", "projects", "Projects"),
            (f"{base_url}/blog/systems", "articles", "Distributed Systems Article"),
        ]
    )

    items = discover_all_ingredients(["https://alex-engineer.dev"])
    assert len(items) == 5
    categories = [i.category for i in items]
    assert "web" in categories
    assert "resume_pdf" in categories
    assert "about" in categories
    assert "projects" in categories
    assert "articles" in categories


def test_discover_all_ingredients_local_files(tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 dummy")

    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("Experienced platform engineer with 5 years experience.", encoding="utf-8")

    items = discover_all_ingredients([str(resume_file), str(notes_file)])
    assert len(items) == 2
    paths = [i.value for i in items]
    assert str(resume_file.resolve()) in paths
    assert str(notes_file.resolve()) in paths


def test_discover_all_ingredients_raw_notes():
    raw_bio = "Senior backend engineer specializing in distributed systems, Raft consensus, and 100k QPS pipelines."
    items = discover_all_ingredients([raw_bio])
    assert len(items) == 1
    assert items[0].category == "notes"
    assert "100k QPS" in items[0].value


class DummyDiscoveryApp(App):
    def __init__(self, sources):
        super().__init__()
        self.sources = sources
        self.modal_result = None

    def on_mount(self):
        def cb(res):
            self.modal_result = res
        self.push_screen(IngredientDiscoveryModal(self.sources), cb)


@pytest.mark.anyio
async def test_ingredient_discovery_modal_interaction():
    app = DummyDiscoveryApp(["https://example.com"])
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert isinstance(app.screen, IngredientDiscoveryModal)
        # Verify submit returns selected values
        app.screen.action_submit()
        await pilot.pause(0.2)
        assert app.modal_result is not None
        assert any("example.com" in s for s in app.modal_result)


def test_is_usable_chat_model():
    from breadwinner.providers.discovery import is_usable_chat_model

    # Should reject deprecated models
    assert not is_usable_chat_model("gemini-2.5-flash")
    assert not is_usable_chat_model("gemini-2.0-flash")
    assert not is_usable_chat_model("text-davinci-003")

    # Should reject TTS, audio, transcription, and speech
    assert not is_usable_chat_model("gemini-3.8-flash-tts")
    assert not is_usable_chat_model("gemini-3.1-flash-tts-preview")
    assert not is_usable_chat_model("whisper-large-v3")
    assert not is_usable_chat_model("gemini-3.5-transcribe")
    assert not is_usable_chat_model("lyria-3-pro-preview")

    # Should reject image, vision, and video generation
    assert not is_usable_chat_model("nano-banana-pro-preview")
    assert not is_usable_chat_model("gemini-3.1-flash-image")
    assert not is_usable_chat_model("dall-e-3")
    assert not is_usable_chat_model("veo-3.1-generate-preview")

    # Should reject embeddings, robotics, and computer use
    assert not is_usable_chat_model("gemini-embedding-2")
    assert not is_usable_chat_model("text-embedding-3-small")
    assert not is_usable_chat_model("gemini-robotics-er-2-preview")
    assert not is_usable_chat_model("gemini-2.5-computer-use-preview-10-2025")

    # Should accept valid text/chat instruction models
    assert is_usable_chat_model("gemini-3.8-flash")
    assert is_usable_chat_model("gemini-3.5-flash")
    assert is_usable_chat_model("gemini-flash-latest")
    assert is_usable_chat_model("gpt-4o")
    assert is_usable_chat_model("gpt-4o-mini")
    assert is_usable_chat_model("o3-mini")
    assert is_usable_chat_model("llama-3.3-70b-versatile")
    assert is_usable_chat_model("claude-3-7-sonnet-20250219")
    assert is_usable_chat_model("deepseek-chat")


def test_provider_discovery_filters_non_chat_gemini_models(monkeypatch):
    from breadwinner.providers.discovery import ProviderDiscovery
    from breadwinner.config import settings
    import requests

    monkeypatch.setattr(settings, "gemini_api_key", "mock-test-key")
    monkeypatch.setattr(settings, "breadwinner_llm_provider", "gemini")

    mock_raw_models = [
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.8-flash-tts", "displayName": "Gemini 3.8 Flash TTS", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/nano-banana-pro-preview", "displayName": "Nano Banana Pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-2", "displayName": "Gemini Embedding 2", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8 Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.5-flash", "displayName": "Gemini 3.5 Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-flash-latest", "displayName": "Gemini Flash Latest", "supportedGenerationMethods": ["generateContent"]},
    ]

    class MockResponse:
        status_code = 200
        def json(self):
            return {"models": mock_raw_models}

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse())

    status = ProviderDiscovery.check_gemini()
    assert status.is_available
    model_ids = [m.id for m in status.models]

    # Non-chat, TTS, Image, and Deprecated must be filtered out
    assert "gemini-2.5-flash" not in model_ids
    assert "gemini-3.8-flash-tts" not in model_ids
    assert "nano-banana-pro-preview" not in model_ids
    assert "gemini-embedding-2" not in model_ids

    # Usable models must be preserved in ranked order
    assert model_ids == ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]

