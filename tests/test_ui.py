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
        assert app.query_one("#studio-stepper") is not None


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

