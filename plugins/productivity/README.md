# productivity

Claude Code skills and commands for non-code workflow.

```
/plugin marketplace add bluehoodie/skills
/plugin install productivity@bluehoodie
```

---

# Set up nightly memory consolidation

This is what most people install this plugin for. Three steps, once.

## 1. Install the plugin

The two commands above, in Claude Code.

## 2. Create a routine in the Claude Desktop app

Open Claude Desktop → **Settings → Routines → New routine**, and set:

| Field | Value |
|---|---|
| **Schedule** | Daily, `03:17` — any hour your Mac is awake and you are not working |
| **Working directory** | Your home directory. **Not a project directory** — see the warning below |
| **Mode** | Local agent mode |

## 3. Paste this as the routine's prompt

```
Consolidate my Claude Code memories by running /productivity:dream.

Run from my home directory, not from inside a project. A dream never
consolidates the project it is running in, so pointing this at a real project
would silently leave that project's memories un-consolidated forever.

Print the roll-up it produces and nothing else — one line per project, plus any
projects the ten-per-pass cap deferred. Do not summarise the memories
themselves, and do not consolidate anything by hand if the pass reports nothing
to do.

If any project reports deletions, say that /productivity:dream-restore can undo
that pass.
```

That's it. Every night it sweeps every project you have worked in, tidies each
one's memories, and commits the result so you can undo it.

> **Two things that will bite you if you skip them.**
>
> **The routine must run in local agent mode.** A cloud run cannot see
> `~/.claude/projects` and will cheerfully report that every project is clean.
>
> **Point it at your home directory, not a project.** Dream never consolidates
> the project it is running from — that session is still writing its own
> transcript, so it would look permanently dirty. Run the routine from a real
> project and that project's memories are never consolidated, silently, forever.

## Checking on it

```
/productivity:dream-status
```

Shows which projects are due, how stale each one is, and how many memories each
holds. Read-only.

## Undoing a pass

```
/productivity:dream-restore
```

Every memory directory dream touches is a git repository and every pass is one
commit, so nothing it removes is lost. The command lists recent passes — three
per project — and you pick which project and which pass to undo. Memories
written *after* that pass are kept: a revert undoes that commit, not everything
since.

To look before you leap:

```bash
git -C ~/.claude/projects/<slug>/memory log -p
```

---

# What dream actually does

Each pass surveys every project under `~/.claude/projects/`, and for each one
that has seen session activity since its last pass, it merges duplicate
memories, deletes stale ones, rewrites what has drifted, and rebuilds that
project's `MEMORY.md` index.

**Deleting is normal, not an error.** A pass that finds a memory stale or
superseded removes the file, and errs toward keeping anything it cannot verify —
memories about you and your preferences are never deleted for failing a
code check, because they were never claims about code. Every pass is a git
commit, so nothing it removes is unrecoverable.

You can also just run `/productivity:dream` by hand whenever you like. The
routine is only a convenience; it is the same pass.

**On the very first run** there is no "last pass", so dream starts from a
seven-day baseline: projects you worked in during the last week get
consolidated, older ones are marked as already seen. A fresh install will not
chew through years of history.

**At most 10 projects per pass.** Any beyond that are named in the summary and
picked up next run, so a backlog drains over several nights instead of being
dropped.

**A missed run costs nothing.** If the machine is asleep the pass just does not
happen, and the next one covers the wider window.

---

## Skills

- [dream](./skills/dream/SKILL.md) — machine-wide memory consolidation, described
  above.
- [context-tune](./skills/context-tune/SKILL.md) — audit and rightsize a project's
  CLAUDE.md files, memories, and skills against the Claude 5 context-engineering
  principles.

## Commands

- [dream-status](./commands/dream-status.md) — which projects need a dream, and the
  state of the memory stores.
- [dream-restore](./commands/dream-restore.md) — undo a dream by reverting that
  project's memory commit.
