"""MCP server: expose email_processor read tools for Team Olimpo.

Provides read-only query tools for the email vault:
- ``status`` — vault statistics
- ``search`` — search emails by content/frontmatter
- ``discover`` — pattern discovery across recent emails
- ``rules_list`` — list active filter rules
- ``contacts`` — list/search Addressbook contacts

Usage
-----
    uv run python -m tools.email_processor.server

Registrazione in opencode.json::

    "email_processor": {
      "type": "local",
      "command": ["uv", "run", "python", "-m", "tools.email_processor.server"],
      "enabled": true
    }
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml as yaml_lib
from loguru import logger

from tools.common.paths import project_root, resolve_relative
from tools.email_processor.discovery import PatternDiscovery

# ---------------------------------------------------------------------------
# Token Juice — graceful fallback if missing
# ---------------------------------------------------------------------------

try:
    from tools.token_juice import maybe_compress
except ImportError:

    def maybe_compress(text: str, **kwargs: object) -> str:  # type: ignore[misc]
        return text

# ---------------------------------------------------------------------------
# MCP SDK
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("email_processor")
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config helpers (mirror cli.py)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = project_root()


def _load_config() -> dict:
    config_path = _PROJECT_ROOT / "tools" / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        return yaml_lib.safe_load(f) or {}


def _get_vault_root() -> Path | None:
    vault_root_str = os.getenv("EMAIL_VAULT_ROOT")
    if vault_root_str:
        return Path(vault_root_str)

    config = _load_config()
    vault_root_str = config.get("email_processor", {}).get("vault_root")
    if vault_root_str:
        return resolve_relative(vault_root_str)

    return None


def _get_rules_path() -> Path | None:
    """Locate filter_rules.yaml next to this module."""
    rules_path = Path(__file__).resolve().parent / "filter_rules.yaml"
    return rules_path if rules_path.exists() else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RE_FM_YAML = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_RE_STATUS = re.compile(r"^status:\s*(\w+)", re.MULTILINE)
_RE_DATE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_RE_LABELS = re.compile(r"^labels:\s*\n((?:\s*-\s+.*\n?)*)", re.MULTILINE)
_RE_FROM = re.compile(r"^from:\s*(.*)$", re.MULTILINE)
_RE_SUBJECT = re.compile(r"^subject:\s*(.*)$", re.MULTILINE)


def _parse_frontmatter(content: str) -> dict:
    """Extract key frontmatter fields from a note's raw content."""
    result: dict = {}
    fm_match = _RE_FM_YAML.search(content)
    if not fm_match:
        return result
    try:
        fm_data = yaml_lib.safe_load(fm_match.group(1))
    except Exception:
        return result
    if not isinstance(fm_data, dict):
        return result
    result["subject"] = str(fm_data.get("subject", ""))
    result["from"] = str(fm_data.get("from", ""))
    result["date"] = str(fm_data.get("date", ""))
    result["status"] = str(fm_data.get("status", ""))
    result["labels"] = fm_data.get("labels", []) or []
    result["message_id"] = str(fm_data.get("message_id", ""))
    return result


