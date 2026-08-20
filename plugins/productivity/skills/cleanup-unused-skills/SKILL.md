---
name: cleanup-unused-skills
description: >
  Find globally installed skills, commands and plugins that no session has
  invoked over a window, show what has gone unused, and remove the ones the
  user picks — all of it reversibly. Use when the user says
  /cleanup-unused-skills, "clean up my skills", "which skills do I actually
  use", "prune my plugins", or asks what is installed and idle. The window is
  optional and can be a number of days or a phrase like "the last three months".
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/skill-usage.py":*), Bash(claude plugin:*), Bash(npx bluehoodie:*), Bash(mkdir:*), Bash(mv:*), Bash(ls:*), Bash(date:*), Read, AskUserQuestion
---

# Cleanup unused skills

Everything installed globally costs context in **every** session — a skill's
description is loaded whether or not it ever fires. This finds the ones earning
nothing and offers to take them out.

Three rules hold throughout, and none of them bend:

- **Nothing is removed without the user choosing it by name.** There is no
  "obviously safe" deletion here.
- **Everything removed is recoverable**, by the route named against it below.
  If you cannot name the way back, do not remove it.
- **Only the global set is in scope** — `~/.claude` and installed plugins.
  A `.claude/skills/` inside a repository belongs to that repository. Never
  touch one, even if the survey says it went unused.

## Step 1 — Fix the window

The argument is optional and may be a number or a phrase. Turn it into one flag:

| The user said | Pass |
|---|---|
| nothing | `--days 30` |
| `90`, `90 days`, `three months` | `--days 90` |
| "since June", "since 2026-06-01" | `--since 2026-06-01` |
| "this year" | `--since <current year>-01-01` |

Resolve the phrase yourself — the script takes only these two forms, and
rejects anything else rather than quietly falling back to a default window.
If a phrase is genuinely ambiguous ("recently"), pick 30 days and say which
window you used; do not stop to ask.

