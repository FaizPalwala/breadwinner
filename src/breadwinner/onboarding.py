"""Interactive onboarding setup wizard for Breadwinner."""

import os
import stat
from pathlib import Path
from typing import Optional, Dict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()

STARTER_JSON_RESUME = """{
  "basics": {
    "name": "Alex Taylor",
    "label": "Software Engineer & Systems Builder",
    "email": "alex.taylor@example.com",
    "phone": "+1-555-0199",
    "url": "https://alextaylor.dev",
    "summary": "Full-stack and distributed systems engineer with experience designing high-throughput services and cloud applications.",
    "location": {
      "city": "London",
      "countryCode": "UK"
    }
  },
  "work": [
    {
      "name": "Apex Cloud Systems",
      "position": "Software Engineer",
      "startDate": "2022-01-01",
      "endDate": "Present",
      "summary": "Core backend platform engineer.",
      "highlights": [
        "Architected real-time streaming pipeline reducing ingestion latency by 45% across 10M+ daily events.",
        "Refactored microservices architecture to asynchronous workers, cutting p99 response times from 420ms to 85ms.",
        "Authored CI/CD deployment pipelines supporting automated canary rollouts with zero downtime."
      ]
    },
    {
      "name": "Nova Dynamics",
      "position": "Junior Engineer",
      "startDate": "2020-06-01",
      "endDate": "2021-12-31",
      "summary": "Frontend and service API developer.",
      "highlights": [
        "Implemented responsive UI components using React and TypeScript, improving user retention by 22%.",
        "Created automated integration test suite that reduced regression bugs in production by 35%."
      ]
    }
  ],
  "education": [
    {
      "institution": "University of Technology",
      "area": "Computer Science",
      "studyType": "B.Sc. (Hons)",
      "startDate": "2016-09-01",
      "endDate": "2020-05-01",
      "courses": ["Distributed Systems", "Algorithms", "Database Engineering"]
    }
  ],
  "skills": [
    {
      "name": "Languages",
      "keywords": ["Python", "TypeScript", "Go", "SQL", "Bash"]
    },
    {
      "name": "Systems & Cloud",
      "keywords": ["Docker", "Kubernetes", "PostgreSQL", "Redis", "AWS", "GCP"]
    }
  ],
  "projects": [
    {
      "name": "Distributed Job Scheduler",
      "description": "High-throughput fault-tolerant task queue with leader election and Raft consensus.",
      "keywords": ["Go", "Raft", "gRPC", "Docker"]
    }
  ]
}
"""


def initialize_starter_portfolio(target_dir: Path) -> Path:
    """Create a starter portfolio with verified mock data for immediate use."""
    target_dir.mkdir(parents=True, exist_ok=True)
    resume_json = target_dir / "resume.json"
    if not resume_json.exists():
        resume_json.write_text(STARTER_JSON_RESUME, encoding="utf-8")
    return resume_json


