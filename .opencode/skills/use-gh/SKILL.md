---
name: use-gh
description: "Use ONLY when interacting with GitHub API: repos, issues, PRs, stars, forks, labels, contents, searches. Covers `gh` CLI and curl with token auth. NEVER create files with payload code as filenames — always use proper temp paths in Library/."
---

# use-gh — GitHub API interactions

Clean, safe patterns for GitHub API access from within Team Olimpo.

## Authentication

| Method | How |
|--------|-----|
| **`gh` CLI** | `gh auth status` first. If invalid → `gh auth login -h github.com` |
| **curl with token** | Token in `~/.config/gh/hosts.yml` or prompt user for `$GITHUB_TOKEN` |
| **.env** | Add `GITHUB_TOKEN=ghp_...` to `Library/System/Poros/.env` if needed |

Never hardcode tokens. Never write tokens into files committed to git.

## `gh` CLI patterns

```bash
# Repo info
gh api repos/{owner}/{repo}

# Issues
gh issue list -R {owner}/{repo} --limit 10
gh issue view {number} -R {owner}/{repo}

# PRs
gh pr list -R {owner}/{repo} --state open
gh pr view {number} -R {owner}/{repo}

# Stars / forks / open issues (compact)
gh api repos/{owner}/{repo} --jq '{stars: .stargazers_count, forks: .forks_count, issues: .open_issues_count}'
```

## curl patterns (when `gh` not available)

Always use `executor_run` for curl calls. Use `-sS` (silent but show errors), never `-c` (cookie jar) unless you *explicitly* need cookies.

```bash
# GET with token
curl -sS -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/repos/{owner}/{repo}

# POST
curl -sS -X POST -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"...","body":"..."}' \
  https://api.github.com/repos/{owner}/{repo}/issues

# Paginated results
curl -sS -H "Authorization: token ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/{owner}/{repo}/issues?per_page=100&page=1"
```

## 🔴 ANTI-PATTERNS — what NOT to do

| ❌ Don't | ✅ Do |
|----------|-------|
| `curl -c "python code here"` — creates files with payload as filename | `gh api ...` or `curl -sS ... \| python -c "..."` with proper piping |
| Write temp files to project root | Use `Library/System/Poros/` or `executor_run` with pipe |
| Leave `.cookie` / `.netrc` artifacts in `TeamOlimpo/` | Clean up after yourself, or skip file-based auth entirely |
| `curl ... \| python -c "..."` with the full script inline in the `-c` arg | Pipe to a temp script file or use `python3 -c` with a short, readable one-liner (≤3 lines) |
| Use `curl ... > file.py && python file.py` | Use `curl ... \| python3` directly |

## Temp file hygiene

If you *must* write an intermediate file:

```bash
TMPDIR="Library/System/Poros/tmp" && mkdir -p "$TMPDIR"
curl -sS ... > "$TMPDIR/gh-response.json"
# ... process it ...
rm -f "$TMPDIR/gh-response.json"
```

Always clean up. Never leave artifacts in `/home/stra/TeamOlimpo/`.

## Chaining with python

For JSON processing, pipe to `python3 -m json.tool` or `python3 -c`:

```bash
# Stars/forks/issues count (the RIGHT way)
gh api repos/{owner}/{repo} --jq '{stars: .stargazers_count, forks: .forks_count, issues: .open_issues_count}'

# Or via curl+python (short pipeline, no temp files)
curl -sS -H "Authorization: token ${GITHUB_TOKEN}" \
  https://api.github.com/repos/{owner}/{repo} \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Stars: {d[\"stargazers_count\"]}')"
```

If the pipeline is long (complex multi-line processing), write a temp script to `Library/System/Poros/tmp/` — never inline it in the shell command as a filename.

## When to use this skill

- Request involves GitHub repos, issues, PRs, stars, forks, labels
- Request is about GitHub API authentication
- Request asks about GitHub data retrieval
- **Trigger keywords:** `gh`, `github`, `api`, `repo`, `issue`, `pr`, `stars`, `forks`, `token`
