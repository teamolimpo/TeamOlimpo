"""Package tools — automazioni del Team Olimpo.

KBA tools (private) are in Library/tools/ — this __init__.py extends
the package search path so they remain importable as tools.kba_*.
"""

from pathlib import Path

_lib_tools = Path(__file__).parent.parent / "Library" / "tools"
if _lib_tools.is_dir():
    import sys

    _lib_tools_str = str(_lib_tools)
    if _lib_tools_str not in __path__:
        __path__ = list(__path__) + [_lib_tools_str]
