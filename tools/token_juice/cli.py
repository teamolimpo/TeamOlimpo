"""CLI per Token Juice Layer.

Usage:
    token-juice tokenize <text>          # C1 — Tokenizer
    token-juice compress <text>           # C2 — Compressor
    token-juice process <argv> <output>   # C3 — Rule Engine
    token-juice rules                     # Lista regole caricate
"""

from __future__ import annotations

import json
import sys

import typer
from loguru import logger

from tools.token_juice.compressor import ProseCompressor as C2
from tools.token_juice.rule_engine import load_all_rules
from tools.token_juice.rule_engine import process as c3_process
from tools.token_juice.tokenizer import tokenize

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="token-juice",
    help="Token Juice Layer — compressione intelligente del contesto per LLM.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


# ---------------------------------------------------------------------------
# C1 — Tokenizer
# ---------------------------------------------------------------------------


@app.command(name="tokenize")
def tokenize_cmd(
    text: str = typer.Argument(..., help="Testo da tokenizzare."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug log."),
) -> None:
    """Segmenta input in blocchi tecnici vs prosa."""
    _setup_logging(verbose)

    segments = tokenize(text)
    if json_output:
        data = [
            {"kind": s.kind, "text": s.text, "is_technical": s.is_technical, "len": len(s.text)}
            for s in segments
        ]
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        for seg in segments:
            label = "🔧" if seg.is_technical else "📝"
            typer.echo(f"{label} [{seg.kind:15s}] ({len(seg.text):>4d} chars) {seg.text[:80]}")
        total = sum(len(s.text) for s in segments)
        tech = sum(len(s.text) for s in segments if s.is_technical)
        ratio = tech / total if total > 0 else 0
        typer.echo(f"\nTotale: {total} chars | Tecnico: {tech} chars ({ratio:.1%})")


# ---------------------------------------------------------------------------
# C2 — Compressor
# ---------------------------------------------------------------------------


@app.command(name="compress")
def compress_cmd(
    text: str = typer.Argument(..., help="Testo prosa da comprimere."),
    intensity: str = typer.Option("lite", "--intensity", "-i", help="Livello: lite, full, ultra."),
    action: str = typer.Option("compress", "--action", "-a", help="compress o expand."),
    locale: str = typer.Option("en", "--locale", "-l", help="Lingua: en o it."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug log."),
) -> None:
    """Comprime o espande contenuto prosa."""
    _setup_logging(verbose)

    compressor = C2(intensity, locale=locale)

    if action == "compress":
        result = compressor.compress(text)
        original_len = len(text)
        compressed_len = len(result)
        ratio = compressed_len / original_len if original_len > 0 else 1.0

        typer.echo(result)
        typer.echo(
            f"\nOriginale: {original_len} chars | Compresso: {compressed_len} chars"
            f" | Ratio: {ratio:.2%}"
        )
    elif action == "expand":
        result = compressor.expand(text)
        typer.echo(result)
    else:
        typer.echo(f"❌ Azione sconosciuta: {action}", err=True)
        raise typer.Exit(code=2)


# ---------------------------------------------------------------------------
# C3 — Rule Engine
# ---------------------------------------------------------------------------


@app.command(name="process")
def process_cmd(
    argv: list[str] = typer.Argument(  # noqa: B008
        ..., help="Argomenti del comando (es. git status)."
    ),
    output: str = typer.Option(
        "", "--output", "-o", help="Output del comando. Se omesso, legge da stdin."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug log."),
) -> None:
    """Classifica e applica regole di compressione."""
    _setup_logging(verbose)

    if not output:
        output = sys.stdin.read()

    rules = load_all_rules()
    result = c3_process(argv, output, rules)

    sys.stdout.write(result)
    if not result.endswith("\n"):
        sys.stdout.write("\n")

    # Metriche
    original_len = len(output)
    compressed_len = len(result)
    ratio = compressed_len / original_len if original_len > 0 else 1.0
    logger.info(
        f"Originale: {original_len} chars | Compresso: {compressed_len} chars | Ratio: {ratio:.2%}"
    )


# ---------------------------------------------------------------------------
# Regole
# ---------------------------------------------------------------------------


@app.command(name="rules")
def rules_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug log."),
) -> None:
    """Lista tutte le regole caricate."""
    _setup_logging(verbose)

    rules = load_all_rules()
    typer.echo(f"Regole caricate: {len(rules)}\n")

    for rule in rules:
        match_str = " | ".join(
            filter(
                None,
                [
                    f"argv0={rule.match.argv0}" if rule.match.argv0 else None,
                    f"includes={rule.match.argv_includes}" if rule.match.argv_includes else None,
                ],
            )
        )
        typer.echo(f"  {rule.id:30s} [{rule.family:20s}] {match_str}")


if __name__ == "__main__":
    app()
