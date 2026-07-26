# Collective (Borg Re-theme) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `dreamscape` plugin to `collective` with Borg-derived verbs, changing zero behaviour, and ship it as 1.0.0.

**Architecture:** A rename in eight reviewable slices. Slice 1 moves the files and proves the 793-line test suite still runs green before anything semantic changes. Slices 2–5 rename inside the script, each ending on a full green suite. Slices 6–7 rename the plugin package and the docs. Slice 8 is the sweep that proves nothing was missed.

**Tech Stack:** Python 3 (stdlib only, no framework), a hand-rolled `check()` test harness, `claude plugin validate`, git plumbing.

**Spec:** `docs/superpowers/specs/2026-07-26-collective-borg-retheme-design.md`

## Global Constraints

- **Zero behaviour changes.** If something looks like a bug during this work, note it and leave it. A rename that also changes semantics is unreviewable.
- **`.collective-memory/` never changes.** It is committed data in adopting team repos.
- **Frontmatter keys `sharedBy`, `promotedAt`, `pulledFrom` never change.** Same reason.
- **The sibling `dream` plugin is never touched.**
- All renames of tracked files use `git mv` so history follows.
- The test suite must be green at the end of **every** task. Run: `python3 plugins/<dir>/scripts/<test file>` — the exact path changes at Task 1 and Task 6.
- The suite has no framework. A test is a top-level `check(label, expected, actual)` call. Exit code 0 = pass; the runner prints `ok —` / `FAIL —` per line.
- Security-path vocabulary stays literal everywhere: `blocked`, `credential`, `secret`, scanner reason strings, `--dry-run`, `SETTLE_HOURS`, `MIN_CONFIDENCE`, the word "memory", and all error text.
- Commit after every task. One-line imperative commit messages, per repo convention.
- Current branch is `feature/dreamscape-plugin`. Do not create a new branch; do not commit to `main`.

**Name map — every task refers back to this:**

| Now | Becomes |
|---|---|
| `plugins/dreamscape/` | `plugins/collective/` |
| `scripts/dreamscape.py` | `scripts/collective.py` |
| `scripts/test_dreamscape.py` | `scripts/test_collective.py` |
| `promote` (verb + function) | `assimilate` |
| `pull` (verb + function) | `adapt` |
| `status` (verb) | `status` (unchanged) |
| `/dreamscape:memory-pull` | `/collective:adapt` |
| `/dreamscape:memory-status` | `/collective:status` |
| `/dreamscape:memory-share` | `/collective:reclaim` |
| `DREAMSCAPE_*` | `COLLECTIVE_*` |
| `~/.claude/dreamscape-state/` | `~/.claude/collective-state/` |
| branch `dreamscape/<date>-<key>` | `assimilate/<date>-<key>` |
| `TEAM_SUBDIR` / `team_dir()` | `COLLECTIVE_SUBDIR` / `collective_dir()` |
| `PERSONAL_TYPES` / `personal()` | `INDIVIDUAL_TYPES` / `individual()` |
| version `0.3.0` | `1.0.0` |

---

### Task 1: Move the files, prove the suite still runs

The whole point of this task is a green baseline. Nothing but paths and the import change.

**Files:**
- Rename: `plugins/dreamscape/scripts/dreamscape.py` → `plugins/dreamscape/scripts/collective.py`
- Rename: `plugins/dreamscape/scripts/test_dreamscape.py` → `plugins/dreamscape/scripts/test_collective.py`
- Modify: `plugins/dreamscape/scripts/test_collective.py:2` (docstring), `:26` (import)

The plugin **directory** is still `dreamscape/` after this task. It moves in Task 6.

**Interfaces:**
- Consumes: nothing.
- Produces: module importable as `collective`; test entry point `plugins/dreamscape/scripts/test_collective.py`.

- [ ] **Step 1: Capture the green baseline before touching anything**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_dreamscape.py | tail -5
echo "exit=$?"
```

Expected: a run of `ok —` lines, no `FAIL —`, `exit=0`. Record how many lines it printed:

```bash
python3 plugins/dreamscape/scripts/test_dreamscape.py | grep -c '^ok'
```

Keep that number. Every later task must print the same count or more, never fewer.

- [ ] **Step 2: Move both files with git**

```bash
cd /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts
git mv dreamscape.py collective.py
git mv test_dreamscape.py test_collective.py
```

- [ ] **Step 3: Run the suite to verify it now fails**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_collective.py
```

Expected: `ModuleNotFoundError: No module named 'dreamscape'`. That failure is the point — it proves the import is the only coupling.

- [ ] **Step 4: Fix the import and the test docstring**

In `plugins/dreamscape/scripts/test_collective.py`, line 26:

```python
import collective as ds
```

The local alias stays `ds`. Renaming it to `co` would churn several hundred call sites for no reader benefit — leave it.

Line 2 of the same file:

```python
"""Self-check for collective.py. Run: python3 scripts/test_collective.py
```

- [ ] **Step 5: Run the suite to verify it passes**

```bash
python3 plugins/dreamscape/scripts/test_collective.py | grep -c '^ok'
echo "failures: $(python3 plugins/dreamscape/scripts/test_collective.py | grep -c '^FAIL')"
```

