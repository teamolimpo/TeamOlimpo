"""CLI per tools.image_gen — generazione immagini via OpenRouter API.

Usage::

    python -m tools.image_gen generate "un gatto cyberpunk" \\
        --model openai/gpt-5-image-mini --ratio 16:9
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import typer
from loguru import logger

from tools.image_gen.client import OpenRouterImageClient
from tools.image_gen.config import (
    DEFAULT_APP_NAME,
    DEFAULT_MODEL,
    DEFAULT_RATIO,
    DEFAULT_SITE_URL,
    DEFAULT_SIZE,
    VALID_RATIOS,
    VALID_SIZES,
    estimate_cost,
    estimate_resolution,
)
from tools.image_gen.image_processor import ImageProcessor

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="image_gen",
    help="Genera immagini via OpenRouter API (Gemini / GPT-5 Image / FLUX / Seedream).",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    """Configure loguru: WARNING by default, DEBUG with --verbose."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, format="<level>{level}</level>: {message}")


def _output_json(data: dict) -> None:
    """Print JSON to stdout for machine consumption."""
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _get_api_key(provided: str | None) -> str:
    """Resolve API key from argument or environment variable."""
    key = provided or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        _output_json(
            {
                "status": "fail",
                "error_type": "policy_rejection",
                "error_message": (
                    "OpenRouter API key required. Pass --api-key or set OPENROUTER_API_KEY env var."
                ),
                "model": DEFAULT_MODEL,
                "retryable": False,
            }
        )
        raise typer.Exit(code=1)
    return key


# ---------------------------------------------------------------------------
# Comandi
# ---------------------------------------------------------------------------


@app.command()
def generate(
    prompt: str = typer.Argument(
        ...,
        help="Text prompt per la generazione dell'immagine.",
    ),
    model: str = typer.Option(
        DEFAULT_MODEL,
        "--model",
        "-m",
        help="OpenRouter model ID (es. openai/gpt-5-image-mini, google/gemini-2.5-flash-image).",
    ),
    size: str = typer.Option(
        DEFAULT_SIZE,
        "--size",
        "-s",
        help=f"Risoluzione immagine: {', '.join(sorted(VALID_SIZES))}.",
    ),
    ratio: str = typer.Option(
        DEFAULT_RATIO,
        "--ratio",
        "-r",
        help=f"Aspect ratio: {', '.join(sorted(VALID_RATIOS))}.",
    ),
    output: str = typer.Option(
        "Library/deliverables/images/YYYY/MM/",
        "--output",
        "-o",
        help="Directory di output (supports YYYY, MM, DD placeholders).",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="OpenRouter API key. Default: env OPENROUTER_API_KEY.",
        envvar="OPENROUTER_API_KEY",
    ),
    site_url: str = typer.Option(
        DEFAULT_SITE_URL,
        "--site-url",
        help="HTTP-Referer header per OpenRouter.",
    ),
    app_name: str = typer.Option(
        DEFAULT_APP_NAME,
        "--app-name",
        help="X-Title header per OpenRouter.",
    ),
    input_image: str = typer.Option(
        None,
        "--input-image",
        "-i",
        help="Path per image-to-image (modelli che lo supportano).",
    ),
    negative_prompt: str = typer.Option(
        None,
        "--negative-prompt",
        "-n",
        help="Prompt negativo (modelli che lo supportano).",
    ),
    seed: int = typer.Option(
        None,
        "--seed",
        help="Seed per riproducibilità.",
    ),
    image_config_json: str = typer.Option(
        None,
        "--image-config-json",
        help="JSON extra per configurazioni avanzate dell'immagine.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simula la chiamata senza inviarla realmente (usa dati fittizi).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Output debug dettagliato su stderr.",
    ),
) -> None:
    """Genera un'immagine via OpenRouter API.

    Chiama il modello scelto su OpenRouter, decodifica l'immagine base64,
    la salva su disco, calcola l'hash CRC32 e restituisce metadati JSON.
    """
    _setup_logging(verbose)

    # Validate parameters
    valid_sizes_str = ", ".join(sorted(VALID_SIZES))
    valid_ratios_str = ", ".join(sorted(VALID_RATIOS))

    if size not in VALID_SIZES:
        _output_json(
            {
                "status": "fail",
                "error_type": "bad_request",
                "error_message": (f"Invalid size '{size}'. Valid values: {valid_sizes_str}."),
                "model": model,
                "retryable": False,
            }
        )
        raise typer.Exit(code=2) from None

    if ratio not in VALID_RATIOS:
        _output_json(
            {
                "status": "fail",
                "error_type": "bad_request",
                "error_message": (f"Invalid ratio '{ratio}'. Valid values: {valid_ratios_str}."),
                "model": model,
                "retryable": False,
            }
        )
        raise typer.Exit(code=2) from None

    # Validate input image
    if input_image and not Path(input_image).is_file():
        _output_json(
            {
                "status": "fail",
                "error_type": "bad_request",
                "error_message": f"Input image not found: {input_image}",
                "model": model,
                "retryable": False,
            }
        )
        raise typer.Exit(code=2) from None

    logger.debug(f"Model: {model}, Size: {size}, Ratio: {ratio}")
    logger.debug(f"Output dir: {output}")

    # DRY RUN mode — skip API key requirement
    if dry_run:
        logger.info("DRY RUN — simulating image generation")
        output_dir = ImageProcessor.resolve_output_dir(output)
        slug = __import__("tools.image_gen.image_processor", fromlist=["slugify"]).slugify(prompt)
        mock_hash = "deadbeef"
        mock_path = output_dir / f"{slug}-{mock_hash}.png"
        est_cost = estimate_cost(model, size)
        est_res = estimate_resolution(size, ratio)

        _output_json(
            {
                "status": "success",
                "path": str(mock_path),
                "cost": est_cost,
                "model": model,
                "hash": mock_hash,
                "size_bytes": 0,
                "resolution": f"{est_res[0]}x{est_res[1]}",
                "generation_time_s": 0.0,
                "dry_run": True,
            }
        )
        return

    # Resolve output directory
    output_dir = ImageProcessor.resolve_output_dir(output)
    logger.debug(f"Output directory resolved: {output_dir}")

    # Resolve API key (needed for real calls, not dry-run)
    key = _get_api_key(api_key)

    # API call
    start_time = time.monotonic()

    try:
        with OpenRouterImageClient(
            api_key=key,
            site_url=site_url,
            app_name=app_name,
        ) as client:
            result = client.generate(
                prompt=prompt,
                model=model,
                size=size,
                ratio=ratio,
                input_image_path=input_image,
                negative_prompt=negative_prompt,
                seed=seed,
                image_config_json=image_config_json,
            )
    except Exception as exc:
        _output_json(
            {
                "status": "fail",
                "error_type": "generic",
                "error_message": f"Unexpected error: {exc}",
                "model": model,
                "retryable": False,
            }
        )
        raise typer.Exit(code=1) from exc

    elapsed = time.monotonic() - start_time

    # Handle API error
    if not result.success:
        _output_json(
            {
                "status": "fail",
                "error_type": result.error_type or "generic",
                "error_message": result.error_message,
                "model": model,
                "retryable": result.retryable,
                "generation_time_s": round(result.generation_time_s, 2),
            }
        )
        raise typer.Exit(code=1 if not result.retryable else 0) from None

    # No image data
    if not result.image_base64:
        _output_json(
            {
                "status": "fail",
                "error_type": "generic",
                "error_message": "No image data returned from API",
                "model": model,
                "retryable": False,
                "generation_time_s": round(elapsed, 2),
            }
        )
        raise typer.Exit(code=1) from None

    resolution = f"{estimate_resolution(size, ratio)[0]}x{estimate_resolution(size, ratio)[1]}"

    # Process and save image
    try:
        validator = ImageProcessor(base_dir=output_dir)
        save_result = validator.save_image(
            base64_data=result.image_base64,
            prompt=prompt,
            mime_type=result.mime_type or "image/png",
            resolution=resolution,
        )
    except Exception as exc:
        # Fallback: try fallback directory
        logger.warning(f"Failed to save to primary dir, trying fallback: {exc}")
        try:
            fallback_dir = ImageProcessor.resolve_output_dir(None)
            validator = ImageProcessor(base_dir=fallback_dir)
            save_result = validator.save_image(
                base64_data=result.image_base64,
                prompt=prompt,
                mime_type=result.mime_type or "image/png",
                resolution=resolution,
            )
            logger.info(f"Saved to fallback directory: {fallback_dir}")
        except Exception as fallback_exc:
            _output_json(
                {
                    "status": "fail",
                    "error_type": "generic",
                    "error_message": f"Failed to save image: {fallback_exc}",
                    "model": model,
                    "retryable": False,
                }
            )
            raise typer.Exit(code=1) from fallback_exc

    # Success output
    _output_json(
        {
            "status": "success",
            "path": save_result["path"],
            "cost": round(result.cost, 6),
            "model": model,
            "hash": save_result["hash"],
            "size_bytes": save_result["size_bytes"],
            "resolution": save_result["resolution"],
            "generation_time_s": round(elapsed, 2),
        }
    )


