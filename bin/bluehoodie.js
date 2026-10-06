#!/usr/bin/env node
'use strict'

const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawn, spawnSync } = require('child_process')

const ROOT = path.join(__dirname, '..')
const SOURCE = path.join(ROOT, 'plugins')
const PKG = require(path.join(ROOT, 'package.json'))

const CLAUDE = path.join(os.homedir(), '.claude')
const SUPPORT = path.join(CLAUDE, 'bluehoodie')
const MANIFEST = path.join(SUPPORT, 'installed.json')
const CHECK = path.join(SUPPORT, 'update-check.json')
const SOURCE_SPEC = process.env.BLUEHOODIE_SOURCE || 'github:bluehoodie/skills'
const DAY = 24 * 60 * 60 * 1000
// npm is npm.cmd on Windows, which Node only spawns through a shell.
const WIN = process.platform === 'win32'

const USAGE = `bluehoodie ${PKG.version}

  bluehoodie install <plugin>[/<name>]   install a plugin, or one skill or command
  bluehoodie remove  <plugin>[/<name>]   remove what install added
  bluehoodie list                        what is available, and what is installed
  bluehoodie update                      update the CLI, then refresh what is installed

Installs to ${CLAUDE}. Pass --force to overwrite files bluehoodie did not install.`

function die (msg) {
  process.stderr.write(`bluehoodie: ${msg}\n`)
  process.exit(1)
}

function ls (dir) {
  try { return fs.readdirSync(dir).sort() } catch { return [] }
}

function plugins () {
  return fs.readdirSync(SOURCE, { withFileTypes: true })
    .filter(d => d.isDirectory()).map(d => d.name).sort()
}

// Skills are directories holding a SKILL.md; commands are flat .md files.
// Skills come first, which fixes the precedence for a bare <name>.
function contents (plugin) {
  const skillDir = path.join(SOURCE, plugin, 'skills')
  const skills = ls(skillDir)
    .filter(n => fs.existsSync(path.join(skillDir, n, 'SKILL.md')))
    .map(name => ({ name, type: 'skill' }))
  const commands = ls(path.join(SOURCE, plugin, 'commands'))
    .filter(f => f.endsWith('.md'))
    .map(f => ({ name: f.slice(0, -3), type: 'command' }))
  return skills.concat(commands)
}

function pluginVersion (plugin) {
  const f = path.join(SOURCE, plugin, '.claude-plugin', 'plugin.json')
  try { return JSON.parse(fs.readFileSync(f, 'utf8')).version } catch { return '0.0.0' }
}

function readManifest () {
  let raw
  try { raw = fs.readFileSync(MANIFEST, 'utf8') } catch { return { package: PKG.version, entries: {} } }
  try {
    const m = JSON.parse(raw)
    return { package: m.package, entries: m.entries || {} }
  } catch {
    process.stderr.write(`bluehoodie: ${MANIFEST} is unreadable — treating nothing as installed\n`)
    return { package: PKG.version, entries: {} }
  }
}

function writeManifest (m) {
  m.package = PKG.version
  fs.mkdirSync(SUPPORT, { recursive: true })
  fs.writeFileSync(MANIFEST, JSON.stringify(m, null, 2) + '\n')
}

// type disambiguates a skill and a command sharing a name; without it skills win.
function resolve (spec, type) {
  const [plugin, name] = String(spec).split('/')
  if (!plugins().includes(plugin)) die(`unknown plugin: ${plugin}`)
  const items = contents(plugin)
  if (!name) return { plugin, items }
  const item = items.find(i => i.name === name && (!type || i.type === type))
  if (!item) die(`unknown skill or command: ${spec}`)
  return { plugin, items: [item] }
}

function list () {
  const m = readManifest()
  for (const p of plugins()) {
    const shipped = pluginVersion(p)
    console.log(`${p} ${shipped}`)
    for (const it of contents(p)) {
      const e = m.entries[key(it)]
      let mark = ''
      if (e && e.plugin === p) {
        mark = e.version === shipped
          ? '  [installed]'
          : `  [installed ${e.version}, ${shipped} available]`
      }
      console.log(`  ${p}/${it.name}  (${it.type})${mark}`)
    }
  }
  console.log(`\nrunning bluehoodie ${PKG.version}`)
}

function key (item) { return `${item.type}:${item.name}` }

function dest (item) {
  return item.type === 'skill'
    ? path.join(CLAUDE, 'skills', item.name)
    : path.join(CLAUDE, 'commands', `${item.name}.md`)
}

function source (plugin, item) {
  return item.type === 'skill'
    ? path.join(SOURCE, plugin, 'skills', item.name)
    : path.join(SOURCE, plugin, 'commands', `${item.name}.md`)
}