Expected: same `ok` count as Step 1, `failures: 0`.

- [ ] **Step 6: Confirm git tracked the moves as renames**

```bash
git -C /Users/colindickson/code/bluehoodie/skills status --short
```

Expected: two `R` (renamed) entries, not a delete-plus-add pair.

- [ ] **Step 7: Commit**

```bash
cd /Users/colindickson/code/bluehoodie/skills
git add plugins/dreamscape/scripts/
git commit -m "Rename the dreamscape script to collective"
```

---

### Task 2: Switch the env prefix, keeping one deliberate fallback

Nine environment variables move to `COLLECTIVE_*`. One — `DRY_RUN` — also keeps reading the old name, because its silent failure opens real pull requests into a team repo from a detached hook.

This is the only task in the plan with genuinely new test coverage. The `env()` helper does not exist yet, and the existing suite sets `ds.DRY_RUN = True` as a module attribute rather than through the environment, so nothing today exercises the env path at all.

**Files:**
- Modify: `plugins/dreamscape/scripts/collective.py:51-74` (the config block), `:462` and `:478` (the two in-function `DREAMSCAPE_GRAPHIFY*` reads)
- Modify: `plugins/dreamscape/scripts/test_collective.py:295, 301, 408, 661, 765-768` (env writes)
- Test: `plugins/dreamscape/scripts/test_collective.py` (new section)

**Interfaces:**
- Produces: `env(name)` — takes the bare suffix (`"DRY_RUN"`, not `"COLLECTIVE_DRY_RUN"`), returns `str | None`. Checks `COLLECTIVE_<name>` first, falls back to `DREAMSCAPE_<name>`. Only `DRY_RUN` is read through it; every other variable reads `os.environ.get("COLLECTIVE_...")` directly.

- [ ] **Step 1: Write the failing test**

Append a new section to `test_collective.py`, immediately after the `redact` section (before the `# --- sandbox` divider at line 120), so it runs before any sandbox mutates `$HOME`:

```python
# ------------------------------------------------------------ env fallback
#
# Only DRY_RUN keeps reading the old prefix. Its failure mode is the one that is
# both silent and outward-facing: someone testing with DREAMSCAPE_DRY_RUN=1
# upgrades, the variable stops being read, and the next SessionEnd pushes real
# branches into a team repo from a detached hook nobody is watching.

for var in ("COLLECTIVE_DRY_RUN", "DREAMSCAPE_DRY_RUN"):
    os.environ.pop(var, None)
check("env reads nothing when nothing is set", None, ds.env("DRY_RUN"))

os.environ["DREAMSCAPE_DRY_RUN"] = "1"
check("env still honours the old prefix", "1", ds.env("DRY_RUN"))

os.environ["COLLECTIVE_DRY_RUN"] = "0"
check("and the new prefix wins when both are set", "0", ds.env("DRY_RUN"))

del os.environ["DREAMSCAPE_DRY_RUN"]
check("env reads the new prefix alone", "0", ds.env("DRY_RUN"))
del os.environ["COLLECTIVE_DRY_RUN"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_collective.py 2>&1 | head -20
```

Expected: `AttributeError: module 'collective' has no attribute 'env'`.

- [ ] **Step 3: Add the helper and switch the config block**

In `collective.py`, define `env()` immediately above the config block (just after the `from pathlib import Path` import, around line 49):

```python
def env(name):  # ponytail: DRY_RUN footgun only; drop when nobody is on 0.3.0
    """A config value, new prefix first. Only DRY_RUN reads the old one."""
    return os.environ.get(f"COLLECTIVE_{name}") or os.environ.get(f"DREAMSCAPE_{name}")
```

Then rewrite each config line. Change **only** the prefix — every default and every surrounding comment stays exactly as it is:

```python
MIN_CONFIDENCE = float(os.environ.get("COLLECTIVE_MIN_CONFIDENCE") or 0.85)
CLAUDE_BIN = os.environ.get("COLLECTIVE_CLAUDE_BIN") or "claude"
COMPARE_MODEL = os.environ.get("COLLECTIVE_COMPARE_MODEL") or "haiku"
DRY_RUN = env("DRY_RUN") == "1"
GRAPH_TIMEOUT = int(os.environ.get("COLLECTIVE_GRAPHIFY_TIMEOUT") or 600)
SETTLE = float(os.environ.get("COLLECTIVE_SETTLE_HOURS") or 24) * 3600
MAX_GRAPH_QUERIES = int(os.environ.get("COLLECTIVE_GRAPHIFY_MAX_QUERIES") or 8)
```

And the two reads inside `graphify_context()` — line 462 and line 478:

```python
    if os.environ.get("COLLECTIVE_GRAPHIFY") == "0" or not shutil.which("graphify"):
```

```python
        backend = os.environ.get("COLLECTIVE_GRAPHIFY_BACKEND")
```

- [ ] **Step 4: Update the docstring's Environment block**

In `collective.py`, replace the four `DREAMSCAPE_*` lines in the module docstring (lines 33–36) with the full current set — the docstring is out of date today and listing only four of nine is worse after a rename:

```
Environment:
  COLLECTIVE_SETTLE_HOURS         hours untouched before a memory is assimilable (24)
  COLLECTIVE_MIN_CONFIDENCE       classifier threshold to auto-assimilate (0.85)
  COLLECTIVE_CLAUDE_BIN           claude executable for the model calls (claude)
  COLLECTIVE_COMPARE_MODEL        model judging whether a change means anything (haiku)
  COLLECTIVE_GRAPHIFY             set to 0 to skip the graphify dedup pass
  COLLECTIVE_GRAPHIFY_BACKEND     pin a graphify backend instead of auto-detecting
  COLLECTIVE_GRAPHIFY_MAX_QUERIES candidates queried for graph neighbours (8)
  COLLECTIVE_GRAPHIFY_TIMEOUT     seconds allowed for the graph build (600)
  COLLECTIVE_DRY_RUN              set to 1 to build the branch but never push
                                  (DREAMSCAPE_DRY_RUN is still read, for upgrades)
```

- [ ] **Step 5: Update the env writes in the test file**

Five sites in `test_collective.py` set `DREAMSCAPE_GRAPHIFY`. Replace every one with `COLLECTIVE_GRAPHIFY` — lines 295, 301, 408, 661, and the block at 765–768. The two `check()` labels at 766–767 name the variable in their text and must change too:

```python
os.environ["COLLECTIVE_GRAPHIFY"] = "0"
check("COLLECTIVE_GRAPHIFY=0 skips it", "", ds.graphify_context(s.team, pending))
check("COLLECTIVE_GRAPHIFY=0 runs nothing", "", g.calls())
del os.environ["COLLECTIVE_GRAPHIFY"]
```

Verify none are left:

```bash
grep -n "DREAMSCAPE_" plugins/dreamscape/scripts/test_collective.py
```

Expected: only the four lines inside the new env-fallback section from Step 1.

- [ ] **Step 6: Run the suite to verify it passes**

