"""Direct Anthropic Claude API provider."""

import json
import re
import requests
from typing import Dict, Any, Optional

from breadwinner.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Direct Anthropic API provider (Claude 3.7 / 3.5 Sonnet & Haiku)."""

    def __init__(self, api_key: str, model: str = "claude-3-7-sonnet-20250219"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content_blocks = data.get("content", [])
        text_parts = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
        return "".join(text_parts).strip()

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        json_system = (
            system_prompt + "\nIMPORTANT: You must respond ONLY with a valid JSON object. "
            "Do not include markdown code block formatting (```json) or introductory commentary."
        )
        raw_text = self.generate_text(json_system, user_prompt, temperature=0.1)
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"Failed to parse JSON response from Anthropic: {raw_text[:200]}")
