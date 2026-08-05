# skills

Colin Dickson's public [Claude Code](https://code.claude.com/docs/en/overview) skills and
commands, shipped as [plugins](https://code.claude.com/docs/en/plugins) split by what
they're for — install only the ones you need.

## Install

Inside Claude Code:

```
/plugin marketplace add bluehoodie/skills
/plugin install engineering@bluehoodie
```

Or from your shell:

```bash
claude plugin marketplace add bluehoodie/skills
claude plugin install engineering@bluehoodie
```

Plugins are managed, read-only bundles — they update when a new version ships, rather than
dropping editable copies into your repo.

## Plugins

### [engineering](./plugins/engineering)

Skills and commands for code work. `/plugin install engineering@bluehoodie`

- [adversarial-review](./plugins/engineering/skills/adversarial-review/SKILL.md) —
  two-agent adversarial code review: the Critic attacks the code, the Author defends it,
  and the debate surfaces issues a single-pass review misses.

### [productivity](./plugins/productivity)

Skills and commands for non-code workflow. `/plugin install productivity@bluehoodie`

- [context-tune](./plugins/productivity/skills/context-tune/SKILL.md) — audit and rightsize
  a project's CLAUDE.md files, memories, and skills against the Claude 5
  context-engineering principles.
- [dream](./plugins/productivity/skills/dream/SKILL.md) — machine-wide memory
  consolidation. Surveys every project for new session activity, then merges, deletes
  and reindexes each one's memories, committing every pass to git. Run it yourself or
  schedule it as a routine.
- [dream-status](./plugins/productivity/commands/dream-status.md) — which projects need
  a dream, and the state of the memory stores.
- [dream-restore](./plugins/productivity/commands/dream-restore.md) — undo a dream by
  reverting that project's memory commit.

### dream (deprecated)

Memory consolidation moved into [productivity](./plugins/productivity). The `dream`
plugin is now an empty stub that removes the `SessionStart` hook version 2.x
installed; install `productivity@bluehoodie` and uninstall `dream@bluehoodie`. The
entry is removed one release from now.

Based on the dream feature originally built into Claude Code, since disabled.
**If Anthropic ever re-enables it, this is deprecated in favour of theirs.**

### [collective](./plugins/collective)

Team memory sharing. Memories are written from one person's experience of a codebase, but
most of what they record is not personal — and it currently dies in one laptop's
`~/.claude`. This moves it into the repo, where distribution, review, and access
control already exist. `/plugin install collective@bluehoodie`

`<repo>/.collective-memory/` is the whole product. A `SessionEnd` hook scans your memories for
credentials, asks whether each is team knowledge, and opens a pull request for the ones
that are — only memories that have gone a day without being rewritten, so drafts stay
home. Nothing comes back the other way until you ask:
`/collective:adapt` copies the collective's memories in as ordinary files you own.

- [adapt](./plugins/collective/commands/adapt.md) — take new or changed memories from the
  collective into your own memory directory.
- [status](./plugins/collective/commands/status.md) — what the collective holds, what is
  settling, what is quarantined.
- [reclaim](./plugins/collective/commands/reclaim.md) — review the memories the
  credential scanner refused, and why.

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
