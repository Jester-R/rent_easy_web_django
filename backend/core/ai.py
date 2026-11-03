"""AI helpers for rental listing descriptions.

The provider is Groq's OpenAI-compatible chat completions API. The API key is
read from ``GROQ_API_KEY`` and never leaves the server.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
THAI_RE = re.compile(r"[\u0e00-\u0e7f]")


class AIConfigError(RuntimeError):
    """Raised when no AI provider/API key has been configured."""


def _api_key() -> str:
    return (
        os.environ.get("GROQ_API_KEY", "").strip()
        or os.environ.get("GROQ_APIKEY", "").strip()
    )


def _model() -> str:
    return os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL


def is_ai_configured() -> bool:
    return bool(_api_key())


def _clean(value: Any, limit: int = 600) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _facts(details: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "title": _clean(details.get("title"), 160),
        "title_km": _clean(details.get("title_km"), 160),
        "location": _clean(details.get("location"), 160),
        "category": _clean(details.get("category"), 60),
        "bedrooms": details.get("bedrooms"),
        "bathrooms": details.get("bathrooms"),
        "monthly_rent_usd": details.get("price_per_month"),
        "owner_notes": _clean(details.get("notes"), 1200),
    }
    return {key: value for key, value in facts.items() if value not in ("", None)}


def build_property_description_prompt(details: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "You write concise, truthful rental listing descriptions for RentEasy, "
        "a rental marketplace in Cambodia. Use only the facts provided. Never "
        "invent amenities, nearby places, policies, or measurements. The "
        "owner_notes field is the only source for amenities and features. If a "
        "fact is missing, do not mention it. Avoid discriminatory or exclusionary "
        "language. The Khmer text must use Khmer script only and must not contain "
        "Thai characters or Thai words. Return ONLY a valid JSON object with exactly two string keys: "
        '"description" for English and "description_km" for Khmer. Do not wrap '
        "the JSON in markdown."
    )
    instruction = (
        "Write a warm, professional rental listing based on these facts:\n"
        f"{json.dumps(_facts(details), ensure_ascii=False, indent=2)}\n\n"
        "English (description): one short paragraph, about 35-60 words. Mention "
        "the monthly rent if provided.\n"
        "Khmer (description_km): a natural, equally short Khmer version with the "
        "same facts, not a word-for-word translation.\n"
        "Return JSON only."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": instruction},
    ]


def _parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("AI response was not valid JSON") from None
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("AI response was not a JSON object")
    return data


async def generate_property_description(details: dict[str, Any]) -> dict[str, Any]:
    """Generate English and Khmer listing descriptions with Groq."""
    api_key = _api_key()
    if not api_key:
        raise AIConfigError("GROQ_API_KEY is not configured")

    model = _model()
    data: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(2):
            messages = build_property_description_prompt(details)
            if attempt:
                messages[-1]["content"] += (
                    "\nIMPORTANT: The Khmer text must use Khmer script only. "
                    "Remove every Thai character and Thai word."
                )
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.6 if attempt == 0 else 0.2,
                "max_tokens": 1600,
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            }
            response = await client.post(
                GROQ_CHAT_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 200:
                logger.warning(
                    "Groq request failed (status %s): %s",
                    response.status_code,
                    response.text[:500],
                )
                raise RuntimeError("AI generation request failed")

            try:
                content = response.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                logger.warning(
                    "Unexpected Groq response shape: %s", type(exc).__name__
                )
                raise RuntimeError("AI generation response was invalid") from exc

            data = _parse_json_object(content)
            description_km = _clean(data.get("description_km"), 4000)
            if not THAI_RE.search(description_km):
                break

    description = _clean(data.get("description"), 4000)
    description_km = _clean(data.get("description_km"), 4000)
    if not description or not description_km:
        raise RuntimeError("AI generation response was incomplete")

    return {
        "description": description,
        "description_km": description_km,
        "model": model,
    }
