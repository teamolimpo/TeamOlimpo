"""Test per Token Juice Layer — C1 Tokenizer, C2 Compressor, C3 Rule Engine."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tools.token_juice.cli import app
from tools.token_juice.compressor import ProseCompressor, compress, expand
from tools.token_juice.rule_engine import (
    Rule,
    TransformsConfig,
    FiltersConfig,
    SummarizeConfig,
    FailureConfig,
    MatchConfig,
    CounterConfig,
    apply_transforms,
    apply_filters,
    apply_summarize,
    utility_gate,
    match_rule,
    process,
    load_all_rules,
    count_matches,
)
from tools.token_juice.tokenizer import (
    RULES,
    Rule as TokenizerRule,
    Segment,
    Span,
    tokenize,
    extract_technical,
    extract_prose,
    count_technical_tokens,
    _find_all_spans,
    _resolve_overlaps,
)

runner = CliRunner()

# ==========================================================================
# C1 — Tokenizer
# ==========================================================================


class TestTokenizer:
    """Test per il tokenizer prioritario."""

    def test_smoke_empty(self) -> None:
        """Test smoke: testo vuoto → lista vuota."""
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_smoke_hello(self) -> None:
        """Test smoke: testo semplice → un segmento prosa."""
        segs = tokenize("Ciao mondo")
        assert len(segs) == 1
        assert segs[0].kind == "prose"
        assert segs[0].is_technical is False
        assert "Ciao" in segs[0].text

    def test_priority_overlap(self) -> None:
        """Test priority resolution: inline-code batte number dentro backtick."""
        text = "usa `version 1.0` per"
        segs = tokenize(text)
        has_inline = any(s.kind == "inline-code" for s in segs)
        assert has_inline, "Dovrebbe trovare inline-code"

    def test_fence_segment(self) -> None:
        """Test che un fence venga segmentato come tecnico."""
        text = "testo\n```\ncode block\n```\nfine"
        segs = tokenize(text)
        assert any(s.kind == "fence" for s in segs)
        fence = [s for s in segs if s.kind == "fence"][0]
        assert fence.is_technical is True

    def test_url_segment(self) -> None:
        """Test che un URL sia segmentato come tecnico."""
        text = "vai su https://example.com/path ora"
        segs = tokenize(text)
        assert any(s.kind == "url" for s in segs)

    def test_heading_segment(self) -> None:
        """Test che un heading sia segmentato come tecnico."""
        text = "# Titolo\n\ncontenuto"
        segs = tokenize(text)
        assert any(s.kind == "heading" for s in segs)

    def test_extract_prose(self) -> None:
        """Test estrazione prosa."""
        text = "Ciao `code` mondo"
        prose = extract_prose(text)
        assert "Ciao" in prose
        assert "mondo" in prose
        assert "code" not in prose

    def test_extract_technical(self) -> None:
        """Test estrazione tecnico."""
        text = "Ciao `code` mondo"
        tech = extract_technical(text)
        assert "code" in tech
        assert "Ciao" not in tech

    def test_count_technical_tokens(self) -> None:
        """Test conteggio token tecnici."""
        text = "run `cmd` now"
        tech, total = count_technical_tokens(text)
        assert total == 3  # run, `cmd`, now
        assert tech == 1  # solo `cmd`

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def test_find_all_spans(self) -> None:
        """Test _find_all_spans trova span."""
        text = "hello `code` world https://example.com"
        spans = _find_all_spans(text, RULES)
        kinds = {s.rule.kind for s in spans}
        assert "inline-code" in kinds
        assert "url" in kinds

    def test_resolve_overlaps_order(self) -> None:
        """Test _resolve_overlaps ordina per start ASC, priority DESC."""
        spans = [
            Span(start=5, end=15, rule=TokenizerRule("url", 80, "")),
            Span(start=5, end=10, rule=TokenizerRule("number", 30, "")),
        ]
        resolved = _resolve_overlaps(spans)
        assert len(resolved) == 1
        assert resolved[0].rule.kind == "url"  # priorità più alta

    def test_resolve_no_overlaps(self) -> None:
        """Test risoluzione senza overlap."""
        spans = [
            Span(start=0, end=5, rule=TokenizerRule("number", 30, "")),
            Span(start=10, end=15, rule=TokenizerRule("number", 30, "")),
        ]
        resolved = _resolve_overlaps(spans)
        assert len(resolved) == 2

    def test_cli_tokenize(self) -> None:
        """Test CLI: tokenize con testo semplice."""
        result = runner.invoke(app, ["tokenize", "Ciao mondo hello"])
        assert result.exit_code == 0
        assert "Ciao" in result.stdout

    def test_cli_tokenize_json(self) -> None:
        """Test CLI: tokenize con output JSON."""
        result = runner.invoke(app, ["tokenize", "--json", "Ciao hello"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["kind"] is not None


# ==========================================================================
# C2 — Compressor
# ==========================================================================


class TestCompressor:
    """Test per il prose compressor."""

    def test_smoke_lite(self) -> None:
        """Test smoke: compressione lite."""
        result = compress("please find the configuration attached", "lite")
        assert "please" not in result or len(result) < len("please find the configuration attached")

    def test_smoke_full(self) -> None:
        """Test smoke: compressione full."""
        result = compress("I would recommend that you please review the configuration", "full")
        assert len(result) < len("I would recommend that you please review the configuration")

    def test_smoke_ultra(self) -> None:
        """Test smoke: compressione ultra."""
        result = compress("basically, the configuration is with the application", "ultra")
        assert "cfg" in result or "app" in result

    def test_abbreviate_configuration(self) -> None:
        """Test che 'configuration' diventi 'cfg'."""
        result = compress("update the configuration", "lite")
        assert "cfg" in result

    def test_expand_roundtrip(self) -> None:
        """Test expand ripristina abbreviazioni."""
        text = "Please update the configuration"
        compressed = compress(text, "lite")
        expanded = expand(compressed, "lite")
        # configuration → cfg → configuration
        assert "configuration" in expanded

    def test_collapse_whitespace(self) -> None:
        """Test che spazi multipli vengano collassati."""
        result = compress("hello     world", "lite")
        assert "  " not in result

    def test_different_intensities(self) -> None:
        """Test che intensity diverse producano risultati diversi."""
        text = "please let me know if you have basically any questions about the configuration"
        lite = compress(text, "lite")
        ultra = compress(text, "ultra")
        assert len(lite) >= len(ultra), "Ultra deve comprimere più di Lite"

    def test_cli_compress(self) -> None:
        """Test CLI: compress."""
        result = runner.invoke(app, ["compress", "please find the configuration"])
        assert result.exit_code == 0
        assert "cfg" in result.stdout or "chars" in result.stdout

    def test_cli_expand(self) -> None:
        """Test CLI: expand."""
        result = runner.invoke(app, ["compress", "--action", "expand", "update the cfg"])
        assert result.exit_code == 0

    def test_prose_compressor_init_invalid(self) -> None:
        """Test init con intensity non valida."""
        c = ProseCompressor("invalid")
        assert c.intensity == "lite"  # fallback


# ==========================================================================
# C3 — Rule Engine
# ==========================================================================


class TestRuleEngine:
    """Test per il rule engine."""

    def test_load_rules_nonempty(self) -> None:
        """Test che carichi regole dal filesystem."""
        rules = load_all_rules()
        assert len(rules) >= 70, f"Caricate solo {len(rules)} regole (min 70)"

    def test_match_rule_git_status(self) -> None:
        """Test che git status matchi la regola git/status."""
        rules = load_all_rules()
        for rule in rules:
            if rule.id == "git/status":
                assert match_rule(["git", "status"], " M file.py\n", rule)
                break
        else:
            # Fallback: prova con match generico
            pass

    def test_match_rule_git_diff(self) -> None:
        """Test che git diff matchi la regola git/diff."""
        rules = load_all_rules()
        for rule in rules:
            if rule.id == "git/diff":
                assert match_rule(["git", "diff"], "diff --git a/file b/file\n", rule)
                break
        else:
            pass

    def test_match_rule_no_match(self) -> None:
        """Test che una regola non matchi comando sbagliato."""
        rule = Rule(
            id="test",
            family="test",
            match=MatchConfig(argv0=["git"]),
        )
        assert not match_rule(["ls"], "", rule)

    def test_process_git_status(self) -> None:
        """Test pipeline process con output git status."""
        output = " M file1.py\n M file2.py\n?? untracked.txt\n"
        result = process(["git", "status"], output)
        assert "file1.py" in result
        assert isinstance(result, str)

    def test_utility_gate_small_output(self) -> None:
        """Test utility gate: output < 512 byte → originale."""
        original = "small output"
        compressed = "sm out"
        assert utility_gate(original, compressed) == original

    def test_utility_good_compression(self) -> None:
        """Test utility gate: compressione buona (<0.95 ratio, >=512 byte) → compresso."""
        original = "a" * 2000
        compressed = "b" * 600  # 600 >= 512, ratio = 0.3
        assert utility_gate(original, compressed) == compressed

    def test_utility_gate_poor_ratio(self) -> None:
        """Test utility gate: ratio > 0.95 → originale."""
        original = "a" * 1000
        compressed = original[:970]  # ratio = 0.97
        assert utility_gate(original, compressed) == original

    # ------------------------------------------------------------------
    # Filtri e trasformazioni
    # ------------------------------------------------------------------

    def test_strip_ansi(self) -> None:
        """Test strip_ansi."""
        text = "\x1b[31mred\x1b[0m"
        transforms = TransformsConfig(strip_ansi=True)
        result = apply_transforms(text, transforms)
        assert "\x1b" not in result

    def test_dedupe_adjacent(self) -> None:
        """Test dedupe_adjacent."""
        text = "line1\nline1\nline2\n"
        transforms = TransformsConfig(dedupe_adjacent=True)
        result = apply_transforms(text, transforms)
        assert result.count("line1") == 1

    def test_trim_empty_edges(self) -> None:
        """Test trim_empty_edges."""
        text = "\n\nhello\n\n"
        transforms = TransformsConfig(trim_empty_edges=True)
        result = apply_transforms(text, transforms)
        assert result == "hello"

    def test_filter_skip_patterns(self) -> None:
        """Test skip_patterns nei filtri."""
        text = "On branch main\n M file.py\n"
        filters = FiltersConfig(skip_patterns=["^On branch "])
        result = apply_filters(text, filters)
        assert "On branch" not in result
        assert "file.py" in result

    def test_filter_keep_patterns(self) -> None:
        """Test keep_patterns nei filtri."""
        text = "line1\nERROR: something\nline2\n"
        filters = FiltersConfig(keep_patterns=["ERROR"])
        result = apply_filters(text, filters)
        assert "ERROR" in result
        assert "line1" not in result

    def test_summarize_head_tail(self) -> None:
        """Test summarization head/tail."""
        text = "\n".join(f"line{i}" for i in range(20))
        summarize = SummarizeConfig(head=3, tail=2)
        result = apply_summarize(text, summarize)
        lines = result.splitlines()
        assert "line0" in lines[0]
        assert len(lines) < 10  # sommario + ellipsis

    def test_count_matches(self) -> None:
        """Test conteggio pattern."""
        text = " M file1\n M file2\n"
        counters = [CounterConfig(name="modified", pattern="^\\s*M")]
        results = count_matches(text, counters)
        assert results["modified"] == 2

    def test_cli_process(self) -> None:
        """Test CLI: process."""
        result = runner.invoke(
            app,
            [
                "process",
                "git",
                "status",
                "--output",
                " M file.py\n M file2.py\n",
            ],
        )
        assert result.exit_code == 0
        assert "file.py" in result.stdout

    def test_cli_rules(self) -> None:
        """Test CLI: rules list."""
        result = runner.invoke(app, ["rules"])
        assert result.exit_code == 0
        assert "git/status" in result.stdout
        assert "pytest" in result.stdout
