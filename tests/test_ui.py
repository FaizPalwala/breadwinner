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


@pytest.mark.anyio
async def test_breadwinner_app_error_change_model_auto_retries():
    from breadwinner.ui.app import ModelQuickSwitcherModal
    from breadwinner.ui.retro import BakingModal

    app = BreadwinnerApp()
    async with app.run_test(size=(120, 36)) as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        pushed_screens = []
        orig_push_screen = app.push_screen
        def tracking_push_screen(screen, callback=None):
            pushed_screens.append(screen)
            return orig_push_screen(screen, callback)
        app.push_screen = tracking_push_screen

        # Simulate ingest modal dismissing with change_model
        app._on_ingest_baking_modal_dismissed({
            "action": "change_model",
            "target_info": {"sources": ["test_source.pdf"], "pantry": app.pantry}
        })
        await pilot.pause(0.1)

        # Quick switcher modal should be active and retry recorded
        assert isinstance(app.screen, ModelQuickSwitcherModal)
        assert app._pending_bake_retry is not None
        assert app._pending_bake_retry["task_type"] == "ingest"

        # Simulate selecting a new model in the switcher
        app._on_model_switched({"provider": "gemini", "model": "gemini-2.5-flash"})
        await pilot.pause(0.1)

        # Pending retry should be cleared and BakingModal should have been re-pushed
        assert app._pending_bake_retry is None
        assert any(isinstance(s, BakingModal) for s in pushed_screens)
        if isinstance(app.screen, BakingModal):
            app.screen.dismiss(None)


@pytest.mark.anyio
async def test_model_quick_switcher_unconfigured_provider_routes_to_welcome_with_sources():
    from breadwinner.ui.welcome import BakeryWelcomeModal
    from breadwinner.ui.app import ModelQuickSwitcherModal

    app = BreadwinnerApp()
    async with app.run_test(size=(120, 36)) as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        pushed_screens = []
        orig_push_screen = app.push_screen
        def tracking_push_screen(screen, callback=None):
            pushed_screens.append(screen)
            return orig_push_screen(screen, callback)
        app.push_screen = tracking_push_screen

        # Set up a pending bake retry with staged sources
        app._pending_bake_retry = {
            "task_type": "ingest",
            "target_info": {"sources": ["https://faizpalwala.tech"], "pantry": app.pantry}
        }

        # Simulate selecting an unconfigured provider (deepseek) from the switcher
        app._on_model_switched({"action": "setup_provider", "provider": "deepseek"})
        await pilot.pause(0.1)

        # BakeryWelcomeModal should have been pushed with initial_step="ai", initial_provider="deepseek", and preserved sources
        welcome_modals = [s for s in pushed_screens if isinstance(s, BakeryWelcomeModal)]
        assert len(welcome_modals) == 1
        wm = welcome_modals[0]
        assert wm.initial_step == "ai"
        assert wm.active_provider == "deepseek"
        assert wm.staged_ingredients == ["https://faizpalwala.tech"]


