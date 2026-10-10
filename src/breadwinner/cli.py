import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich import box

from breadwinner.config import settings, get_breadwinner_home, get_env_path
from breadwinner.db.repository import JobRecord, JobRepository
from breadwinner.core.portfolio import get_profile_source
from breadwinner.core.scraper import JobScraper
from breadwinner.core.persona import (
    Persona,
    PersonaManager,
    generate_job_strategy_questions,
    synthesize_job_directives,
    synthesize_job_persona,
    synthesize_persona_from_braindump,
)
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.providers.factory import get_llm_provider
from breadwinner.providers.discovery import ProviderDiscovery
from breadwinner.db.sync import CsvSync
from breadwinner.automations.health import JobHealthChecker
from breadwinner.automations.reminders import ReminderEngine
from breadwinner.core.pdf import render_html_to_pdf, PDFGenerationError
from breadwinner.core.pantry import PantryManager
from breadwinner.core.ingestor import UniversalIngestor, IngestionError
from breadwinner.core.interview import INTERVIEW_QUESTIONS, synthesize_context


console = Console()


def get_repo() -> JobRepository:
    return JobRepository(settings.database_path)


def try_expand_terminal(target_cols: int = 120, target_rows: int = 38) -> None:
    """Best-effort terminal window resize attempt using standard ANSI escape sequences.

    Checks if stdout is an interactive tty and not inside embedded terminals (like VS Code)
    that explicitly reject or ignore terminal dimension resize codes.
    """
    import os
    import shutil
    import sys

    if not sys.stdout.isatty():
        return

    term_prog = os.environ.get("TERM_PROGRAM", "").lower()
    if "vscode" in term_prog or os.environ.get("VSCODE_PID"):
        return

    try:
        cur_cols, cur_rows = shutil.get_terminal_size()
        if cur_cols < target_cols or cur_rows < target_rows:
            new_cols = max(cur_cols, target_cols)
            new_rows = max(cur_rows, target_rows)
            sys.stdout.write(f"\033[8;{new_rows};{new_cols}t")
            sys.stdout.flush()
    except Exception:
        pass


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context):
    """Breadwinner: Anti-Hallucination Local Career Studio 🍞"""
    if ctx.invoked_subcommand is None:
        try_expand_terminal()
        from breadwinner.ui.app import BreadwinnerApp
        app = BreadwinnerApp()
        app.run()




