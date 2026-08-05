# Repository conventions

This repo is a public collection of Claude Code skills and commands. It is its own
marketplace: `.claude-plugin/marketplace.json` lists every plugin, each one a directory
under `plugins/`. The repo root is not itself a plugin.

Plugins are split by what they are *for*, so users install only what they need:

- `plugins/engineering/` — code work
- `plugins/productivity/` — non-code workflow tools

Add a new plugin only for a genuinely new category, or for something that carries a
hook — background behaviour a user must opt into. A `scripts/` directory is not by
itself a reason: a helper a skill invokes when you run it is not background
behaviour. Everything else goes in `engineering` or `productivity`.

No plugin currently carries a hook. That is worth preserving: a hook runs whether
or not the user asked, so it is the one thing here that needs its own opt-in.

## Anatomy of a plugin

```
plugins/<name>/
  .claude-plugin/plugin.json   # "skills": "./skills/", "commands": "./commands/"
  skills/<skill>/SKILL.md
  commands/<command>.md
  README.md
```

Skills and commands are auto-discovered from those two directories — there is no list to
keep in sync. Nesting is not discovered: a skill is `skills/<name>/SKILL.md`, one level
deep, and a command is `commands/<name>.md`, flat. A subfolder under `commands/`
namespaces the invocation (`/<subfolder>:name`), which is worse to type.

Every `.md` in `commands/` becomes a command, so don't put a `README.md` there — it would
ship as `/README`. That's what the `.gitkeep` is for. Each command needs YAML frontmatter
with at least a `description`.

## What has to stay in sync

- Every shipped skill and command has a line in its plugin's `README.md`, name linked to
  its `SKILL.md` or `.md`.
- Every shipped skill and command has a line in the top-level `README.md`, under its
  plugin's heading, same link.
- Every plugin's `skills/` and `commands/` directory is tracked by git, with a `.gitkeep`
  when it is otherwise empty. Git does not track empty directories, and a plugin whose
  declared `"skills": "./skills/"` path is missing on a fresh clone fails to load — local
  validation passes right up until someone installs it.

## Releasing

Bump `version` in the changed plugin's `plugins/<name>/.claude-plugin/plugin.json`. That
version is what Claude uses to decide when installed users see an update — a change with
no bump is a change nobody gets. Only the plugin you touched needs a bump.

Validate the marketplace and every plugin you changed:

```bash
claude plugin validate . --strict                    # marketplace manifest
claude plugin validate plugins/<name> --strict       # one plugin
```

All of these must pass clean. There are no expected warnings.

The repo root is also the `bluehoodie` npm package, which installs skills for
users whose policy blocks the marketplace. Its `version` in `package.json` is
the package's own semver, independent of every plugin version — bump it on any
publish, meaning any change to `bin/bluehoodie.js` **or** `plugins/`, since the
tarball ships both. A skill edit therefore bumps two numbers: the plugin's and the
package's.

`"files"` in `package.json` must keep listing `plugins`. If it stops, `npx
bluehoodie` installs an empty tree — the same failure class as a missing
version bump, where the published artifact silently stops matching the repo.

```bash
npm pack --dry-run          # confirm plugins/ is in the tarball
bash bin/test-bluehoodie.sh # end-to-end install/remove against a temp HOME
```

## Why the installer works the way it does

Four decisions in `bin/bluehoodie.js` that look arbitrary and are not. Change them
only with these in mind.

**It rewrites `${CLAUDE_PLUGIN_ROOT}`.** That token is substituted by Claude Code's
plugin loader. Nothing substitutes it for a loose skill in `~/.claude/skills/`, where
it resolves to an empty string — so `dream` would silently try to run
`/scripts/survey.sh`. Install copies the plugin's `scripts/` to
`~/.claude/bluehoodie/<plugin>/` and rewrites the token to that absolute path. This
is why a hand-rolled `cp -r` is not equivalent: it passes every "the file exists"
check and still ships a broken skill.

**The manifest keys entries `<type>:<name>`, not by bare name.** A plugin may legally
hold a `dream` skill and a `dream.md` command; they install to different paths, and a
flat key can only record one, orphaning the other.

**`remove` derives its targets from the manifest, then checks containment.** Deleting
only what the manifest claims is what stops it touching a `~/.claude/skills/dream/`
that came from anywhere else. But because the manifest is the path source, a crafted
or corrupt one must not be able to escape — hence the explicit check that the target's
parent is exactly `~/.claude/skills` or `~/.claude/commands`. Deleting that check is
not a simplification: without it, a hand-edited manifest deletes files outside
`~/.claude`. `bin/test-bluehoodie.sh` covers traversal, absolute paths, and unknown
types.

**It does not detect a duplicate marketplace install.** Detection would mean reading
`~/.claude/plugins/installed_plugins.json`, which is Claude Code's private state —
already at schema `version: 2`, keyed by a marketplace name whoever added it chose.
It would fail open, fail noisy, and rot. The duplicate is harmless anyway: plugin
skills are namespaced (`productivity:dream`), user-level ones are bare (`dream`). The
README says the npm path is an alternative, not a supplement; that is the whole
mitigation.
