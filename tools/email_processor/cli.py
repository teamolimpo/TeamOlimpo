"""CLI per email_processor — tool Typer per gestione email in vault Obsidian.

Configurazione (priorità decrescente):
    1. Variabili d'ambiente: EMAIL_DIR, EMAIL_VAULT_ROOT
    2. File tools/config.yaml (sezione email_processor)
    3. Fallback a stringa vuota → errore chiaro

Uso:
    python -m tools.email_processor import --help
    python -m tools.email_processor process --help
    python -m tools.email_processor status --help
"""

from __future__ import annotations

import email
import email.message
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import getaddresses
from pathlib import Path

import yaml
import typer
from dateutil import parser as dateutil_parser
from loguru import logger

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
from rich.text import Text

from tools.common.paths import project_root, resolve_relative
from tools.email_processor.attachment_cache import (
    load_cache,
    save_cache,
    update_cache,
)
from tools.email_processor.contacts import (
    build_addressbook_index,
    save_index_cache,
    upsert_contacts_from_email,
)
from tools.email_processor.discovery import (
    PatternDiscovery,
    _generate_rule_id,
    _slugify,
)

if TYPE_CHECKING:
    from tools.email_processor.aggregator import Aggregator
    from tools.email_processor.filter import RuleEngine


# Lazy import per filtro/aggregatore (caricati solo se usati)
def _load_filter_engine() -> "RuleEngine | None":
    """Carica RuleEngine se filter_rules.yaml esiste.

    Returns:
        Istanza di :class:`RuleEngine` o ``None`` se il file non esiste
        o il caricamento fallisce.
    """
    try:
        from tools.email_processor.filter import RuleEngine  # noqa: PLC0415

        rules_path = Path(__file__).resolve().parent / "filter_rules.yaml"
        if not rules_path.exists():
            logger.info(
                "filter_rules.yaml not found, filter disabled. "
                "Use 'rules add' to create rules, then 'rules save'."
            )
            return None
        engine: RuleEngine = RuleEngine(rules_path)
        logger.info(
            f"Filtro email caricato: {len(engine._sorted_rules)} regole attive"  # noqa: SLF001
        )
        return engine
    except Exception as e:
        logger.warning(f"Impossibile caricare filtro email: {e}")
        return None


_console = Console()

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="email_processor",
    help="Importazione, elaborazione e catalogazione email in vault Obsidian.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Logging & Config
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configura loguru: WARNING di default, DEBUG con --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level: <8}</level> | {message}",
    )


def _load_config() -> dict:
    """Carica tools/config.yaml. Restituisce dict vuoto se non trovato."""
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}


def _get_email_dir() -> Path:
    """Ottiene il percorso delle email grezze.

    Priorità (dal più alto al più basso):
      1. Variabile d'ambiente EMAIL_DIR
      2. Sezione email_processor.email_dir in tools/config.yaml
      3. Fallback a stringa vuota → errore chiaro più avanti.
    """
    email_dir_str = os.getenv("EMAIL_DIR")
    if email_dir_str:
        return Path(email_dir_str)

    config = _load_config()
    email_dir_str = config.get("email_processor", {}).get("email_dir")
    if email_dir_str:
        return Path(email_dir_str)

    return Path("")


def _get_vault_root() -> Path:
    """Percorso root del vault email.

    Priorità (dal più alto al più basso):
      1. Variabile d'ambiente EMAIL_VAULT_ROOT
      2. Sezione email_processor.vault_root in tools/config.yaml,
         risolta rispetto a PROJECT_ROOT (radice del repo).
      3. Fallback a stringa vuota → errore chiaro più avanti.
    """
    vault_root_str = os.getenv("EMAIL_VAULT_ROOT")
    if vault_root_str:
        return Path(vault_root_str)

    config = _load_config()
    vault_root_str = config.get("email_processor", {}).get("vault_root")
    if vault_root_str:
        return resolve_relative(vault_root_str)

    return Path("")


# ---------------------------------------------------------------------------
# Helpers di parsing
# ---------------------------------------------------------------------------


def _decode_mime_header(value: str) -> str:
    """Decodifica un header MIME (es. Subject, From) in stringa Unicode.

    Gestisce =?UTF-8?B?...?= e altre codifiche RFC 2047.
    Normalizza spazi bianchi: newline e CRLF → spazio, multipli spazi → uno.

    Args:
        value: Valore grezzo dell'header.

    Returns:
        Stringa decodificata con spazi normalizzati.
    """
    if not value:
        return ""
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    result = " ".join(parts)
    # Normalizza whitespace: CRLF/LF/CR → spazio, multipli spazi → uno
    result = re.sub(r"[\r\n]+", " ", result)
    result = re.sub(r" {2,}", " ", result)
    return result.strip()


def _format_address(addr: tuple[str | None, str | None]) -> str:
    """Formatta una coppia (nome, email) in ``Nome <email>`` o solo email.

    La stringa risultante va sempre tra virgolette doppie nel frontmatter
    YAML, quindi virgole e caratteri speciali nel nome sono gestiti.

    Args:
        addr: Tupla (nome, email) da email.utils.getaddresses().

    Returns:
        Stringa formattata: ``Nome <email>`` se nome presente, altrimenti
        solo ``email``. Stringa vuota se email_addr è vuoto.
    """
    name, email_addr = addr
    if not email_addr:
        return ""
    email_addr = email_addr.strip()
    name = (name or "").strip()
    if name:
        return f"{name} <{email_addr}>"
    return email_addr


def _format_address_list(addrs: list[tuple[str | None, str | None]]) -> list[str]:
    """Formatta una lista di indirizzi in lista di stringhe YAML-safe.

    Filtra tuple vuote ``('', '')`` restituite da getaddresses().

    Args:
        addrs: Lista di tuple (nome, email).

    Returns:
        Lista di stringhe formattate, ordine preservato.
    """
    result: list[str] = []
    for addr in addrs:
        formatted = _format_address(addr)
        if formatted:
            result.append(formatted)
    return result


def _yaml_escape(value: str) -> str:
    """Escape una stringa per uso in YAML con doppi apici.

    - Backslash ``\\`` → ``\\\\``
    - Doppio apice ``"`` → ``\\"``
    - Newline ``\\n``, CR ``\\r`` → spazio

    Args:
        value: Stringa da quotare.

    Returns:
        Stringa con escaping applicato, pronta per ``"..."`` YAML.
    """
    # Sostituisci controllo caratteri non stampabili
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    # Rimuovi newline/CR dal valore (non possono stare in stringa YAML doppia)
    escaped = re.sub(r"[\r\n]+", " ", escaped)
    return escaped


