"""OpenAI-compatible LLM provider implementation for Gemini, LM Studio, Groq, Ollama, and OpenAI."""

import json
import re
from typing import Optional, Dict, Any
from openai import OpenAI

from breadwinner.providers.base import BaseLLMProvider


class OpenAICompatibleProvider(BaseLLMProvider):
    """Universal provider for all OpenAI-compatible endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: float = 60.0
    ):
        self.base_url = base_url
        self.api_key = api_key or "not-needed"
        self.model = model
        self.timeout = timeout
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )

    def _call_with_retry(self, **kwargs):
        import time
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                err_str = str(e).lower()
                is_transient = "503" in err_str or "429" in err_str or "high demand" in err_str or "rate limit" in err_str
                if is_transient and attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self._call_with_retry(
            model=self.model,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content or ""

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        system_with_json = f"{system_prompt}\n\nIMPORTANT: You must respond ONLY with valid JSON. Do not wrap in markdown or prose unless inside JSON strings."
        messages = [
            {"role": "system", "content": system_with_json},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Try response_format if supported
            response = self._call_with_retry(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception:
            # Fallback without response_format (some local models / older endpoints don't support it)
            response = self._call_with_retry(
                model=self.model,
                messages=messages,
                temperature=0.1
            )
            content = response.choices[0].message.content or "{}"
            return self._extract_json(content)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON even if model surrounded it with markdown fences."""
        # Try raw
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try regex search for code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding outer braces
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        return {"error": "Failed to parse JSON", "raw": text}
