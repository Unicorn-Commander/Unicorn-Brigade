#!/usr/bin/env node
/**
 * Contrast gate for the Unicorn Brigade token layer.
 *
 * Parses src/styles/tokens.css, resolves BOTH themes (dark = :root, light =
 * :root[data-theme="light"]) and asserts WCAG 2.2 AA on every pairing a user
 * can actually see:
 *
 *   4.5:1  text tokens (fg, fg-strong, muted, subtle, accent, ok, warn, danger,
 *          info, live) on every surface (bg, surface, card, elevated, overlay)
 *   4.5:1  on-accent on accent-fill; white on ok/danger/info fills; on-warn on warn-fill
 *   4.5:1  status/accent text on its own soft tint (token at 10% over card)
 *   3.0:1  the focus ring and status dots against every surface (§1.4.11)
 *   1.5:1  hairline borders against the surface they sit on — a VISIBILITY floor
 *          (ours, not WCAG: a card edge is decorative when the fill differs)
 *
 * This exists because "verified AA" comments in CSS files have been wrong
 * before. A human eyeballing HSL triples cannot catch a 4.3:1; a script can,
 * every commit. Never lower a threshold here — change the colour.
 *
 *   node scripts/audit-contrast.mjs            → report, exit 1 on any failure
 *   node scripts/audit-contrast.mjs --verbose  → also print passing pairs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CSS_PATH = path.resolve(HERE, '../src/styles/tokens.css');
const VERBOSE = process.argv.includes('--verbose');

const AA_TEXT = 4.5;
const AA_UI = 3.0;
const BORDER_FLOOR = 1.5;

// ── parse ────────────────────────────────────────────────────────────────────
const css = fs.readFileSync(CSS_PATH, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

function parseBlocks(src) {
  const blocks = [];
  const re = /(:root(?:\[[^\]]+\])*)\s*\{/g;
  let m;
  while ((m = re.exec(src))) {
    const start = src.indexOf('{', m.index);
    let depth = 0;
    let i = start;
    for (; i < src.length; i++) {
      if (src[i] === '{') depth++;
      else if (src[i] === '}') { depth--; if (!depth) break; }
    }
    const body = src.slice(start + 1, i);
    const tokens = {};
    for (const d of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) tokens[d[1]] = d[2].trim();
    blocks.push({ selector: m[1], tokens });
  }
  return blocks;
}

const BLOCKS = parseBlocks(css);
const FAMILIES = ['brigade', 'business', 'graphite'];
/** Real cascade: a block applies when every attribute it demands is active;
 *  higher specificity (more attributes) wins, then source order. */
