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


### [dream](./plugins/dream)

Periodic memory consolidation. A `SessionStart` hook watches time and session gates, then
runs a four-phase pass over Claude Code's auto-memory so it stays relevant instead of
growing forever. `/plugin install dream@bluehoodie`

Based on the dream feature originally built into Claude Code, but which is currently a disabled feature. This plugin is a recreation of that feature, with some improvements and changes to make it more useful.  

**If Anthropic ever re-enables the dream feature in Claude Code, this plugin will be deprecated.**

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
