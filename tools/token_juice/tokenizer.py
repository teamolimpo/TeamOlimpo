"""C1 — Tokenizer Prioritario.

Segmenta input in blocchi "tecnici" (preservati) vs "prosa" (compressibili).
Priority-based overlap resolution (single-pass, greedy).

Priority: fence > inline-code > url > heading > path > date > version > number > identifier
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Modelli
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """Regola di tokenizzazione con priorità e pattern regex."""

    kind: str
    priority: int
    pattern: str


@dataclass(frozen=True)
class Span:
    """Span matchato nel testo: inizio, fine, e regola associata."""

    start: int
    end: int
    rule: Rule


@dataclass(frozen=True)
class Segment:
    """Segmento di output: testo, tipo, flag tecnico."""

    kind: str
    text: str
    is_technical: bool


# ---------------------------------------------------------------------------
# Regole builtin (ordinate per priorità discendente)
# ---------------------------------------------------------------------------

RULES: list[Rule] = [
    Rule(kind="fence", priority=100, pattern=r"```[\s\S]*?```|~~~[\s\S]*?~~~"),
    Rule(kind="inline-code", priority=90, pattern=r"`[^`\n]+`"),
    Rule(kind="url", priority=80, pattern=r"\bhttps?:\/\/[^\s)\]]+"),
    Rule(
        kind="heading",
        priority=70,
        pattern=r"(?m)^#{1,6}\s[^\n]*$",
    ),
    Rule(
        kind="path",
        priority=60,
        pattern=r"(?:(?:\.{1,2})?\/[\w.\-\/]+)",
    ),
    Rule(kind="date", priority=50, pattern=r"\b\d{4}-\d{2}-\d{2}\b"),
    Rule(kind="version", priority=40, pattern=r"\bv?\d+\.\d+(?:\.\d+)?\b"),
    Rule(kind="number", priority=30, pattern=r"\b\d+(?:\.\d+)?\b"),
    Rule(kind="identifier", priority=20, pattern=r"\b[a-z]+[A-Z][A-Za-z0-9]*\b"),
]


# ---------------------------------------------------------------------------
# Core tokenizer
# ---------------------------------------------------------------------------


def _find_all_spans(text: str, rules: list[Rule]) -> list[Span]:
    """Trova tutti gli span per tutte le regole nel testo."""
    spans: list[Span] = []
    for rule in rules:
        try:
            for match in re.finditer(rule.pattern, text):
                spans.append(Span(start=match.start(), end=match.end(), rule=rule))
        except re.error:
            continue
    return spans


def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Single-pass, greedy overlap resolution.

    Spans ordinati per start ASC, poi priority DESC.
    Primo span a ogni start vince. Skip span che cadono dentro un match già preso.
    """
    if not spans:
        return []

    # Ordina: start ASC, poi priority DESC (e end DESC come tiebreaker)
    spans.sort(key=lambda s: (s.start, -s.rule.priority, -s.end))

    resolved: list[Span] = []
    current_end = 0

    for span in spans:
        if span.start >= current_end:
            resolved.append(span)
            current_end = span.end
        elif span.end > current_end:
            # Span inizia dentro un match ma si estende oltre
            # Lo prendiamo solo se ha priorità maggiore (già garantito dall'ordinamento)
            if span.rule.priority > resolved[-1].rule.priority:
                # Rimpiazza l'ultimo
                current_end = span.end
                resolved[-1] = span

    return resolved


def _text_to_segments(text: str, resolved: list[Span]) -> list[Segment]:
    """Converte il testo in segmenti alternando tecnico/prosa."""
    segments: list[Segment] = []
    cursor = 0

    for span in resolved:
        # Prosa prima dello span
        if span.start > cursor:
            prose = text[cursor : span.start]
            if prose.strip():
                segments.append(Segment(kind="prose", text=prose, is_technical=False))

        # Span tecnico
        span_text = text[span.start : span.end]
        segments.append(Segment(kind=span.rule.kind, text=span_text, is_technical=True))
        cursor = span.end

    # Prosa residua dopo l'ultimo span
    if cursor < len(text):
        prose = text[cursor:]
        if prose.strip():
            segments.append(Segment(kind="prose", text=prose, is_technical=False))

    return segments


def tokenize(
    text: str,
    custom_rules: list[Rule] | None = None,
) -> list[Segment]:
    """Segmenta input in blocchi tecnici e prosa.

    Args:
        text: Testo da tokenizzare.
        custom_rules: Regole custom (override parziale delle builtin).

    Returns:
        List[Segment]: Lista ordinata di segmenti.
    """
    if not text or not text.strip():
        return []

    rules = custom_rules if custom_rules else RULES
    spans = _find_all_spans(text, rules)
    resolved = _resolve_overlaps(spans)
    return _text_to_segments(text, resolved)


# ---------------------------------------------------------------------------
# Helper pubblici
# ---------------------------------------------------------------------------


def extract_technical(text: str, custom_rules: list[Rule] | None = None) -> str:
    """Estrae solo i blocchi tecnici dal testo."""
    segments = tokenize(text, custom_rules)
    return "".join(seg.text for seg in segments if seg.is_technical)


def extract_prose(text: str, custom_rules: list[Rule] | None = None) -> str:
    """Estrae solo i blocchi prosa dal testo."""
    segments = tokenize(text, custom_rules)
    return "".join(seg.text for seg in segments if not seg.is_technical)


def count_technical_tokens(text: str) -> tuple[int, int]:
    """Conta token tecnici vs totali (split per whitespace approssimativo).

    Returns:
        (tech_tokens, total_tokens)
    """
    segments = tokenize(text)
    total = len(text.split())
    tech = sum(len(seg.text.split()) for seg in segments if seg.is_technical)
    return tech, total
