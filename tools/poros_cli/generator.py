"""
Generator — Comandi di generazione template per hermes_cli.

Fornisce funzioni per creare scratchpad per nuovi agenti e file handoff
con naming e frontmatter conformi alle convenzioni del Team Olimpo.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger

from tools.hermes_cli.config import (
    HANDOFF_DIR,
    MEMBRI,
    PRIORITA_VALIDE,
    PROJECT_ROOT,
    TIPI_HANDOFF,
)

ROOT_DIR = PROJECT_ROOT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str, max_words: int = 5) -> str:
    """
    Converte un testo in slug kebab-case.

    - lowercase
    - rimuove accenti
    - sostituisce spazi e underscore con trattini
    - rimuove caratteri non alfanumerici (tranne trattini)
    - tronca a max_words parole

    Args:
        text: Testo da convertire.
        max_words: Numero massimo di parole nello slug.

    Returns:
        Slug kebab-case.
    """
    # Normalizza unicode (scompone caratteri accentati)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()

    # Sostituisce underscore con trattini
    text = text.replace("_", "-")

    # Rimuove caratteri non ammessi (solo lettere, numeri, trattini)
    text = re.sub(r"[^a-z0-9-]", " ", text)

    # Split in parole e tronca
    words = [w for w in text.split() if w]
    words = words[:max_words]

    return "-".join(words)


def _template_path(name: str) -> Path:
    """Restituisce il path a un template nella directory templates/."""
    return Path(__file__).parent / "templates" / name


def _backup_path(original: Path) -> Path:
    """Genera un path di backup in /tmp/poros-cli-backup/."""
    today = date.today().isoformat()
    backup_dir = Path("/tmp/poros-cli-backup") / today
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / original.name


def _backup_file(file_path: Path) -> Path | None:
    """Copia un file in /tmp/poros-cli-backup/. Torna il path backup o None."""
    try:
        dest = _backup_path(file_path)
        shutil.copy2(file_path, dest)
        logger.info(f"Backup creato: {dest}")
        return dest
    except OSError as exc:
        logger.error(f"Backup fallito per {file_path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_template(template_name: str, variables: dict[str, str]) -> str:
    """
    Legge un template e sostituisce i placeholder {{CHIAVE}}.

    Args:
        template_name: Nome del file template (es. 'scratchpad-template.md').
        variables: Dizionario {chiave: valore} per i placeholder.

    Returns:
        Contenuto del template renderizzato.

    Raises:
        FileNotFoundError: Se il template non esiste.
    """
    tpl_path = _template_path(template_name)
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template non trovato: {tpl_path}")

    content = tpl_path.read_text(encoding="utf-8")
    for key, value in variables.items():
        content = content.replace("{{" + key + "}}", value)
    return content


# ---------------------------------------------------------------------------
# scratchpad init
# ---------------------------------------------------------------------------


def init_scratchpad(
    agent_name: str,
    role: str = "Membro del Team Olimpo",
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Crea un nuovo scratchpad per un agente.

    Args:
        agent_name: Nome dell'agente (es. 'Eunomia').
        role: Ruolo descrittivo.
        force: Sovrascrive se esiste.
        dry_run: Mostra senza creare.

    Returns:
        Dizionario con esito, path creato, errori.
    """
    result: dict[str, Any] = {
        "success": False,
        "path": None,
        "errors": [],
        "warnings": [],
    }

    # Verifica nome agente
    if not agent_name or not agent_name.strip():
        result["errors"].append("Nome agente non valido.")
        return result

    agent_name = agent_name.strip().capitalize()
    slug = agent_name.lower()

    # Path destinazione
    dest_dir = ROOT_DIR / "Team" / agent_name
    dest_file = dest_dir / "Scratchpad.md"

    if dest_file.exists() and not force:
        result["errors"].append(f"Il file esiste già: {dest_file}. Usa --force per sovrascrivere.")
        return result

    if dry_run:
        result["success"] = True
        result["path"] = str(dest_file)
        result["warnings"].append("Dry-run: nessun file creato.")
        return result

    # Crea directory se non esiste
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result["errors"].append(f"Impossibile creare directory {dest_dir}: {exc}")
        return result

    # Rendi il template
    today = date.today().isoformat()
    try:
        content = _render_template(
            "scratchpad-template.md",
            {
                "NOME": agent_name,
                "SLUG": slug,
                "RUOLO": role,
                "DATA": today,
            },
        )
    except FileNotFoundError as exc:
        result["errors"].append(str(exc))
        return result
    except Exception as exc:
        result["errors"].append(f"Errore rendering template: {exc}")
        return result

    # Backup se esistente
    if dest_file.exists() and force:
        _backup_file(dest_file)

    # Scrivi
    try:
        dest_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        result["errors"].append(f"Impossibile scrivere {dest_file}: {exc}")
        return result

    result["success"] = True
    result["path"] = str(dest_file)
    logger.info(f"Scratchpad creato: {dest_file}")
    return result


