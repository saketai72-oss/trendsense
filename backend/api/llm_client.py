"""
TrendSense — Unified LLM Client
================================
Primary:  OpenRouter (truy cập hàng trăm model qua 1 API key)
Fallback: Groq (llama-3.3-70b-versatile) — nếu OpenRouter lỗi hoặc không có key

Dùng:
    from backend.api.llm_client import chat_completion
    result = chat_completion(prompt, response_format="json_object")
"""
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)


def chat_completion(
    prompt: str,
    system: str = "You are a helpful assistant.",
    response_format: Optional[str] = "json_object",
    temperature: float = 0.5,
    max_tokens: int = 800,
    model: Optional[str] = None,
) -> str:
    """
    Gửi prompt tới LLM, trả về chuỗi content.
    Thử OpenRouter trước → fallback Groq nếu lỗi.

    Args:
        prompt: User message
        system: System message
        response_format: "json_object" hoặc None
        temperature: 0.0 → 1.0
        max_tokens: Giới hạn token output
        model: Override model (mặc định dùng OPENROUTER_DEFAULT_MODEL)

    Returns:
        Chuỗi text (thường là JSON string nếu response_format="json_object")

    Raises:
        RuntimeError: Nếu cả OpenRouter lẫn Groq đều thất bại
    """
    from core.config.backend_settings import (
        OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_DEFAULT_MODEL,
        GROQ_API_KEY,
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    # ── 1. Thử OpenRouter ─────────────────────────────────────────
    if OPENROUTER_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
            )

            # Danh sách 10 model Free xếp theo độ "Tự nhiên, mềm mại" (đặc biệt với Tiếng Việt)
            openrouter_free_models = [
                "google/gemini-2.5-flash:free",               # Cực kỳ tự nhiên, mượt mà tiếng Việt
                "meta-llama/llama-3.3-70b-instruct:free",     # Siêu thông minh, văn phong đa dạng
                "nvidia/llama-3.1-nemotron-70b-instruct:free",# Tinh chỉnh cực tốt cho chat/lời khuyên
                "google/gemma-2-9b-it:free",                  # Sáng tạo, văn phong bay bổng
                "mistralai/mistral-nemo:free",                # Rất tốt về đa ngôn ngữ
                "meta-llama/llama-3.1-8b-instruct:free",      # Khá tốt, an toàn
                "qwen/qwen-2.5-72b-instruct:free",            # Rất thông minh nhưng văn phong hơi formal/khô khan
                "qwen/qwen-2.5-7b-instruct:free",             # Tương tự bản 72b nhưng nhẹ hơn
                "microsoft/phi-3-mini-128k-instruct:free",    # Thường trả lời ngắn gọn, hơi máy móc
                "meta-llama/llama-3-8b-instruct:free"         # Cũ nhất, dự phòng cuối cùng
            ]

            models_to_try = []
            if model:
                models_to_try.append(model)
            else:
                models_to_try = openrouter_free_models

            openrouter_success = False
            content = ""

            for selected_model in models_to_try:
                logger.info(f"[LLM] Thử OpenRouter → {selected_model}")
                kwargs = dict(
                    model=selected_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if response_format == "json_object":
                    kwargs["response_format"] = {"type": "json_object"}

                try:
                    resp = client.chat.completions.create(**kwargs)
                    content = resp.choices[0].message.content
                    logger.info(f"[LLM] OpenRouter ✅ thành công với {selected_model}")
                    openrouter_success = True
                    break
                except Exception as e:
                    logger.warning(f"[LLM] OpenRouter lỗi với {selected_model}: {e}")
                    import time
                    time.sleep(1) # Nghỉ 1s trước khi thử model tiếp theo để tránh rate limit

            if openrouter_success:
                return content
            else:
                logger.warning("[LLM] Tất cả model OpenRouter đều lỗi — Chuyển sang Groq fallback")

        except Exception as e:
            logger.warning(f"[LLM] OpenRouter lỗi cấu hình: {e} — Chuyển sang Groq fallback")

    # ── 2. Fallback Groq ──────────────────────────────────────────
    if GROQ_API_KEY:
        try:
            from groq import Groq

            groq_client = Groq(api_key=GROQ_API_KEY)
            groq_model = "llama-3.3-70b-versatile"
            logger.info(f"[LLM] Groq fallback → {groq_model}")

            kwargs = dict(
                model=groq_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format == "json_object":
                kwargs["response_format"] = {"type": "json_object"}

            resp = groq_client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            logger.info("[LLM] Groq ✅ thành công")
            return content

        except Exception as e:
            logger.error(f"[LLM] Groq fallback cũng lỗi: {e}")
            raise RuntimeError(f"Cả OpenRouter lẫn Groq đều thất bại: {e}")

    raise RuntimeError("Không có LLM API key nào được cấu hình (OPENROUTER_API_KEY hoặc GROQ_API_KEY)")


def chat_completion_json(
    prompt: str,
    system: str = "You are a helpful assistant.",
    temperature: float = 0.5,
    max_tokens: int = 800,
    model: Optional[str] = None,
) -> dict:
    """
    Tiện ích: gọi chat_completion và parse JSON tự động.
    Raises json.JSONDecodeError nếu output không phải JSON hợp lệ.
    """
    raw = chat_completion(
        prompt=prompt,
        system=system,
        response_format="json_object",
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    return json.loads(raw)
