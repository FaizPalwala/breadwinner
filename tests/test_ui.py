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
        assert len(app.query("#global-stepper")) == 0

        # Verify stage synchronization
        app.set_global_stage(3)
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

    try_expand_terminal()
    assert any("\033[8;38;120t" in s for s in written)

    written.clear()
    try_expand_terminal(100, 30)
    assert any("\033[8;30;100t" in s for s in written)

    # In VS Code environment, it must NOT emit escape codes
    written.clear()
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    try_expand_terminal()
    assert len(written) == 0


@pytest.mark.anyio
async def test_pantry_interview_modal_adaptive_and_submission():
    from breadwinner.ui.app import PantryInterviewModal
    from textual.widgets import TextArea, Button

    questions = [
        {"id": "metric_gap_apex", "title": "Apex Scale", "prompt": "What was the QPS?", "placeholder": "..."},
        {"id": "target_roles", "title": "Target Roles", "prompt": "What roles?", "placeholder": "..."}
    ]

    modal = PantryInterviewModal(questions=questions)
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        await app.push_screen(modal)
        await pilot.pause()

        # Check that areas are rendered
        area1 = modal.query_one("#int-q-metric_gap_apex", TextArea)
        area2 = modal.query_one("#int-q-target_roles", TextArea)
        assert area1 is not None
        assert area2 is not None

        # Simulate typing an answer
        area1.text = "Scaled to 50,000 QPS with 99.99% uptime."
        area2.text = "Staff Distributed Systems Engineer."

        # Click save button
        btn_save = modal.query_one("#btn-save-interview", Button)
        await pilot.click(btn_save)
        await pilot.pause()


@pytest.mark.anyio
async def test_breadwinner_app_pipeline_empty_state_row():
    """Verify that when 0 jobs are tracked, the pipeline table shows a friendly retro placeholder instead of a black void."""
    from textual.widgets import DataTable
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()
        table = app.query_one("#pipeline-table", DataTable)
        assert table.row_count >= 1
        # Click the empty row
        await pilot.click("#pipeline-table")
        await pilot.pause()
        assert app.selected_job is None


@pytest.mark.anyio
async def test_breadwinner_app_ingest_baking_modal_and_auto_interview(monkeypatch, tmp_path):
    """Verify welcome modal import launches BakingModal, switches to Pantry tab, and pushes PantryInterviewModal."""
    from textual.widgets import TabbedContent
    from breadwinner.ui.retro import BakingModal
    from breadwinner.ui.app import PantryInterviewModal
    from breadwinner.core.models import CandidateProfile, WorkExperience, SkillCategory
    from breadwinner.core.ingestor import UniversalIngestor

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")

    fake_profile = CandidateProfile(
        full_name="Grace Hopper",
        title="Rear Admiral / Compiler Inventor",
        email="hopper@navy.mil",
        experiences=[
            WorkExperience(
                company="US Navy",
                role="Director of Systems Programming",
                start_date="1943",
                end_date="1986",
                bullets=["Invented first A-0 compiler and coined debugging."]
            )
        ],
        projects=[],
        skills=[SkillCategory(category="Languages", skills=["COBOL", "Machine Code"])]
    )

    monkeypatch.setattr(UniversalIngestor, "ingest", lambda *args, **kwargs: fake_profile)

    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        # Dismiss any welcome modal if present
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # Simulate welcome modal import action
        app._on_welcome_modal_dismissed({
            "action": "import",
            "sources": ["https://grace.hopper.dev"]
        })
        await pilot.pause(0.2)

        # Ingest discovery modal is pushed first (ADR-002 Stage 3)
        from breadwinner.ui.discovery import IngredientDiscoveryModal
        assert isinstance(app.screen, IngredientDiscoveryModal)

        # User submits selected ingredients
        app.screen.action_submit()
        await pilot.pause(0.2)

        # BakingModal is now active
        assert isinstance(app.screen, BakingModal)
        assert app.screen.task_type == "ingest"

        # Simulate completion
        baking_res = {
            "success": True,
            "profile": fake_profile,
            "sources": ["https://grace.hopper.dev"],
            "is_multi": False
        }
        app.pop_screen()
        await pilot.pause()

        # Call the dismissal callback
        app._on_ingest_baking_modal_dismissed(baking_res)
        await pilot.pause()

        # Verify active tab switched to tab-profile
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-profile"

        # Verify PantryInterviewModal was automatically pushed!
        assert isinstance(app.screen, PantryInterviewModal)


