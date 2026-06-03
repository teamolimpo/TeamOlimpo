---
title: "ACM Report Template — Agent Continuous Monitoring"
aliases: [acm, monitoraggio, report-settimanale, metriche, quality-tracking]
tags: [meta, workflow, quality, acm, monitoring, report]
---

# ACM Report Template — Agent Continuous Monitoring

## Cos'è

L'**ACM (Agent Continuous Monitoring)** è il processo settimanale di Dike per tracciare le performance dei membri del Team Olimpo. Il report ACM è uno strumento di **osservazione operativa**, non di giudizio — serve a identificare pattern, tendenze e aree di miglioramento.

Il report viene generato **ogni settimana** (tipicamente il lunedì) e comprende:
- Analisi delle deviazioni della settimana precedente
- Calcolo del deviation rate per membro
- Quality score medio per membro
- Trend di performance
- Raccomandazioni per Hermes

---

## Struttura del report

```markdown
---
title: "ACM Report — Settimana XX"
data: 2026-MM-DD
settimana: "YYYY-WW"
autore: dike
tags: [acm, report, quality]
---

# ACM Report — Settimana [XX]

**Periodo**: [data inizio] — [data fine]
**Generato**: [data generazione]
**Autore**: Dike

---

## Riepilogo settimanale

| Metrica | Valore |
|---------|--------|
| Totale handoff processati | N |
| Handoff completati | N |
| Deviazioni totali | N |
| Deviation rate medio | X% |
| Quality score medio | X.X |

---

## Dettaglio per membro

### [Nome membro 1]

| Metrica | Valore |
|---------|--------|
| Handoff processati | N |
| Deviazioni | N |
| Deviation rate | X% |
| Quality score medio | X.X |
| Trend | [miglioramento / stabile / deterioramento] |

**Note**: [Eventuali note o allarmi]

---

### [Nome membro 2]

| Metrica | Valore |
|---------|--------|
| Handoff processati | N |
| Deviazioni | N |
| Deviation rate | X% |
| Quality score medio | X.X |
| Trend | [miglioramento / stabile / deterioramento] |

**Note**: [Eventuali note o allarmi]

---

[... ripetere per ogni membro attivo]

---

## Alert e segnalazioni

### Deviation rate > 20% (Giallo)

| Membro | Deviation rate | Tipo deviazioni prevalente |
|--------|---------------|---------------------------|
| [Nome] | X% | [tipo1, tipo2] |

### Deviation rate > 40% (Rosso)

| Membro | Deviation rate | Tipo deviazioni prevalente |
|--------|---------------|---------------------------|
| [Nome] | X% | [tipo1, tipo2] |

---

## Raccomandazioni per Hermes

1. **[Priorità alta]** [Raccomandazione 1]
2. **[Priorità media]** [Raccomandazione 2]
3. **[Priorità bassa]** [Raccomandazione 3]

---

## Note operative

[Note aggiuntive sulla metodologia, fonti dati, eccezioni]

---
```

---

## Definizioni delle metriche

### Deviation Rate

```
Deviation Rate = (Deviazioni / Handoff processati) * 100
```

Esempio: 3 deviazioni su 10 handoff → 30%

| Soglia | Livello | Colore |
|--------|---------|--------|
| 0-10% | Normale | — |
| 11-20% | Attenzione | Giallo |
| 21-40% | Allarme | Arancione |
| >40% | Critico | Rosso |

### Quality Score Medio

```
Quality Score Medio = Somma quality_score / Numero handoff completati
```

Arrotondato a 1 decimale.

### Trend

| Trend | Criterio |
|-------|----------|
| **miglioramento** | Quality score medio +0.5+ rispetto alla settimana precedente, deviation rate in calo |
| **stabile** | Variazione contenuta (<0.5 quality score, <5% deviation rate) |
| **deterioramento** | Quality score medio -0.5- rispetto alla settimana precedente, deviation rate in aumento |

---

## Esempio compilato

