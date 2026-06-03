"""Layer 2 — Aggregator: compatta email simili in riepiloghi giornalieri.

Questo modulo implementa il sistema di aggregazione per email a basso
valore informativo (alert Zabbix, notifiche backup, warning hardware).
Invece di importare ogni email singolarmente, le raggruppa in file
di riepilogo giornaliero in ``_review/daily/``.

Tipico utilizzo:
    >>> agg = Aggregator(vault_root)
    >>> agg.add_entry("_review/daily/zabbix-{date}.md", email_data, source_path)
    >>> agg.flush()  # scrive tutti i file aggregati
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from tools.common.paths import resolve_absolute


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class Aggregator:
    """Aggrega email in file di riepilogo giornaliero.

    Bufferizza le entry in memoria e le scrive su disco al ``flush()``.
    I file aggregati seguono il formato definito nel design document
    (sezione 6.2): header + tabella device/problema/conteggio.

    Args:
        vault_root: Percorso root del vault email (dove creare
            ``_review/daily/``).
    """

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root
        # {aggregate_path: {device_key: {"device": ..., "problem": ...,
        #                                 "first_seen": ..., "count": ...,
        #                                 "sources": [...]}}}
        self._entries: dict[str, dict[str, dict]] = defaultdict(dict)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(
        self,
        template_path: str,
        email_data: dict,
        source: Path,
    ) -> None:
        """Bufferizza un'email da aggregare.

        Args:
            template_path: Path template (es. ``_review/daily/zabbix-{date}.md``).
            email_data: Dict con i dati dell'email (subject, from, date, ...).
            source: Percorso del file ``.eml`` originale.
        """
        daily_path = self._resolve_path(template_path)
        path_key = str(daily_path)

        # Estrarre device e problema dal subject
        subject = email_data.get("subject", "")
        device, problem = self._extract_device_problem(subject, email_data)

        # Genera una chiave univoca per device+problema
        device_key = f"{device}||{problem}"

        if device_key not in self._entries[path_key]:
            self._entries[path_key][device_key] = {
                "device": device,
                "problem": problem,
                "first_seen": email_data.get("date", ""),
                "count": 0,
                "sources": [],
            }

        entry = self._entries[path_key][device_key]
        entry["count"] += 1
        if str(source) not in entry["sources"]:
            entry["sources"].append(str(source))

        logger.debug(
            f"Aggregatore: {device} / {problem} (totale: {entry['count']}) → {daily_path.name}"
        )

    def flush(self) -> int:
        """Scrive tutti gli aggregati bufferizzati su disco.

        Per ogni file aggregato:
        1. Se il file esiste già, carica i dati esistenti e li fonde
        2. Se non esiste, crea con header
        3. Ordina per conteggio decrescente
        4. Scrive con formato tabellare

        Returns:
            Numero di file aggregati scritti/aggiornati.
        """
        files_written = 0

        for path_key, device_entries in self._entries.items():
            if not device_entries:
                continue

            daily_path = Path(path_key)

            # Carica dati esistenti se il file esiste
            existing = self._load_existing(daily_path)
            merged = self._merge_entries(existing, device_entries)

            # Scrivi file
            content = self._format_aggregate(daily_path, merged)
            try:
                daily_path.parent.mkdir(parents=True, exist_ok=True)
                daily_path.write_text(content, encoding="utf-8")
                logger.info(
                    f"Aggregato scritto: {daily_path} "
                    f"({len(merged)} device, {sum(e['count'] for e in merged.values())} alert)"
                )
                files_written += 1
            except OSError as e:
                logger.error(f"Errore scrittura aggregato {daily_path}: {e}")

        # Svuota buffer
        self._entries.clear()

        return files_written

    # ------------------------------------------------------------------
    # Helpers interni
    # ------------------------------------------------------------------

    def _resolve_path(self, template_path: str) -> Path:
        """Risolve il template path con ``{date}`` sostituito con la data odierna.

        Args:
            template_path: Path template (es. ``_review/daily/zabbix-{date}.md``).

        Returns:
            :class:`Path` assoluto nel vault.
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path_str = template_path.replace("{date}", date_str)
        return (self.vault_root / path_str).resolve()

    def _extract_device_problem(
        self,
        subject: str,
        email_data: dict,
    ) -> tuple[str, str]:
        """Estrae device e problema dal subject di un'email.

        Cerca di parsare pattern comuni:
        - ``Problem: DEVICE in errore``
        - ``Problem: Service "NAME" is not ok``
        - ``Predictive failure for Disk X in Backplane Y of DEVICE``
        - ``BACKUP FAILED for DEVICE``

        Fallback: usa il sender o "unknown".

        Args:
            subject: Subject dell'email.
            email_data: Dict completo dei dati email.

        Returns:
            Tupla (device, problem).
        """
        device = "unknown"
        problem = subject.strip() if subject else "unknown"

        if not subject:
            return device, problem

        # Pattern: "Problem: DEVICE in errore"
        m = re.search(
            r"problem:\s*(.+?)\s+(?:in errore|has just been restarted|is not ok)",
            subject,
            re.IGNORECASE,
        )
        if m:
            device = m.group(1).strip()
            problem = m.group(0).strip()
            return device, problem

        # Pattern: "Problem: Service "NAME" (DESCRIPTION) is not ok/running"
        m = re.search(
            r'problem:\s*(?:service\s+)"([^"]+)"',
            subject,
            re.IGNORECASE,
        )
        if m:
            device = m.group(1).strip()
            problem = "service not ok"
            return device, problem

        # Pattern: "Predictive failure for Disk X ... of DEVICE"
        m = re.search(
            r"predictive failure.*?(?:of|in)\s+([^\s,]+)",
            subject,
            re.IGNORECASE,
        )
        if m:
            device = m.group(1).strip()
            problem = "predictive failure"
            return device, problem

        # Pattern: "BACKUP FAILED/NOT RESPONDING"
        m = re.search(
            r"(backup\s+(?:failed|is\s+not\s+responding|manuali\s+non\s+eseguiti))",
            subject,
            re.IGNORECASE,
        )
        if m:
            device = self._extract_sender_hostname(email_data)
            problem = m.group(1).strip()
            return device, problem

        # Pattern: "ALERT RECAP"
        if "alert recap" in subject.lower():
            problem = "alert recap"
            device = "global"
            return device, problem

        # Fallback: estrai possibile device dal subject (prima parola uppercase mista)
        m = re.search(r"\b([A-Z][A-Z0-9_-]+(?:[.-][A-Z0-9]+)*)\b", subject)
        if m:
            device = m.group(1)

        return device, problem

    @staticmethod
    def _extract_sender_hostname(email_data: dict) -> str:
        """Estrae un hostname dal sender dell'email.

        Args:
            email_data: Dict con i dati email.

        Returns:
            Hostname estratto o ``"unknown"``.
        """
        sender = email_data.get("from", "")
        if not sender:
            return "unknown"

        # Cerca email nel formato nome@hostname.dominio
        m = re.search(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", sender)
        if m:
            # Prendi il primo segmento del nome host
            host = m.group(1).split(".")[0]
            return host

        return "unknown"

    def _load_existing(self, path: Path) -> dict[str, dict]:
        """Carica gli entry esistenti da un file aggregato.

        Cerca di parsare le tabelle Markdown esistenti con formato:
        ``| Device | Problema | Prima segnalazione | Oggi |``

        Args:
            path: Percorso del file aggregato.

        Returns:
            Dizionario ``{device||problem: entry}``.
        """
        entries: dict[str, dict] = {}

        if not path.exists():
            return entries

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return entries

        # Cerca la tabella "Nuovi problemi"
        table_section = re.search(
            r"## Nuovi problemi.*?\n(\|.*\|(?:\n\|.*\|)+)",
            content,
            re.DOTALL,
        )
        if not table_section:
            return entries

        table_text = table_section.group(1)
        lines = table_text.strip().split("\n")

        if len(lines) < 3:  # header + separator + almeno una riga
            return entries

        # Skip header e separator (line 0 e 1)
        for line in lines[2:]:
            line = line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue

            # Pulisci e splitta per pipe
            parts = [p.strip() for p in line.split("|")]
            # Rimuovi empty first/last da split su pipe iniziale/finale
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]

            if len(parts) >= 4:
                device = parts[0].strip()
                problem = parts[1].strip()
                first_seen = parts[2].strip()

                # Estrai conteggio dalla cella "Oggi" (es. "24 alert" → 24)
                count_cell = parts[3].strip()
                count_match = re.search(r"\d+", count_cell)
                count = int(count_match.group()) if count_match else 0

                device_key = f"{device}||{problem}"
                entries[device_key] = {
                    "device": device,
                    "problem": problem,
                    "first_seen": first_seen,
                    "count": count,
                    "existing": True,  # flag per merge
                }

        return entries

    def _merge_entries(
        self,
        existing: dict[str, dict],
        new_entries: dict[str, dict],
    ) -> dict[str, dict]:
        """Fonde nuovi entry con quelli esistenti.

        Se un entry esiste già (stesso device+problema), somma i conteggi
        e preserva la data di prima segnalazione.

        Args:
            existing: Entry esistenti dal file aggregato.
            new_entries: Nuovi entry dal buffer corrente.

        Returns:
            Dizionario unificato ``{device_key: entry}``.
        """
        merged: dict[str, dict] = {}

        # Copia esistenti
        for key, entry in existing.items():
            merged[key] = dict(entry)
            # Rimuovi flag interno
            merged[key].pop("existing", None)

        # Aggiungi/fondi nuovi
        for key, entry in new_entries.items():
            if key in merged:
                # Somma conteggi
                merged[key]["count"] += entry["count"]
                # Preserva data più antica
                existing_first = merged[key].get("first_seen", "")
                new_first = entry.get("first_seen", "")
                if new_first and (not existing_first or (new_first < existing_first)):
                    merged[key]["first_seen"] = new_first
                # Aggrega sorgenti
                existing_sources = merged[key].get("sources", [])
                new_sources = entry.get("sources", [])
                merged[key]["sources"] = list(set(existing_sources + new_sources))
            else:
                merged[key] = dict(entry)

        return merged

    def _format_aggregate(
        self,
        path: Path,
        entries: dict[str, dict],
    ) -> str:
        """Formatta il contenuto di un file aggregato.

        Args:
            path: Percorso del file (usato per il titolo).
            entries: Dizionario degli entry da formattare.

        Returns:
            Stringa Markdown completa.
        """
        # Determina il nome del report dal nome file (es. "zabbix-2026-05-19" → "Zabbix")
        stem = path.stem
        # Rimuovi la data in fondo: -YYYY-MM-DD
        clean_name = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", stem)
        report_name = clean_name.replace("-", " ").title()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines: list[str] = []
        lines.append(f"# Riepilogo {report_name} — {date_str}")
        lines.append("")

        # Ordina per conteggio decrescente
        sorted_entries = sorted(
            entries.values(),
            key=lambda e: e["count"],
            reverse=True,
        )

        total_count = sum(e["count"] for e in sorted_entries)
        unique_devices = len(set(e["device"] for e in sorted_entries))

        lines.append(f"## Nuovi problemi ({len(sorted_entries)})")
        lines.append("| Device | Problema | Prima segnalazione | Oggi |")
        lines.append("|--------|----------|--------------------|------|")

        for entry in sorted_entries:
            device = entry["device"][:60]
            problem = entry["problem"][:60]
            first_seen = entry.get("first_seen", "—")
            count_display = f"{entry['count']} alert"
            lines.append(f"| {device} | {problem} | {first_seen} | {count_display} |")

        lines.append("")
        lines.append("## Statistiche")
        lines.append(f"- Totale alert oggi: **{total_count}** (da {unique_devices} device)")

        return "\n".join(lines) + "\n"
