# dream — deprecated

This plugin has moved. Memory consolidation now ships as a skill in
[productivity](../productivity), and this package is an empty stub whose only
job is to remove the `SessionStart` hook that version 2.x installed.

```
/plugin install productivity@bluehoodie
/plugin uninstall dream@bluehoodie
```

`/dream:dream` becomes `/productivity:dream`. `/dream:dream-status` and
`/dream:dream-restore` become `/productivity:dream-status` and
`/productivity:dream-restore`.

`/dream:dream-reset` has no successor. It only cleared the gate lock that
decided when the hook should fire, and 3.0 has no gate — you choose when to
run a consolidation.

## What changed

2.x ran consolidation automatically from a `SessionStart` hook, one project at a
time, gated on elapsed hours and session count. 3.0 has no hook: you run
`/productivity:dream` when you want, or schedule it as a routine, and one pass
sweeps every project on the machine.

Recovery changed too. 2.x kept a single `memory-backup/` snapshot per project,
overwritten on every run. Each memory directory is now its own git repository and
every dream is one commit, so `git log -p` shows exactly what changed and
`/productivity:dream-restore` reverts it.

## Your data

Memories are untouched — they live in `~/.claude/projects/<slug>/memory/` and the
new version picks them up as they are.

`~/.claude/dream-plugin-state/` is no longer read and can be deleted. If you have
a 2.x dream you still want to undo, do it with 2.x's `/dream:dream-restore`
**before** deleting that directory — it holds the only snapshot.

## What this plugin still contains

- [dream](./commands/dream.md) — a redirect notice. Typing `/dream:dream` prints where
  memory consolidation moved to. It performs no consolidation.

## This entry is temporary

It exists so that updating disarms the old hook. It is removed one release from
now, at which point uninstalling is the only step left.
