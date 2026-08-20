#!/usr/bin/env python3
"""skill-usage.py — which globally installed skills and commands went unused.

  skill-usage.py [--days N | --since YYYY-MM-DD] [--json]

Inventories every skill and command that is available to *every* session on this
machine — user-level files in ~/.claude, cloud-synced skills, and installed
marketplace plugins — then scans the session transcripts in the window for
invocations of each one. Project-level `.claude/skills` inside a repo are
deliberately out of scope: they are part of that repo, not of the global set.

Read-only. It never deletes, moves or rewrites anything.

Two things it does NOT do, on purpose:

  * It does not grep transcripts for skill names. Every session's transcript
    contains a `skill_listing` attachment naming every installed skill, so a
    grep marks all of them used. Usage is read structurally instead, from
    `Skill` tool_use blocks and `<command-name>` slash-command expansions.

  * It does not read ~/.claude/plugins/installed_plugins.json. That is Claude
    Code's private state; `claude plugin list --json` is the supported route
    and is what this uses. With no `claude` on PATH, plugins are reported as
    unknown rather than guessed at.

Env overrides exist for the test fixture:
  CLEANUP_CLAUDE_HOME   default ~/.claude
  CLEANUP_PLUGIN_JSON   file holding `claude plugin list --json` output;
                        default is to run the CLI. Set to "" to skip plugins.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# `name:` at column 0 inside the frontmatter block. Folded values (description:
# >) continue on indented lines, so anchoring to column 0 cannot pick one up.
FRONT_NAME = re.compile(r"^name:[ \t]*(.+?)[ \t]*$", re.M)
COMMAND_TAG = re.compile(r"<command-name>/([\w:.-]+)</command-name>")


def now():
    return datetime.now(timezone.utc)


def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def day(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d") if dt else "—"


def mtime(path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None


def frontmatter_name(md, fallback):
    """A skill's declared name, which need not match its directory.

    Claude Code lists ~/.claude/skills/session-start-hook/ as `session-start-hook`
    even though its frontmatter says `startup-hook-skill`, so the directory is
    the invocation name here — but plugin loading also consults frontmatter, and
    the two disagreeing is exactly the case that would fake an unused skill.
    Both are recorded, and either one matching counts as a use.
    """
    try:
        head = md.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return fallback
    if not head.startswith("---"):
        return fallback
    end = head.find("\n---", 3)
    block = head[3:end] if end > 0 else head[3:]
    m = FRONT_NAME.search(block)
    if not m:
        return fallback
    return m.group(1).strip().strip("\"'") or fallback


# ---------------------------------------------------------------- inventory

class Item(dict):
    """One installed skill or command. `token` is what an invocation looks like."""


def make(token, name, kind, source, path, installed, owner=None, plugin=None,
         note="", aliases=()):
    return Item(
        token=token, name=name, kind=kind, source=source, path=str(path),
        installed=installed, owner=owner, plugin=plugin, note=note,
        aliases=[a for a in aliases if a and a != token], uses=0, last=None,
    )


def as_list(value, default):
    if value is None:
        return list(default)
    return list(value) if isinstance(value, list) else [value]


def component_dirs(root, manifest, key, default):
    """Resolve a plugin manifest's skills/commands paths against the plugin root."""
    declared = default
    try:
        declared = as_list(json.loads(manifest.read_text(encoding="utf-8")).get(key), default)
    except (OSError, ValueError, AttributeError):
        pass
    return [(root / str(d).lstrip("./")).resolve() for d in declared]


def plugin_items(root, prefix, source, installed, plugin_id):
    """Skills and commands a plugin contributes, named the way they are invoked."""
    items = []
    manifest = root / ".claude-plugin" / "plugin.json"

    for skills_dir in component_dirs(root, manifest, "skills", ["./skills/"]):
        if skills_dir.is_file() and skills_dir.name == "SKILL.md":
            candidates = [skills_dir]
        elif skills_dir.is_dir():
            candidates = sorted(skills_dir.glob("*/SKILL.md"))
            if (skills_dir / "SKILL.md").is_file():
                candidates.append(skills_dir / "SKILL.md")
        else:
            continue
        for md in candidates:
            name = md.parent.name if md.parent != skills_dir else frontmatter_name(md, md.parent.name)
            declared = frontmatter_name(md, name)
            items.append(make(f"{prefix}:{name}", name, "skill", source, md,
                              installed or day(mtime(md)), plugin=plugin_id,
                              aliases=[f"{prefix}:{declared}"]))

    for cmd_dir in component_dirs(root, manifest, "commands", ["./commands/"]):
        if not cmd_dir.is_dir():
            continue
        for md in sorted(cmd_dir.rglob("*.md")):
            # A subfolder namespaces the invocation: commands/git/sync.md is
            # /plugin:git:sync.
            rel = md.relative_to(cmd_dir).with_suffix("")
            name = ":".join(rel.parts)
            items.append(make(f"{prefix}:{name}", name, "command", source, md,
                              installed or day(mtime(md)), plugin=plugin_id))
    return items


