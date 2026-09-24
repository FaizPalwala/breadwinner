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
