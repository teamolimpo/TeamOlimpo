"""
Tool kba_pipeline — orchestratore della pipeline KBA del Team Olimpo.

Chiama in sequenza:
  1. pdf_converter  — converte i PDF nuovi in Markdown
  2. kba_indexer    — analizza con AI e indicizza nel catalogo
  3. kba_resolver   — verifica le dipendenze documentali
  4. kba_merger     — merge + enrichment e produzione Excel finale
"""

__version__ = "0.1.0"
