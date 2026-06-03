"""Log Compressor — cron automation for warm/cold compression.

Usage::

    uv run python -m tools.log_compressor weekly   # warm compression
    uv run python -m tools.log_compressor monthly  # cold compression
    uv run python -m tools.log_compressor status   # show compression status
"""

from __future__ import annotations

__version__ = "0.1.0"
