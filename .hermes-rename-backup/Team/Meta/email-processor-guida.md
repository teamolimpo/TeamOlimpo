# Guida email_processor

## Descrizione
Tool per importazione, elaborazione e catalogazione email in vault Obsidian del Team Olimpo.

## Comandi
- `import`: Importa email .eml da percorso configurato e genera note Markdown in Inbox/emails/.
- `elabora`: Elabora email con analisi AI (sintesi, azioni richieste, etc.).
- `status`: Mostra stato del vault email (conteggi, ultime elaborate).

## Configurazione (variabili d'ambiente)
- `EMAIL_DIR` — percorso email .eml sorgente (default: `/mnt/hgfs/Emails/inbox`)
- `EMAIL_VAULT_ROOT` — percorso vault destinazione (default: `/home/stra/TeamOlimpo/vaults/email/`)
- Output note: `Inbox/emails/` dentro il vault

## Uso
```bash
uv run python -m tools.email_processor --help
uv run python -m tools.email_processor import --limit 10
uv run python -m tools.email_processor elabora
uv run python -m tools.email_processor status
```

## TODO
- Implementare logica di importazione completa
- Implementare elaborazione AI
- Implementare status