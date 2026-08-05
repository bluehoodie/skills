# engineering

Claude Code skills and commands for code work.

```
/plugin marketplace add bluehoodie/skills
/plugin install engineering@bluehoodie
```

Blocked from adding third-party marketplaces? `npx bluehoodie install engineering`
copies these into `~/.claude/` instead — see
[the alternative install path](../../README.md#without-a-marketplace).

## Skills

- [adversarial-review](./skills/adversarial-review/SKILL.md) — two-agent adversarial code
  review: the Critic attacks the code, the Author defends it, and the debate surfaces
  issues a single-pass review misses.
