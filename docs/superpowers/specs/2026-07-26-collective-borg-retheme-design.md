# Re-theme `dreamscape` as `collective`

**Date:** 2026-07-26
**Status:** approved design, not yet implemented
**Scope:** one plugin — `plugins/dreamscape/` — plus the two files that index it.

## What this is

`dreamscape` shares Claude Code memories across a team through the repo. The mechanics
are staying exactly as they are. This changes what everything is *called*, from Borg
terminology, and takes the plugin to 1.0.0 as a deliberate breaking rename.

The theme is not arbitrary. The shared corpus is already `.collective-memory/`, a name
chosen before this idea existed, and the plugin's actual behaviour — many individuals'
knowledge merging into one shared body that everyone then draws from — is the metaphor
already. Renaming makes the existing design legible rather than decorating it.

## Naming

| Now | Becomes |
|---|---|
| plugin `dreamscape` | `collective` |
| `promote` (SessionEnd subcommand) | `assimilate` |
| `/dreamscape:memory-pull` | `/collective:adapt` |
| `/dreamscape:memory-status` | `/collective:status` |
| `/dreamscape:memory-share` | `/collective:reclaim` |
| `DREAMSCAPE_*` | `COLLECTIVE_*` |
| `~/.claude/dreamscape-state/<project>/` | `~/.claude/collective-state/<project>/` |
| PR branch `dreamscape/<date>-<key>` | `assimilate/<date>-<key>` |
| `scripts/dreamscape.py` | `scripts/collective.py` |
| `scripts/test_dreamscape.py` | `scripts/test_collective.py` |
| version `0.3.0` | `1.0.0` |

### Why `assimilate` is the outbound path

Canon: "your biological and technological distinctiveness will be added to our own."
Assimilation is the collective absorbing an individual — never a drone shopping the hive.
It is also the automatic, detached, never-asked SessionEnd path, which is what
assimilation should feel like.

The counter-argument, recorded because it is a real one: `assimilate` is the theme's best
word and `promote` is a hook nobody ever types, so the word is spent where no user reads
it. That lost 2–1 to the direction argument.

### Why inbound is `/adapt`

One drone learns, every drone adapts. The direction is inbound, it is voluntary, and
someone who has never seen Star Trek still reads "adapt" as taking on new knowledge —
which is exactly what the command does. Runner-up was `/link`, weaker on direction.

### Why `/collective:status` rather than `/collective`

Plugin commands namespace as `/<plugin>:<command>`, so naming the file `collective.md`
produces `/collective:collective`. The namespace already carries the theme; the leaf
should carry the meaning.

### Why `/collective:reclaim`

It echoes the Borg Reclamation Project — repair what was rejected as unsuitable — and
that is literally the mechanic: memories the credential scanner refused, fixed by hand,
sent back through the gates on the next pass.

This also corrects a name that is wrong today. `/memory-share` shares nothing. It triages
the scanner's quarantine. The rename fixes a real mislabel that happens to be on-theme.

## What does not change

**`.collective-memory/`.** It is tracked in every repo that has adopted the plugin.
Renaming it requires every teammate's checkout to move at once, for zero gain, and it is
already the most on-theme name in the codebase.

**The sibling `dream` plugin.** Untouched. The `dream` / `dreamscape` name pairing is
lost, which is acceptable: the two were always independent plugins that merely compose
well, and dreamscape's own README already documents that neither requires the other.

**Every mechanic.** The settle window, the four gates, the credential scanner's patterns,
the graphify pass, git-plumbing PR construction, `pulledFrom` lineage, the pull-based
consent model. No behaviour changes in this work.

## Prose and output

Status output takes the theme; error text does not.

```
collective      7   (.collective-memory/)
  clob-v2-order-signing
  grafana-tenant-split

settling        3   (assimilable once unchanged for 24h)
individual      2   (never assimilated: type user or feedback)
pending         0
quarantined     0
```

`personal` → `individual` is the one relabel that gets funnier without getting less
clear. `blocked` → `quarantined` in this listing only; the JSON state file keeps its
`blocked.json` name and the word "blocked" stays in every error string.

PR title becomes `collective: assimilate N memories`. PR body opens "Assimilated from
local Claude Code memory."

### Deliberately left literal

Everything on the security path — `blocked`, `credential`, `secret`, the scanner's
reason strings — plus `--dry-run`, `SETTLE_HOURS`, `MIN_CONFIDENCE`, the word "memory",
and all error and failure text. Nobody should have to decode a joke to find out that a
secret nearly shipped.

