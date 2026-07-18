# agent-cross-check

[한국어](README.md) | **English**

A **mutual health-check skill** for Claude Code ↔ OpenAI Codex. Each agent
diagnoses the *other* one's operating state — because an agent cannot fix
itself: zombie processes of your own session only go away when *you* restart,
and files locked by the other app can only be cleaned while that app is closed.

Distilled from a real 3-day Codex operating-system overhaul (July 2026,
~12.8 GB reclaimed) into a reusable diagnostic skill.

## What it checks

- **Process genealogy** — classifies every node/bun process by owner
  (Codex app / Codex CLI / Claude / other); detects accumulated leftover
  session servers and orphaned processes (dead parent)
- **Windows sandbox** — watches for long-running
  `codex-windows-sandbox-setup.exe` (recursive ACL storms over broad
  trust roots)
- **Config regression** — omo codegraph/lsp toggles and hook-diet state
  (plugin auto-updates tend to silently reset these to defaults)
- **Storage growth** — telemetry DB size, stale plugin version caches
- **Security** — plaintext secret scan (values are *never* printed — only
  location, key name, and length), overly-broad trust entries
  (home/drive roots), and a baseline diff that flags newly-introduced
  hooks / MCP servers / marketplace source changes

## Three principles

1. **Diagnosis is automatic and read-only; any fix, deletion, or process
   kill happens only after explicit user approval** (dry-run with exact
   counts/sizes → approval → post-verification)
2. **Respect the source of truth (SOT)** — settings are fixed at their
   canonical location only (e.g. omo settings live in `~/.omo/config.jsonc`;
   patching the derived config just gets reverted by the next migration)
3. **Never touch the operating fabric** — conversation history, live
   marketplace sources, hooks/memory/skills directories are excluded from
   every prescription

See [SKILL.md](SKILL.md) for thresholds (based on July 2026 measurements),
prescription recipes, and the full no-touch list. (SKILL.md is in Korean —
it is the runtime prompt for a Korean-language workflow.)

## Install

```bash
# Claude Code side (canonical copy)
git clone https://github.com/newskool4d-sketch/agent-cross-check "$HOME/.claude/skills/코덱스점검"

# Codex side (pointer skill)
mkdir -p "$HOME/.codex/skills/claude-check"
cp "$HOME/.claude/skills/코덱스점검/pointers/claude-check.SKILL.md" "$HOME/.codex/skills/claude-check/SKILL.md"
```

Requirements: Python 3.11+ (`tomllib`), `psutil`. Windows-focused
(process attribution and sandbox checks assume the Windows builds of
Claude Code / Codex), though the core logic is `Path.home()`-based.

## Use

- In a Claude session: say "점검" / "코덱스 점검" → diagnoses Codex
- In a Codex session: say "클로드 점검" / "claude-check" → diagnoses Claude
- Manual run:

```bash
PYTHONIOENCODING=utf-8 python scripts/check_core.py --target codex|claude|both
```

The report ends with a verdict (`✅ all clear` or `⚠️ N items to review`),
each warning paired with its prescription. Executing a prescription is
always a separate, user-approved step.