@main.command()
@click.argument("source", required=False)
@click.option("--company", "-c", help="Company name (if pasting text)")
@click.option("--title", "-t", help="Job title (if pasting text)")
@click.option("--persona", "-p", default=None, help="Narrative persona (tech_ai, bridging_admin, hospitality, or custom)")
@click.option("--strategy", "-s", is_flag=True, default=False, help="Run interactive role-specific strategy loop before tailoring")
@click.option("--no-strategy", is_flag=True, default=False, help="Skip strategy loop prompt and use persona directly")
@click.option("--template", default=None, help="Resume template (jakes, modern, ats)")
@click.option("--provider", default=None, help="LLM provider (gemini, lmstudio, groq, ollama, mock)")
@click.option("--portfolio", default=None, help="Path to portfolio source of truth")
def apply(
    source: Optional[str],
    company: Optional[str],
    title: Optional[str],
    persona: Optional[str],
    strategy: bool,
    no_strategy: bool,
    template: Optional[str],
    provider: Optional[str],
    portfolio: Optional[str]
):
    """Ingest a job (URL or text file) and generate a tailored application package."""
    console.print("[bold]Breadwinner Application Generator[/bold]")

    # 1. Resolve source
    if not source:
        source = Prompt.ask("[bold cyan]Enter Job Posting URL (or path to text file)[/bold cyan]")

    source_path = Path(source)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        # 2. Ingest Job
        progress.add_task(description="Ingesting job details...", total=None)
        if source.startswith("http://") or source.startswith("https://"):
            job = JobScraper.ingest_from_url(source)
        elif source_path.is_file():
            text = source_path.read_text(encoding="utf-8")
            job = JobScraper.ingest_from_text(text, company or "Company", title or "Role")
        else:
            job = JobScraper.ingest_from_text(source, company or "Company", title or "Role")

        # 3. Ingest Portfolio / Pantry
        progress.add_task(description="Loading verified profile...", total=None)
        pantry = PantryManager()
        if pantry.is_initialized():
            profile = pantry.load_profile()
        else:
            portfolio_path = Path(portfolio or settings.portfolio_path)
            source_adapter = get_profile_source(portfolio_path)
            profile = source_adapter.load_profile()

    console.print(
        f"\n[bold green]🎯 Target Role Ingested:[/bold green] [bold white]{job.title}[/bold white] at [bold cyan]{job.company}[/bold cyan]"
        + (f" [dim]({job.location})[/dim]" if job.location else "")
    )

    active_provider = get_llm_provider(provider)
    job_directives: Optional[str] = None

    # Decide whether to run the Target Strategy Loop
    run_strategy = False
    if strategy:
        run_strategy = True
    elif persona or no_strategy:
        run_strategy = False
    else:
        try:
            console.print("\n[bold]Select Narrative Strategy for this role:[/bold]")
            console.print("  [bold cyan][1][/bold cyan] [bold]Direct Pantry Match[/bold] [dim](Pure objective alignment, zero persona bias)[/dim]")
            console.print("  [bold cyan][2][/bold cyan] [bold]Run Target Strategy Loop[/bold] [dim](Probe role hook, key proof points & tactical framing)[/dim]")
            console.print("  [bold cyan][3][/bold cyan] [bold]Select an existing Persona[/bold] [dim](tech_ai or custom saved persona)[/dim]")
            choice = Prompt.ask("Strategy mode", choices=["1", "2", "3"], default="1")
            run_strategy = (choice == "2")
            if choice == "3":
                avail = [p.stem for p in PersonaManager.get_built_in_dir().glob("*.yaml")] + [p.stem for p in PersonaManager.get_user_dir().glob("*.yaml")]
                avail = sorted(list(set(avail)))
                persona = Prompt.ask("Enter persona slug", choices=avail, default=settings.default_persona)
            elif choice == "1":
                persona = "none"
        except (EOFError, KeyboardInterrupt):
            run_strategy = False
            persona = "none"

    if run_strategy:
        console.print("\n[bold cyan]─── Target Strategy Discovery Loop ───[/bold cyan]")
        console.print("[dim]Answer 3 quick questions to synthesize role-specific directives for this application.[/dim]\n")
        questions = generate_job_strategy_questions(job, active_provider)
        answers = {}
        for idx, q in enumerate(questions, 1):
            console.print(f"[bold yellow]{idx}. {q.get('title', 'Target Question')}[/bold yellow]")
            console.print(f"[white]{q.get('question', '')}[/white]")
            placeholder = q.get("placeholder", "")
            if placeholder:
                console.print(f"[dim]{placeholder}[/dim]")
            try:
                ans = Prompt.ask("[cyan]Your strategic angle[/cyan] (press Enter to skip)", default="")
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans.strip():
                answers[q.get("id", f"q{idx}")] = ans.strip()

        job_directives = synthesize_job_directives(job, answers, active_provider)
        console.print()
        console.print(Panel(job_directives, title="[bold green]Synthesized Job Directives[/bold green]", border_style="green"))

        # Base persona (optional)
        base_slug = persona if (persona and persona.lower() not in ("none", "direct")) else None
        base_persona = PersonaManager.load_persona(base_slug) if base_slug else None

        # Offer to synthesize and persist a new reusable persona
        save_confirmed = False
        try:
            save_confirmed = Confirm.ask("\nSave this strategy as a new reusable persona for future applications?", default=False)
        except (EOFError, KeyboardInterrupt):
            save_confirmed = False

        if save_confirmed:
            default_p_name = f"{job.company} {job.title} Strategist"
            try:
                p_name = Prompt.ask("Persona Name", default=default_p_name)
            except (EOFError, KeyboardInterrupt):
                p_name = default_p_name
            auto_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in f"{job.company}_{job.title}".lower()).strip("_")
            try:
                p_slug = Prompt.ask("Persona Slug", default=auto_slug)
            except (EOFError, KeyboardInterrupt):
                p_slug = auto_slug

            new_persona = synthesize_job_persona(
                name=p_name,
                slug=p_slug,
                job=job,
                answers=answers,
                base_persona=base_persona,
                provider=active_provider
            )
            saved_path = PersonaManager.save_persona(new_persona)
            console.print(f"[bold green]✓ Saved persona '{new_persona.slug}' to {saved_path}![/bold green]")
            active_persona = new_persona
        else:
            active_persona = base_persona
    else:
        if persona and persona.lower() not in ("none", "direct"):
            active_persona = PersonaManager.load_persona(persona)
        else:
            active_persona = None

    persona_label = active_persona.name if active_persona else "Direct Pantry Match"
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        # 5. Tailor Application
        progress.add_task(description=f"Running Match & Tailoring Engine ({persona_label})...", total=None)
        tailoring_engine = TailoringEngine(active_provider)
        application = tailoring_engine.analyze_and_tailor(profile, job, active_persona, job_directives=job_directives)

        # 6. Render Artifacts
        progress.add_task(description="Rendering application package...", total=None)
        renderer = TemplateRenderer()
        active_template = template or settings.default_template

        resume_html = renderer.render_resume(profile, application, active_template)
        resume_md = renderer.render_resume(profile, application, "ats")
        cover_letter = renderer.render_cover_letter(profile, application)
        portal_qna = renderer.render_portal_qna(profile, application)
        json_resume = renderer.export_json_resume(profile)

        # 7. Write to Application Folder
        date_slug = datetime.now().strftime("%Y-%m-%d")
        safe_company = "".join(c for c in job.company if c.isalnum() or c in "-_").strip()
        safe_title = "".join(c for c in job.title if c.isalnum() or c in "-_").strip()
        app_dir = settings.applications_dir / f"{date_slug}_{safe_company}_{safe_title}"
        app_dir.mkdir(parents=True, exist_ok=True)

        (app_dir / "resume.html").write_text(resume_html, encoding="utf-8")
        (app_dir / "resume.md").write_text(resume_md, encoding="utf-8")
        if application.cover_letter:
            (app_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
        if application.portal_answers:
            (app_dir / "portal_answers.md").write_text(portal_qna, encoding="utf-8")

        # 8. Render Print ATS PDF
        pdf_generated = False
        if settings.auto_generate_pdf:
            try:
                progress.add_task(description="Baking print-ready ATS PDF resume...", total=None)
                render_html_to_pdf(app_dir / "resume.html", app_dir / "resume.pdf", open_after=False)
                pdf_generated = True
            except Exception as e:
                console.print(f"[yellow]Note: PDF auto-generation skipped ({e}). You can print resume.html or run 'breadwinner bake'.[/yellow]")

        # 9. Record in Database
        repo = get_repo()
        job_record = JobRecord(
            id=job.id,
            company=job.company,
            title=job.title,
            url=job.url,
            location=job.location,
            portal_type=job.portal_type,
            status="tailored",
            match_score=application.match_analysis.match_score,
            persona=active_persona.slug if active_persona else "direct",
            date_added=date_slug,
            folder_path=str(app_dir.resolve()),
            notes=f"Auto-generated via {active_persona.name if active_persona else 'Direct Pantry Match'}" + (" (with custom job strategy)" if job_directives else "")
        )
        repo.upsert_job(job_record)

        # 10. Auto-sync to CSV if configured
        if settings.csv_tracker_path:
            CsvSync.export_to_csv(repo, settings.csv_tracker_path)

    # Display Results
    score = application.match_analysis.match_score
    score_color = "green" if score >= 80 else ("yellow" if score >= 60 else "red")

    table = Table(title=f"Target: {job.company} — {job.title}", border_style="cyan")
    table.add_column("Property", style="bold")
    table.add_column("Details")
    table.add_row("Portal Type", job.portal_type.capitalize())
    table.add_row("Location", job.location or "Not specified")
    table.add_row("Persona Applied", f"{active_persona.name} ([dim]{active_persona.slug}[/dim])")
    table.add_row("ATS Match Score", f"[{score_color}]{score}%[/{score_color}]")
    table.add_row("Matched Strengths", ", ".join(application.match_analysis.matched_skills[:8]))
    if application.match_analysis.missing_skills:
        table.add_row("Missing Keywords", ", ".join(application.match_analysis.missing_skills[:5]))
    table.add_row("Application Folder", str(app_dir.resolve()))

    console.print(table)

    pdf_entry = f"• [bold green]Resume (Print ATS PDF):[/bold green] {app_dir}/resume.pdf\n" if pdf_generated else ""

    cl_entry = f"• [cyan]Cover Letter:[/cyan] {app_dir}/cover_letter.md\n" if application.cover_letter else ""
    portal_entry = f"• [cyan]Portal Answers:[/cyan] {app_dir}/portal_answers.md\n" if application.portal_answers else ""

    console.print(Panel(
        f"[bold]Package Baked Successfully:[/bold]\n"
        f"{pdf_entry}"
        f"• [cyan]Resume (Jake's / HTML):[/cyan] {app_dir}/resume.html\n"
        f"• [cyan]Resume (ATS Markdown):[/cyan] {app_dir}/resume.md\n"
        f"{cl_entry}"
        f"{portal_entry}"
        f"• [cyan]JSON Resume:[/cyan] {app_dir}/resume.json\n\n"
        f"[green]✓ Application recorded in tracker.db and synced to {settings.csv_tracker_path or 'CSV'}[/green]",
        border_style="green"
    ))


@main.command(name="track")
@click.option("--status", "-s", help="Filter by status (target, tailored, applied, interviewing, offer, rejected)")
@click.option("--flag", "-f", help="Filter by flag (followup_needed, link_broken, etc.)")
def track_cmd(status: Optional[str], flag: Optional[str]):
    """View all tracked job applications with status, match scores, and flags."""
    repo = get_repo()
    jobs = repo.list_jobs(status=status, flag=flag)

    if not jobs:
        console.print("[yellow]No applications found matching criteria.[/yellow]")
        return

    table = Table(title="Application Tracker", border_style="blue")
    table.add_column("ID", style="dim")
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Match", justify="center")
    table.add_column("Date Added", justify="center")
    table.add_column("Flag", justify="center")

    status_colors = {
        "target": "dim",
        "tailored": "cyan",
        "applied": "blue",
        "interviewing": "green bold",
        "offer": "magenta bold",
        "rejected": "red",
        "archived": "dim"
    }

    for j in jobs:
        s_color = status_colors.get(j.status.lower(), "white")
        m_str = f"{j.match_score}%" if j.match_score is not None else "-"
        f_str = f"[bold red]⚠️ {j.flag}[/bold red]" if j.flag else ""
        table.add_row(
            j.id[:18],
            j.company,
            j.title,
            f"[{s_color}]{j.status.upper()}[/{s_color}]",
            m_str,
            j.date_added,
            f_str
        )

    console.print(table)


@main.command()
@click.argument("job_id")
@click.argument("new_status")
@click.option("--notes", "-n", default=None, help="Update notes")
def status(job_id: str, new_status: str, notes: Optional[str]):
    """Update application status (e.g. breadwinner status monzo-mle interviewing)."""
    repo = get_repo()
    valid_statuses = ["target", "tailored", "applied", "interviewing", "offer", "rejected", "archived"]
    if new_status.lower() not in valid_statuses:
        console.print(f"[red]Error: Invalid status. Choose from: {', '.join(valid_statuses)}[/red]")
        return

    success = repo.update_status(job_id, new_status.lower(), notes)
    if success:
        console.print(f"[green]✓ Updated '{job_id}' status to '{new_status.upper()}'[/green]")
        if settings.csv_tracker_path:
            CsvSync.export_to_csv(repo, settings.csv_tracker_path)
    else:
        console.print(f"[red]Job with ID '{job_id}' not found.[/red]")


@main.command()
@click.argument("job_id")
@click.argument("flag_name", required=False, default=None)
def flag(job_id: str, flag_name: Optional[str]):
    """Set or clear a custom flag on a job (e.g. breadwinner flag monzo-mle high_priority)."""
    repo = get_repo()
    success = repo.set_flag(job_id, flag_name)
    if success:
        if flag_name:
            console.print(f"[green]✓ Set flag '{flag_name}' on '{job_id}'[/green]")
        else:
            console.print(f"[green]✓ Cleared flag on '{job_id}'[/green]")
        if settings.csv_tracker_path:
            CsvSync.export_to_csv(repo, settings.csv_tracker_path)
    else:
        console.print(f"[red]Job with ID '{job_id}' not found.[/red]")


@main.command(name="check-links")
def check_links_cmd():
    """Automated health check on all target job URLs to detect expired postings."""
    repo = get_repo()
    console.print("[cyan]Checking link health for all active job postings...[/cyan]")
    results = JobHealthChecker.check_all_jobs(repo)

    table = Table(title="URL Health Check Results", border_style="magenta")
    table.add_column("Company")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Health Message")

    for job, is_ok, msg in results:
        status_text = "[green]ONLINE[/green]" if is_ok else "[red]DEAD/EXPIRED[/red]"
        table.add_row(job.company, job.title, status_text, msg)

    console.print(table)


@main.command()
@click.option("--days", "-d", default=7, help="Days threshold since submission")
def followups(days: int):
    """Find applications submitted >= N days ago requiring a recruiter follow-up."""
    repo = get_repo()
    overdue = ReminderEngine.find_overdue_followups(repo, days_threshold=days)

    if not overdue:
        console.print(f"[green]✓ No applications pending follow-up (> {days} days)![/green]")
        return

    table = Table(title=f"Applications Needing Follow-up (> {days} days)", border_style="yellow")
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Date Applied")
    table.add_column("Days Since Submission", justify="center")

    for job, delta in overdue:
        table.add_row(job.company, job.title, job.date_applied or "-", f"[bold yellow]{delta} days[/bold yellow]")

    console.print(table)


@main.command(name="sync")
@click.option("--import-csv", "import_path", help="Import jobs from a CSV file into SQLite")
@click.option("--export-csv", "export_path", help="Export jobs from SQLite into a CSV file")
def sync_cmd(import_path: Optional[str], export_path: Optional[str]):
    """Sync between SQLite database and CSV files."""
    repo = get_repo()
    if import_path:
        count = CsvSync.import_from_csv(repo, Path(import_path))
        console.print(f"[green]✓ Imported {count} jobs from {import_path}[/green]")

    if export_path or not import_path:
        out = Path(export_path or settings.csv_tracker_path or "job_tracker.csv")
        count = CsvSync.export_to_csv(repo, out)
        console.print(f"[green]✓ Exported {count} jobs to {out}[/green]")


@main.group(name="personas", invoke_without_command=True)
@click.pass_context
def personas_cmd(ctx):
    """Manage, inspect, and create narrative personas."""
    if ctx.invoked_subcommand is None:
        personas = PersonaManager.list_personas()
        table = Table(title="Available Narrative Personas", border_style="cyan")
        table.add_column("Slug", style="bold cyan")
        table.add_column("Description")

        for slug, desc in personas.items():
            table.add_row(slug, desc)

        console.print(table)
        console.print("\n[dim]Run 'breadwinner personas create' to build a new persona, or 'breadwinner personas view <slug>' to inspect directives.[/dim]")


@personas_cmd.command(name="list")
def personas_list_cmd():
    """List all available narrative personas."""
    personas = PersonaManager.list_personas()
    table = Table(title="Available Narrative Personas", border_style="cyan")
    table.add_column("Slug", style="bold cyan")
    table.add_column("Description")

    for slug, desc in personas.items():
        table.add_row(slug, desc)

    console.print(table)


@personas_cmd.command(name="create")
@click.option("--name", "-n", prompt=True, help="Display Name (e.g. 'Fintech Distributed Systems Lead')")
@click.option("--slug", "-s", prompt=True, help="Slug identifier (e.g. 'fintech_lead')")
@click.option("--tone", "-t", prompt=True, default="Authoritative, highly quantitative, systems-first.", help="Tone")
@click.option("--description", "-d", prompt=True, help="Short description")
def personas_create_cmd(name: str, slug: str, tone: str, description: str):
    """Interactively create and save a new custom persona."""
    console.print("[cyan]Enter System Directives (rules for resume & bullet tailoring):[/cyan]")
    directives = Prompt.ask("System directives", default="PRESERVE HARD METRICS.\nStrict XYZ formula: Accomplished [X] as measured by [Y], by doing [Z].")
    console.print("[cyan]Enter Cover Letter Directives (rules for 3-paragraph letter):[/cyan]")
    cl_directives = Prompt.ask("Cover letter directives", default="Paragraph 1: Technical hook.\nParagraph 2: Two concrete scale metrics.\nParagraph 3: Clean call to action.")

    clean_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug.lower().strip()).strip("_")
    p = Persona(
        name=name,
        slug=clean_slug,
        description=description,
        tone=tone,
        system_directives=directives,
        cover_letter_directives=cl_directives
    )
    saved_path = PersonaManager.save_persona(p)
    console.print(f"[bold green]✓ Created and saved persona '{clean_slug}' to {saved_path}![/bold green]")


