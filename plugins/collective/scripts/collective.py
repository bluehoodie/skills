#!/usr/bin/env python3
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
  status      Print what is shared, settling, individual, pending and quarantined.
  scan        Scan a file and print blockers; exit 1 if any. For CI and testing.

Only memories a dream consolidation has already been over are assimilable — see
candidates().

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
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path


MIN_CONFIDENCE = float(os.environ.get("COLLECTIVE_MIN_CONFIDENCE") or 0.85)
CLAUDE_BIN = os.environ.get("COLLECTIVE_CLAUDE_BIN") or "claude"

# Only the meaningful-change comparison runs here. "Do these two versions assert
# the same thing, and name the fact that differs" is a narrow question with a
# short answer, and the cheapest model answers it well. The classifier in gate 2
# makes the harder judgment — team knowledge versus personal, plus a rewrite for
# a team audience — and stays on whatever model the session is already using.
#
# An alias rather than a pinned id, so the comparison follows the current Haiku
# instead of aging in place. Pin `claude-haiku-4-5` here if a version needs to
# hold still.
COMPARE_MODEL = os.environ.get("COLLECTIVE_COMPARE_MODEL") or "haiku"
DRY_RUN = os.environ.get("COLLECTIVE_DRY_RUN") == "1"
GRAPH_TIMEOUT = int(os.environ.get("COLLECTIVE_GRAPHIFY_TIMEOUT") or 600)

# How long a memory must go untouched before it is worth a teammate's attention.
# A day means it survived past the session that produced it, which is the whole
# claim being made — not that anything in particular has reviewed it.
SETTLE = float(os.environ.get("COLLECTIVE_SETTLE_HOURS") or 24) * 3600

# One graphify query per candidate, and each is a model call. A session that
# wrote thirty memories should not spend thirty of them on a second opinion.
MAX_GRAPH_QUERIES = int(os.environ.get("COLLECTIVE_GRAPHIFY_MAX_QUERIES") or 8)

# Not under .claude/, which plenty of teams gitignore wholesale — often from a
# global ~/.gitignore nobody remembers writing. That would fail quietly rather
# than loudly: assimilations are built with git plumbing that bypasses ignore rules,
# so the corpus would keep propagating while `git status` never showed the
# directory and no teammate could hand-edit a memory. A path of its own is
# ignored by nobody.
COLLECTIVE_SUBDIR = Path(".collective-memory")


# --------------------------------------------------------------------- gate 1
#
# The only thing standing between a memory that quotes an API key and a pull
# request. Fail closed: a pattern that matches sends the memory to the manual
# queue and it is never pushed by the automatic path.
#
# Credentials are matched by shape, not by entropy. Every credential format that
# matters now carries an issuer prefix, and prefixes do not fire on the commit
# shas, uuids and wikilinks that fill real memories. The one entropy-ish rule —
# a long token mixing case and digits — is deliberately narrow for the same
# reason: lowercase hex is a sha, lowercase-with-dashes is a slug, and neither
# should cost someone a manual review.

BLOCKERS = [
    ("an API key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("a GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("a GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("an AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("a private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")),
]

URL_CREDENTIAL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:@/]+:([^\s:@/]+)@")

# KEY=value, but only for names that announce themselves as secrets. Widening
# this to every uppercase assignment blocked things like DEPLOY_TARGET=... and
# sent most memories to manual review, which defeats the automatic path.
SECRET_NAME = r"[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|CRED|AUTH|PRIVATE|SIGNING|SALT|SESSION)[A-Z0-9_]*"
ASSIGNMENT = re.compile(rf"\b{SECRET_NAME}\s*=\s*[\"']?([^\s\"'`]{{8,}})")
PLACEHOLDER = re.compile(
    r"^(?:your|my|the|some|xxx|changeme|placeholder|example|redacted|dummy|fake|test|\.\.\.|<|\$)",
    re.IGNORECASE)

# Matched whole, not as a prefix. `PASS` is a placeholder; `passw0rd-actual` is
# not, and prefix-matching these would exempt it.
PLACEHOLDER_WORDS = {"pass", "password", "passwd", "pwd", "user", "username",
                     "secret", "token", "key", "apikey", "none", "null"}


def is_placeholder(value):
    return (bool(PLACEHOLDER.match(value))
            or value.lower() in PLACEHOLDER_WORDS
            or set(value) <= {"*"})

