---
title: Quality Gate — Validazione Output
tags: [meta, workflow, quality, team, aqf]
aliases: [quality gate, validazione output, gate output, aqf quality gate]
date: 2026-05-16
---

# Quality Gate — Validazione Output

Checklist rapida per validare l'output di un subagent **prima** della consegna all'utente. Parte del framework AQF (fase AOQ). Tempo target: **≤ 2 minuti**.

---

## Quando si applica

- **Prima** di consegnare qualsiasi output all'utente finale
- **Prima** di dichiarare un task "completato" nel flusso
- Sempre per task ad **alto rischio** (script in produzione, ricerca citata in decisioni, documentazione utente)

> [!important]
> Il quality gate è responsabilità di **Poros**. Non delegare la validazione finale — il subagent produce, Poros verifica.

---

## Procedura rapida (2 minuti)

### 1. Completezza — 30s

- [ ] L'output copre **tutti** i punti richiesti nel briefing Poros?
- [ ] Se manca qualcosa: è **documentato come limite/esclusione** nell'output?
- [ ] Se richiedeva fonti: sono tutte presenti? (non "approfondisci dopo" se il briefing chiedeva completezza)

### 2. Accuratezza — 30s

- [ ] A lettura rapida, il contenuto **ha senso logico**? Nessuna contraddizione interna evidente?
- [ ] Se ricerca: le **fonti citate** esistono? I link funzionano? Sono fonti affidabili (es. documentazione ufficiale, non blog anonimi)?
- [ ] Se script: è testabile? I comandi forniti funzionano su un sistema pulito?

### 3. Formattazione — 30s

| Elemento | Cosa verificare |
|----------|-----------------|
| **Frontmatter** | Presente? `tags` e `aliases` plurali? Data corretta? |
| **Wikilink** | Link interni usano `[[nota]]`, non `[nota](../percorso/nota.md)`? |
| **Immagini** | Path relativi al file `.md` (`../assets/images/...`), non assoluti? |
| **Callout** | Sintassi valida `> [!TIPO]`? |
| **Lunghezza** | Troppo lungo per una lettura rapida? Va spezzato in sottopagine? |

### 4. Decisione — 30s

| Esito | Azione |
|-------|--------|
| ✅ **PASS** | Consegna all'utente. Nessuna nota aggiuntiva. |
| ⚠️ **WARN** | Consegna all'utente, ma **allega nota esplicita** sui limiti noti (cosa manca, cosa non è stato verificato, rischi). |
| ❌ **FAIL** | Rimanda al mittente con feedback strutturato (vedi sotto). Non consegnare. |

---

## Feedback strutturato (se FAIL)

Template per il rimando al subagent:

```
Output non conforme: [task_id / breve descrizione]

Cosa non va:
1. [elemento specifico 1]
2. [elemento specifico 2]

Dove:
- [file:riga o posizione]

Cosa mi aspettavo:
- [criterio violato]

Riferimento:
- [link a convenzione / documento / briefing]
```

> [!tip]
> Sii preciso nel feedback. "Riscrivi tutto" non aiuta. "La sezione X non copre il punto Y del briefing" sì.

---

## Esempi

### ✅ PASS

**Scenario**: Proteo produce un report di ricerca su "architettura DeltaV".

```
Output: research/deltav-arch-report.md

Verifica:
1. Completezza ✅ — copre tutti e 5 i punti del briefing (architettura, moduli, API, sicurezza, costi). Limiti dichiarati: "non copre deployment on-prem perché fuori scope".
2. Accuratezza ✅ — logica coerente, fonti citate: documentazione ufficiale DeltaV e 3 paper revisionati. Link verificati funzionanti.
3. Formattazione ✅ — frontmatter presente (tags: [deltav, research]), wikilink [[documento-di-riferimento]] corretti, immagini in ../assets/images/deltav-arch/.

Decisione: ✅ PASS → consegna a Poros per inoltro utente.
```

### ❌ FAIL

**Scenario**: Efesto produce uno script Python "convertitore CSV → JSON".

```
Output: tools/csv2json/cli.py

Verifica:
1. Completezza ❌ — il briefing chiedeva: flag --verbose, logging su stderr, errore su file inesistente. Manca la gestione errore su file inesistente.
2. Accuratezza ✅ — logica corretta, testabile.
3. Formattazione ⚠️ — frontmestone non applicabile (non è .md). Ma manca docstring nel modulo.

Decisione: ❌ FAIL

Feedback:
Output non conforme: csv2json cli.py
Cosa non va: manca gestione errore su file input inesistente
Dove: cli.py — funzione main() non ha try/except su open()
Cosa mi aspettavo: se il file non esiste, script deve uscire con exit code 1 e messaggio su stderr
Riferimento: standard-programmazione-python.md #gestione-errori
```

---

## Riferimenti

- [[aqf-framework]] — Framework AQF completo (se presente)
- [[standard-programmazione-python]] — Convenzioni Python per script Efesto
- [[obsidian-vault]] — Convenzioni vault (frontmatter, wikilink, immagini)
- [[handoff-guida]] — Gestione handoff tra membri
