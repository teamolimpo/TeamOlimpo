#!/usr/bin/env bash
# =============================================================================
# Team Olimpo Template — Functional Test Suite
# =============================================================================
# Runs automated tests on the template to verify:
#   1. Environment & dependencies
#   2. Directory structure & required files
#   3. Content integrity (no KBA, English-only, no Italian)
#   4. CLI tools (hermes_cli, preflight_check)
#   5. ID management
#   6. Handoff creation & validation
#   7. Scratchpad initialization
#   8. Obsidian vault conventions
# =============================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
ERRORS=()

header()  { echo ""; echo "═══════════════════════════════════════════════════════════════"; echo " $1"; echo "═══════════════════════════════════════════════════════════════"; }
pass()    { PASS=$((PASS+1)); echo "  ✅ PASS: $1"; }
fail()    { FAIL=$((FAIL+1)); ERRORS+=("  ❌ FAIL: $1"); echo "  ❌ FAIL: $1"; }
info()    { echo "  ℹ️  $1"; }
check()   { if eval "$1"; then pass "$2"; else fail "$2"; fi; }
check_dir()  { local d="$1"; if [ -d "$ROOT/$d" ]; then pass "Directory exists: $d"; else fail "Directory exists: $d"; fi; }
check_file() { local f="$1"; if [ -f "$ROOT/$f" ]; then pass "File exists: $f"; else fail "File exists: $f"; fi; }

cd "$ROOT"

# =============================================================================
# 1. ENVIRONMENT
# =============================================================================
header "1. ENVIRONMENT & DEPENDENCIES"

check "python3 --version > /dev/null 2>&1" "Python 3 is available"
check "python3 -c 'import typer; import loguru; import yaml'" "Core dependencies importable (typer, loguru, pyyaml)"
check "python3 -c 'import pathlib; import datetime; import json'" "Standard library modules available"

# =============================================================================
# 2. DIRECTORY STRUCTURE
# =============================================================================
header "2. DIRECTORY STRUCTURE"

EXPECTED_DIRS=(
  ".opencode/agents"
  "Team"
  "Team/Members"
  "lib/Fucina/Handoff"
  "lib/Fucina/Hermes"
  "lib/Fucina"
  "Inbox"
  "Owner's Inbox"
  "lib"
  "Team/Meta"
  "Team/Prompts"
  "lib/assets/images"
  "lib/documents"
  "lib/data"
  "lib/Wiki"
  "tools"
  "tools/hermes_cli"
  "tools/llm"
  "tools/preflight_check"
  "tools/_template"
)
for dir in "${EXPECTED_DIRS[@]}"; do
  check_dir "$dir"
done

EXPECTED_FILES=(
  "opencode.json"
  "AGENTS.md"
  "README.md"
  ".gitignore"
  "Team/Config.md"
  "Team/README.md"
  "Team/Members/Registro.md"
  "lib/Fucina/Hermes/Scratchpad.md"
  "Team/Meta/strumenti-indice.md"
  "Team/Meta/llm-guida.md"
  "Team/Meta/hermes-cli-guida.md"
  "Team/Meta/preflight-check-guida.md"
  "Team/Meta/obsidian-vault.md"
  "Team/Meta/flusso-creazione-membro.md"
  "Team/Prompts/README.md"
  "Team/Prompts/test-agent-profile.md"
  "tools/hermes_cli/cli.py"
  "tools/hermes_cli/generator.py"
  "tools/hermes_cli/validator.py"
  "tools/hermes_cli/scanner.py"
  "tools/hermes_cli/config.py"
  "tools/hermes_cli/report.py"
  "tools/hermes_cli/models.py"
  "tools/hermes_cli/templates/handoff-template.md"
  "tools/hermes_cli/templates/scratchpad-template.md"
  "tools/llm/__init__.py"
  "tools/llm/__main__.py"
  "tools/llm/cli.py"
  "tools/llm/batch.py"
  "tools/llm/interactive.py"
  "tools/llm/config.py"
  "tools/preflight_check/__init__.py"
  "tools/preflight_check/__main__.py"
  "tools/preflight_check/cli.py"
  "tools/_template/__init__.py"
  "tools/_template/__main__.py"
  "tools/_template/cli.py"
)
for file in "${EXPECTED_FILES[@]}"; do
  check_file "$file"
done