```bash
python3 plugins/dreamscape/scripts/test_collective.py | grep -c '^ok'
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: the Task 1 count **plus 4**, and `no failures`.

- [ ] **Step 7: Commit**

```bash
git add plugins/dreamscape/scripts/
git commit -m "Read configuration from the COLLECTIVE_ prefix"
```

---

### Task 3: Rename the verbs and the state directory

`promote` → `assimilate`, `pull` → `adapt`, and the state directory moves. All three are behavioural naming, so they land together: a reviewer approving one would approve all three.

**Files:**
- Modify: `plugins/dreamscape/scripts/collective.py:223` (`state_dir`), `:663` (`promote`), `:768` (`pulled_path`), `:772` (`pull`), `:851-880` (`main` dispatch)
- Modify: `plugins/dreamscape/scripts/test_collective.py` — every `ds.promote(` and `ds.pull(` call site

**Interfaces:**
- Consumes: `env()` from Task 2.
- Produces: `assimilate(project, cwd) -> str | None` (was `promote`); `adapt(project, cwd) -> list[tuple[str, Path]]` (was `pull`); `state_dir(project) -> Path` now ending `collective-state/<name>`. `take(cwd, name)` and `mark_pulled(project, cwd, names)` keep their names — they are `adapt`'s internals, and `mark_pulled` pairs with the `pulled.json` state file, which is not being renamed.

- [ ] **Step 1: Update the test call sites first**

Every `ds.promote(` in `test_collective.py` becomes `ds.assimilate(`, and every `ds.pull(` becomes `ds.adapt(`. There are roughly a dozen of the first and a handful of the second.

```bash
cd /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("test_collective.py")
t = p.read_text()
t = t.replace("ds.promote(", "ds.assimilate(").replace("ds.pull(", "ds.adapt(")
p.write_text(t)
PY
grep -n "ds\.promote\|ds\.pull(" test_collective.py || echo "none left"
```

Expected: `none left`.

Then update the `check()` labels that use the word "promote". These are prose, and they should read as the new verb. Find them:

```bash
grep -n 'check("' test_collective.py | grep -i "promot"
```

Rewrite each label's "promote"/"promoted"/"promotion" as "assimilate"/"assimilated"/"assimilation". Leave any label containing `blocked` or `credential` alone — those are security-path words the spec keeps literal. Note the section-divider comments (`# --- promote`, `# --- promotion candidates`) also mention the verb; update those in Task 5 with the rest of the prose, not here.

- [ ] **Step 2: Run the suite to verify it fails**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_collective.py 2>&1 | head -5
```

Expected: `AttributeError: module 'collective' has no attribute 'assimilate'`.

- [ ] **Step 3: Rename the functions and the state directory**

In `collective.py`:

```python
def state_dir(project):
    return Path.home() / ".claude" / "collective-state" / project.name
```

```python
def assimilate(project, cwd):
```

```python
def adapt(project, cwd):
    """Return [(new|changed, path)] for team memories this user has not taken."""
```

The three state **filenames** inside that directory — `considered.json`, `pulled.json`, `blocked.json` — do not change. `blocked.json` in particular is security-path vocabulary.

- [ ] **Step 4: Rewrite the verb dispatch in `main()`**

Replace the dispatch block (the `if verb == "promote": ... elif verb == "pull": ...` chain near line 866) with:

```python
    if verb == "assimilate":
        result = assimilate(project, cwd)
        if result:
            print(result, file=sys.stderr)
    elif verb == "adapt":
        if "--take" in sys.argv:
            print(take(cwd, sys.argv[sys.argv.index("--take") + 1]), end="")
        elif "--mark" in sys.argv:
            mark_pulled(project, cwd, sys.argv[sys.argv.index("--mark") + 1:])
        else:
            # First line is where an adapted memory goes. The command used to
            # restate Claude Code's slug rule in prose and got it wrong; the
            # script already knows the directory, so it says it.
            print(f"memory-dir\t{project / 'memory'}")
            # Tab-separated: /collective:adapt parses it, a person can still read it.
            for state, f in adapt(project, cwd):
                print(f"{state}\t{f.stem}\t{f}\t{describe(f)}")
    else:
        status(project, cwd)
```

No alias for the old verb names. `hooks.json` is the only caller of `assimilate` and it is updated in Task 6; the command files are the only callers of `adapt` and they are updated there too.

- [ ] **Step 5: Run the suite to verify it passes**

```bash
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: `no failures`.

- [ ] **Step 6: Verify the CLI dispatch by hand**

The suite calls the functions directly and never goes through `main()`, so exercise the verbs once:

```bash
cd /tmp && rm -rf collective-smoke && mkdir collective-smoke && cd collective-smoke && git init -q
python3 /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts/collective.py status
python3 /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts/collective.py adapt
```

Expected: `status` prints its report without a traceback; `adapt` prints a `memory-dir<TAB>...` line. Then clean up:

```bash
cd /tmp && rm -rf collective-smoke
```

- [ ] **Step 7: Commit**

```bash
cd /Users/colindickson/code/bluehoodie/skills
git add plugins/dreamscape/scripts/
git commit -m "Rename the verbs to assimilate and adapt"
```

---

### Task 4: Re-theme the user-facing output

The status report, the PR title and body, and the branch prefix. This is everything a user or a teammate actually reads.

**Files:**
- Modify: `plugins/dreamscape/scripts/collective.py:738-747` (PR title, body, branch), `:815-846` (`status`)
- Modify: `plugins/dreamscape/scripts/test_collective.py:442` (branch assertion), plus any `capture(ds.status, ...)` assertions

**Interfaces:**
- Consumes: `assimilate()` from Task 3.
- Produces: branch names now prefixed `assimilate/`. Any test asserting on `dreamscape/` must move.

- [ ] **Step 1: Update the branch assertion in the test**

`test_collective.py` line 442 asserts on the dry-run branch prefix:

```python
check("a completed assimilation reports the branch", True,
      "(dry run) branch assimilate/" in (ds.assimilate(s.project, str(s.work)) or ""))
```

Then find any assertion on status output text:

```bash
cd /Users/colindickson/code/bluehoodie/skills
grep -n "capture(ds.status" plugins/dreamscape/scripts/test_collective.py
```

For each hit, read the surrounding `check()` and update any expected substring that uses a label being renamed below (`team memories`, `personal`, `blocked`). Leave expected substrings that name a memory or a count.

- [ ] **Step 2: Run the suite to verify it fails**

```bash
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL'
```

Expected: at least the branch check fails, reporting it got `dreamscape/...`.

- [ ] **Step 3: Rewrite the PR title, body and branch**

In `collective.py`, lines 738–747:

```python
    title = f"collective: assimilate {len(files)} memor{'y' if len(files) == 1 else 'ies'}"
    body = "Assimilated from local Claude Code memory.\n\n" + \
           "\n".join(f"- {s}" for s in shared) + \
           "\n\nEach file was scanned for credentials and rewritten for a team " \
           "audience before landing here. Review the wording as well as the facts."
    # Keyed on content as well as paths: two assimilations of the same memory on
    # the same day would otherwise build the same branch name twice, and the
    # second push is rejected as a non-fast-forward.
    key = digest("".join(f"{k}{v}" for k, v in sorted(files.items())))[:8]
    result = open_pr(root, f"assimilate/{date.today().isoformat()}-{key}", files, title, body)
```

The second body sentence keeps the words "scanned for credentials" verbatim — security-path vocabulary.

- [ ] **Step 4: Rewrite the status labels**

In `status()`, lines 822–846. Only the printed labels change; every variable, every glob, and the `blocked.json` load stay as they are:

```python
    print(f"collective      {len(shared)}" +
          (f"  ({team})" if team else "  (not a git repository)"))
```

```python
    print(f"\nsettling        {len(young)}"
          f"  (assimilable once unchanged for {SETTLE / 3600:g}h)")
```

```python
    kept = [f for f in mine if personal(f.read_text())]
    print(f"\nindividual      {len(kept)}"
          f"  (never assimilated: type {' or '.join(PERSONAL_TYPES)})")
```

```python
    print(f"\nquarantined     {len(blocked)}")
```

Note the deliberate mismatch on that third block: the printed **label** becomes `individual` now, but the **identifiers** stay `personal()` and `PERSONAL_TYPES` until Task 5 renames them. Write it exactly as shown — using `individual()` here would reference a function that does not exist yet. The `type user or feedback` values interpolated at the end are Claude Code's frontmatter vocabulary and are never renamed.

Also update the two explanatory comments in `status()` that say "promoted"/"promotable" to say "assimilated"/"assimilable".

- [ ] **Step 5: Run the suite to verify it passes**

```bash
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: `no failures`.

- [ ] **Step 6: Eyeball the status report**

```bash
cd /tmp && rm -rf collective-smoke && mkdir collective-smoke && cd collective-smoke && git init -q
mkdir -p .collective-memory
python3 /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts/collective.py status
cd /tmp && rm -rf collective-smoke
```

Expected: labels read `collective`, `settling`, `individual`, `pending`, `quarantined` — and the columns still line up. If a label changed width, adjust the padding so the numbers stay in one column.

- [ ] **Step 7: Commit**

```bash
cd /Users/colindickson/code/bluehoodie/skills
git add plugins/dreamscape/scripts/
git commit -m "Re-theme the status report and pull request text"
```

---

### Task 5: Rename the remaining identifiers and rewrite the prose

Internal names a reader of this file will trip over, plus the module docstring and section comments. No behaviour, no output — this task is entirely for the human reading the source.

**Files:**
- Modify: `plugins/dreamscape/scripts/collective.py:2-38` (docstring), `:82` (`TEAM_SUBDIR`), `:217` (`team_dir`), `:271-282` (`PERSONAL_TYPES`, `personal`), and every comment mentioning a renamed thing
- Modify: `plugins/dreamscape/scripts/test_collective.py` — section dividers and comments

**Interfaces:**
- Produces: `COLLECTIVE_SUBDIR`, `collective_dir(cwd)`, `INDIVIDUAL_TYPES`, `individual(text)`. Signatures and return types are unchanged from the names they replace.

- [ ] **Step 1: Rename the four identifiers across both files**

```bash
cd /Users/colindickson/code/bluehoodie/skills/plugins/dreamscape/scripts
python3 - <<'PY'
import pathlib
for name in ("collective.py", "test_collective.py"):
    p = pathlib.Path(name)
    t = p.read_text()
    for old, new in (("TEAM_SUBDIR", "COLLECTIVE_SUBDIR"),
                     ("team_dir", "collective_dir"),
                     ("PERSONAL_TYPES", "INDIVIDUAL_TYPES"),
                     ("def personal(", "def individual("),
                     ("personal(f.read_text())", "individual(f.read_text())"),
                     ("ds.personal(", "ds.individual(")):
        t = t.replace(old, new)
    p.write_text(t)
PY
```

Then check for stragglers — `personal` is a common English word, so this one needs eyes rather than a blind replace:

```bash
grep -n "personal\|team_dir\|TEAM_SUBDIR\|PERSONAL_TYPES" collective.py test_collective.py
```

Every remaining hit should be prose. Judge each: "personal knowledge" describing what the classifier rejects is correct English and can stay; a comment describing the `personal()` function must become `individual()`.

- [ ] **Step 2: Run the suite to verify it still passes**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: `no failures`. A pure rename must not move the count.

- [ ] **Step 3: Rewrite the module docstring**

Replace lines 2–30 of `collective.py` (down to but not including the `Environment:` block already rewritten in Task 2):

```python
"""Collective — share Claude Code memories across a team through the repo.

Memories are written from one person's experience of a codebase, but most of
what they record is not personal: how the sidecar rounds USDC, why the Grafana
tenants are split, which flag wipes the database on restart. That knowledge
currently dies in one laptop's ~/.claude directory. This moves it into the
repo, where the team already has distribution, review and access control.

<repo>/.collective-memory/ is the entire product. Nothing is ever injected into
anyone's memory directory. It is written to by `assimilate`, and read from
deliberately by a person running /collective:adapt. What lands from an adapt is
theirs: an ordinary memory file their next dream owns like any other.

Verbs:
  assimilate  SessionEnd. Finds consolidated memories written since the last
              pass, scans them for credentials, redacts machine-specific detail,
              asks a model which are team knowledge, and opens a pull request.
              Detached. The collective absorbing the individual.
  adapt       List the collective's memories that are new or changed for this
              user. Prints only; /collective:adapt is what writes them.
              `adapt --take <name>` prints one rewritten as the reader's own
              file, `adapt --mark <name>...` records what was taken.
  status      Print what is shared, settling, queued and quarantined.
  scan        Scan a file and print blockers; exit 1 if any. For CI and testing.

Only memories a dream consolidation has already been over are assimilable — see
candidates().
"""
```

The 0.2.0 history paragraph is dropped: it explains a version nobody upgrading to 1.0.0 has run, and the README carries the same story for anyone who wants it.

- [ ] **Step 4: Sweep the remaining comments in both files**

```bash
grep -ni "dreamscape\|/memory-pull\|/memory-share\|/memory-status\|promot" collective.py test_collective.py
```

For each hit, apply the name map. Specifically:
- `/memory-pull` → `/collective:adapt`, `/memory-share` → `/collective:reclaim`, `/memory-status` → `/collective:status`
- "promote"/"promoted"/"promotion" → "assimilate"/"assimilated"/"assimilation", **except** inside the words `promotedAt` and `promotedAt:`, which are frontmatter keys and must not change
- "dreamscape" → "collective", except where it names the old version in a history note

The `# --- promote` and `# --- promotion candidates` section dividers in both files are included here.

- [ ] **Step 5: Verify `promotedAt` survived**

```bash
grep -c "promotedAt" collective.py test_collective.py
```

Expected: non-zero for both. If either is zero, Step 4 over-replaced — restore with `git checkout` and redo it more carefully.

- [ ] **Step 6: Run the suite to verify it passes**

```bash
cd /Users/colindickson/code/bluehoodie/skills
python3 plugins/dreamscape/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: `no failures`.

- [ ] **Step 7: Commit**

```bash
git add plugins/dreamscape/scripts/
git commit -m "Rename internal identifiers and rewrite the script prose"
```

---

### Task 6: Rename the plugin package

The directory, the manifest, the hook, and the three command files. After this task the plugin loads under its new name.

**Files:**
- Rename: `plugins/dreamscape/` → `plugins/collective/`
- Rename: `commands/memory-pull.md` → `commands/adapt.md`, `commands/memory-status.md` → `commands/status.md`, `commands/memory-share.md` → `commands/reclaim.md`
- Modify: `.claude-plugin/plugin.json`, `hooks/hooks.json`, all three command files

**Interfaces:**
- Consumes: verbs `assimilate`, `adapt`, `status` from Task 3; script at `scripts/collective.py` from Task 1.
- Produces: commands `/collective:adapt`, `/collective:status`, `/collective:reclaim`.

- [ ] **Step 1: Move the directory and the command files**

```bash
cd /Users/colindickson/code/bluehoodie/skills
git mv plugins/dreamscape plugins/collective
git mv plugins/collective/commands/memory-pull.md   plugins/collective/commands/adapt.md
git mv plugins/collective/commands/memory-status.md plugins/collective/commands/status.md
git mv plugins/collective/commands/memory-share.md  plugins/collective/commands/reclaim.md
```

- [ ] **Step 2: Confirm the suite still runs from its new home**

```bash
python3 plugins/collective/scripts/test_collective.py | grep '^FAIL' || echo "no failures"
```

Expected: `no failures`. From here on, this is the test command.

- [ ] **Step 3: Rewrite `plugin.json`**

`plugins/collective/.claude-plugin/plugin.json` in full:

```json
{
  "name": "collective",
  "description": "Share Claude Code memories across a team through the repo — your settled team-worthy memories are assimilated out as pull requests, and you adapt the collective's in when you ask for them.",
  "version": "1.0.0",
  "license": "MIT",
  "author": {
    "name": "Colin Dickson",
    "url": "https://github.com/bluehoodie"
  },
  "homepage": "https://github.com/bluehoodie/skills/tree/main/plugins/collective",
  "keywords": ["memory", "team", "sharing", "knowledge", "collective"],
  "commands": "./commands/"
}
```

- [ ] **Step 4: Rewrite `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/collective.py\" assimilate",
            "async": true
          }
        ]
      }
    ]
  }
}
```

Both the script filename and the verb change on this line. Getting one and not the other is the single most likely way to ship a plugin whose hook silently does nothing every session.

- [ ] **Step 5: Update the three command files**

In all three, every `scripts/dreamscape.py` becomes `scripts/collective.py`. Then, per file:

**`commands/adapt.md`** — frontmatter description, and the verb in all three code blocks (`pull` → `adapt`):

```markdown
---
description: Adapt the collective's memories into your own, choosing what you take
---
```

The three commands inside become:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt --take <name>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt --mark <name> [<name>...]
```