function resolveTheme(theme, family = 'brigade') {
  const applicable = BLOCKS.map((b, i) => {
    const wantsLight = b.selector.includes('[data-theme="light"]');
    const fam = b.selector.match(/\[data-theme-family="([\w-]+)"\]/);
    if (wantsLight && theme !== 'light') return null;
    if (fam && fam[1] !== family) return null;
    const spec = (b.selector.match(/\[/g) || []).length;
    return { ...b, i, spec };
  }).filter(Boolean).sort((a, b) => a.spec - b.spec || a.i - b.i);
  const out = {};
  for (const b of applicable) Object.assign(out, b.tokens);
  return out;
}

// ── colour maths ─────────────────────────────────────────────────────────────
function hslToRgb(h, s, l) {
  s /= 100; l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let [r, g, b] = [0, 0, 0];
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + m, g + m, b + m].map((v) => Math.round(v * 255));
}
function hex2rgb(h) {
  h = h.replace('#', '');
  if (h.length === 3) h = [...h].map((c) => c + c).join('');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
/** Resolve a token to {rgb,a}; follows var() chains. Triples are HSL channels. */
function color(cell, name, depth = 0) {
  const v = cell[name];
  if (!v || depth > 6) return null;
  const ref = v.match(/^var\((--[\w-]+)\)$/);
  if (ref) return color(cell, ref[1], depth + 1);
  const triple = v.match(/^(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%$/);
  if (triple) return { rgb: hslToRgb(+triple[1], +triple[2], +triple[3]), a: 1 };
  if (v.startsWith('#')) return { rgb: hex2rgb(v), a: 1 };
  return null;
}
const composite = (fg, bgRgb) => fg.rgb.map((c, i) => c * fg.a + bgRgb[i] * (1 - fg.a));
function luminance(rgb) {
  const [r, g, b] = rgb.map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  const l1 = luminance(a);
  const l2 = luminance(b);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}
const hex = (rgb) => '#' + rgb.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');

// ── pairings ─────────────────────────────────────────────────────────────────
const SURFACES = ['--bg', '--surface', '--card', '--elevated', '--overlay'];
const TEXT = ['--fg', '--fg-strong', '--muted', '--subtle', '--accent', '--ok', '--warn', '--danger', '--info', '--live'];
const FILLS = [
  ['--on-accent', '--accent-fill'],
  ['--fg-strong', '--ok-fill'],
  ['--on-warn', '--warn-fill'],
  ['--fg-strong', '--danger-fill'],
  ['--fg-strong', '--info-fill'],
];
const TINTED = ['--accent', '--ok', '--warn', '--danger', '--info', '--live'];
const UI = ['--ring', '--ok', '--warn', '--danger', '--info', '--live', '--accent-fill'];
const BORDERS = ['--border', '--border-strong'];

let failures = 0;
let checks = 0;
const rows = [];

function check(theme, label, ratio, min) {
  checks++;
  const ok = ratio >= min;
  if (!ok) failures++;
  if (!ok || VERBOSE) rows.push(`${ok ? '  ok ' : ' FAIL'}  ${theme.padEnd(15)}  ${label.padEnd(58)} ${ratio.toFixed(2)}:1  (min ${min})`);
}

for (const family of FAMILIES) for (const mode of ['dark', 'light']) {
  const theme = `${family}/${mode}`;
  const cell = resolveTheme(mode, family);
  const need = (n) => {
    const c = color(cell, n);
    if (!c) { console.error(`✖ ${theme}: token ${n} missing or unparsable`); process.exit(2); }
    return c;
  };
  // the fill token for light is light-tinted, so "white" = --fg-strong only in dark;
  // for fills we always use literal white except on-accent / on-warn.
  const WHITE = { rgb: [255, 255, 255], a: 1 };

  for (const s of SURFACES) {
    const bg = need(s).rgb;
    for (const t of TEXT) {
      const fg = need(t);
      check(theme, `${t} on ${s}  (${hex(fg.rgb)} / ${hex(bg)})`, contrast(composite(fg, bg), bg), AA_TEXT);
    }
    for (const u of UI) {
      const c = need(u);
      check(theme, `${u} (ui/ring/dot) on ${s}`, contrast(composite(c, bg), bg), AA_UI);
    }
    for (const b of BORDERS) {
      const c = need(b);
      check(theme, `${b} edge on ${s}`, contrast(composite(c, bg), bg), BORDER_FLOOR);
    }
    // soft tint chips: token at 12% over the surface, with the token as text
    for (const t of TINTED) {
      const tok = need(t);
      const tint = composite({ rgb: tok.rgb, a: 0.10 }, bg);
      check(theme, `${t} text on ${t}/10 tint over ${s}`, contrast(tok.rgb, tint), AA_TEXT);
    }
  }
  for (const [textTok, fillTok] of FILLS) {
    const fill = need(fillTok).rgb;
    const text = textTok === '--fg-strong' && mode === 'light' ? WHITE : need(textTok);
    check(theme, `${textTok === '--fg-strong' ? 'white' : textTok} on ${fillTok}  (${hex(fill)})`, contrast(composite(text, fill), fill), AA_TEXT);
  }
}

console.log(`Contrast gate — ${checks} pairings across ${FAMILIES.length} families × 2 modes`);
for (const r of rows) console.log(r);
if (failures) {
  console.log(`\n✖ ${failures} pairing(s) below threshold. Fix the token in src/styles/tokens.css; do not lower the bar.`);
  process.exit(1);
}
console.log('✓ every pairing clears its threshold');
