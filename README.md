# skills

Colin Dickson's public [Claude Code](https://code.claude.com/docs/en/overview) skills and
commands, shipped as a [plugin](https://code.claude.com/docs/en/plugins).

## Install

Inside Claude Code:

```
/plugin marketplace add bluehoodie/skills
/plugin install bluehoodie-skills@bluehoodie
```

Or from your shell:

```bash
claude plugin marketplace add bluehoodie/skills
claude plugin install bluehoodie-skills@bluehoodie
```

The plugin is a managed, read-only bundle — it updates when a new version ships, rather
than dropping editable copies into your repo.

## Skills

### Engineering

Skills for code work.

_No skills yet._

### Productivity

Non-code workflow tools.

- [context-tune](./skills/productivity/context-tune/SKILL.md) — audit and rightsize a
  project's CLAUDE.md files, memories, and skills against the Claude 5
  context-engineering principles.

## Commands

_No commands yet._

## Other plugins

This marketplace also ships plugins that are more than a skill — they carry hooks or
scripts, so they install separately and only if you want them.

- [dream](./plugins/dream) — periodic memory consolidation. A `SessionStart` hook watches
  time and session gates, then runs a four-phase pass over Claude Code's auto-memory so it
  stays relevant instead of growing forever. Install with
  `/plugin install dream@bluehoodie`.

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