function installScripts (plugin) {
  const src = path.join(SOURCE, plugin, 'scripts')
  if (!fs.existsSync(src)) return
  const target = path.join(SUPPORT, plugin, 'scripts')
  fs.rmSync(target, { recursive: true, force: true })
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.cpSync(src, target, { recursive: true })
  for (const f of fs.readdirSync(target, { recursive: true })) {
    const p = path.join(target, f)
    if (f.endsWith('.sh') && fs.lstatSync(p).isFile()) fs.chmodSync(p, 0o755)
  }
  console.log(`  ${target}`)
}

// ${CLAUDE_PLUGIN_ROOT} is substituted by Claude Code's plugin loader. Nothing
// substitutes it for a loose skill in ~/.claude/skills, where it resolves to an
// empty string — so point it at the support dir ourselves.
function rewrite (target, pluginRoot) {
  const files = fs.statSync(target).isDirectory()
    ? fs.readdirSync(target, { recursive: true }).map(f => path.join(target, f))
    : [target]
  for (const f of files) {
    if (!f.endsWith('.md') || !fs.lstatSync(f).isFile()) continue
    const before = fs.readFileSync(f, 'utf8')
    const after = before.split('${CLAUDE_PLUGIN_ROOT}').join(pluginRoot)
    if (after !== before) fs.writeFileSync(f, after)
  }
}

function install (spec, force, type) {
  const { plugin, items } = resolve(spec, type)
  const m = readManifest()
  const version = pluginVersion(plugin)

  for (const item of items) {
    const target = dest(item)
    const owned = m.entries[key(item)]
    if (fs.existsSync(target) && !force && (!owned || owned.plugin !== plugin)) {
      die(`${target} already exists and was not installed by bluehoodie.\n` +
          '  Move it aside, or re-run with --force.')
    }
  }

  console.log(`installing ${plugin} ${version}`)
  installScripts(plugin)
  for (const item of items) {
    const target = dest(item)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.rmSync(target, { recursive: true, force: true })
    fs.cpSync(source(plugin, item), target, { recursive: true })
    rewrite(target, path.join(SUPPORT, plugin))
    m.entries[key(item)] = { type: item.type, plugin, version }
    console.log(`  ${target}`)
  }
  writeManifest(m)
}

// Deletion targets come from the manifest, not from the shipped plugin tree —
// a shipped skill that was later renamed or dropped must still be removable,
// and its manifest entry must not permanently pin the plugin's support dir.
// That makes the manifest the actual source of paths to delete, so every
// entry is validated for containment under ~/.claude/skills or
// ~/.claude/commands before anything is deleted: a crafted key like
// "skill:../../../outside/victim" must never reach rmSync.
function remove (spec) {
  const [plugin, name] = String(spec).split('/')
  if (!plugins().includes(plugin)) die(`unknown plugin: ${plugin}`)

  const m = readManifest()
  const owned = Object.entries(m.entries)
    .filter(([, e]) => e && typeof e === 'object')
    // The key is authoritative for type as well as name — it's why entries
    // are keyed "${type}:${name}" in the first place. Reading type from the
    // value would let a key/value disagreement delete against the wrong kind.
    .map(([k, e]) => ({ key: k, type: k.slice(0, k.indexOf(':')), name: k.slice(k.indexOf(':') + 1), plugin: e.plugin }))
    .filter(i => i.plugin === plugin && (!name || i.name === name))

  if (!owned.length) die(`nothing installed by bluehoodie matches ${spec}`)

  const targets = owned.map(item => {
    if (item.type !== 'skill' && item.type !== 'command') {
      die(`refusing to remove ${item.key} — unknown type ${item.type}`)
    }
    const resolved = path.resolve(dest(item))
    const allowed = path.join(CLAUDE, item.type === 'skill' ? 'skills' : 'commands')
    // ponytail: string comparison, not realpath — a symlinked ~/.claude/skills
    // would pass. Not reachable from manifest content alone, and realpath
    // costs a syscall on every remove for an attack that already needs write
    // access to ~/.claude. Upgrade to realpath if ~/.claude ever becomes
    // shared or symlinked.
    if (path.dirname(resolved) !== allowed) {
      die(`refusing to remove ${resolved} — outside ${allowed}`)
    }
    return { item, resolved }
  })

  for (const { item, resolved } of targets) {
    fs.rmSync(resolved, { recursive: true, force: true })
    delete m.entries[item.key]
    console.log(`  ${resolved}`)
  }

  if (!Object.values(m.entries).some(e => e.plugin === plugin)) {
    const support = path.join(SUPPORT, plugin)
    if (fs.existsSync(support)) {
      fs.rmSync(support, { recursive: true, force: true })
      console.log(`  ${support}`)
    }
  }
  writeManifest(m)
}