@pytest.mark.anyio
async def test_tailor_studio_and_pantry_ui_enhancements(monkeypatch):
    from textual.widgets import Button, Input, TextArea

    class MockProvider:
        def generate_text(self, sys_prompt, user_prompt, temperature=0.1):
            return "- Architected high-throughput Go microservices scaling to 50,000 QPS with p99 < 5ms."

    monkeypatch.setattr("breadwinner.ui.app.get_llm_provider", lambda: MockProvider())

    app = BreadwinnerApp()
    async with app.run_test(size=(100, 35)) as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # 1. Preset cycling check
        cycle_btn = app.query_one("#btn-app-cycle-preset", Button)
        assert str(cycle_btn.label) == "⛶ Normal"

        app.action_cycle_preset()
        await pilot.pause()
        assert str(cycle_btn.label) == "⛶ Split"

        app.action_cycle_preset()
        await pilot.pause()
        assert str(cycle_btn.label) == "⛶ Full"

        app.action_cycle_preset()
        await pilot.pause()
        assert str(cycle_btn.label) == "⛶ Normal"

        # 2. Studio Lab view & folder button check
        app.action_view_lab()
        await pilot.pause()
        folder_btn = app.query_one("#btn-lab-folder", Button)
        assert str(folder_btn.label) == "↗ Folder"
        assert len(app.query("#lab-refine-prompt-label")) == 0
        assert app.query_one("#lab-refine-prompt", TextArea) is not None

        # 3. Pantry IDE prompt box
        app.action_tab_profile()
        await pilot.pause()
        assert app.query_one("#pantry-prompt-box") is not None
        assert app.query_one("#pantry-ai-prompt", TextArea) is not None

        # 4. Global hotkeys: "o" is preserved in app.BINDINGS
        bindings_keys = [b.key for b in app.BINDINGS]
        assert "o" in bindings_keys

        # 5. Right-hand preview is scrollable and focusable
        from breadwinner.ui.editor import ScrollableMarkdown
        preview_md = app.query_one("#preview-resume-md", ScrollableMarkdown)
        assert preview_md is not None
        assert preview_md.can_focus is True
        assert preview_md.styles.overflow_y == "auto"

        # 6. Verify functional scrolling in resume preview
        app.action_tab_studio()
        await pilot.pause()
        app.action_view_lab()
        await pilot.pause()
        r_editor = app.query_one("#lab-resume-editor")
        r_editor.text = "# Full Resume\n\n" + "\n\n".join(f"- Bullet point achievement line {i}" for i in range(80))
        app.action_toggle_resume_preview()
        await pilot.pause()
        assert preview_md.styles.display == "block"
        assert preview_md.has_focus is True
        assert preview_md.is_scrollable is True
        assert preview_md.max_scroll_y > 0
        preview_md.scroll_page_down(animate=False)
        await pilot.pause()
        assert preview_md.scroll_y > 0

        # 7. Verify multiline PromptTextArea in Studio and Pantry with Ctrl+Enter triggers
        studio_prompt = app.query_one("#lab-refine-prompt", TextArea)
        studio_prompt.text = "Emphasize high-throughput Go microservices"
        studio_prompt.focus()
        await pilot.pause()
        await pilot.press("ctrl+j")
        await pilot.pause(0.2)
        from breadwinner.ui.app import DiffModal
        assert isinstance(app.screen, DiffModal)
        app.pop_screen()
        await pilot.pause()

        app.action_tab_profile()
        await pilot.pause()
        pantry_prompt = app.query_one("#pantry-ai-prompt", TextArea)
        pantry_prompt.text = "Add Go and Kubernetes expertise"
        pantry_prompt.focus()
        await pilot.pause()
        assert pantry_prompt.text == "Add Go and Kubernetes expertise"


@pytest.mark.anyio
async def test_breadwinner_app_pipeline_open_studio_and_folder_resolution(tmp_path, monkeypatch):
    from breadwinner.db.repository import JobRecord
    from textual.widgets import TabbedContent, TextArea, Markdown, Label
    import subprocess

    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # Set up a fake tailored app folder
        test_app_dir = tmp_path / "2026-10-12_Acme_LeadEngineer"
        test_app_dir.mkdir(parents=True, exist_ok=True)
        (test_app_dir / "resume.md").write_text("# Acme Resume\n\n- Engineered distributed pipeline scaling to 10M events/sec.\n", encoding="utf-8")
        (test_app_dir / "cover_letter.md").write_text("Dear Hiring Team at Acme,\n\nI am thrilled...", encoding="utf-8")
        (test_app_dir / "portal_answers.md").write_text("Q: Notice period?\nA: Immediate", encoding="utf-8")

        job = JobRecord(
            id="acme_lead",
            company="Acme Corp",
            title="Lead Engineer",
            url="https://acme.com/jobs/1",
            status="tailored",
            match_score=94,
            folder_path=str(test_app_dir),
            date_added="2026-10-12"
        )
        app.repo.upsert_job(job)
        app.load_pipeline_table()
        await pilot.pause()

        # 1. Verify auto-selection of first job on table load
        assert app.selected_job is not None
        assert app.selected_job.id == "acme_lead"

        # 2. Verify on_data_table_row_highlighted
        class FakeRowKey:
            value = "acme_lead"
        class FakeHighlightedEvent:
            row_key = FakeRowKey()
        app.on_data_table_row_highlighted(FakeHighlightedEvent())
        assert app.selected_job.id == "acme_lead"

        # 3. Action pipeline edit studio
        app.action_pipeline_edit_studio()
        await pilot.pause()

        # Tab should be studio
        tabs = app.query_one("#main-tabs", TabbedContent)
        assert tabs.active == "tab-studio"

        # Bullet lab view should be visible
        lab_view = app.query_one("#studio-lab-view")
        assert lab_view.styles.display == "block"

        # Active job label and ATS badge should be populated
        job_label = app.query_one("#lab-active-job-label", Label)
        assert "Acme Corp" in str(job_label.render())
        ats_badge = app.query_one("#lab-ats-badge", Label)
        assert "94% ATS Match" in str(ats_badge.render())

        # Editors and previews populated
        resume_preview = app.query_one("#preview-resume-md", Markdown)
        assert "Acme Resume" in str(resume_preview.source)
        resume_editor = app.query_one("#lab-resume-editor", TextArea)
        assert "Acme Resume" in resume_editor.text
        bullet_editor = app.query_one("#lab-bullet-editor", TextArea)
        assert "Engineered distributed pipeline" in bullet_editor.text
        letter_editor = app.query_one("#lab-letter-editor", TextArea)
        assert "Dear Hiring Team at Acme" in letter_editor.text

        # 4. Open folder action resolves properly
        opened_cmds = []
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: opened_cmds.append(cmd))
        app.action_open_folder()
        assert len(opened_cmds) == 1
        assert opened_cmds[0] == ["open", str(test_app_dir)]


