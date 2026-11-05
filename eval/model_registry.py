"""
eval/model_registry.py
----------------------
Registry of the models evaluated in AppCIF-Bench, plus the default judge model.

Users only need to set the relevant API-key environment variable for each
provider they use.  Everything else — base URL, official model ID, and
provider-specific extra parameters — is pre-configured here.

Model aliases and required env vars
-------------------------------------
Alias                        | Provider              | Env var
-----------------------------|-----------------------|-------------------
GPT-5.4-xhigh                | OpenAI                | OPENAI_API_KEY
Gemini-3.1-Pro-Preview       | Google                | GEMINI_API_KEY
Doubao-Seed-2.0-Pro-high     | Volcano Engine (Ark)  | ARK_API_KEY
GLM-5.1                      | Zhipu AI              | ZHIPU_API_KEY
Gemini-3-Flash-Preview       | Google                | GEMINI_API_KEY
Kimi-K2.5-Thinking           | Moonshot AI           | MOONSHOT_API_KEY
Qwen-3.6-Plus-Thinking       | Alibaba DashScope     | DASHSCOPE_API_KEY
Grok-4.2                     | xAI                   | XAI_API_KEY
DeepSeek-V3.2-Thinking       | DeepSeek              | DEEPSEEK_API_KEY
Xiaomi-MiMo-V2-Pro           | Xiaomi MiMo           | XIAOMI_API_KEY
Minimax-M2.7                 | MiniMax               | MINIMAX_API_KEY
Xiaomi-MiMo-V2-Omni          | Xiaomi MiMo           | XIAOMI_API_KEY
Doubao-Seed-2.0-lite         | Volcano Engine (Ark)  | ARK_API_KEY   ← default judge
doubao-seed1.6-10.15         | Volcano Engine (Ark)  | ARK_API_KEY   ← judge of the paper results (offline)

Kimi-K2.5-Thinking, DeepSeek-V3.2-Thinking and the two Xiaomi MiMo-V2 models
are no longer served by their providers; their entries document the
configuration of the paper results.

Other models (local or self-hosted models, another judge, ...) are added with
:func:`register_model`, usually from a file passed to ``run_eval.py
--models_file`` (see README); a registered model is either an
OpenAI-compatible endpoint or a Python function. Any other name is sent
verbatim to ``OPENAI_BASE_URL`` (default ``https://api.openai.com/v1``) with
``OPENAI_API_KEY``.

The base URL of a built-in model can be overridden with ``<PREFIX>_BASE_URL``,
where ``<PREFIX>`` is its key variable without ``_API_KEY`` (e.g.
``MINIMAX_BASE_URL=https://api.minimaxi.com/v1`` for a Mainland China MiniMax
account). GPT-5.4-xhigh is the exception: ``OPENAI_BASE_URL`` only sets the
endpoint of unregistered names, so register an entry of your own to reach GPT
through a proxy.

A missing key raises :class:`ModelConfigError` before any request is sent.

``extra_params`` are sent in the request body (``extra_body``) unchanged, so
provider-specific fields such as ``thinking`` or ``enable_thinking`` work with
any version of the ``openai`` SDK. Decoding parameters that are not listed
(temperature, top-p, ...) are left at the provider's default.
"""

from __future__ import annotations

import os
import runpy
from dataclasses import dataclass, field
from typing import Any, Callable


class ModelConfigError(RuntimeError):
    """A model cannot be used as configured (unknown name, missing or rejected key, ...)."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """Configuration for a single model / provider endpoint."""

    model_id: str
    """Official model identifier sent to the provider's API."""

    base_url: str
    """OpenAI-compatible base URL for this provider."""

    api_key_env: str | None = None
    """Name of the environment variable that holds the API key; ``None`` if no key is needed."""

    extra_params: dict[str, Any] = field(default_factory=dict)
    """Additional keyword arguments forwarded to ``chat.completions.create``."""

    base_url_env: str | None = None
    """Name of the environment variable that overrides ``base_url``, if any."""