# ---------------------------------------------------------------------------
# handoff create
# ---------------------------------------------------------------------------


def create_handoff(
    tipo: str,
    destinatario: str,
    titolo: str,
    mittente: str = "poros",
    priorita: str = "media",
    data_str: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Crea un file handoff con naming e frontmatter corretti.

    Args:
        tipo: Tipo handoff (da HANDOFF_TIPI).
        destinatario: Nome destinatario (da MEMBRI o 'team').
        titolo: Titolo descrittivo (max 60 caratteri).
        mittente: Nome mittente (default: poros).
        priorita: Priorità (alta|media|bassa).
        data_str: Data YYYY-MM-DD (default: oggi).
        force: Sovrascrive se esiste.
        dry_run: Mostra senza creare.

    Returns:
        Dizionario con esito, path creato, errori.
    """
    result: dict[str, Any] = {
        "success": False,
        "path": None,
        "errors": [],
        "warnings": [],
    }

    # Valida tipo
    if tipo not in TIPI_HANDOFF:
        result["errors"].append(f"Tipo non valido: '{tipo}'. Validi: {', '.join(TIPI_HANDOFF)}")
        return result

    # Valida destinatario
    if destinatario not in MEMBRI and destinatario != "team":
        result["errors"].append(
            f"Destinatario non valido: '{destinatario}'. "
            f"Validi: {', '.join(sorted(MEMBRI))}, 'team'"
        )
        return result

    # Valida mittente
    if mittente not in MEMBRI:
        result["errors"].append(
            f"Mittente non valido: '{mittente}'. Validi: {', '.join(sorted(MEMBRI))}"
        )
        return result

    # Valida priorità
    if priorita not in PRIORITA_VALIDE:
        result["errors"].append(
            f"Priorità non valida: '{priorita}'. Validi: {', '.join(PRIORITA_VALIDE)}"
        )
        return result

    # Valida titolo
    if len(titolo) > 60:
        result["warnings"].append(
            f"Titolo troppo lungo ({len(titolo)} caratteri, max 60). Verrà troncato."
        )
        titolo = titolo[:57] + "..."

    if not titolo.strip():
        result["errors"].append("Titolo non può essere vuoto.")
        return result

    if result["errors"]:
        return result

    # Data
    if data_str:
        try:
            parsed_date = date.fromisoformat(data_str)
        except ValueError:
            result["errors"].append(f"Data non valida: '{data_str}'. Usa YYYY-MM-DD.")
            return result
    else:
        parsed_date = date.today()

    data_str = parsed_date.isoformat()

    # Genera slug
    slug = _slugify(titolo)
    if not slug:
        result["errors"].append(f"Impossibile generare slug dal titolo: '{titolo}'")
        return result

    # Nome file
    filename = f"{data_str}_{mittente}-{destinatario}_{tipo}_{slug}.md"

    # Cartella destinazione
    year = str(parsed_date.year)
    month = f"{parsed_date.month:02d}"
    day = f"{parsed_date.day:02d}"
    dest_dir = HANDOFF_DIR / year / month / day
    dest_file = dest_dir / filename

    # Verifica collisioni
    if dest_file.exists() and not force:
        result["errors"].append(f"Il file esiste già: {dest_file}. Usa --force per sovrascrivere.")
        return result

    if dry_run:
        result["success"] = True
        result["path"] = str(dest_file)
        result["warnings"].append("Dry-run: nessun file creato.")
        result["_content"] = _render_template(
            "handoff-template.md",
            {
                "DATA": data_str,
                "MITTENTE": mittente,
                "DESTINATARIO": destinatario,
                "TIPO": tipo,
                "TITOLO": titolo,
                "PRIORITA": priorita,
            },
        )
        return result

    # Crea directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Rendering template
    try:
        content = _render_template(
            "handoff-template.md",
            {
                "DATA": data_str,
                "MITTENTE": mittente,
                "DESTINATARIO": destinatario,
                "TIPO": tipo,
                "TITOLO": titolo,
                "PRIORITA": priorita,
            },
        )
    except FileNotFoundError as exc:
        result["errors"].append(str(exc))
        return result

    # Backup se esistente
    if dest_file.exists() and force:
        _backup_file(dest_file)

    # Scrivi
    try:
        dest_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        result["errors"].append(f"Impossibile scrivere {dest_file}: {exc}")
        return result

    result["success"] = True
    result["path"] = str(dest_file)
    logger.info(f"Handoff creato: {dest_file}")
    return result


# ---------------------------------------------------------------------------
# Fix logic (validate --fix)
# ---------------------------------------------------------------------------


def _ensure_handoff_frontmatter(file_path: Path) -> dict[str, Any]:
    """
    Aggiunge frontmatter minimale a un file handoff che ne è privo.

    Args:
        file_path: Path del file da riparare.

    Returns:
        Dizionario con esito e operazioni effettuate.
    """
    result: dict[str, Any] = {
        "fixed": False,
        "action": None,
        "backup": None,
    }

    text = file_path.read_text(encoding="utf-8")

    # Verifica se ha già frontmatter
    if text.startswith("---"):
        result["action"] = "already_has_frontmatter"
        return result

    # Backup
    backup = _backup_file(file_path)
    if backup:
        result["backup"] = str(backup)

    # Genera frontmatter minimale dal nome file
    # Pattern: YYYY-MM-DD_mittente-destinatario_tipo_slug.md
    stem = file_path.stem
    parts = stem.split("_")

    fm_data = date.today().isoformat()
    fm_mittente = "poros"
    fm_destinatario = "team"
    fm_tipo = "nota"
    fm_titolo = stem.replace("-", " ").replace("_", " ").title()

    # Prova a parsare dal nome
    if len(parts) >= 4:
        # Potrebbe essere YYYY-MM-DD_mittente-dest_tipo_slug
        date_part = parts[0]
        try:
            date.fromisoformat(date_part)
            fm_data = date_part
            mittente_dest = parts[1].split("-")
            if len(mittente_dest) >= 1:
                fm_mittente = mittente_dest[0]
            if len(mittente_dest) >= 2:
                fm_destinatario = mittente_dest[1]
            if len(parts) >= 3:
                fm_tipo = (
                    parts[2]
                    if parts[2]
                    in ("profilo", "specifica", "feedback", "bug", "report", "test", "nota")
                    else "nota"
                )
        except ValueError:
            pass

    frontmatter = (
        "---\n"
        f"data: {fm_data}\n"
        f"mittente: {fm_mittente}\n"
        f"destinatario: {fm_destinatario}\n"
        f"tipo: {fm_tipo}\n"
        f"stato: da-processare\n"
        f"priorita: media\n"
        f'titolo: "{fm_titolo[:60]}"\n'
        "---\n"
    )

    new_text = frontmatter + text

    try:
        file_path.write_text(new_text, encoding="utf-8")
        result["fixed"] = True
        result["action"] = "added_frontmatter"
        logger.info(f"Frontmatter aggiunto a {file_path.name}")
    except OSError as exc:
        logger.error(f"Errore scrittura {file_path}: {exc}")
        result["action"] = f"error: {exc}"

    return result


def fix_handoff_file(
    file_path: Path, fix_name: bool = True, fix_frontmatter: bool = True
) -> dict[str, Any]:
    """
    Applica --fix a un file handoff.

    - Rinomina il file se il nome non è conforme
    - Aggiunge frontmatter se assente

    Args:
        file_path: Path del file da riparare.
        fix_name: Se True, corregge il naming.
        fix_frontmatter: Se True, aggiunge frontmatter se assente.

    Returns:
        Dizionario con esito e operazioni.
    """
    from tools.hermes_cli.validator import validate_handoff_file

    result: dict[str, Any] = {
        "path": str(file_path),
        "renamed": False,
        "new_path": None,
        "frontmatter_fixed": False,
        "backup": None,
        "warnings": [],
        "errors": [],
    }

    hv = validate_handoff_file(file_path)

    # Fix naming: se non valido, rinomina
    if fix_name and not hv.naming_valid:
        # Cerca di estrarre data dal contenuto o usa oggi
        data = date.today().isoformat()
        mittente = "poros"
        dest = "team"
        tipo = "nota"
        slug = _slugify(file_path.stem)

        # Se possibile, estrai mittente-destinatario dal vecchio nome
        stem = file_path.stem.lower()
        parts = stem.split("_")
        for i, part in enumerate(parts):
            if "-" in part and i >= 1:
                names = part.split("-")
                if len(names) >= 2:
                    # Potrebbe essere mittente-destinatario
                    if names[0] in MEMBRI:
                        mittente = names[0]
                    if names[1] in MEMBRI or names[1] == "team":
                        dest = names[1]

        new_name = f"{data}_{mittente}-{dest}_{tipo}_{slug}.md"
        new_path = file_path.parent / new_name

        if new_path == file_path:
            # Già conforme dopo normalizzazione
            result["renamed"] = False
        elif new_path.exists():
            result["warnings"].append(f"Collisione: {new_path} esiste già. Skippo rename.")
        else:
            # Backup
            backup = _backup_file(file_path)
            if backup:
                result["backup"] = str(backup)
            # Rinomina
            try:
                file_path.rename(new_path)
                result["renamed"] = True
                result["new_path"] = str(new_path)
                logger.info(f"File rinominato: {file_path.name} → {new_name}")
                file_path = new_path  # Aggiorna per eventuale fix frontmatter
            except OSError as exc:
                result["errors"].append(f"Errore rename {file_path.name}: {exc}")

    # Fix frontmatter: se assente, aggiungi
    if fix_frontmatter and hv is not None and not hv.has_frontmatter:
        fm_result = _ensure_handoff_frontmatter(file_path)
        result["frontmatter_fixed"] = fm_result["fixed"]
        if fm_result.get("backup"):
            result["backup"] = fm_result["backup"]

    return result


def fix_all_handoffs(
    fix_name: bool = True,
    fix_frontmatter: bool = True,
) -> dict[str, Any]:
    """
    Applica --fix a tutti gli handoff.

    Args:
        fix_name: Se True, corregge naming.
        fix_frontmatter: Se True, aggiunge frontmatter se assente.

    Returns:
        Dizionario con riepilogo operazioni.
    """
    from tools.hermes_cli.scanner import scan_handoff_files

    paths = scan_handoff_files(HANDOFF_DIR)
    results = []
    fixed_count = 0
    error_count = 0

    for p in paths:
        r = fix_handoff_file(p, fix_name=fix_name, fix_frontmatter=fix_frontmatter)
        results.append(r)
        if r.get("renamed") or r.get("frontmatter_fixed"):
            fixed_count += 1
        if r.get("errors"):
            error_count += 1

    return {
        "total": len(paths),
        "fixed": fixed_count,
        "errors": error_count,
        "details": results,
    }
