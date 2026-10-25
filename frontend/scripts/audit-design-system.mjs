#!/usr/bin/env node
/**
 * Design-system ratchet for Unicorn Brigade.
 *
 * WHY THIS EXISTS
 * The 2026-10 world-class pass is being rolled out by several agent lanes in
 * parallel. Documentation does not survive that: a written rule ("use
 * <Button size='sm'>, never text-[10px]") is followed by most lanes and
 * quietly ignored by some, and nobody reviewing six branches catches the
 * difference. Six months of that is how the codebase reached 125 hard-coded
 * hex colours, 78 arbitrary font sizes, 1,783 raw slate classes, 9 hand-rolled
 * modals and 70 bare spinners.
 *
 * So the rules are executable and they RATCHET: each violation class has a
 * recorded baseline and the gate fails only if a count goes UP. Lanes can
 * land partial migrations safely — the system can only get better.
 *
 *   node scripts/audit-design-system.mjs            → check vs baseline, exit 1 on regression
 *   node scripts/audit-design-system.mjs --report   → full breakdown with file:line
 *   node scripts/audit-design-system.mjs --bless    → rewrite the baseline (after a real fix)
 *   node scripts/audit-design-system.mjs --only <rule-id>  → report one rule
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../src');
const BASELINE_PATH = path.resolve(HERE, 'design-system-baseline.json');
const argv = process.argv.slice(2);
const MODE = argv.includes('--bless') ? 'bless' : argv.includes('--report') ? 'report' : 'check';
const ONLY = argv.includes('--only') ? argv[argv.indexOf('--only') + 1] : null;

const UI_DIR = 'components/ui/';

/** Each rule: what it bans, why, what to do instead, and where it is legitimately unavoidable. */
const RULES = [
  {
    id: 'arbitrary-font-size',
    re: /text-\[\d+(?:\.\d+)?(?:px|rem)\]/g,
    why: '78 arbitrary sizes (8/9/10/11/12/13px) bypassed the type scale; 8–10px text is unreadable and fails accessibility outright.',
    instead: 'A scale step: text-micro (11px floor) / text-caption / text-body-sm / text-body / text-lead / text-heading / text-title / text-display / text-hero.',
    exempt: [],
  },
  {
    id: 'raw-hex-color',
    // (?<!&) so HTML entities like &#123; are not read as colours.
    re: /(?<!&)#[0-9a-fA-F]{6}\b|(?<!&)#[0-9a-fA-F]{3}\b(?![0-9a-fA-F])/g,
    why: 'A hex literal in JSX ignores the theme: it is the same colour on the dark and the light canvas.',
    instead: 'A token class (text-ok, bg-accent-fill) or, in canvas/graph code, getComputedStyle(document.documentElement).getPropertyValue("--ok") via utils/tokens.js.',
    exempt: ['index.css', 'styles/tokens.css', 'utils/tokens.js'],
    onlyIn: (rel) => /\.(jsx|js)$/.test(rel),
  },
  {
    id: 'raw-neutral-palette',
    re: /\b(?:bg|text|border|ring|divide|placeholder|from|via|to|fill|stroke|outline|shadow)-(?:slate|gray|zinc|neutral|stone)-(?:50|[1-9]00|950)\b/g,
    why: '1,783 raw slate classes are why the light theme had to be patched with 30 CSS overrides and why half the pages stay dark on the light canvas.',
    instead: 'Surface tokens (bg-bg / bg-surface / bg-card / bg-elevated), edge tokens (border-border / border-border-strong) and text tokens (text-fg / text-muted / text-subtle).',
    exempt: ['index.css'],
  },
  {
    id: 'raw-status-palette',
    re: /\b(?:bg|text|border|ring|from|via|to|fill|stroke|shadow)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(?:50|[1-9]00|950)\b/g,
    why: 'Status meaning was carried by eleven different hues with no rule (emerald AND green for success, amber AND yellow AND orange for warning).',
    instead: 'text-ok / text-warn / text-danger / text-info / text-live and their -fill variants; soft tints as bg-ok/12 etc.',
    // The agent classification vocabulary is shared verbatim with Stable; its
    // hues are canonical across the two products. Migrate the two together.
    // index.css remaps those same hues for the light theme (a mapping, not a usage).
    exempt: ['utils/agentClass.js', 'components/AgentBadges.jsx', 'index.css'],
  },
  {
    id: 'raw-brand-scale',
    re: /\b(?:bg|text|border|ring|from|via|to|shadow|fill|stroke|divide|outline)-unicorn-(?:50|[1-9]00|950)\b/g,
    why: 'unicorn-N is a palette, not a decision. Pages picked 300/400/500/600 at random, so the same control had four accent shades across the app.',
    instead: 'text-accent (text-safe) / bg-accent-fill + text-on-accent (buttons) / bg-accent/12 (tints) / ring-ring (focus).',
    exempt: ['components/UnicornBrigadeLogo.jsx', 'styles/tokens.css', 'index.css'],
  },
  {
    id: 'off-token-radius',
    // `(?![\w-=])` so a PROP named rounded (<AgentAvatar rounded="rounded-control">) is not a hit.
    re: /\brounded(?:-(?:sm|md|lg|xl|2xl|3xl))?(?![\w-=])(?!\s*=)(?!\})/g,
    why: 'rounded (4px), rounded-md (6), rounded-lg (8), rounded-xl (12), rounded-2xl (16) and rounded-3xl (24) all coexisted on identical components.',
    instead: 'rounded-chip (6) / rounded-control (8) / rounded-card (12) / rounded-pane (16) / rounded-full.',
    exempt: [],
  },
  {
    id: 'off-token-shadow',
    re: /\bshadow-(?:sm|md|lg|xl|2xl|inner)\b/g,
    why: 'Elevation was improvised per component, so dialogs and dock windows sat at visibly different heights.',
    instead: 'shadow-e1 (hairline) / shadow-e2 (card hover) / shadow-e3 (popover, dock window) / shadow-e4 (modal).',
    exempt: [],
  },
  {
    id: 'raw-z-index',
    re: /\bz-(?:\[\d+\]|\d+)\b/g,
    why: 'Fourteen numeric z-indexes with no named order is how a tooltip ends up under a dock window.',
    instead: 'z-raised / z-sticky / z-dock / z-nav / z-overlay / z-modal / z-popover / z-toast / z-tooltip.',
    exempt: [],
  },
  {
    id: 'hand-rolled-modal',
    re: /\bfixed inset-0\b/g,
    why: 'Nine hand-rolled overlays with three scrim treatments and, outside ui/Modal, no focus trap, Escape handling or scroll lock.',
    instead: '<Modal> (dialogs) or <Sheet> (mobile drawers) from components/ui.',
    // CommandPalette is a reviewed dialog (role=dialog, aria-modal, focus trap +
    // restore, Escape); WorkflowVisualization3D's fixed inset-0 is a fullscreen
    // presentation mode with an Exit control and Escape handled by its page.
    exempt: [`${UI_DIR}Modal.jsx`, `${UI_DIR}Sheet.jsx`, 'components/CommandPalette.jsx', 'components/WorkflowVisualization3D.jsx'],
  },
  {
    id: 'bare-spinner',
    re: /\banimate-spin\b/g,
    why: '70 spinners. A spinner says "wait"; a skeleton says "here is the shape of what is coming" and causes no layout shift when it lands.',
    instead: '<LoadingState variant="cards|list|table|stats|text"> for page/section loads; <Button loading> for in-button progress; <Spinner> only inline inside a sentence.',
    exempt: [`${UI_DIR}Spinner.jsx`, `${UI_DIR}Button.jsx`, `${UI_DIR}LoadingState.jsx`],
  },
  {
    id: 'title-as-tooltip',
    re: /\stitle=(?:"|\{)/g,
    // Only the HTML attribute counts: <div title=…>, <button title=…>. A
    // `title` PROP on a component (<Modal title=…>, <PageHeader title=…>) is
    // the component's own API, resolved by looking back to the enclosing tag.
    htmlOnly: true,
    why: 'A title attribute is not a tooltip: it never shows on touch, never on keyboard focus, and is read inconsistently by screen readers.',
    instead: '<Tooltip content="…"> from components/ui (keyboard + touch aware); aria-label for the accessible name.',
    exempt: ['components/AgentAvatar.jsx'],
  },
  {
    id: 'focus-outline-suppressed',
    re: /\bfocus:outline-none\b/g,
    why: 'focus:outline-none also suppresses :focus-visible, which deletes the keyboard focus ring the global stylesheet provides.',
    instead: 'Drop it. The global focus-visible ring (tokens: --ring) applies to every control; add focus-visible:ring-2 focus-visible:ring-ring only on custom surfaces.',
    // The primitives pair every outline-none with a visible ring (reviewed by hand).
    // The palette panel is a tabIndex=-1 container; its input shows focus via
    // focus-within on the search row.
    exempt: ['components/ui/Field.jsx', 'components/ui/Modal.jsx', 'components/ui/Sheet.jsx', 'components/ui/Menu.jsx', 'components/ui/DataTable.jsx', 'components/CommandPalette.jsx'],
  },
  {
    id: 'gradient-heading',
    re: /\b(?:text-gradient|bg-clip-text)\b/g,
    why: 'Every page title in a pink→cyan gradient is noise; the brand gradient is a display moment, not a heading style.',
    instead: '<PageHeader eyebrow title description actions> — plain text-fg-strong titles. The gradient belongs to the wordmark and one hero word.',
    exempt: ['components/UnicornBrigadeLogo.jsx', 'components/Navigation.jsx', 'pages/Login.jsx', 'pages/Register.jsx', 'pages/NotFound.jsx', 'pages/ServerError.jsx', 'index.css'],
  },
  {
    id: 'inline-style-color',
    re: /style=\{\{[^}]*\b(?:color|background|backgroundColor|borderColor|stroke|fill)\s*:/g,
    why: 'Inline colour styles are invisible to the theme and to this audit.',
    instead: 'Token classes; for canvas/graph libraries read the token at runtime via utils/tokens.js.',
    exempt: [],
  },
  {
    id: 'important-override',
    re: /(?:^|[\s"'`])!(?:p[xytblr]?|m[xytblr]?|text|bg|border|rounded|w|h|z|shadow)-/g,
    why: 'An ! override is a component fighting the design system and winning (today: restyling xyflow controls by force).',
    instead: 'Style third-party widgets through their documented class hooks in index.css, under the token layer.',
    exempt: [],
  },
  {
    id: 'raw-error-message',
    re: /\{(?:err|error|e)\.message\}|\$\{(?:err|error|e)\.message\}|\{error\}/g,
    why: 'A raw exception message in the UI reads "Request failed with status code 500" or worse, a stack. The person needs what happened and what to do.',
    instead: '<ErrorState title="Couldn’t load the roster" detail={humanize(err)} onRetry={reload}> and utils/errors.js humanize().',
    exempt: ['utils/errors.js', 'components/ui/Field.jsx'],
  },
];

// ── walk ─────────────────────────────────────────────────────────────────────
function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, out);
    else if (/\.(jsx?|css)$/.test(e.name) && !/\.test\.jsx?$/.test(e.name)) out.push(full);
  }
  return out;
}