No "resistance is futile" anywhere near `/collective:adapt`. That command is
consent-first by design, and the tagline would lie about the mechanic.

## Migration

A clean break, with exactly one carve-out.

| What | Cost when it breaks | Handling |
|---|---|---|
| plugin id | installed users silently stop getting updates | announce in both READMEs + CHANGELOG; ship as 1.0.0; do not dual-publish |
| state directory | memories re-evaluated, duplicate PRs, pull list shows all as new | accept — self-healing and visible |
| `COLLECTIVE_*` env vars | setting ignored, default applies | accept, except below |
| `DREAMSCAPE_DRY_RUN` | **silent** — real PRs open into a team repo from a detached hook | read both prefixes |

`DRY_RUN` is the only one whose failure is both silent and outward-facing: someone
running `DREAMSCAPE_DRY_RUN=1` to test safely upgrades, the variable stops being read,
and the next SessionEnd pushes real branches. Three lines:

```python
def env(name):  # ponytail: DRY_RUN footgun only; drop when nobody is on 0.3.0
    return os.environ.get(f"COLLECTIVE_{name}") or os.environ.get(f"DREAMSCAPE_{name}")
```

Applied to `DRY_RUN` alone. Every other variable reads the new prefix only. If the fallback
is unwanted, deleting it is a one-line change and the rest of this spec is unaffected.

## Files

Renames use `git mv` so history follows.

```
plugins/dreamscape/                    → plugins/collective/
  .claude-plugin/plugin.json             name, description, homepage, keywords, 1.0.0
  hooks/hooks.json                       script path + verb assimilate
  commands/memory-pull.md              → commands/adapt.md
  commands/memory-status.md            → commands/status.md
  commands/memory-share.md             → commands/reclaim.md
  scripts/dreamscape.py                → scripts/collective.py
  scripts/test_dreamscape.py           → scripts/test_collective.py
  README.md                              full rewrite of names, prose intact
  CHANGELOG.md                           1.0.0 entry documenting the break
.claude-plugin/marketplace.json          name, source, description, keywords
README.md                                heading, links, install line, prose
```

### Script internals

Rename in `collective.py`: the module docstring; every `DREAMSCAPE_*` read; `state_dir()`
path segment; `promote()` → `assimilate()`; `pull()` → `adapt()` with `take()` and
`mark_pulled()` following; the verb dispatch in `main()`; PR title, body and branch
prefix; every status label; and the `/memory-*` command references in docstrings and
comments.

Also rename for coherence, since this file is read by users: `TEAM_SUBDIR` →
`COLLECTIVE_SUBDIR`, `team_dir()` → `collective_dir()`, `PERSONAL_TYPES` →
`INDIVIDUAL_TYPES`, `personal()` → `individual()`. Local variables are left alone —
renaming them is churn with no reader.

The frontmatter keys `sharedBy`, `promotedAt` and `pulledFrom` **do not change**. They
exist in `.collective-memory/` files already committed to team repos, and `pulledFrom`
in local memories is what stops a pulled memory being re-filed as a duplicate. Renaming
them is a data migration wearing a rename's clothing.

The subcommand `adapt --take` / `--mark` interface stays as-is; only the verb changes.
`commands/adapt.md` must be updated to call `adapt` rather than `pull`.

## Success criteria

1. `python3 plugins/collective/scripts/test_collective.py` passes, with every test
   renamed to the new verbs, env vars and state path — not merely re-pointed at them.
2. `claude plugin validate . --strict` passes clean.
3. `claude plugin validate plugins/collective --strict` passes clean.
4. `grep -ri dreamscape plugins/ README.md .claude-plugin/` returns only the intentional
   migration notes in `CHANGELOG.md`, the two READMEs, and the `DRY_RUN` fallback.
5. Both READMEs list all three commands under their new names, per the repo's
   stay-in-sync rules in `CLAUDE.md`.
6. Every command file still has YAML frontmatter with a `description`.
7. No `README.md` lands in `commands/` — every `.md` there ships as a command.

## Not doing

- **No behaviour changes.** Anything that looks like a fix during this work gets noted,
  not merged in. A rename that also changes semantics is unreviewable.
- **No re-theme of `dream`.** Out of scope; the user asked about one plugin.
- **No compatibility shim for the plugin id.** There is no alias mechanism, and
  dual-publishing two marketplace entries for one plugin is worse than one announced break.
- **No renaming of `.collective-memory/` or the frontmatter keys.** Both are committed
  data in other people's repos.
