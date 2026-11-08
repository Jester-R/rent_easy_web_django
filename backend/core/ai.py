"""AI helpers for rental listing descriptions and structured property drafts."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
THAI_RE = re.compile(r"[\u0e00-\u0e7f]")
PRICE_NUMBER = r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
EXPLICIT_RENT_PATTERNS = (
    re.compile(rf"(?:US\$|USD|\$)\s*{PRICE_NUMBER}", re.IGNORECASE),
    re.compile(rf"{PRICE_NUMBER}\s*\$"),
    re.compile(rf"{PRICE_NUMBER}\s*(?:USD|US dollars?|dollars?)\b", re.IGNORECASE),
    re.compile(
        rf"(?:rent|price|monthly)\s*(?:is|to|at|of|:|=)?\s*(?:US\$|\$)?\s*{PRICE_NUMBER}\s*(?:/\s*month|per\s+month|a\s+month|monthly)?",
        re.IGNORECASE,
    ),
)

PROPERTY_DRAFT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "title_km": {"type": "STRING"},
        "location": {"type": "STRING"},
        "price_per_month": {"type": "NUMBER", "nullable": True},
        "category": {"type": "STRING"},
        "bedrooms": {"type": "INTEGER", "nullable": True},
        "bathrooms": {"type": "INTEGER", "nullable": True},
        "description": {"type": "STRING"},
        "description_km": {"type": "STRING"},
    },
    "required": [
        "title",
        "title_km",
        "location",
        "price_per_month",
        "category",
        "bedrooms",
        "bathrooms",
        "description",
        "description_km",
    ],
}
DESCRIPTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "description": {"type": "STRING"},
        "description_km": {"type": "STRING"},
    },
    "required": ["description", "description_km"],
}


class AIConfigError(RuntimeError):
    """Raised when no AI provider/API key has been configured."""


def _provider() -> str:
    configured = os.environ.get("AI_PROVIDER", "").strip().lower()
    provider = configured or (
        "gemini" if os.environ.get("GEMINI_API_KEY", "").strip() else "groq"
    )
    if provider not in {"groq", "gemini"}:
        raise AIConfigError("AI_PROVIDER must be 'groq' or 'gemini'")
    return provider


def _api_key(provider: str | None = None) -> str:
    provider = provider or _provider()
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY", "").strip()
    return (
        os.environ.get("GROQ_API_KEY", "").strip()
        or os.environ.get("GROQ_APIKEY", "").strip()
    )


def _model(provider: str | None = None) -> str:
    provider = provider or _provider()
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL
    return os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL


def is_ai_configured() -> bool:
    return bool(_api_key())


async def _request_json(
    client: httpx.AsyncClient,
    provider: str,
    model: str,
    api_key: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float,
) -> dict[str, Any]:
    if provider == "groq":
        response = await client.post(
            GROQ_CHAT_URL,
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1600,
                "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        )
        if response.status_code != 200:
            logger.warning(
                "Groq AI request failed (status %s): %s",
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError("AI generation request failed")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("AI generation response was invalid") from exc
        return _parse_json_object(content)

    model_path = quote(model, safe="-")
    response = await client.post(
        f"{GEMINI_API_URL}/{model_path}:generateContent",
        json={
            "systemInstruction": {
                "parts": [
                    {
                        "text": "\n".join(
                            m["content"] for m in messages if m["role"] == "system"
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
                for m in messages
                if m["role"] != "system"
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1600,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        },
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )
    if response.status_code != 200:
        logger.warning(
            "Gemini AI request failed (status %s): %s",
            response.status_code,
            response.text[:500],
        )
        raise RuntimeError("AI generation request failed")
    try:
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Gemini returned no usable AI content")
        raise RuntimeError("AI generation response was invalid") from exc
    return _parse_json_object(content)


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


def build_property_draft_prompt(details: dict[str, Any]) -> list[dict[str, str]]:
    """Build a structured property draft from an owner's freeform request."""
    system = (
        "You help property owners draft rental listings in Cambodia. Extract only "
        "facts stated by the owner; never invent prices, locations, bedrooms, "
        "bathrooms, amenities, or policies. Translate the title to natural Khmer "
        "when possible. Infer the best matching category from the supplied options. "
        "Choose a district only when its English or Khmer name is explicitly present "
        "in the owner's request. Return that option's exact value. Do not infer a "
        "district from a city, province, or vague area; if no supplied district name "
        "matches the request, return an empty location. For unknown numeric facts return null. "
        "Always create a clear title and a short listing description from the "
        "available facts; include rental duration or terms if stated. If the request "
        "states a rent or price, always extract its numeric monthly USD amount into "
        "price_per_month, including amounts written with $, USD, commas, or 'per month'. "
        "If no price is stated, return null. Do not require "
        "the owner to provide every field. Return ONLY JSON with "
        "exactly these keys: title, title_km, location, price_per_month, category, "
        "bedrooms, bathrooms, description, description_km. Text values must be "
        "strings; price and room counts must be numbers or null."
    )
    instruction = (
        "Create a property form draft from the owner's request and options below. "
        "Do not include photos or map coordinates.\n"
        f"{json.dumps({'request': _clean(details.get('prompt'), 3000), 'locations': details.get('locations', []), 'categories': details.get('categories', [])}, ensure_ascii=False, indent=2)}\n"
        "Use the exact option value for location/category. Match location against "
        "the supplied district names in either language. Treat a trailing dollar "
        "sign as currency too: '50$' means a monthly rent of 50 USD. A request such as "
        "'mini house for $1,200 a month, 12-month rental' should produce a house "
        "category, rent 1200, a mini-house title, and descriptions mentioning the "
        "12-month rental term. Leave unknown location and room counts blank/null."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": instruction},
    ]


