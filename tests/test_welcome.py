"""Unit tests for BakeryWelcomeModal onboarding screen."""

import pytest
from unittest.mock import MagicMock
from textual.app import App
from textual.widgets import Input, TextArea, Button, Select

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

    assert app.result == {"action": "import", "source": "https://example.com/resume.pdf"}


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

    assert app.result == {"action": "import", "source": "/Users/test/my_resume.pdf"}


@pytest.mark.anyio
async def test_welcome_modal_tabs_and_bio():
    """Verify switching to bio notes tab and submitting pasted text."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry)
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        # Click bio notes tab
        btn_tab_bio = modal.query_one("#btn-tab-bio", Button)
        btn_tab_bio.press()
        await pilot.pause()

        bio_box = modal.query_one("#welcome-bio-box")
        assert bio_box.styles.display == "block"

        # Type bio text
        bio_input = modal.query_one("#input-welcome-bio", TextArea)
        bio_input.text = "Staff SRE with 8 years scaling distributed systems."

        # Click stock pantry
        btn = modal.query_one("#btn-welcome-stock", Button)
        btn.press()
        await pilot.pause()

    assert app.result == {"action": "import", "source": "Staff SRE with 8 years scaling distributed systems."}


@pytest.mark.anyio
async def test_welcome_modal_ai_setup_flow(tmp_path, monkeypatch):
    """Verify Step 1 AI engine configuration transitions cleanly to Step 2 pantry."""
    env_file = tmp_path / ".env"
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        ai_step = modal.query_one("#welcome-ai-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "block"
        assert pantry_step.styles.display == "none"

        # Select gemini explicitly
        sel = modal.query_one("#select-welcome-provider", Select)
        sel.value = "gemini"

        # Fill API key
        key_input = modal.query_one("#input-welcome-api-key", Input)
        key_input.value = "AIzaSyTestApiKey12345"

        # Click save AI
        btn_save = modal.query_one("#btn-welcome-save-ai", Button)
        btn_save.press()
        await pilot.pause()

        # Step 1 should now be hidden and Step 2 visible
        assert ai_step.styles.display == "none"
        assert pantry_step.styles.display == "block"

        # Now click demo in step 2
        btn_demo = modal.query_one("#btn-welcome-demo", Button)
        btn_demo.press()
        await pilot.pause()

    assert app.result == {"action": "demo"}
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=\"AIzaSyTestApiKey12345\"" in content


@pytest.mark.anyio
async def test_welcome_modal_ai_mock_drive(tmp_path, monkeypatch):
    """Verify instant test drive button configures mock provider and advances to pantry."""
    monkeypatch.chdir(tmp_path)

    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        btn_mock = modal.query_one("#btn-welcome-mock-drive", Button)
        btn_mock.press()
        await pilot.pause()

        ai_step = modal.query_one("#welcome-ai-step")
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "none"
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
        pantry_step = modal.query_one("#welcome-pantry-step")
        assert ai_step.styles.display == "none"
        assert pantry_step.styles.display == "block"


@pytest.mark.anyio
async def test_welcome_modal_model_dropdown_populates():
    """Verify that switching AI providers dynamically populates available models."""
    mock_pantry = MagicMock()
    modal = BakeryWelcomeModal(pantry=mock_pantry, initial_step="ai")
    app = WelcomeHostApp(modal)

    async with app.run_test(size=(120, 40)) as pilot:
        sel_prov = modal.query_one("#select-welcome-provider", Select)
        sel_model = modal.query_one("#select-welcome-model", Select)

        # Initially gemini is selected and gemini models are loaded
        sel_prov.value = "gemini"
        await pilot.pause()
        assert sel_model.value == "gemini-2.5-flash"

        # Switch to DeepSeek
        sel_prov.value = "deepseek"
        await pilot.pause()
        assert sel_model.value == "deepseek-chat"

        # Switch to Groq
        sel_prov.value = "groq"
        await pilot.pause()
        assert sel_model.value == "llama-3.3-70b-versatile"

        # Switch back to Gemini
        sel_prov.value = "gemini"
        await pilot.pause()
        assert sel_model.value == "gemini-2.5-flash"