def run_setup_wizard(env_file_path: Optional[Path] = None) -> bool:
    """Run an interactive 60-second onboarding wizard."""
    env_path = env_file_path or Path(".env")

    console.print(Panel(
        "[bold yellow]🥖 Welcome to Breadwinner![/bold yellow]\n\n"
        "[white]The craft bakery for your career. Local-first, anti-slop resume tailoring\n"
        "grounded in your verified facts. Let's get your studio set up in 60 seconds.[/white]",
        border_style="yellow",
        title="[bold]Breadwinner Setup Studio[/bold]",
        subtitle="Step 1 of 3"
    ))

    # -------------------------------------------------------------
    # Step 1: Candidate Portfolio / Ingredients
    # -------------------------------------------------------------
    console.print("\n[bold cyan]Step 1: Your Career Ingredients (Portfolio Source of Truth)[/bold cyan]")
    console.print(
        "[dim]Breadwinner needs a source of truth for your work history (JSON Resume or Markdown folder).\n"
        "It will NEVER hallucinate credentials; it only selects and tailors verified facts.[/dim]\n"
    )

    default_portfolio = "./portfolio"
    if Path(default_portfolio).exists():
        portfolio_input = Prompt.ask(
            "Portfolio directory or resume.json path",
            default=default_portfolio
        )
    else:
        create_starter = Confirm.ask(
            "No portfolio found. Would you like to create a clean starter portfolio in './portfolio'?",
            default=True
        )
        if create_starter:
            p_dir = Path("./portfolio")
            initialize_starter_portfolio(p_dir)
            console.print("[green]✓ Created starter portfolio in ./portfolio/resume.json[/green]")
            portfolio_input = "./portfolio"
        else:
            portfolio_input = Prompt.ask("Enter the path to your portfolio or resume.json")

    # -------------------------------------------------------------
    # Step 2: Choose AI Intelligence Engine
    # -------------------------------------------------------------
    console.print("\n[bold cyan]Step 2: Choose Your AI Engine (Local or BYOK)[/bold cyan]")
    console.print(
        "[dim]Choose how you want to run tailoring. All keys stay private on your machine.[/dim]\n"
    )

    table = Table(box=None, padding=(0, 2))
    table.add_column("Option", style="bold yellow")
    table.add_column("Engine", style="bold")
    table.add_column("Type")
    table.add_column("Description")

    table.add_row("1", "Google Gemini", "Cloud (Free Tier / BYOK)", "Recommended. Free 15 RPM tier, fast, high quality.")
    table.add_row("2", "DeepSeek", "Cloud (BYOK)", "V3 and R1 reasoning models with ultra-low cost.")
    table.add_row("3", "LM Studio", "100% Local (Offline)", "Runs locally on Apple Silicon / PC via localhost:1234.")
    table.add_row("4", "Groq Cloud", "Cloud (BYOK)", "Ultra-fast inference for open-weights models (Llama 3.3).")
    table.add_row("5", "Ollama", "100% Local (CLI)", "Runs local models via localhost:11434.")
    table.add_row("6", "Offline Mock", "Local Offline", "Instant testing mode without API keys or models.")

    console.print(table)

    choice = Prompt.ask("\nSelect your preferred AI engine", choices=["1", "2", "3", "4", "5", "6"], default="1")

    provider_map = {
        "1": "gemini",
        "2": "deepseek",
        "3": "lmstudio",
        "4": "groq",
        "5": "ollama",
        "6": "mock"
    }
    selected_provider = provider_map[choice]

    env_vars: Dict[str, str] = {
        "BREADWINNER_LLM_PROVIDER": selected_provider,
        "PORTFOLIO_PATH": portfolio_input,
        "DEFAULT_PERSONA": "tech_ai",
        "DEFAULT_TEMPLATE": "jakes",
        "AUTO_GENERATE_PDF": "true",
    }

    # -------------------------------------------------------------
    # Step 3: Provider-specific configuration & credentials
    # -------------------------------------------------------------
    console.print(f"\n[bold cyan]Step 3: Configure {selected_provider.upper()}[/bold cyan]")

    if selected_provider == "gemini":
        console.print("[dim]Get a free key from: https://aistudio.google.com/app/apikey[/dim]")
        key = Prompt.ask("Enter your Google Gemini API key", password=True)
        model = Prompt.ask("Select model", default="gemini-2.5-flash")
        env_vars["GEMINI_API_KEY"] = key.strip()
        env_vars["GEMINI_MODEL"] = model.strip()

    elif selected_provider == "deepseek":
        console.print("[dim]Get an API key from: https://platform.deepseek.com[/dim]")
        key = Prompt.ask("Enter your DeepSeek API key", password=True)
        model = Prompt.ask("Select model (deepseek-chat or deepseek-reasoner)", default="deepseek-chat")
        env_vars["DEEPSEEK_API_KEY"] = key.strip()
        env_vars["DEEPSEEK_MODEL"] = model.strip()

    elif selected_provider == "lmstudio":
        url = Prompt.ask("LM Studio Base URL", default="http://localhost:1234/v1")
        model = Prompt.ask("Model ID loaded in LM Studio", default="local-model")
        env_vars["LMSTUDIO_BASE_URL"] = url.strip()
        env_vars["LMSTUDIO_MODEL"] = model.strip()

    elif selected_provider == "groq":
        console.print("[dim]Get an API key from: https://console.groq.com/keys[/dim]")
        key = Prompt.ask("Enter your Groq API key", password=True)
        model = Prompt.ask("Select model", default="llama-3.3-70b-versatile")
        env_vars["GROQ_API_KEY"] = key.strip()
        env_vars["GROQ_MODEL"] = model.strip()

    elif selected_provider == "ollama":
        url = Prompt.ask("Ollama Base URL", default="http://localhost:11434/v1")
        model = Prompt.ask("Ollama model name", default="llama3.2")
        env_vars["OLLAMA_BASE_URL"] = url.strip()
        env_vars["OLLAMA_MODEL"] = model.strip()

    # -------------------------------------------------------------
    # Step 4: Write .env with strict security permissions
    # -------------------------------------------------------------
    existing_env: Dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing_env[k.strip()] = v.strip().strip('"').strip("'")

    existing_env.update(env_vars)

    env_lines = [
        "# Breadwinner Configuration (Auto-generated by setup wizard)",
        "# Permissions: 0600 (Private)",
        ""
    ]
    for k, v in existing_env.items():
        env_lines.append(f'{k}="{v}"')

    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # Set strict 0600 file permissions
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

    console.print(Panel(
        f"[bold green]✓ Setup Complete![/bold green]\n\n"
        f"• [cyan]Intelligence Engine:[/cyan] {selected_provider.upper()}\n"
        f"• [cyan]Portfolio Source:[/cyan] {portfolio_input}\n"
        f"• [cyan]Config Saved To:[/cyan] {env_path.resolve()} (chmod 0600)\n\n"
        f"[bold]Ready to bake your first application:[/bold]\n"
        f"  [yellow]breadwinner apply --url <job_url>[/yellow]  (CLI mode)\n"
        f"  [yellow]breadwinner ui[/yellow]                     (Interactive Studio)\n",
        border_style="green",
        title="[bold green]Bakery Open For Business 🍞[/bold green]"
    ))

    return True