@pytest.mark.anyio
async def test_breadwinner_app_model_quick_switcher_modal():
    from breadwinner.ui.app import ModelQuickSwitcherModal
    from textual.widgets import OptionList, Input
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, ModelQuickSwitcherModal)
        search_inp = app.screen.query_one("#switcher-search", Input)
        assert search_inp is not None
        opt_list = app.screen.query_one("#switcher-list", OptionList)
        assert opt_list is not None
        initial_count = opt_list.option_count
        assert initial_count > 0

        # Test search filtering
        await pilot.press(*list("claude"))
        await pilot.pause()
        assert opt_list.option_count > 0
        assert opt_list.option_count < initial_count

        # Test escape closes modal
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ModelQuickSwitcherModal)

        # Test 1-keystroke quick pick
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, ModelQuickSwitcherModal)
        await pilot.press("1")
        await pilot.pause()
        assert not isinstance(app.screen, ModelQuickSwitcherModal)


@pytest.mark.anyio
async def test_breadwinner_app_pipeline_notes_and_status_cycle():
    from breadwinner.db.repository import JobRecord
    from datetime import datetime, timezone
    from textual.widgets import TextArea
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()
        job = JobRecord(
            id="job_cycle_test",
            company="Stripe",
            title="Infrastructure Engineer",
            url="https://stripe.com/jobs/1",
            status="target",
            notes="Initial inquiry",
            date_added=datetime.now(timezone.utc).isoformat()
        )
        app.repo.upsert_job(job)
        app.load_pipeline_table()
        await pilot.pause()

        # Select the job
        app.selected_job = job
        app.update_details_pane()
        await pilot.pause()

        # Check notes text
        notes_widget = app.query_one("#input-job-notes", TextArea)
        assert notes_widget.text == "Initial inquiry"

        # Update notes and save
        notes_widget.text = "Reached out on LinkedIn"
        app.action_save_notes()
        await pilot.pause()
        reloaded = app.repo.get_job("job_cycle_test")
        assert reloaded.notes == "Reached out on LinkedIn"

        # Cycle status
        app.action_change_status()
        assert app.selected_job.status == "tailored"
        app.action_change_status()
        assert app.selected_job.status == "applied"


@pytest.mark.anyio
async def test_breadwinner_app_living_studio_lab_and_xyz_validation():
    from textual.widgets import TextArea, Markdown
    from breadwinner.ui.editor import XYZValidatorWidget
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        app.action_view_lab()
        await pilot.pause()
        assert app.query_one("#studio-lab-view").styles.display == "block"
        assert app.query_one("#studio-formulation-view").styles.display == "none"

        editor = app.query_one("#lab-bullet-editor", TextArea)
        editor.text = "- Scaled distributed Redis cache to 50,000 QPS with 99.99% uptime reducing p99 latency by 35%."
        await pilot.pause(0.2)

        validator = app.query_one("#lab-xyz-validator", XYZValidatorWidget)
        assert validator is not None
        assert validator.latest_report.quantified_bullets >= 1
        assert validator.latest_report.action_verbs_count >= 1

        # Test format XYZ
        app.action_format_lab_xyz()
        assert any(editor.text.lstrip("- ").startswith(v) for v in ["Architected", "Engineered", "Spearheaded", "Optimized", "Scaled", "Deployed"])

        # Test column stacking toggle
        lab_split = app.query_one("#studio-lab-split")
        assert not lab_split.has_class("-vertical-stack")
        app.action_toggle_lab_stack()
        await pilot.pause()
        assert lab_split.has_class("-vertical-stack")
        app.action_toggle_lab_stack()
        await pilot.pause()
        assert not lab_split.has_class("-vertical-stack")

        # Test editable resume textarea
        resume_editor = app.query_one("#lab-resume-editor", TextArea)
        assert resume_editor is not None
        resume_editor.text = "# Custom Edited Resume\n- Bullet 1"
        assert "Custom Edited Resume" in resume_editor.text

        # Test toggle preview
        preview_md = app.query_one("#preview-resume-md", Markdown)
        assert preview_md.styles.display == "none"
        app.action_toggle_resume_preview()
        await pilot.pause()
        assert preview_md.styles.display == "block"
        assert resume_editor.styles.display == "none"
        app.action_toggle_resume_preview()
        await pilot.pause()
        assert preview_md.styles.display == "none"
        assert resume_editor.styles.display == "block"


