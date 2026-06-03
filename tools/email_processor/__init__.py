"""Tool per importazione, elaborazione e catalogazione email in vault Obsidian.

Nuovo in 0.8.0:
- ``rules trust`` subcommand: --suggest, --add, --list per mittenti trusted

Nuovo in 0.7.0:
- Discovery Tool riscritto: output YAML strutturato, zero interattivo
- ``rules`` command group: add, remove, list, show, apply, save
- Nuova normalizzazione con placeholder ``{device}``, ``{date}``, ``{num}``
- ``infer_rule_from_pattern()`` per creazione automatica regole
"""

__version__ = "0.8.0"
