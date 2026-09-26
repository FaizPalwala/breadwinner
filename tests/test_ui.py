"""Unit tests for Textual UI application."""

import pytest
from breadwinner.ui.app import BreadwinnerApp


@pytest.mark.anyio
async def test_breadwinner_app_mount():
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        assert app.title == "Breadwinner"
        assert app.query_one("#pipeline-table") is not None
        assert app.query_one("#select-persona") is not None
        assert app.query_one("#select-template") is not None
        assert app.query_one("#btn-strategy-loop") is not None
        assert app.query_one("#studio-mascot") is not None
        assert app.query_one("#studio-oven") is not None
        assert app.query_one("#studio-stepper") is not None
        assert app.query_one("#global-stepper") is not None

        # Verify stage synchronization
        app.set_global_stage(3)
        assert app.query_one("#global-stepper").current_stage == 3
        assert app.query_one("#studio-stepper").current_stage == 3


@pytest.mark.anyio
async def test_job_strategy_modal():
    from breadwinner.ui.app import JobStrategyModal
    from breadwinner.core.models import JobPosting
    from breadwinner.core.persona import PersonaManager

    job = JobPosting(
        id="job_modal_test",
        company="Datadog",
        title="Site Reliability Engineer",
        url="https://datadog.com/jobs/1",
        portal_type="greenhouse",
        raw_text="Observability and distributed systems scale."
    )
    base = PersonaManager.load_persona("tech_ai")
    questions = [
        {"id": "hook", "title": "Hook", "question": "Why Datadog?", "placeholder": "..."}
    ]

    modal = JobStrategyModal(job, questions, base)
    assert modal.job.company == "Datadog"
    assert len(modal.questions) == 1


@pytest.mark.anyio
async def test_breadwinner_app_first_run_prompts_ai_modal(tmp_path, monkeypatch):
    """Verify first launch with no .env pushes BakeryWelcomeModal in initial_step='ai' mode."""
    from breadwinner.ui.welcome import BakeryWelcomeModal
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, BakeryWelcomeModal)
        assert app.screen.initial_step == "ai"
        assert app.screen.query_one("#welcome-ai-step").styles.display == "block"


@pytest.mark.anyio
async def test_breadwinner_app_screen_guard_sentinel():
    from breadwinner.ui.screen_guard import ScreenGuardScreen
    app = BreadwinnerApp()
    async with app.run_test(size=(85, 26)) as pilot:
        assert not isinstance(app.screen, ScreenGuardScreen)

        # Shrink terminal below 76x22
        await pilot.resize_terminal(60, 18)
        assert isinstance(app.screen, ScreenGuardScreen)
        lbl = app.screen.query_one("#guard-dimensions-label")
        assert "60 cols × 18 rows" in str(lbl.render())

        # Expand terminal back above minimum threshold
        await pilot.resize_terminal(85, 26)
        assert not isinstance(app.screen, ScreenGuardScreen)


def test_try_expand_terminal(monkeypatch):
    import os
    from breadwinner.cli import try_expand_terminal

    written = []
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.write", lambda s: written.append(s))
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.delenv("VSCODE_PID", raising=False)
    monkeypatch.setattr("shutil.get_terminal_size", lambda fallback=(80, 24): os.terminal_size((70, 20)))

    try_expand_terminal(100, 30)
    assert any("\033[8;30;100t" in s for s in written)

    # In VS Code environment, it must NOT emit escape codes
    written.clear()
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    try_expand_terminal(100, 30)
    assert len(written) == 0



