"""LLM providers for the AI opponent.

Every provider speaks its own HTTP dialect but exposes the same single
entry point: :func:`call_llm`. The user configures them in Settings;
keys are stored in the local database and never leave the server except
towards the provider itself.
"""
from __future__ import annotations

import re

import requests

PROVIDERS = ("manual", "openai", "anthropic", "gemini", "lmstudio", "compat")

PROVIDER_LABELS = {
    "manual": "Manual / paste reply",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "gemini": "Google Gemini",
    "lmstudio": "LM Studio (local)",
    "compat": "OpenAI-compatible (custom URL)",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.0-flash",
    "lmstudio": "",
    "compat": "",
    "manual": "",
}


class AIProviderError(Exception):
    """Raised for any network/API failure; message is safe to show."""


def _lmstudio_base_url(cfg: dict) -> str:
    host = (cfg.get("lm_host") or "127.0.0.1").strip()
    if not re.match(r"^[a-zA-Z0-9._-]+$", host):
        raise AIProviderError("invalid-lm-host")
    try:
        port = int(cfg.get("lm_port") or 1234)
    except (TypeError, ValueError):
        port = 1234
    if not 1 <= port <= 65535:
        raise AIProviderError("invalid-lm-host")
    return f"http://{host}:{port}/v1"


def _base_url(cfg: dict) -> str:
    provider = cfg.get("provider")
    if provider == "openai":
        return (cfg.get("base_url") or "").strip() or "https://api.openai.com/v1"
    if provider == "compat":
        url = (cfg.get("base_url") or "").strip().rstrip("/")
        if not url:
            raise AIProviderError("no-base-url")
        return url
    if provider == "lmstudio":
        return _lmstudio_base_url(cfg)
    raise AIProviderError("no-base-url")


def _post(url: str, *, headers: dict, json_body: dict, timeout: int) -> dict:
    try:
        response = requests.post(url, headers=headers, json=json_body, timeout=timeout)
    except requests.RequestException as exc:
        raise AIProviderError(f"network: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        detail = ""
        try:
            detail = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = (response.text or "")[:200]
        raise AIProviderError(f"http {response.status_code}: {detail}")
    try:
        return response.json()
    except ValueError as exc:
        raise AIProviderError("bad-response") from exc


def _call_openai_shape(cfg: dict, system: str, user: str, timeout: int) -> str:
    base = _base_url(cfg)
    api_key = (cfg.get("api_key") or "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    model = (cfg.get("model") or "").strip() or DEFAULT_MODELS.get(cfg.get("provider"), "")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(cfg.get("temperature") or 0.7),
        "max_tokens": 300,
    }
    data = _post(f"{base}/chat/completions", headers=headers, json_body=body, timeout=timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("bad-response") from exc
    return content or ""


def _call_anthropic(cfg: dict, system: str, user: str, timeout: int) -> str:
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise AIProviderError("no-api-key")
    model = (cfg.get("model") or "").strip() or DEFAULT_MODELS["anthropic"]
    data = _post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json_body={
            "model": model,
            "max_tokens": 300,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": float(cfg.get("temperature") or 0.7),
        },
        timeout=timeout,
    )
    try:
        return "".join(block.get("text", "") for block in data["content"])
    except (KeyError, TypeError) as exc:
        raise AIProviderError("bad-response") from exc


def _call_gemini(cfg: dict, system: str, user: str, timeout: int) -> str:
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise AIProviderError("no-api-key")
    model = (cfg.get("model") or "").strip() or DEFAULT_MODELS["gemini"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    data = _post(
        url,
        headers={"Content-Type": "application/json"},
        json_body={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": float(cfg.get("temperature") or 0.7),
                "maxOutputTokens": 300,
            },
        },
        timeout=timeout,
    )
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("bad-response") from exc


def call_llm(cfg: dict, system_prompt: str, user_prompt: str) -> str:
    """Send one prompt to the configured provider and return raw text."""
    provider = cfg.get("provider")
    timeout = 120
    if provider == "openai" or provider == "compat" or provider == "lmstudio":
        return _call_openai_shape(cfg, system_prompt, user_prompt, timeout)
    if provider == "anthropic":
        return _call_anthropic(cfg, system_prompt, user_prompt, timeout)
    if provider == "gemini":
        return _call_gemini(cfg, system_prompt, user_prompt, timeout)
    raise AIProviderError("unknown-provider")


def test_connection(cfg: dict) -> dict:
    """Quick smoke test used by the Settings page.

    Asks for a single fixed reply, so it costs almost nothing and also
    verifies that the model follows the MOVE/CHAT format.
    """
    system = (
        "You are testing a chess app integration. Answer in exactly this "
        "format and nothing else:\nMOVE: (reply with the word: ok)\n"
        "CHAT: (reply with one short greeting word)"
    )
    text = call_llm(cfg, system, "Say hi for the connection test.")
    move_ok = re.search(r"MOVE:\s*ok", text, re.IGNORECASE) is not None
    return {"ok": move_ok, "raw": text.strip()[:300]}
