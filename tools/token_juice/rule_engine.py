"""C3 — Rule Engine.

Classificazione per tool + applicazione regole di compressione.
Three-layer overlay: builtin → user (~/.config/token-juice/rules/) → project (.tokenjuice/rules/)

Utility Gate: se ratio > 0.95 o output < 512 byte, passa l'originale.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Modelli dati
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchConfig:
    """Criteri di match per una regola."""

    argv0: list[str] | None = None
    argv_includes: list[list[str]] | None = None
    output_pattern: str | None = None


@dataclass(frozen=True)
class TransformsConfig:
    """Trasformazioni da applicare all'output."""

    strip_ansi: bool = False
    dedupe_adjacent: bool = False
    trim_empty_edges: bool = False
    strip_timestamps: bool = False
    collapse_paths: bool = False


@dataclass(frozen=True)
class FiltersConfig:
    """Filtri su singole righe."""

    skip_patterns: list[str] = field(default_factory=list)
    keep_patterns: list[str] | None = None


@dataclass(frozen=True)
class SummarizeConfig:
    """Configurazione summarization (head/tail)."""

    head: int = 0
    tail: int = 0


@dataclass(frozen=True)
class CounterConfig:
    """Estrattore di conteggi (es. righe modificate, test falliti)."""

    name: str
    pattern: str


@dataclass(frozen=True)
class FailureConfig:
    """Comportamento in caso di fallimento della regola."""

    preserve_on_failure: bool = True
    head: int = 12
    tail: int = 12


