---
name: context-tune
description: "Audit and rightsize a project's CLAUDE.md files, memories, and skills against the Claude 5 context-engineering principles (rules→judgment, progressive disclosure, no repetition, rich references). Use when the user says /context-tune, 'tune my claude.md', 'audit my context', 'my CLAUDE.md is bloated', or after a project's instruction files have grown large."
trigger: /context-tune
---

# /context-tune

Applies the Claude 5 context-engineering principles to this project's instruction context.

Source: https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models

## Usage

```
/context-tune              # audit current project, report, then apply on approval
/context-tune --report     # audit only, change nothing
/context-tune --apply      # audit and apply without the approval pause
/context-tune <path>       # target a specific directory
```

## The principles (the rubric)

| # | Then | Now |
|---|------|-----|
| 1 | Prescriptive rules ("never write multi-line docstrings") | State the goal, trust judgment ("match the surrounding code's comment density, naming, idiom") |
| 2 | Usage examples for every tool | Expressive interfaces — descriptive names, enums, typed params carry the guidance |
| 3 | Everything loaded upfront | Progressive disclosure — detail lives in skills/reference files loaded when needed |
| 4 | Same instruction repeated in 3 places | Say it once, in the place closest to where it's used |
| 5 | Manual memory bookkeeping in CLAUDE.md | Auto-memory handles it; CLAUDE.md keeps only durable repo facts |
| 6 | Prose specs | Rich references — real code, test suites, rubrics, mockups |

Architecture targets:
- **CLAUDE.md** — lightweight. Repo *gotchas* only: what's surprising, what breaks, what's non-obvious. Not what Claude can read from the code.
- **Skills** — team-specific opinions and practices. Split long ones into multiple files.
- **References** — @-mentioned specs, code, mockups. Prefer code over description.

## Steps

### 1. Inventory

Find, in the target directory:
- `CLAUDE.md`, `AGENTS.md`, and any nested ones (`**/CLAUDE.md`)
- `.claude/skills/**/SKILL.md`
- memory files (`.claude/**/memory/`, `MEMORY.md`)
- `@`-referenced files pulled in by the above

Read every one in full. Report line counts before you touch anything.

### 2. Audit each line against the rubric

Classify every instruction as exactly one of:

- **KEEP** — a non-obvious repo gotcha, a hard constraint, or a fact that can't be derived from the code.
- **SOFTEN** — a prescriptive micro-rule that should become a goal statement (rule 1).
- **DEFER** — detail that belongs in a skill or reference file, not in always-loaded context (rule 3).
- **DEDUPE** — stated elsewhere already; keep the copy closest to its point of use (rule 4).
- **CUT** — derivable from the code, obvious to any competent engineer, stale, or memory-bookkeeping the auto-memory system already covers (rules 5, and general).

For CUT, be strict. The default question is *"would Claude get this wrong without the line?"* If no, cut it.

### 3. Report

Show a table: file, line, verdict, one-line reason, proposed replacement. Then the projected before/after line counts.

Stop here if `--report`.

### 4. Apply

With approval (or `--apply`):

- Rewrite CLAUDE.md files keeping only KEEP + SOFTEN'd lines.
- Move DEFER'd content into `.claude/skills/<topic>/SKILL.md` with a `description` written so it triggers on the right task — that description is the only thing always in context, so it must earn the load.
- Replace prose specs with `@path/to/real/code.ts` pointers where the code says it better (rule 6).
- Leave a one-line note in the response naming what moved where.

Never delete a file outright — empty CLAUDE.md files get a stub, deferred content always lands somewhere before its source is cut.

### 5. Verify

- Every `@`-reference resolves.
- Every new skill's `description` names its trigger conditions.
- Nothing classified DEFER was lost — grep the new location for it.
- Report the actual before/after line counts, not the projected ones.

## Notes

- Global `~/.claude/CLAUDE.md` is out of scope unless the user points at it explicitly. It's their standing preferences, not project context.
- User preferences ("always ask before X", "I hate Y") are KEEP even when they read like micro-rules — rule 1 is about trusting Claude's judgment on *craft*, not about overriding what the user asked for.
- Claude Code's built-in `/doctor` does a similar audit on skills and system prompts; mention it if the user wants the built-in path.
