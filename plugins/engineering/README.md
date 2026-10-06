# engineering

Claude Code skills and commands for code work.

```
/plugin marketplace add bluehoodie/skills
/plugin install engineering@bluehoodie
```

Not using a marketplace? `npx bluehoodie install engineering` copies these into
`~/.claude/` as ordinary files instead — see
[the alternative install path](../../README.md#without-a-marketplace).

## Skills

- [adversarial-review](./skills/adversarial-review/SKILL.md) — two-agent adversarial code
  review: the Critic attacks the code, the Author defends it, and the debate surfaces
  issues a single-pass review misses.
- [ship-pr](./skills/ship-pr/SKILL.md) — take the current branch to a PR that is ready to
  merge: rename it to convention, review and fix the diff before the PR exists, fill in the
  repo's PR template, watch CI, fix or rerun what breaks. Never merges — that click is yours.
