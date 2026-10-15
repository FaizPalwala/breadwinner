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
    assert not is_usable_chat_model("gemini-1.0-pro")
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
    assert is_usable_chat_model("gemini-2.0-flash")
    assert is_usable_chat_model("gemini-1.5-flash")
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
        {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-1.5-flash", "displayName": "Gemini 1.5 Flash", "supportedGenerationMethods": ["generateContent"]},
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
    assert model_ids == ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]


def test_discover_all_ingredients_bracketed_titles_do_not_vanish(monkeypatch):
    from breadwinner.core.ingestor import UniversalIngestor
    from rich.text import Text

    # Simulate portfolio returning raw bracketed markdown-style navigation titles
    monkeypatch.setattr(
        UniversalIngestor,
        "discover_portfolio_routes",
        lambda base_url, timeout=4: [
            (f"{base_url}/about", "about", "[hire_me]"),
            (f"{base_url}/projects", "projects", "[./projects]"),
            (f"{base_url}/noggin", "articles", "[noggin]"),
            (f"{base_url}/thesis", "research", "[thesis]"),
            (f"{base_url}/projects/graphcontext", "projects", "GraphContext MCP"),
        ]
    )

    items = discover_all_ingredients(["https://faizpalwala.tech"])
    for item in items:
        # Render the label with Rich to verify no tags get stripped into empty dashes
        rendered = Text.from_markup(item.label).plain
        assert ":" in rendered
        title_part = rendered.split(":", 1)[1].strip()
        assert len(title_part) > 0, f"Title vanished after separator in label: {item.label}"
        assert not title_part.startswith("[]"), f"Uncleaned brackets in: {title_part}"


def test_discover_portfolio_routes_scans_projects_index(monkeypatch):
    import requests
    from breadwinner.core.ingestor import UniversalIngestor

    homepage_html = """
    <html>
      <body>
        <a href="/about">[hire_me]</a>
        <a href="/projects">[./projects]</a>
        <a href="/projects/sfhq"><h3>SFHQ-VirtualID</h3><p>Synthetic identity benchmark</p></a>
        <a href="/projects/graphcontext"><h3>GraphContext MCP</h3><p>Privacy-first assistant</p></a>
        <a href="/projects/calendar"><h3>Serverless GitHub Calendar</h3><p>Architecture for React</p></a>
        <a href="/projects/unlearning"><h3>MSc Project: Unlearning</h3><p>Evaluation framework</p></a>
      </body>
    </html>
    """

    projects_page_html = """
    <html>
      <body>
        <a href="/projects/sfhq"><h3>SFHQ-VirtualID</h3></a>
        <a href="/projects/graphcontext"><h3>GraphContext MCP</h3></a>
        <a href="/projects/calendar"><h3>Serverless GitHub Calendar</h3></a>
        <a href="/projects/unlearning"><h3>MSc Project: Unlearning</h3></a>
        <a href="/projects/breadwinner"><h3>Breadwinner</h3><p>Anti-hallucination studio</p></a>
        <a href="/projects/portfolio"><h3>This Portfolio</h3><p>Astro + Tailwind</p></a>
      </body>
    </html>
    """

    class MockResp:
        def __init__(self, text):
            self.text = text
            self.status_code = 200
        def raise_for_status(self):
            pass

    def mock_get(url, *args, **kwargs):
        if url.rstrip("/").endswith("/projects"):
            return MockResp(projects_page_html)
        return MockResp(homepage_html)

    monkeypatch.setattr(requests, "get", mock_get)

    routes = UniversalIngestor.discover_portfolio_routes("https://faizpalwala.tech")
    proj_routes = [r for r in routes if r[1] == "projects"]
    
    # All 6 projects + projects index must be discovered
    proj_titles = [r[2] for r in proj_routes]
    assert "SFHQ-VirtualID" in proj_titles
    assert "GraphContext MCP" in proj_titles
    assert "Serverless GitHub Calendar" in proj_titles
    assert "Breadwinner" in proj_titles
    assert "This Portfolio" in proj_titles
    assert any("Unlearning" in t for t in proj_titles)
    # Total projects: index + 6 projects = 7
    assert len(proj_routes) >= 7

