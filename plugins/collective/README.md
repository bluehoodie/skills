# collective

Share Claude Code memories across a team through the repo.

Memories are written from one person's experience of a codebase, but most of what
they record is not personal: how the sidecar rounds USDC, why the Grafana tenants
are split, which flag wipes the database on restart. That knowledge currently dies
in one laptop's `~/.claude` directory. Collective moves it into the repo, where the
team already has distribution, review, and access control.

## How it works

`<repo>/.collective-memory/` is the entire product. One directory of markdown, one
file per memory, versioned like everything else in the repo. Nothing is ever
injected into your memory directory behind your back.

```
   ~/.claude/projects/<slug>/memory/
     clob-v2-order-signing.md     ← yours, written by you or by /dream
             │
             │  ASSIMILATE — SessionEnd, once the memory has settled
             │  pull request, never main
             ▼
   ┌──────────────────────────────────────┐
   │    <repo>/.collective-memory/*.md    │
   │        (one file per memory)         │
   └──────────────────────────────────────┘
             │
             │  ADAPT — /collective:adapt, when you ask for it
             │  copied in as a normal 644 memory, frontmatter stripped
             ▼
   ~/.claude/projects/<slug>/memory/
     grafana-tenant-split.md      ← yours now; /dream merges and prunes it
```

**Assimilate** (`assimilate`) runs detached at SessionEnd. It finds settled memories written
since the last pass and puts each through four gates.

**Adapt** (`/collective:adapt`) runs when you run it. It lists the team memories that are
new to you or have changed since you last took them, you pick, and the chosen ones
land in your memory directory as ordinary files — no `team-` prefix, no `sharedBy`
or `promotedAt` frontmatter, normal permissions. From then on they are yours: `/dream`
merges, rewrites and prunes them like anything else you wrote. The one thing that
comes along is a `pulledFrom` line naming the memory it descends from, which is what
lets it go home again as an edit rather than a duplicate.

The obvious alternative is to do this the other way — a SessionStart hook mirroring
the whole corpus in as chmod 444 `team-*.md` clones and rebuilding a managed block
in `MEMORY.md`. That puts read-only files inside the one directory `/dream` exists
to rewrite, which is a latent bug, not merely extra machinery. Copies you own and
can edit are the whole point.

## Only settled memories are assimilable

A memory reaches the gates once it has gone `COLLECTIVE_SETTLE_HOURS` (default 24)
without being rewritten. Raw auto-memory is one session's impression of a codebase,
and impressions get revised; surviving a day untouched is the difference between a
durable claim and a draft. Anything that rewrites the memory restarts the clock —
you, auto-memory, a consolidation pass — which is the right answer for all three.

The signal is the file's own mtime, so this asks nothing of any other tool.
`/collective:status` shows what is still settling, so a directory of memories written
today never reads as a plugin that quietly does nothing:

```
settling        3  (assimilable once unchanged for 24h)
individual      2  (never assimilated: type user or feedback)
```

### Memories about you are never assimilated

A memory's frontmatter already records whether it is about its author. `user` is who
you are — role, expertise, preferences. `feedback` is how you like to be worked with.
Neither is the team's business, and both are excluded before the classifier is called,
by reading `metadata.type` rather than asking a model to infer it.

Only `project` and `reference` memories are ever eligible. That is deliberately
stricter than it needs to be: a team-wide convention filed as `feedback` — "always run
migrations before the tests" — will not auto-share at all; nothing routes it to the
team except re-filing its `type` as `project` or `reference` and letting it settle
again. The asymmetry is the point. A memory that failed to share costs one manual
retype; a memory about you that reached the team repo is in git history for good.

A memory with **no** type is not blocked. Refusing anything unrecognised would quietly
disable assimilation for anyone whose memories lack the field, and a gate that silently
does nothing is a failure mode this plugin has already been bitten by. The classifier
still sits behind this one, so untyped memories get judged rather than waved through.

### collective does not require dream

They are separate plugins and neither reads the other's state. `/dream` is
mentioned throughout this README because the two compose well — a consolidation
rewrites the memories it improves, which restarts their settle clock, and deletes
the ones it finds stale, which stops them being assimilated at all. That makes what
reaches the team better. None of it is required, and collective never looks for
it: install either one alone and it works.

## The gates

