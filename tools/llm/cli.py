"""
Parsing degli argomenti CLI e logica principale per il tool consulto.

Gestisce:
- Due app Typer separate: app_main (comando principale) e app_models (subcommand models)
- Il routing tra le due app e' gestito in __main__.py in base al primo argomento
- Setup del logging via loguru
- Risoluzione del provider e della API key
- Esecuzione della chiamata e output del risultato
- Comando 'models': lista modelli disponibili
- Modalita' batch: --prompt + --input
- Modalita' interattiva: nessun argomento oppure -i

Utilizzo:
  python -m tools.llm "testo del prompt"
  python -m tools.llm --provider gemini "testo"
  python -m tools.llm --provider grok --model grok-4.20-0309-non-reasoning "testo"
  python -m tools.llm --stdin < file.txt
  python -m tools.llm models
  python -m tools.llm models --provider grok
  python -m tools.llm --prompt Team/Prompts/kba/analisi-rischio.md --input lib/documents/*.md
  python -m tools.llm -i
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger

from tools.llm.config import (
    DEFAULT_PROVIDER,
    KNOWN_PRICES,
    PROMPTS_DIR,
    TOOL_VERSION,
    get_api_key,
)
from tools.llm.providers import PROVIDERS

# App principale: gestisce il prompt singolo, batch, interattivo
app = typer.Typer(
    name="llm",
    help="Invia prompt a Grok o Gemini. Senza argomenti avvia la modalita' interattiva.",
    no_args_is_help=False,
)

# App per il subcommand 'models': routing manuale da __main__.py
app_models = typer.Typer(
    name="llm models",
    help="Elenca i modelli disponibili per provider.",
    no_args_is_help=False,
)


# ---------------------------------------------------------------------------
# Configurazione logging
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False) -> None:
    """
    Configura loguru per il tool consulto.

    In modalita' normale: solo WARNING+ su stderr.
    In modalita' verbose: DEBUG su stderr.

    Args:
        verbose: Se True, mostra i messaggi DEBUG su stderr
    """
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{level:<8}</level> | {message}",
        colorize=False,
    )


# ---------------------------------------------------------------------------
# Helper dry-run
# ---------------------------------------------------------------------------


def _print_dry_run(system: str | None, user_prompt: str, n_files: int = 1) -> None:
    """
    Stampa il payload che verrebbe inviato all'API senza effettuare la chiamata.

    Args:
        system: System prompt (o None se assente)
        user_prompt: Testo del prompt utente (gia' renderizzato se batch)
        n_files: Numero totale di file nel batch (default 1 per chiamata singola)
    """
    print("=== SYSTEM ===")
    print(system if system else "(nessuno)")
    print("=== USER ===")
    print(user_prompt)
    print("=== END DRY RUN ===")
    if n_files > 1:
        print(
            f"[dry-run] Batch: {n_files} file totali (mostrato solo il primo)",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Formato prezzi modelli
# ---------------------------------------------------------------------------


def _format_price(model_id: str) -> str:
    """
    Formatta la riga prezzi per un modello.

    Se il modello e' in KNOWN_PRICES mostra input/output per milione di token.
    Altrimenti mostra 'prezzo n.d.'.

    Args:
        model_id: Identificatore del modello

    Returns:
        Stringa formattata con i prezzi o indicazione di non disponibilita'
    """
    if model_id in KNOWN_PRICES:
        inp, out = KNOWN_PRICES[model_id]
        return f"input: ${inp:.2f}/M   output: ${out:.2f}/M"
    return "prezzo n.d."


def _format_stats(response: Any) -> str:
    """
    Formatta una riga compatta di statistiche dopo una chiamata AI.

    Esempio output: (3m 25s · 8.0k tokens · $0.0032)

    Args:
        response: ChatResponse con elapsed_seconds, input_tokens, output_tokens, model_used.

    Returns:
        Stringa formattata tra parentesi, o stringa vuota se nessun dato disponibile.
    """
    parts: list[str] = []

    # Tempo
    if response.elapsed_seconds is not None:
        secs = response.elapsed_seconds
        if secs >= 60:
            m = int(secs // 60)
            s = int(secs % 60)
            parts.append(f"{m}m {s:02d}s")
        else:
            parts.append(f"{secs:.1f}s")

    # Token distinti input / output
    inp = response.input_tokens
    out = response.output_tokens
    if inp is not None or out is not None:

        def _fmt(n: int | None) -> str:
            if n is None:
                return "?"
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

        parts.append(f"↑{_fmt(inp)} ↓{_fmt(out)} tok")

    # Costo stimato
    model_id = response.model_used or ""
    if model_id in KNOWN_PRICES and response.input_tokens and response.output_tokens:
        inp_price, out_price = KNOWN_PRICES[model_id]
        cost = (response.input_tokens * inp_price + response.output_tokens * out_price) / 1_000_000
        parts.append(f"${cost:.4f}")

    if not parts:
        return ""
    return "(" + " · ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Subcommand: models (app separata, invocata da __main__.py)
# ---------------------------------------------------------------------------


@app_models.command()
def cmd_models(
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="Filtra per provider (grok, gemini, openrouter)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
) -> None:
    """Elenca i modelli disponibili per provider."""
    _setup_logging(verbose=verbose)

    # Determina quali provider interrogare
    if provider:
        if provider not in PROVIDERS:
            print(f"Errore: provider '{provider}' non riconosciuto.", file=sys.stderr)
            raise typer.Exit(code=1)
        target_providers = {provider: PROVIDERS[provider]}
    else:
        target_providers = dict(PROVIDERS)

    # Nomi display per i provider
    provider_display = {
        "grok": "GROK (xAI)",
        "gemini": "GEMINI (Google)",
        "openrouter": "OPENROUTER",
    }

    any_error = False

    for pname, pclass in target_providers.items():
        display = provider_display.get(pname, pname.upper())
        print(f"\n{display}")

        api_key = get_api_key(pname)
        try:
            instance = pclass(api_key=api_key)
        except ImportError as exc:
            print(f"  Errore: {exc}", file=sys.stderr)
            any_error = True
            continue

        try:
            models = instance.list_models()
        except RuntimeError as exc:
            print(f"  Errore recupero modelli: {exc}", file=sys.stderr)
            any_error = True
            continue

        if not models:
            print("  (nessun modello trovato)")
            continue

        for m in models:
            default_tag = "[default]" if m.is_default else ""
            price_str = _format_price(m.id)
            print(f"  {m.id:<40} {default_tag:<12} {price_str}")

    print()  # riga vuota finale

    if any_error:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Comando principale (app)
# ---------------------------------------------------------------------------


@app.command()
def main(
    prompt_text: Optional[str] = typer.Argument(None, help="Testo del prompt (opzionale)."),
    provider: str = typer.Option(
        DEFAULT_PROVIDER, "--provider", "-p", help="Provider LLM (grok, gemini, openrouter)."
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override modello."),
    system: Optional[str] = typer.Option(None, "--system", help="System prompt o path a file."),
    stdin: bool = typer.Option(False, "--stdin", help="Legge prompt da stdin."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Modalita' interattiva."),
    prompt_file: Optional[Path] = typer.Option(None, "--prompt", help="Template Markdown batch."),
    input: Optional[List[Path]] = typer.Option(None, "--input", help="File/glob per batch."),
    output: Optional[Path] = typer.Option(None, "--output", help="Cartella output batch."),
    merge: bool = typer.Option(False, "--merge", help="Merge file in singolo call."),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="Salta output esistenti."),
    var: Optional[List[str]] = typer.Option(
        None, "--var", metavar="KEY=VALUE", help="Variabile template (ripetibile)."
    ),
    agent_count: int = typer.Option(
        4,
        "--agent-count",
        help="Numero agenti per modelli multi-agent (4 o 16). Ignorato per modelli standard.",
    ),
    web_search: bool = typer.Option(
        False, "--web-search", help="Abilita ricerca web (solo Grok, Responses API)."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Mostra payload senza chiamare API."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output debug su stderr."),
    version: bool = typer.Option(False, "--version", help="Mostra versione ed esce."),
) -> None:
    """Invia prompt a Grok o Gemini. Senza argomenti avvia la modalita' interattiva."""
    # Forza UTF-8 su stdout e stderr per gestire caratteri non-ASCII
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if version:
        print(f"llm {TOOL_VERSION}")
        raise typer.Exit(code=0)

    # --- Risoluzione --system come path ---
    if system:
        try:
            _p = Path(system)
            if _p.is_file():
                system = _p.read_text(encoding="utf-8")
        except OSError:
            pass

    # --- Parsing --var ---
    extra_vars: dict[str, str] = {}
    if var:
        for _entry in var:
            _k, _, _v = _entry.partition("=")
            if _k:
                extra_vars[_k] = _v

    _setup_logging(verbose=verbose)

    # --- Modalita' interattiva ---
    no_input = not prompt_text and not stdin and not prompt_file
    if interactive or no_input:
        from tools.llm.interactive import run_interactive

        result = run_interactive(
            providers_map=PROVIDERS,
            get_api_key_fn=get_api_key,
            default_provider=provider,
            prompts_dir=PROMPTS_DIR,
            web_search=web_search,
        )
        raise typer.Exit(code=result)

    # --- Modalita' batch ---
    if prompt_file:
        if not input:
            print(
                "Errore: --prompt richiede --input con uno o piu' file o glob pattern.",
                file=sys.stderr,
            )
            raise typer.Exit(code=1)

        from tools.llm.batch import (
            expand_inputs,
            extract_prompt_section,
            render_template,
            run_batch,
            run_merge,
        )

        # Leggi template
        if not prompt_file.is_file():
            print(f"Errore: file template non trovato: {prompt_file}", file=sys.stderr)
            raise typer.Exit(code=1)

        try:
            raw_md = prompt_file.read_text(encoding="utf-8")
            template = extract_prompt_section(raw_md)
        except ValueError as exc:
            print(f"Errore template: {exc}", file=sys.stderr)
            raise typer.Exit(code=1)

        # Espandi file di input — input e' una lista di Path, batch.py gestisce glob
        input_strs = [str(p) for p in input]
        try:
            input_files = expand_inputs(input_strs)
        except ValueError as exc:
            print(f"Errore: {exc}", file=sys.stderr)
            raise typer.Exit(code=1)

        logger.debug(f"Batch: {len(input_files)} file trovati")

        # --- Dry-run batch ---
        if dry_run:
            first_file = input_files[0]
            kba_text_dr = first_file.read_text(encoding="utf-8", errors="replace")
            rendered_dr = render_template(template, kba_text_dr, first_file.stem, extra_vars)
            _print_dry_run(system, rendered_dr, n_files=len(input_files))
            raise typer.Exit(code=0)

        # Provider
        api_key = get_api_key(provider)
        provider_class = PROVIDERS[provider]
        try:
            provider_instance = provider_class(api_key=api_key)
        except ImportError as exc:
            print(f"Errore: {exc}", file=sys.stderr)
            raise typer.Exit(code=1)

        output_dir = output if output else None

        if merge:
            errors = run_merge(
                provider=provider_instance,
                provider_name=provider,
                template=template,
                input_files=input_files,
                output_dir=output_dir,
                model=model,
                system=system,
                extra_vars=extra_vars,
            )
        else:
            errors = run_batch(
                provider=provider_instance,
                provider_name=provider,
                template=template,
                input_files=input_files,
                output_dir=output_dir,
                model=model,
                system=system,
                skip_existing=skip_existing,
                extra_vars=extra_vars,
            )
        raise typer.Exit(code=0 if errors == 0 else 1)

    # --- Chiamata singola ---
    if stdin:
        logger.debug("Lettura prompt da stdin")
        prompt = sys.stdin.read()
        if not prompt.strip():
            print("Errore: stdin vuoto — nessun prompt ricevuto.", file=sys.stderr)
            raise typer.Exit(code=1)
    elif prompt_text:
        prompt = prompt_text
    else:
        # Fallback: interattiva
        from tools.llm.interactive import run_interactive

        result = run_interactive(
            providers_map=PROVIDERS,
            get_api_key_fn=get_api_key,
            default_provider=provider,
            prompts_dir=PROMPTS_DIR,
            web_search=web_search,
        )
        raise typer.Exit(code=result)

    # --- Dry-run singolo ---
    if dry_run:
        _print_dry_run(system, prompt)
        raise typer.Exit(code=0)

    logger.debug(f"Provider selezionato: {provider}")

    api_key = get_api_key(provider)
    provider_class = PROVIDERS[provider]
    try:
        provider_instance = provider_class(api_key=api_key)
    except ImportError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    effective_model = model or provider_instance.default_model
    logger.debug(f"Modello effettivo: {effective_model}")

    try:
        # Se web_search e' attivo e il provider supporta la Responses API,
        # usa _chat_responses_api direttamente invece del metodo chat() stateless.
        if web_search and hasattr(provider_instance, "_chat_responses_api"):
            logger.debug("Chiamata singola via Responses API (web_search attivo)")
            response, _ = provider_instance._chat_responses_api(
                prompt=prompt,
                model=effective_model,
                system=system,
                web_search=True,
            )
        else:
            response = provider_instance.chat(
                prompt=prompt,
                model=model,
                system=system,
                agent_count=agent_count,
            )
    except RuntimeError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(response.text)

    # Riga stats sempre su stderr: (3m 25s · 8.0k tokens · $0.0032)
    stats = _format_stats(response)
    if stats:
        print(stats, file=sys.stderr)

    if verbose:
        lines = [
            "--- verbose ---",
            f"Provider:  {provider}",
            f"Modello:   {response.model_used}",
        ]
        if response.input_tokens is not None:
            lines.append(f"Token in:  {response.input_tokens}")
        if response.output_tokens is not None:
            lines.append(f"Token out: {response.output_tokens}")
        print("\n".join(lines), file=sys.stderr)
