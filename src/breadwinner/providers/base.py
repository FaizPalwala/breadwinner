"""Base interface for LLM providers in Breadwinner."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseLLMProvider(ABC):
    """Abstract class for all LLM providers (Gemini, LM Studio, Groq, Ollama, Mock)."""

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Generate text completion from prompt."""
        pass

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Generate structured JSON completion from prompt."""
        pass