**1 — credential scan.** Deterministic, no model, fail-closed. Matches credentials
by issuer prefix (`sk-`, `ghp_`, `AKIA`, `xox[baprs]-`, JWTs, private key blocks),
secret-named assignments, connection-string passwords, and long mixed-case tokens.
A hit is never auto-pushed; it lands in a queue for `/collective:reclaim`.

Prefixes rather than entropy, because real memories are full of commit shas, uuids
and `[[wikilink-slugs]]`, and a scanner that blocks those sends everything to
manual review. For the same reason home paths, RFC1918 addresses and `*.local`
hostnames are **redacted** rather than blocked — mechanically, not by a model. An
LLM asked to redact a path paraphrases the sentence around it, and a memory whose
meaning drifted is worse than one with a hostname in it.

**2 — classify and rewrite.** One `claude -p` call over the whole batch. Team
knowledge is a durable fact about the codebase, infrastructure, or a team-wide
convention. Personal knowledge is about the individual — who they are, their
hardware, how they like to be worked with. Mixed memories are shared only if the
team-relevant part stands alone, rewritten so it does. Below
`COLLECTIVE_MIN_CONFIDENCE` (default 0.85), nothing ships.

The model's output is re-scanned before it lands. A rewrite can reintroduce
anything gate 1 removed.

**3 — dedup.** The classifier is given the existing corpus, so it answers "extend
that one" instead of "add another" and the shared directory stays flat. Extending
appends you to `sharedBy` rather than creating a second file.

**4 — meaningful change.** A candidate that extends an existing memory only ships if
it asserts something that memory does not. Without this the corpus thrashes, and the
mechanism is worth spelling out: gate 2 rewrites *every* memory for a team audience,
and that rewrite is a model call, so it is not stable run to run. You adapt a memory,
your next `/dream` rephrases it, it settles, it assimilates. A teammate adapts your
wording, their dream rephrases it, they assimilate. Left alone the two of you take turns
rewording one file forever, and every pull request adds nothing but a name in
`sharedBy`.

Deciding it is a question about meaning, so a model is asked — and required to *name*
the fact that differs. A reword has nothing to name, so "I cannot name it" and "it is
phrasing" are the same answer, and the name it does give goes into the pull request
body, which is what a reviewer wants to read anyway.

The question is narrow and the answer is short, so it runs on Haiku
(`COLLECTIVE_COMPARE_MODEL`, default `haiku`) rather than on whatever the session is
using. Gate 2 is the expensive judgment — team knowledge versus personal, plus a
rewrite for a team audience — and stays on the session's model. An alias rather than a
pinned id, so this follows the current Haiku instead of aging in place.

A lexical version came first and is instructive, because it was wrong in both
directions at once:

| | shared vocabulary | actual meaning | lexical verdict |
|---|---|---|---|
| "tenants are separated by org id" vs "each org gets its own tenant" | almost none | identical | change — thrashes |
| "rounds USDC before writing" vs "writes USDC before rounding" | every word | opposite | reword — correction lost |

No arrangement of token sets, stemming or diff ratios separates those, because what
is being measured is not in the tokens. Two things are still decided without a model:
text identical but for whitespace and case needs no call, and a comparison that
cannot be made **ships anyway**. A pull request nobody wanted is read and closed by a
human; a correction suppressed here would be lost with nothing left to review.

Recorded lineage outranks the classifier's guess. What `classify()` sees of the
corpus is names and descriptions, never bodies, so once a pulled memory has been
merged into a file of its own and renamed — a consolidation pass is the usual
culprit — nothing is left to match on and the same fact is filed a second time.
`pulledFrom` makes that case a fact rather than an inference: the memory extends
what it came from, whatever it has since been renamed to. It is stripped on the
way out — where a memory came from is your bookkeeping, not the team's.

Nothing guarantees the key survives. It is ordinary frontmatter in a file you own,
and a tool that rewrites memories may normalise it away; if that happens, dedup
falls back to the classifier and behaves as it would have anyway. Best-effort, and
never a dependency.