# A long token is only suspicious when it mixes upper, lower and digits. That
# excludes shas (lowercase hex), uuids, and [[wikilink-slugs]] without needing a
# special case for each.
LONG_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b")


def scan(text):
    """Return human-readable reasons this text must not be auto-assimilated."""
    hits = []
    for label, pattern in BLOCKERS:
        if pattern.search(text):
            hits.append(f"looks like {label}")
    for value in ASSIGNMENT.findall(text):
        if not is_placeholder(value):
            hits.append("assigns a value to a secret-named variable")
            break
    for value in URL_CREDENTIAL.findall(text):
        if not is_placeholder(value):
            hits.append("looks like a credential in a URL")
            break
    for token in LONG_TOKEN.findall(text):
        mixed = (any(c.islower() for c in token)
                 and any(c.isupper() for c in token)
                 and any(c.isdigit() for c in token))
        if mixed:
            hits.append("contains a long mixed-case token that may be a secret")
            break
    return hits


# --------------------------------------------------------------------- redact
#
# Home paths, private addresses and mDNS names are not secrets — they are
# machine-specific and deanonymizing. Blocking on them would stop nearly every
# memory, since real ones are full of paths. They are rewritten instead, and
# mechanically: an LLM asked to redact a path tends to paraphrase the sentence
# around it, and a memory whose meaning drifted is worse than one with a
# hostname in it.

