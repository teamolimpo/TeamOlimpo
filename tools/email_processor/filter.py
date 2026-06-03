"""Layer 2 — Runtime Engine: classifica email in base a regole YAML.

Questo modulo implementa il motore di classificazione delle email
basato su regole definite in ``filter_rules.yaml``.

Tipico utilizzo:
    >>> engine = RuleEngine(rules_path / "filter_rules.yaml")
    >>> result = engine.classify({"subject": "...", "from": "...", "body": "..."})
    >>> if result.action == "discard":
    ...     # skip import
    ...     pass
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Risultato della classificazione di una email.

    Attributes:
        action: Azione da eseguire (``"discard"`` | ``"aggregate"`` | ``"keep"``
            | ``"fallback"``).
        rule_id: Identificativo della regola che ha matchato
            (``"__fallback__"`` per fallback).
        label: Etichetta opzionale per la classificazione.
        aggregate_to: Path template per l'aggregazione (solo se
            ``action == "aggregate"``).
        flag: Flag opzionale (es. ``"unchecked"`` per fallback).
    """

    action: str
    rule_id: str
    label: str | None = None
    aggregate_to: str | None = None
    flag: str | None = None


# ---------------------------------------------------------------------------
# Rule Engine
# ---------------------------------------------------------------------------


class RuleEngine:
    """Motore di classificazione basato su regole YAML.

    Carica regole da ``filter_rules.yaml``, le ordina per priorità
    decrescente, e classifica le email con first-match-wins.

    Args:
        rules_path: Percorso del file YAML con le regole. Se ``None``,
            nessuna regola caricata (tutte fallback).
    """

    # Operatori supportati per campo
    _SUPPORTED_OPS = {
        "contains",
        "starts_with",
        "ends_with",
        "contains_regex",
        "not_contains",
    }

    def __init__(self, rules_path: Path | None = None) -> None:
        self.rules: list[dict] = []
        self._sorted_rules: list[dict] = []

        if rules_path is not None:
            self.load_rules(rules_path)

    # ------------------------------------------------------------------
    # Caricamento regole
    # ------------------------------------------------------------------

    def load_rules(self, path: Path) -> None:
        """Carica le regole da un file YAML.

        Valida la struttura, ordina per priority decrescente.

        Args:
            path: Percorso del file YAML.

        Raises:
            FileNotFoundError: Se il file non esiste.
            ValueError: Se la struttura YAML non è valida.
        """
        if not path.exists():
            raise FileNotFoundError(f"File regole non trovato: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Struttura YAML non valida in {path}: atteso dict")

        version = data.get("version", 1)
        raw_rules = data.get("rules", [])

        if not isinstance(raw_rules, list):
            raise ValueError("'rules' deve essere una lista")

        # Valida ogni regola
        validated: list[dict] = []
        for i, rule in enumerate(raw_rules):
            if not isinstance(rule, dict):
                logger.warning(f"Regola {i}: saltata (non dict): {rule}")
                continue

            rule_id = rule.get("id", f"rule-{i}")
            action = rule.get("action")

            if action not in ("discard", "aggregate", "keep"):
                logger.warning(f"Regola {rule_id}: action '{action}' non valida, saltata")
                continue

            if "match" not in rule or not isinstance(rule["match"], dict):
                logger.warning(f"Regola {rule_id}: match mancante o non dict, saltata")
                continue

            if action == "aggregate" and not rule.get("aggregate_to"):
                logger.warning(f"Regola {rule_id}: action='aggregate' ma aggregate_to mancante")
                continue

            # Default priority
            rule.setdefault("priority", 50)

            # Validazione operatori
            for field, conditions in rule["match"].items():
                if not isinstance(conditions, dict):
                    logger.warning(f"Regola {rule_id}: match.{field} non è un dict, saltata")
                    continue
                for op in conditions:
                    if op not in self._SUPPORTED_OPS:
                        logger.warning(
                            f"Regola {rule_id}: operatore '{op}' non supportato in match.{field}"
                        )

            validated.append(rule)

        # Ordina per priority decrescente
        validated.sort(key=lambda r: r.get("priority", 0), reverse=True)

        self.rules = raw_rules
        self._sorted_rules = validated

        logger.info(
            f"Regole caricate: {len(validated)}/{len(raw_rules)} valide (versione {version})"
        )

    # ------------------------------------------------------------------
    # Classificazione
    # ------------------------------------------------------------------

    def classify(self, email_data: dict) -> ClassificationResult:
        """Classifica un'email applicando le regole in ordine di priorità.

        First-match-wins: restituisce la prima regola che matcha.
        Se nessuna regola matcha, restituisce fallback (keep + flag:unchecked).

        Args:
            email_data: Dict con i dati dell'email. Deve contenere almeno
                ``subject`` e ``from``. Può contenere ``body`` e ``to``.

        Returns:
            :class:`ClassificationResult` con l'azione decisa.
        """
        for rule in self._sorted_rules:
            if self._match_rule(email_data, rule):
                logger.debug(
                    f"Match regola {rule['id']}: "
                    f"action={rule['action']}, subject={email_data.get('subject', '')[:60]}"
                )
                return ClassificationResult(
                    action=rule["action"],
                    rule_id=rule["id"],
                    label=rule.get("label"),
                    aggregate_to=rule.get("aggregate_to"),
                    flag=rule.get("flag"),
                )

        # Fallback: nessuna regola matchata
        logger.debug(f"Nessuna regola matchata per subject: {email_data.get('subject', '')[:60]}")
        return ClassificationResult(
            action="keep",
            rule_id="__fallback__",
            flag="unchecked",
        )

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _match_rule(self, email_data: dict, rule: dict) -> bool:
        """Verifica se un'email matcha una regola.

        Più campi = AND: TUTTI i campi devono matchare.
        Più valori stesso campo = OR: almeno UN valore deve matchare.

        Args:
            email_data: Dict con i dati dell'email.
            rule: Dict regola con sezione ``match``.

        Returns:
            ``True`` se l'email matcha la regola.
        """
        match_section = rule.get("match", {})
        if not match_section:
            return False

        for field, conditions in match_section.items():
            # Ottieni il valore dall'email data (supporta subject, from, body, to)
            field_value = self._get_field_value(email_data, field)
            if field_value is None:
                # Campo non presente → non matcha
                return False

            if not self._match_field(field_value, conditions):
                return False

        return True

    def _get_field_value(self, email_data: dict, field: str) -> str | None:
        """Ottiene il valore di un campo dall'email data.

        Supporta: ``subject``, ``from``, ``body``, ``to``.
        Per ``from`` restituisce il nome+email completo.
        Per ``to`` restituisce gli indirizzi concatenati.

        Args:
            email_data: Dict con i dati dell'email.
            field: Nome del campo richiesto.

        Returns:
            Valore stringa o ``None`` se campo non trovato.
        """
        if field in email_data:
            val = email_data[field]
            if isinstance(val, str):
                return val.lower() if val else None
            if isinstance(val, list):
                # Per campi lista (to, cc), concatena
                combined = " ".join(str(v) for v in val)
                return combined.lower() if combined else None
            return None

        # Campi speciali
        if field == "to":
            to_vals = email_data.get("to", [])
            if isinstance(to_vals, list):
                combined = " ".join(str(v) for v in to_vals)
                return combined.lower() if combined else None
            return str(to_vals).lower() if to_vals else None

        return None

    def _match_field(self, field_value: str, conditions: dict) -> bool:
        """Applica le condizioni di match su un singolo campo.

        Più operatori sullo stesso campo = AND (tutti devono passare).
        Più valori nello stesso operatore = OR (almeno uno passa).

        Args:
            field_value: Valore del campo (già lowercase).
            conditions: Dict operatore → lista di pattern.

        Returns:
            ``True`` se il campo soddisfa tutte le condizioni.
        """
        for operator, patterns in conditions.items():
            if not isinstance(patterns, list):
                patterns = [patterns]

            result = self._apply_operator(field_value, operator, patterns)
            if not result:
                return False

        return True

    def _apply_operator(
        self,
        field_value: str,
        operator: str,
        patterns: list,
    ) -> bool:
        """Applica un singolo operatore di match.

        Args:
            field_value: Valore del campo (lowercase).
            operator: Nome dell'operatore.
            patterns: Lista di pattern (stringhe regex o testuali).

        Returns:
            ``True`` se almeno un pattern matcha.
        """
        for pattern in patterns:
            pattern_str = str(pattern).lower()

            try:
                if operator == "contains":
                    if pattern_str.lower() in field_value.lower():
                        return True

                elif operator == "starts_with":
                    if field_value.startswith(pattern_str):
                        return True

                elif operator == "ends_with":
                    if field_value.endswith(pattern_str):
                        return True

                elif operator == "contains_regex":
                    if re.search(pattern_str, field_value):
                        return True

                elif operator == "not_contains":
                    if pattern_str.lower() not in field_value.lower():
                        return True

                else:
                    logger.warning(f"Operatore sconosciuto: {operator}")

            except re.error as e:
                logger.warning(f"Regex non valida ({pattern_str}): {e}")
                continue

        return False
