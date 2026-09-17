"""Provider and model auto-discovery service."""

import re
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from breadwinner.config import settings


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    is_active: bool = False
    description: Optional[str] = None


class ProviderStatus(BaseModel):
    name: str
    slug: str
    is_available: bool
    status_text: str  # e.g. "🟢 Online", "⚪ Missing API Key", "🔴 Offline"
    base_url: Optional[str] = None
    models: List[ModelInfo] = []
    active_model: Optional[str] = None


class ProviderDiscovery:
    """Discovers available LLM providers, health, and currently loaded models."""

    @classmethod
    def discover_all(cls) -> List[ProviderStatus]:
        """Discover all supported providers and their models."""
        results = []
        results.append(cls.check_lmstudio())
        results.append(cls.check_deepseek())
        results.append(cls.check_gemini())
        results.append(cls.check_groq())
        results.append(cls.check_ollama())
        results.append(cls.check_mock())
        return results


    @classmethod
    def check_lmstudio(cls) -> ProviderStatus:
        """Check LM Studio local server and discover loaded models."""
        base_url = settings.lmstudio_base_url.rstrip("/")
        models_url = f"{base_url}/models"
        is_active_provider = settings.breadwinner_llm_provider == "lmstudio"
        
        try:
            resp = requests.get(models_url, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", [])
                models = [
                    ModelInfo(
                        id=m["id"],
                        name=m["id"].split("/")[-1],
                        provider="lmstudio",
                        is_active=(is_active_provider and m["id"] == settings.lmstudio_model)
                    )
                    for m in raw_models if isinstance(m, dict) and "id" in m
                ]
                # If active model not in list or default 'local-model', mark first as active
                if is_active_provider and models and not any(m.is_active for m in models):
                    models[0].is_active = True

                active_id = next((m.id for m in models if m.is_active), (models[0].id if models else None))
                return ProviderStatus(
                    name="LM Studio (Local M4/PC)",
                    slug="lmstudio",
                    is_available=True,
                    status_text="🟢 Online (Local)",
                    base_url=base_url,
                    models=models,
                    active_model=active_id
                )
        except Exception:
            pass

        return ProviderStatus(
            name="LM Studio (Local M4/PC)",
            slug="lmstudio",
            is_available=False,
            status_text="🔴 Offline (Server not started)",
            base_url=base_url,
            models=[]
        )

    @classmethod
    def check_deepseek(cls) -> ProviderStatus:
        """Check DeepSeek API configuration."""
        key_configured = bool(settings.deepseek_api_key and settings.deepseek_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "deepseek"

        known_models = [
            ("deepseek-chat", "DeepSeek-V3 (High-throughput reasoning & coding)"),
            ("deepseek-reasoner", "DeepSeek-R1 (Chain-of-thought reasoning model)")
        ]

        models = [
            ModelInfo(
                id=mid,
                name=mname,
                provider="deepseek",
                is_active=(is_active_provider and mid == settings.deepseek_model),
                description=mname
            )
            for mid, mname in known_models
        ]

        status_text = "🟢 Configured (DeepSeek Key)" if key_configured else "⚪ Missing DEEPSEEK_API_KEY in .env"
        return ProviderStatus(
            name="DeepSeek",
            slug="deepseek",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.deepseek_model if key_configured else None
        )

    @classmethod
    def check_gemini(cls) -> ProviderStatus:
        """Check Google Gemini API configuration."""
        key_configured = bool(settings.gemini_api_key and settings.gemini_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "gemini"

        known_models = [
            ("gemini-2.5-flash", "Gemini 2.5 Flash (Fastest, 1M context)"),
            ("gemini-1.5-flash", "Gemini 1.5 Flash (Ultra-low latency)"),
            ("gemini-1.5-pro", "Gemini 1.5 Pro (Deep reasoning)")
        ]

        models = [
            ModelInfo(
                id=mid,
                name=mname,
                provider="gemini",
                is_active=(is_active_provider and mid == settings.gemini_model),
                description=mname
            )
            for mid, mname in known_models
        ]

        status_text = "🟢 Configured (AI Studio Key)" if key_configured else "⚪ Missing GEMINI_API_KEY in .env"
        return ProviderStatus(
            name="Google Gemini",
            slug="gemini",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.gemini_model if key_configured else None
        )

    @classmethod
    def check_groq(cls) -> ProviderStatus:
        """Check Groq Cloud configuration."""
        key_configured = bool(settings.groq_api_key and settings.groq_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "groq"

        known_models = [
            ("llama-3.3-70b-versatile", "Llama 3.3 70B (High speed)"),
            ("qwen-2.5-32b", "Qwen 2.5 32B (Advanced reasoning)"),
            ("llama-3.1-8b-instant", "Llama 3.1 8B (Sub-second speed)")
        ]

        models = [
            ModelInfo(
                id=mid,
                name=mname,
                provider="groq",
                is_active=(is_active_provider and mid == settings.groq_model)
            )
            for mid, mname in known_models
        ]

        status_text = "🟢 Configured (Groq Key)" if key_configured else "⚪ Missing GROQ_API_KEY in .env"
        return ProviderStatus(
            name="Groq Cloud",
            slug="groq",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.groq_model if key_configured else None
        )


    @classmethod
    def check_ollama(cls) -> ProviderStatus:
        """Check local Ollama server."""
        base_url = settings.ollama_base_url.rstrip("/")
        is_active_provider = settings.breadwinner_llm_provider == "ollama"

        try:
            resp = requests.get(f"{base_url}/tags", timeout=1.0)
            if resp.status_code == 200:
                raw_models = resp.json().get("models", [])
                models = [
                    ModelInfo(
                        id=m["name"],
                        name=m["name"],
                        provider="ollama",
                        is_active=(is_active_provider and m["name"] == settings.ollama_model)
                    )
                    for m in raw_models
                ]
                return ProviderStatus(
                    name="Ollama (Local)",
                    slug="ollama",
                    is_available=True,
                    status_text="🟢 Online (Local)",
                    base_url=base_url,
                    models=models,
                    active_model=settings.ollama_model
                )
        except Exception:
            pass

        return ProviderStatus(
            name="Ollama (Local)",
            slug="ollama",
            is_available=False,
            status_text="🔴 Offline",
            base_url=base_url,
            models=[]
        )

    @classmethod
    def check_mock(cls) -> ProviderStatus:
        """Always-available offline mock provider."""
        is_active_provider = settings.breadwinner_llm_provider == "mock"
        return ProviderStatus(
            name="Offline Mock (Zero Network)",
            slug="mock",
            is_available=True,
            status_text="🟢 Ready (Unit Tests & Offline)",
            models=[ModelInfo(id="mock-deterministic", name="Mock Engine", provider="mock", is_active=is_active_provider)],
            active_model="mock-deterministic" if is_active_provider else None
        )

    @classmethod
    def switch_model(cls, provider_slug: str, model_id: Optional[str] = None) -> bool:
        """Update active provider and model in .env and runtime settings."""
        env_file = Path(".env")
        if not env_file.exists():
            env_file.write_text("# Breadwinner Config\n", encoding="utf-8")

        lines = env_file.read_text(encoding="utf-8").splitlines()
        updated_lines = []
        
        provider_set = False
        model_set = False

        model_env_keys = {
            "lmstudio": "LMSTUDIO_MODEL",
            "deepseek": "DEEPSEEK_MODEL",
            "gemini": "GEMINI_MODEL",
            "groq": "GROQ_MODEL",
            "ollama": "OLLAMA_MODEL",
            "openai": "OPENAI_MODEL"
        }
        target_model_key = model_env_keys.get(provider_slug.lower())

        for line in lines:
            if line.startswith("BREADWINNER_LLM_PROVIDER="):
                updated_lines.append(f"BREADWINNER_LLM_PROVIDER={provider_slug.lower()}")
                provider_set = True
            elif target_model_key and line.startswith(f"{target_model_key}=") and model_id:
                updated_lines.append(f"{target_model_key}={model_id}")
                model_set = True
            else:
                updated_lines.append(line)

        if not provider_set:
            updated_lines.append(f"BREADWINNER_LLM_PROVIDER={provider_slug.lower()}")
        if target_model_key and model_id and not model_set:
            updated_lines.append(f"{target_model_key}={model_id}")

        env_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

        # Update runtime
        settings.breadwinner_llm_provider = provider_slug.lower()
        if target_model_key and model_id:
            if provider_slug == "lmstudio":
                settings.lmstudio_model = model_id
            elif provider_slug == "deepseek":
                settings.deepseek_model = model_id
            elif provider_slug == "gemini":
                settings.gemini_model = model_id
            elif provider_slug == "groq":
                settings.groq_model = model_id
            elif provider_slug == "ollama":
                settings.ollama_model = model_id

        return True

