"""Unit tests for BakeryWelcomeModal onboarding screen."""

import pytest
from unittest.mock import MagicMock
from textual.app import App
from textual.widgets import Input, TextArea, Button, Select, Static

from breadwinner.ui.welcome import BakeryWelcomeModal


class WelcomeHostApp(App):
    """Test harness to mount BakeryWelcomeModal."""
    def __init__(self, modal):
        super().__init__()
        self.modal = modal
        self.result = None

    def on_mount(self):
        def _cb(res):
            self.result = res
        self.push_screen(self.modal, callback=_cb)


@pytest.mark.anyio
async def test_welcome_modal_load_demo():
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        assert modal.query_one("#welcome-container") is not None
        assert modal.query_one("#welcome-mascot") is not None
        assert modal.query_one("#input-welcome-source", Input) is not None
        assert modal.query_one("#btn-welcome-demo", Button) is not None

        # Click demo loaf button
        btn = modal.query_one("#btn-welcome-demo", Button)
        btn.press()
        await pilot.pause()

    assert app.result == {"action": "demo"}


@pytest.mark.anyio
async def test_welcome_modal_import_source():
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Fill source input
        source_input = modal.query_one("#input-welcome-source", Input)
        source_input.value = "https://example.com/resume.pdf"

        # Click stock pantry
        btn = modal.query_one("#btn-welcome-stock", Button)
        btn.press()
        await pilot.pause()

    assert app.result == {
        "action": "import",
        "source": "https://example.com/resume.pdf",
        "sources": ["https://example.com/resume.pdf"]
    }


@pytest.mark.anyio
async def test_welcome_modal_skip():
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        btn = modal.query_one("#btn-welcome-skip", Button)
        btn.press()
        await pilot.pause()

    assert app.result is None


@pytest.mark.anyio
async def test_welcome_modal_drag_and_drop_cleaning():
    """Verify dropped terminal file paths with quotes and file:// prefixes are cleaned."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = modal.query_one("#input-welcome-source", Input)
        # Simulate dragged terminal input with single quotes
        source_input.value = "'/Users/test/my_resume.pdf'"
        await pilot.pause()

        badge = modal.query_one("#ingredient-badge")
        assert badge is not None

        # Click stock pantry
        btn = modal.query_one("#btn-welcome-stock", Button)
        btn.press()
        await pilot.pause()

    assert app.result == {
        "action": "import",
        "source": "/Users/test/my_resume.pdf",
        "sources": ["/Users/test/my_resume.pdf"]
    }


@pytest.mark.anyio
async def test_welcome_modal_tabs_and_bio():
    """Verify entering raw career bio notes in the unified Dough Bin."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = modal.query_one("#input-welcome-source", Input)
        source_input.value = "Staff SRE with 8 years scaling distributed systems."
        await pilot.pause()

        # Click stock pantry
        btn = modal.query_one("#btn-welcome-stock", Button)
        btn.press()
        await pilot.pause()

    assert app.result == {
        "action": "import",
        "source": "Staff SRE with 8 years scaling distributed systems.",
        "sources": ["Staff SRE with 8 years scaling distributed systems."]
    }


