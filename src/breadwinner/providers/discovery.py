"""Provider and model auto-discovery service."""

import re
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel

from breadwinner.config import settings


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    is_active: bool = False
    description: Optional[str] = None


COMMON_EXCLUDED_PATTERNS = [
    r"tts", r"audio", r"voice", r"transcribe", r"whisper", r"lyria",
    r"image", r"banana", r"imagen", r"dall-e", r"veo", r"video",
    r"embed", r"embedding", r"moderation", r"clip", r"robotics",
    r"computer-use", r"reward", r"rerank", r"aqa", r"realtime",
    r"preview-customtools", r"antigravity-preview", r"deep-research"
]

DEPRECATED_MODELS = {
    # Gemini retired models that return 404
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-image",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    # OpenAI retired / completion-only models
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
    "davinci-002",
    "babbage-002",
}

# Backward compatibility alias
DEPRECATED_GEMINI_MODELS = DEPRECATED_MODELS


def is_usable_chat_model(model_id: str, supported_methods: Optional[List[str]] = None) -> bool:
    """Determine whether a model is suitable for Breadwinner's text/chat/JSON workflow.
    
    Excludes:
    - Deprecated models returning 404
    - Text-to-speech (TTS), audio, transcription, and whisper models
    - Image and video generation models (Imagen, Dall-E, Veo, Banana)
    - Embedding and vector representations
    - Robotics, computer-use, and internal agent test harnesses
    """
    mid = model_id.lower().replace("models/", "")

    if mid in DEPRECATED_MODELS:
        return False

    if supported_methods is not None and len(supported_methods) > 0:
        if "generateContent" not in supported_methods and "chat" not in supported_methods:
            return False

    for pat in COMMON_EXCLUDED_PATTERNS:
        if re.search(r'(^|[-_./])' + pat + r'([-_./]|$)', mid) or pat in mid:
            return False

    return True


class ProviderStatus(BaseModel):
    name: str
    slug: str
    is_available: bool
    status_text: str  # e.g. "🟢 Online", "⚪ Missing API Key", "🔴 Offline"
    base_url: Optional[str] = None
    models: List[ModelInfo] = []
    active_model: Optional[str] = None


PROVIDER_MODELS: Dict[str, List[Tuple[str, str]]] = {
    "gemini": [
        ("Gemini 3.8 Flash (Fastest, latest generation - Recommended)", "gemini-3.8-flash"),
        ("Gemini 3.5 Flash (High throughput & reliable)", "gemini-3.5-flash"),
        ("Gemini Flash Latest (Dynamic latest alias)", "gemini-flash-latest"),
        ("Gemini Flash-Lite Latest (Ultra-fast, lowest latency)", "gemini-flash-lite-latest"),
    ],
    "openrouter": [
        ("Claude 3.7 Sonnet (Anthropic flagship via OpenRouter)", "anthropic/claude-3.7-sonnet"),
        ("Claude 3.5 Sonnet (High intelligence via OpenRouter)", "anthropic/claude-3.5-sonnet"),
        ("GPT-4o (OpenAI flagship via OpenRouter)", "openai/gpt-4o"),
        ("Gemini 2.0 Flash (Google via OpenRouter)", "google/gemini-2.0-flash-001"),
        ("DeepSeek R1 (Chain of thought logic via OpenRouter)", "deepseek/deepseek-r1"),
        ("Llama 3.3 70B (Meta open weights via OpenRouter)", "meta-llama/llama-3.3-70b-instruct"),
    ],
    "anthropic": [
        ("Claude 3.7 Sonnet (Hybrid fast/extended reasoning - Recommended)", "claude-3-7-sonnet-20250219"),
        ("Claude 3.5 Sonnet (Gold standard prose & precision)", "claude-3-5-sonnet-20241022"),
        ("Claude 3.5 Haiku (Fast & affordable lightweight model)", "claude-3-5-haiku-20241022"),
    ],
    "openai": [
        ("GPT-4o (Flagship multimodal intelligence - Recommended)", "gpt-4o"),
        ("GPT-4o Mini (High-speed & cost-efficient)", "gpt-4o-mini"),
        ("o3-mini (High-speed STEM & logic reasoning)", "o3-mini"),
        ("o1 (Deep analytical complex reasoning)", "o1"),
    ],
    "deepseek": [
        ("DeepSeek-V3 Chat (Fast reasoning & coding - Default)", "deepseek-chat"),
        ("DeepSeek-R1 Reasoner (Chain-of-thought logic)", "deepseek-reasoner"),
    ],
    "groq": [
        ("Llama 3.3 70B Versatile (Ultra-fast - Default)", "llama-3.3-70b-versatile"),
        ("Llama 3.1 8B Instant (Sub-second speed)", "llama-3.1-8b-instant"),
        ("Qwen 2.5 32B (Advanced reasoning)", "qwen-2.5-32b"),
    ],
    "mistral": [
        ("Mistral Large (Premier frontier reasoning)", "mistral-large-latest"),
        ("Codestral (State-of-the-art coding)", "codestral-latest"),
        ("Mistral Small (Fast & responsive)", "mistral-small-latest"),
    ],
    "lmstudio": [
        ("local-model (Active loaded model in LM Studio)", "local-model"),
    ],
    "ollama": [
        ("llama3.2 (Standard Llama 3.2)", "llama3.2"),
        ("qwen2.5-coder (Qwen 2.5 Coder)", "qwen2.5-coder"),
        ("deepseek-r1 (DeepSeek R1 Distill)", "deepseek-r1"),
    ],
    "mock": [
        ("mock-deterministic (Offline Anti-Slop Engine)", "mock-deterministic"),
    ],
}


