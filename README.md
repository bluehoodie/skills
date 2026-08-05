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
  consolidation. Tidies every project's memories in one pass and commits the result so
  you can undo it. Usually run nightly as a Claude Desktop routine —
  [setup is three steps](./plugins/productivity#set-up-nightly-memory-consolidation).
- [dream-status](./plugins/productivity/commands/dream-status.md) — which projects need
  a dream, and the state of the memory stores.
- [dream-restore](./plugins/productivity/commands/dream-restore.md) — undo a dream by
  reverting that project's memory commit.

> **Upgrading from the standalone `dream` plugin?** It has been removed — memory
> consolidation now ships inside `productivity`. Run `/plugin uninstall dream@bluehoodie`
> explicitly: uninstalling is the only thing that stops version 2.x's `SessionStart`
> hook, which fires a consolidation in every session. Your memories are untouched by
> the move, and `~/.claude/dream-plugin-state/` becomes unused — but it holds the only
> snapshot of your last 2.x dream, so undo anything you still want with 2.x's
> `/dream:dream-restore` before deleting it.
>
> Dream is based on a feature originally built into Claude Code, since disabled.
> **If Anthropic ever re-enables it, this is deprecated in favour of theirs.**

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