In the body prose: "team memories" → "the collective's memories", and the closing line of step 3 keeps its point about `/dream` verbatim. The sentence in step 3 naming `sharedBy` and `promotedAt` must keep those keys spelled exactly as they are.

**`commands/status.md`** — description and the interpretation notes:

```markdown
---
description: Show what the collective holds, what is settling, and what is quarantined
---
```

Its body references `/memory-share` in the last line; that becomes `/collective:reclaim`. The bullet explaining **blocked** entries keeps the word "blocked" — it describes the credential scanner.

**`commands/reclaim.md`** — description, and the opening framing:

```markdown
---
description: Reclaim memories the credential scanner refused, and send the safe ones back through
---
```

Its body's "The automatic path handles clean memories on its own" paragraph stays. Change "The next promotion pass rescans it automatically" to "The next assimilation pass rescans it automatically". Every other sentence in this file is security-path prose and stays verbatim — including "Never propose loosening the scanner to clear a blockage."

- [ ] **Step 6: Verify no command file lost its frontmatter**

```bash
head -3 plugins/collective/commands/*.md
ls plugins/collective/commands/
```

Expected: each file opens with `---` / `description:` / `---`, and the directory holds exactly `adapt.md`, `status.md`, `reclaim.md`. No `README.md` — every `.md` in `commands/` ships as a command.