@pytest.mark.anyio
async def test_breadwinner_app_pantry_ide_file_navigation(tmp_path, monkeypatch):
    from textual.widgets import TextArea, TabbedContent
    monkeypatch.chdir(tmp_path)
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # Switch to pantry tab
        app.action_tab_profile()
        await pilot.pause()
        assert app.query_one("#main-tabs", TabbedContent).active == "tab-profile"

        # Check default profile file
        editor = app.query_one("#pantry-editor-textarea", TextArea)
        assert editor.language in ("yaml", "json", "markdown")

        # Load context
        app.load_pantry_file("context")
        await pilot.pause()
        assert editor.language == "markdown"

        # Load profile
        app.load_pantry_file("profile")
        await pilot.pause()
        assert editor.language in ("yaml", "json")


@pytest.mark.anyio
async def test_breadwinner_app_adaptive_layout_and_vertical_blade(tmp_path, monkeypatch):
    """Verify sidebar collapsing, VerticalEngineBlade display, and 3-preset cycling."""
    from breadwinner.ui.app import VerticalEngineBlade
    from textual.containers import Vertical
    monkeypatch.chdir(tmp_path)
    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        sidebar = app.query_one("#app-sidebar", Vertical)
        blade = app.query_one("#blade-sidebar-engine", VerticalEngineBlade)
        top_pills = app.query_one("#top-bar-nav-pills")
        pipe_container = app.query_one("#pipeline-container")

        # Initial state: Normal layout
        assert app.layout_preset == "normal"
        assert not sidebar.has_class("-collapsed")
        assert sidebar.styles.display != "none"
        assert top_pills.styles.display == "none"

        # Toggle sidebar collapse
        app.action_toggle_sidebar()
        await pilot.pause()
        assert sidebar.has_class("-collapsed")
        assert app.sidebar_collapsed is True

        # Test blade rendering and provider update
        blade.update_provider("DEEPSEEK")
        assert blade.blade_text == "DSEEK"

        # Toggle back to expanded
        app.action_toggle_sidebar()
        await pilot.pause()
        assert not sidebar.has_class("-collapsed")

        lab_split = app.query_one("#studio-lab-split")

        # Cycle to Split view preset
        app.action_cycle_preset()
        await pilot.pause()
        assert app.layout_preset == "split"
        assert sidebar.styles.display == "none"
        assert top_pills.styles.display == "block"
        assert pipe_container.has_class("-vertical-stack")
        assert lab_split.has_class("-vertical-stack")

        # Cycle to Full view preset
        app.action_cycle_preset()
        await pilot.pause()
        assert app.layout_preset == "full"
        assert sidebar.styles.display != "none"
        assert not pipe_container.has_class("-vertical-stack")
        assert not lab_split.has_class("-vertical-stack")

        # Cycle back to Normal view preset
        app.action_cycle_preset()
        await pilot.pause()
        assert app.layout_preset == "normal"
        assert sidebar.styles.display != "none"
        assert not pipe_container.has_class("-vertical-stack")
        assert not lab_split.has_class("-vertical-stack")


@pytest.mark.anyio
async def test_breadwinner_app_settings_modal(tmp_path, monkeypatch):
    from breadwinner.ui.app import BakerySettingsModal
    from textual.widgets import Select, Button
    import breadwinner.config as conf

    env_file = tmp_path / ".env"
    monkeypatch.setattr("breadwinner.config.get_env_path", lambda: env_file)

    app = BreadwinnerApp()
    async with app.run_test(size=(120, 36)) as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # Trigger settings via sidebar button
        await pilot.click("#btn-sidebar-settings")
        await pilot.pause()

        assert isinstance(app.screen, BakerySettingsModal)
        modal = app.screen
        assert modal.query_one("#settings-dialog") is not None
        assert modal.query_one("#settings-select-template") is not None
        assert modal.query_one("#settings-select-persona") is not None

        # Change template to modern and save
        tmpl_sel = modal.query_one("#settings-select-template", Select)
        tmpl_sel.value = "modern"
        await pilot.click("#btn-settings-save")
        await pilot.pause()

        assert not isinstance(app.screen, BakerySettingsModal)
        assert conf.settings.default_template == "modern"