## Step 2 — Survey

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/skill-usage.py" --days 30
```

The path in that command is filled in before the prompt reaches you — either
by the plugin loader, or by `bluehoodie install`, which writes an absolute path
in its place. It arrives correct; never edit it, and never rewrite it as a
shell variable, because `$CLAUDE_PLUGIN_ROOT` and `${CLAUDE_PLUGIN_ROOT:-…}`
are not environment variables and both expand to an empty string.

Add `--json` if you need the fields (`owner`, `path`, `plugin`) to build the
removal commands in step 4. The table is what you show the user.

Run the script. Do not reimplement the scan inline, and in particular **do not
grep transcripts for skill names**: every session's transcript contains a
listing of every installed skill, so a grep reports all of them as used. The
script reads invocations structurally instead.

The report has four sections:

- **UNUSED** — installed before the window opened, never invoked inside it.
  These are the candidates.
- **TOO NEW TO JUDGE** — installed inside the window. Never offer these;
  a skill installed on Tuesday being unused by Friday means nothing.
- **USED** — with a count and a last-used date.
- **INVOKED BUT NOT INSTALLED** — invoked in the window but not in the global
  set: project-level skills, or something already removed. Informational.

## Step 3 — Show it and ask

First, check whether the evidence is worth acting on. The `evidence` line gives
sessions and invocations in the window. Under ~5 sessions, or 0 invocations,
say so plainly before anything else — "unused" then means the window was quiet,
not that the skills are dead weight — and offer a longer window instead of a
list of things to delete.

Otherwise show the UNUSED table. Keep the script's rows; add nothing to them.

Then work out what is actually offerable, because the rows are not all
independent choices.

**Collapse plugin components into their plugin.** A plugin's skills and
commands appear as separate rows, but uninstalling takes all of them. Group the
rows that share a `plugin` field, then compare against the plugin's full
component list in the USED table:

- every component unused → offer **the plugin**, as one choice, named
  `<plugin>@<marketplace>`, saying how many components go with it.
- any component used → offer nothing for that plugin. Report it as kept, and
  name the component keeping it — that is the answer worth having.

**Set cloud-synced skills aside.** `source: synced` came down from the user's
account on claude.ai and syncs back, so deleting the local copy lasts until the
next sync. List them under a heading that says so, and **never put one in the
removal choices.** They are removed for good where they were added.

Everything else — `user`, `bluehoodie`, `skills-dir` — is offered as itself.

If nothing offerable is left, say what was found, note the synced and the
kept-because-used ones, and stop. Do not ask a question with no answers behind
it.

Now ask, with `AskUserQuestion`, one single-select question:

| Option | Meaning |
|---|---|
| Remove all *N* | every removable candidate |
| Choose which | go to the multi-select below |
| Leave them all | stop, change nothing |

Put "Choose which" first when there are more than three candidates, and
"Leave them all" first when the evidence was thin.

### Choosing some

With **16 or fewer** candidates, ask with `AskUserQuestion` again: chunk them
into questions of at most 4 options each, at most 4 questions per call, every
question `multiSelect: true`. Each option's label is the skill or command name,
its description the kind, source and install date. That gives the user
checkboxes over the whole list.

With **more than 16**, checkboxes stop being usable. Print the candidates as a
numbered list and ask the user to reply with the numbers or names they want
gone. Accept ranges (`1-4`), lists (`2, 7, 9`), and names.

Either way: an empty selection means remove nothing. Take it at face value and
stop — do not re-ask.

## Step 4 — Remove what was chosen

Each candidate carries an `owner` in the JSON, and that decides the route.
**Use the route, not `rm`.** Removing a plugin's files by hand leaves Claude
Code's own record of it pointing at a directory that is gone.

### `owner: marketplace` — an installed plugin

Step 3 has already established that every component of this plugin is unused —
uninstalling removes all of them, so that is the only condition under which one
can be offered.

```bash
claude plugin uninstall <plugin>@<marketplace> --scope <scope>
```

Take `<plugin>@<marketplace>` from the item's `plugin` field and `<scope>` from
`claude plugin list --json`. Back with `claude plugin install <plugin>@<marketplace>`.

If the user is hesitant, offer `claude plugin disable <plugin>` instead: it
stops the plugin loading into sessions and costing context, keeps the files,
and is undone with `claude plugin enable`.

### `owner: bluehoodie` — installed by this repo's own CLI

```bash
npx bluehoodie remove <plugin>/<name>
```

Take `<plugin>` from the item's `plugin` field. Go through the CLI rather than
deleting the files: it also drops the entry from its manifest, and a manifest
still claiming a file that is gone is what makes the next `install` refuse.
Back with `npx bluehoodie install <plugin>/<name>`.

### `owner: user` or `owner: skills-dir` — files you put in `~/.claude`

Nothing else knows about these, so move them aside rather than deleting them.
Use one dated directory for the whole pass:

```bash
mkdir -p "$HOME/.claude/cleanup-attic/$(date +%Y-%m-%d-%H%M)"
mv "<path>" "$HOME/.claude/cleanup-attic/<that same stamp>/"
```

`<path>` is the item's `path` field — for a skill, its **directory**
(`~/.claude/skills/<name>`), not the `SKILL.md` inside it; for a command, the
`.md` file itself. A `skills-dir` plugin is its whole top-level directory.

Compute the stamp once and reuse it, so one pass is one directory and undoing
it is one `mv` back. Never write the attic anywhere but under `~/.claude`.

### `owner: synced`

Not reachable from here — step 3 kept it out of the choices. If one somehow
arrives, refuse it and say why.

## Step 5 — Report

One line per removal, then one line saying how to undo the pass:

```
removed  productivity:old-thing   plugin      claude plugin install productivity@bluehoodie
removed  scratch-notes            user skill  mv ~/.claude/cleanup-attic/2026-08-20-1412/scratch-notes ~/.claude/skills/
kept     xlsx, pptx               synced      remove these on claude.ai
```

Then say that removals take effect in the next session — this one already
loaded what it loaded.

Do not summarise what the skills did, do not suggest replacements, and do not
offer to run again with a different window unless asked.
