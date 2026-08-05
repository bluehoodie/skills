---
name: dream
description: DEPRECATED — dream has moved to the productivity plugin
---

Tell the user, verbatim and without embellishment:

> `dream` has moved into the `productivity` plugin and is now
> `/productivity:dream`.
>
> ```
> /plugin install productivity@bluehoodie
> /plugin uninstall dream@bluehoodie
> ```
>
> Your memories are untouched — they live in `~/.claude/projects/<slug>/memory/`
> and the new version picks them up as they are. The old per-project state in
> `~/.claude/dream-plugin-state/` is no longer read. Before deleting it, note
> that it holds the only snapshot of your last 2.x dream — if there is one you
> still want to undo, run `/dream:dream-restore` on 2.x first. Once you have
> updated to 3.0 that snapshot is no longer reachable from this plugin.

Do not attempt to run a consolidation. This plugin no longer contains one.
