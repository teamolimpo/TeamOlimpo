from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Task:
    id: str
    title: str | None = None
    description: str | None = None
    delegated_to: str | None = None
    responsible: str | None = None
    status: str | None = None
    started_at: str | None = None
    subtasks: list[dict[str, Any]] | None = None
    notes: str | None = None


@dataclass
class Decision:
    id: str
    date: str | None = None
    description: str | None = None
    topic: str | None = None
    decision: str | None = None
    rationale: str | None = None


@dataclass
class Scratchpad:
    path: Path
    raw: dict[str, Any] = field(default_factory=dict)
    tasks: list[Task] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    parsed: bool = False
    yaml_error: str | None = None
    yaml_error_line: int | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def rel_path(self) -> str:
        try:
            from tools.hermes_cli.config import PROJECT_ROOT

            return str(self.path.relative_to(PROJECT_ROOT))
        except (ValueError, ImportError):
            return str(self.path)

    @property
    def has_yaml(self) -> bool:
        return self.parsed


@dataclass
class HandoffValidation:
    path: Path
    frontmatter: dict[str, Any] = field(default_factory=dict)
    has_frontmatter: bool = False
    naming_valid: bool = True
    naming_errors: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.naming_valid and len(self.errors) == 0

    @property
    def rel_path(self) -> str:
        try:
            from tools.hermes_cli.config import PROJECT_ROOT

            return str(self.path.relative_to(PROJECT_ROOT))
        except (ValueError, ImportError):
            return str(self.path)
