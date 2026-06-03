"""Layer 1 — Discovery Tool: scan email vault notes and discover classification patterns.

Produces structured YAML output with normalized subject patterns,
counts, senders, and sample subjects — ready for Hermes to parse
and apply rules via 'rules apply'.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from loguru import logger


# Regex for device/hostname tokens (applied case-sensitively before lowering).
# Matches:
#   - tokens with internal separators (underscore/hyphen/dot) length >= 4
#   - mixed uppercase+digit tokens length >= 5 (MM_Z1_ZSERVZ1, IT_MM-W19-DV-CYB01)
#   - pure uppercase tokens length >= 4
_RE_DEVICE_TOKEN = re.compile(
    r"\b[A-Za-z0-9]{4,}(?:[-_.][A-Za-z0-9]+)+\b"  # token con separatori interni
    r"|\b(?=\w*[A-Z])(?=\w*\d)\w{5,}\b"  # misto uppercase+digit >=5
    r"|\b[A-Z][A-Z0-9]{3,}\b",  # uppercase stringa >=4
)

_RE_EXTERNAL = re.compile(r"^\[(?:external|ext|ext\.?)\]\s*", re.IGNORECASE)
_RE_THREAD_PREFIX = re.compile(
    r"^(?:re|r|fw|fwd|rif|oggi|tr|vs|aw|antw|wg):\s*",
    re.IGNORECASE,
)
_RE_NUMBERS = re.compile(r"\b\d[\d,.:]*\d\b|\b\d\b")
_RE_HEX_HASH = re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE)
_RE_PERCENT = re.compile(r"\d+%")
_RE_EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_DATE_LIKE = re.compile(
    r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
    r"|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\b",
)
_RE_MULTI_DEVICE = re.compile(r"\{device\}\s*\{device\}")
_RE_WS = re.compile(r"\s+")
_RE_PLACEHOLDER_ONLY = re.compile(r"[\s{}a-z]+")
_RE_NOT_SLUG = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Pattern entity
# ---------------------------------------------------------------------------


@dataclass
class Pattern:
    """A cluster of emails with similar subject lines.

    Attributes:
        id: Numeric identifier (1-based, sorted by count descending).
        normalized: Normalized subject pattern (e.g. ``"problem: {device} in errore"``).
        count: Number of emails in this cluster.
        senders: List of unique sender addresses.
        sender_domain: Primary sender domain (e.g. ``"fisvi.com"``).
        date_range: ``[min_date, max_date]`` as ``"YYYY-MM-DD"``.
        samples: Up to 3 real subject examples.
    """

    id: int
    normalized: str
    count: int
    senders: list[str]
    sender_domain: str
    date_range: list[str]
    samples: list[str]


# ---------------------------------------------------------------------------
# Pattern Discovery Engine
# ---------------------------------------------------------------------------


class PatternDiscovery:
    """Scans email vault notes and discovers classification patterns.

    Reads Markdown notes from ``Inbox/emails/YYYY/MM/DD/*.md``,
    extracts subject/from/date from YAML frontmatter, normalizes subjects,
    groups by normalized form, and produces structured :class:`Pattern` objects.

    Args:
        vault_root: Root path of the email vault (contains ``Inbox/emails/``).
    """

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, days: int | None = None) -> list[Pattern]:
        """Scan email vault notes and return discovered patterns.

        Args:
            days: If set, only scan notes from the last N days.

        Returns:
            List of :class:`Pattern` objects sorted by count descending.
            Empty list if no notes found.
        """
        entries = self._collect_entries(days)
        if not entries:
            logger.info("No email notes found in scan period.")
            return []

        grouped = self._cluster(entries)
        patterns = self._build_patterns(grouped)
        return patterns

    @staticmethod
    def infer_rule_from_pattern(pattern: Pattern) -> dict:
        """Generate match conditions from a discovered pattern.

        Heuristic:
          1. Extract the first word >3 chars (not a placeholder) from
             the normalized pattern.
          2. Use sender_domain as ``from`` contains condition.
          3. Fall back to scanning original samples for keywords.

        Args:
            pattern: A discovered :class:`Pattern`.

        Returns:
            Dict with keys ``name`` and ``match`` suitable for a YAML rule.
        """
        match: dict[str, dict] = {}
        subject_contains: list[str] = []

        # Try extracting key token from normalized pattern first
        for word in pattern.normalized.split():
            clean = word.strip("{}:,;!?.")
            if len(clean) >= 4 and clean not in ("device", "date", "num", "email"):
                subject_contains.append(clean)
                break

        # Fallback: scan original samples for meaningful keywords
        if not subject_contains:
            _STOPWORDS = {
                "the",
                "and",
                "for",
                "not",
                "has",
                "been",
                "with",
                "from",
                "this",
                "that",
                "are",
                "was",
                "were",
                "you",
                "your",
                "our",
                "all",
                "can",
                "new",
                "use",
                "used",
                "using",
                "via",
                "per",
                "del",
                "che",
                "con",
                "external",
                "message",
                "email",
                "mail",
                "notification",
            }
            for sample in pattern.samples:
                words = re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", sample)
                for w in words:
                    if w.lower() not in _STOPWORDS:
                        subject_contains.append(w)
                        break
                if subject_contains:
                    break

        if subject_contains:
            match["subject"] = {"contains": subject_contains[:3]}

        # From condition based on sender domain / sender username
        from_contains: list[str] = []
        if pattern.sender_domain and pattern.sender_domain != "unknown":
            from_contains.append(pattern.sender_domain)
        # Extract sender username prefix for more specific matching
        for sender in pattern.senders:
            local = sender.split("@")[0].lower()
            if (
                local
                and len(local) >= 3
                and local
                not in (
                    "postmaster",
                    "mailer-daemon",
                    "noreply",
                    "no-reply",
                )
            ):
                from_contains.append(local)
                break

        if from_contains:
            match["from"] = {"contains": from_contains[:2]}

        return {
            "name": pattern.normalized[:80],
            "match": match,
        }

    @staticmethod
    def patterns_to_yaml(
        patterns: list[Pattern],
        period_start: str,
        period_end: str,
    ) -> str:
        """Convert patterns to structured YAML string.

        Args:
            patterns: List of discovered patterns.
            period_start: Start date string (``YYYY-MM-DD``).
            period_end: End date string (``YYYY-MM-DD``).

        Returns:
            YAML string with ``scan`` and ``patterns`` sections.
        """
        total_emails = sum(p.count for p in patterns)
        data = {
            "scan": {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "period_start": period_start,
                "period_end": period_end,
                "total_emails": total_emails,
                "total_patterns": len(patterns),
            },
            "patterns": [
                {
                    "id": p.id,
                    "normalized": p.normalized,
                    "count": p.count,
                    "senders": p.senders,
                    "sender_domain": p.sender_domain,
                    "date_range": p.date_range,
                    "samples": p.samples,
                }
                for p in patterns
            ],
        }
        return yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    @staticmethod
    def pattern_from_yaml_dict(data: dict) -> Pattern:
        """Reconstruct a :class:`Pattern` from a YAML dict.

        Args:
            data: Dict with keys matching ``Pattern`` fields.

        Returns:
            :class:`Pattern` instance.
        """
        return Pattern(
            id=data["id"],
            normalized=data["normalized"],
            count=data["count"],
            senders=data.get("senders", []),
            sender_domain=data.get("sender_domain", "unknown"),
            date_range=data.get("date_range", ["unknown", "unknown"]),
            samples=data.get("samples", []),
        )

    # ------------------------------------------------------------------
    # Entry collection
    # ------------------------------------------------------------------

    def _collect_entries(self, days: int | None) -> list[dict]:
        """Walk vault notes and collect subject/from/date metadata.

        Args:
            days: Optional recency filter in days.

        Returns:
            List of dicts with keys: ``subject``, ``sender``, ``date``.
        """
        emails_dir = self.vault_root / "Inbox" / "emails"
        if not emails_dir.exists():
            logger.warning(f"Email directory not found: {emails_dir}")
            return []

        cutoff: datetime | None = None
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        entries: list[dict] = []
        for md_file in sorted(emails_dir.rglob("*.md")):
            # Quick time filter via directory structure YYYY/MM/DD
            if cutoff is not None:
                try:
                    rel = md_file.relative_to(emails_dir)
                    parts = rel.parts
                    if len(parts) >= 3:
                        file_date = datetime(
                            int(parts[0]),
                            int(parts[1]),
                            int(parts[2]),
                            tzinfo=timezone.utc,
                        )
                        if file_date < cutoff:
                            continue
                except (ValueError, IndexError):
                    pass

            fm = self._read_frontmatter(md_file)
            if fm is None:
                continue

            subject = str(fm.get("subject", "")).strip()
            sender = str(fm.get("from", "")).strip()
            date = str(fm.get("date", "")).strip()

            if not subject:
                continue

            entries.append(
                {
                    "subject": subject,
                    "sender": sender,
                    "date": date or "unknown",
                }
            )

        logger.debug(f"Collected {len(entries)} entries from vault scan")
        return entries

    @staticmethod
    def _read_frontmatter(md_file: Path) -> dict | None:
        """Parse YAML frontmatter from a Markdown note.

        Args:
            md_file: Path to ``.md`` file.

        Returns:
            Dict of frontmatter fields, or ``None`` if unparseable.
        """
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            return None

        try:
            fm_data = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            return None

        if not isinstance(fm_data, dict):
            return None

        return fm_data

    # ------------------------------------------------------------------
    # Normalization & clustering
    # ------------------------------------------------------------------

    def _normalize_subject(self, subject: str) -> str:
        """Normalize email subject for pattern clustering.

        Steps (inherited from v0, adapted for ``{placeholder}`` tokens):
          1. Remove ``[EXTERNAL]`` and ``RE:/FW:`` prefixes
          2. Replace device/hostname tokens with ``{device}``
          3. Replace hex hashes, dates, times, percentages
          4. Replace email addresses
          5. Lowercase
          6. Replace isolated numbers with ``{num}``
          7. Collapse multiple placeholders and spaces
          8. Fallback to truncated original if too generic

        Args:
            subject: Raw subject string.

        Returns:
            Normalized string with ``{device}``, ``{date}``, ``{num}`` placeholders.
        """
        s = subject.strip()

        # Remove [EXTERNAL] marker (before lower)
        s = _RE_EXTERNAL.sub("", s).strip()
        # Remove thread prefixes
        s = _RE_THREAD_PREFIX.sub("", s).strip()

        # Replace device tokens with {device}
        s = _RE_DEVICE_TOKEN.sub("{device}", s)

        # Replace hex hashes
        s = _RE_HEX_HASH.sub("{num}", s)
        # Replace date-like patterns
        s = _RE_DATE_LIKE.sub("{date}", s)
        # Replace percentages
        s = _RE_PERCENT.sub("{num}", s)
        # Replace email addresses
        s = _RE_EMAIL_ADDR.sub("{email}", s)

        # Lowercase
        s = s.lower().strip()

        # Replace standalone numbers
        s = _RE_NUMBERS.sub("{num}", s)

        # Collapse consecutive ``{device} {device}`` -> ``{device}``
        s = _RE_MULTI_DEVICE.sub("{device}", s)

        # Collapse multiple spaces
        s = _RE_WS.sub(" ", s).strip()

        # Trim trailing/leading placeholders
        s = re.sub(r"^\{device\}\s*", "", s)
        s = re.sub(r"\s*\{device\}$", "", s)

        # If after normalization only placeholders remain, fallback
        if not _RE_PLACEHOLDER_ONLY.sub("", s) or len(set(s.split())) <= 1:
            fallback = subject.lower().strip()[:60]
            fallback = _RE_EXTERNAL.sub("", fallback).strip()
            fallback = _RE_THREAD_PREFIX.sub("", fallback).strip()
            fallback = _RE_WS.sub(" ", fallback).strip()
            if fallback:
                return fallback

        return s

    def _cluster(self, entries: list[dict]) -> dict[str, list[dict]]:
        """Group entries by normalized subject.

        Args:
            entries: List of entry dicts with ``subject`` key.

        Returns:
            Dict mapping normalized pattern -> list of entries.
        """
        groups: dict[str, list[dict]] = defaultdict(list)
        for entry in entries:
            normalized = self._normalize_subject(entry["subject"])
            groups[normalized].append(entry)

        logger.debug(f"Clustering: {len(entries)} entries -> {len(groups)} groups")
        return groups

    def _build_patterns(self, groups: dict[str, list[dict]]) -> list[Pattern]:
        """Convert clustered groups into sorted Pattern list.

        Args:
            groups: Dict from :meth:`_cluster`.

        Returns:
            List of :class:`Pattern` sorted by count descending.
        """
        sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

        patterns: list[Pattern] = []
        for idx, (normalized, group) in enumerate(sorted_groups, start=1):
            # Collect dates
            dates = [e["date"] for e in group if e["date"] not in ("unknown", "", "0000-00-00")]
            min_date = min(dates) if dates else "unknown"
            max_date = max(dates) if dates else "unknown"

            # Unique senders
            senders = sorted({e["sender"] for e in group if e["sender"]})

            # Determine primary sender domain
            sender_domain = "unknown"
            for s in senders:
                if "@" in s:
                    domain = s.split("@")[-1].rstrip(">").strip()
                    if domain:
                        sender_domain = domain
                        break

            # Up to 3 unique sample subjects
            seen: set[str] = set()
            samples: list[str] = []
            for e in group:
                subj = e["subject"]
                if subj not in seen:
                    seen.add(subj)
                    samples.append(subj)
                    if len(samples) >= 3:
                        break

            normalized_clean = normalized[:120] if normalized else "(empty)"

            patterns.append(
                Pattern(
                    id=idx,
                    normalized=normalized_clean,
                    count=len(group),
                    senders=senders,
                    sender_domain=sender_domain,
                    date_range=[min_date, max_date],
                    samples=samples,
                )
            )

        return patterns


def _slugify(s: str) -> str:
    """Convert a string to a URL-safe slug.

    Args:
        s: Input string.

    Returns:
        Lowercase slug with non-alphanumeric chars replaced by ``-``.
    """
    slug = _RE_NOT_SLUG.sub("-", s.lower())
    return slug.strip("-")


def _generate_rule_id(
    subject_contains: list[str] | None = None,
    name: str | None = None,
) -> str:
    """Generate a rule ID from subject conditions or name.

    Args:
        subject_contains: List of subject match patterns.
        name: Human-readable rule name.

    Returns:
        A slug string suitable as a YAML rule ``id``.
    """
    import time  # noqa: PLC0415

    if name:
        return _slugify(name)[:50] or f"rule-{int(time.time())}"
    if subject_contains:
        return _slugify(subject_contains[0])[:50] or f"rule-{int(time.time())}"
    return f"rule-{int(time.time())}"
