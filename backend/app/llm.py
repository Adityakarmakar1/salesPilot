"""Shared LLM chat helper.

Selects the provider from settings.LLM_PROVIDER ("groq" by default, or
"openai"). The product does not depend on the OpenAI API: Groq is the
default provider and OpenAI is only used when explicitly selected.
"""

import httpx
from fastapi import HTTPException, status

from .config import settings

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def _provider_config() -> tuple[str, str, str, str]:
    """Return (provider, url, api_key, model) for the selected provider."""
    provider = (settings.LLM_PROVIDER or "groq").strip().lower()
    if provider == "openai":
        return provider, OPENAI_CHAT_URL, settings.OPENAI_API_KEY, settings.OPENAI_MODEL
    # Default: groq (any unrecognised value falls back to groq).
    return "groq", GROQ_CHAT_URL, settings.GROQ_API_KEY, settings.GROQ_MODEL


def _missing_key_detail(provider: str) -> str:
    if provider == "openai":
        return "LLM not connected — OPENAI_API_KEY is required (or set LLM_PROVIDER=groq with GROQ_API_KEY set)."
    return "LLM not connected — GROQ_API_KEY is required (or set LLM_PROVIDER=openai with OPENAI_API_KEY set)."


def llm_status() -> dict:
    provider, _url, api_key, model = _provider_config()
    return {"provider": provider, "model": model, "connected": bool(api_key)}


# Groq retired llama-3.3-70b-versatile / llama-3.1-8b-instant for free and
# developer tiers on 2026-08-16; the recommended replacements are the
# gpt-oss models. If the configured model is ever missing on the account,
# fall back through these instead of failing the request.
GROQ_FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]


def _is_model_missing(resp) -> bool:
    if resp.status_code not in (400, 404):
        return False
    try:
        err = resp.json().get("error", {})
        return err.get("code") == "model_not_found" or "does not exist" in str(err.get("message", ""))
    except ValueError:
        return "does not exist" in resp.text


def chat_completion(messages, json_mode: bool = False) -> str:
    provider, url, api_key, model = _provider_config()
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _missing_key_detail(provider))

    candidates = [model]
    if provider == "groq":
        candidates += [m for m in GROQ_FALLBACK_MODELS if m != model]

    headers = {"Authorization": f"Bearer {api_key}"}
    resp = None
    try:
        with httpx.Client(timeout=120) as client:
            for candidate in candidates:
                payload: dict = {"model": candidate, "messages": messages}
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}
                resp = client.post(url, headers=headers, json=payload)
                if _is_model_missing(resp):
                    continue
                if json_mode and resp.status_code == 400:
                    # Some models reject response_format — retry once without it.
                    payload.pop("response_format", None)
                    resp = client.post(url, headers=headers, json=payload)
                    if _is_model_missing(resp):
                        continue
                break
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM request failed: {exc}")
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    try:
        content = resp.json()["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, ValueError, AttributeError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM returned an unexpected response: {exc}")
    content = content.strip()
    if not content:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LLM returned an empty response — nothing was fabricated.")
    return content