# ---------------------------------------------------------------------------
# List models command
# ---------------------------------------------------------------------------


@app.command()
def list_models(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Mostra dettagli completi dei modelli.",
    ),
) -> None:
    """Elenca i modelli supportati con prezzi e caratteristiche."""
    _setup_logging(verbose)

    from tools.image_gen.config import MODEL_PRICES

    rows = []
    for mid, cfg in sorted(MODEL_PRICES.items()):
        name = cfg.get("name", mid.split("/")[-1])
        price_info = cfg.get("per", "?")
        if cfg["type"] == "token":
            if cfg.get("special") == "priced_per_token":
                price_str = f"${cfg['total']}/{price_info}"
            else:
                price_str = f"in:${cfg['input']} out:${cfg['output']}/{price_info}"
        elif cfg["type"] == "mp":
            if "per_mp" in cfg:
                price_str = f"${cfg['per_mp']}/MP"
            elif "first_mp" in cfg:
                price_str = f"${cfg['first_mp']}/first + ${cfg['subsequent_mp']}/subseq MP"
            else:
                price_str = f"in:${cfg['input_per_mp']} out:${cfg['output_per_mp']}/MP"
        elif cfg["type"] == "fixed":
            price_str = f"${cfg['per_image']}/image"
        else:
            price_str = "?"

        if verbose:
            rows.append(f"  {mid:50s}  {name:30s}  {price_str}")
        else:
            rows.append(f"  {mid:50s}  {price_str}")

    typer.echo("Modelli supportati da image_gen:\n")
    for row in rows:
        typer.echo(row)
    typer.echo(f"\nTotale: {len(rows)} modelli")


if __name__ == "__main__":
    app()
