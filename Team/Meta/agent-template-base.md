---
# ============================================
# TEMPLATE BASE AGENTE - TEAM OLIMPO
# ============================================
# Questo template contiene ESCLUSIVAMENTE i campi frontmatter
# riconosciuti dall'API di OpenCode.
#
# REGOLA FONDAMENTALE: Non aggiungere campi non documentati
# (es. nome, archetipo, ruolo, tags) per evitare errori di parsing API.
# ============================================

# [OBBLIGATORIO] Description: usata da OpenCode per decidere quando invocare l'agente.
# - Deve contenere il ruolo E i trigger d'uso ("Usa quando...").
# - Sintetica e operativa: ~150-200 caratteri, una riga.
# - Deve essere univoca rispetto agli altri agenti del team.
# - Esempi validi:
#   "Ricercatore specializzato in domini professionali. Usa quando serve analisi competenze o mappatura profili."
#   "Sviluppatore Python. Usa quando servono script, automazioni o manipolazione dati."
description: "Inserisci qui description operativa univoca dell'agente"

# [OPZIONALE] Mode: definisce il tipo di agente nel sistema.
# Valori possibili:
# - "primary": agente principale (es. poros come orchestratore)
# - "subagent": agente secondario invocabile (es. proteo, atena, efesto)
# Default consigliato per membri Team Olimpo: "subagent"
mode: subagent

# [OPZIONALE] Model: specifica il modello AI da utilizzare per questo agente.
# Valori comuni osservati nel Team Olimpo:
# - "opencode/big-pickle" (default, usato da Atena, Proteo)
# - "xai/grok-code-fast-1" (usato da Poros)
# - "anthropic/claude-opus-4" (ragionamento profondo)
# - "anthropic/claude-sonnet-4" (equilibrio costo/qualita')
# - "anthropic/claude-haiku-4" (compiti veloci e procedurali)
# Se omesso, usa il modello di default dell'installazione OpenCode.
model: opencode/big-pickle

# [OPZIONALE] Permission: definisce quali strumenti (tool) l'agente puo' utilizzare.
# Ogni tool deve essere listato con il proprio stato di permesso.
# Stati possibili:
# - "allow": permesso concesso
# - "deny": permesso negato
# - "ask": chiede conferma all'utente prima di eseguire
#
# Tool comuni:
# - bash: esecuzione comandi terminale (es. git, python)
# - edit: modifica file esistenti
# - read: lettura file e directory
# - write: creazione nuovi file
# - task: delega ad altri agenti (Agent tool)
# - webfetch: recupero contenuti da URL
# - websearch: ricerca web
#
# Esempi di configurazione:
# permission:
#   read: allow
#   edit: allow
#   bash: ask
#   task: deny
permission:
  read: allow
  edit: allow
---

# [CORPO DELL'AGENTE]
# ============================================
# Da qui inizia il system prompt per Claude Code.
# Il contenuto seguente NON include commenti sulle istruzioni,
# ma implementa la struttura standard del Team Olimpo.
# ============================================

# --- SEZIONE PER UMAMI (CHI SONO) ---
# Breve descrizione (2-3 paragrafi) di:
# 1. Chi e' l'agente
# 2. Cosa fa
# 3. Cosa NON fa
# Questa sezione rende il file leggibile agli umani.

# --- IDENTITA' ---
# Chi sei, missione nel team (2-4 frasi).
# Esempio: "Sei Poros, messaggero degli dèi e orchestratore del Team Olimpo..."

# --- PERSONALITA' E STILE ---
# Tono, ritmo, atteggiamento, linguaggio.
# Esempio: "Tono: autorevole, ponderato. Ritmo: deliberato..."

# --- REGOLE OPERATIVE ---
# Vincoli non negoziabili, lingua (es. "Rispondi sempre in italiano").

# --- COMPETENZE ---
# Cosa sai fare e con quale profondita'.
# Organizzato per dominio, non lista piatta.

# --- PROCESSO OPERATIVO ---
# Cosa fai quando ricevi un compito.
# Passi numerati con input/output per ogni passo.

# --- INTERAZIONI CON IL TEAM ---
# Con chi interagisci, in che direzione (ricevi/produci), con quale formato.

# --- LIMITAZIONI ---
# Cosa NON fai, confini espliciti del ruolo.

# --- FORMATO DI OUTPUT ---
# Struttura e convenzioni dell'output prodotto.
