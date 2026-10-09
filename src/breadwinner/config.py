"""Configuration module for Breadwinner using Pydantic Settings."""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_breadwinner_home() -> Path:
    """Return the canonical home directory for Breadwinner data and configs.

    Precedence:
    1. BREADWINNER_HOME environment variable
    2. ~/.breadwinner
    """
    if os.environ.get("BREADWINNER_HOME"):
        p = Path(os.environ["BREADWINNER_HOME"]).expanduser().resolve()
    else:
        p = (Path.home() / ".breadwinner").resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def _is_readable_file(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as _:
            return True
    except Exception:
        return False


def _resolve_env_files() -> tuple[str, ...]:
    files = []
    try:
        home_env = get_breadwinner_home() / ".env"
        if _is_readable_file(home_env):
            files.append(str(home_env))
    except Exception:
        pass
    local_env = Path(".env").resolve()
    if _is_readable_file(local_env) and str(local_env) not in files:
        files.append(str(local_env))
    return tuple(files) if files else (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Provider
    breadwinner_llm_provider: Literal[
        "gemini", "openrouter", "anthropic", "openai", "deepseek", "groq", "mistral", "lmstudio", "ollama", "mock"
    ] = "gemini"

    # Google Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.8-flash"

    # OpenRouter (Multi-model aggregator)
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-3.7-sonnet"

    # Anthropic Claude
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-7-sonnet-20250219"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # DeepSeek (Reasoning & Chat)
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"

    # Groq Cloud
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Mistral AI
    mistral_api_key: Optional[str] = None
    mistral_model: str = "mistral-large-latest"

    # LM Studio (Local M4 Pro / PC)
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = "local-model"

    # Ollama (Local)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"


    # Portfolio & Sources
    portfolio_path: Path = Field(default_factory=lambda: get_breadwinner_home() / "portfolio")
    pantry_dir: Path = Field(default_factory=lambda: get_breadwinner_home() / "pantry")

    # Personas & Templates
    default_persona: str = "tech_ai"
    default_template: str = "jakes"

    # Storage paths
    applications_dir: Path = Field(default_factory=lambda: get_breadwinner_home() / "applications")
    database_path: Path = Field(default_factory=lambda: get_breadwinner_home() / "tracker.db")
    csv_tracker_path: Optional[Path] = Field(default_factory=lambda: get_breadwinner_home() / "job_tracker.csv")
    user_personas_dir: Path = Field(default_factory=lambda: get_breadwinner_home() / "user_personas")

    # PDF & Browser
    browser_path: Optional[str] = None
    auto_generate_pdf: bool = True

    # UI & Layout Preferences
    navigation_style: str = "auto"  # 'auto', 'sidebar', 'top_deck'
    studio_lab_layout: str = "side_by_side"  # 'side_by_side', 'stacked'
    default_preset: str = "normal"  # 'normal', 'split', 'fullscreen'

    # Voice STT Configuration
    voice_stt_engine: str = "auto"  # 'auto', 'mlx-whisper', 'groq-whisper', 'openai-whisper', 'faster-whisper'
    voice_stt_model: str = "whisper-large-v3-turbo"


settings = Settings()


def save_env_config(env_vars: dict, env_path: Optional[Path] = None) -> None:
    """Save or update configuration key-values in .env with private 0600 file permissions."""
    import os
    import stat

    target_paths: list[Path] = [env_path] if env_path else []
    if not target_paths:
        primary = get_env_path()
        target_paths.append(primary)
        home = get_breadwinner_home() / ".env"
        if home.resolve() != primary.resolve() and home.exists():
            target_paths.append(home)

    for path in target_paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing_env: dict[str, str] = {}
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        existing_env[k.strip()] = v.strip().strip('"').strip("'")

            existing_env.update({k: str(v) for k, v in env_vars.items()})

            env_lines = [
                "# Breadwinner Configuration (Auto-generated)",
                "# Permissions: 0600 (Private)",
                ""
            ]
            for k, v in existing_env.items():
                env_lines.append(f'{k}="{v}"')

            path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            try:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
        except Exception:
            pass

    for k, v in env_vars.items():
        os.environ[k] = str(v)

    global settings
    settings = Settings()


def get_env_path() -> Path:
    """Return the path to the active .env configuration file (local first, fallback to canonical home)."""
    local_env = Path(".env").resolve()
    if local_env.is_file():
        return local_env
    try:
        home_env = get_breadwinner_home() / ".env"
        if home_env.is_file():
            return home_env
    except Exception:
        pass
    # If running directly inside user home directory, prefer home_env to avoid polluting ~
    try:
        if Path.cwd().resolve() == Path.home().resolve():
            return get_breadwinner_home() / ".env"
    except Exception:
        pass
    return local_env