- [ ] **Step 7: Validate the plugin**

```bash
claude plugin validate plugins/collective --strict
```

Expected: passes clean, no warnings.

- [ ] **Step 8: Commit**

```bash
git add -A plugins/
git commit -m "Rename the plugin package to collective"
```

---

### Task 7: Rewrite the documentation

The plugin README, the CHANGELOG's 1.0.0 entry, the marketplace manifest, and the root README. The repo's `CLAUDE.md` requires every command to be listed in both READMEs.

**Files:**
- Modify: `plugins/collective/README.md`, `plugins/collective/CHANGELOG.md`
- Modify: `.claude-plugin/marketplace.json:43-55`
- Modify: `README.md:55-73`

**Interfaces:**
- Consumes: the command names from Task 6.

- [ ] **Step 1: Rewrite the plugin README**

Apply the name map throughout `plugins/collective/README.md`. The document's arguments are good and stay — this is a rename, not a rewrite. Specifically:

- Title `# dreamscape` → `# collective`
- The ASCII diagram's `PROMOTE` label → `ASSIMILATE`, and `PULL — /memory-pull` → `ADAPT — /collective:adapt`
- The **Promote** and **Pull** paragraph headings → **Assimilate** and **Adapt**
- "Only settled memories are promotable" → "Only settled memories are assimilable"
- The sample status block updated to the Task 4 labels
- The install block:

  ```
  /plugin marketplace add bluehoodie/skills
  /plugin install collective@bluehoodie
  ```

