"""Breadbox application tracking and pipeline screen module."""

from typing import Optional, List, Dict, Any
from pathlib import Path
import shutil
import subprocess

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Label,
    Button,
    DataTable,
    TextArea,
    Static,
    TabPane,
    RadioSet,
    RadioButton,
    Select,
)

from breadwinner.config import settings
from breadwinner.db.repository import JobRepository, JobRecord
from breadwinner.db.sync import CsvSync
from breadwinner.core.persona import PersonaManager
from breadwinner.ui.visuals import PipelineFunnelWidget
from breadwinner.ui.retro import BakingModal


MODAL_BASE_CSS = """
    .modal-header-bar {
        height: 1;
        width: 100%;
        align: left middle;
        margin-bottom: 1;
    }
    .modal-header-title {
        width: 1fr;
        color: #ffb86c;
        text-style: bold;
    }
    Button.modal-close-btn, .modal-close-btn,
    #btn-switcher-close, #btn-settings-close, #btn-strategy-close,
    #btn-modal-close, #btn-ingest-close, #btn-interview-close,
    #btn-history-close, #btn-status-close, #btn-flag-close, #btn-close-persona-synth {
        dock: right;
        min-width: 3;
        width: 3;
        height: 1;
        border: none;
        background: transparent;
        color: #6272a4;
        padding: 0;
    }
    Button.modal-close-btn:focus, .modal-close-btn:focus,
    #btn-switcher-close:focus, #btn-settings-close:focus, #btn-strategy-close:focus,
    #btn-modal-close:focus, #btn-ingest-close:focus, #btn-interview-close:focus,
    #btn-history-close:focus, #btn-status-close:focus, #btn-flag-close:focus, #btn-close-persona-synth:focus {
        background: transparent;
        color: #6272a4;
        border: none;
        text-style: none;
    }
    Button.modal-close-btn:hover, .modal-close-btn:hover,
    #btn-switcher-close:hover, #btn-settings-close:hover, #btn-strategy-close:hover,
    #btn-modal-close:hover, #btn-ingest-close:hover, #btn-interview-close:hover,
    #btn-history-close:hover, #btn-status-close:hover, #btn-flag-close:hover, #btn-close-persona-synth:hover {
        background: transparent;
        color: #ff5555;
        border: none;
        text-style: bold;
    }
    .modal-action-bar {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    .modal-action-bar Button {
        margin-left: 1;
    }
"""


