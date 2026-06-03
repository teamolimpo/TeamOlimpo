"""Entry point: python -m tools.log_compressor

Runs the log compressor CLI::

    uv run python -m tools.log_compressor weekly
    uv run python -m tools.log_compressor monthly
    uv run python -m tools.log_compressor status
"""

from tools.log_compressor.main import app

app()