@personas_cmd.command(name="synthesize")
@click.option("--dump", "-d", default=None, help="Raw text stream-of-consciousness / brain-dump")
@click.option("--name", "-n", default=None, help="Optional name hint for the persona")
@click.option("--provider", default=None, help="LLM provider override")
def personas_synthesize_cmd(dump: Optional[str], name: Optional[str], provider: Optional[str]):
    """Synthesize a new custom persona from an unstructured brain-dump or voice notes."""
    llm = get_llm_provider(provider) if provider else None
    if not dump:
        console.print("[bold yellow]🌾 Persona Brain-Dump Studio[/bold yellow]")
        console.print("[dim]Type or paste your unstructured stream-of-consciousness (market, visa, notice period, location, salary, archetype, tone, or slop words you hate):[/dim]\n")
        dump = Prompt.ask("[bold cyan]Brain-Dump[/bold cyan]")

    if not dump.strip():
        console.print("[red]Aborted: Empty brain-dump.[/red]")
        return

    console.print("[cyan]Deconstructing brain-dump into Application Class Persona...[/cyan]")
    p = synthesize_persona_from_braindump(dump, name_hint=name, provider=llm)

    console.print(Panel(
        f"[bold cyan]Name:[/bold cyan] {p.name}\n"
        f"[bold cyan]Slug:[/bold cyan] {p.slug}\n"
        f"[bold cyan]Market:[/bold cyan] {p.market}\n"
        f"[bold cyan]Archetype:[/bold cyan] {p.archetype}\n"
        f"[bold cyan]Logistics:[/bold cyan] {p.logistics}\n"
        f"[bold cyan]Tone:[/bold cyan] {p.tone}\n\n"
        f"[bold yellow]System Directives:[/bold yellow]\n{p.system_directives}\n\n"
        f"[bold green]Cover Letter Directives:[/bold green]\n{p.cover_letter_directives}\n\n"
        f"[bold magenta]Banned Words:[/bold magenta] {', '.join(p.banned_words)}",
        title=f"Synthesized Persona: {p.name}",
        border_style="green"
    ))

    if Confirm.ask(f"Save as user_personas/{p.slug}.yaml?", default=True):
        saved_path = PersonaManager.save_persona(p)
        console.print(f"[bold green]✓ Created and saved persona '{p.slug}' to {saved_path}![/bold green]")
    else:
        console.print("[dim]Discarded synthesized persona.[/dim]")


