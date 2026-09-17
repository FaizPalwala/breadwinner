"""Factory for resolving and instantiating the requested LLM provider."""

import json
from typing import Optional, Dict, Any

from breadwinner.config import settings
from breadwinner.providers.base import BaseLLMProvider
from breadwinner.providers.openai_compatible import OpenAICompatibleProvider


class MockLLMProvider(BaseLLMProvider):
    """Offline mock provider for testing and environments without an active API key."""

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        return (
            "Dear Hiring Team,\n\n"
            "I am writing to express my strong interest in this role. With extensive engineering experience "
            "scaling distributed platforms in production and a solid foundation in computer science, "
            "I look forward to contributing to your team's technical goals.\n\n"
            "Sincerely,\nCandidate"
        )


    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        return {
            "match_score": 88,
            "matched_skills": ["Python", "Java", "Distributed Systems", "Cloud", "Agile"],
            "missing_skills": ["Kafka", "GraphQL"],
            "rationale": "Candidate has strong engineering background matching 88% of core requirements.",
            "strategic_recommendations": [
                "Highlight distributed systems and backend engineering experience.",
                "Emphasize relevant technical projects and quantitative impact."
            ],
            "tailored_summary": (
                "Software Engineer with experience architecting reliable distributed services and backend platforms. "
                "Specializing in scalable architecture, data pipelines, and high availability."
            ),
            "tailored_bullets": [
                "Delivered end-to-end platform features and resolved critical production incidents across release cycles.",
                "Architected data remediation pipelines processing high-volume record ingestion with zero data loss.",
                "Built distributed backend services maintaining high availability and extensive automated test coverage."
            ],
            "portal_answers": {
                "why_us": "Your team's mission and engineering challenges align with my background in building resilient software systems.",
                "challenge": "Architected an automated remediation workflow to resolve systemic validation errors, reducing failure backlog by 40%."
            }
        }



def get_llm_provider(
    provider_name: Optional[str] = None,
    model_override: Optional[str] = None
) -> BaseLLMProvider:
    """Instantiate and return the configured LLM provider."""
    provider = (provider_name or settings.breadwinner_llm_provider).lower()

    if provider == "gemini":
        key = settings.gemini_api_key
        # Gemini provides standard OpenAI compatibility endpoint
        return OpenAICompatibleProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=key or "missing-key",
            model=model_override or settings.gemini_model
        )

    elif provider == "lmstudio":
        return OpenAICompatibleProvider(
            base_url=settings.lmstudio_base_url,
            api_key="lm-studio",
            model=model_override or settings.lmstudio_model
        )

    elif provider == "groq":
        return OpenAICompatibleProvider(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key or "missing-key",
            model=model_override or settings.groq_model
        )

    elif provider == "ollama":
        return OpenAICompatibleProvider(
            base_url=settings.ollama_base_url,
            api_key="ollama",
            model=model_override or settings.ollama_model
        )

    elif provider == "openai":
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key or "missing-key",
            model=model_override or settings.openai_model
        )

    elif provider == "deepseek":
        return OpenAICompatibleProvider(
            base_url="https://api.deepseek.com",
            api_key=settings.deepseek_api_key or "missing-key",
            model=model_override or settings.deepseek_model
        )

    elif provider == "mock":
        return MockLLMProvider()


    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