@pytest.mark.anyio
async def test_breadwinner_app_studio_refine_engine_and_diff_accept(monkeypatch):
    from textual.widgets import TextArea, Static
    from breadwinner.ui.editor import XYZValidatorWidget

    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        app.action_view_lab()
        await pilot.pause()

        # Set initial bullets
        editor = app.query_one("#lab-bullet-editor", TextArea)
        editor.text = "- Worked on database queries."
        prompt_area = app.query_one("#lab-refine-prompt", TextArea)
        prompt_area.text = "Quantify performance improvement using Google XYZ format"

        # Mock LLM provider to return realistic refined bullet
        class MockProvider:
            def generate_text(self, sys_prompt, user_prompt, temperature=0.1):
                return "- Optimized distributed PostgreSQL queries scaling throughput by 45% with p99 < 8ms."

        monkeypatch.setattr("breadwinner.ui.app.get_llm_provider", lambda: MockProvider())

        # Trigger refine diff
        app.action_lab_refine_diff()
        await pilot.pause(0.2)

        # DiffModal should be visible on top of screen stack
        from breadwinner.ui.app import DiffModal
        from textual.widgets import Button
        assert isinstance(app.screen, DiffModal)
        modal = app.screen
        diff_body = modal.query_one("#diff-modal-body", Static)
        diff_str = str(diff_body.render())
        assert "Optimized distributed PostgreSQL queries" in diff_str

        # Accept diff via modal button
        btn_accept = modal.query_one("#btn-diff-modal-accept", Button)
        await pilot.click(btn_accept)
        await pilot.pause()

        assert not isinstance(app.screen, DiffModal)
        assert "Optimized distributed PostgreSQL queries" in editor.text

        # Verify XYZ validator was immediately refreshed
        validator = app.query_one("#lab-xyz-validator", XYZValidatorWidget)
        assert validator.latest_report is not None
        assert validator.latest_report.quantified_bullets >= 1


@pytest.mark.anyio
async def test_breadwinner_app_pipeline_reload_scopes_bullets_preventing_dilution(tmp_path):
    from breadwinner.db.repository import JobRecord
    from textual.widgets import TextArea
    from breadwinner.ui.editor import XYZValidatorWidget

    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        # Set up a tailored app folder with markdown containing experience, education, skills, and coursework
        test_dir = tmp_path / "2026-10-12_Dilution_Test"
        test_dir.mkdir(parents=True, exist_ok=True)
        resume_md = (
            "# Jane Doe\n\n"
            "## EXPERIENCE\n"
            "- Architected real-time streaming pipeline processing 100,000 events/sec with 99.99% reliability.\n\n"
            "## EDUCATION\n"
            "- Master of Science in Computer Science\n\n"
            "## SKILLS\n"
            "- Python, Go, Kafka, Redis, Docker, Kubernetes\n\n"
            "## COURSEWORK\n"
            "- Distributed Systems, Advanced Algorithms\n"
        )
        (test_dir / "resume.md").write_text(resume_md, encoding="utf-8")

        job = JobRecord(
            id="dilution_test_job",
            company="Fintech Co",
            title="Senior Platform Engineer",
            url="https://fintech.example/jobs/1",
            status="tailored",
            match_score=95,
            folder_path=str(test_dir),
            date_added="2026-10-12"
        )
        app.repo.upsert_job(job)
        app.load_pipeline_table()
        await pilot.pause()

        # Load into studio
        app.action_pipeline_edit_studio()
        await pilot.pause()

        # Bullet editor should strictly contain the 1 experience bullet
        editor = app.query_one("#lab-bullet-editor", TextArea)
        lines = [l.strip() for l in editor.text.splitlines() if l.strip().startswith(("-", "*", "•"))]
        assert len(lines) == 1
        assert "Architected real-time streaming pipeline" in lines[0]
        assert not any("Python, Go" in l for l in lines)
        assert not any("Master of Science" in l for l in lines)

        # Validator should have 100% quantified score (1/1) instead of diluted (1/4 = 25%)
        validator = app.query_one("#lab-xyz-validator", XYZValidatorWidget)
        assert validator.latest_report is not None
        assert validator.latest_report.total_bullets == 1
        assert validator.latest_report.quantified_score == 100


