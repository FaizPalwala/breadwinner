"""Declarative registry of supported AI providers for Breadwinner.

Serves as the single source of truth for provider metadata, environment variables,
pills, hints, documentation links, and default model settings.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from breadwinner.config import settings


@dataclass(frozen=True)
class ProviderSpec:
    slug: str
    name: str
    pill_label: str
    category: str  # "cloud", "gateway", "local", "mock"
    env_var: Optional[str] = None
    settings_key_attr: Optional[str] = None
    settings_model_attr: Optional[str] = None
    key_placeholder: str = "Enter API Key..."
    key_url: Optional[str] = None
    hint_text: str = ""
    mascot_msg: str = ""
    is_local: bool = False
    requires_key: bool = True


PROVIDERS_REGISTRY: List[ProviderSpec] = [
    ProviderSpec(
        slug="gemini",
        name="Google Gemini",
        pill_label="Gemini",
        category="cloud",
        env_var="GEMINI_API_KEY",
        settings_key_attr="gemini_api_key",
        settings_model_attr="gemini_model",
        key_placeholder="Enter Google Gemini API Key (AIzaSy...)",
        key_url="https://aistudio.google.com/app/apikey",
        hint_text="[dim]Free API key: [underline]https://aistudio.google.com/app/apikey[/underline] (Free 15 RPM)[/dim]",
        mascot_msg="Google Gemini selected! Generous free tier and ultra-high quality.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="openrouter",
        name="OpenRouter",
        pill_label="OpenRouter",
        category="gateway",
        env_var="OPENROUTER_API_KEY",
        settings_key_attr="openrouter_api_key",
        settings_model_attr="openrouter_model",
        key_placeholder="Enter OpenRouter API Key (sk-or-...)",
        key_url="https://openrouter.ai/keys",
        hint_text="[dim]Universal Gateway key: [underline]https://openrouter.ai/keys[/underline] (Access 300+ models)[/dim]",
        mascot_msg="OpenRouter selected! Universal access to Claude, GPT, DeepSeek, and Llama.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="anthropic",
        name="Anthropic Claude",
        pill_label="Claude",
        category="cloud",
        env_var="ANTHROPIC_API_KEY",
        settings_key_attr="anthropic_api_key",
        settings_model_attr="anthropic_model",
        key_placeholder="Enter Anthropic Claude API Key (sk-ant-...)",
        key_url="https://console.anthropic.com/settings/keys",
        hint_text="[dim]Anthropic API key: [underline]https://console.anthropic.com/settings/keys[/underline][/dim]",
        mascot_msg="Anthropic Claude selected! Gold standard career narrative reasoning.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="openai",
        name="OpenAI",
        pill_label="OpenAI",
        category="cloud",
        env_var="OPENAI_API_KEY",
        settings_key_attr="openai_api_key",
        settings_model_attr="openai_model",
        key_placeholder="Enter OpenAI API Key (sk-proj-...)",
        key_url="https://platform.openai.com/api-keys",
        hint_text="[dim]OpenAI API key: [underline]https://platform.openai.com/api-keys[/underline][/dim]",
        mascot_msg="OpenAI selected! Flagship GPT-4o intelligence and reasoning models.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="deepseek",
        name="DeepSeek",
        pill_label="DeepSeek",
        category="cloud",
        env_var="DEEPSEEK_API_KEY",
        settings_key_attr="deepseek_api_key",
        settings_model_attr="deepseek_model",
        key_placeholder="Enter DeepSeek API Key (sk-...)",
        key_url="https://platform.deepseek.com",
        hint_text="[dim]DeepSeek API key: [underline]https://platform.deepseek.com[/underline] (V3 & R1 models)[/dim]",
        mascot_msg="DeepSeek selected! Ultra-low cost frontier reasoning.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="groq",
        name="Groq Cloud",
        pill_label="Groq",
        category="cloud",
        env_var="GROQ_API_KEY",
        settings_key_attr="groq_api_key",
        settings_model_attr="groq_model",
        key_placeholder="Enter Groq API Key (gsk_...)",
        key_url="https://console.groq.com/keys",
        hint_text="[dim]Free Groq API key: [underline]https://console.groq.com/keys[/underline] (Llama 3.3)[/dim]",
        mascot_msg="Groq Cloud selected! Ultra-fast inference speeds.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="mistral",
        name="Mistral AI",
        pill_label="Mistral",
        category="cloud",
        env_var="MISTRAL_API_KEY",
        settings_key_attr="mistral_api_key",
        settings_model_attr="mistral_model",
        key_placeholder="Enter Mistral API Key (API key...)",
        key_url="https://console.mistral.ai/api-keys",
        hint_text="[dim]Mistral API key: [underline]https://console.mistral.ai/api-keys[/underline][/dim]",
        mascot_msg="Mistral AI selected! Premier open-weights frontier reasoning.",
        is_local=False,
        requires_key=True,
    ),
    ProviderSpec(
        slug="ollama",
        name="Ollama (Local)",
        pill_label="Ollama",
        category="local",
        env_var=None,
        settings_key_attr=None,
        settings_model_attr="ollama_model",
        key_placeholder="No API key required for local server",
        key_url="http://localhost:11434/v1",
        hint_text="[dim]Local inference via Ollama at [underline]http://localhost:11434/v1[/underline][/dim]",
        mascot_msg="Ollama selected! Local open-source models running on localhost.",
        is_local=True,
        requires_key=False,
    ),
    ProviderSpec(
        slug="lmstudio",
        name="LM Studio (Local)",
        pill_label="LM Studio",
        category="local",
        env_var=None,
        settings_key_attr=None,
        settings_model_attr="lmstudio_model",
        key_placeholder="No API key required for local server",
        key_url="http://localhost:1234/v1",
        hint_text="[dim]Local inference via LM Studio at [underline]http://localhost:1234/v1[/underline][/dim]",
        mascot_msg="LM Studio selected! 100% offline local privacy on your hardware.",
        is_local=True,
        requires_key=False,
    ),
    ProviderSpec(
        slug="mock",
        name="Offline Mock",
        pill_label="Mock",
        category="mock",
        env_var=None,
        settings_key_attr=None,
        settings_model_attr=None,
        key_placeholder="No API key required (Mock Test Drive)",
        key_url=None,
        hint_text="[dim]Instant testing mode without any API keys or network connection[/dim]",
        mascot_msg="Offline Mock selected! Perfect for an instant zero-setup test drive.",
        is_local=True,
        requires_key=False,
    ),

]


_SPECS_BY_SLUG: Dict[str, ProviderSpec] = {spec.slug: spec for spec in PROVIDERS_REGISTRY}


def get_provider_specs() -> List[ProviderSpec]:
    """Return all registered provider specifications."""
    return list(PROVIDERS_REGISTRY)


def get_provider_spec(slug: str) -> Optional[ProviderSpec]:
    """Retrieve spec for a given provider slug."""
    return _SPECS_BY_SLUG.get(slug.lower().strip())


def get_provider_options() -> List[Tuple[str, str]]:
    """Return list of (display_name, slug) tuples for dropdown selectors."""
    return [(spec.name, spec.slug) for spec in PROVIDERS_REGISTRY]


def get_provider_env_vars() -> Dict[str, str]:
    """Map provider slugs to their environment variable names."""
    return {spec.slug: spec.env_var for spec in PROVIDERS_REGISTRY if spec.env_var}


def get_configured_initial_keys() -> Dict[str, str]:
    """Read currently configured API keys from application settings."""
    keys: Dict[str, str] = {}
    for spec in PROVIDERS_REGISTRY:
        if spec.settings_key_attr:
            val = getattr(settings, spec.settings_key_attr, None)
            if val and str(val).strip():
                keys[spec.slug] = str(val).strip()
    return keys