def _get_email_files(vault_root: Path) -> list[Path]:
    emails_dir = vault_root / "Inbox" / "emails"
    if not emails_dir.exists():
        return []
    return sorted(emails_dir.rglob("*.md"))


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def status() -> str:
    """Statistiche vault email."""
    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        return json.dumps({"error": "Vault email non trovato"}, indent=2)

    total_notes = 0
    status_counts: dict[str, int] = {"new": 0, "processed": 0, "flagged": 0}
    dates: list[str] = []

    for md_file in _get_email_files(vault_root):
        total_notes += 1
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        st_match = _RE_STATUS.search(content)
        if st_match:
            st_val = st_match.group(1).strip()
            status_counts[st_val] = status_counts.get(st_val, 0) + 1

        dt_match = _RE_DATE.search(content)
        if dt_match:
            dates.append(dt_match.group(1))

    # Thread count
    threads_dir = vault_root / "Review" / "threads"
    thread_count = len(list(threads_dir.glob("*.md"))) if threads_dir.exists() else 0

    # Contact count
    addressbook_dir = vault_root / "Addressbook"
    contact_count = (
        len([f for f in addressbook_dir.glob("*.md") if f.name != "_index.md"])
        if addressbook_dir.exists()
        else 0
    )

    min_date = min(dates) if dates else "—"
    max_date = max(dates) if dates else "—"

    # Count by label
    label_counts: dict[str, int] = {}
    for md_file in _get_email_files(vault_root):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(content)
        for label in fm.get("labels", []):
            label_counts[label] = label_counts.get(label, 0) + 1

    result = {
        "vault": str(vault_root),
        "total_notes": total_notes,
        "by_status": {k: v for k, v in sorted(status_counts.items())},
        "other_status": total_notes - sum(status_counts.values()),
        "threads": thread_count,
        "contacts": contact_count,
        "date_range": {"from": min_date, "to": max_date},
        "by_label": dict(sorted(label_counts.items(), key=lambda x: -x[1])),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def search(
    query: str,
    field: Optional[str] = None,
    limit: int = 10,
    status_filter: Optional[str] = None,
) -> str:
    """Cerca nel vault email per contenuto o campo."""
    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        return json.dumps({"error": "Vault email non trovato"}, indent=2)

    query_lower = query.lower()
    results: list[dict] = []

    for md_file in _get_email_files(vault_root):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Parse frontmatter
        fm = _parse_frontmatter(content)

        # Filter by status
        if status_filter and fm.get("status", "").lower() != status_filter.lower():
            continue

        # Determine body (everything after ---\n)
        body = ""
        body_match = content.split("---", 2)
        if len(body_match) > 2:
            body = body_match[2].strip()

        # Compress large bodies to reduce token usage
        if len(body) > 1024:
            body = maybe_compress(
                body, intensity="ultra", argv=["email_processor", "search", query]
            )

        # Search logic
        matched = False
        if not field or field == "all":
            matched = (
                query_lower in fm.get("subject", "").lower()
                or query_lower in fm.get("from", "").lower()
                or query_lower in body.lower()
                or query_lower in " ".join(fm.get("labels", [])).lower()
            )
        elif field == "subject":
            matched = query_lower in fm.get("subject", "").lower()
        elif field == "from":
            matched = query_lower in fm.get("from", "").lower()
        elif field == "body":
            matched = query_lower in body.lower()
        elif field == "label":
            matched = any(query_lower in label.lower() for label in fm.get("labels", []))

        if not matched:
            continue

        # Build snippet
        snippet = ""
        if body:
            idx = body.lower().find(query_lower)
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(body), idx + len(query) + 60)
                snippet = body[start:end].strip().replace("\n", " ")
                if start > 0:
                    snippet = "..." + snippet
                if end < len(body):
                    snippet = snippet + "..."

        rel_path = str(md_file.relative_to(vault_root))
        results.append(
            {
                "path": rel_path,
                "subject": fm.get("subject", ""),
                "from": fm.get("from", ""),
                "date": fm.get("date", ""),
                "status": fm.get("status", ""),
                "labels": fm.get("labels", []),
                "snippet": snippet,
            }
        )

        if len(results) >= limit:
            break

    return json.dumps(
        {"results": results, "total": len(results), "query": query},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def discover(days: int = 30) -> str:
    """Scopre pattern nelle email recenti."""
    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        return json.dumps({"error": "Vault email non trovato"}, indent=2)

    discovery = PatternDiscovery(vault_root)
    patterns = discovery.scan(days=days)

    results = []
    for p in patterns:
        results.append(
            {
                "id": p.id,
                "normalized": p.normalized,
                "count": p.count,
                "senders": p.senders[:5],  # top 5
                "sender_domain": p.sender_domain,
                "date_range": p.date_range,
                "samples": p.samples,
            }
        )

    return json.dumps(
        {"patterns": results, "total": len(results), "window_days": days},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def rules_list() -> str:
    """Elenca regole filtro email attive."""
    rules_path = _get_rules_path()
    if not rules_path:
        return json.dumps({"error": "filter_rules.yaml non trovato"}, indent=2)

    try:
        raw = rules_path.read_text(encoding="utf-8")
        data: dict = yaml_lib.safe_load(raw) or {}
    except Exception as e:
        return json.dumps({"error": f"Errore lettura regole: {e}"}, indent=2)

    rules = data.get("rules", [])
    results = []
    for r in rules:
        match = r.get("match", {})
        match_summary = {}
        for field, conditions in match.items():
            if isinstance(conditions, dict):
                match_summary[field] = {
                    k: (v[:3] if isinstance(v, list) else v) for k, v in conditions.items()
                }

        results.append(
            {
                "id": r.get("id"),
                "name": r.get("name", ""),
                "action": r.get("action"),
                "priority": r.get("priority"),
                "label": r.get("label"),
                "reason": r.get("reason", ""),
                "match": match_summary,
            }
        )

    results.sort(key=lambda x: -(x.get("priority", 0) or 0))

    return json.dumps(
        {"rules": results, "total": len(results)},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def contacts(search_query: Optional[str] = None) -> str:
    """Elenca o cerca contatti nell'Addressbook."""
    vault_root = _get_vault_root()
    if not vault_root or not vault_root.exists():
        return json.dumps({"error": "Vault email non trovato"}, indent=2)

    addressbook_dir = vault_root / "Addressbook"
    if not addressbook_dir.exists():
        return json.dumps({"contacts": [], "total": 0}, indent=2)

    results: list[dict] = []
    for md_file in sorted(addressbook_dir.glob("*.md")):
        if md_file.name == "_index.md":
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm = _parse_frontmatter(content)
        name = md_file.stem.replace("-", " ").title()
        email = fm.get("from", "")  # fallback: non è l'email reale

        # Try to read email from frontmatter properly
        fm_match = _RE_FM_YAML.search(content)
        email_val = ""
        company_val = ""
        if fm_match:
            try:
                fm_data = yaml_lib.safe_load(fm_match.group(1))
                if isinstance(fm_data, dict):
                    email_val = str(fm_data.get("email", ""))
                    company_val = str(fm_data.get("company", ""))
            except Exception:
                pass

        entry = {
            "name": name,
            "email": email_val or email,
            "company": company_val,
        }

        if search_query:
            q = search_query.lower()
            if q not in entry["name"].lower() and q not in entry["email"].lower():
                continue

        results.append(entry)

    return json.dumps(
        {"contacts": results, "total": len(results)},
        indent=2,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main_server() -> None:
    """Start the MCP server on stdio transport."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Run: uv add mcp")
        raise SystemExit(1)

    logger.info("Starting email_processor MCP server on stdio...")
    mcp.run()


if __name__ == "__main__":
    main_server()