async def generate_property_draft(details: dict[str, Any]) -> dict[str, Any]:
    """Generate form fields from an owner's freeform property prompt."""
    provider = _provider()
    api_key = _api_key(provider)
    if not api_key:
        raise AIConfigError(f"{provider.upper()}_API_KEY is not configured")
    model = _model(provider)
    async with httpx.AsyncClient(timeout=45.0) as client:
        messages = build_property_draft_prompt(details)
        data: dict[str, Any] | None = None
        for attempt in range(2):
            if attempt:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response could not be read as a JSON object. "
                            "Return a complete valid JSON object now with every required "
                            "key and the correct value types. Do not use markdown."
                        ),
                    }
                )
            try:
                data = await _request_json(
                    client,
                    provider,
                    model,
                    api_key,
                    messages,
                    PROPERTY_DRAFT_SCHEMA,
                    0.2 if attempt == 0 else 0,
                )
                break
            except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
                logger.warning(
                    "%s property draft response failed (attempt %s)",
                    provider,
                    attempt + 1,
                )
                if attempt:
                    raise RuntimeError("AI generation response was invalid") from exc
        if data is None:
            raise RuntimeError("AI generation response was invalid")
    result: dict[str, Any] = {}
    for key in (
        "title",
        "title_km",
        "location",
        "category",
        "description",
        "description_km",
    ):
        result[key] = _clean(
            data.get(key), 4200 if key.startswith("description") else 160
        )
    prompt = _clean(details.get("prompt"), 3000)
    for key in ("price_per_month", "bedrooms", "bathrooms"):
        value = data.get(key)
        try:
            if key == "price_per_month" and isinstance(value, str):
                value = re.sub(r"[^0-9.]", "", value.replace(",", "")) or None
            number = float(value) if value is not None else None
            result[key] = (
                int(number)
                if key != "price_per_month" and number is not None
                else number
            )
        except TypeError, ValueError:
            result[key] = None
    # Treat an amount explicitly written in the owner's prompt as authoritative.
    # This prevents the model from omitting or changing prices such as "50$".
    for pattern in EXPLICIT_RENT_PATTERNS:
        match = pattern.search(prompt)
        if match:
            result["price_per_month"] = float(match.group(1).replace(",", ""))
            break
    result["model"] = model
    result["provider"] = provider
    result["location"] = _match_prompt_location(
        result.get("location", ""), prompt, details.get("locations", [])
    )
    return result


def _match_prompt_location(candidate: str, prompt: str, options: Any) -> str:
    """Return a supplied district only when its name appears in the request."""

    def clean(value: Any) -> str:
        return " ".join(str(value or "").casefold().split())

    request = clean(prompt)
    if not isinstance(options, list):
        return ""

    normalized_options: list[tuple[str, list[str]]] = []
    for option in options:
        if isinstance(option, dict):
            value = str(option.get("value") or "").strip()
            names = [
                option.get("name_en"),
                option.get("name_km"),
                option.get("label"),
                value,
            ]
        else:
            value = str(option or "").strip()
            names = [value]
        if not value:
            continue
        parts = [clean(name) for name in names if clean(name)]
        # Combined bilingual labels are also useful when the source only sends a value.
        parts.extend(part.strip() for part in clean(value).split("/") if part.strip())
        normalized_options.append((value, list(dict.fromkeys(parts))))

    allowed_candidate = next(
        (value for value, names in normalized_options if clean(candidate) in names),
        "",
    )
    mentions = [
        (len(name), value)
        for value, names in normalized_options
        for name in names
        if len(name) >= 3 and name in request
    ]
    if mentions:
        mentions.sort(key=lambda item: item[0], reverse=True)
        longest = mentions[0][0]
        best = {value for length, value in mentions if length == longest}
        if allowed_candidate in best:
            return allowed_candidate
        if len(best) == 1:
            return next(iter(best))
    return ""


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
    """Generate English and Khmer listing descriptions."""
    provider = _provider()
    api_key = _api_key(provider)
    if not api_key:
        raise AIConfigError(f"{provider.upper()}_API_KEY is not configured")

    model = _model(provider)
    data: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=45.0) as client:
        for attempt in range(2):
            messages = build_property_description_prompt(details)
            if attempt:
                messages[-1]["content"] += (
                    "\nIMPORTANT: The Khmer text must use Khmer script only. "
                    "Remove every Thai character and Thai word."
                )
            try:
                data = await _request_json(
                    client,
                    provider,
                    model,
                    api_key,
                    messages,
                    DESCRIPTION_SCHEMA,
                    0.6 if attempt == 0 else 0.2,
                )
            except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
                logger.warning(
                    "Unexpected %s response shape: %s", provider, type(exc).__name__
                )
                raise RuntimeError("AI generation response was invalid") from exc

            description_km = _clean(data.get("description_km"), 4200)
            if not THAI_RE.search(description_km):
                break

    description = _clean(data.get("description"), 4200)
    description_km = _clean(data.get("description_km"), 4200)
    if not description or not description_km:
        raise RuntimeError("AI generation response was incomplete")

    return {
        "description": description,
        "description_km": description_km,
        "model": model,
        "provider": provider,
    }