// The running process has the old code loaded, so the self-update step hands
// the refresh to the freshly installed copy via --no-self.
function update (noSelf) {
  if (!noSelf) {
    if (spawnSync('npm', ['install', '-g', SOURCE_SPEC], { stdio: 'inherit', shell: WIN }).status !== 0) {
      // Not `sudo bluehoodie update`: sudo may reset HOME and refresh root's ~/.claude.
      die(`npm install -g ${SOURCE_SPEC} failed.\n  Run it yourself (with sudo if your npm prefix needs it), then: bluehoodie update --no-self`)
    }
    const g = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: WIN })
    const bin = path.join(String(g.stdout).trim(), 'bluehoodie', 'bin', 'bluehoodie.js')
    if (g.status !== 0 || !fs.existsSync(bin)) die(`updated CLI not found at ${bin}`)
    process.exit(spawnSync(process.execPath, [bin, 'update', '--no-self'], { stdio: 'inherit' }).status ?? 1)
  }

  const m = readManifest()
  for (const [k, e] of Object.entries(m.entries)) {
    if (!e || typeof e !== 'object') continue
    const name = k.slice(k.indexOf(':') + 1)
    const spec = `${e.plugin}/${name}`
    // Not through resolve(): it dies on an unknown plugin, and a dropped
    // item must be reported, never fatal and never auto-deleted.
    const shipped = plugins().includes(e.plugin) && contents(e.plugin).some(i => key(i) === k)
    if (!shipped) {
      console.log(`${spec} is no longer shipped — run: bluehoodie remove ${spec}`)
    } else if (e.version !== pluginVersion(e.plugin)) {
      install(spec, false, k.slice(0, k.indexOf(':')))
      console.log(`updated ${spec} ${e.version} -> ${pluginVersion(e.plugin)}`)
    } else {
      console.log(`current ${spec}`)
    }
  }
  for (const p of plugins()) {
    for (const it of contents(p)) {
      if (m.entries[key(it)]?.plugin !== p) console.log(`new: ${p}/${it.name} (${it.type})`)
    }
  }
}

// ponytail: numeric major.minor.patch only, no prerelease tags. Upgrade to
// the `semver` package if versions ever carry -rc suffixes.
function newer (a, b) {
  const x = String(a).split('.').map(Number)
  const y = String(b).split('.').map(Number)
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0)
  return false
}

function readCheck () {
  try { return JSON.parse(fs.readFileSync(CHECK, 'utf8')) || {} } catch { return {} }
}

// update-notifier pattern: print what the last background check found and
// refresh it out of band, so the network never delays the command being run.
function notify () {
  const c = readCheck()
  if (c.latest && newer(c.latest, PKG.version)) {
    process.stderr.write(`bluehoodie ${c.latest} is available — run: bluehoodie update\n`)
  }
  if (!(Date.now() - c.checked < DAY)) {
    spawn(process.execPath, [__filename, '--update-check-worker'], { detached: true, stdio: 'ignore' }).unref()
  }
}

// Failures still stamp `checked`, so a dead network costs one attempt a day.
async function checkWorker () {
  let latest = readCheck().latest
  try {
    const url = process.env.BLUEHOODIE_UPDATE_URL || 'https://raw.githubusercontent.com/bluehoodie/skills/main/package.json'
    // fetch() rejects file: URLs, so a plain path is read directly (tests).
    const text = /^https?:/.test(url)
      ? await (await fetch(url, { signal: AbortSignal.timeout(5000) })).text()
      : fs.readFileSync(url, 'utf8')
    latest = JSON.parse(text).version || latest
  } catch {}
  fs.mkdirSync(SUPPORT, { recursive: true })
  fs.writeFileSync(CHECK, JSON.stringify({ checked: Date.now(), latest }) + '\n')
}

function main (argv) {
  if (argv[0] === '--update-check-worker') return checkWorker().catch(() => {})
  const force = argv.includes('--force')
  const [cmd, spec] = argv.filter(a => !a.startsWith('--'))
  if (cmd !== 'update' && !process.env.BLUEHOODIE_NO_UPDATE_CHECK && !process.env.CI) notify()
  if (cmd === 'update') return update(argv.includes('--no-self'))
  if (cmd === 'list') return list()
  if (cmd === 'install' || cmd === 'remove') {
    if (!spec) die(`${cmd} needs a target, e.g. ${cmd} productivity/dream`)
    return cmd === 'install' ? install(spec, force) : remove(spec)
  }
  if (!cmd) {
    console.log(USAGE)
    process.exit(0)
  }
  process.stderr.write(USAGE + '\n')
  process.exit(1)
}

main(process.argv.slice(2))