def installed_plugins(plugin_json):
    """`claude plugin list --json`, or a fixture file, or nothing."""
    if plugin_json is not None:
        if plugin_json == "":
            return [], None
        try:
            return json.loads(Path(plugin_json).read_text(encoding="utf-8")), None
        except (OSError, ValueError) as e:
            return [], f"could not read {plugin_json}: {e}"
    try:
        out = subprocess.run(["claude", "plugin", "list", "--json"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"`claude plugin list --json` did not run ({e}); plugins not inventoried"
    if out.returncode != 0:
        return [], "`claude plugin list --json` failed; plugins not inventoried"
    try:
        return json.loads(out.stdout or "[]"), None
    except ValueError:
        return [], "`claude plugin list --json` returned unparseable output"


def bluehoodie_owned(home):
    """Entries this repo's own installer put in ~/.claude, keyed "<type>:<name>"."""
    try:
        raw = json.loads((home / "bluehoodie" / "installed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = raw.get("entries") or {}
    return {k: v for k, v in entries.items() if isinstance(v, dict)}


def inventory(home, plugin_json):
    items, notes = [], []

    plugins, err = installed_plugins(plugin_json)
    if err:
        notes.append(err)
    for p in plugins:
        pid = p.get("id") or ""
        prefix = pid.split("@")[0]
        root = Path(p.get("installPath") or "")
        if not prefix or not root.is_dir():
            continue
        source = "plugin" if p.get("enabled", True) else "plugin (disabled)"
        found = plugin_items(root, prefix, source, day(parse_ts(p.get("installedAt"))), pid)
        for it in found:
            it["owner"] = "marketplace"
        items += found

    skills_root = home / "skills"
    for entry in sorted(skills_root.glob("*")) if skills_root.is_dir() else []:
        if not entry.is_dir() or entry.name == "synced":
            continue
        # `claude plugin init` scaffolds a whole plugin here; it loads as
        # <name>@skills-dir, and its skills are namespaced, not bare.
        if (entry / ".claude-plugin" / "plugin.json").is_file():
            found = plugin_items(entry, entry.name, "skills-dir plugin", day(mtime(entry)),
                                 f"{entry.name}@skills-dir")
            for it in found:
                it["owner"] = "skills-dir"
            items += found
            continue
        md = entry / "SKILL.md"
        if md.is_file():
            items.append(make(entry.name, entry.name, "skill", "user", md, day(mtime(md)),
                              owner="user", aliases=[frontmatter_name(md, entry.name)]))

    synced = skills_root / "synced"
    for entry in sorted(synced.glob("*")) if synced.is_dir() else []:
        md = entry / "SKILL.md"
        if entry.is_dir() and md.is_file():
            items.append(make(entry.name, entry.name, "skill", "synced", md, day(mtime(md)),
                              owner="synced", aliases=[frontmatter_name(md, entry.name)],
                              note="managed at claude.ai — deleting it locally only lasts until the next sync"))

    commands_root = home / "commands"
    for md in sorted(commands_root.rglob("*.md")) if commands_root.is_dir() else []:
        name = ":".join(md.relative_to(commands_root).with_suffix("").parts)
        items.append(make(name, name, "command", "user", md, day(mtime(md)), owner="user"))

    owned = bluehoodie_owned(home)
    for it in items:
        if it["owner"] == "user":
            entry = owned.get(f"{it['kind']}:{it['name']}")
            if entry:
                it["owner"] = "bluehoodie"
                it["plugin"] = entry.get("plugin")
    return items, notes


# ------------------------------------------------------------------- usage

def demangle(tool_name):
    """skill__foo__bar is the tool form of foo:bar (lossy — matched loosely)."""
    return tool_name[len("skill__"):].replace("__", ":")


def scan(home, cutoff):
    """Invocations at or after cutoff: token -> [count, last seen]."""
    used, sessions, total = {}, set(), 0
    projects = home / "projects"
    if not projects.is_dir():
        return used, sessions, total

    def hit(token, ts, path):
        nonlocal total
        if not token:
            return
        total += 1
        sessions.add(path)
        entry = used.setdefault(token, [0, None])
        entry[0] += 1
        if entry[1] is None or ts > entry[1]:
            entry[1] = ts

    for path in sorted(projects.rglob("*.jsonl")):
        fallback = mtime(path)
        # Cheap skip: a transcript untouched since before the window holds
        # nothing in it. Appends bump mtime, so this never drops a live one.
        if fallback and fallback < cutoff:
            continue
        try:
            fh = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"Skill"' not in line and "<command-name>" not in line and '"skill__' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                ts = parse_ts(rec.get("timestamp")) or fallback
                if ts is None or ts < cutoff:
                    continue
                message = rec.get("message") or {}
                content = message.get("content")
                blocks = [content] if isinstance(content, str) else (content or [])
                for block in blocks:
                    if isinstance(block, str):
                        for m in COMMAND_TAG.finditer(block):
                            hit(m.group(1), ts, str(path))
                        continue
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        for m in COMMAND_TAG.finditer(block.get("text") or ""):
                            hit(m.group(1), ts, str(path))
                    elif block.get("type") == "tool_use":
                        name = block.get("name") or ""
                        args = block.get("input")
                        if name == "Skill" and isinstance(args, dict):
                            hit(args.get("skill"), ts, str(path))
                        elif name.startswith("skill__"):
                            hit(demangle(name), ts, str(path))
    return used, sessions, total


def session_count(home, cutoff):
    """Transcripts with any activity in the window — how much evidence there is."""
    projects = home / "projects"
    if not projects.is_dir():
        return 0
    n = 0
    for path in projects.rglob("*.jsonl"):
        ts = mtime(path)
        if ts and ts >= cutoff:
            n += 1
    return n


def attribute(items, used):
    """Match invocation tokens onto inventory. Ambiguity resolves toward 'used'."""
    by_token, by_name = {}, {}
    for it in items:
        for token in [it["token"]] + it["aliases"]:
            by_token.setdefault(token, []).append(it)
            by_name.setdefault(token.split(":")[-1], []).append(it)

    unmatched = {}
    for token, (count, last) in used.items():
        targets = by_token.get(token)
        if not targets:
            # A bare token matches every entry of that name — two skills can
            # share one. Marking both used keeps a live one from being offered
            # for deletion; the opposite error loses work.
            targets = by_name.get(token.split(":")[-1])
        if not targets:
            unmatched[token] = [count, last]
            continue
        seen = set()
        for it in targets:
            if id(it) in seen:
                continue
            seen.add(id(it))
            it["uses"] += count
            if it["last"] is None or (last and last > it["last"]):
                it["last"] = last
    return unmatched


# ------------------------------------------------------------------ output

def table(rows, columns):
    width = [len(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            width[i] = max(width[i], len(cell))
    out = ["  " + "  ".join(c.ljust(width[i]) for i, c in enumerate(columns)).rstrip()]
    for row in rows:
        out.append("  " + "  ".join(c.ljust(width[i]) for i, c in enumerate(row)).rstrip())
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, help="window length in days (default 30)")
    group.add_argument("--since", help="window start, YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.since:
        try:
            start = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            sys.stderr.write("skill-usage: --since wants YYYY-MM-DD\n")
            return 2
        if start > now():
            sys.stderr.write("skill-usage: --since is in the future\n")
            return 2
        days = max(1, (now() - start).days)
    else:
        days = args.days if args.days and args.days > 0 else 30
        start = now() - timedelta(days=days)

    home = Path(os.environ.get("CLEANUP_CLAUDE_HOME") or (Path.home() / ".claude"))
    items, notes = inventory(home, os.environ.get("CLEANUP_PLUGIN_JSON"))
    used, _, invocations = scan(home, start)
    unmatched = attribute(items, used)

    for it in items:
        it["last"] = day(parse_ts(it["last"])) if isinstance(it["last"], str) else day(it["last"])
        # Installed after the window opened: absence of use is not evidence.
        it["too_new"] = it["installed"] != "—" and it["installed"] > day(start)

    items.sort(key=lambda i: (i["source"], i["kind"], i["token"]))
    fresh = [i for i in items if i["uses"] == 0 and i["too_new"]]
    unused = [i for i in items if i["uses"] == 0 and not i["too_new"]]
    active = [i for i in items if i["uses"] > 0]

    report = {
        "window": {"from": day(start), "to": day(now()), "days": days},
        "sessions_in_window": session_count(home, start),
        "invocations_in_window": invocations,
        "used": active, "unused": unused, "too_new": fresh,
        "unmatched": sorted(unmatched),
        "notes": notes,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    print(f"window   {report['window']['from']} .. {report['window']['to']}  ({days} days)")
    print(f"evidence {report['sessions_in_window']} sessions active, "
          f"{invocations} skill/command invocations")
    for n in notes:
        print(f"note     {n}")

    print(f"\nUNUSED ({len(unused)})")
    if unused:
        print(table([[i["token"], i["kind"], i["source"], i["owner"] or "—", i["installed"]]
                     for i in unused],
                    ["name", "kind", "source", "owner", "installed"]))
    elif active:
        print("  nothing — everything installed old enough to judge was used")
    else:
        print("  nothing to judge in this window")

    if fresh:
        print(f"\nTOO NEW TO JUDGE ({len(fresh)}) — installed inside the window")
        print(table([[i["token"], i["kind"], i["source"], i["installed"]] for i in fresh],
                    ["name", "kind", "source", "installed"]))

    print(f"\nUSED ({len(active)})")
    print(table([[i["token"], i["kind"], i["source"], str(i["uses"]), i["last"]] for i in active]
                or [["—", "", "", "", ""]], ["name", "kind", "source", "uses", "last"]))

    if report["unmatched"]:
        print(f"\nINVOKED BUT NOT INSTALLED ({len(report['unmatched'])})"
              " — project-level, or since removed")
        print("  " + ", ".join(report["unmatched"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
