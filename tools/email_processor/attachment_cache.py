"""Cache content-addressable per allegati email — mapping SHA256 full → metadati.

Struttura del JSON::

    {
      "<sha256_full>": {
        "original_name": "report.pdf",
        "path": "Inbox/attachments/2026/05/a3f8c2d1e5b790ab.pdf",
        "size": 123456,
        "first_seen": "2026-05-19T12:00:00",
        "email_ids": ["<message-id-1>", "<message-id-2>"]
      }
    }

Uso::

    cache = load_cache(cache_path)
    update_cache(cache, sha256_full, original_name, attach_path, size, message_id)
    save_cache(cache_path, cache)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Path del file cache (fisso in tools/email_processor/)
# ---------------------------------------------------------------------------

CACHE_PATH = Path(__file__).resolve().parent / "attachment_cache.json"


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------


def load_cache(cache_path: Path = CACHE_PATH) -> dict:
    """Carica il file JSON di cache da disco.

    Restituisce un dict vuoto se il file non esiste o non è parsabile
    (il tool continua comunque, al prossimo save sovrascrive).

    Args:
        cache_path: Percorso del file JSON cache.

    Returns:
        Dizionario ``{sha256_full: entry}`` già deserializzato.
    """
    if not cache_path.exists():
        logger.debug(f"Cache allegati non presente ({cache_path}), partenza vuota")
        return {}

    try:
        raw = cache_path.read_text(encoding="utf-8")
        data: dict = json.loads(raw)
        if not isinstance(data, dict):
            logger.warning(
                f"Cache allegati {cache_path}: atteso dict, trovato {type(data).__name__}, reset"
            )
            return {}
        logger.debug(f"Cache allegati caricata: {cache_path} ({len(data)} entry)")
        return data
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Cache allegati {cache_path} non valida, reset: {e}")
        return {}


def save_cache(cache: dict, cache_path: Path = CACHE_PATH) -> None:
    """Scrive il dizionario cache su disco come JSON indentato.

    Args:
        cache: Dizionario ``{sha256_full: entry}``.
        cache_path: Percorso del file JSON cache.
    """
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        logger.debug(f"Cache allegati salvata: {cache_path} ({len(cache)} entry)")
    except OSError as e:
        logger.warning(f"Impossibile salvare cache allegati {cache_path}: {e}")


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_cache(
    cache: dict,
    sha256_full: str,
    original_name: str,
    attach_path: str,
    size: int,
    message_id: str,
) -> None:
    """Aggiorna (o crea) una entry nella cache.

    Se *sha256_full* è già presente, aggiunge *message_id* alla lista
    ``email_ids`` (se non già presente). Altrimenti crea una nuova entry.

    Args:
        cache: Dizionario cache (modificato in-place).
        sha256_full: SHA256 hex digest completo del payload.
        original_name: Nome originale dell'allegato.
        attach_path: Path relativo (tipo ``Inbox/attachments/2026/05/hash.pdf``).
        size: Dimensione in byte.
        message_id: Message-ID dell'email (con ``<>``).
    """
    if sha256_full in cache:
        entry = cache[sha256_full]
        if message_id not in entry["email_ids"]:
            entry["email_ids"].append(message_id)
            logger.debug(f"Cache hit: {sha256_full[:16]} → aggiunto message_id {message_id}")
        else:
            logger.debug(f"Cache hit: {sha256_full[:16]} — message_id già presente, skip")
    else:
        now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cache[sha256_full] = {
            "original_name": original_name,
            "path": attach_path,
            "size": size,
            "first_seen": now_str,
            "email_ids": [message_id],
        }
        logger.debug(f"Cache miss: {sha256_full[:16]} — nuova entry ({original_name}, {size} byte)")
