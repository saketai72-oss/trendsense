r"""
TrendSense — Unified LLM Client
================================
Primary:  OpenRouter (truy cập hàng trăm model qua 1 API key)
Fallback: Groq (llama-3.3-70b-versatile) — nếu OpenRouter lỗi hoặc không có key

Dùng:
    from backend.api.llm_client import chat_completion_json
    result = chat_completion_json(prompt, system="...")
"""

import logging
import json
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _clean_malformed_json(json_str: str) -> str:
    r"""
    Sửa các lỗi JSON thường gặp từ Groq / OpenRouter:
    - Chuyển \u{XXXX} thành \uXXXX (không có dấu ngoặc nhọn)
    - Thoát các ký tự đặc biệt nếu cần
    """
    def replacer(match):
        code = match.group(1)
        if len(code) <= 4:
            return f"\\u{code.zfill(4)}"
        else:
            return match.group(0)
    json_str = re.sub(r'\\u\{([0-9A-Fa-f]+)\}', replacer, json_str)
    return json_str


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    r"""
    Extract the first valid JSON object from a string that may contain extra text.
    Tries to clean malformed Unicode escapes first.
    """
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in output")
    brace_count = 0
    end = None
    for i in range(start, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i
                break
    if end is None:
        raise ValueError("Unbalanced braces, cannot extract JSON")
    json_str = text[start:end+1]

    json_str = _clean_malformed_json(json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        try:
            unescaped = json_str.encode().decode('unicode_escape')
            return json.loads(unescaped)
        except Exception:
            raise ValueError(f"Failed to parse JSON even after cleaning: {e}")


def chat_completion_json(
    prompt: str,
    system: str = "You are a helpful assistant. Output only valid JSON.",
    temperature: float = 0.5,
    max_tokens: int = 800,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gửi prompt tới LLM (OpenRouter → Groq), trả về dict JSON đã parse.
    Sử dụng plain text + regex extraction để tránh lỗi type và tăng độ tin cậy.
    """
    from core.config.backend_settings import (
        OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
        GROQ_API_KEY,
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    # --- 1. Try OpenRouter (plain text) ---
    if OPENROUTER_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

            openrouter_free_models = [
                "google/gemini-2.5-flash:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "nvidia/llama-3.1-nemotron-70b-instruct:free",
                "google/gemma-2-9b-it:free",
                "mistralai/mistral-nemo:free",
                "meta-llama/llama-3.1-8b-instruct:free",
                "qwen/qwen-2.5-72b-instruct:free",
                "qwen/qwen-2.5-7b-instruct:free",
                "microsoft/phi-3-mini-128k-instruct:free",
                "meta-llama/llama-3-8b-instruct:free"
            ]

            models_to_try = [model] if model else openrouter_free_models
            for selected_model in models_to_try:
                logger.info(f"[LLM] OpenRouter → {selected_model}")
                try:
                    resp = client.chat.completions.create(  # type: ignore[call-overload]
                        model=selected_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    content = resp.choices[0].message.content
                    if content:
                        return _extract_json_from_text(content)
                except Exception as e:
                    logger.warning(f"OpenRouter {selected_model} error: {e}")
                    continue
        except Exception as e:
            logger.warning(f"OpenRouter configuration error: {e}")

    # --- 2. Try Groq (plain text) ---
    if GROQ_API_KEY:
        try:
            from groq import Groq
            groq_client = Groq(api_key=GROQ_API_KEY)
            logger.info("[LLM] Groq plain text")
            resp = groq_client.chat.completions.create(  # type: ignore[call-overload]
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            return _extract_json_from_text(content)
        except Exception as e:
            logger.error(f"Groq failed: {e}")
            raise RuntimeError(f"Unable to obtain valid JSON from any LLM provider: {e}")

    raise RuntimeError("No LLM API key configured (OPENROUTER_API_KEY or GROQ_API_KEY)")