@dataclass(frozen=True)
class Rule:
    """Regola completa di compressione per tool."""

    id: str
    family: str
    match: MatchConfig
    transforms: TransformsConfig = field(default_factory=TransformsConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    summarize: SummarizeConfig = field(default_factory=SummarizeConfig)
    counters: list[CounterConfig] = field(default_factory=list)
    failure: FailureConfig = field(default_factory=FailureConfig)


# ---------------------------------------------------------------------------
# Caricamento regole
# ---------------------------------------------------------------------------

_RULES_DIR = Path(__file__).parent / "rules"
_USER_RULES_DIR = Path.home() / ".config" / "token-juice" / "rules"
_PROJECT_RULES_DIR = Path.cwd() / ".tokenjuice" / "rules"


def _load_rule_file(path: Path) -> dict[str, Any] | None:
    """Carica una singola regola da file JSON."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Impossibile caricare regola {path}: {e}")
        return None


def _parse_rule(data: dict[str, Any]) -> Rule | None:
    """Converte dict → Rule con validazione."""
    try:
        match_data = data.get("match", {})
        match = MatchConfig(
            argv0=match_data.get("argv0"),
            argv_includes=match_data.get("argv_includes"),
            output_pattern=match_data.get("output_pattern"),
        )

        transforms_data = data.get("transforms", {})
        transforms = TransformsConfig(
            strip_ansi=transforms_data.get("strip_ansi", False),
            dedupe_adjacent=transforms_data.get("dedupe_adjacent", False),
            trim_empty_edges=transforms_data.get("trim_empty_edges", False),
            strip_timestamps=transforms_data.get("strip_timestamps", False),
            collapse_paths=transforms_data.get("collapse_paths", False),
        )

        filters_data = data.get("filters", {})
        filters = FiltersConfig(
            skip_patterns=filters_data.get("skip_patterns", []),
            keep_patterns=filters_data.get("keep_patterns"),
        )

        summarize_data = data.get("summarize", {})
        summarize = SummarizeConfig(
            head=summarize_data.get("head", 0),
            tail=summarize_data.get("tail", 0),
        )

        counters = [
            CounterConfig(name=c["name"], pattern=c["pattern"]) for c in data.get("counters", [])
        ]

        failure_data = data.get("failure", {})
        failure = FailureConfig(
            preserve_on_failure=failure_data.get("preserve_on_failure", True),
            head=failure_data.get("head", 12),
            tail=failure_data.get("tail", 12),
        )

        return Rule(
            id=data["id"],
            family=data.get("family", "generic"),
            match=match,
            transforms=transforms,
            filters=filters,
            summarize=summarize,
            counters=counters,
            failure=failure,
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Regola malformata (id={data.get('id', '?')}): {e}")
        return None


def _discover_rules(directory: Path) -> list[Rule]:
    """Scansiona una directory per file JSON di regole."""
    if not directory.exists():
        return []
    rules: list[Rule] = []
    for fpath in sorted(directory.glob("*.json")):
        data = _load_rule_file(fpath)
        if data:
            rule = _parse_rule(data)
            if rule:
                rules.append(rule)
    return rules


def load_all_rules(
    builtin_dir: Path = _RULES_DIR,
    user_dir: Path = _USER_RULES_DIR,
    project_dir: Path = _PROJECT_RULES_DIR,
) -> list[Rule]:
    """Carica regole con overlay three-layer.

    Priority: builtin < user < project (project sovrascrive user che sovrascrive builtin).

    Returns:
        List[Rule]: Regole ordinate per id.
    """
    rules_map: dict[str, Rule] = {}

    for rule in _discover_rules(builtin_dir):
        rules_map[rule.id] = rule

    if user_dir.exists():
        for rule in _discover_rules(user_dir):
            rules_map[rule.id] = rule
            logger.debug(f"User rule overlay: {rule.id} ({user_dir})")

    if project_dir.exists():
        for rule in _discover_rules(project_dir):
            rules_map[rule.id] = rule
            logger.debug(f"Project rule overlay: {rule.id} ({project_dir})")

    return sorted(rules_map.values(), key=lambda r: r.id)


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


def _match_argv0(argv: list[str], patterns: list[str]) -> bool:
    """Verifica se il primo argomento (tool name) matcha uno dei pattern."""
    if not argv:
        return False
    tool = argv[0]
    return any(tool == p or tool.endswith("/" + p) for p in patterns)


def _match_argv_includes(argv: list[str], includes: list[list[str]]) -> bool:
    """Verifica se gli argomenti includono sequenze specifiche."""
    for seq in includes:
        for i, _arg in enumerate(argv):
            if all(
                argv[j] == seq[k] if j < len(argv) else False
                for j, k in zip(range(i, i + len(seq)), range(len(seq)), strict=False)
            ):
                break
        else:
            return False
    return True


def _match_output(output: str, pattern: str) -> bool:
    """Verifica se l'output matcha un pattern regex."""
    return bool(re.search(pattern, output))


def match_rule(argv: list[str], output: str, rule: Rule) -> bool:
    """Verifica se una regola si applica al comando/output dato.

    Args:
        argv: Lista degli argomenti del comando.
        output: Output del comando.
        rule: Regola da verificare.

    Returns:
        True se la regola matcha.
    """
    if rule.match.argv0:
        if not _match_argv0(argv, rule.match.argv0):
            return False
    if rule.match.argv_includes:
        if not _match_argv_includes(argv, rule.match.argv_includes):
            return False
    if rule.match.output_pattern:
        if not _match_output(output, rule.match.output_pattern):
            return False
    return True


def find_matching_rule(argv: list[str], output: str, rules: list[Rule]) -> Rule | None:
    """Trova la prima regola che matcha il comando/output.

    Args:
        argv: Lista degli argomenti del comando.
        output: Output del comando.
        rules: Lista di regole da provare.

    Returns:
        Rule | None: Prima regola matching, o None.
    """
    for rule in rules:
        if match_rule(argv, output, rule):
            return rule
    return None


# ---------------------------------------------------------------------------
# Trasformazioni
# ---------------------------------------------------------------------------


def _strip_ansi(text: str) -> str:
    """Rimuove codici ANSI dal testo."""
    ansi_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_pattern.sub("", text)


def _dedupe_adjacent(text: str) -> str:
    """Rimuove righe adiacenti duplicate."""
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for i, line in enumerate(lines):
        if i == 0 or line != lines[i - 1]:
            result.append(line)
    return "".join(result)


def _trim_empty_edges(text: str) -> str:
    """Rimuove righe vuote all'inizio e alla fine."""
    return text.strip("\n").strip()


def _strip_timestamps(text: str) -> str:
    """Rimuove timestamp in formato ISO dalle righe."""
    timestamp_pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*"
    )
    return timestamp_pattern.sub("", text)


def _collapse_paths(text: str) -> str:
    """Sostituisce path assoluti con nomi file."""
    path_pattern = re.compile(r"(?:/[^\s/]+)+/([^\s/]+)")
    return path_pattern.sub(r"\1", text)


def apply_transforms(text: str, transforms: TransformsConfig) -> str:
    """Applica trasformazioni configurate al testo.

    Args:
        text: Testo da trasformare.
        transforms: Configurazione trasformazioni.

    Returns:
        Testo trasformato.
    """
    result = text
    if transforms.strip_ansi:
        result = _strip_ansi(result)
    if transforms.dedupe_adjacent:
        result = _dedupe_adjacent(result)
    if transforms.trim_empty_edges:
        result = _trim_empty_edges(result)
    if transforms.strip_timestamps:
        result = _strip_timestamps(result)
    if transforms.collapse_paths:
        result = _collapse_paths(result)
    return result


