"""Production-grade Rich CLI interface for Breadwinner."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from breadwinner.config import settings
from breadwinner.db.repository import JobRecord, JobRepository
from breadwinner.core.portfolio import get_profile_source
from breadwinner.core.scraper import JobScraper
from breadwinner.core.persona import PersonaManager
from breadwinner.core.tailor import TailoringEngine
from breadwinner.core.renderer import TemplateRenderer
from breadwinner.providers.factory import get_llm_provider
from breadwinner.providers.discovery import ProviderDiscovery
from breadwinner.db.sync import CsvSync
from breadwinner.automations.health import JobHealthChecker
from breadwinner.automations.reminders import ReminderEngine
from breadwinner.core.pdf import render_html_to_pdf, PDFGenerationError


console = Console()


def get_repo() -> JobRepository:
    return JobRepository(settings.database_path)


@click.group()
def main():
    """Breadwinner: CLI tool for tailoring and tracking job applications."""
    pass


@main.command()
@click.argument("source", required=False)
@click.option("--company", "-c", help="Company name (if pasting text)")
@click.option("--title", "-t", help="Job title (if pasting text)")
@click.option("--persona", "-p", default=None, help="Narrative persona (tech_ai, bridging_admin, hospitality)")
@click.option("--template", default=None, help="Resume template (jakes, modern, ats)")
@click.option("--provider", default=None, help="LLM provider (gemini, lmstudio, groq, ollama, mock)")
@click.option("--portfolio", default=None, help="Path to portfolio source of truth")
def apply(
    source: Optional[str],
    company: Optional[str],
    title: Optional[str],
    persona: Optional[str],
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

        # 3. Ingest Portfolio
        progress.add_task(description="Loading verified profile from portfolio...", total=None)
        portfolio_path = Path(portfolio or settings.portfolio_path)
        source_adapter = get_profile_source(portfolio_path)
        profile = source_adapter.load_profile()

        # 4. Resolve Persona & Provider
        active_persona_slug = persona or settings.default_persona
        active_persona = PersonaManager.load_persona(active_persona_slug)
        active_provider = get_llm_provider(provider)

        # 5. Tailor Application
        progress.add_task(description=f"Running Match & Tailoring Engine ({active_persona.name})...", total=None)
        tailoring_engine = TailoringEngine(active_provider)
        application = tailoring_engine.analyze_and_tailor(profile, job, active_persona)

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
        (app_dir / "resume.json").write_text(json_resume, encoding="utf-8")
        (app_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
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
            persona=active_persona.slug,
            date_added=date_slug,
            folder_path=str(app_dir.resolve()),
            notes=f"Auto-generated via {active_persona.name}"
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

    console.print(Panel(
        f"[bold]Package Baked Successfully:[/bold]\n"
        f"{pdf_entry}"
        f"• [cyan]Resume (Jake's / HTML):[/cyan] {app_dir}/resume.html\n"
        f"• [cyan]Resume (ATS Markdown):[/cyan] {app_dir}/resume.md\n"
        f"• [cyan]Cover Letter:[/cyan] {app_dir}/cover_letter.md\n"
        f"• [cyan]Portal Answers:[/cyan] {app_dir}/portal_answers.md\n"
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


@main.command(name="personas")
def personas_cmd():
    """List all available narrative personas."""
    personas = PersonaManager.list_personas()
    table = Table(title="Available Narrative Personas", border_style="cyan")
    table.add_column("Slug", style="bold cyan")
    table.add_column("Description")

    for slug, desc in personas.items():
        table.add_row(slug, desc)

    console.print(table)


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
    from breadwinner.ui.app import BreadwinnerApp
    app = BreadwinnerApp(initial_url=url)
    app.run()


if __name__ == "__main__":
    main()
