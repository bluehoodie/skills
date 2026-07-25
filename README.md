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

_No skills yet._

_No commands yet._

### [productivity](./plugins/productivity)

Skills and commands for non-code workflow. `/plugin install productivity@bluehoodie`

- [context-tune](./plugins/productivity/skills/context-tune/SKILL.md) — audit and rightsize
  a project's CLAUDE.md files, memories, and skills against the Claude 5
  context-engineering principles.

_No commands yet._

### [dream](./plugins/dream)

Periodic memory consolidation. A `SessionStart` hook watches time and session gates, then
runs a four-phase pass over Claude Code's auto-memory so it stays relevant instead of
growing forever. `/plugin install dream@bluehoodie`

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
