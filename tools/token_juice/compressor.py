"""C2 — Prose Compressor.

Compressione deterministica del contenuto prosa con tre livelli di intensità:
    - lite: rimozione cortesie base, abbreviazioni soft
    - full: rimozione moderata, abbreviazioni comuni
    - ultra: rimozione aggressiva, abbreviazioni estreme

Supporta round-trip expand (lossy su fillers, reversibile su abbreviazioni).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

Intensity = str  # "lite" | "full" | "ultra"

_LEXICON_PATH = Path(__file__).parent / "lexicon.json"

# ---------------------------------------------------------------------------
# Caricamento lexicon
# ---------------------------------------------------------------------------


def _load_lexicon(path: Path = _LEXICON_PATH) -> dict:
    """Carica il lexicon da file JSON.

    Args:
        path: Path al file lexicon.json.

    Returns:
        Dict con chiavi 'phrases', 'abbreviations', 'contractions'.
    """
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Lexicon non trovato: {path}. Uso lexicon vuoto.")
        return {"phrases": {}, "abbreviations": {}, "contractions": {}}
    except json.JSONDecodeError as e:
        logger.error(f"Lexicon malformato: {e}")
        return {"phrases": {}, "abbreviations": {}, "contractions": {}}


_LEXICON = _load_lexicon()


def _get_phrases(intensity: Intensity, locale: str = "en") -> list[str]:
    """Recupera tutte le frasi da rimuovere per un dato intensity level.

    Args:
        intensity: Livello di compressione ('lite', 'full', 'ultra').
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Returns:
        Lista di frasi da rimuovere.
    """
    source = _LEXICON.get("it", {}) if locale == "it" else _LEXICON
    phrases: list[str] = []
    level_phrases = source.get("phrases", {}).get(intensity, {})
    for _category, items in level_phrases.items():
        phrases.extend(items)
    return phrases


def _get_abbreviations(intensity: Intensity, locale: str = "en") -> dict[str, str]:
    """Recupera le abbreviazioni per un dato intensity level.

    Args:
        intensity: Livello di compressione ('lite', 'full', 'ultra').
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Returns:
        Dict parola → abbreviazione.
    """
    source = _LEXICON.get("it", {}) if locale == "it" else _LEXICON
    level = source.get("abbreviations", {}).get(intensity, {})
    return dict(level)


def _build_expand_map(intensity: Intensity, locale: str = "en") -> dict[str, str]:
    """Costruisce la mappa inversa (abbreviazione → parola) per expand.

    Args:
        intensity: Livello di compressione ('lite', 'full', 'ultra').
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Returns:
        Dict abbreviazione → parola.
    """
    abbr = _get_abbreviations(intensity, locale=locale)
    return {v: k for k, v in abbr.items()}


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------


class ProseCompressor:
    """Compressore deterministico di contenuto prosa.

    Args:
        intensity: Livello di compressione ('lite', 'full', 'ultra').
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Usage:
        compressor = ProseCompressor("full")
        compressed = compressor.compress("Hello, please find the configuration attached.")
        expanded   = compressor.expand(compressed)

        # Italiano
        it_compressor = ProseCompressor("ultra", locale="it")
        it_compressed = it_compressor.compress("Si prega di verificare la configurazione.")
    """

    def __init__(self, intensity: Intensity = "lite", locale: str = "en") -> None:
        if intensity not in ("lite", "full", "ultra"):
            logger.warning(f"Intensity '{intensity}' non valida. Uso 'lite'.")
            intensity = "lite"

        if locale not in ("en", "it"):
            logger.warning(f"Locale '{locale}' non supportato. Uso 'en'.")
            locale = "en"

        self.intensity: Intensity = intensity
        self.locale: str = locale
        self._phrases: list[str] = _get_phrases(intensity, locale=locale)
        self._abbreviations: dict[str, str] = _get_abbreviations(intensity, locale=locale)
        self._expand_map: dict[str, str] = _build_expand_map(intensity, locale=locale)

    # ------------------------------------------------------------------
    # Compress
    # ------------------------------------------------------------------

    def compress(self, text: str) -> str:
        """Comprime il testo applicando tutte le operazioni.

        Ordine: removePhrases → abbreviate → collapseWhitespace → strip

        Args:
            text: Testo prosa da comprimere.

        Returns:
            Testo compresso.
        """
        result = text
        result = self._remove_phrases(result)
        result = self._abbreviate(result)
        result = self._collapse_whitespace(result)
        return result.strip()

    def _remove_phrases(self, text: str) -> str:
        """Rimuove frasi di cortesia, hedges, fillers."""
        result = text
        for phrase in sorted(self._phrases, key=len, reverse=True):
            # Case-insensitive replace con boundary di parola
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
            result = pattern.sub("", result)
        return result

    def _abbreviate(self, text: str) -> str:
        """Sostituisce parole lunghe con abbreviazioni."""
        result = text
        for word, abbr in sorted(
            self._abbreviations.items(), key=lambda x: len(x[0]), reverse=True
        ):
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            result = pattern.sub(abbr, result)
        return result

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        """Collassa spazi multipli in uno singolo."""
        return re.sub(r"\s+", " ", text).strip()

    # ------------------------------------------------------------------
    # Expand
    # ------------------------------------------------------------------

    def expand(self, text: str) -> str:
        """Espande le abbreviazioni (lossy su fillers e frasi rimosse).

        Note:
            Le frasi rimosse (pleasantries, hedges, fillers) non sono
            recuperabili. Questo metodo ripristina solo le abbreviazioni.
        """
        result = text
        for abbr, word in sorted(self._expand_map.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.IGNORECASE)
            result = pattern.sub(word, result)
        return result


# ---------------------------------------------------------------------------
# Shortcut functions
# ---------------------------------------------------------------------------

_DEFAULT_COMPRESSOR = ProseCompressor("lite")


def compress(text: str, intensity: Intensity = "lite", locale: str = "en") -> str:
    """Shortcut per compressione prosa.

    Args:
        text: Testo da comprimere.
        intensity: Livello di compressione.
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Returns:
        Testo compresso.
    """
    compressor = ProseCompressor(intensity, locale=locale)
    return compressor.compress(text)


def expand(text: str, intensity: Intensity = "lite", locale: str = "en") -> str:
    """Shortcut per espansione prosa.

    Args:
        text: Testo compresso da espandere.
        intensity: Livello di compressione usato.
        locale: Lingua del lexicon ('en' o 'it'). Default 'en'.

    Returns:
        Testo espanso (lossy).
    """
    compressor = ProseCompressor(intensity, locale=locale)
    return compressor.expand(text)