class ProviderDiscovery:
    """Discovers available LLM providers, health, and currently loaded models."""

    @classmethod
    def discover_all(cls) -> List[ProviderStatus]:
        """Discover all supported providers and their models."""
        results = []
        results.append(cls.check_gemini())
        results.append(cls.check_openrouter())
        results.append(cls.check_anthropic())
        results.append(cls.check_openai())
        results.append(cls.check_deepseek())
        results.append(cls.check_groq())
        results.append(cls.check_mistral())
        results.append(cls.check_lmstudio())
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
        """Check DeepSeek API configuration and dynamically fetch available models."""
        key_configured = bool(settings.deepseek_api_key and settings.deepseek_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "deepseek"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {settings.deepseek_api_key.strip()}"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("id", "")
                            if is_usable_chat_model(mid):
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mid,
                                    provider="deepseek",
                                    is_active=(is_active_provider and mid == settings.deepseek_model),
                                    description=f"DeepSeek {mid}"
                                ))
            except Exception:
                pass

        if not models:
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
        """Check Google Gemini API configuration and dynamically discover available text/chat models."""
        key_configured = bool(settings.gemini_api_key and settings.gemini_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "gemini"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.gemini_api_key.strip()}",
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("models", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("name", "").replace("models/", "")
                            methods = m.get("supportedGenerationMethods", [])
                            if is_usable_chat_model(mid, methods):
                                mname = m.get("displayName", mid)
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mname,
                                    provider="gemini",
                                    is_active=(is_active_provider and mid == settings.gemini_model),
                                    description=m.get("description", mname)
                                ))
                    
                    def _gemini_sort_rank(m_info: ModelInfo) -> Tuple[int, str]:
                        mid = m_info.id.lower()
                        if "3.8-flash" in mid:
                            return (0, mid)
                        if "3.7-flash" in mid:
                            return (1, mid)
                        if "3.6-flash" in mid:
                            return (2, mid)
                        if "3.5-flash" in mid:
                            return (3, mid)
                        if "flash-latest" in mid:
                            return (4, mid)
                        if "flash-lite-latest" in mid:
                            return (5, mid)
                        if "pro-latest" in mid:
                            return (6, mid)
                        if "flash" in mid:
                            return (7, mid)
                        if "pro" in mid:
                            return (8, mid)
                        return (9, mid)

                    models.sort(key=_gemini_sort_rank)
            except Exception:
                pass

        if not models:
            known_models = PROVIDER_MODELS.get("gemini", [
                ("Gemini 3.8 Flash (Fastest, latest generation - Recommended)", "gemini-3.8-flash"),
                ("Gemini 3.5 Flash (High throughput & reliable)", "gemini-3.5-flash"),
                ("Gemini Flash Latest (Dynamic latest alias)", "gemini-flash-latest"),
                ("Gemini Flash-Lite Latest (Ultra-fast, lowest latency)", "gemini-flash-lite-latest"),
            ])
            models = [
                ModelInfo(
                    id=mid,
                    name=mname,
                    provider="gemini",
                    is_active=(is_active_provider and mid == settings.gemini_model),
                    description=mname
                )
                for mname, mid in known_models
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
        """Check Groq Cloud configuration and dynamically fetch available models."""
        key_configured = bool(settings.groq_api_key and settings.groq_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "groq"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {settings.groq_api_key.strip()}"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("id", "")
                            if is_usable_chat_model(mid):
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mid,
                                    provider="groq",
                                    is_active=(is_active_provider and mid == settings.groq_model),
                                    description=f"Groq {mid}"
                                ))
                    def _groq_sort_rank(m_info: ModelInfo) -> Tuple[int, str]:
                        mid = m_info.id.lower()
                        if "llama-3.3-70b" in mid: return (0, mid)
                        if "qwen-2.5-32b" in mid: return (1, mid)
                        if "llama-3.1-8b" in mid: return (2, mid)
                        return (3, mid)
                    models.sort(key=_groq_sort_rank)
            except Exception:
                pass

        if not models:
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
    def check_openrouter(cls) -> ProviderStatus:
        """Check OpenRouter multi-model gateway configuration and dynamically discover models."""
        key_configured = bool(settings.openrouter_api_key and settings.openrouter_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "openrouter"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {settings.openrouter_api_key.strip()}"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("id", "")
                            if is_usable_chat_model(mid):
                                mname = m.get("name", mid)
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mname,
                                    provider="openrouter",
                                    is_active=(is_active_provider and mid == settings.openrouter_model),
                                    description=m.get("description", mname)
                                ))
                    models = models[:20]  # Cap at top 20 active models
            except Exception:
                pass

        if not models:
            known_models = [
                ("anthropic/claude-3.7-sonnet", "Claude 3.7 Sonnet (Anthropic flagship)"),
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (High intelligence)"),
                ("openai/gpt-4o", "GPT-4o (OpenAI Omni flagship)"),
                ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash (Fast & reliable)"),
                ("deepseek/deepseek-r1", "DeepSeek R1 (Chain of thought logic)"),
                ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B (Open weights)"),
            ]
            models = [
                ModelInfo(
                    id=mid,
                    name=mname,
                    provider="openrouter",
                    is_active=(is_active_provider and mid == settings.openrouter_model),
                    description=mname
                )
                for mid, mname in known_models
            ]

        status_text = "🟢 Configured (OpenRouter Key)" if key_configured else "⚪ Missing OPENROUTER_API_KEY in .env"
        return ProviderStatus(
            name="OpenRouter (Universal Gateway)",
            slug="openrouter",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.openrouter_model if key_configured else None
        )

    @classmethod
    def check_anthropic(cls) -> ProviderStatus:
        """Check Anthropic Claude API configuration."""
        key_configured = bool(settings.anthropic_api_key and settings.anthropic_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "anthropic"

        known_models = [
            ("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet (Flagship hybrid reasoning)"),
            ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet (Gold standard prose)"),
            ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku (Fast & affordable)")
        ]

        models = [
            ModelInfo(
                id=mid,
                name=mname,
                provider="anthropic",
                is_active=(is_active_provider and mid == settings.anthropic_model),
                description=mname
            )
            for mid, mname in known_models
        ]

        status_text = "🟢 Configured (Anthropic Key)" if key_configured else "⚪ Missing ANTHROPIC_API_KEY in .env"
        return ProviderStatus(
            name="Anthropic Claude",
            slug="anthropic",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.anthropic_model if key_configured else None
        )

    @classmethod
    def check_openai(cls) -> ProviderStatus:
        """Check OpenAI API configuration and dynamically fetch available models."""
        key_configured = bool(settings.openai_api_key and settings.openai_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "openai"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.openai_api_key.strip()}"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("id", "")
                            if is_usable_chat_model(mid) and any(mid.startswith(pfx) for pfx in ("gpt-", "o1", "o3", "chatgpt-")):
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mid,
                                    provider="openai",
                                    is_active=(is_active_provider and mid == settings.openai_model),
                                    description=f"OpenAI {mid}"
                                ))
                    def _openai_sort_rank(m_info: ModelInfo) -> Tuple[int, str]:
                        mid = m_info.id.lower()
                        if mid == "gpt-4o": return (0, mid)
                        if mid == "gpt-4o-mini": return (1, mid)
                        if mid.startswith("o3-mini"): return (2, mid)
                        if mid.startswith("o1"): return (3, mid)
                        return (4, mid)
                    models.sort(key=_openai_sort_rank)
            except Exception:
                pass

        if not models:
            known_models = [
                ("gpt-4o", "GPT-4o (Flagship omni model)"),
                ("gpt-4o-mini", "GPT-4o Mini (Fast & cost efficient)"),
                ("o3-mini", "o3-mini (High-speed reasoning)"),
                ("o1", "o1 (Deep analytical reasoning)")
            ]
            models = [
                ModelInfo(
                    id=mid,
                    name=mname,
                    provider="openai",
                    is_active=(is_active_provider and mid == settings.openai_model),
                    description=mname
                )
                for mid, mname in known_models
            ]

        status_text = "🟢 Configured (OpenAI Key)" if key_configured else "⚪ Missing OPENAI_API_KEY in .env"
        return ProviderStatus(
            name="OpenAI",
            slug="openai",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.openai_model if key_configured else None
        )

    @classmethod
    def check_mistral(cls) -> ProviderStatus:
        """Check Mistral AI configuration and dynamically fetch available models."""
        key_configured = bool(settings.mistral_api_key and settings.mistral_api_key.strip())
        is_active_provider = settings.breadwinner_llm_provider == "mistral"

        models = []
        if key_configured:
            try:
                resp = requests.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {settings.mistral_api_key.strip()}"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    for m in raw:
                        if isinstance(m, dict):
                            mid = m.get("id", "")
                            if is_usable_chat_model(mid):
                                models.append(ModelInfo(
                                    id=mid,
                                    name=mid,
                                    provider="mistral",
                                    is_active=(is_active_provider and mid == settings.mistral_model),
                                    description=f"Mistral {mid}"
                                ))
            except Exception:
                pass

        if not models:
            known_models = [
                ("mistral-large-latest", "Mistral Large (Premier frontier reasoning)"),
                ("codestral-latest", "Codestral (State of the art coding)"),
                ("mistral-small-latest", "Mistral Small (Fast & responsive)")
            ]
            models = [
                ModelInfo(
                    id=mid,
                    name=mname,
                    provider="mistral",
                    is_active=(is_active_provider and mid == settings.mistral_model),
                    description=mname
                )
                for mid, mname in known_models
            ]

        status_text = "🟢 Configured (Mistral Key)" if key_configured else "⚪ Missing MISTRAL_API_KEY in .env"
        return ProviderStatus(
            name="Mistral AI",
            slug="mistral",
            is_available=key_configured,
            status_text=status_text,
            models=models,
            active_model=settings.mistral_model if key_configured else None
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
            "openai": "OPENAI_MODEL",
            "openrouter": "OPENROUTER_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "mistral": "MISTRAL_MODEL",
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
            elif provider_slug == "openai":
                settings.openai_model = model_id
            elif provider_slug == "openrouter":
                settings.openrouter_model = model_id
            elif provider_slug == "anthropic":
                settings.anthropic_model = model_id
            elif provider_slug == "mistral":
                settings.mistral_model = model_id

        return True

    @classmethod
    def fetch_models_with_status(cls, provider: str, api_key: Optional[str] = None) -> Tuple[List[Tuple[str, str]], bool]:
        """Fetch models for provider, returning (models, is_live_boolean)."""
        prov = provider.lower()
        key = api_key.strip() if api_key else ""
        if not key:
            if prov == "gemini":
                key = settings.gemini_api_key or ""
            elif prov == "deepseek":
                key = settings.deepseek_api_key or ""
            elif prov == "groq":
                key = settings.groq_api_key or ""
            elif prov == "openrouter":
                key = settings.openrouter_api_key or ""
            elif prov == "anthropic":
                key = settings.anthropic_api_key or ""
            elif prov == "openai":
                key = settings.openai_api_key or ""
            elif prov == "mistral":
                key = settings.mistral_api_key or ""

        fallbacks = PROVIDER_MODELS

        if prov == "gemini" and key:
            try:
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("models", [])
                    live = []
                    for m in raw:
                        if isinstance(m, dict) and "generateContent" in m.get("supportedGenerationMethods", []):
                            mid = m["name"].replace("models/", "")
                            if mid.startswith("gemini-") and mid not in DEPRECATED_GEMINI_MODELS:
                                mname = m.get("displayName") or mid
                                live.append((f"{mname} ({mid})", mid))
                    if live:
                        # Prioritize 3.8-flash, 3.5-flash, and flash-latest
                        def _gemini_sort(item: Tuple[str, str]) -> int:
                            m_id = item[1].lower()
                            if "3.8-flash" in m_id:
                                return 0
                            if "3.5-flash" in m_id:
                                return 1
                            if "flash-latest" in m_id:
                                return 2
                            if "3." in m_id and "flash" in m_id:
                                return 3
                            if "3." in m_id:
                                return 4
                            return 10
                        live.sort(key=_gemini_sort)
                        return live, True
            except Exception:
                pass

        elif prov == "openrouter" and key:
            try:
                resp = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = []
                    for m in raw:
                        if isinstance(m, dict) and "id" in m:
                            mid = m["id"]
                            mname = m.get("name") or mid
                            live.append((f"{mname} ({mid})", mid))
                    if live:
                        return live[:40], True
            except Exception:
                pass

        elif prov == "anthropic" and key:
            try:
                resp = requests.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01"
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = [
                        (f"{m.get('display_name', m['id'])} ({m['id']})", m["id"])
                        for m in raw if isinstance(m, dict) and "id" in m
                    ]
                    if live:
                        return live, True
            except Exception:
                pass

        elif prov == "openai" and key:
            try:
                resp = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    valid_prefixes = ("gpt-4", "o1", "o3", "chatgpt")
                    live = [
                        (f"{m['id']}", m["id"])
                        for m in raw if isinstance(m, dict) and any(m.get("id", "").startswith(p) for p in valid_prefixes)
                    ]
                    if live:
                        return sorted(live, key=lambda x: x[1], reverse=True), True
            except Exception:
                pass

        elif prov == "deepseek" and key:
            try:
                resp = requests.get(
                    "https://api.deepseek.com/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = [
                        (f"{m['id']}", m["id"])
                        for m in raw if isinstance(m, dict) and "id" in m
                    ]
                    if live:
                        return live, True
            except Exception:
                pass

        elif prov == "groq" and key:
            try:
                resp = requests.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = [
                        (f"{m['id']}", m["id"])
                        for m in raw if isinstance(m, dict) and "id" in m and not m["id"].startswith("whisper")
                    ]
                    if live:
                        return live, True
            except Exception:
                pass

        elif prov == "mistral" and key:
            try:
                resp = requests.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = [
                        (f"{m['id']}", m["id"])
                        for m in raw if isinstance(m, dict) and "id" in m
                    ]
                    if live:
                        return live, True
            except Exception:
                pass

        elif prov == "lmstudio":
            try:
                base = settings.lmstudio_base_url.rstrip("/")
                resp = requests.get(f"{base}/models", timeout=2.0)
                if resp.status_code == 200:
                    raw = resp.json().get("data", [])
                    live = [(f"{m['id'].split('/')[-1]} ({m['id']})", m["id"]) for m in raw if "id" in m]
                    if live:
                        return live, True
            except Exception:
                pass

        elif prov == "ollama":
            try:
                base = settings.ollama_base_url.rstrip("/")
                resp = requests.get(f"{base}/tags", timeout=2.0)
                if resp.status_code == 200:
                    raw = resp.json().get("models", [])
                    live = [(f"{m['name']}", m["name"]) for m in raw if "name" in m]
                    if live:
                        return live, True
            except Exception:
                pass

        return fallbacks.get(prov, [("Default Model", "default")]), False

    @classmethod
    def fetch_models_for_provider(cls, provider: str, api_key: Optional[str] = None) -> List[Tuple[str, str]]:
        """Fetch live models for a provider or return curated defaults."""
        return cls.fetch_models_with_status(provider, api_key=api_key)[0]

