"""Unit tests for BakeryWelcomeModal onboarding screen."""

import pytest
from unittest.mock import MagicMock
from textual.app import App
from textual.widgets import Input, TextArea, Button

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

