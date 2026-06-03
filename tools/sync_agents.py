#!/usr/bin/env python3
"""Sync OpenCode agents to Claude Code format.

Transforms .opencode/agents/*.md to .claude/agents/*.md, converting:
- Frontmatter schema (name, tools, model format, etc.)
- Tool names (lowercase → PascalCase)
- Permission rules → tools allowlist
"""

import re
import sys
from pathlib import Path
from typing import Any

import yaml


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter and body from markdown.

    Returns (frontmatter_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content

    try:
        fm = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}, content

    return fm, match.group(2).lstrip("\n")


def convert_model(opencode_model: str) -> str:
    """Convert OpenCode model ID to Claude Code alias.

    Always returns 'haiku'.
    """
    return "haiku"


def extract_tools(permission: dict) -> list[str]:
    """Convert OpenCode permission object to Claude Code tools list.

    Examples:
    - read: allow → ['Read']
    - bash: allow → ['Bash']
    - edit: {path: allow} → ['Edit']

    All agents automatically get access to all MCP tools:
    - synapsis: synapsis_hf, synapsis_search, synapsis_session, synapsis_task, synapsis_admin, synapsis_consolidate
    - email_processor: status, search, discover, rules_list, contacts
    - taskmanager: task_create, task_update_status, task_query, task_summary, task_log_event, task_export
    - executor: executor_run
    """
    tools = []

    if permission.get("read") == "allow":
        tools.append("Read")

    if permission.get("write") == "allow":
        tools.append("Write")

    if permission.get("bash") == "allow":
        tools.append("Bash")

    if permission.get("edit"):
        if isinstance(permission["edit"], dict) and any(
            v == "allow" for v in permission["edit"].values()
        ):
            tools.append("Edit")
        elif permission["edit"] == "allow":
            tools.append("Edit")

    if permission.get("task") == "allow":
        tools.append("Agent")

    if permission.get("webfetch") == "allow":
        tools.append("WebFetch")

    if permission.get("websearch") == "allow":
        tools.append("WebSearch")

    # Add all MCP tools to every agent
    # Tool names are as exposed by their MCP servers in .mcp.json
    mcp_tools = [
        # synapsis (includes hf: handoff create/get)
        "synapsis_hf",
        "synapsis_search",
        "synapsis_session",
        "synapsis_task",
        "synapsis_admin",
        "synapsis_consolidate",
        # email_processor
        "status",
        "search",
        "discover",
        "rules_list",
        "contacts",
        # taskmanager
        "task_create",
        "task_update_status",
        "task_query",
        "task_summary",
        "task_log_event",
        "task_export",
        # synapsis (KB search)
        "knowledge_search",
        "knowledge_read",
        # session_memory
        "session_init",
        "session_observe",
        "session_context",
        "session_recall",
        "session_summarize",
    ]
    tools.extend(mcp_tools)

    return tools


def convert_frontmatter(opencode_fm: dict[str, Any], filename: str) -> dict[str, Any]:
    """Transform OpenCode frontmatter to Claude Code format."""
    claude_fm = {}

    # Required: name (from filename)
    claude_fm["name"] = filename.replace(".md", "")

    # Copy description (required in both)
    if "description" in opencode_fm:
        claude_fm["description"] = opencode_fm["description"]

    # Model conversion
    if "model" in opencode_fm:
        claude_fm["model"] = convert_model(opencode_fm["model"])

    # Temperature (same in both)
    if "temperature" in opencode_fm:
        claude_fm["temperature"] = opencode_fm["temperature"]

    # Color (same in both)
    if "color" in opencode_fm:
        claude_fm["color"] = opencode_fm["color"]

    # Convert permission → tools
    if "permission" in opencode_fm:
        tools = extract_tools(opencode_fm["permission"])
        if tools:
            claude_fm["tools"] = ", ".join(tools)

    # Top-level permission mode (if not covered by per-tool rules)
    if "permission" in opencode_fm:
        perm = opencode_fm["permission"]
        if isinstance(perm, dict) and "deny" in str(perm):
            # Has deny rules; use ask mode for safety
            claude_fm["permissionMode"] = "ask"

    return claude_fm


def sync_agents() -> int:
    """Sync all agents from .opencode/agents/ to .claude/agents/."""
    repo_root = Path(__file__).parent.parent
    opencode_dir = repo_root / ".opencode" / "agents"
    claude_dir = repo_root / ".claude" / "agents"

    if not opencode_dir.exists():
        print(f"Error: {opencode_dir} not found")
        return 1

    claude_dir.mkdir(parents=True, exist_ok=True)

    agent_files = sorted(opencode_dir.glob("*.md"))
    if not agent_files:
        print(f"Warning: no agent files found in {opencode_dir}")
        return 1

    synced = 0
    errors = 0

    for opencode_file in agent_files:
        try:
            filename = opencode_file.name
            content = opencode_file.read_text(encoding="utf-8")

            opencode_fm, body = parse_frontmatter(content)
            if not opencode_fm:
                print(f"⚠️  {filename}: no frontmatter, skipping")
                continue

            claude_fm = convert_frontmatter(opencode_fm, filename)

            # Reconstruct with Claude Code frontmatter
            claude_fm_yaml = yaml.dump(claude_fm, default_flow_style=False, sort_keys=False)
            claude_content = f"---\n{claude_fm_yaml}---\n\n{body}"

            # Write to .claude/agents/
            claude_file = claude_dir / filename
            claude_file.write_text(claude_content, encoding="utf-8")
            print(f"✓ {filename}")
            synced += 1

        except Exception as e:
            print(f"✗ {filename}: {e}")
            errors += 1

    print(f"\nSynced {synced} agents to .claude/agents/")
    if errors:
        print(f"Errors: {errors}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(sync_agents())