@personas_cmd.command(name="view")
@click.argument("slug")
def personas_view_cmd(slug: str):
    """View details and directives for a specific persona."""
    try:
        p = PersonaManager.load_persona(slug)
        console.print(Panel(
            f"[bold cyan]Name:[/bold cyan] {p.name}\n"
            f"[bold cyan]Slug:[/bold cyan] {p.slug}\n"
            f"[bold cyan]Description:[/bold cyan] {p.description}\n"
            f"[bold cyan]Tone:[/bold cyan] {p.tone}\n\n"
            f"[bold yellow]System Directives:[/bold yellow]\n{p.system_directives}\n\n"
            f"[bold green]Cover Letter Directives:[/bold green]\n{p.cover_letter_directives}",
            title=f"Persona: {p.name}",
            border_style="cyan"
        ))
    except Exception as e:
        console.print(f"[red]Error loading persona '{slug}': {e}[/red]")


@personas_cmd.command(name="delete")
@click.argument("slug")
def personas_delete_cmd(slug: str):
    """Delete a custom persona from user_personas/."""
    if PersonaManager.delete_persona(slug):
        console.print(f"[green]✓ Persona '{slug}' deleted from user_personas/.[/green]")
    else:
        console.print(f"[red]Could not delete '{slug}'. Either it does not exist in user_personas/ or it is a protected built-in persona.[/red]")


@main.command(name="profile")
@click.option("--portfolio", "-p", default=None, help="Portfolio path override")
def profile_cmd(portfolio: Optional[str]):
    """Inspect and verify the extracted candidate profile from portfolio."""
    p_path = Path(portfolio or settings.portfolio_path)
    adapter = get_profile_source(p_path)
    profile = adapter.load_profile()

    console.print(Panel(
        f"[bold]Candidate Profile Source:[/bold] {p_path}\n"
        f"[bold]Name:[/bold] {profile.full_name}\n"
        f"[bold]Title:[/bold] {profile.title}\n"
        f"[bold]Location:[/bold] {profile.location}\n"
        f"[bold]Summary:[/bold] {profile.summary}",
        border_style="blue",
        title="Candidate Profile"
    ))

    # Experience
    table = Table(title=f"Extracted Work Experiences ({len(profile.experiences)})", border_style="green")
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Dates")
    table.add_column("Bullets", justify="center")
    for exp in profile.experiences:
        table.add_row(exp.company, exp.role, f"{exp.start_date} - {exp.end_date}", str(len(exp.bullets)))
    console.print(table)

    # Education & Projects
    console.print(f"[bold cyan]Education ({len(profile.education)}):[/bold cyan] " + ", ".join([f"{e.degree} ({e.institution})" for e in profile.education]))
    console.print(f"[bold cyan]Projects ({len(profile.projects)}):[/bold cyan] " + ", ".join([p.name for p in profile.projects]))


@main.command(name="models")
def models_cmd():
    """Discover available LLM providers, health status, and loaded models."""
    console.print("[cyan]Discovering LLM providers and local models...[/cyan]")
    statuses = ProviderDiscovery.discover_all()

    active_provider = settings.breadwinner_llm_provider.lower()

    for p in statuses:
        is_active = p.slug == active_provider
        badge = "[bold green](ACTIVE PROVIDER)[/bold green]" if is_active else ""
        panel_title = f"{p.name} {badge}"

        table = Table(box=None, padding=(0, 2))
        table.add_column("Status", style="bold")
        table.add_column("Value")
        table.add_row("Health", p.status_text)
        if p.base_url:
            table.add_row("Base URL", p.base_url)

        if p.models:
            model_lines = []
            for m in p.models:
                marker = "👉 [bold green]" if m.is_active else "   [white]"
                suffix = " (Active)[/bold green]" if m.is_active else "[/white]"
                desc = f" — [dim]{m.description}[/dim]" if m.description else ""
                model_lines.append(f"{marker}{m.id}{suffix}{desc}")
            table.add_row("Models", "\n".join(model_lines))
        else:
            table.add_row("Models", "[dim]None detected or missing API credentials[/dim]")

        console.print(Panel(table, title=panel_title, border_style="green" if is_active else "dim"))