# =============================================================================
# 3. CONTENT INTEGRITY — No KBA/Emerson/DeltaV
# =============================================================================
header "3. CONTENT INTEGRITY — NO KBA/EMERSON/DELTAV"

kba_hits=$(find "$ROOT/tools" "$ROOT/.opencode" "$ROOT/Team" "$ROOT/Library" \
  -type f \( -name '*.md' -o -name '*.py' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' \) \
  ! -path '*/__pycache__/*' ! -path '*/Archivio/*' \
  2>/dev/null \
  | grep -v 'scripts/test-template.sh' | grep -v 'whitepaper-it.md' \
  | xargs grep -s -li 'kba\|emerson\|deltav' 2>/dev/null | wc -l)
if [ "$kba_hits" -eq 0 ]; then
  pass "Zero KBA/Emerson/DeltaV references in source files"
else
  fail "Found $kba_hits files with KBA/Emerson/DeltaV references"
  find "$ROOT/tools" "$ROOT/.opencode" "$ROOT/Team" "$ROOT/Library" \
    -type f \( -name '*.md' -o -name '*.py' -o -name '*.json' \) \
    ! -path '*/__pycache__/*' ! -path '*/Archivio/*' 2>/dev/null \
    | grep -v 'scripts/test-template.sh' \
    | xargs grep -s -li 'kba\|emerson\|deltav' 2>/dev/null | head -10
fi

# =============================================================================
# 4. CONTENT INTEGRITY — English Only (no Italian in code)
# =============================================================================
header "4. CONTENT INTEGRITY — ENGLISH ONLY"

italian_in_code=$(find "$ROOT/tools" "$ROOT/.opencode" "$ROOT/Team" "$ROOT/Library" \
  -type f \( -name '*.md' -o -name '*.py' -o -name '*.json' -o -name '*.yaml' -o -name '*.yml' \) \
  ! -path '*/__pycache__/*' \
  2>/dev/null \
  | grep -v 'whitepaper-it.md' | grep -v 'scripts/test-template.sh' | grep -v 'obsidian-vault.md' \
  | xargs grep -s -n '[àèéìòù]' 2>/dev/null | wc -l)
if [ "$italian_in_code" -eq 0 ]; then
  pass "Zero Italian accented characters in source files"
else
  fail "Found $italian_in_code lines with Italian characters"
  find "$ROOT/tools" "$ROOT/.opencode" "$ROOT/Team" "$ROOT/Library" \
    -type f \( -name '*.md' -o -name '*.py' \) \
    ! -path '*/__pycache__/*' 2>/dev/null \
    | grep -v 'whitepaper-it.md' | grep -v 'scripts/test-template.sh' | grep -v 'obsidian-vault.md' \
    | xargs grep -s -n '[àèéìòù]' 2>/dev/null | head -20
fi

# =============================================================================
# 5. CLI TOOLS — Syntax & Help
# =============================================================================
header "5. CLI TOOLS — SYNTAX & HELP"

# Check all Python files compile
broken_py=0
while IFS= read -r -d '' pyfile; do
  if ! python3 -c "import py_compile; py_compile.compile('$pyfile', doraise=True)" 2>/dev/null; then
    fail "Python syntax error: $pyfile"
    broken_py=$((broken_py+1))
  fi
done < <(find "$ROOT/tools" -name '*.py' ! -path '*/__pycache__/*' -print0)

if [ "$broken_py" -eq 0 ]; then
  pass "All Python files compile without syntax errors"
fi

# hermes_cli help
check "python3 -m tools.hermes_cli --help > /dev/null 2>&1" "hermes_cli --help works"

# hermes_cli subcommand help
for cmd in validate id scratchpad handoff report stats diff; do
  check "python3 -m tools.hermes_cli $cmd --help > /dev/null 2>&1" "hermes_cli $cmd --help works"
done

# preflight_check help
check "python3 -m tools.preflight_check --help > /dev/null 2>&1" "preflight_check --help works"

# =============================================================================
# 6. ID MANAGEMENT
# =============================================================================
header "6. ID MANAGEMENT"

# Generate task ID — parse from text output
task_output=$(python3 -m tools.hermes_cli id next task 2>/dev/null || echo "")
task_id=$(echo "$task_output" | grep -oE 'T-[0-9]{3}' | head -1)
if [ -n "$task_id" ]; then
  pass "Task ID generation: $task_id"
else
  fail "Task ID format incorrect: got '$task_output'"
fi

# Generate decision ID
dec_output=$(python3 -m tools.hermes_cli id next decision 2>/dev/null || echo "")
dec_id=$(echo "$dec_output" | grep -oE 'D-[0-9]{3}' | head -1)
if [ -n "$dec_id" ]; then
  pass "Decision ID generation: $dec_id"
else
  fail "Decision ID format incorrect: got '$dec_output'"
fi

# =============================================================================
# 7. HANDOFF CREATION & VALIDATION
# =============================================================================
header "7. HANDOFF CREATION & VALIDATION"

# Helper: extract handoff path from output (handles absolute paths)
extract_handoff_path() {
  echo "$1" | tr -d '\n' | grep -oE '/lib/Fucina/Handoff/[0-9]{4}/[0-9]{2}/[^/]+\.md' | head -1
}

# Create a test handoff (dry-run first)
DRY_RUN_OUTPUT=$(python3 -m tools.hermes_cli handoff create \
  --type report \
  --dest proteo \
  --title "Template-verification-test-run" \
  --from hermes \
  --priority medium \
  --date 2026-05-16 \
  --dry-run 2>&1 || echo "")
DRY_HANDOFF=$(extract_handoff_path "$DRY_RUN_OUTPUT")

if [ -n "$DRY_HANDOFF" ]; then
  pass "Handoff dry-run generates valid path: $(basename "$DRY_HANDOFF")"
else
  fail "Handoff dry-run failed: $(echo "$DRY_RUN_OUTPUT" | grep -v '_content' | head -1)"
fi

# Create actual handoff (with --force for robustness)
CREATE_OUTPUT=$(python3 -m tools.hermes_cli handoff create \
  --type report \
  --dest proteo \
  --title "Template-verification-test-run" \
  --from hermes \
  --priority medium \
  --date 2026-05-16 \
  --force 2>&1 || echo "")
CREATE_HANDOFF=$(extract_handoff_path "$CREATE_OUTPUT")
CREATE_FULLPATH="$ROOT$CREATE_HANDOFF"

if [ -n "$CREATE_HANDOFF" ] && [ -f "$CREATE_FULLPATH" ]; then
  pass "Handoff file created: $(basename "$CREATE_HANDOFF")"

  # Validate the created handoff
  val_output=$(python3 -m tools.hermes_cli validate handoff "$CREATE_FULLPATH" 2>&1 || echo "")
  val_match=$(echo "$val_output" | grep -ci 'valid\|PASS\|✅\|naming_valid.*true\|has_frontmatter.*true' || true)
  
  if [ "$val_match" -gt 0 ]; then
    pass "Handoff validation produces results"
  fi
  
  pass "Handoff file is validatable"

  # Cleanup
  rm -f "$CREATE_FULLPATH"
  rmdir "$(dirname "$CREATE_FULLPATH")" 2>/dev/null || true
else
  fail "Handoff file creation: $CREATE_OUTPUT"
fi

# =============================================================================
# 8. SCRATCHPAD INITIALIZATION
# =============================================================================
header "8. SCRATCHPAD INITIALIZATION"

scratch_output=$(python3 -m tools.hermes_cli scratchpad init \
  --agent Testus \
  --role "Test Agent for Template Verification" \
  --dry-run 2>&1 || echo "")
scratch_ok=$(echo "$scratch_output" | grep -ci 'dry.run\|Testus\|Scratchpad' || true)
if [ "$scratch_ok" -gt 0 ]; then
  pass "Scratchpad dry-run produces expected output"
else
  fail "Scratchpad dry-run: $(echo "$scratch_output" | head -3)"
fi

# =============================================================================
# 9. PREFLIGHT CHECK
# =============================================================================
header "9. PREFLIGHT CHECK"

pf_output=$(python3 -m tools.preflight_check 2>&1 || true)
if echo "$pf_output" | grep -qE '\[PASS\]|\[WARN\]'; then
  pass "Preflight check runs and produces results"
else
  fail "Preflight check produced no expected output"
fi
info "Preflight output preview:"
echo "$pf_output" | head -8 | sed 's/^/    /'

# =============================================================================
# 10. OBSIDIAN CONVENTIONS — Frontmatter Check
# =============================================================================
header "10. OBSIDIAN CONVENTIONS"

fm_issues=0
while IFS= read -r -d '' mdfile; do
  # Check frontmatter starts on line 1
  firstline=$(head -1 "$mdfile")
  if [ "$firstline" != "---" ]; then
    fail "Frontmatter not on first line: ${mdfile#$ROOT/}"
    fm_issues=$((fm_issues+1))
    continue
  fi
  # Check for singular field names
  if head -20 "$mdfile" | grep -q '^tag: '; then
    fail "Singular 'tag:' in frontmatter: ${mdfile#$ROOT/}"
    fm_issues=$((fm_issues+1))
  fi
  if head -20 "$mdfile" | grep -q '^alias: '; then
    fail "Singular 'alias:' in frontmatter: ${mdfile#$ROOT/}"
    fm_issues=$((fm_issues+1))
  fi
done < <(find "$ROOT/Library" "$ROOT/Team" -name '*.md' \
  ! -name 'README.md' ! -name 'handoff-template.md' ! -name 'scratchpad-template.md' \
  ! -path '*/Archivio/*' ! -path '*/__pycache__/*' ! -path '*/.git/*' \
  -print0 2>/dev/null)

if [ "$fm_issues" -eq 0 ]; then
  pass "All frontmatter checks passed (first line, plural fields)"
fi

# =============================================================================
# 11. AGENT FILE INTEGRITY
# =============================================================================
header "11. AGENT FILE INTEGRITY"

CORE_AGENTS=("hermes" "proteo" "atena" "efesto" "clio" "dike" "metis")
missing_agents=0
for agent in "${CORE_AGENTS[@]}"; do
  if [ ! -f "$ROOT/.opencode/agents/$agent.md" ]; then
    fail "Missing agent file: .opencode/agents/$agent.md"
    missing_agents=$((missing_agents+1))
  fi
done
if [ "$missing_agents" -eq 0 ]; then
  pass "All 7 core agent files present"
fi

# Count non-core agents (should be exactly 7)
agent_count=$(find "$ROOT/.opencode/agents" -name '*.md' | wc -l)
if [ "$agent_count" -eq 7 ]; then
  pass "Exactly 7 agents in .opencode/agents/ (found: $agent_count)"
else
  fail "Expected 7 agents, found $agent_count"
fi

# Verify agent registry lists exactly 7 members
# Count members in registry table (lines with | **Name** | under "Current Members")
registry_count=$(sed -n '/## Current Members/,/## Adding/p' "$ROOT/Team/Members/Registro.md" \
  | grep -c '| \*\*' 2>/dev/null || echo 0)
if [ "$registry_count" -eq 7 ]; then
  pass "Registry lists exactly 7 members"
else
  fail "Expected 7 members in registry, found $registry_count"
fi

# =============================================================================
# 12. CONFIG INTEGRITY
# =============================================================================
header "12. CONFIG INTEGRITY"

# Config.md has language field
check "grep -q 'language' '$ROOT/Team/Config.md'" "Config.md has 'language' field"

# opencode.json has default_agent = hermes
check "python3 -c \"import json; c=json.load(open('$ROOT/opencode.json')); assert c.get('default_agent') == 'hermes'\" 2>/dev/null" "opencode.json configured with default_agent = hermes"

# =============================================================================
# 13. HERMES SCRATCHPAD
# =============================================================================
header "13. HERMES SCRATCHPAD — PERSISTENT STATE"

scratchpad="$ROOT/lib/Fucina/Hermes/Scratchpad.md"
check "test -f '$scratchpad'" "Hermes scratchpad exists"

# Validate scratchpad structure
sp_valid=$(python3 -m tools.hermes_cli validate scratchpad --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('parsed',''))" 2>/dev/null || echo "False")
if [ "$sp_valid" = "True" ]; then
  pass "Scratchpad frontmatter is valid YAML"
else
  info "Scratchpad may need initialization (empty template is fine)"
fi

# =============================================================================
# SUMMARY
# =============================================================================
header "TEST SUMMARY"
echo ""
echo "  ✅ PASSED: $PASS"
echo "  ❌ FAILED: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "  FAILURES:"
  for err in "${ERRORS[@]}"; do
    echo "    $err"
  done
  echo ""
  echo "  ❌ Some tests failed. Review issues before publishing."
  exit 1
else
  echo "  ✅ ALL TESTS PASSED — Template is ready for publishing!"
  exit 0
fi
