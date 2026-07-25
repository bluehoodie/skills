# Repository conventions

This repo is a public collection of Claude Code skills and commands. It is its own
marketplace: `.claude-plugin/marketplace.json` lists the `bluehoodie-skills` plugin,
whose source is this repo root, plus any standalone plugins under `plugins/`.

Default to shipping a skill inside `bluehoodie-skills`. Give something its own plugin
only when it carries a hook — a hook at the repo root fires for everyone who installs
`bluehoodie-skills` for something else, and background behaviour has to be opted into,
not bundled. `plugins/dream/` is the case: its `SessionStart` hook launches detached
sessions.

A standalone plugin owns its own `.claude-plugin/plugin.json`, version, CHANGELOG, and
README, and appears in the marketplace `plugins` array with `"source":
"./plugins/<name>"`. Its skills and commands stay inside it — they are not listed in the
root plugin's `skills` array or the bucket READMEs.

## Skills

Skills live in bucket folders under `skills/`:

- `engineering/` — code work
- `productivity/` — non-code workflow tools
- `in-progress/` — drafts not yet ready to ship
- `deprecated/` — no longer used

`engineering/` and `productivity/` are the **promoted** buckets. Every skill in a
promoted bucket must have:

- an entry in `.claude-plugin/plugin.json`'s `skills` array (the plugin ships exactly
  the promoted set — nested bucket folders are not auto-discovered, so the array is the
  source of truth)
- a line in that bucket's `README.md`, with the skill name linked to its `SKILL.md`
- a line in the top-level `README.md`, same link

Skills in `in-progress/` and `deprecated/` must appear in none of those three places.

## Commands

Commands live flat in `commands/`, one `.md` per command, auto-discovered by the plugin.
Do not nest them in subfolders — a subfolder namespaces the invocation (`/bucket:name`),
which is worse to type. Every command gets a line in the top-level `README.md`.

Every `.md` in `commands/` becomes a command, so don't put a `README.md` there — it would
ship as `/README`. That's what the `.gitkeep` is for. Each command needs YAML frontmatter
with at least a `description`.

## Releasing

Bump `version` in the changed plugin's `plugin.json` — the root one for skills and
commands, `plugins/<name>/.claude-plugin/plugin.json` for a standalone. That version is
what Claude uses to decide when installed users see an update — a change with no bump is
a change nobody gets.

Run `claude plugin validate . --strict` after touching either manifest,
`claude plugin validate plugins/<name> --strict` for a standalone plugin, and
`claude plugin validate .claude-plugin/plugin.json --strict` to also lint the skills and
commands themselves.

The latter always reports one known warning — that this `CLAUDE.md` is not loaded as
plugin context. That is intended: it is contributor documentation for people who clone
the repo, not context shipped to people who install the plugin. Ignore that one warning;
treat any other as a real failure.