const files = walk(SRC);
const results = Object.fromEntries(RULES.map((r) => [r.id, { count: 0, hits: [] }]));

for (const file of files) {
  const rel = path.relative(SRC, file).split(path.sep).join('/');
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split('\n');
  for (const rule of RULES) {
    if (ONLY && rule.id !== ONLY) continue;
    if (rule.exempt.some((e) => rel === e || rel.endsWith(e))) continue;
    if (rule.onlyIn && !rule.onlyIn(rel)) continue;
    let offset = 0;
    lines.forEach((line, i) => {
      const lineStart = offset;
      offset += line.length + 1;
      const t = line.trim();
      // A rule quoted in a comment is not a violation.
      if (t.startsWith('*') || t.startsWith('//') || t.startsWith('/*')) return;
      const re = new RegExp(rule.re.source, 'g');
      let m;
      while ((m = re.exec(line))) {
        if (rule.htmlOnly) {
          // Walk back to the nearest tag opener and keep only lowercase (HTML) tags.
          const before = text.slice(0, lineStart + m.index + 1);
          const open = before.lastIndexOf('<');
          const tag = open >= 0 ? before.slice(open).match(/^<([A-Za-z][\w.-]*)/) : null;
          if (!tag || !/^[a-z]/.test(tag[1])) continue;
        }
        results[rule.id].count += 1;
        results[rule.id].hits.push({ file: rel, line: i + 1, match: m[0] });
      }
    });
  }
}