class StatusModal(ModalScreen):
    """Modal screen for updating job status."""

    DEFAULT_CSS = """
    StatusModal {
        align: center middle;
    }
    #status-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 50;
        max-width: 54;
        min-width: 44;
        height: auto;
        max-height: 18;
    }
    #status-radios {
        height: auto;
        border: none;
        background: transparent;
        padding: 0;
        margin-bottom: 1;
    }
    """ + MODAL_BASE_CSS

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label(f"[bold]Update Status for {self.job.company}:[/bold]", classes="modal-header-title"),
                Button("✕", id="btn-status-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
            RadioSet(
                RadioButton("Target", value=self.job.status == "target", id="rb-target"),
                RadioButton("Tailored", value=self.job.status == "tailored", id="rb-tailored"),
                RadioButton("Applied", value=self.job.status == "applied", id="rb-applied"),
                RadioButton("Interviewing", value=self.job.status == "interviewing", id="rb-interviewing"),
                RadioButton("Offer", value=self.job.status == "offer", id="rb-offer"),
                RadioButton("Rejected", value=self.job.status == "rejected", id="rb-rejected"),
                RadioButton("Archived", value=self.job.status == "archived", id="rb-archived"),
                id="status-radios"
            ),
            Horizontal(
                Button("Save", variant="success", id="btn-save-status"),
                Button("Cancel", variant="error", id="btn-cancel-status"),
                classes="modal-action-bar"
            ),
            id="status-dialog"
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#status-radios", RadioSet).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-cancel-status", "btn-status-close"):
            self.dismiss(False)
            return

        if event.button.id == "btn-save-status":
            radios = self.query_one("#status-radios", RadioSet)
            selected_rb = radios.pressed_button
            if selected_rb:
                new_status = selected_rb.label.plain.lower()
                self.repo.update_status(self.job.id, new_status)
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.dismiss(True)
        else:
            self.dismiss(False)


class FlagModal(ModalScreen):
    """Modal screen for toggling custom flags."""

    DEFAULT_CSS = """
    FlagModal {
        align: center middle;
    }
    #flag-dialog {
        padding: 1 2;
        background: #10141f;
        border: heavy #d4a373;
        width: 50;
        max-width: 54;
        min-width: 44;
        height: auto;
        max-height: 16;
    }
    #flag-radios {
        height: auto;
        border: none;
        background: transparent;
        padding: 0;
        margin-bottom: 1;
    }
    """ + MODAL_BASE_CSS

    def __init__(self, job: JobRecord, repo: JobRepository):
        super().__init__()
        self.job = job
        self.repo = repo

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Label(f"[bold]Set Flag for {self.job.company}:[/bold]", classes="modal-header-title"),
                Button("✕", id="btn-flag-close", classes="modal-close-btn"),
                classes="modal-header-bar"
            ),
            RadioSet(
                RadioButton("None (Clear Flag)", value=self.job.flag is None, id="flag-none"),
                RadioButton("High Priority", value=self.job.flag == "high_priority", id="flag-high"),
                RadioButton("Follow-up Needed", value=self.job.flag == "followup_needed", id="flag-follow"),
                RadioButton("Link Broken", value=self.job.flag == "link_broken", id="flag-broken"),
                id="flag-radios"
            ),
            Horizontal(
                Button("Save", variant="success", id="btn-save-flag"),
                Button("Cancel", variant="error", id="btn-cancel-flag"),
                classes="modal-action-bar"
            ),
            id="flag-dialog"
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#flag-radios", RadioSet).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-cancel-flag", "btn-flag-close"):
            self.dismiss(False)
            return

        if event.button.id == "btn-save-flag":
            radios = self.query_one("#flag-radios", RadioSet)
            selected_rb = radios.pressed_button
            if selected_rb:
                val = selected_rb.label.plain.lower()
                flag_map = {
                    "none (clear flag)": None,
                    "high priority": "high_priority",
                    "follow-up needed": "followup_needed",
                    "link broken": "link_broken"
                }
                new_flag = flag_map.get(val)
                self.repo.set_flag(self.job.id, new_flag)
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.dismiss(True)


