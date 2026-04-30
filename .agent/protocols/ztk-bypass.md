# ztk-Bypass Protocol — when to use lossless tools

> **For high-stakes context-dependent reads (code review, security audit,
> architecture analysis, file discovery, log archaeology), prefer the
> Read / Glob / Grep tools over Bash. ztk compresses Bash output and may
> drop context that matters for these tasks.**

This protocol exists because ztk (the bash-output compression proxy
configured globally via `~/.claude/settings.json` PreToolUse hook on Bash)
runs lossy filters on common commands — git diff, ls -la, grep, find,
cargo test, pytest, etc. The compression is safe for routine engineering
work but can drop signal that high-stakes agents need.

The Read / Glob / Grep tools bypass Bash entirely, so ztk doesn't intercept
their outputs — these tools deliver content losslessly to the model.

## Failure modes ztk creates (and the lossless alternative)

### 1. Code review with context dependence

**Risk:** `git diff` filter keeps **only 1 line of context above/below
each change**. Reviewer sees the change but loses the function's
purpose, related comments, surrounding logic that establishes
invariants.

**Example failure:** reviewer APPROVES `if (x > 5)` → `if (x >= 5)`
not realizing the comment 4 lines above said "must match RFC limit
exactly" — comment dropped by ztk's context trim.

**Use instead:**
- `Read` the file directly (lossless full content)
- `Grep` the file for the changed function name to see full context
- For diff context: `git show HEAD:path/to/file` then Read both — or
  use Read tool's full file output with line numbers as cross-reference

### 2. File discovery via `ls -la`

**Risk:** ztk's `ls_long` filter outputs counts + "notable" items
(executables, symlinks, unusual perms). Regular files with normal
perms collapse into a count.

**Example failure:** agent runs `ls -la ~/.aws/` to check if
`credentials` exists. ztk says "5 files, 1 dir, 2 notable: config
(executable), credentials.bak (group-writable)." If `credentials`
is a normal file with normal perms, **its name doesn't appear**.

**Use instead:**
- `Glob` with pattern `~/.aws/*` (lossless directory listing)
- `Glob` with `~/.aws/credentials*` for specific file existence
- For specific file checks: `Read` and check for "file not found"

### 3. Long log archaeology

**Risk:** Per-command budgets cap output and truncate with a marker:
- `git log` capped at 4000 tokens
- `git diff` capped at 8000 tokens
- `grep` / `rg` capped at 2000 tokens
- `find` capped at 800 tokens

The model should notice the truncation marker `[ztk: N more tokens
omitted]` and re-query with narrower scope — but if the agent
doesn't notice, it makes decisions on partial data.

**Use instead:**
- For text search: `Grep` tool (no truncation, returns matches directly)
- For file discovery: `Glob` tool (no truncation, returns paths)
- For commit-history archaeology: scope `git log` first
  (`--grep="auth"`, `-S "function_name"`, `--since="2 weeks ago"`)
  before reading

### 4. Test debugging with pass-list dependence

**Risk:** `cargo test` / `pytest` / `jest` filter collapses passing
tests to a count. You can't see WHICH tests passed by name.

**Example failure:** agent needs to confirm `test_session_timeout`
passed in a 50-test run. ztk shows "✓ 47 passed, 3 failed: [list]"
— the 47 names are gone.

**Note:** failure details ARE preserved verbatim. The asymmetry is
deliberate (failures matter more than passes for debugging).

**Use instead:**
- Run the specific test directly: `pytest tests/auth/test_session.py::test_session_timeout` (small output, ztk bypasses by guard <80 bytes)
- Use the test framework's own filter: `pytest -k session_timeout -v`

### 5. Cache staleness (subtle)

**Risk:** ztk caches command outputs with TTLs (30s for `git status`,
120s for tests, 300s for `git log`). If you edit files via your IDE
or external process, ztk's cache may return stale results to the
agent.

**Use instead:**
- For up-to-date file state: `Read` the file directly
- For up-to-date directory state: `Glob`
- To force-refresh ztk: clear `~/.ztk/cache/` (manual)

## Decision rule for agents

Per task type, prefer the listed tool:

| Task | Preferred tool | Why |
|---|---|---|
| Reading source code | `Read` | Lossless, full content with line numbers |
| Finding files by pattern | `Glob` | Lossless, returns paths |
| Searching text in codebase | `Grep` | Lossless, returns line+context |
| Inspecting a diff for review | `Read` source files + `Bash` diff | Hybrid: ztk shows changed lines, Read shows full context |
| Inspecting test output (failures) | `Bash` (pytest, etc.) | ztk preserves failure detail verbatim — no risk |
| Inspecting test output (which passed by name) | `Bash` with `-v` flag + scoped pattern | Workaround: explicit test names appear in small outputs |
| Long log archaeology | `Bash` with scoping flags first (`--grep`, `-S`, `--since`) | Avoid hitting the 4000-token cap |
| Finding a specific file in a dir | `Glob` | Lossless, returns paths directly |
| Counting files in a dir | `Bash ls` | ztk's count is correct; quality not impacted |

## When ztk compression is provably safe

Don't panic-bypass for everything. ztk is safe for:
- Routine `git status` (clean tree → small output → bypassed by guard)
- Test runs where you only care about pass/fail summary
- `ls` (without `-l`) for quick "what's roughly in this dir?"
- Any output containing error markers (stack traces, panics, etc.) —
  ztk preserves these verbatim
- JSON / YAML / TOML file reads — ztk bypasses these by extension
- Anything ztk doesn't recognize — passes through untouched

## How agents should apply this

When a task is one of the high-stakes types listed in §1-5, the agent
should:

1. **Mention the choice explicitly** in the dispatch reasoning ("Using
   Read instead of `cat` here because reviewer-grade context matters.")
2. **Use the lossless tool** as the primary read path
3. **Use Bash + ztk** only when the lossy path is sufficient
   (e.g., counting files, checking pass/fail summary)
4. **If a Bash output shows the `[ztk: N more tokens omitted]` marker**:
   re-run with narrower scope OR switch to the lossless tool

This is not a "ztk is unsafe, avoid it" rule — it's "use the right
tool for the task." For most tasks, ztk's compression is pure win
(cuts tokens, no quality loss). For the listed high-stakes types,
the few-token savings aren't worth the potential information loss.

## Anti-patterns

- **Bypassing ztk for routine work** — wastes the value ztk provides
  on noisy outputs. Don't go to lossless tools for every Bash call.
- **Trusting truncated output silently** — if you see the ztk
  truncation marker, ALWAYS act on it (re-query or switch tool).
  Don't make decisions on partial data without flagging it.
- **Forgetting Glob/Grep/Read exist** — these are the canonical
  lossless paths. They're tools, not workarounds.
- **Disabling ztk globally to "be safe"** — over-corrects. Per-task
  routing is the right discipline.

## Reference

- ztk article: `examples/agentic-stack-resource/ztk_token.md`
- ztk repo: `https://github.com/codejunkie99/ztk`
- ztk hook: `~/.claude/settings.json` `hooks.PreToolUse[matcher=Bash]`