def _slugify(s: str) -> str:
    """Converte una stringa in slug URL-safe.

    - lowercase
    - sostituisce caratteri non alfanumerici con ``-``
    - rimuove ``-`` iniziali/finali e doppi ``-``

    Args:
        s: Stringa da slugificare.

    Returns:
        Slug pulito.
    """
    slug = re.sub(r"[^\w\s-]", "", s.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def _truncate_slug(slug: str, max_len: int = 60) -> str:
    """Tronca slug a ``max_len`` caratteri, tagliando a word boundary.

    Trova l'ultimo ``-`` entro i primi ``max_len`` caratteri e taglia lì.
    Se non c'è ``-`` (o è a inizio stringa), restituisce i primi
    ``max_len`` caratteri senza word boundary.

    Args:
        slug: Slug da troncare.
        max_len: Lunghezza massima (default 60).

    Returns:
        Slug troncato.
    """
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    last_dash = truncated.rfind("-")
    if last_dash > 0:
        return truncated[:last_dash]
    return truncated


def _parse_date(date_str: str) -> tuple[str, str, str, str]:
    """Parsa una data email e restituisce (date_iso, year, month, day).

    Args:
        date_str: Header Date grezzo dall'email.

    Returns:
        Tupla (date_iso, year, month, day):
        - date_iso: ``YYYY-MM-DD`` o ``unknown`` se non parsabile.
        - year, month, day: per struttura directory. ``unknown`` se non parsabile.
          day è zero-padded ``%d`` (01–31).
    """
    if not date_str or not date_str.strip():
        logger.debug("Date header vuoto, uso unknown/unknown/unknown")
        return "unknown", "unknown", "unknown", "unknown"
    try:
        dt = dateutil_parser.parse(date_str)
        date_iso = dt.strftime("%Y-%m-%d")
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
        day = dt.strftime("%d")
        return date_iso, year, month, day
    except Exception:
        logger.debug(f"Data non parsabile: {date_str!r}, uso unknown/unknown/unknown")
        return "unknown", "unknown", "unknown", "unknown"


# ---------------------------------------------------------------------------
# Deduplica cache — message_id già presenti nel vault
# ---------------------------------------------------------------------------


def _build_message_id_cache(vault_root: Path) -> set[str]:
    """Costruisce un set di message_id già importati.

    Scansiona ricorsivamente ``Inbox/emails/**/*.md`` e cerca il frontmatter
    ``message_id:`` in ogni file. Per performance su vault grandi.

    Args:
        vault_root: Percorso root del vault email.

    Returns:
        Set di stringhe message_id (con ``<>``) già presenti nel vault.
    """
    cache: set[str] = set()
    emails_dir = vault_root / "Inbox" / "emails"
    if not emails_dir.exists():
        return cache

    # Cerca sia formato con virgolette che senza
    pattern = re.compile(r"^message_id:\s*\"?([^\"]+)\"?$", re.MULTILINE)
    for md_file in sorted(emails_dir.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            match = pattern.search(content)
            if match:
                mid = match.group(1).strip()
                if mid:
                    cache.add(mid)
        except OSError as e:
            logger.warning(f"Impossibile leggere {md_file} per cache: {e}")

    logger.debug(f"Cache deduplica: {len(cache)} message_id già presenti")
    return cache


# ---------------------------------------------------------------------------
# Parsing .eml
# ---------------------------------------------------------------------------


def _parse_eml(eml_path: Path) -> dict:
    """Parsa un file .eml e restituisce i dati strutturati.

    Include la chiave ``_raw_msg`` (l'oggetto ``email.message.Message``)
    per l'estrazione successiva degli allegati da parte del chiamante.

    Args:
        eml_path: Percorso del file .eml.

    Returns:
        Dizionario con:
        - message_id, date, year, month
        - from, to (list), cc (list)
        - subject, body, source, priority, status, labels
        - _raw_msg (oggetto Message, consumato dal chiamante)
    """
    with open(eml_path, "rb") as f:
        raw = f.read()
    msg: email.message.Message = email.message_from_bytes(raw)

    # --- Message-ID ---
    raw_message_id = _decode_mime_header(msg.get("Message-ID", ""))
    message_id = raw_message_id.strip()
    # Normalizza: assicura presenza di <>
    if message_id and not message_id.startswith("<"):
        message_id = f"<{message_id}>"

    # --- References ---
    references_raw = _decode_mime_header(msg.get("References", ""))
    references = [ref.strip() for ref in references_raw.split() if ref.strip()]

    # --- Subject ---
    subject = _decode_mime_header(msg.get("Subject", ""))

    # --- From / To / CC con email.utils.getaddresses() ---
    from_addrs = getaddresses([msg.get("From", "")])
    to_addrs = getaddresses([msg.get("To", "")])
    cc_addrs = getaddresses([msg.get("Cc", "")])

    from_str = _format_address(from_addrs[0]) if from_addrs else ""
    to_list = _format_address_list(to_addrs)
    cc_list = _format_address_list(cc_addrs)

    # --- Date ---
    raw_date = msg.get("Date", "")
    date_iso, year, month, day = _parse_date(raw_date)

    # --- Priority & Status (fissi all'import) ---
    priority = "normal"
    status = "new"
    labels: list[str] = []

    # --- Body (solo primo text/plain) ---
    body = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not body:
            charset = part.get_content_charset("utf-8")
            payload = part.get_payload(decode=True)
            if payload:
                body = payload.decode(charset or "utf-8", errors="replace")
            break  # solo primo text/plain

    # --- Raw address tuples per contact extraction ---
    # Normalizza None → "" per sicurezza
    _from_raw: tuple[str, str] = (
        (from_addrs[0][0] or "", from_addrs[0][1] or "") if from_addrs else ("", "")
    )
    _to_raw: list[tuple[str, str]] = [(name or "", email or "") for name, email in to_addrs]
    _cc_raw: list[tuple[str, str]] = [(name or "", email or "") for name, email in cc_addrs]

    return {
        "message_id": message_id,
        "references": references,
        "date": date_iso,
        "year": year,
        "month": month,
        "day": day,
        "from": from_str,
        "to": to_list,
        "cc": cc_list,
        "from_raw": _from_raw,
        "to_raw": _to_raw,
        "cc_raw": _cc_raw,
        "subject": subject,
        "body": body,
        "attachments": [],
        "source": eml_path.name,
        "priority": priority,
        "status": status,
        "labels": labels,
        "_raw_msg": msg,
    }


# ---------------------------------------------------------------------------
# Allegati
# ---------------------------------------------------------------------------


def _save_attachment(
    part: email.message.Message,
    attach_base: Path,
    year: str,
    month: str,
    index: int,
    cache: dict,
    message_id: str,
) -> dict | None:
    """Salva un allegato da una part MIME con naming content-addressable (SHA256).

    Usa i primi 16 caratteri dell'hex digest SHA256 del payload come nome
    file, con estensione preservata dall'originale. La cache evita di
    riscrivere file già noti.

    Args:
        part: Part MIME con Content-Disposition: attachment.
        attach_base: Directory base per allegati (``Inbox/attachments``).
        year: Anno (o ``unknown``).
        month: Mese (o ``unknown``).
        index: Indice progressivo per nome fallback.
        cache: Dizionario cache ``{sha256_full: entry}`` (modificato in-place).
        message_id: Message-ID dell'email contenitore.

    Returns:
        Dict con ``name``, ``path``, ``size``, ``hash`` o ``None`` se errore.
    """
    target_dir = attach_base / year / month
    target_dir.mkdir(parents=True, exist_ok=True)

    raw_name = part.get_filename()
    if raw_name:
        name = _decode_mime_header(raw_name)
    else:
        name = f"attachment-{index}.bin"

    # Pulisci il nome (niente path traversal, solo basename)
    name = Path(name).name

    payload = part.get_payload(decode=True)
    if payload is None:
        logger.warning(f"Allegato {name}: payload vuoto, skip")
        return None

    size = len(payload)

    # --- Calcola SHA256 del payload ---
    sha256_full = hashlib.sha256(payload).hexdigest()
    sha256_prefix = sha256_full[:16]

    # Estensione dal nome originale (o Content-Type fallback)
    ext = Path(name).suffix.lower()
    if not ext:
        # Fallback a estensione da Content-Type
        main = part.get_content_maintype()
        sub = part.get_content_subtype()
        ext = _mime_ext(main, sub) or ".bin"

    new_filename = f"{sha256_prefix}{ext}"

    # --- Verifica cache ---
    if sha256_full in cache:
        # File già noto: non salvare, solo aggiorna email_ids
        entry = cache[sha256_full]
        if message_id not in entry["email_ids"]:
            entry["email_ids"].append(message_id)
        relative_path = entry["path"]
        logger.debug(
            f"Cache hit: {sha256_prefix} → skip salvataggio "
            f"(già presente come {entry['original_name']})"
        )
    else:
        # Nuovo file: salva su disco
        target_path = target_dir / new_filename

        # --- Safety net: path troppo lungo (dovrebbe essere impossibile con 16 char) ---
        if len(str(target_path.resolve())) > 255:
            logger.warning(f"Path allegato troppo lungo con hash 16 char: {target_path}")
            return None

        try:
            target_path.write_bytes(payload)
            logger.debug(f"Allegato salvato: {target_path} ({size} byte)")
        except OSError as e:
            logger.error(f"Errore salvataggio allegato {target_path}: {e}")
            return None

        relative_path = f"Inbox/attachments/{year}/{month}/{new_filename}"

        # --- Aggiorna cache ---
        update_cache(cache, sha256_full, name, relative_path, size, message_id)

    return {
        "name": name,
        "path": relative_path,
        "size": size,
        "hash": sha256_full,
    }


def _mime_ext(main: str, sub: str) -> str | None:
    """Mappa Content-Type a estensione file comune.

    Usata come fallback quando un allegato non ha filename.

    Args:
        main: Content-Type main type (es. ``application``).
        sub: Content-Type sub type (es. ``pdf``).

    Returns:
        Estensione con punto (es. ``.pdf``) o ``None``.
    """
    mime_map: dict[str, str] = {
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/gzip": ".gz",
        "application/x-tar": ".tar",
        "application/x-rar-compressed": ".rar",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "text/plain": ".txt",
        "text/csv": ".csv",
        "text/html": ".html",
        "text/xml": ".xml",
        "application/json": ".json",
    }
    return mime_map.get(f"{main}/{sub}")


# ---------------------------------------------------------------------------
# Collision handling per filename note
# ---------------------------------------------------------------------------


def _resolve_note_path(
    emails_dir: Path,
    subject_slug: str,
    subject: str,
) -> Path:
    """Risolve il path per una nota email gestendo collisioni.

    Strategia (v2 — niente prefisso data):
    1. Prova ``{slug}.md``
    2. Se esiste → hash MD5(subject)[:6] → ``{slug}-{hash}.md``
    3. Se ancora collisione → contatore → ``{slug}-{hash}-{n}.md``

    Args:
        emails_dir: Directory ``Inbox/emails/{year}/{month}/{day}/``.
        subject_slug: Slug del subject troncato a 60.
        subject: Subject originale (per hash).

    Returns:
        Path completo del file nota (garantito non esistente).
    """
    # 1. Tenta nome base: solo slug, niente prefisso data
    filepath = emails_dir / f"{subject_slug}.md"
    if not filepath.exists():
        return filepath

    # 2. Collisione: aggiungi hash MD5 a 6 char
    hash_part = hashlib.md5(subject.encode("utf-8")).hexdigest()[:6]
    filepath = emails_dir / f"{subject_slug}-{hash_part}.md"
    if not filepath.exists():
        return filepath

    # 3. Ancora collisione: contatore progressivo
    counter = 1
    while True:
        filepath = emails_dir / f"{subject_slug}-{hash_part}-{counter}.md"
        if not filepath.exists():
            return filepath
        counter += 1


# ---------------------------------------------------------------------------
# Thread — helper functions
# ---------------------------------------------------------------------------


def _scan_all_notes(vault_root: Path) -> list[dict]:
    """Scansiona ``Inbox/emails/**/*.md`` e restituisce metadati delle note.

    Estrae da ogni file frontmatter: ``message_id``, ``references``,
    ``subject``, ``from``, ``date``.

    Args:
        vault_root: Percorso root del vault email.

    Returns:
        Lista di dict con chiavi:
        ``path``, ``message_id``, ``references``, ``subject``, ``from``, ``date``.
        Lista vuota se vault inesistente o nessuna nota trovata.
    """
    notes: list[dict] = []
    emails_dir = vault_root / "Inbox" / "emails"
    if not emails_dir.exists():
        logger.info(f"Directory email non trovata: {emails_dir}")
        return notes

    for md_file in sorted(emails_dir.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"Impossibile leggere {md_file}: {e}")
            continue

        # Estrai frontmatter tra i delimitatori ---
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            logger.debug(f"Frontmatter non trovato in {md_file}")
            continue

        try:
            fm_data = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError as e:
            logger.warning(f"Frontmatter YAML non valido in {md_file}: {e}")
            continue

        if not isinstance(fm_data, dict):
            continue

        message_id = fm_data.get("message_id", "")
        if not message_id:
            continue

        refs_raw = fm_data.get("references", []) or []
        if not isinstance(refs_raw, list):
            refs_raw = []

        notes.append(
            {
                "path": md_file,
                "message_id": str(message_id),
                "references": [str(r) for r in refs_raw],
                "subject": str(fm_data.get("subject", "")),
                "from": str(fm_data.get("from", "")),
                "date": str(fm_data.get("date", "")),
            }
        )

    logger.debug(f"Scansione note: {len(notes)} note trovate")
    return notes


def _build_thread_graph(
    notes: list[dict],
) -> tuple[dict[str, str | None], dict[str, list[str]], dict[str, str | None]]:
    """Costruisce i mapping parent/children/root da una lista di note.

    **Algoritmo**:
    - References vuoto → thread root
    - References con N elementi → parent = references[-1], root = references[0]

    Args:
        notes: Lista di dict con ``message_id`` e ``references``.

    Returns:
        Tupla (parent_of, children_of, root_of):
        - parent_of[msg_id] = references[-1] o None
        - children_of[msg_id] = lista di message_id figli diretti
        - root_of[msg_id] = references[0] o None (se root)
    """
    parent_of: dict[str, str | None] = {}
    children_of: dict[str, list[str]] = {}
    root_of: dict[str, str | None] = {}

    for note in notes:
        msg_id = note["message_id"]
        refs = note["references"]

        if not refs:
            # Thread root
            parent_of[msg_id] = None
            root_of[msg_id] = None
        else:
            parent = refs[-1]
            parent_of[msg_id] = parent
            root_of[msg_id] = refs[0]

        # Inizializza lista figli (sarà popolata dal lato parent)
        children_of.setdefault(msg_id, [])

    # Popola children_of: per ogni nota con parent, aggiungi come figlio
    for msg_id, parent_id in parent_of.items():
        if parent_id:
            if parent_id not in children_of:
                children_of[parent_id] = []
            children_of[parent_id].append(msg_id)

    logger.debug(
        f"Thread graph: {len(parent_of)} nodi, {sum(1 for p in parent_of.values() if p)} con parent"
    )
    return parent_of, children_of, root_of


def _update_note_frontmatter(
    note_path: Path,
    parent: str | None,
    children: list[str],
    root: str | None,
) -> bool:
    """Aggiorna frontmatter YAML con campi thread.

    Preserva tutti gli altri campi del frontmatter. Aggiunge o aggiorna:
    ``thread_parent``, ``thread_children``, ``thread_root``.

    Args:
        note_path: Percorso del file ``.md``.
        parent: Message-ID del parent (o None).
        children: Lista di message-id dei figli diretti.
        root: Message-ID del thread root (o None).

    Returns:
        True se il file è stato modificato, False altrimenti.
    """
    try:
        content = note_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning(f"Impossibile leggere {note_path}: {e}")
        return False

    # Estrai frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        logger.debug(f"Frontmatter non trovato in {note_path}, skip")
        return False

    fm_text = fm_match.group(1)
    body = content[fm_match.end() :]

    try:
        fm_data = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        logger.warning(f"YAML non valido in {note_path}: {e}")
        return False

    if not isinstance(fm_data, dict):
        return False

    # Aggiorna campi thread
    fm_data["thread_parent"] = parent or ""
    fm_data["thread_children"] = children
    fm_data["thread_root"] = root or ""

    # Ricostruisci frontmatter
    new_fm = yaml.dump(
        fm_data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).strip()

    new_content = f"---\n{new_fm}\n---{body}"

    try:
        note_path.write_text(new_content, encoding="utf-8")
        logger.debug(f"Aggiornato frontmatter thread: {note_path.name}")
        return True
    except OSError as e:
        logger.error(f"Errore scrittura {note_path}: {e}")
        return False


def _write_thread_index(
    root_id: str,
    all_notes_map: dict[str, dict],
    children_of: dict[str, list[str]],
    vault_root: Path,
) -> Path | None:
    """Scrive un file indice per un thread in ``Review/threads/<slug>.md``.

    Args:
        root_id: Message-ID del thread root.
        all_notes_map: Mapping ``{message_id: note_dict}`` con metadati.
        children_of: Mapping ``{message_id: [child_ids]}``.
        vault_root: Percorso root del vault email.

    Returns:
        Path del file indice creato, o None se errore.
    """
    # --- Raccogli tutti i messaggi del thread in ordine cronologico ---
    root_info = all_notes_map.get(root_id)
    if not root_info:
        logger.warning(f"Root non trovata nel grafo: {root_id}")
        return None

    # Traversa BFS/DFS per raccogliere tutti i messaggi del thread
    thread_messages: list[dict] = []
    visited: set[str] = set()

    def _collect(mid: str) -> None:
        if mid in visited:
            return
        visited.add(mid)
        info = all_notes_map.get(mid)
        if info:
            thread_messages.append(info)
        for child_id in children_of.get(mid, []):
            _collect(child_id)

    _collect(root_id)

    # Ordina per data
    thread_messages.sort(key=lambda m: m.get("date", ""))

    if not thread_messages:
        return None

    # --- Costruisci indice ---
    subject = root_info.get("subject", "(senza oggetto)")
    participants: set[str] = set()
    for m in thread_messages:
        sender = m.get("from", "")
        if sender:
            participants.add(sender)

    last_date = thread_messages[-1].get("date", "sconosciuta")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017
    is_open = "aperta" if last_date >= today_str else "chiusa"

    lines: list[str] = []
    lines.append(f"# Thread: {subject}")
    lines.append("")
    lines.append("Cronologia:")
    for i, m in enumerate(thread_messages, start=1):
        d = m.get("date", "?")
        f = m.get("from", "?")
        s = m.get("subject", "")
        label = "prima email" if i == 1 else "risposta" if i == 2 else "risposta alla risposta"
        lines.append(f"{i}. {d} — {s} (da {f}) ← {label}")

    lines.append("")
    lines.append(f"Totale: {len(thread_messages)} email, {len(participants)} partecipanti")
    stato_label = "aperto" if is_open == "aperta" else "chiuso"
    lines.append(f"Stato: {stato_label} (ultima risposta {last_date})")
    lines.append("")

    content = "\n".join(lines) + "\n"

    # --- Scrivi file ---
    slug = root_info.get("subject", root_id)
    file_slug = _slugify(slug)
    file_slug = _truncate_slug(file_slug, 60)
    if not file_slug:
        file_slug = hashlib.md5(root_id.encode()).hexdigest()[:12]

    threads_dir = vault_root / "Review" / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)

    index_path = threads_dir / f"{file_slug}.md"

    # Collision handling: se il file esiste già, aggiungi hash del root_id
    if index_path.exists():
        id_hash = hashlib.md5(root_id.encode()).hexdigest()[:6]
        index_path = threads_dir / f"{file_slug}-{id_hash}.md"

    try:
        index_path.write_text(content, encoding="utf-8")
        logger.info(f"Indice thread scritto: {index_path}")
        return index_path
    except OSError as e:
        logger.error(f"Errore scrittura indice thread {index_path}: {e}")
        return None


def _rebuild_contacts_from_notes(vault_root: Path) -> dict[str, int]:
    """Ricostruisce Addressbook scansionando tutte le note email.

    Scansiona ``Inbox/emails/**/*.md``, estrae from/to/cc dal frontmatter,
    e upserta i contatti in Addressbook/.

    Args:
        vault_root: Percorso root del vault email.

    Returns:
        Dizionario statistiche: ``{"created": N, "updated": N, "skipped": N}``.
    """
    from tools.email_processor.contacts import (
        build_addressbook_index,
        upsert_contacts_from_email,
        save_index_cache,
    )

    addressbook_dir = vault_root / "Addressbook"
    index = build_addressbook_index(addressbook_dir)
    logger.info(f"Indice contatti caricato: {len(index)} contatti noti")

    emails_dir = vault_root / "Inbox" / "emails"
    if not emails_dir.exists():
        logger.info(f"Nessuna nota email trovata in {emails_dir}")
        return {"created": 0, "updated": 0, "skipped": 0}

    total_created = 0
    total_updated = 0
    total_skipped = 0

    for md_file in sorted(emails_dir.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"Impossibile leggere {md_file}: {e}")
            continue

        # Estrai frontmatter
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue

        try:
            fm_data = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            continue

        if not isinstance(fm_data, dict):
            continue

        # Estrai from/to/cc dal frontmatter
        # from è una stringa "Nome <email>", to/cc sono liste
        from_str = str(fm_data.get("from", ""))
        to_list: list[str] = fm_data.get("to", []) or []
        cc_list: list[str] = fm_data.get("cc", []) or []
        date = str(fm_data.get("date", ""))

        if not isinstance(to_list, list):
            to_list = [to_list] if to_list else []
        if not isinstance(cc_list, list):
            cc_list = [cc_list] if cc_list else []

        # Ricava tuple (name, email) dal formato "Nome <email>"
        def _parse_addr(addr_str: str) -> tuple[str, str]:
            """Parsa "Nome <email>" in (name, email)."""
            match = re.match(r'^"?([^"]*)"?\s*<([^>]+)>', addr_str)
            if match:
                return match.group(1).strip(), match.group(2).strip()
            # Solo email, senza <>
            addr_clean = addr_str.strip().strip('"')
            if "@" in addr_clean:
                return "", addr_clean
            return "", ""

        # from
        from_raw = _parse_addr(from_str)
        # to
        to_raw = [_parse_addr(a) for a in to_list if a]
        # cc
        cc_raw = [_parse_addr(a) for a in cc_list if a]

        if from_raw[1] or to_raw or cc_raw:
            stats = upsert_contacts_from_email(
                addressbook_dir=addressbook_dir,
                from_raw=from_raw,
                to_raw=to_raw,
                cc_raw=cc_raw,
                date=date,
                index=index,
            )
            total_created += stats["created"]
            total_updated += stats["updated"]
            total_skipped += stats["skipped"]

    # Salva cache
    save_index_cache(addressbook_dir, index)

    logger.info(
        f"Rebuild contatti completato: {total_created} creati, "
        f"{total_updated} aggiornati, {total_skipped} saltati"
    )
    return {"created": total_created, "updated": total_updated, "skipped": total_skipped}


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


def _run_import(
    vault_root: Path,
    email_dir: Path,
    limit: int | None = None,
) -> None:
    """Esegue la logica di importazione email (core, senza CLI Typer).

    Integra il filtro intelligente (Layer 2) se ``filter_rules.yaml`` esiste.
    Le email classificate come discard/aggregate non vengono importate
    singolarmente; quelle aggregate finiscono in ``_review/daily/``.

    Args:
        vault_root: Percorso root del vault email.
        email_dir: Directory contenente i file .eml.
        limit: Numero massimo di email da importare (None = tutte).
    """
    logger.info(f"Directory sorgente: {email_dir}")
    logger.info(f"Vault destinazione: {vault_root}")

    # --- NUOVO: carica filtro email (se filter_rules.yaml esiste) ---
    filter_engine_result = _load_filter_engine()
    filter_engine: RuleEngine | None = None
    aggregator: Aggregator | None = None
    if filter_engine_result is not None:
        filter_engine = filter_engine_result
        try:
            from tools.email_processor.aggregator import Aggregator

            aggregator = Aggregator(vault_root)
        except Exception as e:
            logger.warning(f"Impossibile inizializzare aggregator: {e}")
            aggregator = None

    # --- Scansiona file .eml ---
    eml_files: list[Path] = []
    for p in sorted(email_dir.rglob("*.eml")):
        try:
            p.stat()  # verifica accessibilità
            eml_files.append(p)
        except OSError:
            logger.warning(f"Saltando file inaccessibile {p}")
            continue

    if not eml_files:
        logger.warning("Nessun file .eml accessibile trovato")
        return

    # Ordina per mtime decrescente (più recenti prima)
    eml_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if limit:
        eml_files = eml_files[:limit]
        logger.info(f"Limit: importazione di massimo {limit} email")

    # --- Cache deduplica (message_id per email) ---
    logger.info("Costruzione cache deduplica...")
    existing_ids = _build_message_id_cache(vault_root)
    logger.info(f"Cache deduplica: {len(existing_ids)} message_id già noti")

    # --- Cache content-addressable allegati ---
    attach_cache = load_cache()
    logger.info(f"Cache allegati: {len(attach_cache)} entry caricate")

    # --- Costruisci indice contatti Addressbook ---
    addressbook_dir = vault_root / "Addressbook"
    logger.info("Costruzione indice contatti Addressbook...")
    addressbook_index = build_addressbook_index(addressbook_dir)
    logger.info(f"Indice contatti: {len(addressbook_index)} contatti noti")

    # --- Statistiche ---
    imported_count = 0
    skipped_count = 0
    error_count = 0
    total_created = 0
    total_updated = 0
    total = len(eml_files)

    # NUOVO: statistiche filtro
    filter_stats: dict[str, int] = {
        "discard": 0,
        "aggregate": 0,
        "keep": 0,
        "fallback": 0,
    }

    for idx, eml_path in enumerate(eml_files, start=1):
        logger.debug(f"[{idx}/{total}] Parsing {eml_path.name}")

        try:
            data = _parse_eml(eml_path)
        except Exception as e:
            logger.error(f"Errore nel parsing di {eml_path.name}: {e}")
            error_count += 1
            continue

        # --- NUOVO: classifica email con filtro ---
        if filter_engine is not None:
            try:
                result = filter_engine.classify(data)
                filter_stats[result.action] = filter_stats.get(result.action, 0) + 1

                if result.action == "discard":
                    logger.info(f"[{idx}/{total}] DISCARD {eml_path.name} ({result.rule_id})")
                    skipped_count += 1
                    continue

                if result.action == "aggregate":
                    logger.info(f"[{idx}/{total}] AGGREGATE {eml_path.name} ({result.rule_id})")
                    if aggregator is not None and result.aggregate_to:
                        aggregator.add_entry(result.aggregate_to, data, eml_path)
                    skipped_count += 1
                    continue

                # keep o fallback: import normale con flag opzionale
                if result.flag:
                    data["flag"] = result.flag
                if result.label:
                    data.setdefault("labels", []).append(result.label)

            except Exception as e:
                logger.warning(f"Errore nel filtro per {eml_path.name}: {e}")
                # Fallback safe: importa normalmente

        # --- Estrazione contatti (anche per email duplicate) ---
        if data.get("from_raw") or data.get("to_raw"):
            contact_stats = upsert_contacts_from_email(
                addressbook_dir=addressbook_dir,
                from_raw=data["from_raw"],
                to_raw=data["to_raw"],
                cc_raw=data["cc_raw"],
                date=data["date"],
                index=addressbook_index,
            )
            total_created += contact_stats["created"]
            total_updated += contact_stats["updated"]

        # --- Deduplica via message_id ---
        if data["message_id"] and data["message_id"] in existing_ids:
            logger.info(
                f"[{idx}/{total}] Skipping {eml_path.name}: "
                f"already imported (message_id: {data['message_id']})"
            )
            skipped_count += 1
            continue

        # --- Slug del subject ---
        slug = _slugify(data["subject"])
        slug = _truncate_slug(slug, 60)

        year = data["year"]
        month = data["month"]
        day = data["day"]

        # --- Directory per la nota: Inbox/emails/{year}/{month}/{day}/ ---
        emails_dir = vault_root / "Inbox" / "emails" / year / month / day
        emails_dir.mkdir(parents=True, exist_ok=True)

        # --- Estrazione allegati ---
        raw_msg = data.pop("_raw_msg", None)
        attachments: list[dict] = []
        if raw_msg:
            attach_base = vault_root / "Inbox" / "attachments"
            for part in raw_msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                disp = part.get("Content-Disposition", "")
                if not disp or "attachment" not in disp.lower():
                    continue
                attach_info = _save_attachment(
                    part,
                    attach_base,
                    year,
                    month,
                    len(attachments) + 1,
                    attach_cache,
                    data["message_id"],
                )
                if attach_info:
                    attachments.append(attach_info)

        data["attachments"] = attachments

        # --- Risolvi path nota (con gestione collisioni) ---
        note_path = _resolve_note_path(emails_dir, slug, data["subject"])

        # --- Genera frontmatter YAML ---
        # Costruzione manuale per preservare ordine e struttura esatta del design
        fm_lines: list[str] = []
        fm_lines.append("---")
        fm_lines.append(f'message_id: "{_yaml_escape(data["message_id"])}"')
        fm_lines.append("references:")
        if data["references"]:
            for ref in data["references"]:
                fm_lines.append(f'  - "{_yaml_escape(ref)}"')
        else:
            fm_lines.append("  []")
        fm_lines.append(f"date: {data['date']}")
        fm_lines.append(f'from: "{_yaml_escape(data["from"])}"')

        # To - lista YAML
        fm_lines.append("to:")
        if data["to"]:
            for addr in data["to"]:
                fm_lines.append(f'  - "{_yaml_escape(addr)}"')
        else:
            fm_lines.append("  []")

        # CC
        fm_lines.append("cc:")
        if data["cc"]:
            for addr in data["cc"]:
                fm_lines.append(f'  - "{_yaml_escape(addr)}"')
        else:
            fm_lines.append("  []")

        fm_lines.append(f'subject: "{_yaml_escape(data["subject"])}"')
        fm_lines.append(f"priority: {data['priority']}")
        fm_lines.append(f"status: {data['status']}")

        # NUOVO: aggiungi flag/label dal filtro
        flag = data.get("flag")
        if flag:
            fm_lines.append(f"flag: {flag}")

        labels = data.get("labels", [])
        if labels:
            fm_lines.append("labels:")
            for lb in labels:
                fm_lines.append(f'  - "{lb}"')
        else:
            fm_lines.append("labels: []")

        # Attachments
        if data["attachments"]:
            fm_lines.append("attachments:")
            for att in data["attachments"]:
                fm_lines.append(f'  - name: "{_yaml_escape(att["name"])}"')
                fm_lines.append(f'    path: "{_yaml_escape(att["path"])}"')
                fm_lines.append(f"    size: {att['size']}")
                fm_lines.append(f'    hash: "{att["hash"]}"')
        else:
            fm_lines.append("attachments: []")

        fm_lines.append(f'source: "{_yaml_escape(data["source"])}"')
        fm_lines.append("---")
        fm_lines.append(f"# {data['subject']}")
        fm_lines.append("")

        # Body — solo text/plain raw
        if data["body"]:
            fm_lines.append(data["body"])
            fm_lines.append("")

        content = "\n".join(fm_lines)

        try:
            note_path.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Errore scrittura nota {note_path}: {e}")
            error_count += 1
            continue

        # Aggiungi alla cache per evitare duplicati nello stesso run
        if data["message_id"]:
            existing_ids.add(data["message_id"])

        imported_count += 1
        logger.info(f"[{idx}/{total}] ✅ {note_path.relative_to(vault_root)}")

    # --- NUOVO: flush aggregati ---
    if aggregator is not None:
        try:
            agg_count = aggregator.flush()
            if agg_count > 0:
                logger.info(f"File aggregati scritti: {agg_count}")
        except Exception as e:
            logger.error(f"Errore flush aggregator: {e}")

    # --- Salva indice contatti (cache) ---
    save_index_cache(addressbook_dir, addressbook_index)

    # --- Salva cache allegati ---
    save_cache(attach_cache)
    logger.info(f"Cache allegati salvata: {len(attach_cache)} entry")

    # --- Report finale ---
    logger.info("=" * 50)
    logger.info("  IMPORT COMPLETATO")
    logger.info(f"    Importate:        {imported_count}")
    logger.info(f"    Saltate (dup):     {skipped_count}")
    logger.info(f"    Contatti creati:   {total_created}")
    logger.info(f"    Contatti agg.:     {total_updated}")
    logger.info(f"    Errori:            {error_count}")
    logger.info(f"    Totale:            {imported_count + skipped_count + error_count}")

    # NUOVO: statistiche filtro
    if filter_engine is not None:
        filtered_total = sum(filter_stats.values())
        logger.info("---")
        logger.info("  STATISTICHE FILTRO:")
        for action in ("discard", "aggregate", "keep", "fallback"):
            count = filter_stats.get(action, 0)
            pct = (count / filtered_total * 100) if filtered_total > 0 else 0
            logger.info(f"    {action:<12} {count:>5} ({pct:>5.1f}%)")
        if filtered_total > 0:
            logger.info(
                f"    Riduzione:        {filter_stats.get('discard', 0) + filter_stats.get('aggregate', 0)} email non importate singolarmente"
            )

    logger.info("=" * 50)

    if error_count > 0:
        logger.warning(f"Si sono verificati {error_count} errori durante l'importazione.")


@app.command("import")
def import_cmd(
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="Numero massimo di email da importare (default: tutte, più recenti prima).",
    ),
    email_dir: Path = typer.Option(
        None,
        "--email-dir",
        help="Percorso delle email grezze .eml. Default da EMAIL_DIR env var.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Importa email .eml e genera note Markdown nel vault email.

    Parsa file .eml, estrae header e body text/plain, salva allegati,
    e produce note Markdown con frontmatter strutturato in
    ``Inbox/emails/YYYY/MM/DD/``.

    La deduplica avviene via Message-ID: se un messaggio con lo stesso ID
    è già presente nel vault, viene saltato.
    """
    _setup_logging(verbose)

    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        logger.error(
            f"Vault email non trovato: {vault_root}. "
            "Imposta EMAIL_VAULT_ROOT o configuralo in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    if email_dir is None:
        email_dir = _get_email_dir()

    if not email_dir or not email_dir.exists():
        logger.error(
            f"Directory email {email_dir} non esiste. "
            "Imposta EMAIL_DIR o configurala in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    _run_import(vault_root=vault_root, email_dir=email_dir, limit=limit)


@app.command()
def process(
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="Numero massimo di email da elaborare (default: tutte).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Elabora email con analisi AI (sintesi, azioni, etc.). [STUB]"""
    _setup_logging(verbose)

    logger.info("Elaborazione AI non ancora implementata (stub)")
    typer.echo("Stub: elaborazione di email, limite {}".format(limit))


@app.command()
def status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Mostra lo stato del vault email.

    Scansiona il vault e mostra statistiche: note totali per stato,
    thread ricostruiti, contatti in Addressbook, intervallo date.
    """
    _setup_logging(verbose)

    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        logger.error(
            f"Vault email non trovato: {vault_root}. "
            "Imposta EMAIL_VAULT_ROOT o configuralo in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    logger.info(f"Scansione vault: {vault_root}")

    # --- Scansiona note ---
    emails_dir = vault_root / "Inbox" / "emails"
    total_notes = 0
    status_counts: dict[str, int] = {"new": 0, "processed": 0, "flagged": 0}
    dates: list[str] = []

    if emails_dir.exists():
        pattern_status = re.compile(r"^status:\s*(\w+)", re.MULTILINE)
        pattern_date = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)

        for md_file in emails_dir.rglob("*.md"):
            total_notes += 1
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # Status
            st_match = pattern_status.search(content)
            if st_match:
                st_val = st_match.group(1).strip()
                if st_val in status_counts:
                    status_counts[st_val] += 1
                else:
                    status_counts[st_val] = status_counts.get(st_val, 0) + 1

            # Date
            dt_match = pattern_date.search(content)
            if dt_match:
                dates.append(dt_match.group(1))

    # --- Conteggio thread ---
    threads_dir = vault_root / "Review" / "threads"
    thread_count = 0
    if threads_dir.exists():
        thread_count = len(list(threads_dir.glob("*.md")))

    # --- Conteggio contatti ---
    addressbook_dir = vault_root / "Addressbook"
    contact_count = 0
    if addressbook_dir.exists():
        contact_count = len([f for f in addressbook_dir.glob("*.md") if f.name != "_index.md"])

    # --- Intervallo date ---
    min_date = min(dates) if dates else "—"
    max_date = max(dates) if dates else "—"

    # --- Output ---
    vault_display = str(vault_root)
    typer.echo(f"📊 Status vault email: {vault_display}")
    typer.echo("")
    typer.echo(f"Note totali:    {total_notes:,}")
    for st in ("new", "processed", "flagged"):
        typer.echo(f"  - {st:<12} {status_counts.get(st, 0):,}")
    other = total_notes - sum(status_counts.values())
    if other:
        typer.echo(f"  - altro         {other:,}")
    typer.echo("")
    typer.echo(f"Thread:         {thread_count:,} thread ricostruiti")
    typer.echo(f"Contatti:       {contact_count:,} in Addressbook")
    typer.echo("")
    typer.echo(f"Intervallo:     {min_date} → {max_date}")


# ---------------------------------------------------------------------------
# Discover (Layer 1 — Pattern Discovery)
# ---------------------------------------------------------------------------


@app.command()
def discover(
    days: int = typer.Option(
        None,
        "--days",
        "-d",
        help="Scan last N days only (default: entire vault).",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Save YAML to file (stdout if not set).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Scan email vault and discover classification patterns.

    Analyzes imported email notes, groups them by normalized subject,
    and produces structured YAML output with sample subjects, counts,
    and sender info -- ready for Poros to parse and apply rules.

    Output is always YAML. Use -o to write to file, otherwise stdout.
    """
    _setup_logging(verbose)

    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        logger.error(
            f"Vault root not found: {vault_root}. "
            "Set EMAIL_VAULT_ROOT or configure in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    logger.info(f"Vault root: {vault_root}")

    # --- Scan ---
    discovery_engine = PatternDiscovery(vault_root)
    patterns = discovery_engine.scan(days=days)

    if not patterns:
        typer.echo("No patterns found.")
        raise typer.Exit(code=0)

    # --- Calculate period ---
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    period_start: str
    if days:
        period_start = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")
    else:
        # Infer from earliest pattern date
        all_dates: list[str] = []
        for p in patterns:
            all_dates.extend(p.date_range)
        valid_dates = [d for d in all_dates if d != "unknown"]
        period_start = min(valid_dates) if valid_dates else "unknown"

    total_emails = sum(p.count for p in patterns)

    # --- Terminal table (summary) ---
    typer.echo("")
    typer.echo(f"  EMAIL DISCOVERY -- Period: {period_start} -> {today_str}")
    typer.echo(f"  Total files: {total_emails} | Unique patterns: {len(patterns)}")
    typer.echo("")

    table = Table(title="Discovered Patterns")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Normalized pattern", style="white", width=60)
    table.add_column("Count", style="yellow", justify="right")
    table.add_column("Domain", style="green")

    for p in patterns[:50]:
        pattern_disp = p.normalized[:65]
        if len(p.normalized) > 65:
            pattern_disp += "..."
        table.add_row(
            str(p.id),
            pattern_disp,
            str(p.count),
            p.sender_domain,
        )

    _console.print(table)

    if len(patterns) > 50:
        typer.echo(f"  ... and {len(patterns) - 50} more patterns")
    typer.echo("")

    # --- YAML output ---
    yaml_content = PatternDiscovery.patterns_to_yaml(patterns, period_start, today_str)

    if output:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(yaml_content, encoding="utf-8")
            typer.echo(f"Patterns saved to: {output}")
        except OSError as e:
            logger.error(f"Failed to write {output}: {e}")
            raise typer.Exit(code=1)
    else:
        typer.echo(yaml_content)


# ---------------------------------------------------------------------------
# Rules management (Layer 2 — classification rules)
# ---------------------------------------------------------------------------

rules_app = typer.Typer(
    name="rules",
    help="Manage classification rules (add, remove, list, show, apply, save, trust).",
    no_args_is_help=True,
)
app.add_typer(rules_app, name="rules", help="Manage classification rules.")


def _get_rules_path() -> Path:
    """Return the path to ``filter_rules.yaml`` adjacent to this file."""
    return Path(__file__).resolve().parent / "filter_rules.yaml"


def _load_rules_from_disk(path: Path | None = None) -> list[dict]:
    """Load rules from the YAML file on disk.

    Args:
        path: Path to the rules YAML file. Defaults to ``filter_rules.yaml``.

    Returns:
        List of rule dicts, ordered by priority descending.
        Empty list if file does not exist or is invalid.
    """
    path = path or _get_rules_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = data.get("rules", [])
        if not isinstance(rules, list):
            return []
        # Sort by priority descending
        rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        return rules
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Failed to load rules from {path}: {e}")
        return []


def _save_rules_to_disk(
    rules: list[dict],
    path: Path | None = None,
) -> None:
    """Save a list of rule dicts to the YAML file on disk.

    Produces a clean, sorted file with version header.

    Args:
        rules: List of rule dicts.
        path: Output path. Defaults to ``filter_rules.yaml``.
    """
    path = path or _get_rules_path()
    # Sort by priority descending for consistent output
    rules_sorted = sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)
    data = {
        "version": 1,
        "rules": rules_sorted,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )
        logger.info(f"Rules saved to {path} ({len(rules_sorted)} rules)")
    except OSError as e:
        logger.error(f"Failed to write {path}: {e}")
        raise typer.Exit(code=1)


def _display_rules_table(rules: list[dict]) -> None:
    """Print a table of rules to the terminal.

    Args:
        rules: List of rule dicts to display.
    """
    if not rules:
        typer.echo("No rules defined.")
        return

    table = Table(title=f"Classification rules ({len(rules)})", expand=True)
    table.add_column("Rule ID", style="cyan", no_wrap=True)
    table.add_column("Action", style="yellow", no_wrap=True)
    table.add_column("Match", style="white", ratio=2)
    table.add_column("Priority", style="green", justify="right", no_wrap=True)

    for rule in rules:
        rule_id = rule.get("id", "?")
        action = rule.get("action", "?")
        match = rule.get("match", {})
        priority = rule.get("priority", 50)

        # Summarise match conditions
        match_parts: list[str] = []
        for field, conditions in match.items():
            if isinstance(conditions, dict):
                for op, vals in conditions.items():
                    if isinstance(vals, list):
                        for v in vals:
                            match_parts.append(f"{field}: {v}")
                    else:
                        match_parts.append(f"{field}: {vals}")
            else:
                match_parts.append(f"{field}: {conditions}")

        match_summary = "\n".join(match_parts[:4])
        if not match_summary:
            match_summary = "(no conditions)"

        table.add_row(rule_id, action, match_summary, str(priority))

    _console.print(table)


# ---------------------------------------------------------------------------
# Rules trust (trusted senders management)
# ---------------------------------------------------------------------------

# Sender local parts / names esclusi (non umani)
_HUMAN_EXCLUDE_NAMES: set[str] = {
    "noreply",
    "no-reply",
    "no_reply",
    "automation",
    "system",
    "zabbixsrv",
    "backup",
    "postmaster",
    "mailer-daemon",
    "mailerdaemon",
    "administrator",
}

# Domini esclusi (automazione / sistema)
_HUMAN_EXCLUDE_DOMAINS: set[str] = {
    "alero.eu",
    "sharepointonline.com",
    "rubrik.com",
    "oracle.com",
    "emerson.com",
}


def _parse_sender(sender_str: str) -> tuple[str, str]:
    """Parsa una stringa mittente in ``(nome, email)``.

    Supporta sia ``Nome <email>`` che ``email`` nuda.

    Args:
        sender_str: Stringa mittente (es. ``"Luca Bighignoli <luca@fisvi.com>"``).

    Returns:
        Tupla ``(nome, email)``. ``nome`` può essere stringa vuota.
        ``email`` è sempre il local-part@dominio.
    """
    sender_str = sender_str.strip()
    match = re.match(r'^"?([^"]*)"?\s*<([^>]+)>', sender_str)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        return name, email
    # Solo email
    if "@" in sender_str:
        return "", sender_str
    return sender_str, ""


def _is_human_sender(email: str, name: str = "") -> bool:
    """Verifica se un mittente è umano (non automation/system).

    Args:
        email: Indirizzo email completo.
        name: Nome visualizzato opzionale.

    Returns:
        ``True`` se il mittente è considerato umano.
    """
    if not email or "@" not in email:
        return False

    local_part = email.split("@")[0].lower().strip()
    domain = email.split("@")[1].lower().strip()

    # Escludi per local part / name
    for exclude in _HUMAN_EXCLUDE_NAMES:
        if exclude in local_part or exclude in name.lower():
            return False

    # Escludi per dominio
    if domain in _HUMAN_EXCLUDE_DOMAINS:
        return False

    # Escludi indirizzi interni a Emerson generici
    if domain == "emerson.com" and local_part in (
        "noreply",
        "no-reply",
        "automation",
        "system",
    ):
        return False

    return bool(local_part)


def _create_trusted_rule(
    email_or_pattern: str,
    display_name: str = "",
) -> dict:
    """Crea un dict regola trusted per un mittente.

    Usa la parte locale dell'email (o il pattern passato) come
    ``from: contains``. ID generato come ``trusted-{slug}``.

    Args:
        email_or_pattern: Indirizzo email completo o pattern di match.
        display_name: Nome visualizzato del mittente.

    Returns:
        Dict regola pronto per ``filter_rules.yaml``.
    """
    # Determina il pattern di match dalla parte locale dell'email
    if "@" in email_or_pattern:
        match_pattern = email_or_pattern.split("@")[0].strip()
    else:
        match_pattern = email_or_pattern.strip()

    # Pulisci lo slug dal pattern di match (sostituisci punti con trattini
    # prima di slugificare, così ``donato.siravo`` → ``trusted-donato-siravo``)
    slug_source = match_pattern.replace(".", "-")
    slug = _slugify(slug_source)
    rule_id = f"trusted-{slug}"

    rule: dict = {
        "id": rule_id,
        "action": "keep",
        "priority": 95,
        "label": "fis-work",
        "match": {
            "from": {
                "contains": [match_pattern],
            },
        },
    }

    if display_name:
        rule["name"] = f"Trusted sender: {display_name}"
    rule["reason"] = "Trusted colleague — all emails are work"

    return rule


def _load_patterns_from_yaml(path: Path) -> list[dict]:
    """Carica patterns da un file YAML prodotto da ``discover``.

    Args:
        path: Percorso del file YAML.

    Returns:
        Lista di dict pattern. Lista vuota se errore.
    """
    if not path.exists():
        logger.error(f"Patterns file not found: {path}")
        raise typer.Exit(code=1)

    try:
        yaml_text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(yaml_text)
    except (yaml.YAMLError, OSError) as e:
        logger.error(f"Failed to load patterns YAML: {e}")
        raise typer.Exit(code=1) from e

    if not isinstance(data, dict) or "patterns" not in data:
        logger.error("Input YAML has no 'patterns' key (not discover output?).")
        raise typer.Exit(code=1)

    return data["patterns"]


def _build_pattern_actions_from_rules(rules: list[dict], patterns: list[dict]) -> dict[int, str]:
    """Mappa pattern ID → azione ``keep``/``discard``/``aggregate``.

    Cerca nelle regole il campo ``reason`` contenente ``"pattern #N"``
    per associare ogni regola al pattern da cui è stata generata.

    Args:
        rules: Lista di regole da ``filter_rules.yaml``.
        patterns: Lista di pattern dal file YAML di discover.

    Returns:
        Dict ``{pattern_id: action}``. Solo per pattern con regole associate.
    """
    pattern_actions: dict[int, str] = {}

    for rule in rules:
        reason = rule.get("reason", "")
        if not reason:
            continue
        match = re.search(r"pattern #(\d+)", reason)
        if match:
            pid = int(match.group(1))
            pattern_actions[pid] = rule.get("action", "keep")
            continue

        # Fallback: se la regola ha name che matcha normalized di un pattern
        rule_name = (rule.get("name") or "").lower()
        for pat in patterns:
            normalized = (pat.get("normalized") or "").lower()
            pid = pat.get("id")
            if pid and normalized and rule_name and normalized.startswith(rule_name[:30]):
                pattern_actions.setdefault(pid, rule.get("action", "keep"))

    return pattern_actions


def _suggest_trusted(file: Path) -> None:
    """Suggerisce mittenti da trustare analizzando patterns YAML e regole esistenti.

    Args:
        file: Percorso del file YAML prodotto da ``discover``.
    """
    patterns = _load_patterns_from_yaml(file)
    rules = _load_rules_from_disk()
    pattern_actions = _build_pattern_actions_from_rules(rules, patterns)

    # Raccogli mittenti umani da pattern classificati come keep
    # sender_map: {email -> {name, domain, keep_patterns: [(normalized, pid)]}}
    sender_map: dict[str, dict] = {}

    for pat in patterns:
        pid = pat.get("id")
        normalized = pat.get("normalized", "")
        senders = pat.get("senders", [])

        # È già classificato come keep?
        is_keep = pattern_actions.get(pid) == "keep"

        if not is_keep:
            continue

        for sender_str in senders:
            name, email = _parse_sender(sender_str)
            if not email or not _is_human_sender(email, name):
                continue

            domain = email.split("@")[1].lower() if "@" in email else ""

            if email not in sender_map:
                sender_map[email] = {
                    "name": name,
                    "domain": domain,
                    "keep_patterns": [],
                }
            # Evita duplicati dello stesso pattern
            if not any(pn == normalized for pn, _ in sender_map[email]["keep_patterns"]):
                sender_map[email]["keep_patterns"].append((normalized, pid))

    # Ordina per numero di keep patterns decrescente, poi per email
    sorted_senders = sorted(
        sender_map.items(),
        key=lambda x: (-len(x[1]["keep_patterns"]), x[0]),
    )

    if not sorted_senders:
        typer.echo("\nNo suggested trusted senders found.")
        typer.echo(
            "Tip: use 'rules apply <id> -a keep -f <patterns.yaml>' first "
            "to classify patterns as keep."
        )
        return

    typer.echo("\nSuggested trusted senders:\n")

    # Raccogli i pattern ``from:contains`` delle regole trusted esistenti
    # per saltare mittenti già trustati
    _trusted_patterns: set[str] = set()
    for rule in rules:
        if rule.get("priority") == 95 and rule.get("label") == "fis-work":
            from_match = rule.get("match", {}).get("from", {}).get("contains", [])
            for pattern in from_match:
                if isinstance(pattern, str):
                    _trusted_patterns.add(pattern.lower())

    # Loop interattivo
    added: int = 0
    skipped: int = 0
    errors: int = 0
    rule_ids_to_add: list[dict] = []

    for i, (email, info) in enumerate(sorted_senders, start=1):
        # Salta se già trustato: la parte locale dell'email è già nei
        # ``from:contains`` di una regola priority=95 / label=fis-work
        local_part = email.split("@")[0].lower()
        if local_part in _trusted_patterns:
            logger.debug(f"Skipping {email}: already trusted ({local_part})")
            continue

        patterns_count = len(info["keep_patterns"])
        patterns_detail = ", ".join(pn[:50] for pn, _ in info["keep_patterns"])

        display_name = email
        if info["name"]:
            display_name = f"{info['name']} <{email}>"

        typer.echo(f" {i}. {display_name}")
        typer.echo(
            f"    {'Patterns' if patterns_count > 1 else 'Pattern'}: "
            f"{patterns_count} keep ({patterns_detail})"
        )

        confirmed = typer.confirm("    Trust?", default=False)

        if confirmed:
            try:
                rule = _create_trusted_rule(email, info["name"])
                rule_ids_to_add.append(rule)
                typer.echo("      ✓ Added")
                added += 1
            except Exception as e:
                logger.error(f"Failed to create rule for {email}: {e}")
                typer.echo("      ✗ Error")
                errors += 1
        else:
            typer.echo("      ⏭ Skipped")
            skipped += 1

    # Salva tutte le nuove regole su disco
    if rule_ids_to_add:
        path = _get_rules_path()
        existing = _load_rules_from_disk(path)
        # Aggiungi/overwrite per ID
        existing_ids = {r.get("id") for r in existing}
        for rule in rule_ids_to_add:
            if rule["id"] in existing_ids:
                existing = [r for r in existing if r.get("id") != rule["id"]]
            existing.append(rule)
        _save_rules_to_disk(existing, path)
        typer.echo("\nRules saved to disk. Run 'rules save' to deduplicate and sort.")

    typer.echo(f"\n Summary: {added} trusted added, {skipped} skipped, {errors} errors")


def _add_trusted(email_or_name: str) -> None:
    """Aggiunge un singolo mittente come trusted.

    Args:
        email_or_name: Indirizzo email o nome del mittente.
    """
    rule = _create_trusted_rule(email_or_name)

    path = _get_rules_path()
    existing = _load_rules_from_disk(path)
    # Overwrite per ID
    existing = [r for r in existing if r.get("id") != rule["id"]]
    existing.append(rule)
    _save_rules_to_disk(existing, path)

    typer.echo("Trusted rule created:\n")
    yaml_str = yaml.dump(
        rule,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    typer.echo(yaml_str.strip())
    typer.echo("\nRule added. Run 'rules save' to deduplicate and sort.")


def _list_trusted_rules() -> None:
    """Mostra tutte le regole trusted (priority=95, label=fis-work)."""
    rules = _load_rules_from_disk()
    trusted = [r for r in rules if r.get("priority") == 95 and r.get("label") == "fis-work"]

    if not trusted:
        typer.echo("No trusted sender rules found.")
        return

    _display_rules_table(trusted)


@rules_app.command("trust")
def rules_trust(
    suggest: bool = typer.Option(
        False,
        "--suggest",
        help="Suggest trusted senders from patterns YAML file.",
    ),
    add: str = typer.Option(
        None,
        "--add",
        help="Add a single sender as trusted (email or display name).",
    ),
    list_trusted: bool = typer.Option(
        False,
        "--list",
        help="List all trusted rules.",
    ),
    file: Path = typer.Option(
        None,
        "-f",
        "--file",
        help="Patterns YAML file (required for --suggest).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Manage trusted senders.

    Crea regole ``trusted-<slug>`` per mittenti da considerare
    sempre come ``keep`` (priority=95, label=fis-work).

    Esempi:

    \b
        # Suggerisci mittenti da patterns YAML
        rules trust --suggest -f /tmp/patterns.yaml

        # Aggiungi manualmente un mittente
        rules trust --add "donato.siravo@fisvi.com"

        # Elenca tutte le regole trusted
        rules trust --list
    """
    _setup_logging(verbose)

    # Verifica che esattamente uno dei tre modi sia attivo
    opt_count = sum([suggest, add is not None, list_trusted])
    if opt_count == 0:
        logger.error("Specifica uno di: --suggest, --add, --list")
        raise typer.Exit(code=2)
    if opt_count > 1:
        logger.error("--suggest, --add, --list sono mutuamente esclusivi")
        raise typer.Exit(code=2)

    if suggest:
        if not file:
            logger.error("--suggest requires -f/--file <patterns.yaml>")
            raise typer.Exit(code=2)
        _suggest_trusted(file)

    elif add is not None:
        _add_trusted(add)

    elif list_trusted:
        _list_trusted_rules()


@rules_app.command("list")
def rules_list(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """List current rules from filter_rules.yaml.

    Shows a table with ID, action, match conditions, and priority.
    """
    _setup_logging(verbose)
    rules = _load_rules_from_disk()
    _display_rules_table(rules)


@rules_app.command("show")
def rules_show(
    rule_id: str = typer.Argument(..., help="Rule ID to show (e.g. 'zabbix-problem')."),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Show details of a specific rule as YAML.

    Displays the full rule definition including all match conditions,
    action, priority, and metadata.
    """
    _setup_logging(verbose)
    rules = _load_rules_from_disk()
    found = [r for r in rules if r.get("id") == rule_id]

    if not found:
        typer.echo(f"Rule not found: {rule_id}")
        raise typer.Exit(code=1)

    rule = found[0]
    yaml_str = yaml.dump(
        rule,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    typer.echo(yaml_str.strip())


@rules_app.command("remove")
def rules_remove(
    rule_id: str = typer.Argument(..., help="Rule ID to remove (e.g. 'patrol-read')."),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Remove a rule from filter_rules.yaml on disk.

    The rule is removed immediately from the file.
    Use 'rules list' to verify the change.
    """
    _setup_logging(verbose)

    path = _get_rules_path()
    rules = _load_rules_from_disk(path)

    before = len(rules)
    rules = [r for r in rules if r.get("id") != rule_id]
    removed = before - len(rules)

    if removed == 0:
        typer.echo(f"Rule not found: {rule_id}")
        raise typer.Exit(code=1)

    _save_rules_to_disk(rules, path)
    typer.echo(f"Removed rule '{rule_id}' ({removed} rule(s) deleted).")


@rules_app.command("add")
def rules_add(
    subject_contains: list[str] = typer.Option(
        None,
        "--subject-contains",
        help="Subject contains pattern (can repeat for OR).",
    ),
    subject_not_contains: list[str] = typer.Option(
        None,
        "--subject-not-contains",
        help="Subject NOT contains pattern (can repeat).",
    ),
    from_contains: list[str] = typer.Option(
        None,
        "--from-contains",
        help="From contains pattern (can repeat for OR).",
    ),
    from_not_contains: list[str] = typer.Option(
        None,
        "--from-not-contains",
        help="From NOT contains pattern (can repeat).",
    ),
    action: str = typer.Option(..., "--action", "-a", help="Action: discard | aggregate | keep."),
    aggregate_to: str = typer.Option(
        None,
        "--aggregate-to",
        help="Template path for aggregates (e.g. '_review/daily/foo-{date}.md').",
    ),
    label: str = typer.Option(None, "--label", help="Label for keep actions."),
    priority: int = typer.Option(50, "--priority", "-p", help="Rule priority (default: 50)."),
    reason: str = typer.Option(None, "--reason", help="Human-readable reason."),
    name: str = typer.Option(None, "--name", help="Human-readable rule name."),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Add a classification rule to filter_rules.yaml on disk.

    Use --subject-contains multiple times for OR matching:
      --subject-contains "BACKUP FAILED" --subject-contains "BACKUP IS NOT"

    Use multiple different options for AND matching:
      --subject-contains "Problem:" --from-contains "zabbixsrv"

    The rule is written to disk immediately. Use 'rules save' to
    sort and deduplicate the full ruleset if needed.
    """
    _setup_logging(verbose)

    # Validate action
    if action not in ("discard", "aggregate", "keep"):
        logger.error(f"Invalid action '{action}'. Must be discard, aggregate, or keep.")
        raise typer.Exit(code=2)

    if action == "aggregate" and not aggregate_to:
        logger.error("Action 'aggregate' requires --aggregate-to.")
        raise typer.Exit(code=2)

    # Build match conditions
    match: dict[str, dict] = {}
    if subject_contains:
        match.setdefault("subject", {})["contains"] = subject_contains
    if subject_not_contains:
        match.setdefault("subject", {})["not_contains"] = subject_not_contains
    if from_contains:
        match.setdefault("from", {})["contains"] = from_contains
    if from_not_contains:
        match.setdefault("from", {})["not_contains"] = from_not_contains

    if not match:
        logger.error("At least one match condition is required (e.g. --subject-contains).")
        raise typer.Exit(code=2)

    # Generate rule ID
    rule_id = _generate_rule_id(subject_contains=subject_contains, name=name)

    rule: dict = {
        "id": rule_id,
        "action": action,
        "priority": priority,
        "match": match,
    }

    if name:
        rule["name"] = name
    if reason:
        rule["reason"] = reason
    if label:
        rule["label"] = label
    if aggregate_to:
        rule["aggregate_to"] = aggregate_to

    # Load existing rules, add/overwrite by ID
    path = _get_rules_path()
    existing = _load_rules_from_disk(path)
    existing = [r for r in existing if r.get("id") != rule_id]
    existing.append(rule)
    _save_rules_to_disk(existing, path)

    # Show the created rule
    typer.echo("Rule created:\n")
    yaml_str = yaml.dump(
        rule,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    typer.echo(yaml_str.strip())
    typer.echo(f"\nRule added. Use 'rules save' to sort and deduplicate the file.")


@rules_app.command("apply")
def rules_apply(
    pattern_id: int = typer.Argument(
        ..., help="Pattern ID from discover output to convert into a rule."
    ),
    action: str = typer.Option(..., "--action", "-a", help="Action: discard | aggregate | keep."),
    aggregate_to: str = typer.Option(
        None,
        "--aggregate-to",
        help="Template path for aggregates (required if action=aggregate).",
    ),
    label: str = typer.Option(None, "--label", help="Label for keep actions."),
    priority: int = typer.Option(50, "--priority", "-p", help="Rule priority (default: 50)."),
    file: Path = typer.Option(
        None,
        "--file",
        "-f",
        help="Discover YAML output file. Reads from stdin if not set.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Create a rule from a discovered pattern.

    Reads the discover output (from --file or stdin), finds the pattern
    by ID, automatically generates match conditions (subject contains
    key tokens, from contains domain), and adds a new rule.

    Example:
      discover -d 7 -o /tmp/patterns.yaml
      rules apply 1 -a aggregate \\
        --aggregate-to "_review/daily/zabbix-{date}.md" -f /tmp/patterns.yaml
    """
    _setup_logging(verbose)

    # Validate action
    if action not in ("discard", "aggregate", "keep"):
        logger.error(f"Invalid action '{action}'. Must be discard, aggregate, or keep.")
        raise typer.Exit(code=2)

    if action == "aggregate" and not aggregate_to:
        logger.error("Action 'aggregate' requires --aggregate-to.")
        raise typer.Exit(code=2)

    # Read discover YAML
    yaml_text: str
    if file:
        if not file.exists():
            logger.error(f"Discover output file not found: {file}")
            raise typer.Exit(code=1)
        yaml_text = file.read_text(encoding="utf-8")
    else:
        # Read from stdin
        if sys.stdin.isatty():
            logger.error(
                "No --file specified and stdin is a terminal. "
                "Either pipe discover output or use --file."
            )
            raise typer.Exit(code=2)
        yaml_text = sys.stdin.read()

    # Parse YAML
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML input: {e}")
        raise typer.Exit(code=1)

    if not isinstance(data, dict) or "patterns" not in data:
        logger.error("Input YAML has no 'patterns' key (not discover output?).")
        raise typer.Exit(code=1)

    # Find pattern by ID
    patterns_list = data["patterns"]
    pattern_data = None
    for pd in patterns_list:
        if isinstance(pd, dict) and pd.get("id") == pattern_id:
            pattern_data = pd
            break

    if pattern_data is None:
        logger.error(f"Pattern #{pattern_id} not found in discover output.")
        raise typer.Exit(code=1)

    # Reconstruct Pattern and infer rule
    pattern = PatternDiscovery.pattern_from_yaml_dict(pattern_data)
    inferred = PatternDiscovery.infer_rule_from_pattern(pattern)

    # Build the rule
    rule_id = _generate_rule_id(name=inferred.get("name", pattern.normalized))

    rule: dict = {
        "id": rule_id,
        "name": inferred.get("name", pattern.normalized)[:80],
        "action": action,
        "priority": priority,
        "match": inferred.get("match", {}),
    }

    if action == "aggregate" and aggregate_to:
        rule["aggregate_to"] = aggregate_to
    if label:
        rule["label"] = label
    rule["reason"] = f"Generated from discovered pattern #{pattern_id}: {pattern.count} emails"

    # Add to rules on disk
    path = _get_rules_path()
    existing = _load_rules_from_disk(path)
    existing = [r for r in existing if r.get("id") != rule_id]
    existing.append(rule)
    _save_rules_to_disk(existing, path)

    # Show what was generated
    typer.echo(f"Rule generated from pattern #{pattern_id}:\n")
    yaml_str = yaml.dump(
        rule,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    typer.echo(yaml_str.strip())
    typer.echo("\nRule added. Use 'rules save' to sort and deduplicate the file.")


@rules_app.command("save")
def rules_save(
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: filter_rules.yaml in tool directory).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite without confirmation.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Debug output to stderr.",
    ),
) -> None:
    """Save and finalize rules to filter_rules.yaml.

    Loads the current rules from disk, deduplicates by rule ID
    (last definition wins), sorts by priority descending, and
    writes a clean file with version header.
    """
    _setup_logging(verbose)

    path = output or _get_rules_path()

    # Warn if file exists and --force not set
    if path.exists() and not force:
        typer.echo(
            f"File {path} exists. Use --force to overwrite, or specify a different --output path."
        )
        if not typer.confirm("Proceed?", default=False):
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

    rules = _load_rules_from_disk(path if output else None)

    # Deduplicate by ID (last wins)
    seen: dict[str, dict] = {}
    for rule in rules:
        rule_id = rule.get("id")
        if rule_id:
            seen[rule_id] = rule
    deduped = list(seen.values())

    _save_rules_to_disk(deduped, path)
    typer.echo(
        f"Rules saved: {len(deduped)} rules (deduplicated from {len(rules)}, sorted by priority)."
    )


@app.command()
def thread(
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Ricostruisce il grafo thread da zero scansionando tutte le note.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Gestisce i thread email.

    Con ``--rebuild`` scansiona tutte le note nel vault, ricostruisce
    il grafo delle relazioni (parent/children/root), aggiorna il frontmatter
    di ogni nota e crea gli indici in ``Review/threads/``.
    """
    _setup_logging(verbose)

    if not rebuild:
        typer.echo("Specifica --rebuild per ricostruire i thread.")
        raise typer.Exit(code=0)

    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        logger.error(
            f"Vault email non trovato: {vault_root}. "
            "Imposta EMAIL_VAULT_ROOT o configuralo in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    logger.info("Fase 1: scansione note email...")
    notes = _scan_all_notes(vault_root)
    typer.echo(f"Note trovate: {len(notes)}")

    if not notes:
        logger.info("Nessuna nota da elaborare.")
        return

    logger.info("Fase 2: costruzione grafo thread...")
    parent_of, children_of, root_of = _build_thread_graph(notes)
    typer.echo(f"Thread root: {sum(1 for r in root_of.values() if r is None)}")

    # Crea mapping message_id → note info per lookup
    all_notes_map: dict[str, dict] = {n["message_id"]: n for n in notes}

    # --- Insieme di root IDs per creare indici ---
    root_ids: set[str] = set()
    for msg_id, root_id in root_of.items():
        if root_id is None:
            root_ids.add(msg_id)
        else:
            root_ids.add(root_id)

    logger.info("Fase 3: aggiornamento frontmatter note...")
    updated_count = 0
    for note in notes:
        msg_id = note["message_id"]
        parent = parent_of.get(msg_id)
        children = children_of.get(msg_id, [])
        root = root_of.get(msg_id)

        if _update_note_frontmatter(note["path"], parent, children, root):
            updated_count += 1

    typer.echo(f"Frontmatter aggiornati: {updated_count}")

    logger.info("Fase 4: scrittura indici thread...")
    index_count = 0
    for root_id in sorted(root_ids):
        result = _write_thread_index(root_id, all_notes_map, children_of, vault_root)
        if result:
            index_count += 1

    typer.echo(f"Indici thread creati: {index_count}")
    logger.info("Thread rebuild completato.")


@app.command()
def pipeline(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Esegue la pipeline completa: import → thread --rebuild → contacts.

    Esegue in sequenza:
    1. ``import --all`` (importa tutte le email dal source)
    2. ``thread --rebuild`` (ricostruisce il grafo thread)
    3. ``contacts`` (ricostruisce Addressbook da tutte le note)

    Infine crea un file segnale ``_review/queue/ready.task``.
    """
    _setup_logging(verbose)

    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        logger.error(
            f"Vault email non trovato: {vault_root}. "
            "Imposta EMAIL_VAULT_ROOT o configuralo in tools/config.yaml"
        )
        raise typer.Exit(code=1)

    typer.echo("=" * 50)
    typer.echo("  PIPELINE EMAIL — AVVIO")
    typer.echo("=" * 50)

    # --- Step 1: Import ---
    typer.echo("")
    typer.echo("[1/3] Importazione email...")
    email_dir = _get_email_dir()
    if not email_dir or not email_dir.exists():
        logger.error(
            f"Directory email {email_dir} non esiste. "
            "Imposta EMAIL_DIR o configurala in tools/config.yaml"
        )
        raise typer.Exit(code=1)
    _run_import(vault_root=vault_root, email_dir=email_dir, limit=None)
    typer.echo("  ✓ Import completato")

    # --- Step 2: Thread rebuild ---
    typer.echo("")
    typer.echo("[2/3] Ricostruzione thread...")

    notes = _scan_all_notes(vault_root)
    if notes:
        parent_of, children_of, root_of = _build_thread_graph(notes)
        all_notes_map = {n["message_id"]: n for n in notes}

        root_ids = set()
        for msg_id, root_id in root_of.items():
            if root_id is None:
                root_ids.add(msg_id)
            else:
                root_ids.add(root_id)

        updated = 0
        for note in notes:
            if _update_note_frontmatter(
                note["path"],
                parent_of.get(note["message_id"]),
                children_of.get(note["message_id"], []),
                root_of.get(note["message_id"]),
            ):
                updated += 1

        idx_count = 0
        for root_id in sorted(root_ids):
            if _write_thread_index(root_id, all_notes_map, children_of, vault_root):
                idx_count += 1

        typer.echo(f"  ✓ Thread ricostruiti: {idx_count} indici, {updated} frontmatter aggiornati")
    else:
        typer.echo("  - Nessuna nota trovata per thread rebuild")

    # --- Step 3: Contacts ---
    typer.echo("")
    typer.echo("[3/3] Ricostruzione contatti...")
    contact_stats = _rebuild_contacts_from_notes(vault_root)
    typer.echo(
        f"  ✓ Contatti: {contact_stats['created']} creati, "
        f"{contact_stats['updated']} aggiornati, {contact_stats['skipped']} saltati"
    )

    # --- Signal file ---
    typer.echo("")
    signal_dir = vault_root / "_review" / "queue"
    signal_dir.mkdir(parents=True, exist_ok=True)
    signal_path = signal_dir / "ready.task"

    signal_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),  # noqa: UP017
        "pipeline": "import+thread+contacts",
        "status": "ready",
    }

    try:
        signal_path.write_text(
            json.dumps(signal_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        typer.echo(f"  ✓ File segnale creato: {signal_path}")
    except OSError as e:
        logger.error(f"Errore scrittura file segnale {signal_path}: {e}")
        typer.echo(f"  ✗ Errore creazione file segnale: {e}")

    typer.echo("")
    typer.echo("=" * 50)
    typer.echo("  PIPELINE COMPLETATA")
    typer.echo("=" * 50)