@main.command(name="switch")
@click.argument("provider")
@click.argument("model", required=False, default=None)
def switch_cmd(provider: str, model: Optional[str]):
    """Switch active LLM provider and model (e.g. breadwinner switch lmstudio qwen2.5-coder-14b)."""
    valid_providers = ["gemini", "deepseek", "lmstudio", "groq", "ollama", "mock", "openai"]
    if provider.lower() not in valid_providers:
        console.print(f"[red]Invalid provider '{provider}'. Valid choices: {', '.join(valid_providers)}[/red]")
        return


    ProviderDiscovery.switch_model(provider, model)
    model_msg = f" with model '{model}'" if model else ""
    console.print(f"[bold green]✓ Switched active LLM provider to '{provider.upper()}'{model_msg}[/bold green]")


@main.command(name="setup")
def setup_cmd():
    """Interactive onboarding wizard to configure portfolio, AI provider, and keys."""
    from breadwinner.onboarding import run_setup_wizard
    run_setup_wizard()


@main.command(name="bake")
@click.argument("target", required=False, default=None)
@click.option("--no-open", "no_open", is_flag=True, default=False, help="Do not open PDF in viewer after baking")
def bake_cmd(target: Optional[str], no_open: bool):
    """Bake an ATS print-ready PDF from an application folder, job ID, or latest tailored job."""
    app_dir = None
    if target:
        p = Path(target)
        if p.is_dir() and (p / "resume.html").exists():
            app_dir = p
        elif (settings.applications_dir / target).is_dir() and (settings.applications_dir / target / "resume.html").exists():
            app_dir = settings.applications_dir / target
        else:
            repo = get_repo()
            job = repo.get_job(target)
            if job and job.folder_path and Path(job.folder_path).is_dir():
                app_dir = Path(job.folder_path)

    if not app_dir:
        # Pick the latest modified folder in settings.applications_dir
        if settings.applications_dir.exists():
            dirs = [d for d in settings.applications_dir.iterdir() if d.is_dir() and (d / "resume.html").exists()]
            if dirs:
                dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
                app_dir = dirs[0]

    if not app_dir or not (app_dir / "resume.html").exists():
        console.print("[red]Error: Could not locate an application folder with resume.html.[/red]")
        console.print("[dim]Usage: breadwinner bake [path_or_job_id][/dim]")
        return

    html_file = app_dir / "resume.html"
    pdf_file = app_dir / "resume.pdf"

    console.print(f"[cyan]Baking ATS PDF from:[/cyan] {html_file}")
    try:
        render_html_to_pdf(html_file, pdf_file, open_after=not no_open)
        console.print(Panel(
            f"[bold green]✓ Fresh out of the oven![/bold green] 🍞\n\n"
            f"• [bold]Output PDF:[/bold] {pdf_file.resolve()}\n"
            f"• [bold]File size:[/bold] {pdf_file.stat().st_size} bytes\n\n"
            f"[dim]Optimized for Applicant Tracking Systems (ATS) and 1-page standard printing.[/dim]",
            border_style="green",
            title="Breadwinner Bakery"
        ))
    except Exception as e:
        console.print(f"[bold red]PDF Baking Error:[/bold red] {e}")


@main.command(name="ui")
@click.option("--url", "-u", default=None, help="Pre-load a target job URL into Tailor Studio")
def ui_cmd(url: Optional[str]):
    """Launch the interactive terminal UI (TUI) studio."""
    try_expand_terminal()
    from breadwinner.ui.app import BreadwinnerApp
    app = BreadwinnerApp(initial_url=url)
    app.run()


