"""CLI del tool — Pre-flight check automatico dell'ambiente Team Olimpo.

Esegue verifiche su disco, permessi, rete, dipendenze Python e vault.

Uso:
    python -m tools.preflight_check
    python -m tools.preflight_check --verbose
"""

from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404
import sys
from pathlib import Path

import typer
from loguru import logger

# ---------------------------------------------------------------------------
# App Typer
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="preflight_check",
    help="Pre-flight check automatico dell'ambiente Team Olimpo.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Soglie
# ---------------------------------------------------------------------------

MIN_DISK_MB = 500

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


def _project_root() -> Path:
    """Risale fino alla root del progetto (dov'è opencode.json o Team/)."""
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "opencode.json").exists() or (candidate / "Team").is_dir():
            return candidate
    return cwd


# ---------------------------------------------------------------------------
# Check funzioni
# ---------------------------------------------------------------------------


def _check_disk(root: Path) -> tuple[bool, str]:
    """Spazio disco: almeno MIN_DISK_MB liberi."""
    usage = shutil.disk_usage(root)
    free_mb = usage.free / (1024 * 1024)
    ok = free_mb >= MIN_DISK_MB
    msg = (
        f"{free_mb:.0f} MB liberi (soglia: {MIN_DISK_MB} MB)"
        if ok
        else f"Solo {free_mb:.0f} MB liberi, serve almeno {MIN_DISK_MB} MB"
    )
    return ok, msg


def _check_permissions(root: Path) -> list[tuple[bool, str, str]]:
    """Permessi scrittura su cartelle critiche."""
    results: list[tuple[bool, str, str]] = []
    folders = ["Team/Handoff", "Library/deliverables"]
    for folder in folders:
        path = root / folder
        if not path.exists():
            results.append((False, folder, "Cartella non trovata"))
        elif os.access(str(path), os.W_OK):
            results.append((True, folder, "Scrivibile"))
        else:
            results.append((False, folder, "Permessi insufficienti"))
    return results


def _check_internet() -> tuple[bool, str]:
    """Ping a 8.8.8.8."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "8.8.8.8"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Raggiungibile (8.8.8.8)"
        return False, "Ping fallito"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"Errore ping: {e}"


def _check_python_env(root: Path) -> list[tuple[bool, str, str]]:
    """Verifica che typer e loguru siano importabili."""
    results: list[tuple[bool, str, str]] = []
    for mod in ("typer", "loguru"):
        try:
            __import__(mod)
            results.append((True, mod, "Importabile"))
        except ImportError:
            results.append((False, mod, f"Modulo '{mod}' non trovato"))
    return results


def _check_vault(root: Path) -> tuple[bool, str]:
    """Verifica che Library/ esista e contenga .md."""
    vault = root / "lib"
    if not vault.is_dir():
        return False, "Cartella Library/ non trovata"
    md_files = list(vault.rglob("*.md"))
    if md_files:
        return True, f"Trovati {len(md_files)} file .md in Library/"
    return False, "Nessun file .md in Library/"


# ---------------------------------------------------------------------------
# Comando
# ---------------------------------------------------------------------------


@app.command()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Esegue il pre-flight check completo dell'ambiente."""
    _setup_logging(verbose)

    root = _project_root()
    logger.debug(f"Project root: {root}")

    results: list[tuple[str, bool, str]] = []

    # 1. Disco (critico)
    ok, msg = _check_disk(root)
    results.append(("disco", ok, msg))
    logger.debug(f"Check disco: {msg}")

    # 2. Permessi (non critico)
    perm_results = _check_permissions(root)
    for ok, folder, msg in perm_results:
        tag = "permessi"
        results.append((tag, ok, f"{folder}: {msg}"))
        logger.debug(f"Check permessi {folder}: {msg}")

    # 3. Internet (critico)
    ok, msg = _check_internet()
    results.append(("internet", ok, msg))
    logger.debug(f"Check internet: {msg}")

    # 4. Python env (critico)
    mod_results = _check_python_env(root)
    for ok, mod, msg in mod_results:
        tag = "python_env"
        results.append((tag, ok, f"{mod}: {msg}"))
        logger.debug(f"Check python_env {mod}: {msg}")

    # 5. Vault (non critico)
    ok, msg = _check_vault(root)
    results.append(("vault", ok, msg))
    logger.debug(f"Check vault: {msg}")

    # --- Output ---
    critical_fails = 0
    noncritical_fails = 0

    critical_tags = {"disco", "internet", "python_env"}
    noncritical_tags = {"permessi", "vault"}

    for tag, ok, msg in results:
        if ok:
            typer.echo(f"[PASS] {msg}")
        elif tag in critical_tags:
            typer.echo(f"[FAIL] {msg}")
            critical_fails += 1
        elif tag in noncritical_tags:
            typer.echo(f"[WARN] {msg}")
            noncritical_fails += 1

    # --- Exit ---
    if critical_fails > 0:
        typer.echo("")
        typer.echo("❌ Check critici falliti")
        raise typer.Exit(code=1)

    if noncritical_fails > 0:
        typer.echo("")
        typer.echo("⚠️ Check superati con warning")
        raise typer.Exit(code=0)

    typer.echo("")
    typer.echo("✅ Tutti i check superati")