ModelFunction = Callable[[list[dict]], str]
"""A model registered as a Python function: OpenAI-format messages in, reply text out."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DEFAULT_EVAL_MODEL = "Doubao-Seed-2.0-lite"

_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

MODEL_REGISTRY: dict[str, ModelConfig] = {

    # ── OpenAI  ───────────────────────────────────────────────────────────────
    # https://platform.openai.com/docs/api-reference
    "GPT-5.4-xhigh": ModelConfig(
        model_id="gpt-5.4-2026-03-05",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        extra_params={"reasoning_effort": "xhigh"},
    ),

    # ── Google Gemini  ────────────────────────────────────────────────────────
    # https://ai.google.dev/gemini-api/docs/openai
    "Gemini-3.1-Pro-Preview": ModelConfig(
        model_id="gemini-3.1-pro-preview",
        base_url=_GOOGLE_BASE_URL,
        api_key_env="GEMINI_API_KEY",
    ),
    "Gemini-3-Flash-Preview": ModelConfig(
        model_id="gemini-3-flash-preview",
        base_url=_GOOGLE_BASE_URL,
        api_key_env="GEMINI_API_KEY",
    ),

    # ── Volcano Engine / ByteDance (Doubao Seed)  ─────────────────────────────
    # https://www.volcengine.com/docs/82379/1302008
    # Ark lists doubao-seed-2-0-pro-260215 as scheduled for retirement.
    "Doubao-Seed-2.0-Pro-high": ModelConfig(
        model_id="doubao-seed-2-0-pro-260215",
        base_url=_ARK_BASE_URL,
        api_key_env="ARK_API_KEY",
        extra_params={"max_tokens": 128000, "reasoning_effort": "high"},
    ),
    # Default judge model (all results on the released v1.1 data)
    "Doubao-Seed-2.0-lite": ModelConfig(
        model_id="doubao-seed-2-0-lite-260428",
        base_url=_ARK_BASE_URL,
        api_key_env="ARK_API_KEY",
        extra_params={"thinking": {"type": "enabled"}, "max_completion_tokens": 65536},
    ),
    # Judge of the leaderboard reported in the paper; no longer served
    "doubao-seed1.6-10.15": ModelConfig(
        model_id="doubao-seed-1-6-251015",
        base_url=_ARK_BASE_URL,
        api_key_env="ARK_API_KEY",
        extra_params={"max_tokens": 32000, "reasoning_effort": "minimal"},
    ),

    # ── Zhipu AI (GLM)  ───────────────────────────────────────────────────────
    # https://open.bigmodel.cn/dev/api
    "GLM-5.1": ModelConfig(
        model_id="glm-5.1",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key_env="ZHIPU_API_KEY",
        extra_params={"thinking": {"type": "enabled"}, "max_tokens": 128000},
    ),

    # ── Moonshot AI (Kimi)  ───────────────────────────────────────────────────
    # https://platform.moonshot.cn/docs/api-reference
    # kimi-k2.5 was retired on 2026-08-31; requests now return 404.
    "Kimi-K2.5-Thinking": ModelConfig(
        model_id="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        api_key_env="MOONSHOT_API_KEY",
        extra_params={
            "thinking": {"type": "enabled"},
            "max_tokens": 128000,
            "temperature": 1.0,
        },
    ),

    # ── Alibaba Cloud DashScope (Qwen)  ───────────────────────────────────────
    # https://help.aliyun.com/zh/model-studio/developer-reference/
    "Qwen-3.6-Plus-Thinking": ModelConfig(
        model_id="qwen3.6-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        # In thinking mode max_tokens only accepts [1, 32768]; max_completion_tokens
        # covers reasoning + answer and allows the model's full 65,536 output.
        extra_params={"enable_thinking": True, "max_completion_tokens": 65536},
    ),

    # ── xAI (Grok)  ───────────────────────────────────────────────────────────
    # https://docs.x.ai/developers/models/grok-4.20
    "Grok-4.2": ModelConfig(
        model_id="grok-4.20-0309-reasoning",
        base_url="https://api.x.ai/v1",
        api_key_env="XAI_API_KEY",
    ),

    # ── DeepSeek  ─────────────────────────────────────────────────────────────
    # https://api-docs.deepseek.com
    # deepseek-reasoner was retired on 2026-07-24; the name is now served by a
    # V4-series model, so this entry no longer reaches DeepSeek-V3.2.
    "DeepSeek-V3.2-Thinking": ModelConfig(
        model_id="deepseek-reasoner",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        extra_params={"max_tokens": 64000},
    ),

    # ── Xiaomi MiMo  ──────────────────────────────────────────────────────────
    # https://mimo.mi.com/docs/api/chat/openai-api
    # The MiMo-V2 models are no longer offered; the API now serves the V2.6 series.
    "Xiaomi-MiMo-V2-Pro": ModelConfig(
        model_id="mimo-v2-pro",
        base_url="https://api.xiaomimimo.com/v1",
        api_key_env="XIAOMI_API_KEY",
        extra_params={"max_completion_tokens": 131072},
    ),
    "Xiaomi-MiMo-V2-Omni": ModelConfig(
        model_id="mimo-v2-omni",
        base_url="https://api.xiaomimimo.com/v1",
        api_key_env="XIAOMI_API_KEY",
        extra_params={"max_completion_tokens": 131072},
    ),

    # ── MiniMax  ──────────────────────────────────────────────────────────────
    # https://platform.minimax.io/docs/api-reference/text-openai-api
    # Keys are region-locked: Mainland China accounts set
    # MINIMAX_BASE_URL=https://api.minimaxi.com/v1. Without reasoning_split the
    # thinking is returned inside `content` and would be judged as the answer.
    "Minimax-M2.7": ModelConfig(
        model_id="MiniMax-M2.7",
        base_url="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        extra_params={"max_tokens": 128000, "reasoning_split": True},
    ),
}

# OPENAI_BASE_URL is left out: it sets the endpoint of unregistered names.
for _config in MODEL_REGISTRY.values():
    if _config.api_key_env != "OPENAI_API_KEY":
        _config.base_url_env = _config.api_key_env.removesuffix("_API_KEY") + "_BASE_URL"

MODEL_FUNCTIONS: dict[str, ModelFunction] = {}
"""Models registered as Python functions (see :func:`register_model`)."""


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_model(
    name: str,
    fn: ModelFunction | None = None,
    *,
    base_url: str | None = None,
    model_id: str | None = None,
    api_key_env: str | None = None,
    extra_params: dict[str, Any] | None = None,
):
    """Register a model under *name*, for use as ``--model_name`` or ``--eval_model``.

    An OpenAI-compatible endpoint (vLLM, SGLang, Ollama, a gateway, ...)::

        register_model("my-qwen", base_url="http://localhost:8000/v1", model_id="Qwen/Qwen3-32B")

    ``model_id`` defaults to *name*; ``api_key_env`` names the environment
    variable that holds the key (``None``: the endpoint needs no key);
    ``extra_params`` are sent in the request body unchanged.

    A Python function that takes the messages in OpenAI format
    (``[{"role": ..., "content": ...}, ...]``) and returns the reply text::

        @register_model("my-hf-model")
        def generate(messages: list[dict]) -> str: ...

    The function is called from up to ``--concurrency`` threads at once.
    Names must not clash with a model that is already registered.
    """
    if name in MODEL_REGISTRY or name in MODEL_FUNCTIONS:
        raise ValueError(f"model {name!r} is already registered")
    if base_url is not None:
        if fn is not None:
            raise ValueError(f"model {name!r}: pass either a function or base_url, not both")
        MODEL_REGISTRY[name] = ModelConfig(
            model_id=model_id or name,
            base_url=base_url,
            api_key_env=api_key_env,
            extra_params=dict(extra_params or {}),
        )
        return None
    if model_id or api_key_env or extra_params:
        raise ValueError(f"model {name!r}: model_id, api_key_env and extra_params need base_url")

    def decorator(func: ModelFunction) -> ModelFunction:
        if not callable(func):
            raise TypeError(f"model {name!r}: expected a function, got {type(func).__name__}")
        MODEL_FUNCTIONS[name] = func
        return func

    return decorator if fn is None else decorator(fn)


def load_models_file(path: str) -> None:
    """Run the Python file *path*, whose :func:`register_model` calls add models."""
    if not os.path.isfile(path):
        raise ModelConfigError(f"models file not found: {path}")
    runpy.run_path(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_config(model_name: str) -> ModelConfig | None:
    """Return the :class:`ModelConfig` for *model_name*, or ``None``."""
    return MODEL_REGISTRY.get(model_name)


def resolve_client_params(model_name: str) -> tuple[str, str, str, dict[str, Any]]:
    """Resolve API credentials and model identifier for the endpoint *model_name*.

    Returns
    -------
    (api_key, base_url, model_id, extra_params)

    If *model_name* is not in the registry the function falls back to the
    generic ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` pair and uses
    *model_name* verbatim as the model identifier.  Raises
    :class:`ModelConfigError` if a required key is not set.
    """
    config = get_config(model_name)
    if config is not None:
        api_key = os.getenv(config.api_key_env) if config.api_key_env else "EMPTY"
        if not api_key:
            raise ModelConfigError(
                f"{model_name} needs its API key in ${config.api_key_env} (environment or .env)"
            )
        base_url = (config.base_url_env and os.getenv(config.base_url_env)) or config.base_url
        return api_key, base_url, config.model_id, config.extra_params

    # Fallback: generic OpenAI-compatible setup; a custom endpoint may need no key
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return api_key or "EMPTY", base_url, model_name, {}
    if not api_key:
        raise ModelConfigError(
            f"unknown model {model_name!r}: register it with register_model() in a --models_file, "
            "or set OPENAI_BASE_URL (and OPENAI_API_KEY if needed) to an OpenAI-compatible endpoint"
        )
    return api_key, "https://api.openai.com/v1", model_name, {}