REDACTIONS = [
    ("a home path", re.compile(r"/(?:Users|home)/[^/\s\"'`]+/"), "~/"),
    ("a private address", re.compile(
        r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"), "<host>"),
    ("an internal hostname", re.compile(
        r"\b[A-Za-z0-9][A-Za-z0-9-]*\.(?:local|lan|internal)\b"), "<host>"),
]


def redact(text):
    """Return (rewritten text, notes). Clean text comes back byte-identical."""
    notes = []
    for label, pattern, replacement in REDACTIONS:
        text, count = pattern.subn(replacement, text)
        if count:
            notes.append(f"redacted {label} ({count})")
    return text, notes


# ----------------------------------------------------------------- filesystem

def resolve(payload):
    """Return (project directory, launch directory) for this session.

    transcript_path is authoritative — it already lives in the directory we
    want, so we never have to re-implement Claude Code's path slugification and
    can never drift from it. Only `assimilate` gets one, from the SessionEnd hook;
    every command-invoked verb takes the cwd fallback, so the two have to agree.
    Claude Code replaces EVERY non-alphanumeric character, not just the slashes:
    keying on `_`, `.` or a space would send status and adapt to a different
    state directory than the one assimilate writes.
    """
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    transcript = payload.get("transcript_path")
    if transcript:
        return Path(transcript).parent, cwd
    # ponytail: Claude Code also truncates at 200 chars and appends a hash of the
    # path. Not reproduced — the hash is internal. Paths that long resolve wrong;
    # copy the hash if one ever shows up.
    slug = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    return Path.home() / ".claude" / "projects" / slug, cwd


def repo_root(cwd):
    out = run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"])
    return Path(out.strip()) if out else None


def collective_dir(cwd):
    root = repo_root(cwd)
    return root / COLLECTIVE_SUBDIR if root else None


def state_dir(project):
    return Path.home() / ".claude" / "collective-state" / project.name


def run(args, input=None, cwd=None, env=None, timeout=120):
    """Run a command and return stdout, or None if it failed."""
    try:
        p = subprocess.run(args, input=input, cwd=cwd, env=env, timeout=timeout,
                           capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def frontmatter(text):
    """Parse the leading --- block. Flat scalars only; that is all memories use."""
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("---")
    block, _, _ = rest.partition("\n---")
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t", "-")):
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def describe(path):
    return frontmatter(path.read_text()).get("description") or path.stem


# ------------------------------------------------------------------ gate 0
#
# What the credential scanner is to secrets, this is to the other kind of leak.
# A memory's `type` already records whether it is about its author — `user` is
# who they are, `feedback` is how they like to be worked with — so that is read
# rather than left to the classifier to infer. Deterministic for the same reason
# gate 1 is: the corpus is git history, so a wrong call here cannot be taken
# back, while a memory that failed to auto-share costs one `/collective:reclaim`.
#
# A memory with no type at all is NOT blocked. Refusing anything unrecognised
# would silently disable assimilation for anyone whose memories lack the field, and
# a gate that quietly does nothing is the failure mode this plugin has already
# been bitten by once. The classifier is still behind this.

INDIVIDUAL_TYPES = ("user", "feedback")


def memory_type(text):
    """The memory's declared `type`, or None.

    Nested under `metadata:`, so read by regex — frontmatter() parses top-level
    scalars only. Anchored to the line so `node_type: memory`, which stamp()
    writes on memories that arrive without frontmatter, is not mistaken for it.
    """
    found = re.search(r"^\s*type:\s*(\S+)", text, re.M)
    return found.group(1) if found else None


def individual(text):
    """True if this memory is about its author rather than the codebase."""
    return memory_type(text) in INDIVIDUAL_TYPES


def lineage(text):
    """The team memory this one was pulled from, or None if nobody pulled it.

    Read with a regex rather than frontmatter(), which parses top-level scalars
    only — this key lives nested under `metadata:`, the way sharedBy does.
    """
    found = re.search(r"^\s*pulledFrom:\s*(\S+)", text, re.M)
    return found.group(1) if found else None


# ------------------------------------------------------------ meaningful change
#
# Gate 2 rewrites every memory for a team audience, and that rewrite is a model
# call, so it varies run to run even on identical input. Without this, Alice
# adapts a memory, her dream rephrases it, she assimilates; Bob adapts that, his dream
# rephrases it, he assimilates — and the two of them take turns rewording one file
# forever, every PR adding nothing but a name in sharedBy.
#
# Measuring only how MUCH text changed would be worse than nothing: `6 decimals`
# to `8 decimals` is one character and is the entire content of that memory. So
# the load-bearing tokens are compared exactly and only the prose around them is
# allowed to be approximately equal.

# Whether two versions of a memory say the same thing is a question about
# meaning, so it is asked of a model rather than guessed from the text. A lexical
# version came first and was wrong in both directions at once, which is what
# argues for the model rather than against it:
#
#   "Grafana tenants are separated by org id"  /  "each org gets its own tenant"
#       — almost no shared vocabulary, identical meaning. Judged a change, so the
#         two teammates keep rewording it at each other forever.
#   "rounds USDC before writing to Postgres"  /  "writes USDC before rounding"
#       — identical vocabulary, opposite meaning. Judged a reword, so a real
#         correction is swallowed in silence. This is the dangerous one.
#
# No arrangement of token sets, stemming or diff ratios separates those two cases,
# because the thing being measured is not in the tokens.

CHANGE_PROMPT = """Two versions of one team memory. Decide whether the new version \
asserts anything the current one does not.

A reword is NOT a change: different phrasing, different sentence order, synonyms, \
a tidier explanation, or the same fact stated from another angle. A change means a \
different value, identifier, path, version, threshold, condition, or order of \
operations — or a fact added or removed.

You must NAME the fact that differs. If you cannot name one, it is a reword.

CURRENT:
{old}

NEW:
{new}

Return ONLY this JSON, no prose and no code fence:
{{"changed": true|false, "what": "<the one fact that differs, or null>"}}"""


def meaningful(old, new):
    """(changed, what) — whether `new` asserts anything `old` does not.

    Requiring the model to name the differing fact is what keeps it honest: a
    reword has nothing to name, so "I cannot name it" and "it is phrasing" are the
    same answer. The name it gives also ends up in the pull request body, which is
    the thing a reviewer actually wants to read.
    """
    if " ".join(old.lower().split()) == " ".join(new.lower().split()):
        return False, None      # identical but for whitespace and case; no call needed

    out = run([CLAUDE_BIN, "-p", "--model", COMPARE_MODEL,
               CHANGE_PROMPT.format(old=old, new=new)], timeout=180)
    start, end = (out.find("{"), out.rfind("}")) if out else (-1, -1)
    if start < 0 or end < 0:
        # Fail toward shipping. A pull request nobody wanted is read and closed by
        # a human; a correction suppressed here is lost with nothing to review.
        return True, "could not be compared"
    try:
        verdict = json.loads(out[start:end + 1])
    except ValueError:
        return True, "could not be compared"
    return bool(verdict.get("changed")), verdict.get("what")


def body_only(text):
    """Everything below the frontmatter — what two memories have to differ in."""
    if not text.lstrip().startswith("---"):
        return text.strip()
    _, _, rest = text.lstrip().partition("---")
    _, _, tail = rest.partition("\n---")
    return tail.strip()


# ------------------------------------------------------------------ manifest
#
# The manifest is the queue. Keying on content hash rather than a timestamp
# means a memory is considered exactly once per version of itself: rewriting it
# makes it a candidate again, re-reading it does not.

def manifest_path(project):
    return state_dir(project) / "considered.json"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def settling(f):
    """True while a memory is still being revised.

    Raw auto-memory is one session's impression of a codebase, and impressions
    get rewritten. Waiting until a memory has gone SETTLE hours untouched is what
    separates a durable claim from a draft, and it asks nothing of any other
    tool: the file's own mtime is the whole signal. Anything that revises the
    memory — the user, auto-memory, a consolidation pass — restarts the clock,
    which is the behaviour we want from all three.
    """
    return time.time() - f.stat().st_mtime < SETTLE


def candidates(project):
    memory = project / "memory"
    seen = load_json(manifest_path(project), {})
    out = []
    for f in sorted(memory.glob("*.md")):
        if f.name == "MEMORY.md" or settling(f):
            continue
        text = f.read_text()
        if individual(text):
            continue
        if seen.get(f.name) != digest(text):
            out.append(f)
    return out


def mark_considered(project, paths):
    seen = load_json(manifest_path(project), {})
    for f in paths:
        seen[f.name] = digest(f.read_text())
    save_json(manifest_path(project), seen)


# -------------------------------------------------------------------- gate 3
#
# Six people assimilating independently will write about the same fact. The
# classifier is given the existing corpus so it can answer "extend that one"
# instead of "add another", which keeps the shared directory flat. graphify, if
# installed, supplies semantic neighbours the flat index would miss — but it is
# an enrichment, never a dependency: a corpus this small is well within what the
# index alone handles, and a failed graph build must not stop an assimilation.

def graphify_context(team, pending):
    """Semantic neighbours for each candidate, or "" when no graph can be built.

    The graph is built in a staging directory holding the corpus *and* the
    candidates, never in the repo. Building in the shared directory was the
    first version and it dropped a `graphify-out/` tree into the shared
    directory on every assimilation — build artifacts in everyone's checkout.

    Staging is also what makes the query useful. With only the corpus graphed,
    graphify can describe overlaps between memories the team already has, but
    can never answer the question that matters here: does this new memory
    duplicate one of them. The candidate has to be a node to be a neighbour.
    """
    if os.environ.get("COLLECTIVE_GRAPHIFY") == "0" or not shutil.which("graphify"):
        return ""
    corpus = [f for f in team.glob("*.md") if f.name != "MEMORY.md"]
    if not corpus or not pending:
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for f in corpus:
            (stage / f.name).write_text(f.read_text())
        # Prefixed so a candidate never overwrites the corpus file it may be
        # about to extend — that collision is exactly the case worth asking about.
        for f in pending:
            (stage / f"candidate-{f.name}").write_text(f.read_text())

        args = ["graphify", "extract", "."]
        backend = os.environ.get("COLLECTIVE_GRAPHIFY_BACKEND")
        if backend:
            args += ["--backend", backend]
        run(args, cwd=str(stage), timeout=GRAPH_TIMEOUT)

        # graphify exits 0 when every semantic chunk fails — a missing backend
        # package and an exhausted API quota both look like success to a return
        # code. The graph file is the only trustworthy signal that anything got
        # built, so it is what we check.
        if not (stage / "graphify-out" / "graph.json").exists():
            return ""

        asked = pending[:MAX_GRAPH_QUERIES]
        notes = []
        for f in asked:
            out = run(["graphify", "query",
                       f"Which existing memories overlap with candidate-{f.stem}?",
                       "--budget", "600"], cwd=str(stage), timeout=180)
            if out and out.strip():
                notes.append(f"- {f.stem}: {out.strip()}")
        if len(pending) > len(asked):
            notes.append(f"- ({len(pending) - len(asked)} further candidates not queried)")

    if not notes:
        return ""
    return ("\n\nGraph neighbours for each candidate (advisory — the graph is built "
            "from the same text you are reading, so treat it as a second opinion, "
            "not evidence):\n" + "\n".join(notes) + "\n")


def corpus_index(team):
    entries = [f"- {f.stem}: {describe(f)}" for f in sorted(team.glob("*.md"))
               if f.name != "MEMORY.md"]
    return "\n".join(entries) if entries else "(empty — nothing shared yet)"


PROMPT = """You are deciding which of one engineer's Claude Code memories belong to their whole team.

Team knowledge is a durable fact about the codebase, infrastructure, deployment, \
data model, or a team-wide convention — something a new teammate would need and \
could not get from reading the code. Personal knowledge is about this individual: \
who they are, how they like to be worked with, their hardware, their preferences, \
or a correction that only makes sense given their habits. When a memory mixes \
both, share it only if the team-relevant part stands on its own without the \
personal framing; rewrite it in `body` so it does.

Memories already shared with the team:
{corpus}
{graph}
Candidates:
{candidates}

Return ONLY a JSON array, one object per candidate, no prose and no code fence:
[{{"name": "<candidate name>",
   "shareable": true|false,
   "confidence": 0.0-1.0,
   "reason": "<one sentence>",
   "extends": "<name of an existing shared memory this duplicates, or null>",
   "body": "<the full memory file to write, frontmatter included, rewritten for a \
team audience: no first-person reference to the author, no personal framing. \
When `extends` is set, this is the MERGED file that replaces the existing one. \
Omit when shareable is false.>"}}]"""


def classify(team, files):
    blob = "\n\n".join(
        f"--- {f.stem} ---\n{f.read_text()}" for f in files)
    prompt = PROMPT.format(corpus=corpus_index(team),
                           graph=graphify_context(team, files),
                           candidates=blob)
    out = run([CLAUDE_BIN, "-p", prompt], timeout=600)
    if not out:
        return []
    start, end = out.find("["), out.rfind("]")
    if start < 0 or end < 0:
        return []
    try:
        return json.loads(out[start:end + 1])
    except ValueError:
        return []


# ------------------------------------------------------------------- the PR
#
# Built with plumbing so the working tree and index are never touched. A
# background job that runs `git checkout` in someone's repo while they have
# uncommitted work is exactly the kind of thing that pages you at 3am.

def open_pr(root, branch, files, title, body):
    fetched = run(["git", "-C", str(root), "fetch", "-q", "origin"])
    if fetched is None:
        return None
    head = run(["git", "-C", str(root), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    base = (head or "origin/main").strip()
    base_sha = run(["git", "-C", str(root), "rev-parse", base])
    if not base_sha:
        return None
    base_sha = base_sha.strip()

    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))

        def git(*args, **kw):
            return run(["git", "-C", str(root), *args], env=env, **kw)

        if git("read-tree", base_sha) is None:
            return None
        for relpath, content in sorted(files.items()):
            blob = git("hash-object", "-w", "--stdin", input=content)
            if not blob:
                return None
            if git("update-index", "--add", "--cacheinfo",
                   f"100644,{blob.strip()},{relpath}") is None:
                return None
        tree = git("write-tree")
        if not tree:
            return None
        commit = git("commit-tree", tree.strip(), "-p", base_sha, "-m", title)
        if not commit:
            return None
        commit = commit.strip()
        if git("update-ref", f"refs/heads/{branch}", commit) is None:
            return None

    if DRY_RUN:
        return f"(dry run) branch {branch} at {commit[:8]}"
    if run(["git", "-C", str(root), "push", "-q", "origin",
            f"refs/heads/{branch}:refs/heads/{branch}"]) is None:
        return None
    if not shutil.which("gh"):
        return f"branch {branch} pushed — `gh` not installed, open the PR manually"
    url = run(["gh", "pr", "create", "--head", branch, "--base", base.split("/", 1)[-1],
               "--title", title, "--body", body], cwd=str(root), timeout=120)
    return url.strip() if url else f"branch {branch} pushed — `gh pr create` failed"


# ------------------------------------------------------------------ provenance

# Fields that belong to one side of the fence and are dropped crossing it.
# originSessionId points at one person's transcript and means nothing to anyone
# else; modified describes their copy, not the shared one; pulledFrom is the
# reader's own bookkeeping and says nothing to the team.
DROP_FIELDS = ("originSessionId", "modified", "sharedBy", "promotedAt", "pulledFrom")


def respan(body, name, add):
    """Rewrite a memory's frontmatter: drop DROP_FIELDS, insert `add` under metadata.

    Dropping first means re-running this is idempotent — the key it is about to
    write is the key it just removed.
    """
    if not body.lstrip().startswith("---"):
        body = f"---\nname: {name}\nmetadata:\n  node_type: memory\n---\n\n{body}"
    _, _, rest = body.lstrip().partition("---")
    front, _, tail = rest.partition("\n---")

    lines = [l for l in front.splitlines()
             if not any(l.strip().startswith(f"{d}:") for d in DROP_FIELDS)]
    for i, line in enumerate(lines):
        if line.strip() == "metadata:":
            lines[i + 1:i + 1] = add
            break
    else:
        lines += ["metadata:"] + add

    return "---" + "\n".join(lines) + "\n---" + tail


def stamp(body, name, existing=None):
    """Normalise an assimilated memory's frontmatter for the shared corpus."""
    author = (run(["git", "config", "user.email"]) or "unknown").strip() or "unknown"
    authors = []
    if existing:
        found = re.search(r"^\s*sharedBy:\s*\[(.*)\]", existing, re.M)
        if found:
            authors = [a.strip() for a in found.group(1).split(",") if a.strip()]
    if author not in authors:
        authors.append(author)

    return respan(body, name, [f"  sharedBy: [{', '.join(authors)}]",
                               f"  promotedAt: {date.today().isoformat()}"])


# ----------------------------------------------------------------- assimilate

def assimilate(project, cwd):
    team = collective_dir(cwd)
    if team is None:
        return "not a git repository"
    root = repo_root(cwd)

    pending = candidates(project)
    if not pending:
        return "nothing new"

    blocked, clean = {}, []
    for f in pending:
        reasons = scan(f.read_text())
        if reasons:
            # Deliberately not marked considered: leaving it a candidate means
            # editing the memory to remove the secret re-runs the scan for free.
            blocked[f.name] = reasons
        else:
            clean.append(f)
    save_json(state_dir(project) / "blocked.json", blocked)

    if not clean:
        return f"{len(blocked)} blocked, nothing to assimilate"

    verdicts = classify(team, clean)
    if not verdicts:
        # A rate limit, an expired token and a timeout all arrive here as an
        # empty list. Marking these considered would retire them permanently on
        # a failure nobody sees — the hook is detached and its stderr goes
        # nowhere. Leave them queued; the next session evaluates them for free.
        return "classifier unavailable — retrying next session"

    by_name = {f.stem: f for f in clean}

    files, shared = {}, []
    for v in verdicts:
        f = by_name.get(v.get("name"))
        if not f or not v.get("shareable") or not v.get("body"):
            continue
        if float(v.get("confidence") or 0) < MIN_CONFIDENCE:
            continue
        body, _ = redact(v["body"])
        # Re-scan the model's output. It was asked to rewrite the memory, and a
        # rewrite can reintroduce anything gate 1 removed.
        if scan(body):
            blocked[f.name] = ["rewrite reintroduced a blocked pattern"]
            continue
        # Recorded lineage beats the classifier's guess. classify() is shown
        # corpus names and descriptions, never bodies, so once /dream has merged
        # a pulled memory into a file of its own and renamed it there is nothing
        # left to match on — and the same fact lands in the corpus twice.
        target = lineage(f.read_text()) or v.get("extends") or f.stem
        prior = team / f"{target}.md"
        existing = prior.read_text() if prior.exists() else None
        # A memory someone pulled is an ordinary memory, so it becomes a candidate
        # again after their next dream — and by then the dream has probably reworded
        # it. The incumbent wins ties on principle: the team's wording has already
        # been through a pull request and a local paraphrase has not, so only a
        # difference in what the memory asserts is worth another one.
        note = v.get("reason", "")
        if existing:
            changed, what = meaningful(body_only(existing), body_only(body))
            if not changed:
                continue
            note = what or note
        files[str(COLLECTIVE_SUBDIR / f"{target}.md")] = stamp(body, target, existing)
        verb = "extends" if existing else "adds"
        shared.append(f"{verb} `{target}` — {note}")

    save_json(state_dir(project) / "blocked.json", blocked)

    if not files:
        mark_considered(project, clean)
        return f"{len(clean)} evaluated, none met the bar, {len(blocked)} blocked"

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
    if not result:
        # Not marked considered on purpose. open_pr returns None for anything
        # transient — offline at SessionEnd is the common one — and marking here
        # would drop the assimilation permanently and silently.
        return "PR failed — branch left unpushed"
    mark_considered(project, clean)
    return result


# ---------------------------------------------------------------------- adapt
#
# The read path is a listing, nothing more. /collective:adapt writes the files the
# person picks, as their own plain memories — no prefix, no read-only bit, no
# managed block. Once written they are indistinguishable from ones they wrote,
# which is the point: /dream then merges, prunes and rewrites them like any other.
#
# Keyed by content digest rather than a timestamp, for the same reason the
# assimilation manifest is: a memory the team edited comes back as changed, and
# re-reading the directory changes nothing.

def pulled_path(project):
    return state_dir(project) / "pulled.json"


def adapt(project, cwd):
    """Return [(new|changed, path)] for team memories this user has not taken."""
    team = collective_dir(cwd)
    if team is None or not team.is_dir():
        return []
    taken = load_json(pulled_path(project), {})
    out = []
    for f in sorted(team.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        if taken.get(f.name) == digest(f.read_text()):
            continue
        out.append(("changed" if f.name in taken else "new", f))
    return out


def take(cwd, name):
    """The team memory rewritten as the reader's own file, ready to be written.

    Their copy is theirs: the team's sharedBy and promotedAt come off, and what
    goes on is the one thing only they need — where it came from. /dream owns
    the file from here and may merge and rename it, and when that copy is
    assimilated back, this is what tells assimilate which memory it descends from
    instead of leaving the classifier to guess from a name that has changed.
    """
    f = collective_dir(cwd) / (name if name.endswith(".md") else f"{name}.md")
    return respan(f.read_text(), f.stem, [f"  pulledFrom: {f.stem}"])


def mark_pulled(project, cwd, names):
    team = collective_dir(cwd)
    if team is None:
        return
    taken = load_json(pulled_path(project), {})
    for name in names:
        f = team / (name if name.endswith(".md") else f"{name}.md")
        if f.exists():
            taken[f.name] = digest(f.read_text())
    save_json(pulled_path(project), taken)


# --------------------------------------------------------------------- status

def status(project, cwd):
    team = collective_dir(cwd)
    shared = [f for f in sorted(team.glob("*.md")) if f.name != "MEMORY.md"] \
        if team and team.is_dir() else []
    blocked = load_json(state_dir(project) / "blocked.json", {})
    pending = candidates(project)

    print(f"collective      {len(shared)}" +
          (f"  ({team})" if team else "  (not a git repository)"))
    for f in shared:
        print(f"  {f.stem}")

    # Without this line the gate is invisible: a directory of memories written
    # today shows `pending 0` and nothing explains why.
    mine = [f for f in sorted((project / "memory").glob("*.md"))
            if f.name != "MEMORY.md"]
    young = [f for f in mine if settling(f)]
    print(f"\nsettling        {len(young)}"
          f"  (assimilable once unchanged for {SETTLE / 3600:g}h)")
    for f in young:
        print(f"  {f.stem}")

    # Held back by type, not by timing — these never become assimilable at all,
    # so without a line of their own they would look like they were still waiting.
    kept = [f for f in mine if individual(f.read_text())]
    print(f"\nindividual      {len(kept)}"
          f"  (never assimilated: type {' or '.join(INDIVIDUAL_TYPES)})")
    for f in kept:
        print(f"  {f.stem}")

    print(f"\npending         {len(pending)}")
    for f in pending:
        print(f"  {f.stem}")
    print(f"\nquarantined     {len(blocked)}")
    for name, reasons in sorted(blocked.items()):
        print(f"  {name}: {'; '.join(reasons)}")


# ----------------------------------------------------------------------- main

def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else "status"

    if verb == "scan":
        text = Path(sys.argv[2]).read_text()
        for reason in scan(text):
            print(reason)
        return 1 if scan(text) else 0

    payload = {}
    if not sys.stdin.isatty():
        payload = load_json_str(sys.stdin.read())
    project, cwd = resolve(payload)

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
    return 0


def load_json_str(text):
    try:
        return json.loads(text)
    except ValueError:
        return {}


if __name__ == "__main__":
    sys.exit(main())
