# Git Quick Reference — Team Olimpo

Comandi usati per diagnosticare e sistemare il repo dopo il primo push.

## Stato e tracking

```bash
# Stato working tree (compatto)
git status --short

# Stato completo
git status

# Diff riepilogativo
git diff --stat

# Diff completo
git diff

# Diff dello staging (ciò che sarà committato)
git diff --cached --stat
```

## Cosa è tracciato

```bash
# Lista completa dei file tracciati
git ls-files

# Controllare se un file specifico è tracciato
git ls-files uv.lock
git ls-files lib/

# File "ignorati ma tracciati" (dovrebbe essere vuoto)
git ls-files --cached --ignored --exclude-standard

# Symlink tracciati (mode 120000)
git ls-files -s | grep "^120000"
```

## Storico

```bash
# Ultimi commit
git log --oneline -5

# Reflog (cronologia operazioni locali)
git reflog -5
```

## Operazioni comuni

```bash
# Rimuovere un file dal tracking (senza cancellarlo dal disco)
git rm --cached <file>

# Staging selettivo
git add <file>

# Commit
git commit -m "messaggio"

# Push
git push
```