const current = Object.fromEntries(RULES.map((r) => [r.id, results[r.id].count]));

if (MODE === 'bless') {
  fs.writeFileSync(BASELINE_PATH, `${JSON.stringify(current, null, 2)}\n`);
  console.log('Baseline updated:');
  for (const [k, v] of Object.entries(current)) console.log(`  ${k.padEnd(26)} ${v}`);
  process.exit(0);
}

let baseline = {};
if (fs.existsSync(BASELINE_PATH)) baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));
else {
  console.log('No baseline found — recording the current state as the baseline.');
  fs.writeFileSync(BASELINE_PATH, `${JSON.stringify(current, null, 2)}\n`);
  baseline = current;
}

let regressions = 0;
let total = 0;
console.log('Design-system ratchet — violation counts may only go DOWN');
console.log('  rule'.padEnd(30) + 'now'.padStart(6) + 'base'.padStart(7) + '   ');
for (const rule of RULES) {
  if (ONLY && rule.id !== ONLY) continue;
  const now = current[rule.id];
  const base = baseline[rule.id] ?? now;
  total += now;
  const worse = now > base;
  if (worse) regressions++;
  const mark = worse ? ' ✖ REGRESSION' : now < base ? ' ▼ improved (run --bless to lock in)' : '';
  console.log(`  ${rule.id.padEnd(28)}${String(now).padStart(6)}${String(base).padStart(7)}${mark}`);
  if (MODE === 'report' || worse) {
    console.log(`      why: ${rule.why}`);
    console.log(`      instead: ${rule.instead}`);
    const hits = results[rule.id].hits.slice(0, MODE === 'report' ? 400 : 12);
    for (const h of hits) console.log(`        ${h.file}:${h.line}  ${h.match}`);
    if (results[rule.id].hits.length > hits.length) console.log(`        … ${results[rule.id].hits.length - hits.length} more`);
  }
}
console.log(`  total violations: ${total}`);
if (regressions) {
  console.log(`\n✖ ${regressions} rule(s) regressed. Fix the new violations (see file:line above) or use the primitive the rule names.`);
  process.exit(1);
}
console.log('✓ no rule regressed');
