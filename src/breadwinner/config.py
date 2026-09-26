"""Configuration module for Breadwinner using Pydantic Settings."""

from pathlib import Path
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Provider
    breadwinner_llm_provider: Literal[
        "gemini", "openrouter", "anthropic", "openai", "deepseek", "groq", "mistral", "lmstudio", "ollama", "mock"
    ] = "gemini"

    # Google Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

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
    portfolio_path: Path = Path("./portfolio")
    pantry_dir: Path = Path("./pantry")

    # Personas & Templates
    default_persona: str = "tech_ai"
    default_template: str = "jakes"

    # Storage paths
    applications_dir: Path = Path("./applications")
    database_path: Path = Path("./tracker.db")
    csv_tracker_path: Optional[Path] = Path("./job_tracker.csv")

    # PDF & Browser
    browser_path: Optional[str] = None
    auto_generate_pdf: bool = True


settings = Settings()


def save_env_config(env_vars: dict, env_path: Optional[Path] = None) -> None:
    """Save or update configuration key-values in .env with private 0600 file permissions."""
    import os
    import stat

    path = env_path or Path(".env")
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

    for k, v in env_vars.items():
        os.environ[k] = str(v)

    global settings
    settings = Settings()