If [graphify](https://github.com/Graphify-Labs/graphify) has a working backend, it
also graphs the corpus **and the candidates together** in a staging directory and
queries each candidate for its neighbours. The candidate has to be a node to be a
neighbour — graphing the corpus alone can describe overlaps between memories the
team already has, but never answers whether the new one duplicates them. Staging
also keeps `graphify-out/` out of your checkout.

This is advisory context for the classifier, never a dependency, and never a
verdict on its own — the graph is built from the same text the classifier is
already reading, so it is a second opinion rather than evidence.

Presence of the binary is not enough. graphify's semantic extraction needs one of
its LLM backends (`openai`, `claude`, `gemini`, `deepseek`, `kimi`, `ollama`) with
a key or a local server, and **it exits 0 when every chunk fails** — a missing
package and an exhausted quota both look like success to a return code. Collective
therefore checks for `graph.json` on disk rather than trusting the exit status, and
contributes nothing when it is absent. Set `COLLECTIVE_GRAPHIFY_BACKEND` to pin
one; one query per candidate, capped at `COLLECTIVE_GRAPHIFY_MAX_QUERIES`.

The PR is built with git plumbing (`hash-object` / `write-tree` / `commit-tree`).
The working tree and index are never touched: a background job running `git
checkout` in someone's repo while they have uncommitted work is exactly the kind
of thing that pages you at 3am.

A memory is only recorded as evaluated once its assimilation actually completed. A
classifier that timed out or a push that never reached the remote — being offline
at SessionEnd is the ordinary case — leaves the batch queued for the next session.
The hook is detached, so anything dropped here would be dropped silently.

## Install

```
/plugin marketplace add bluehoodie/skills
/plugin install collective@bluehoodie
```

Then, in any repo the team shares:

```bash
mkdir -p .collective-memory && git add .collective-memory
```

That directory is the whole contract. No server, no second clone, no path mapping —
the repo you are already in is the team identity.

It sits at the repo root rather than under `.claude/` because plenty of teams
gitignore that directory wholesale, frequently from a global `~/.gitignore` written
years ago and long forgotten. Under an ignored path this breaks quietly rather than
loudly: assimilations are built with git plumbing that bypasses ignore rules, so the
corpus would keep propagating while `git status` stayed silent and no teammate could
hand-edit a memory. A path of its own is ignored by nobody.

## Commands

| Command | What it does |
|---------|-------------|
| [`/collective:adapt`](./commands/adapt.md) | take new or changed memories from the collective into your own |
| [`/collective:status`](./commands/status.md) | what the collective holds, what is settling, what is quarantined |
| [`/collective:reclaim`](./commands/reclaim.md) | review what the scanner refused, and why |

## Configuration

| Variable | Default | |
|---|---|---|
| `COLLECTIVE_SETTLE_HOURS` | `24` | hours a memory must go untouched to be assimilable |
| `COLLECTIVE_MIN_CONFIDENCE` | `0.85` | classifier threshold to auto-assimilate |
| `COLLECTIVE_CLAUDE_BIN` | `claude` | executable used for the model calls |
| `COLLECTIVE_COMPARE_MODEL` | `haiku` | model that judges whether a change means anything |
| `COLLECTIVE_GRAPHIFY` | on | set `0` to skip the graphify pass |
| `COLLECTIVE_GRAPHIFY_BACKEND` | auto | pin a graphify backend instead of auto-detecting |
| `COLLECTIVE_GRAPHIFY_MAX_QUERIES` | `8` | candidates queried for graph neighbours |
| `COLLECTIVE_GRAPHIFY_TIMEOUT` | `600` | seconds allowed for the graph build |
| `COLLECTIVE_DRY_RUN` | off | set `1` to build the branch but never push |

## Tests

```bash
python3 scripts/test_collective.py
```

Sandboxed `$HOME`, throwaway git repos, no model calls. The scan cases are
enumerated one per line rather than looped: a false positive costs a manual
review, a false negative leaks a credential, so a missing case should read as a
missing line.

## Not built

- **No consolidation of the shared corpus.** Team memories go stale like any
  other, and nothing prunes `.collective-memory/`. `/dream` consolidates the copy
  you adapted, in your own directory, and never writes back — so a memory you have
  fixed locally is still wrong for everyone who adapts it next. Add a scheduled pass
  over the shared directory when the corpus is big enough to drift.
- **Adapting is one-way and one-shot.** A memory you took and then edited is
  divergent, and `/collective:adapt` will offer the newer team version without knowing
  what you changed. Merging is yours to do.
- **No cross-repo memories.** Knowledge that spans repos has nowhere to live.
  Add a second store when something concrete needs one.
- **`sharedBy` is advisory.** It records who assimilated a memory, not who verified
  it. Git history is the real provenance.
