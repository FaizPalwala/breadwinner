"""Unit tests for 8-bit retro bakery aesthetic and animated TUI sprites."""

import pytest
from breadwinner.ui.retro import (
    AnimatedOven,
    AnimatedMascot,
    BakeryStepper,
    RetroProgressBar,
    BakingModal,
    OVEN_FRAMES,
    OVEN_CELEBRATION_FRAME,
    OVEN_BURNT_FRAME,
    MASCOT_FRAMES
)
from textual.app import App, ComposeResult
from textual.widgets import Button, Label


def test_animated_oven_frames_and_states():
    oven = AnimatedOven()
    assert oven.state == "baking"
    assert oven.frame_idx == 0

    # Advance through baking cycle
    for i in range(1, len(OVEN_FRAMES)):
        oven.advance_frame()
        assert oven.frame_idx == i

    # Wraps around
    oven.advance_frame()
    assert oven.frame_idx == 0

    # Celebration state
    oven.set_state("celebrate")
    assert oven.state == "celebrate"

    # Burnt state
    oven.set_state("burnt")
    assert oven.state == "burnt"

    # Idle state
    oven.set_state("idle")
    assert oven.state == "idle"


def test_animated_mascot_frames_and_speech():
    mascot = AnimatedMascot()
    assert mascot.frame_idx == 0

    for i in range(1, len(MASCOT_FRAMES)):
        mascot.advance_frame()
        assert mascot.frame_idx == i

    # Set custom speech bubble
    mascot.set_message("Test Baking Message!")
    assert mascot.active_message == "Test Baking Message!"


def test_bakery_stepper_stages():
    stepper = BakeryStepper(current_stage=0)
    assert stepper.current_stage == 0

    # Advance stage to PROOF (index 2)
    stepper.set_stage(2)
    assert stepper.current_stage == 2

    # Clamps high stage
    stepper.set_stage(10)
    assert stepper.current_stage == 4

    # Clamps low stage
    stepper.set_stage(-5)
    assert stepper.current_stage == 0


def test_retro_progress_bar():
    bar = RetroProgressBar(percent=25)
    assert bar.percent == 25

    bar.update_progress(80)
    assert bar.percent == 80

    # Clamping
    bar.update_progress(150)
    assert bar.percent == 100
    bar.update_progress(-20)
    assert bar.percent == 0


class DummyRetroApp(App):
    def compose(self) -> ComposeResult:
        yield AnimatedOven(id="test-oven")
        yield AnimatedMascot(id="test-mascot")
        yield BakeryStepper(current_stage=1, id="test-stepper")
        yield RetroProgressBar(percent=50, id="test-gauge")


@pytest.mark.anyio
async def test_retro_widgets_in_textual_app():
    app = DummyRetroApp()
    async with app.run_test() as pilot:
        oven = app.query_one("#test-oven", AnimatedOven)
        mascot = app.query_one("#test-mascot", AnimatedMascot)
        stepper = app.query_one("#test-stepper", BakeryStepper)
        gauge = app.query_one("#test-gauge", RetroProgressBar)

        assert oven is not None
        assert mascot is not None
        assert stepper is not None
        assert gauge is not None


@pytest.mark.anyio
async def test_baking_modal_mount():
    modal = BakingModal(
        task_type="bake_pdf",
        target_info={"app_dir": None}
    )
    # Check initial construction
    assert modal.task_type == "bake_pdf"
    assert modal.is_done is False


class DummyModalApp(App):
    def compose(self) -> ComposeResult:
        yield Button("Open", id="btn-open")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.push_screen(BakingModal(task_type="bake_pdf", target_info={"app_dir": None}))


@pytest.mark.anyio
async def test_baking_modal_in_app():
    app = DummyModalApp()
    async with app.run_test() as pilot:
        await pilot.click("#btn-open")
        modal = app.screen
        assert isinstance(modal, BakingModal)
        assert modal.query_one("#modal-stepper", BakeryStepper) is not None
        assert modal.query_one("#oven-widget", AnimatedOven) is not None
        modal.dismiss(None)
        await pilot.pause()
        assert not isinstance(app.screen, BakingModal)


def test_clean_error_message():
    from breadwinner.ui.retro import clean_error_message

    # Test 429 / Quota
    raw_429 = "Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information...', 'status': 'RESOURCE_EXHAUSTED'}}]"
    h_429, d_429 = clean_error_message(raw_429)
    assert "429" in h_429
    assert "You exceeded your current quota" in d_429
    assert "Change Model" in d_429

    # Test 404 / Retired
    raw_404 = "Error code: 404 - models/gemini-2.5-flash is not found for API version v1beta"
    h_404, d_404 = clean_error_message(raw_404)
    assert "404" in h_404
    assert "Change Model" in d_404

    # Test 401 / Auth
    raw_401 = "401 Unauthorized: API_KEY_INVALID"
    h_401, d_401 = clean_error_message(raw_401)
    assert "401" in h_401
    assert "API key" in d_401

    # Test generic fallback
    h_gen, d_gen = clean_error_message("RuntimeError: Internal arithmetic calculation failed")
    assert "Hearth Malfunction" in h_gen
    assert "Internal arithmetic calculation failed" in d_gen


def test_all_oven_frames_exact_cell_width():
    from rich.cells import cell_len
    from rich.text import Text

    all_frames = list(OVEN_FRAMES) + [OVEN_CELEBRATION_FRAME, OVEN_BURNT_FRAME]
    for idx, frame_str in enumerate(all_frames):
        for line_num, line in enumerate(frame_str.split("\n")):
            plain = Text.from_markup(line).plain
            width = cell_len(plain)
            assert width == 29, f"Frame {idx} line {line_num} width is {width} != 29: {plain!r}"


@pytest.mark.anyio
async def test_baking_modal_error_state_and_change_model():
    app = DummyModalApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.click("#btn-open")
        modal = app.screen
        assert isinstance(modal, BakingModal)

        # Trigger error screen with simulated 429
        modal._show_error_screen("Error code: 429 - [{'error': {'code': 429, 'message': 'Quota exceeded'}}]")
        await pilot.pause(0.1)

        # Verify stepper and gauge are hidden to save vertical space
        assert modal.query_one("#modal-stepper").display is False
        assert modal.query_one("#retro-progress-gauge").display is False

        # Verify status text is clean and doesn't repeat 429
        status_lbl = modal.query_one("#baking-status-text", Label)
        assert "Baking Halted — Hearth Malfunction" in str(status_lbl.render())
        assert "429" not in str(status_lbl.render())

        # Verify score card displays clean error
        card = modal.query_one("#baking-score-card")
        assert card.display is True
        assert "error-card" in card.classes

        score_title = modal.query_one("#score-card-title", Label)
        assert "429" in str(score_title.render())

        cancel_btn = modal.query_one("#btn-modal-cancel", Button)
        assert "Dismiss (Esc)" in cancel_btn.label.plain

        # Click change model button and verify dismiss action
        change_btn = modal.query_one("#btn-modal-change-model", Button)
        assert change_btn.display is True
        assert change_btn.label.plain == "Change Model"

        dismissed_payload = None
        orig_dismiss = modal.dismiss
        def mock_dismiss(result=None):
            nonlocal dismissed_payload
            dismissed_payload = result
            orig_dismiss(result)
        modal.dismiss = mock_dismiss

        change_btn.press()
        await pilot.pause(0.1)
        assert dismissed_payload.get("action") == "change_model"
        assert dismissed_payload.get("task_type") == "bake_pdf"