@main.command(name="where")
def where_cmd():
    """Display active Breadwinner storage paths, home directory, and environment diagnostics."""
    home_dir = get_breadwinner_home()
    env_file = get_env_path()
    pantry = PantryManager(settings.pantry_dir)

    table = Table(title="🥖 Breadwinner Storage & Environment Map", border_style="#d4a373", box=box.ROUNDED)
    table.add_column("Component", style="bold cyan", width=22)
    table.add_column("Location / Value", style="white")
    table.add_column("Status", style="yellow")

    # Breadwinner Home
    table.add_row("Breadwinner Home", str(home_dir), "[green]Active[/green]")

    # Pantry
    if pantry.is_initialized():
        try:
            profile = pantry.load_profile()
            snapshots = pantry.list_snapshots()
            pantry_status = f"[green]Initialized[/green] ({profile.full_name}, {len(profile.experiences)} roles, {len(snapshots)} snapshots)"
        except Exception as e:
            pantry_status = f"[red]Error loading profile ({e})[/red]"
    else:
        pantry_status = "[dim]Empty / Not Initialized[/dim]"
    table.add_row("Career Pantry", str(settings.pantry_dir), pantry_status)

    # Database
    if settings.database_path.exists():
        try:
            repo = JobRepository(settings.database_path)
            jobs = repo.get_all_jobs()
            db_status = f"[green]Active[/green] ({len(jobs)} tracked jobs)"
        except Exception:
            db_status = "[green]Active[/green] (SQLite file present)"
    else:
        db_status = "[dim]Not Created Yet[/dim]"
    table.add_row("Tracking Database", str(settings.database_path), db_status)

    # CSV Tracker
    if settings.csv_tracker_path and settings.csv_tracker_path.exists():
        csv_status = "[green]Active[/green]"
    else:
        csv_status = "[dim]Not Created Yet[/dim]"
    table.add_row("CSV Tracker", str(settings.csv_tracker_path) if settings.csv_tracker_path else "None", csv_status)

    # Applications
    try:
        if settings.applications_dir.exists():
            apps = [p for p in settings.applications_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
            app_status = f"[green]Active[/green] ({len(apps)} applications)"
        else:
            app_status = "[dim]Empty / Not Created[/dim]"
    except Exception as e:
        app_status = f"[yellow]Restricted / Present ({e})[/yellow]"
    table.add_row("Applications Dir", str(settings.applications_dir), app_status)

    # User Personas
    try:
        if settings.user_personas_dir.exists():
            personas = [p.stem for p in settings.user_personas_dir.glob("*.yaml")]
            persona_status = f"[green]Active[/green] ({len(personas)} custom: {', '.join(personas) if personas else 'none'})"
        else:
            persona_status = "[dim]Default Only[/dim]"
    except Exception as e:
        persona_status = f"[yellow]Restricted / Default Only ({e})[/yellow]"
    table.add_row("User Personas", str(settings.user_personas_dir), persona_status)

    # Configuration .env
    try:
        env_status = "[green]Present[/green]" if env_file.exists() else "[dim]Not Found (Using Defaults)[/dim]"
    except Exception:
        env_status = "[dim]Not Found (Using Defaults)[/dim]"
    table.add_row("Environment (.env)", str(env_file), env_status)

    # LLM Provider
    provider = settings.breadwinner_llm_provider
    key_found = False
    if provider == "gemini" and settings.gemini_api_key:
        key_found = True
    elif provider == "openrouter" and settings.openrouter_api_key:
        key_found = True
    elif provider == "anthropic" and settings.anthropic_api_key:
        key_found = True
    elif provider == "openai" and settings.openai_api_key:
        key_found = True
    elif provider == "groq" and settings.groq_api_key:
        key_found = True
    elif provider in ("mock", "lmstudio", "ollama"):
        key_found = True

    key_status = "[green]API Key Configured[/green]" if key_found else "[red]Missing API Key[/red]"
    table.add_row("LLM Provider", f"{provider}", key_status)

    console.print(table)

    # Stray directory check
    stray_warnings = []
    try:
        stray_pantry_cwd = Path("./pantry").resolve()
        if stray_pantry_cwd != settings.pantry_dir.resolve() and stray_pantry_cwd.exists():
            stray_warnings.append(f"Stray pantry directory detected in CWD: {stray_pantry_cwd}")
    except Exception:
        pass

    try:
        stray_pantry_home = (Path.home() / "pantry").resolve()
        if stray_pantry_home != settings.pantry_dir.resolve() and stray_pantry_home.exists():
            stray_warnings.append(f"Stray pantry directory detected in user home: {stray_pantry_home}")
    except Exception:
        pass

    if stray_warnings:
        console.print(Panel(
            "\n".join(f"⚠️  {w}" for w in stray_warnings) + "\n\n"
            "[dim]Run 'breadwinner reset --all' to purge stray directories and harmonize storage.[/dim]",
            title="Storage Warning",
            border_style="yellow"
        ))


@main.command(name="reset")
@click.option("--all", "reset_all", is_flag=True, default=False, help="Reset pantry, applications, database, and personas (preserves API keys)")
@click.option("--pantry", "reset_pantry", is_flag=True, default=False, help="Clear pantry profile, context, and snapshots")
@click.option("--db", "reset_db", is_flag=True, default=False, help="Delete tracking database and CSV export")
@click.option("--applications", "reset_apps", is_flag=True, default=False, help="Delete generated applications")
@click.option("--personas", "reset_personas", is_flag=True, default=False, help="Delete custom user personas")
@click.option("--keys", "reset_keys", is_flag=True, default=False, help="Purge API keys from .env")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def reset_cmd(reset_all: bool, reset_pantry: bool, reset_db: bool, reset_apps: bool, reset_personas: bool, reset_keys: bool, yes: bool):
    """Reset Breadwinner data, career pantry, applications, or database."""
    if not (reset_all or reset_pantry or reset_db or reset_apps or reset_personas or reset_keys):
        reset_all = True

    items_to_reset = []
    if reset_all or reset_pantry:
        items_to_reset.append("Career Pantry (profile.json, context.md, snapshots)")
    if reset_all or reset_db:
        items_to_reset.append("Job Tracking Database & CSV Tracker")
    if reset_all or reset_apps:
        items_to_reset.append("Generated Applications Directory")
    if reset_all or reset_personas:
        items_to_reset.append("Custom User Personas")
    if reset_keys:
        items_to_reset.append("API Keys & Environment Credentials")

    console.print(Panel(
        "[bold red]⚠️  Breadwinner Reset Operation[/bold red]\n\n"
        "The following components will be cleared:\n" +
        "\n".join(f"  • {item}" for item in items_to_reset),
        border_style="red"
    ))

    if not yes:
        if not Confirm.ask("[bold red]Are you sure you want to proceed with this reset?[/bold red]", default=False):
            console.print("[yellow]Reset cancelled.[/yellow]")
            return

    # 1. Pantry
    if reset_all or reset_pantry:
        pantry = PantryManager(settings.pantry_dir)
        pantry.clear()
        stray_home = (Path.home() / "pantry").resolve()
        if stray_home.exists() and stray_home != settings.pantry_dir.resolve():
            shutil.rmtree(stray_home, ignore_errors=True)
        stray_cwd = Path("./pantry").resolve()
        if stray_cwd.exists() and stray_cwd != settings.pantry_dir.resolve():
            shutil.rmtree(stray_cwd, ignore_errors=True)
        console.print("[bold green]✓ Career Pantry cleared.[/bold green]")

    # 2. Database & CSV
    if reset_all or reset_db:
        if settings.database_path.exists():
            try:
                settings.database_path.unlink()
            except Exception:
                pass
        stray_db_home = (Path.home() / "tracker.db").resolve()
        if stray_db_home.exists() and stray_db_home != settings.database_path.resolve():
            try:
                stray_db_home.unlink()
            except Exception:
                pass
        stray_db_cwd = Path("./tracker.db").resolve()
        if stray_db_cwd.exists() and stray_db_cwd != settings.database_path.resolve():
            try:
                stray_db_cwd.unlink()
            except Exception:
                pass
        if settings.csv_tracker_path and settings.csv_tracker_path.exists():
            try:
                settings.csv_tracker_path.unlink()
            except Exception:
                pass
        console.print("[bold green]✓ Tracking database and CSV reset.[/bold green]")

    # 3. Applications
    if reset_all or reset_apps:
        if settings.applications_dir.exists():
            for child in settings.applications_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                elif child.is_file() and not child.name.startswith("."):
                    child.unlink()
        console.print("[bold green]✓ Applications directory cleared.[/bold green]")

    # 4. Personas
    if reset_all or reset_personas:
        if settings.user_personas_dir.exists():
            for p in settings.user_personas_dir.glob("*.yaml"):
                p.unlink()
        console.print("[bold green]✓ Custom user personas cleared.[/bold green]")

    # 5. Keys
    if reset_keys:
        env_file = get_env_path()
        if env_file.exists():
            env_file.unlink()
        console.print("[bold green]✓ API keys and .env removed.[/bold green]")

    console.print("[bold green]✓ Reset operation complete.[/bold green]")


# ==============================================================================
# PANTRY COMMANDS (Canonical Knowledge Base & Sync)
# ==============================================================================

@main.group(name="pantry")
def pantry_group():
    """Manage your canonical career knowledge base, snapshots, and two-way sync."""
    pass


@pantry_group.command(name="clear")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def pantry_clear_cmd(yes: bool):
    """Clear canonical pantry profile, context, and snapshots."""
    pantry = PantryManager(settings.pantry_dir)
    if not yes:
        if not Confirm.ask("Are you sure you want to clear your Career Pantry?", default=False):
            console.print("[yellow]Pantry clear cancelled.[/yellow]")
            return
    pantry.clear()
    console.print(f"[bold green]✓ Pantry at {settings.pantry_dir} cleared successfully.[/bold green]")


@pantry_group.command(name="show")
def pantry_show_cmd():
    """Inspect what Breadwinner is currently deriving from your Pantry."""
    pantry = PantryManager(settings.pantry_dir)
    if not pantry.is_initialized():
        console.print("[yellow]Pantry is not initialized yet. Run 'breadwinner pantry ingest' or 'breadwinner setup'.[/yellow]")
        return

    profile = pantry.load_profile()
    context = pantry.load_context()
    meta = pantry.load_source_metadata()

    src_label = f"Linked Source: [cyan]{meta.get('source', 'Local')}[/cyan]" if meta else "Linked Source: Local"

    console.print(Panel(
        f"[bold yellow]🥖 Breadwinner Pantry (Canonical Knowledge Base)[/bold yellow]\n\n"
        f"• [bold]Candidate:[/bold] {profile.full_name} ({profile.title})\n"
        f"• [bold]Location:[/bold] {profile.location} | [bold]Email:[/bold] {profile.email}\n"
        f"• [bold]{src_label}[/bold]\n"
        f"• [bold]Summary:[/bold] {profile.summary}",
        border_style="yellow",
        title="Pantry Profile"
    ))

    table = Table(title=f"Verified Experiences ({len(profile.experiences)})", border_style="green")
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Dates")
    table.add_column("Bullets", justify="center")
    for exp in profile.experiences:
        table.add_row(exp.company, exp.role, f"{exp.start_date} - {exp.end_date}", str(len(exp.bullets)))
    console.print(table)

    if profile.projects:
        console.print(f"[bold cyan]Verified Projects ({len(profile.projects)}):[/bold cyan] " + ", ".join([p.name for p in profile.projects]))
    if profile.skills:
        all_skills = [s for cat in profile.skills for s in cat.skills]
        console.print(f"[bold cyan]Skills Catalog ({len(all_skills)}):[/bold cyan] " + ", ".join(all_skills[:12]) + ("..." if len(all_skills) > 12 else ""))

    if context:
        console.print(Panel(context, title="Personal Directives & Guardrails (context.md)", border_style="cyan"))


@pantry_group.command(name="ingest")
@click.argument("source", required=False, default=None)
def pantry_ingest_cmd(source: Optional[str]):
    """Ingest candidate context from a live website URL, file (.docx, .pdf, .json, .md), or text."""
    if not source:
        source = Prompt.ask("[bold cyan]Enter portfolio URL, document path, or text snippet[/bold cyan]")

    provider = get_llm_provider()
    console.print(f"[cyan]Analyzing and extracting verified profile from: {source}...[/cyan]")

    try:
        new_profile = UniversalIngestor.ingest(source, provider)
    except Exception as e:
        console.print(f"[bold red]Ingestion Error:[/bold red] {e}")
        return

    # Preview
    console.print(Panel(
        f"[bold green]✓ Ingestion Complete![/bold green]\n\n"
        f"• [bold]Candidate:[/bold] {new_profile.full_name} ({new_profile.title})\n"
        f"• [bold]Experiences:[/bold] {len(new_profile.experiences)} roles detected\n"
        f"• [bold]Projects:[/bold] {len(new_profile.projects)} projects detected\n"
        f"• [bold]Skills:[/bold] {len(new_profile.skills)} categories detected\n"
        f"• [bold]Summary:[/bold] {new_profile.summary}",
        border_style="green",
        title="Ingestion Preview"
    ))

    confirm = Confirm.ask("Save this profile to your Pantry as your canonical source of truth?", default=True)
    if confirm:
        pantry = PantryManager(settings.pantry_dir)
        source_meta = {
            "source": source,
            "ingestion_type": "url" if source.startswith("http") else "file"
        }
        pantry.save_pantry(new_profile, source_info=source_meta, trigger=f"ingest_{source[:20]}")
        console.print(f"[bold green]✓ Saved to {settings.pantry_dir}/profile.json with snapshot history.[/bold green]")


@pantry_group.command(name="interview")
def pantry_interview_cmd():
    """Run the interactive Baker's Interview loop to discover qualitative nuances and guardrails."""
    pantry = PantryManager(settings.pantry_dir)
    if not pantry.is_initialized():
        console.print("[yellow]Pantry is not initialized yet. Ingest a profile first with 'breadwinner pantry ingest'.[/yellow]")
        return

    profile = pantry.load_profile()
    console.print(Panel(
        f"[bold yellow]🥖 The Baker's Interview: Discovering Your Context[/bold yellow]\n\n"
        f"Candidate: [bold]{profile.full_name}[/bold]\n"
        f"[dim]Answer 3 quick questions. Breadwinner will synthesize this into personal directives\n"
        f"that guide AI tailoring, non-negotiables, and cover letters.[/dim]",
        border_style="yellow"
    ))

    answers = {}
    for q in INTERVIEW_QUESTIONS:
        console.print(f"\n[bold cyan]{q['title']}[/bold cyan]")
        console.print(f"[dim]{q['prompt']}[/dim]")
        ans = Prompt.ask("Your response", default="")
        if ans.strip():
            answers[q["id"]] = ans.strip()

    if not answers:
        console.print("[yellow]No responses provided. Pantry context left unchanged.[/yellow]")
        return

    provider = get_llm_provider()
    console.print("[cyan]Synthesizing personal career directives...[/cyan]")
    synthesized_md = synthesize_context(profile, answers, provider)

    console.print(Panel(synthesized_md, title="Synthesized Directives Preview", border_style="green"))
    save_it = Confirm.ask("Save these directives to your Pantry (pantry/context.md)?", default=True)
    if save_it:
        pantry.save_pantry(profile, context=synthesized_md, trigger="interview_synthesis")
        console.print("[bold green]✓ Saved to pantry/context.md and recorded snapshot.[/bold green]")


@pantry_group.command(name="sync")
def pantry_sync_cmd():
    """Sync and diff against your linked upstream portfolio (live URL or folder)."""
    pantry = PantryManager(settings.pantry_dir)
    if not pantry.is_initialized():
        console.print("[yellow]Pantry is not initialized. Run 'breadwinner pantry ingest' first.[/yellow]")
        return

    meta = pantry.load_source_metadata()
    if not meta.get("source"):
        console.print("[yellow]No linked upstream source found. Use 'breadwinner pantry ingest <url_or_path>' to link one.[/yellow]")
        return

    source = meta["source"]
    console.print(f"[cyan]Syncing and diffing against linked source: {source}...[/cyan]")
    provider = get_llm_provider()

    try:
        diff, new_profile = pantry.sync_from_linked_source(provider)
    except Exception as e:
        console.print(f"[bold red]Sync Error:[/bold red] {e}")
        return

    # Display Diff
    has_changes = (
        bool(diff.get("added_experiences")) or
        bool(diff.get("modified_experiences")) or
        bool(diff.get("added_projects")) or
        diff.get("summary_changed")
    )

    if not has_changes:
        console.print("[bold green]✓ Pantry is completely up to date with your portfolio. Zero changes detected![/bold green]")
        return

    console.print(Panel(
        f"[bold yellow]Changes Detected in Upstream Portfolio:[/bold yellow]\n\n"
        + (f"🟢 [bold]New Experiences:[/bold] {', '.join(diff['added_experiences'])}\n" if diff.get("added_experiences") else "")
        + (f"🟢 [bold]New Projects:[/bold] {', '.join(diff['added_projects'])}\n" if diff.get("added_projects") else "")
        + (f"🟡 [bold]Summary Updated[/bold]\n" if diff.get("summary_changed") else "")
        + (f"🟡 [bold]Modified Experiences:[/bold] {len(diff.get('modified_experiences', []))} updated\n" if diff.get("modified_experiences") else ""),
        title="Sync Diff Review",
        border_style="yellow"
    ))

    merge = Confirm.ask("Merge these updates into your canonical Pantry?", default=True)
    if merge:
        curr_context = pantry.load_context()
        pantry.save_pantry(new_profile, context=curr_context, source_info=meta, trigger="portfolio_sync")
        console.print("[bold green]✓ Successfully merged changes and created rollback snapshot![/bold green]")


@pantry_group.command(name="history")
def pantry_history_cmd():
    """List historical snapshots of your Pantry for auditing or rollback."""
    pantry = PantryManager(settings.pantry_dir)
    snapshots = pantry.list_snapshots()

    if not snapshots:
        console.print("[dim]No historical snapshots recorded yet.[/dim]")
        return

    table = Table(title="Pantry Snapshot History", border_style="cyan")
    table.add_column("Snapshot ID", style="bold cyan")
    table.add_column("Timestamp")
    table.add_column("Trigger Event")

    for s in snapshots:
        table.add_row(s["id"], s.get("timestamp", "-"), s.get("trigger", "-"))

    console.print(table)
    console.print("[dim]To revert to any past snapshot, run: breadwinner pantry revert <snapshot_id>[/dim]")


@pantry_group.command(name="revert")
@click.argument("snapshot_id")
def pantry_revert_cmd(snapshot_id: str):
    """Revert your Pantry to a previous snapshot ID."""
    pantry = PantryManager(settings.pantry_dir)
    success = pantry.revert_snapshot(snapshot_id)
    if success:
        console.print(f"[bold green]✓ Successfully reverted Pantry to snapshot '{snapshot_id}'![/bold green]")
    else:
        console.print(f"[bold red]Error: Snapshot '{snapshot_id}' not found.[/bold red]")


# =========================================================================
# UNIVERSAL JOB INGESTION COMMANDS (ADR 001)
# =========================================================================

@main.group(name="job")
def job_group():
    """Universal job ingestion and requirement inspection."""
    pass


@job_group.command(name="inspect")
@click.argument("source")
def job_inspect_cmd(source: str):
    """Inspect any job posting link or file for questions, tech tags, and knockout fields."""
    from breadwinner.core.universal import UniversalJobIngestor
    from breadwinner.core.models import CoverLetterRequirement

    console.print(f"\n[bold #d4a373]🥐 BREADWINNER UNIVERSAL JOB INSPECTOR[/bold #d4a373]")
    console.print(f"[dim]Resolving and analyzing: {source}[/dim]\n")

    pantry = PantryManager(settings.pantry_dir)
    profile = pantry.load_profile() if pantry.is_initialized() else None

    if source.startswith("http://") or source.startswith("https://"):
        result = UniversalJobIngestor.ingest_url(source, profile=profile)
    else:
        p_path = Path(source)
        if p_path.is_file():
            text = p_path.read_text(encoding="utf-8")
        else:
            text = source
        result = UniversalJobIngestor.ingest_text(text, company="Target Company", title="Target Role", profile=profile)

    # 1. Summary Card
    tier_desc = "Tier 1: Verified ATS API" if result.extraction_method == "tier_1_api" else "Tier 2: Universal Fallback"
    summary_table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
    summary_table.add_column("Field", style="bold cyan", width=18)
    summary_table.add_column("Value")

    summary_table.add_row("Target Role", f"[bold white]{result.title}[/bold white]")
    summary_table.add_row("Company", f"[bold yellow]{result.company}[/bold yellow]")
    summary_table.add_row("Location", result.location or "[dim]Unspecified / Remote[/dim]")
    summary_table.add_row("Portal Platform", f"{result.portal_type.upper()} ({tier_desc})")

    # Cover Letter status
    if result.cover_letter_status == CoverLetterRequirement.MANDATORY:
        cl_str = "[bold #50fa7b][✓] MANDATORY[/bold #50fa7b]"
    elif result.cover_letter_status == CoverLetterRequirement.OPTIONAL:
        cl_str = "[bold #ffb86c][·] OPTIONAL[/bold #ffb86c]"
    elif result.cover_letter_status == CoverLetterRequirement.PROHIBITED:
        cl_str = "[bold #ff5555][✕] PROHIBITED (Not Accepted)[/bold #ff5555]"
    else:
        cl_str = "[dim][?] Not Specified[/dim]"
    summary_table.add_row("Cover Letter", cl_str)

    console.print(summary_table)

    # 2. Matched Technology Tags
    log = result.logistics
    if log.matched_technology_tags:
        console.print(f"\n[bold #8be9fd]🏷 Matched Technology Tags (to paste into Skills field):[/bold #8be9fd]")
        console.print(f"  [bold green]{', '.join(log.matched_technology_tags)}[/bold green]")

    # 3. Mathematical Experience
    if log.calculated_years_of_experience:
        console.print(f"\n[bold #8be9fd]⏱ Calculated Experience from Career Pantry:[/bold #8be9fd]")
        for tech, yrs in sorted(log.calculated_years_of_experience.items(), key=lambda x: -x[1]):
            console.print(f"  • [bold white]{tech}:[/bold white] [bold cyan]{yrs} Year{'s' if yrs != 1 else ''}[/bold cyan]")

    # 4. Detected Application Questions
    if result.questions:
        console.print(f"\n[bold #8be9fd]📝 Detected Application Questions ({len(result.questions)} Prompts):[/bold #8be9fd]")
        for idx, q in enumerate(result.questions, 1):
            req_tag = "[bold #ff5555][REQUIRED][/bold #ff5555]" if q.required else "[dim][OPTIONAL][/dim]"
            src_tag = "[cyan]Form Field[/cyan]" if q.source.value == "form_field" else "[yellow]In-Text Screening[/yellow]"
            type_tag = f"[dim]({q.question_type.value})[/dim]"
            console.print(f"  {idx}. {req_tag} {src_tag} {type_tag}: [bold white]\"{q.prompt}\"[/bold white]")
            if q.options:
                console.print(f"     [dim]Options: {', '.join(q.options)}[/dim]")
    else:
        console.print(f"\n[dim]✓ No custom essay questions detected.[/dim]")

    console.print(f"\n[dim]To generate the complete copy-paste dossier, run: breadwinner job answers {source}[/dim]\n")


@job_group.command(name="answers")
@click.argument("source")
def job_answers_cmd(source: str):
    """Generate the complete copy-paste Application Dossier (`portal_answers.md`)."""
    from breadwinner.core.universal import UniversalJobIngestor
    from breadwinner.core.dossier import render_application_dossier

    pantry = PantryManager(settings.pantry_dir)
    profile = pantry.load_profile() if pantry.is_initialized() else None

    if source.startswith("http://") or source.startswith("https://"):
        result = UniversalJobIngestor.ingest_url(source, profile=profile)
    else:
        p_path = Path(source)
        text = p_path.read_text(encoding="utf-8") if p_path.is_file() else source
        result = UniversalJobIngestor.ingest_text(text, profile=profile)

    dossier_md = render_application_dossier(result, profile=profile)
    console.print(dossier_md)


if __name__ == "__main__":
    main()