```markdown
---
title: "ACM Report — Settimana 20"
data: 2026-05-16
settimana: "2026-W20"
autore: dike
tags: [acm, report, quality]
---

# ACM Report — Settimana 20

**Periodo**: 2026-05-09 — 2026-05-15
**Generato**: 2026-05-16
**Autore**: Dike

---

## Riepilogo settimanale

| Metrica | Valore |
|---------|--------|
| Totale handoff processati | 12 |
| Handoff completati | 10 |
| Deviazioni totali | 3 |
| Deviation rate medio | 25% |
| Quality score medio | 3.8 |

---

## Dettaglio per membro

### Clio

| Metrica | Valore |
|---------|--------|
| Handoff processati | 4 |
| Deviazioni | 1 |
| Deviation rate | 25% |
| Quality score medio | 3.5 |
| Trend | stabile |

**Note**: Una deviazione di tipo `tool_failure` per converter PDF. Workaround applicato. Da monitorare.

---

### Efesto

| Metrica | Valore |
|---------|--------|
| Handoff processati | 3 |
| Deviazioni | 0 |
| Deviation rate | 0% |
| Quality score medio | 4.2 |
| Trend | miglioramento |

**Note**: Nessuna deviazione. Qualità in aumento rispetto alla settimana scorsa.

---

### Proteo

| Metrica | Valore |
|---------|--------|
| Handoff processati | 2 |
| Deviazioni | 1 |
| Deviation rate | 50% |
| Quality score medio | 3.0 |
| Trend | deterioramento |

**Note**: Deviazione di tipo `output_incompleto`. Problema con parsing di fonti web. Richiede supporto.

---

### Atena

| Metrica | Valore |
|---------|--------|
| Handoff processati | 2 |
| Deviazioni | 1 |
| Deviation rate | 50% |
| Quality score medio | 4.0 |
| Trend | stabile |

**Note**: Deviazione di tipo `timeout` su generazione profilo complesso. Workaround applicato.

---

### Hermes

| Metrica | Valore |
|---------|--------|
| Handoff processati | 1 |
| Deviazioni | 0 |
| Deviation rate | 0% |
| Quality score medio | 5.0 |
| Trend | stabile |

**Note**: Non applicabile — coordinamento generale.

---

## Alert e segnalazioni

### Deviation rate > 20% (Giallo)

| Membro | Deviation rate | Tipo deviazioni prevalente |
|--------|---------------|---------------------------|
| Clio | 25% | tool_failure |

### Deviation rate > 40% (Rosso)

| Membro | Deviation rate | Tipo deviazioni prevalente |
|--------|---------------|---------------------------|
| Proteo | 50% | output_incompleto |
| Atena | 50% | timeout |

---

## Raccomandazioni per Hermes

1. **[Priorità alta]** Intervenire su Proteo: la deviazione `output_incompleto` ricorrente indica possibile gap nelle capacità di parsing web. Valutare aggiornamento competenze o strumenti.

2. **[Priorità media]** Investigare timeout Atena: profili complessi richiedono troppo tempo. Verificare se ottimizzazione tool o aumento timeout configurabile.

3. **[Priorità bassa]** Clio: monitorare la situazione converter. La deviazione è stata risolta con workaround, ma potrebbe ripresentarsi con altri file.

---

## Note operative

- Settimana parziale (5 giorni lavorativi)
- Dati estratti da frontmatter handoff in `Team/Handoff/`
- Deviazioni contate solo su handoff con `stato: completato` o `bloccato`
- Quality score disponibile solo su handoff completati

---
```

---

## Metodologia di raccolta dati

### Fonti dati

1. **Team/Handoff/** — Frontmatter degli handoff
2. **Team/Handoff/Registro.md** — Indice aggregato
3. **Deviazioni** — Campo `deviazione` nel frontmatter

### Frequenza

- **Report settimanale**: Lunedì mattina, copre la settimana precedente (lun-dom)
- **Report mensile**: Primo lunedì del mese, aggregato mensile

### Eccezioni

- Se un membro non ha handoff nella settimana, viene escluso dal report
- Se un membro è nuovo (< 2 settimane), il trend è "N/A"

---

## Integrazione con altri strumenti

- [[handoff-guida]] — Per la struttura degli handoff
- [[deviation-log-guida]] — Per la definizione delle deviazioni
- [[oq-recovery-template]] — Per la verifica post-blocco
- [[handoff-register-guida]] — Per l'automazione del Registro

---

## Limitazioni

- L'ACM è uno strumento di **osservazione**, non di valutazione individuale
- Deviation rate alto non implica necessariamente incompetence — potrebbe indicare complessità dei task
- Quality score è soggettivo e riflette il giudizio del destinatario dell'handoff
- L'ACM non sostituisce la review operativa di Hermes