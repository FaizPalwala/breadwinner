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
from textual.widgets import Button


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

