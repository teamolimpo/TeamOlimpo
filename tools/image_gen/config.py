"""Model configuration, pricing map, and default settings for image_gen.

All prices are hardcoded per the OpenRouter documentation as of 2026-05.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Model pricing map
# ---------------------------------------------------------------------------
# Structure:
#   {"type": "token", "input": ..., "output": ..., "per": "1M_tokens"}
#   {"type": "mp", "input_per_mp": ..., "output_per_mp": ..., "per": "megapixel"}
#   {"type": "fixed", "per_image": ..., "per": "image"}

MODEL_PRICES: dict[str, dict[str, Any]] = {
    "openai/gpt-5-image": {
        "type": "token",
        "input": 10.0,
        "output": 10.0,
        "per": "1M_tokens",
        "name": "GPT-5 Image",
    },
    "openai/gpt-5-image-mini": {
        "type": "token",
        "input": 2.50,
        "output": 2.00,
        "per": "1M_tokens",
        "name": "GPT-5 Image Mini",
    },
    "openai/gpt-5.4-image-2": {
        "type": "token",
        "input": 8.0,
        "output": 15.0,
        "per": "1M_tokens",
        "name": "GPT-5.4 Image 2",
    },
    "google/gemini-2.5-flash-image": {
        "type": "token",
        "input": 0.30,
        "output": 2.50,
        "per": "1M_tokens",
        "name": "Gemini 2.5 Flash Image",
    },
    "google/gemini-3.1-flash-image": {
        "type": "token",
        "input": 0.50,
        "output": 3.0,
        "per": "1M_tokens",
        "name": "Gemini 3.1 Flash Image",
    },
    "google/gemini-3-pro-image-preview": {
        "type": "token",
        "input": 2.0,
        "output": 12.0,
        "per": "1M_tokens",
        "name": "Gemini 3 Pro Image Preview",
    },
    "black-forest-labs/flux-2-pro": {
        "type": "mp",
        "input_per_mp": 0.015,
        "output_per_mp": 0.03,
        "per": "megapixel",
        "name": "FLUX 2 Pro",
    },
    "black-forest-labs/flux-2-max": {
        "type": "mp",
        "input_per_mp": 0.03,
        "output_per_mp": 0.07,
        "per": "megapixel",
        "name": "FLUX 2 Max",
    },
    "black-forest-labs/flux-2-flex": {
        "type": "mp",
        "per_mp": 0.06,
        "per": "megapixel",
        "name": "FLUX 2 Flex",
    },
    "black-forest-labs/flux-2-klein-4b": {
        "type": "mp",
        "first_mp": 0.014,
        "subsequent_mp": 0.001,
        "per": "megapixel",
        "name": "FLUX 2 Klein 4B",
    },
    "x-ai/grok-imagine-image-quality": {
        "type": "token",
        "input": 0,
        "output": 0,
        "special": "priced_per_token",
        "total": 11.98,
        "per": "1M_tokens",
        "name": "Grok Imagine Image Quality",
    },
    "bytedance-seed/seedream-4.5": {
        "type": "fixed",
        "per_image": 0.04,
        "per": "image",
        "name": "Seedream 4.5",
    },
}

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "openai/gpt-5-image-mini"
DEFAULT_SIZE = "1K"
DEFAULT_RATIO = "1:1"
DEFAULT_SITE_URL = "https://github.com/TeamOlimpo"
DEFAULT_APP_NAME = "TeamOlimpo-Fidia"

VALID_SIZES = {"1K", "2K", "4K"}
VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:2"}

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 180  # seconds (GPT-5 Image can be slow)
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

SIZE_TO_MP: dict[str, int] = {
    "1K": 1,
    "2K": 4,
    "4K": 16,
}

RATIO_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1024, 576),
    "9:16": (576, 1024),
    "4:3": (1024, 768),
    "3:2": (1024, 683),
}


def estimate_cost(model_id: str, size: str = "1K", prompt_tokens: int = 200) -> float:
    """Estimate the cost of an image generation request.

    Args:
        model_id: OpenRouter model identifier.
        size: Image size key (1K, 2K, 4K).
        prompt_tokens: Estimated token count for the prompt (default 200).

    Returns:
        Estimated cost in USD.
    """
    cfg = MODEL_PRICES.get(model_id)
    if cfg is None:
        return 0.0

    if cfg["type"] == "fixed":
        return float(cfg["per_image"])

    if cfg["type"] == "token":
        if cfg.get("special") == "priced_per_token":
            return (prompt_tokens / 1_000_000) * float(cfg["total"])
        inp = float(cfg["input"])
        out = float(cfg["output"])
        return (prompt_tokens / 1_000_000) * inp + (100 / 1_000_000) * out

    if cfg["type"] == "mp":
        mp = SIZE_TO_MP.get(size, 1)
        if "per_mp" in cfg:
            return float(cfg["per_mp"]) * mp
        if "first_mp" in cfg and "subsequent_mp" in cfg:
            extra = mp - 1
            return float(cfg["first_mp"]) + max(0, extra) * float(cfg["subsequent_mp"])
        if "input_per_mp" in cfg and "output_per_mp" in cfg:
            return (float(cfg["input_per_mp"]) + float(cfg["output_per_mp"])) * mp

    return 0.0


def estimate_resolution(size: str, ratio: str) -> tuple[int, int]:
    """Estimate image resolution in pixels for a given size and aspect ratio.

    Args:
        size: Image size key (1K, 2K, 4K).
        ratio: Aspect ratio key (1:1, 16:9, etc.).

    Returns:
        Tuple of (width, height) in pixels.
    """
    base = RATIO_DIMENSIONS.get(ratio, (1024, 1024))
    w, h = base
    if size == "2K":
        w, h = w * 2, h * 2
    elif size == "4K":
        w, h = w * 4, h * 4
    return (w, h)