- The commands table:

  | Command | What it does |
  |---------|-------------|
  | [`/collective:adapt`](./commands/adapt.md) | take new or changed memories from the collective into your own |
  | [`/collective:status`](./commands/status.md) | what the collective holds, what is settling, what is quarantined |
  | [`/collective:reclaim`](./commands/reclaim.md) | review what the scanner refused, and why |

- The configuration table's nine variables re-prefixed to `COLLECTIVE_*`, with a row noting `DREAMSCAPE_DRY_RUN` is still read
- The test command → `python3 scripts/test_collective.py`
- The paragraph beginning "Version 0.2.0 did this the other way" is rewritten to say "Before 1.0.0 this plugin was called dreamscape" and keeps its 0.2.0 explanation after it

Keep verbatim: the whole **gates** section's security prose, the credential-scanner reasoning, the graphify caveat about exit codes, and the **Not built** section.

- [ ] **Step 2: Add the CHANGELOG entry**

At the top of `plugins/collective/CHANGELOG.md`, above the existing 0.3.0 entry:

```markdown
## 1.0.0

Renamed from `dreamscape` to `collective`, with Borg-derived verbs. No behaviour
changed in this release.

**This is a breaking rename.** A plugin id has no alias mechanism, so installed
users must reinstall:

```
/plugin uninstall dreamscape@bluehoodie
/plugin install collective@bluehoodie
```

- `promote` is now `assimilate` — the collective absorbing the individual, which
  is what the automatic SessionEnd pass does.
- `/memory-pull` is now `/collective:adapt` — inbound and voluntary.
- `/memory-status` is now `/collective:status`.
- `/memory-share` is now `/collective:reclaim`. That command never shared
  anything; it triages what the credential scanner refused, and the new name
  says so.
- `DREAMSCAPE_*` variables are now `COLLECTIVE_*`. `DREAMSCAPE_DRY_RUN` is still
  read as a fallback, because losing it silently opens real pull requests.
- State moved from `~/.claude/dreamscape-state/` to `~/.claude/collective-state/`.
  It is not migrated: the first run after upgrading re-evaluates your memories and
  offers the whole corpus as new. Both settle on the second pass.
- Pull request branches are now prefixed `assimilate/`.

`.collective-memory/` is unchanged, as are the `sharedBy`, `promotedAt` and
`pulledFrom` frontmatter keys — all of it is committed data in team repos.
```

- [ ] **Step 3: Update the marketplace manifest**

In `.claude-plugin/marketplace.json`, the dreamscape entry becomes:

```json
    {
      "name": "collective",
      "source": "./plugins/collective",
      "description": "Share Claude Code memories across a team through the repo — your settled team-worthy memories are assimilated out as pull requests, and you adapt the collective's in when you ask for them.",
      "category": "productivity",
      "keywords": [
        "memory",
        "team",
        "sharing",
        "knowledge",
        "collective"
      ]
    }
```

The `description` must match `plugin.json` exactly.

- [ ] **Step 4: Update the root README**

Replace the `### [dreamscape](./plugins/dreamscape)` section (lines 55–73):

```markdown
### [collective](./plugins/collective)

Team memory sharing. Memories are written from one person's experience of a codebase, but
most of what they record is not personal — and it currently dies in one laptop's
`~/.claude`. This moves it into the repo, where distribution, review, and access
control already exist. `/plugin install collective@bluehoodie`

`<repo>/.collective-memory/` is the whole product. A `SessionEnd` hook scans your memories for
credentials, asks whether each is team knowledge, and opens a pull request for the ones
that are — only memories that have gone a day without being rewritten, so drafts stay
home. Nothing comes back the other way until you ask:
`/collective:adapt` copies the collective's memories in as ordinary files you own.

Renamed from `dreamscape` in 1.0.0; installed users need to reinstall under the new name.

- [adapt](./plugins/collective/commands/adapt.md) — take new or changed memories from the
  collective into your own memory directory.
- [status](./plugins/collective/commands/status.md) — what the collective holds, what is
  settling, what is quarantined.
- [reclaim](./plugins/collective/commands/reclaim.md) — review the memories the
  credential scanner refused, and why.
```

