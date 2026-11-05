"""
eval/llm_client.py
------------------
Lightweight chat-completion wrapper built on the OpenAI SDK.

Every model is used through ``chat(messages) -> str``: a model of
eval/model_registry.py is called at its OpenAI-compatible endpoint, a model
registered as a Python function is called directly.

Configuration (via environment variables or .env file):
    OPENAI_API_KEY   — API key for generic / OpenAI models
    OPENAI_BASE_URL  — endpoint of unregistered model names
                       (default: https://api.openai.com/v1)
    EVAL_MODEL       — model to use for LLM-based evaluation
                       (default: Doubao-Seed-2.0-lite)

    For models in the built-in registry (see eval/model_registry.py) you only
    need to set the provider-specific key, e.g.:
        OPENAI_API_KEY     — OpenAI (GPT)
        ARK_API_KEY        — Volcano Engine / Doubao Seed
        GEMINI_API_KEY     — Google Gemini
        DEEPSEEK_API_KEY   — DeepSeek
        DASHSCOPE_API_KEY  — Alibaba Qwen
        ZHIPU_API_KEY      — Zhipu GLM
        MOONSHOT_API_KEY   — Moonshot Kimi
        XAI_API_KEY        — xAI Grok
        MINIMAX_API_KEY    — MiniMax
        XIAOMI_API_KEY     — Xiaomi MiMo

Usage:
    from eval.llm_client import LLM, extract_json_from_text, get_model

    llm = LLM()                                        # uses EVAL_MODEL from env
    llm = LLM(model_name="Doubao-Seed-2.0-lite")      # explicit model
    answer: str = llm.get_model_answer("What is 2+2?")

    model = get_model("my-hf-model")                   # any registered model
    reply: str = model.chat([{"role": "user", "content": "What is 2+2?"}])
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Protocol

import openai
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

from eval.model_registry import (
    DEFAULT_EVAL_MODEL,
    MODEL_FUNCTIONS,
    ModelConfigError,
    ModelFunction,
    resolve_client_params,
)


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def extract_json_from_text(text: str) -> Any:
    """
    Extract the first JSON object or array from *text*.

    Tries, in order:
    1. Direct parse (the whole string is valid JSON)
    2. Strip markdown code fences (```json … ```)
    3. Regex search for the first {...} or [...] block
    Returns the parsed Python object, or None if nothing valid is found.
    """
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip code fences
    fenced = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced.strip())
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    # 3. Search for first JSON object or array
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# A rejected key, missing permission or unknown model: every request would fail.
_FATAL_STATUS = (401, 403, 404)
# The other 4xx (e.g. an input longer than the context window) are not retried.
_RETRY_STATUS = (408, 409, 429)


class ChatModel(Protocol):
    name: str

    def chat(self, messages: list[dict]) -> str:
        """Return the reply text to *messages* (OpenAI format)."""


class EndpointModel:
    """A model served at an OpenAI-compatible endpoint."""

    def __init__(self, name: str, timeout: float) -> None:
        self.name = name
        api_key, base_url, self._model_id, self._extra_params = resolve_client_params(name)
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat(self, messages: list[dict]) -> str:
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=messages,  # type: ignore[arg-type]
            extra_body=self._extra_params or None,
        )
        return response.choices[0].message.content or ""


class FunctionModel:
    """A model registered as a Python function."""

    def __init__(self, name: str, fn: ModelFunction) -> None:
        self.name = name
        self._fn = fn

    def chat(self, messages: list[dict]) -> str:
        reply = self._fn([dict(m) for m in messages])
        if not isinstance(reply, str):
            raise ModelConfigError(
                f"{self.name}: the registered function returned {type(reply).__name__}, expected str"
            )
        return reply


def get_model(model_name: str, timeout: float = 3600.0) -> ChatModel:
    """Return the model registered as *model_name* (see eval/model_registry.py).

    Raises :class:`ModelConfigError` if it cannot be used, e.g. its key is not set.
    """
    fn = MODEL_FUNCTIONS.get(model_name)
    if fn is not None:
        return FunctionModel(model_name, fn)
    return EndpointModel(model_name, timeout)


def chat_with_retries(
    model: ChatModel,
    messages: list[dict],
    max_retries: int,
    retry_delay: float,
    label: str | None = None,
) -> str:
    """Return a non-empty reply of *model* to *messages*.

    Empty replies, timeouts, rate limits, server errors and exceptions of a
    function model are retried, up to *max_retries* attempts in total.  A
    rejected key, missing permission or unknown model raises
    :class:`ModelConfigError` at once; other HTTP 4xx errors are raised
    without retry.
    """
    label = label or model.name
    last: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            reply = model.chat(messages)
            if reply:
                return reply
            last = RuntimeError("empty reply")
        except openai.APIStatusError as exc:
            if exc.status_code in _FATAL_STATUS:
                raise ModelConfigError(f"{model.name}: {exc.message}") from exc
            if exc.status_code < 500 and exc.status_code not in _RETRY_STATUS:
                raise
            last = exc
        except ModelConfigError:
            raise
        except Exception as exc:
            last = exc
        print(f"\n[{label}] attempt {attempt}/{max_retries} failed: {last}")
        if attempt < max_retries:
            time.sleep(retry_delay)
    raise RuntimeError(f"no reply after {max_retries} attempts: {last}")


# ---------------------------------------------------------------------------
# LLM wrapper
# ---------------------------------------------------------------------------

class LLM:
    """
    Thin single-prompt wrapper around a registered model (used for the judge).

    Parameters
    ----------
    model_name : str, optional
        Registered model name.  Falls back to the ``EVAL_MODEL`` environment
        variable, then to ``"Doubao-Seed-2.0-lite"``.
    max_retries : int
        Attempts per request on empty replies and transient errors (default: 5).
    retry_delay : float
        Seconds to wait between retries (default: 5).
    timeout : float
        Per-request timeout in seconds for endpoint models (default: 3600).
    """

    def __init__(
        self,
        model_name: str | None = None,
        max_retries: int = 5,
        retry_delay: float = 5.0,
        timeout: float = 3600.0,
    ) -> None:
        self.model_name = (
            model_name
            or os.getenv("EVAL_MODEL")
            or DEFAULT_EVAL_MODEL
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._model = get_model(self.model_name, timeout=timeout)

    # ------------------------------------------------------------------
    def get_model_answer(
        self,
        prompt: str,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Send *prompt* to the model and return the response text.

        Parameters
        ----------
        prompt : str
            The user message / evaluation prompt.
        history : list[dict], optional
            Prior conversation messages in OpenAI format
            ``[{"role": "...", "content": "..."}, ...]``.
            Pass the dialogue history when evaluating multi-turn tasks.
        system_prompt : str, optional
            System message prepended before history.

        Returns
        -------
        str
            The model's (non-empty) text response.  Decoding parameters stay
            at the provider's default, as in all reported runs.  Raises
            :class:`ModelConfigError` or the last error (see
            :func:`chat_with_retries`) if no reply is obtained.
        """
        messages: list[dict] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle internal format: [{"type": "text", "value": "..."}]
                    content = "".join(
                        part.get("value", "") for part in content if isinstance(part, dict)
                    )
                messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": prompt})

        return chat_with_retries(self._model, messages, self.max_retries, self.retry_delay)
