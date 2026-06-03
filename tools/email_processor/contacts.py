"""Modulo contatti per email_processor — crea/aggiorna schede in Addressbook/.

Funzioni principali:
- build_addressbook_index(): scansiona Addressbook/*.md, restituisce {email: slug}
- upsert_contact(): crea o aggiorna una singola scheda contatto
- upsert_contacts_from_email(): crea/aggiorna contatti da mittente/destinatari email
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_USER_EMAIL = "stefano.ranghetto@emerson.com"

# Regex per estrarre email: dal frontmatter YAML
_RE_EMAIL_FM = re.compile(r"^email:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

# Regex per pulizia nome mittente
_RE_DEPT_CODE = re.compile(r"\[[^\]]*\]")
_RE_EMAIL_ANGLE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Helpers di pulizia nome
# ---------------------------------------------------------------------------


def _clean_display_name(raw: str) -> str:
    """Pulisce un nome mittente grezzo.

    - Rimuove ``[dipartimento]`` (codici Outlook interni)
    - Rimuove ``<email>`` dal nome
    - Inverte ``"Cognome, Nome"`` → ``"Nome Cognome"``
    - Pulisce virgolette e spazi

    Args:
        raw: Nome grezzo (può contenere ``[codice]`` e ``<email>``).

    Returns:
        Nome pulito o stringa vuota se solo spazi.
    """
    if not raw:
        return ""
    s = _RE_DEPT_CODE.sub("", raw)
    s = _RE_EMAIL_ANGLE.sub("", s)
    s = s.strip().rstrip(">").strip().strip('"').strip("'").strip()
    s = re.sub(r"\s{2,}", " ", s)
    # Inverti "Cognome, Nome" → "Nome Cognome" (una sola virgola = separatore)
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            s = f"{parts[1]} {parts[0]}"
    return s.strip()


def _name_to_slug(name: str) -> str:
    """Converte un nome in slug per filename.

    "Mario Rossi" → ``mario-rossi``
    "Cognome, Nome" → ``nome-cognome`` (dopo clean interno)

    Args:
        name: Nome da convertire.

    Returns:
        Slug lowercase con trattini, max 60 caratteri.
        Stringa vuota se name è vuoto dopo pulizia.
    """
    cleaned = _clean_display_name(name)
    if not cleaned:
        return ""
    slug = re.sub(r"[^\w\s-]", "", cleaned.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    slug = slug.strip("-")
    # Tronca a 60 caratteri a word boundary
    if len(slug) > 60:
        last_dash = slug[:60].rfind("-")
        if last_dash > 0:
            slug = slug[:last_dash]
        else:
            slug = slug[:60]
    return slug


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _make_frontmatter(name: str, email: str, contact_date: str) -> str:
    """Costruisce il frontmatter YAML per una scheda contatto.

    Args:
        name: Nome completo del contatto (già pulito).
        email: Indirizzo email.
        contact_date: Data ISO (``YYYY-MM-DD``) del primo contatto.

    Returns:
        Stringa frontmatter YAML completa.
    """
    return (
        "---\n"
        f'name: "{name}"\n'
        f'email: "{email}"\n'
        'organization: ""\n'
        'role: ""\n'
        'phone: ""\n'
        f'first_contact: "{contact_date}"\n'
        f'last_contact: "{contact_date}"\n'
        "tags: []\n"
        "---\n"
    )


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------


def build_addressbook_index(addressbook_dir: Path) -> dict[str, str]:
    """Scansiona ``Addressbook/*.md`` e costruisce ``{email_lower: slug}``.

    Legge il frontmatter di ogni file ``.md`` in *addressbook_dir*,
    estrae il campo ``email:`` e costruisce un mapping
    email → slug (filename stem senza estensione).

    Args:
        addressbook_dir: Percorso della directory ``Addressbook/``.

    Returns:
        Dizionario ``{email_lowercase: slug}`` per contatti esistenti.
    """
    index: dict[str, str] = {}
    if not addressbook_dir.exists():
        logger.debug(f"Addressbook directory {addressbook_dir} non esiste")
        return index

    for md_file in sorted(addressbook_dir.glob("*.md")):
        # Salta il file cache _index.json (non è un .md, ma meglio controllare)
        if md_file.name == "_index.md":
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            match = _RE_EMAIL_FM.search(content)
            if match:
                # Strip eventuali virgolette YAML dal valore email
                email = match.group(1).strip().strip('"').strip("'").lower()
                if email:
                    index[email] = md_file.stem
        except OSError as e:
            logger.warning(f"Impossibile leggere {md_file}: {e}")

    logger.debug(f"Addressbook index: {len(index)} contatti trovati")
    return index


# ---------------------------------------------------------------------------
# CRUD contatti
# ---------------------------------------------------------------------------


def upsert_contact(
    addressbook_dir: Path,
    name: str,
    email: str,
    contact_date: str,
    index: dict[str, str],
) -> str | None:
    """Crea o aggiorna una scheda contatto in ``Addressbook/``.

    - **Skip** se email == ``stefano.ranghetto@emerson.com`` (contatto proprio)
    - **Skip** se *name* è vuoto dopo pulizia (mittenti macchina)
    - Cerca per **email** nell'*index*
    - **ESISTE**: aggiorna ``last_contact`` solo se *contact_date* > data esistente
    - **NON ESISTE**: crea nuova scheda con frontmatter standard

    Args:
        addressbook_dir: Percorso della directory ``Addressbook/``.
        name: Nome grezzo del contatto (viene pulito internamente).
        email: Indirizzo email.
        contact_date: Data ISO (``YYYY-MM-DD``).
        index: Mapping ``{email_lower: slug}`` — **aggiornato in-place**
              se viene creato un nuovo contatto.

    Returns:
        Slug del contatto (es. ``"mario-rossi"``) o ``None`` se skippato.
    """
    # --- Skip contatto proprio ---
    if email.lower() == _USER_EMAIL:
        logger.debug(f"Skip contatto utente: {email}")
        return None

    # --- Skip nome vuoto (mittenti macchina / automated) ---
    cleaned_name = _clean_display_name(name)
    if not cleaned_name:
        logger.debug(f"Skip mittente macchina: {email}")
        return None

    email_lower = email.lower()
    slug = index.get(email_lower)

    if slug:
        # --- CONTATTO ESISTE → aggiorna last_contact se più recente ---
        contact_path = addressbook_dir / f"{slug}.md"
        if contact_path.exists():
            try:
                content = contact_path.read_text(encoding="utf-8")
                # Leggi last_contact corrente
                lc_match = re.search(
                    r'^last_contact:\s*"?(\d{4}-\d{2}-\d{2})"?$',
                    content,
                    re.MULTILINE,
                )
                existing_lc = lc_match.group(1) if lc_match else ""
                if existing_lc and contact_date > existing_lc:
                    content = re.sub(
                        r'^last_contact:\s*"?(\d{4}-\d{2}-\d{2})"?$',
                        f'last_contact: "{contact_date}"',
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )
                    contact_path.write_text(content, encoding="utf-8")
                    logger.debug(f"Aggiornato last_contact per {slug}: {contact_date}")
            except OSError as e:
                logger.warning(f"Errore aggiornamento {slug}: {e}")
        return slug

    # --- CONTATTO NUOVO → crea scheda ---
    slug = _name_to_slug(cleaned_name)
    if not slug:
        logger.warning(f"Impossibile generare slug per {cleaned_name!r} / {email}")
        return None

    # Gestione collisione slug: se il file esiste già, disambiguia con hash email
    contact_path = addressbook_dir / f"{slug}.md"
    if contact_path.exists():
        email_hash = hashlib.md5(email.encode("utf-8")).hexdigest()[:6]
        slug = f"{slug}-{email_hash}"
        contact_path = addressbook_dir / f"{slug}.md"

    # Crea directory se non esiste
    addressbook_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = _make_frontmatter(cleaned_name, email, contact_date)
    try:
        contact_path.write_text(frontmatter, encoding="utf-8")
        logger.info(f"Nuovo contatto: {slug} ({cleaned_name} <{email}>)")
    except OSError as e:
        logger.error(f"Errore scrittura contatto {slug}: {e}")
        return None

    # Aggiorna index in-place per evitare duplicati nello stesso run
    index[email_lower] = slug

    return slug


def upsert_contacts_from_email(
    addressbook_dir: Path,
    from_raw: tuple[str, str],
    to_raw: list[tuple[str, str]],
    cc_raw: list[tuple[str, str]],
    date: str,
    index: dict[str, str],
) -> dict[str, int]:
    """Estrae contatti da una email e crea/aggiorna schede in ``Addressbook/``.

    Processa mittente (from), destinatari diretti (to) e copia (cc).

    Args:
        addressbook_dir: Percorso della directory ``Addressbook/``.
        from_raw: Tupla ``(name, email)`` del mittente.
        to_raw: Lista di tuple ``(name, email)`` dei destinatari To.
        cc_raw: Lista di tuple ``(name, email)`` dei destinatari Cc.
        date: Data ISO (``YYYY-MM-DD``) dell'email.
        index: Mapping ``{email_lower: slug}`` — aggiornato in-place.

    Returns:
        Dizionario statistiche: ``{"created": N, "updated": N, "skipped": N}``.
    """
    stats: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0}

    def _process_addr(name: str, email_addr: str) -> None:
        """Processa un singolo indirizzo e aggiorna stats."""
        if not email_addr:
            stats["skipped"] += 1
            return
        old_len = len(index)
        slug = upsert_contact(addressbook_dir, name, email_addr, date, index)
        if slug is None:
            stats["skipped"] += 1
        elif len(index) > old_len:
            stats["created"] += 1
        else:
            stats["updated"] += 1

    # Mittente
    if from_raw and len(from_raw) >= 2:
        _process_addr(from_raw[0], from_raw[1])

    # Destinatari To
    for addr in to_raw:
        if len(addr) >= 2:
            _process_addr(addr[0], addr[1])

    # Destinatari Cc
    for addr in cc_raw:
        if len(addr) >= 2:
            _process_addr(addr[0], addr[1])

    return stats


# ---------------------------------------------------------------------------
# Cache persistente
# ---------------------------------------------------------------------------


def save_index_cache(addressbook_dir: Path, index: dict[str, str]) -> None:
    """Salva l'indice contatti come ``Addressbook/_index.json`` (cache).

    Args:
        addressbook_dir: Percorso della directory ``Addressbook/``.
        index: Mapping ``{email_lower: slug}`` da salvare.
    """
    cache_path = addressbook_dir / "_index.json"
    try:
        addressbook_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        logger.debug(f"Cache indice salvata: {cache_path} ({len(index)} contatti)")
    except OSError as e:
        logger.warning(f"Impossibile salvare cache indice: {e}")


def load_index_cache(addressbook_dir: Path) -> dict[str, str] | None:
    """Carica l'indice contatti dalla cache ``Addressbook/_index.json``.

    Usato come fallback o ottimizzazione, ma il source of truth sono
    i file ``.md`` in ``Addressbook/``.

    Args:
        addressbook_dir: Percorso della directory ``Addressbook/``.

    Returns:
        Dizionario ``{email_lower: slug}`` o ``None`` se cache non valida.
    """
    cache_path = addressbook_dir / "_index.json"
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            logger.debug(f"Cache indice caricata: {cache_path} ({len(data)} contatti)")
            return data
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Cache indice non valida ({cache_path}): {e}")
    return None