@pytest.mark.anyio
async def test_welcome_modal_ai_setup_flow(tmp_path, monkeypatch):
    """Verify Step 1 AI keys -> Step 2 Model discovery -> Step 3 Pantry flow."""
    env_file = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        ai_step = modal.query_one("#welcome-ai-step")
        models_step = modal.query_one("#welcome-models-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "block"
        assert models_step.styles.display == "none"
        assert pantry_step.styles.display == "none"

        # Step 1: Select gemini via pill and fill API key
        pill_gemini = modal.query_one("#pill-prov-gemini", Button)
        pill_gemini.press()
        await pilot.pause()

        key_input = modal.query_one("#input-welcome-api-key", Input)
        key_input.value = "AIzaSyTestApiKey12345"
        await pilot.pause()

        # Click Next: Discover Live Models
        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # Step 1 is hidden, Step 2 is visible
        assert ai_step.styles.display == "none"
        assert models_step.styles.display == "block"
        assert pantry_step.styles.display == "none"

        # Step 2: Save active model and proceed to pantry
        btn_save_model = modal.query_one("#btn-welcome-save-model", Button)
        btn_save_model.press()
        await pilot.pause()

        # Step 2 is hidden, Step 3 (pantry) is visible
        assert ai_step.styles.display == "none"
        assert models_step.styles.display == "none"
        assert pantry_step.styles.display == "block"

        # Step 3: Click demo loaf in pantry
        btn_demo = modal.query_one("#btn-welcome-demo", Button)
        btn_demo.press()
        await pilot.pause()

    assert app.result == {"action": "demo"}
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=\"AIzaSyTestApiKey12345\"" in content


@pytest.mark.anyio
async def test_welcome_modal_ai_mock_drive(tmp_path, monkeypatch):
    """Verify instant test drive button configures mock provider and advances directly to pantry."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        btn_mock = modal.query_one("#btn-welcome-mock-drive", Button)
        btn_mock.press()
        await pilot.pause()

        ai_step = modal.query_one("#welcome-ai-step")
        models_step = modal.query_one("#welcome-models-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "none"
        assert models_step.styles.display == "none"
        assert pantry_step.styles.display == "block"


@pytest.mark.anyio
async def test_welcome_modal_ai_skip(tmp_path, monkeypatch):
    """Verify skip AI button advances directly to pantry."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        btn_skip_ai = modal.query_one("#btn-welcome-skip-ai", Button)
        btn_skip_ai.press()
        await pilot.pause()

        ai_step = modal.query_one("#welcome-ai-step")
        models_step = modal.query_one("#welcome-models-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "none"
        assert models_step.styles.display == "none"
        assert pantry_step.styles.display == "block"


@pytest.mark.anyio
async def test_welcome_modal_step2_live_model_discovery(tmp_path, monkeypatch):
    """Verify that Step 2 fetches and populates live models for active configured providers."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Configure keys for Groq and Gemini
        pill_groq = modal.query_one("#pill-prov-groq", Button)
        pill_groq.press()
        await pilot.pause()
        modal.query_one("#input-welcome-api-key", Input).value = "gsk_test123"
        await pilot.pause()

        pill_gemini = modal.query_one("#pill-prov-gemini", Button)
        pill_gemini.press()
        await pilot.pause()
        modal.query_one("#input-welcome-api-key", Input).value = "AIzaSy_test123"
        await pilot.pause()

        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # We are on Step 2
        active_sel = modal.query_one("#select-active-provider", Select)
        model_sel = modal.query_one("#select-welcome-model", Select)

        # Active provider options should contain configured providers (Gemini, Groq)
        # and exclude unconfigured providers (Anthropic, OpenAI, etc.)
        prov_values = [val for _, val in active_sel._options]
        assert "groq" in prov_values
        assert "gemini" in prov_values
        assert "anthropic" not in prov_values
        assert "openai" not in prov_values

        # Switch to Groq
        active_sel.value = "groq"
        await pilot.pause()
        assert model_sel.value == "llama-3.3-70b-versatile"

        # Switch to Gemini
        active_sel.value = "gemini"
        await pilot.pause()
        assert model_sel.value == "gemini-2.0-flash"


@pytest.mark.anyio
async def test_welcome_modal_step2_single_provider_badge_and_filter(tmp_path, monkeypatch):
    """Verify that when only 1 provider is configured, Step 2 displays a single-engine badge,
    hides the provider select dropdown, and strictly populates its models."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        pill_gemini = modal.query_one("#pill-prov-gemini", Button)
        pill_gemini.press()
        await pilot.pause()
        modal.query_one("#input-welcome-api-key", Input).value = "AIzaSy_only_gemini"
        await pilot.pause()

        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # In Step 2
        active_sel = modal.query_one("#select-active-provider", Select)
        badge = modal.query_one("#label-step2-engine-badge", Static)
        model_sel = modal.query_one("#select-welcome-model", Select)

        # Single provider badge should be visible, dropdown hidden
        assert active_sel.styles.display == "none"
        assert badge.styles.display == "block"
        assert "Google Gemini" in str(badge.render())

        # Models populated should be Gemini's, not Anthropic/OpenAI
        assert model_sel.value == "gemini-2.0-flash"


@pytest.mark.anyio
async def test_welcome_modal_exit_button():
    """Verify that clicking the Quit button exits the application."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        exit_btn = modal.query_one("#btn-welcome-exit", Button)
        assert exit_btn is not None
        exit_btn.press()
        await pilot.pause()

    # The app should have exited
    assert app.is_running is False


@pytest.mark.anyio
async def test_welcome_modal_custom_model_option_c(tmp_path, monkeypatch):
    """Verify Option C: user can choose Custom Model ID on Step 2 and enter custom model."""
    env_file = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Step 1: Configure key via pill
        pill_gemini = modal.query_one("#pill-prov-gemini", Button)
        pill_gemini.press()
        await pilot.pause()

        key_input = modal.query_one("#input-welcome-api-key", Input)
        key_input.value = "AIzaSyCustomKey"
        await pilot.pause()

        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # Step 2: Custom model ID input
        custom_input = modal.query_one("#input-welcome-custom-model", Input)
        assert custom_input.styles.display == "none"

        # Select custom in model dropdown
        sel_model = modal.query_one("#select-welcome-model", Select)
        sel_model.value = "custom"
        await pilot.pause()

        # Custom input should now be visible
        assert custom_input.styles.display == "block"

        # Enter custom model ID
        custom_input.value = "gemini-3.8-flash"
        await pilot.pause()

        # Save AI settings and advance to pantry
        btn_save_model = modal.query_one("#btn-welcome-save-model", Button)
        btn_save_model.press()
        await pilot.pause()

        ai_step = modal.query_one("#welcome-ai-step")
        models_step = modal.query_one("#welcome-models-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "none"
        assert models_step.styles.display == "none"
        assert pantry_step.styles.display == "block"

    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'GEMINI_MODEL="gemini-3.8-flash"' in content
    assert 'GEMINI_API_KEY="AIzaSyCustomKey"' in content


@pytest.mark.anyio
async def test_welcome_modal_openrouter_setup(tmp_path, monkeypatch):
    """Verify setting up OpenRouter provider and advancing through Step 1 and Step 2."""
    env_file = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        pill_openrouter = modal.query_one("#pill-prov-openrouter", Button)
        pill_openrouter.press()
        await pilot.pause()

        key_input = modal.query_one("#input-welcome-api-key", Input)
        key_input.value = "sk-or-v1-abcdef12345"
        await pilot.pause()

        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        btn_save_model = modal.query_one("#btn-welcome-save-model", Button)
        btn_save_model.press()
        await pilot.pause()

    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'BREADWINNER_LLM_PROVIDER="openrouter"' in content
    assert 'OPENROUTER_API_KEY="sk-or-v1-abcdef12345"' in content


@pytest.mark.anyio
async def test_welcome_modal_back_to_keys(tmp_path, monkeypatch):
    """Verify that clicking Back to Keys on Step 2 returns to Step 1."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        pill_ollama = modal.query_one("#pill-prov-ollama", Button)
        pill_ollama.press()
        await pilot.pause()

        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # On Step 2
        models_step = modal.query_one("#welcome-models-step")
        assert models_step.styles.display == "block"

        # Click Back to Keys
        btn_back = modal.query_one("#btn-welcome-back-to-keys", Button)
        btn_back.press()
        await pilot.pause()

        ai_step = modal.query_one("#welcome-ai-step")
        assert ai_step.styles.display == "block"
        assert models_step.styles.display == "none"


@pytest.mark.anyio
async def test_welcome_modal_multi_provider_key_configuration(tmp_path, monkeypatch):
    """Verify entering multiple keys using provider switcher pills and saving all to .env."""
    env_file = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Check Step 1 mascot dialogue is correct (not overwritten by Step 2)
        mascot = modal.query_one("#welcome-mascot")
        assert mascot.badge_title == "BREADWINNER SETUP STUDIO"
        assert mascot.status_line.startswith("Engine:")

        # Step 1: Click Gemini pill to ensure active engine is gemini
        pill_gemini = modal.query_one("#pill-prov-gemini", Button)
        pill_gemini.press()
        await pilot.pause()

        key_input = modal.query_one("#input-welcome-api-key", Input)
        key_input.value = "AIzaSyGeminiKey123"
        await pilot.pause()

        # Click OpenRouter pill
        pill_openrouter = modal.query_one("#pill-prov-openrouter", Button)
        pill_openrouter.press()
        await pilot.pause()

        # Input should now reflect OpenRouter
        assert key_input.placeholder.startswith("Enter OpenRouter")
        key_input.value = "sk-or-v1-OpenRouterKey456"
        await pilot.pause()

        # Click Anthropic pill
        pill_anthropic = modal.query_one("#pill-prov-anthropic", Button)
        pill_anthropic.press()
        await pilot.pause()

        assert key_input.placeholder.startswith("Enter Anthropic")
        key_input.value = "sk-ant-AnthropicKey789"
        await pilot.pause()

        # Verify provider keys tracked and summary
        assert modal.provider_keys["gemini"] == "AIzaSyGeminiKey123"
        assert modal.provider_keys["openrouter"] == "sk-or-v1-OpenRouterKey456"
        assert modal.provider_keys["anthropic"] == "sk-ant-AnthropicKey789"
        summary_text = modal.render_keys_summary()
        assert "Google Gemini" in summary_text
        assert "OpenRouter" in summary_text
        assert "Anthropic Claude" in summary_text

        # Advance to Step 2
        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        assert modal.query_one("#welcome-models-step").styles.display == "block"

    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'GEMINI_API_KEY="AIzaSyGeminiKey123"' in content
    assert 'OPENROUTER_API_KEY="sk-or-v1-OpenRouterKey456"' in content
    assert 'ANTHROPIC_API_KEY="sk-ant-AnthropicKey789"' in content


@pytest.mark.anyio
async def test_welcome_modal_all_nine_provider_pills_interactive(tmp_path, monkeypatch):
    """Verify that all 9 provider pills exist, dropdown is eliminated, and pill switching functions."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Step 1 should NOT have the redundant dropdown
        with pytest.raises(Exception):
            modal.query_one("#select-welcome-provider")

        expected_slugs = [
            "gemini", "openrouter", "anthropic", "openai", "deepseek",
            "groq", "mistral", "ollama", "lmstudio"
        ]

        # Verify all 9 pills are mounted
        for slug in expected_slugs:
            pill = modal.query_one(f"#pill-prov-{slug}", Button)
            assert pill is not None

        key_input = modal.query_one("#input-welcome-api-key", Input)

        # Click Ollama pill (local provider, key input disabled)
        pill_ollama = modal.query_one("#pill-prov-ollama", Button)
        pill_ollama.press()
        await pilot.pause()

        assert modal.active_provider == "ollama"
        assert pill_ollama.has_class("active-pill")
        assert key_input.disabled is True

        # Click DeepSeek pill (frontier cloud, key input enabled)
        pill_deepseek = modal.query_one("#pill-prov-deepseek", Button)
        pill_deepseek.press()
        await pilot.pause()

        assert modal.active_provider == "deepseek"
        assert pill_deepseek.has_class("active-pill")
        assert not pill_ollama.has_class("active-pill")
        assert key_input.disabled is False
        assert "DeepSeek" in key_input.placeholder


@pytest.mark.anyio
async def test_welcome_modal_multi_source_staging():
    """Verify entering website, committing via Enter to tray, adding dissertation, and stocking both."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = modal.query_one("#input-welcome-source", Input)

        # 1. Type website and hit Enter (Input.Submitted)
        source_input.value = "faizpalwala.tech"
        await source_input.action_submit()
        await pilot.pause()

        # Input should be cleared for next ingredient and staged in tray
        assert source_input.value == ""
        assert len(modal.staged_ingredients) == 1
        assert "faizpalwala.tech" in modal.staged_ingredients
        assert len(modal.query(".ingredient-pill")) == 1

        # 2. Add second ingredient: dissertation
        source_input.value = "'/Users/test/dissertation.pdf'"
        await source_input.action_submit()
        await pilot.pause()

        assert source_input.value == ""
        assert len(modal.staged_ingredients) == 2
        assert "/Users/test/dissertation.pdf" in modal.staged_ingredients
        assert len(modal.query(".ingredient-pill")) == 2

        # 3. Press Enter on empty input to trigger stocking
        await source_input.action_submit()
        await pilot.pause()

    assert app.result is not None
    assert app.result["action"] == "import"
    assert app.result["sources"] == ["https://faizpalwala.tech", "/Users/test/dissertation.pdf"]


@pytest.mark.anyio
async def test_welcome_modal_tray_pill_removal():
    """Verify clicking ✕ on a tray pill badge removes it from the staged queue."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = modal.query_one("#input-welcome-source", Input)

        # Add two ingredients
        source_input.value = "https://example.com/site"
        await source_input.action_submit()
        await pilot.pause()

        source_input.value = "/Users/test/resume.docx"
        await source_input.action_submit()
        await pilot.pause()

        assert len(modal.staged_ingredients) == 2

        # Click remove on first pill (site)
        del_btn = modal.query(".ingredient-pill").first()
        del_btn.press()
        await pilot.pause()

        assert len(modal.staged_ingredients) == 1
        assert modal.staged_ingredients[0] == "/Users/test/resume.docx"

        # Submit remaining
        btn_stock = modal.query_one("#btn-welcome-stock", Button)
        btn_stock.press()
        await pilot.pause()

    assert app.result == {
        "action": "import",
        "source": "/Users/test/resume.docx",
        "sources": ["/Users/test/resume.docx"]
    }


@pytest.mark.anyio
async def test_welcome_modal_drag_and_drop_paste_event():
    """Verify pasting or dropping into input preserves existing input in queue instead of string-concatenating."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = modal.query_one("#input-welcome-source", Input)

        # User started typing website
        source_input.value = "faizpalwala.tech"
        await pilot.pause()

        # User drops dissertation.pdf from Finder into the terminal
        modal.handle_pasted_or_dropped_text("'/Users/test/dissertation.pdf'")
        await pilot.pause()

        # Existing website should have been moved into staged_ingredients queue
        assert "faizpalwala.tech" in modal.staged_ingredients
        # And input now holds the clean dropped path
        assert source_input.value == "/Users/test/dissertation.pdf"

        # Click Stock Pantry
        btn_stock = modal.query_one("#btn-welcome-stock", Button)
        btn_stock.press()
        await pilot.pause()

    assert app.result is not None
    assert app.result["action"] == "import"
    assert app.result["sources"] == ["https://faizpalwala.tech", "/Users/test/dissertation.pdf"]