- [ ] **Step 5: Validate the marketplace**

```bash
cd /Users/colindickson/code/bluehoodie/skills
claude plugin validate . --strict
claude plugin validate plugins/collective --strict
```

Expected: both pass clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Document the collective rename"
```

---

### Task 8: Sweep for anything missed

A rename is only done when the old name is gone from everywhere it was never meant to survive.

**Files:** none modified unless the sweep finds something.

- [ ] **Step 1: Grep for the old name across everything that ships**

```bash
cd /Users/colindickson/code/bluehoodie/skills
grep -rn "dreamscape" --include="*.md" --include="*.json" --include="*.py" \
  plugins/ README.md .claude-plugin/ | grep -v __pycache__
```

Expected — and **only** these:
- `plugins/collective/CHANGELOG.md` — the 1.0.0 migration entry and older entries
- `plugins/collective/README.md` — the "before 1.0.0 this was called dreamscape" line
- `README.md` — the "renamed from dreamscape" line
- `plugins/collective/scripts/collective.py` — the `env()` helper's `DREAMSCAPE_` fallback and its comment
- `plugins/collective/scripts/test_collective.py` — the four env-fallback test lines

Anything else is a miss. Fix it and re-run.

- [ ] **Step 2: Grep for the old command names**

```bash
grep -rn "memory-pull\|memory-share\|memory-status" \
  --include="*.md" --include="*.json" --include="*.py" plugins/ README.md .claude-plugin/
```

Expected: hits only in `CHANGELOG.md`, where they name what changed. Note `memory-dir` is a different string and legitimately survives in `collective.py` and `adapt.md` — it is the tab-separated protocol between them.

- [ ] **Step 3: Grep for the old verbs outside their legitimate homes**

```bash
grep -rn "\"promote\"\|'promote'\|py\" promote\|py\" pull" \
  --include="*.md" --include="*.json" --include="*.py" plugins/
```

Expected: no hits. A hit in `hooks.json` or a command file means the plugin is broken in a way no test catches.

- [ ] **Step 4: Confirm the untouched things are untouched**

```bash
git diff --stat main -- plugins/dream/
grep -rn "\.collective-memory" plugins/collective/scripts/collective.py | head -3
grep -c "sharedBy\|promotedAt\|pulledFrom" plugins/collective/scripts/collective.py
```

Expected: `plugins/dream/` shows no changes; `.collective-memory` still present; the frontmatter keys still present in quantity.

- [ ] **Step 5: Full green run and both validations**

```bash
python3 plugins/collective/scripts/test_collective.py
echo "exit=$?"
claude plugin validate . --strict
claude plugin validate plugins/collective --strict
```

Expected: `exit=0`, zero `FAIL —` lines, both validations clean.

- [ ] **Step 6: Confirm git recorded renames, not rewrites**

```bash
git log --oneline main..HEAD
git diff --stat --find-renames main..HEAD | tail -20
```

Expected: eight commits; the moved files show as renames.

- [ ] **Step 7: Commit anything the sweep fixed**

```bash
git add -A && git commit -m "Fix stragglers from the collective rename" || echo "nothing to fix"
```

---

## Self-Review

**Spec coverage.** Every row of the spec's naming table maps to a task: plugin dir and script filenames → 1 and 6; env prefix and the `DRY_RUN` carve-out → 2; verbs and state dir → 3; branch prefix, PR text and status labels → 4; internal identifiers and prose → 5; commands, manifest and hook → 6; version bump, both READMEs, CHANGELOG and marketplace → 7. The spec's "what does not change" list is asserted in Task 8 Step 4. The success criteria map to Task 8 Steps 1, 5, and 6, and to Task 6 Steps 6–7.

**Two spec details worth calling out.** The spec says state files live in the renamed directory but does not name them; they are `considered.json`, `pulled.json` and `blocked.json`, and Task 3 Step 3 states explicitly that none of the three filenames change. The spec also says `pull()` → `adapt()` "with `take()` and `mark_pulled()` following"; Task 3's Interfaces block overrides that — both keep their names, because `mark_pulled` pairs with `pulled.json`, which is not being renamed. Renaming a function away from the file it writes would be a worse name, not a better one.

**Placeholder scan.** No TBDs. Every code step carries the actual replacement text. The two steps that cannot be fully enumerated in advance — Task 4 Step 1's status assertions and Task 5 Step 4's comment sweep — each ship the grep that finds the sites and the rule for judging each hit, rather than the instruction "update as appropriate".

**Type consistency.** `assimilate(project, cwd)` and `adapt(project, cwd)` keep the signatures of `promote` and `pull`. `env(name)` takes the bare suffix, and every call site in the plan passes `"DRY_RUN"` rather than a full variable name. The one ordering hazard is `personal()` / `PERSONAL_TYPES`: Task 4 changes the status **label** to `individual` while the **identifiers** keep their old names until Task 5. Task 4 Step 4 shows the code with the old identifiers and names the mismatch as deliberate, so a subagent reading tasks out of order cannot write a reference to a function that does not exist yet.
