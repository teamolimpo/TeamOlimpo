"""Image Generation Tool — OpenRouter API image generation for Fidia.

This module provides a CLI interface for generating images via OpenRouter's
chat completions API (Gemini/GPT-5/FLUX/Seedream style models). It handles
API calls, base64 image decoding, file saving with hash collision detection,
cost estimation, and error reporting.

Typical usage::

    python -m tools.image_gen generate "un gatto cyberpunk" \\
        --model openai/gpt-5-image-mini --ratio 16:9 \\
        --output Library/deliverables/images/2026/05/
"""

from __future__ import annotations

__version__ = "1.0.0"