def test_ml_linter_action_verbs_and_metrics():
    from breadwinner.ui.editor import analyze_bullets_xyz

    sample_bullets = (
        "- Fine-tuned 70b parameter LLM across 500 gpu-hours achieving 0.94 f1 score on benchmark suite.\n"
        "- Quantized transformer models into 4-bit weights reducing latency by 45% with 75,000 daily requests.\n"
        "- Benchmarked distributed inference clusters sustaining 1,200 QPS with p99 < 15ms.\n"
        "- Evaluated retrieval pipelines improving precision to 0.88 across 10,000 test cases.\n"
        "- Curated 250,000 multimodal training samples for domain adaptation."
    )

    report = analyze_bullets_xyz(sample_bullets)
    assert report.total_bullets == 5
    assert report.action_verbs_count == 5
    assert report.quantified_bullets == 5
    assert report.quantified_score == 100


@pytest.mark.anyio
async def test_studio_bidirectional_sync_markdown_html_and_pdf(tmp_path):
    """Verify editing resume.md in Studio updates #lab-bullet-editor, gauges, resume.html, and resume.pdf."""
    from pathlib import Path
    from breadwinner.db.repository import JobRecord
    from textual.widgets import TextArea
    from unittest.mock import patch

    app = BreadwinnerApp()
    async with app.run_test() as pilot:
        if len(app._screen_stack) > 1:
            app.pop_screen()
            await pilot.pause()

        test_dir = tmp_path / "2026-10-13_Sync_Test"
        test_dir.mkdir(parents=True, exist_ok=True)
        initial_resume_md = (
            "# Alice Walker\n\n"
            "## EXPERIENCE\n\n"
            "### Principal Engineer @ Anthropic\n"
            "- Trained frontier reasoning model over 10,000 GPU-hours.\n"
        )
        (test_dir / "resume.md").write_text(initial_resume_md, encoding="utf-8")
        (test_dir / "cover_letter.md").write_text("Dear Hiring Team,\n\nExcited to apply.", encoding="utf-8")

        resume_json = {
            "basics": {"name": "Alice Walker", "email": "alice@example.com"},
            "work": [{"name": "Anthropic", "position": "Principal Engineer", "highlights": ["Trained frontier reasoning model over 10,000 GPU-hours."]}]
        }
        import json
        (test_dir / "resume.json").write_text(json.dumps(resume_json), encoding="utf-8")

        job = JobRecord(
            id="sync_test_job",
            company="Anthropic",
            title="Principal Engineer",
            url="https://anthropic.com/jobs/1",
            status="tailored",
            match_score=96,
            folder_path=str(test_dir),
            date_added="2026-10-13"
        )
        app.repo.upsert_job(job)
        app.load_pipeline_table()
        await pilot.pause()

        # 1. Load job into studio
        app.action_pipeline_edit_studio()
        await pilot.pause()

        # 2. Edit resume.md in #lab-resume-editor
        r_editor = app.query_one("#lab-resume-editor", TextArea)
        new_resume_md = (
            "# Alice Walker\n\n"
            "## EXPERIENCE\n\n"
            "### Principal Engineer @ Anthropic\n"
            "- Quantized multimodal transformer models reducing latency by 50% with 25,000 QPS.\n"
            "- Benchmarked inference engine achieving 99.9% uptime across 1,000 nodes.\n"
        )
        r_editor.text = new_resume_md

        # Mock render_html_to_pdf
        pdf_baked = []
        def fake_render_pdf(src, dst, **kwargs):
            pdf_baked.append((Path(src).name, Path(dst).name))
            Path(dst).write_bytes(b"%PDF-1.4 Mock PDF bytes" * 100)
            return Path(dst)

        with patch("breadwinner.ui.app.render_html_to_pdf", side_effect=fake_render_pdf):
            # Save resume (Ctrl+S / action_save_lab_resume)
            app.action_save_lab_resume()
            await pilot.pause()

            # Verify #lab-bullet-editor received the updated bullets
            bullet_editor = app.query_one("#lab-bullet-editor", TextArea)
            assert "Quantized multimodal transformer models" in bullet_editor.text
            assert "Benchmarked inference engine" in bullet_editor.text

            # Verify resume.html was regenerated with updated text
            html_txt = (test_dir / "resume.html").read_text(encoding="utf-8")
            assert "Quantized multimodal transformer models" in html_txt
            assert "Benchmarked inference engine" in html_txt

            # Verify resume.pdf was compiled
            assert ("resume.html", "resume.pdf") in pdf_baked
            assert (test_dir / "resume.pdf").exists()

            # Verify cover letter save re-bakes cover_letter.pdf
            l_editor = app.query_one("#lab-letter-editor", TextArea)
            l_editor.text = "Dear Anthropic,\n\nI love Claude and constitutional AI."
            app.action_save_lab_letter()
            await pilot.pause()

            assert (test_dir / "cover_letter.html").exists()
            assert ("cover_letter.html", "cover_letter.pdf") in pdf_baked
            assert (test_dir / "cover_letter.pdf").exists()
