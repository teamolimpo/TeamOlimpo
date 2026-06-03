---
data: 2026-05-12
mittente: efesto
destinatario: team
tipo: documentazione
stato: completato
priorita: alta
titolo: "Guida Tool Automation Video IA"
tags: [automazione, ia, video, keraunos]
aliases: [automation_video_ia_guida]
---

# Guida Tool Automation Video IA

## Panoramica

Il tool `automation_video_ia` implementa il sistema **Keraunos** per automazione completa di contenuti video IA, basato sui template di Calliope e sui report di Proteo/Metis.

- **Funzionalità**: Workflow settimanale da trend detection a pubblicazione automatica.
- **Minimizzazione intervento umano**: Tutto automatico tranne setup iniziale.
- **Gestione errori**: Error handling, logging con loguru.
- **Tecnologie**: Typer CLI, pydantic per modelli, placeholder per API reali.

## Installazione

```bash
cd /home/stra/TeamOlimpo
uv add pytrends  # già aggiunto
uv run python -m tools.automation_video_ia --help
```

## Uso

### Comando principale

```bash
uv run python -m tools.automation_video_ia run-weekly --verbose
```

Esegue il workflow completo:
1. Rileva trend (Google Trends placeholder).
2. Genera script usando prompt Keraunos (LLM placeholder).
3. Crea video con avatar (API HeyGen placeholder).
4. Pubblica su YouTube/TikTok (API placeholder).

### Opzioni

- `--output-dir`: Directory per output (default: lib/deliverables).
- `--verbose`: Logging debug.

## Architettura

- **Modelli**: TrendData, ScriptData, VideoData con pydantic.
- **Workflow**: Funzioni modulari per ogni fase.
- **Logging**: Loguru su stderr.
- **Error handling**: Try/except con exit code appropriato.

## Placeholder API

Dato che API reali (Exploding Topics, HeyGen, YouTube) richiedono chiavi e costi, sono implementate come placeholder con dati dummy. Per produzione:
- Sostituisci `_get_trends()` con pytrends o Exploding Topics API.
- `_generate_script()` con Claude/OpenAI API usando prompt Keraunos.
- `_create_video()` con HeyGen/Creatify API.
- `_publish_video()` con YouTube Data API v3 o TikTok API.

## Test base

Crea `tests/test_automation_video_ia.py`:

```python
from tools.automation_video_ia.cli import app

def test_run_weekly():
    # Mock API calls
    # Test workflow
    pass
```

Esegui con `uv run pytest`.

## Limitazioni prototipo

- API placeholder: non funzionale senza chiavi reali.
- 1 video/settimana: scheduling manuale, non automatico.
- Quality gate: implementato base, espandibile con LLM eval.

## Estensioni future

- Integrazione scheduling con `schedule` per esecuzione settimanale automatica.
- Dashboard performance con Metis feedback loop.
- Multi-formato per diverse piattaforme.

## Riferimenti

- Sistema Keraunos: Team/Handoff/2026-05-12_calliope-prompt-system.md
- Report Proteo: Team/Handoff/2026-05-12_proteo-team_report_strategia-ia-2026.md
- Analisi Metis: Team/Handoff/2026-05-12_metis-analisi-strategia-ia.md