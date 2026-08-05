#!/usr/bin/env node
'use strict'

const fs = require('fs')
const os = require('os')
const path = require('path')

const ROOT = path.join(__dirname, '..')
const SOURCE = path.join(ROOT, 'plugins')
const PKG = require(path.join(ROOT, 'package.json'))

const CLAUDE = path.join(os.homedir(), '.claude')
const SUPPORT = path.join(CLAUDE, 'bluehoodie')
const MANIFEST = path.join(SUPPORT, 'installed.json')

const USAGE = `bluehoodie ${PKG.version}

  bluehoodie install <plugin>[/<name>]   install a plugin, or one skill or command
  bluehoodie remove  <plugin>[/<name>]   remove what install added
  bluehoodie list                        what is available, and what is installed

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
  try { return JSON.parse(fs.readFileSync(MANIFEST, 'utf8')) } catch {
    return { package: PKG.version, entries: {} }
  }
}

function writeManifest (m) {
  m.package = PKG.version
  fs.mkdirSync(SUPPORT, { recursive: true })
  fs.writeFileSync(MANIFEST, JSON.stringify(m, null, 2) + '\n')
}

function resolve (spec) {
  const [plugin, name] = String(spec).split('/')
  if (!plugins().includes(plugin)) die(`unknown plugin: ${plugin}`)
  const items = contents(plugin)
  if (!name) return { plugin, items }
  const item = items.find(i => i.name === name)
  if (!item) die(`unknown skill or command: ${spec}`)
  return { plugin, items: [item] }
}

function list () {
  const m = readManifest()
  for (const p of plugins()) {
    const shipped = pluginVersion(p)
    console.log(`${p} ${shipped}`)
    for (const it of contents(p)) {
      const e = m.entries[it.name]
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

// Filled in by Task 3.
function installScripts (plugin) {}

function install (spec, force) {
  const { plugin, items } = resolve(spec)
  const m = readManifest()
  const version = pluginVersion(plugin)

  for (const item of items) {
    const target = dest(item)
    const owned = m.entries[item.name]
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
    m.entries[item.name] = { type: item.type, plugin, version }
    console.log(`  ${target}`)
  }
  writeManifest(m)
}

function main (argv) {
  const force = argv.includes('--force')
  const [cmd, spec] = argv.filter(a => !a.startsWith('--'))
  if (cmd === 'list') return list()
  if (cmd === 'install' || cmd === 'remove') {
    if (!spec) die(`${cmd} needs a target, e.g. ${cmd} productivity/dream`)
    return cmd === 'install' ? install(spec, force) : remove(spec)
  }
  console.log(USAGE)
  process.exit(cmd ? 1 : 0)
}

main(process.argv.slice(2))
