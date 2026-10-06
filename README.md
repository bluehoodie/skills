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

This is the recommended way in. Plugins are managed, read-only bundles — they update when
a new version ships, rather than dropping editable copies into your repo.

### Without a marketplace

There is also a small CLI that copies individual skills and commands straight into
`~/.claude/`, for setups where a marketplace isn't the right fit:

```bash
npm install -g bluehoodie
```

That puts a `bluehoodie` command on your `PATH`:

```bash
bluehoodie install productivity/dream   # one skill or command
bluehoodie install productivity         # everything in a plugin
bluehoodie remove productivity/dream
bluehoodie list                         # what's available, what's installed
```

Or skip the install and run it directly: `npx bluehoodie list`.

What you get are ordinary files you own and can edit, not a managed bundle — so nothing
auto-updates, and you re-run `install` to pick up a new version. Use one route or the
other, not both: if a plugin is already installed from the marketplace, uninstall it
before installing the same thing this way.

## Plugins

### [engineering](./plugins/engineering)

Skills and commands for code work. `/plugin install engineering@bluehoodie`

- [adversarial-review](./plugins/engineering/skills/adversarial-review/SKILL.md) —
  two-agent adversarial code review: the Critic attacks the code, the Author defends it,
  and the debate surfaces issues a single-pass review misses.
- [ship-pr](./plugins/engineering/skills/ship-pr/SKILL.md) — take the current branch to a PR
  that is ready to merge: rename it to convention, review and fix the diff before the PR
  exists, fill in the repo's PR template, watch CI, fix or rerun what breaks. Never merges —
  that click is yours.

### [productivity](./plugins/productivity)

Skills and commands for non-code workflow. `/plugin install productivity@bluehoodie`

- [dream](./plugins/productivity/skills/dream/SKILL.md) — machine-wide memory
  consolidation. Tidies every project's memories in one pass and commits the result so
  you can undo it. Usually run nightly as a Claude Desktop routine —
  [setup is three steps](./plugins/productivity#set-up-nightly-memory-consolidation).
- [dream-status](./plugins/productivity/commands/dream-status.md) — which projects need
  a dream, and the state of the memory stores.
- [dream-restore](./plugins/productivity/commands/dream-restore.md) — undo a dream by
  reverting that project's memory commit.

> Dream is based on a feature originally built into Claude Code, since disabled.
> **If Anthropic ever re-enables it, this is deprecated in favour of theirs.**

## Contributing

Repo conventions — where skills go, what has to stay in sync — are in
[CLAUDE.md](./CLAUDE.md).

## License

[MIT](./LICENSE)