class DeleteJobModal(ModalScreen[bool]):
    """Modal screen for confirming permanent application deletion."""

    BINDINGS = [
        Binding("escape", "dismiss_cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    DeleteJobModal {
        align: center middle;
    }
    #delete-dialog {
        padding: 1 2;
        background: #18111B;
        border: heavy #FF5555;
        width: 56;
        max-width: 62;
        height: auto;
    }
    #delete-title {
        color: #FF5555;
        text-style: bold;
        margin-bottom: 1;
    }
    #delete-warning-text {
        color: #F8F8F2;
        margin-bottom: 1;
    }
    #delete-folder-text {
        color: #A89F91;
        margin-bottom: 1;
    }
    #delete-action-row {
        height: 3;
        align: right middle;
    }
    #delete-action-row Button {
        margin-left: 1;
    }
    """

    def __init__(self, job: JobRecord):
        super().__init__()
        self.job = job

    def compose(self) -> ComposeResult:
        with Vertical(id="delete-dialog"):
            yield Label("[!] PERMANENT APPLICATION DELETION", id="delete-title")
            yield Label(
                f"Are you sure you want to delete [bold white]{self.job.title}[/bold white] at [bold #FFB86C]{self.job.company}[/bold #FFB86C]?",
                id="delete-warning-text"
            )
            folder_str = self.job.folder_path or f"output/{self.job.id}"
            yield Label(f"This will permanently delete tracked data and application folder:\n[dim]{folder_str}[/dim]", id="delete-folder-text")
            with Horizontal(id="delete-action-row"):
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel-delete")
                yield Button("✕ Delete Application", variant="error", id="btn-confirm-delete")

    def on_mount(self) -> None:
        try:
            self.query_one("#btn-cancel-delete", Button).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm-delete":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss_cancel(self) -> None:
        self.dismiss(False)


class BreadboxScreenMixin:
    """Mixin providing Breadbox pipeline tracking, table updates, and lifecycle operations."""

    def compose_breadbox_tab(self) -> TabPane:
        return TabPane(
            "Pipeline (Breadbox)",
            PipelineFunnelWidget(id="pipeline-funnel-widget"),
            Horizontal(
                Vertical(
                    DataTable(id="pipeline-table", cursor_type="row"),
                    Label(
                        "[dim]Quick keys: (s) Status • (f) Flag • (e) Studio • (r) Re-bake\n            (b) Bake • (v) PDF • (o) Folder • (d) Delete[/dim]",
                        id="pipeline-table-hint"
                    ),
                    id="pipeline-table-col"
                ),
                VerticalScroll(
                    Label("[bold #FFB86C]APPLICATION INSPECTOR[/bold #FFB86C] [dim]• Dossier[/dim]", id="details-header"),
                    Static(
                        "[dim]Select a job row from the table to inspect details.[/dim]",
                        id="details-body"
                    ),
                    Label("[bold #A89F91]JOB ACTIONS[/bold #A89F91]", classes="inspector-sec-label"),
                    Horizontal(
                        Button("✦ Studio (e)", id="btn-pipeline-edit-studio"),
                        Button("▲ Bake (b)", id="btn-pipeline-bake"),
                        Button("▤ View (v)", id="btn-pipeline-view-pdf"),
                        classes="inspector-btn-row"
                    ),
                    Horizontal(
                        Button("↗ Folder (o)", id="btn-open-folder"),
                        Button("↻ Status (s)", id="btn-status"),
                        Button("⚑ Flag (f)", id="btn-flag"),
                        classes="inspector-btn-row"
                    ),
                    Horizontal(
                        Button("↻ Re-bake (r)", id="btn-rebake-job"),
                        Button("✕ Delete (d)", variant="error", id="btn-delete-job"),
                        classes="inspector-btn-row"
                    ),
                    Horizontal(
                        Label("Application Notes:", id="details-notes-label"),
                        Button("✓ Save", id="btn-save-notes"),
                        id="notes-header-row"
                    ),
                    TextArea("", id="input-job-notes"),
                    id="job-details-pane"
                ),
                id="pipeline-container"
            ),
            id="tab-pipeline"
        )

    def load_pipeline_table(self) -> None:
        table = self.query_one("#pipeline-table", DataTable)
        table.clear(columns=True)
        table.add_column("ID", width=12)
        table.add_column("Company", width=12)
        table.add_column("Role", width=24)
        table.add_column("Status", width=12)
        table.add_column("Match", width=6)
        table.add_column("Date Added", width=10)
        table.add_column("Flag", width=14)

        jobs = self.repo.list_jobs()

        drafts = sum(1 for j in jobs if j.status.lower() in ("target", "tailored", "draft"))
        applied = sum(1 for j in jobs if j.status.lower() == "applied")
        interview = sum(1 for j in jobs if j.status.lower() == "interviewing")
        offer = sum(1 for j in jobs if j.status.lower() == "offer")
        try:
            self.query_one("#pipeline-funnel-widget", PipelineFunnelWidget).update_pipeline(
                draft_count=drafts,
                applied_count=applied,
                interview_count=interview,
                offer_count=offer
            )
        except Exception:
            pass

        if not jobs:
            table.add_row(
                "-",
                "[dim italic]No target jobs tracked yet[/dim italic]",
                "[dim italic]Switch to Studio (t) or press (a) to track your first job[/dim italic]",
                "[dim]EMPTY[/dim]",
                "-",
                "-",
                "",
                key="empty_placeholder"
            )
            return

        for j in jobs:
            status_style = {
                "target": "[dim]TARGET[/dim]",
                "tailored": "[cyan]TAILORED[/cyan]",
                "applied": "[blue]APPLIED[/blue]",
                "interviewing": "[bold green]INTERVIEWING[/bold green]",
                "offer": "[bold magenta]OFFER[/bold magenta]",
                "rejected": "[red]REJECTED[/red]",
                "archived": "[dim]ARCHIVED[/dim]"
            }.get(j.status.lower(), j.status.upper())

            match_str = f"{j.match_score}%" if j.match_score is not None else "-"
            flag_str = f"[!] {j.flag}" if j.flag else ""
            date_str = str(j.date_added)[:10] if j.date_added else "-"

            table.add_row(
                j.id,
                j.company,
                j.title,
                status_style,
                match_str,
                date_str,
                flag_str,
                key=j.id
            )

        if jobs:
            if not self.selected_job or not any(j.id == self.selected_job.id for j in jobs):
                self.selected_job = jobs[0]
            else:
                self.selected_job = self.repo.get_job(self.selected_job.id) or jobs[0]
            self.update_details_pane()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if row_key == "empty_placeholder":
            return
        self.selected_job = self.repo.get_job(row_key)
        self.update_details_pane()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value != "empty_placeholder":
            self.selected_job = self.repo.get_job(event.row_key.value)
            self.update_details_pane()

    def update_details_pane(self) -> None:
        details_body = self.query_one("#details-body", Static)
        if not self.selected_job:
            details_body.update("[dim]Select a job row from the table to inspect details.[/dim]")
            try:
                self.query_one("#input-job-notes", TextArea).text = ""
            except Exception:
                pass
            return

        j = self.selected_job
        folder_info = f"[bold #8BE9FD]↗ {j.folder_path}[/bold #8BE9FD]" if j.folder_path else "[dim]Not tailored yet[/dim]"
        url_info = f"↗ [underline #8BE9FD]{j.url[:34]}...[/underline #8BE9FD]" if j.url and len(j.url) > 34 else (f"↗ [underline #8BE9FD]{j.url}[/underline #8BE9FD]" if j.url else "[dim]No URL[/dim]")
        match_str = f"[bold #50FA7B]{j.match_score}% ATS Match[/bold #50FA7B]" if j.match_score is not None else "[#A89F91]Unscored[/#A89F91]"
        flag_str = f" | [bold #FF79C6]⚑ {j.flag}[/bold #FF79C6]" if j.flag else ""

        details_body.update(
            f"[bold #FFFFFF]{j.company}[/bold #FFFFFF] - [bold #FFB86C]{j.title}[/bold #FFB86C]\n"
            f"Stage: [bold #50FA7B]{j.status.upper()}[/bold #50FA7B] • ({match_str}){flag_str}\n"
            f"Location: [#F8F8F2]{j.location or 'N/A'}[/#F8F8F2]\n"
            f"{url_info}\n"
            f"{folder_info}"
        )
        try:
            notes_area = self.query_one("#input-job-notes", TextArea)
            if notes_area.text != (j.notes or ""):
                notes_area.text = j.notes or ""
        except Exception:
            pass

    def action_change_status(self) -> None:
        if not self.selected_job:
            self.notify("Please select a job from the table first.", severity="warning")
            return
        STATUS_CYCLE = ["target", "tailored", "applied", "interviewing", "offer", "archived"]
        curr = (self.selected_job.status or "target").lower()
        try:
            idx = STATUS_CYCLE.index(curr)
            next_status = STATUS_CYCLE[(idx + 1) % len(STATUS_CYCLE)]
        except ValueError:
            next_status = "target"

        self.repo.update_status(self.selected_job.id, next_status)
        if settings.csv_tracker_path:
            CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
        self.selected_job = self.repo.get_job(self.selected_job.id)
        self.load_pipeline_table()
        self.update_details_pane()
        self.notify(f"Status advanced to {next_status.upper()}!", title="Lifecycle Advanced")

    def action_save_notes(self) -> None:
        if not self.selected_job:
            self.notify("Please select a job from the table first.", severity="warning")
            return
        try:
            notes = self.query_one("#input-job-notes", TextArea).text.strip()
            self.repo.update_notes(self.selected_job.id, notes)
            if settings.csv_tracker_path:
                CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)
            self.selected_job = self.repo.get_job(self.selected_job.id)
            self.notify("✓ Saved application notes!", title="Notes Saved")
        except Exception as e:
            self.notify(f"Failed to save notes: {e}", severity="error")

    def action_delete_job(self) -> None:
        """Prompt confirmation and permanently delete the selected application."""
        target_job = self.selected_job
        if not target_job:
            self.notify("Please select an application from the table first.", severity="warning")
            return

        def on_confirmed(confirmed: Optional[bool]) -> None:
            if not confirmed:
                return
            try:
                # 1. Wipe application folder on disk if it exists
                if target_job.folder_path:
                    folder = Path(target_job.folder_path)
                    if not folder.is_absolute():
                        folder = settings.applications_dir / folder
                    if folder.exists() and folder.is_dir():
                        shutil.rmtree(folder, ignore_errors=True)

                # 2. Delete record from DB
                self.repo.delete_job(target_job.id)

                # 3. Re-export CSV tracker
                if settings.csv_tracker_path:
                    CsvSync.export_to_csv(self.repo, settings.csv_tracker_path)

                # 4. If current studio active application matches target_job, clear studio state
                if self.selected_job and self.selected_job.id == target_job.id:
                    self.selected_job = None
                if self.last_tailored_dir and target_job.folder_path and Path(target_job.folder_path).name in str(self.last_tailored_dir):
                    self.last_tailored_dir = None
                    self.current_app_result = None

                # 5. Refresh Breadbox UI
                self.load_pipeline_table()
                self.update_details_pane()
                self.notify(f"✓ Permanently deleted application for {target_job.company} ({target_job.title}).", severity="information")
            except Exception as e:
                self.notify(f"Failed to delete application: {e}", severity="error")

        self.push_screen(DeleteJobModal(target_job), on_confirmed)

    def action_rebake_job(self) -> None:
        """Re-compile the application from Pantry using the active model, update files and match score."""
        target_job = self.selected_job
        if not target_job:
            self.notify("Please select an application to re-bake.", severity="warning")
            return

        # Determine input for re-baking
        url_input = ""
        folder_path = None
        if target_job.folder_path:
            p_candidate = Path(target_job.folder_path)
            if p_candidate.exists():
                folder_path = p_candidate
            elif not p_candidate.is_absolute() and (settings.applications_dir / p_candidate).exists():
                folder_path = settings.applications_dir / p_candidate
            elif (settings.applications_dir / p_candidate.name).exists():
                folder_path = settings.applications_dir / p_candidate.name

        if folder_path and (folder_path / "job_description.txt").exists():
            url_input = str((folder_path / "job_description.txt").resolve())
        elif target_job.url:
            url_input = target_job.url
        elif folder_path and (folder_path / "resume.md").exists():
            url_input = f"Company: {target_job.company}\nTitle: {target_job.title}\n"
        else:
            url_input = f"Company: {target_job.company}\nTitle: {target_job.title}\n"

        persona = None
        if target_job.persona and target_job.persona != "direct":
            try:
                persona = PersonaManager.load_persona(target_job.persona)
            except Exception:
                persona = None

        template_name = self.current_template or "jakes"
        try:
            sel_tmpl = self.query_one("#select-template", Select).value
            if sel_tmpl:
                template_name = str(sel_tmpl)
        except Exception:
            pass

        target_info = {
            "url_input": url_input,
            "pantry": self.pantry,
            "repo": self.repo,
            "job_directives": None,
            "persona": persona,
            "template_name": template_name,
            "existing_folder": str(folder_path.resolve()) if folder_path else None,
            "job_id": target_job.id,
        }

        try:
            self.set_global_stage(1)
        except Exception:
            pass

        self.push_screen(
            BakingModal(task_type="tailor", target_info=target_info),
            self._on_tailoring_modal_dismissed
        )

    def action_toggle_flag(self) -> None:
        if self.selected_job:
            self.push_screen(FlagModal(self.selected_job, self.repo), self._on_modal_dismissed)
        else:
            self.notify("Please select a job from the table first.", severity="warning")

    def action_open_folder(self) -> None:
        target_dir = None
        if self.selected_job and self.selected_job.folder_path:
            p = Path(self.selected_job.folder_path)
            if p.exists():
                target_dir = p
            elif not p.is_absolute() and (settings.applications_dir / p).exists():
                target_dir = settings.applications_dir / p
            elif (settings.applications_dir / p.name).exists():
                target_dir = settings.applications_dir / p.name
        elif self.last_tailored_dir and self.last_tailored_dir.exists():
            target_dir = self.last_tailored_dir

        if target_dir and target_dir.exists():
            self.last_tailored_dir = target_dir
            subprocess.run(["open", str(target_dir)])
            self.notify(f"Opened folder: {target_dir.name}", title="Finder")
        else:
            self.notify("No application folder generated for this job yet.", severity="warning")

    def action_pipeline_bake(self) -> None:
        self.action_bake_pdf()

    def action_pipeline_view_pdf(self) -> None:
        self.action_view_pdf()

    def handle_breadbox_button(self, bid: str) -> bool:
        """Route Breadbox-specific button events."""
        if bid == "btn-status":
            self.action_change_status()
            return True
        if bid == "btn-flag":
            self.action_toggle_flag()
            return True
        if bid in ("btn-open-folder", "btn-studio-folder"):
            self.action_open_folder()
            return True
        if bid == "btn-pipeline-edit-studio":
            self.action_pipeline_edit_studio()
            return True
        if bid == "btn-save-notes":
            self.action_save_notes()
            return True
        if bid == "btn-rebake-job":
            self.action_rebake_job()
            return True
        if bid == "btn-delete-job":
            self.action_delete_job()
            return True
        return False