# ---------------------------------------------------------------------------
# Filtri
# ---------------------------------------------------------------------------


def apply_filters(text: str, filters: FiltersConfig) -> str:
    """Applica filtri di skip/keep alle righe.

    Args:
        text: Testo da filtrare.
        filters: Configurazione filtri.

    Returns:
        Testo filtrato.
    """
    lines = text.splitlines(keepends=True)
    result: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if filters.keep_patterns:
            if any(re.search(p, stripped) for p in filters.keep_patterns):
                result.append(line)
            continue

        if filters.skip_patterns:
            if any(re.search(p, stripped) for p in filters.skip_patterns):
                continue

        result.append(line)

    return "".join(result)


# ---------------------------------------------------------------------------
# Summarization
# --------------------------------------------------------------------------


def apply_summarize(text: str, summarize: SummarizeConfig) -> str:
    """Applica head/tail summarization.

    Args:
        text: Testo da riassumere.
        summarize: Configurazione head/tail.

    Returns:
        Testo riassunto.
    """
    lines = text.splitlines(keepends=False)
    total = len(lines)

    if summarize.head == 0 and summarize.tail == 0:
        return text

    parts: list[str] = []

    if summarize.head > 0:
        parts.extend(lines[: summarize.head])

    if summarize.head > 0 and summarize.tail > 0 and (summarize.head + summarize.tail) < total:
        parts.append(f"\n... ({total - summarize.head - summarize.tail} lines omitted) ...\n")

    if summarize.tail > 0:
        parts.extend(lines[-summarize.tail :])

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Utility Gate
# --------------------------------------------------------------------------


def utility_gate(original: str, compressed: str) -> str:
    """Utility Gate: se ratio > 0.95 o output < 512 byte, passa l'originale.

    Args:
        original: Testo originale.
        compressed: Testo compresso.

    Returns:
        Testo da usare (originale se gate scatta, compresso altrimenti).
    """
    if len(compressed) < 512:
        return original

    ratio = len(compressed) / len(original) if original else 1.0
    if ratio > 0.95:
        return original

    return compressed


# ---------------------------------------------------------------------------
# Pipeline completa
# --------------------------------------------------------------------------


def process(
    argv: list[str],
    output: str,
    rules: list[Rule] | None = None,
) -> str:
    """Pipeline completa: classifica → trasforma → filtra → riassumi → gate.

    Args:
        argv: Argomenti del comando che ha prodotto l'output.
        output: Output del comando.
        rules: Lista di regole. Se None, carica tutte le regole.

    Returns:
        Output processato (compresso o originale se utility gate scatta).
    """
    if rules is None:
        rules = load_all_rules()

    rule = find_matching_rule(argv, output, rules)

    if rule is None:
        # Fallback: se nessuna regola matcha, passa l'output così com'è
        logger.debug(f"Nessuna regola matcha per argv={argv}. Output preserved.")
        return output

    logger.debug(f"Matching rule: {rule.id} (family={rule.family})")

    try:
        result = output
        result = apply_filters(result, rule.filters)
        result = apply_transforms(result, rule.transforms)
        result = apply_summarize(result, rule.summarize)
        result = utility_gate(output, result)
        return result
    except Exception as e:
        logger.error(f"Rule {rule.id} failed: {e}")
        if rule.failure.preserve_on_failure:
            lines = output.splitlines()
            head = rule.failure.head
            tail = rule.failure.tail
            if head + tail < len(lines):
                omitted = len(lines) - head - tail
                result_lines = (
                    lines[:head] + [f"\n... ({omitted} lines omitted) ...\n"] + lines[-tail:]
                )
                return "\n".join(result_lines)
            return output
        return output


# ---------------------------------------------------------------------------
# Conteggio metriche
# --------------------------------------------------------------------------


def count_matches(text: str, counters: list[CounterConfig]) -> dict[str, int]:
    """Conta occorrenze di pattern nel testo.

    Args:
        text: Testo da analizzare.
        counters: Lista di pattern da contare.

    Returns:
        Dict[str, int]: Mappa nome → conteggio.
    """
    results: dict[str, int] = {}
    for counter in counters:
        try:
            matches = re.findall(counter.pattern, text, re.MULTILINE)
            results[counter.name] = len(matches)
        except re.error:
            results[counter.name] = 0
    return results
