# productivity

Claude Code skills and commands for non-code workflow.

```
/plugin marketplace add bluehoodie/skills
/plugin install productivity@bluehoodie
```

## Skills

- [context-tune](./skills/context-tune/SKILL.md) — audit and rightsize a project's
  CLAUDE.md files, memories, and skills against the Claude 5 context-engineering
  principles.
- [dream](./skills/dream/SKILL.md) — machine-wide memory consolidation. Surveys every
  project for new session activity, then merges, deletes and reindexes each one's
  memories, committing every pass to git. Deletion is a normal outcome, not an
  error: a pass that finds a memory stale or superseded may remove the file, and
  it errs toward keeping anything it cannot verify. Every pass is a git commit,
  so nothing it removes is unrecoverable — see *Recovering from a bad dream*
  below.

## Commands

- [dream-status](./commands/dream-status.md) — which projects need a dream, and the
  state of the memory stores.
- [dream-restore](./commands/dream-restore.md) — undo a dream by reverting that
  project's memory commit.

## Running dream on a schedule

`/productivity:dream` is a manual command — run it at the end of a working stretch
and it sweeps every project that has seen activity since its last pass.

On the very first run there is no "last pass", so dream starts from a seven-day
baseline: projects you have worked in during the last week are consolidated,
older ones are marked as already seen. That keeps a fresh install from
consolidating years of history in one go.

To make it recurring, create a scheduled routine in the Claude Desktop app with
the prompt `/productivity:dream`. Nothing is installed on your machine by this
plugin; the schedule lives in Claude, not in launchd or cron.

Three things worth knowing before you schedule it:

- **It must be a local-agent-mode routine.** A cloud run has no
  `~/.claude/projects` to read and will report every project clean.
- **Point the routine at a directory you do not work in** — `$HOME` is the
  obvious choice. A dream never consolidates the project it is running from,
  because that session is still writing its own transcript and would be dirty
  forever. Run the routine from a real project and you silently starve that
  project.
- **A missed run costs nothing.** If the machine is asleep the pass does not
  happen, and the next one covers the wider window. Markers are per-project
  high-water marks, not a schedule.

Each pass consolidates at most 10 projects. Any beyond that stay dirty and are
named in the run summary, so a long backlog drains over several runs rather than
being dropped.

## Recovering from a bad dream

Every memory directory a dream touches becomes a git repository, and every pass is
one commit. To see what last night changed:

```bash
git -C ~/.claude/projects/<slug>/memory log -p
```

To undo it, run `/productivity:dream-restore`. It lists recent dream commits across
your memory repositories — three passes per project — and you choose which project
and which pass to undo. Memories written after that dream are preserved: a revert
undoes that commit, not everything since.
