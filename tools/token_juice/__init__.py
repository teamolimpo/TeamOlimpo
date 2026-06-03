"""Token Juice Layer — compressione intelligente del contesto per LLM.

Moduli:
    tokenizer   — C1: tokenizer prioritario (segmentazione input)
    compressor  — C2: compressione deterministica della prosa
    rule_engine — C3: classificazione per tool + applicazione regole
"""

from __future__ import annotations

__version__ = "0.1.0"


def maybe_compress(
    text: str,
    threshold: int = 1024,
    intensity: str = "ultra",
    argv: list[str] | None = None,
) -> str:
    """Comprime il testo se supera la soglia.

    Args:
        text: Testo da comprimere
        threshold: Se len(text) < threshold, restituisce invariato
        intensity: Livello compressione ('lite', 'full', 'ultra')
        argv: Se fornito, usa C3 Rule Engine con classifica per tool
              Se None, applica solo C2 Prose Compressor

    Returns:
        Testo compresso (o originale se sotto soglia o errore)
    """
    if len(text) < threshold:
        return text
    try:
        if argv:
            from tools.token_juice.rule_engine import load_all_rules
            from tools.token_juice.rule_engine import process as c3_process

            rules = load_all_rules()
            text = c3_process(argv, text, rules)
        from tools.token_juice.compressor import compress as c2_compress

        text = c2_compress(text, intensity=intensity)
        return text
    except Exception:
        return text  # fallback safe
