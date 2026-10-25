/**
 * Cron in human words — the one reader for every place a schedule is shown:
 * Scheduled runs, the Command Center's Autonomous catalogue and an agent's
 * "Runs on its own" card.
 *
 * Standard five-field cron: minute hour day-of-month month day-of-week, with
 * 0 (or 7) = Sunday. describeCron() returns null for shapes it cannot say in a
 * short sentence; callers then show the raw expression in mono, never a guess.
 */

/** Business time is explicit Eastern (the scheduled-runs API default since 2026-10-16). */
export const BUSINESS_TZ = 'America/New_York';

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const DAY_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DOW_NAMES = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
const MONTH_NAMES = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

const isNum = (s) => /^\d+$/.test(s);
const pad2 = (n) => String(n).padStart(2, '0');
const ordinal = (n) => {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
};
const joinAnd = (arr) => (arr.length <= 1 ? arr.join('') : `${arr.slice(0, -1).join(', ')} and ${arr[arr.length - 1]}`);
const toInt = (tok, names) => {
  if (isNum(tok)) return Number(tok);
  const v = names?.[String(tok).toLowerCase()];
  return v === undefined ? NaN : v;
};

/** "1-5" → [1,2,3,4,5] · "mon,wed" → [1,3] · "1,3-5" → [1,3,4,5]; null for steps or anything unusual. */
function listOf(spec, names) {
  const out = [];
  for (const part of String(spec).split(',')) {
    const m = /^([a-z0-9]+)(?:-([a-z0-9]+))?$/i.exec(part);
    if (!m) return null;
    const a = toInt(m[1], names);
    const b = m[2] === undefined ? a : toInt(m[2], names);
    if (!Number.isInteger(a) || !Number.isInteger(b) || b < a) return null;
    for (let i = a; i <= b; i += 1) out.push(i);
  }
  return [...new Set(out)].sort((x, y) => x - y);
}

/** The day part of a sentence: { title: 'Weekdays', on: 'on weekdays' }; null when unreadable. */
function daysOf(dow) {
  if (dow === '*') return { title: 'Daily', on: '' };
  const days = listOf(dow, DOW_NAMES);
  if (!days || days.some((d) => d > 7)) return null;
  const set = [...new Set(days.map((d) => d % 7))].sort((a, b) => a - b);
  const key = set.join(',');
  if (key === '0,1,2,3,4,5,6') return { title: 'Daily', on: '' };
  if (key === '1,2,3,4,5') return { title: 'Weekdays', on: 'on weekdays' };
  if (key === '0,6') return { title: 'Weekends', on: 'on weekends' };
  if (set.length === 1) return { title: `${DAY_NAMES[set[0]]}s`, on: `on ${DAY_NAMES[set[0]]}s` };
  const list = joinAnd(set.map((d) => DAY_SHORT[d]));
  return { title: list, on: `on ${list}` };
}

/**
 * "Weekdays at 08:00", "Daily at 06:00, 14:00 and 22:00", "Every 15 minutes",
 * "On the 1st and 15th at 07:00" — or null when it is not a common shape.
 */
export function describeCron(cron) {
  const parts = String(cron || '').trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const [m, h, dom, mon, dow] = parts;
  if (mon !== '*') return null;
  const days = daysOf(dow);
  if (!days) return null;
  const onDays = days.on ? ` ${days.on}` : '';

  if (dom === '*' && h === '*') {
    if (m === '*') return `Every minute${onDays}`;
    const step = /^\*\/(\d+)$/.exec(m);
    if (step) return `Every ${step[1]} minutes${onDays}`;
    if (isNum(m)) return `Hourly at :${pad2(m)}${onDays}`;
    const mins = listOf(m);
    if (!mins || mins.length < 2 || mins.some((x) => x > 59)) return null;
    const gap = mins[1] - mins[0];
    const even = gap * mins.length === 60 && mins.every((x, i) => i === 0 || x - mins[i - 1] === gap);
    const at = joinAnd(mins.map((x) => `:${pad2(x)}`));
    return even ? `Every ${gap} minutes (${at})${onDays}` : `Hourly at ${at}${onDays}`;
  }
  if (!isNum(m) || Number(m) > 59) return null;

  if (dom === '*') {
    const everyH = /^\*\/(\d+)$/.exec(h);
    if (everyH) return `Every ${everyH[1]} hours at :${pad2(m)}${onDays}`;
    const range = /^(\d+)-(\d+)$/.exec(h);
    if (range) return `Hourly at :${pad2(m)} from ${pad2(range[1])}:${pad2(m)} to ${pad2(range[2])}:${pad2(m)}${onDays}`;
    const hours = listOf(h);
    if (!hours || hours.length > 8 || hours.some((x) => x > 23)) return null;
    return `${days.title} at ${joinAnd(hours.map((x) => `${pad2(x)}:${pad2(m)}`))}`;
  }

  // Day-of-month schedules (monthly). Mixed day-of-month + weekday is too subtle for one line.
  if (dow !== '*') return null;
  const dates = listOf(dom);
  const hours = listOf(h);
  if (!dates || !hours || hours.length > 4 || dates.some((d) => d < 1 || d > 31) || hours.some((x) => x > 23)) return null;
  return `On the ${joinAnd(dates.map(ordinal))} at ${joinAnd(hours.map((x) => `${pad2(x)}:${pad2(m)}`))}`;
}

// ── time zones ──────────────────────────────────────────────────────────────
const TZ_SHORT = {
  'America/New_York': 'ET',
  'US/Eastern': 'ET',
  'America/Chicago': 'CT',
  'US/Central': 'CT',
  'America/Denver': 'MT',
  'America/Phoenix': 'MT',
  'America/Los_Angeles': 'PT',
  'US/Pacific': 'PT',
  UTC: 'UTC',
  'Etc/UTC': 'UTC',
};

/** The zones offered in schedule forms; the current value and the viewer's zone are added when missing. */
export const TZ_OPTIONS = [
  ['America/New_York', 'Eastern (America/New_York)'],
  ['America/Chicago', 'Central (America/Chicago)'],
  ['America/Denver', 'Mountain (America/Denver)'],
  ['America/Phoenix', 'Arizona (America/Phoenix)'],
  ['America/Los_Angeles', 'Pacific (America/Los_Angeles)'],
  ['UTC', 'UTC'],
];

/** "ET" / "PT" / "UTC", else the zone's own short name ("GMT+1"), else the IANA name. A missing zone is Eastern. */
export function zoneLabel(tz) {
  const zone = tz || BUSINESS_TZ;
  if (TZ_SHORT[zone]) return TZ_SHORT[zone];
  try {
    const part = new Intl.DateTimeFormat('en-US', { timeZone: zone, timeZoneName: 'short' })
      .formatToParts(new Date())
      .find((p) => p.type === 'timeZoneName');
    return part ? part.value : zone;
  } catch {
    return zone;
  }
}

export function viewerTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** True when the browser knows the IANA zone (the same check the API makes server-side). */
export function isValidTimezone(tz) {
  if (!tz || typeof tz !== 'string') return false;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/** TZ_OPTIONS plus any extra zones (the value being edited, the viewer's), de-duplicated. */
export function timezoneChoices(...extra) {
  const seen = new Set(TZ_OPTIONS.map(([v]) => v));
  const more = [...new Set(extra.filter((z) => z && !seen.has(z)))];
  return [...TZ_OPTIONS, ...more.map((z) => [z, z])];
}

/** "Daily at 08:15 UTC" — the reading plus its zone, or null when the cron has no plain reading. */
export function describeSchedule(cron, tz) {
  const reading = describeCron(cron);
  return reading ? `${reading} ${zoneLabel(tz)}` : null;
}

// ── validation ──────────────────────────────────────────────────────────────
const FIELDS = [
  { label: 'minute', min: 0, max: 59 },
  { label: 'hour', min: 0, max: 23 },
  { label: 'day-of-month', min: 1, max: 31 },
  { label: 'month', min: 1, max: 12, names: MONTH_NAMES },
  { label: 'weekday', min: 0, max: 7, names: DOW_NAMES },
];

/** null when the expression is a well-formed five-field cron, else one sentence saying what to fix. */
export function validateCron(expr) {
  const parts = String(expr || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length !== 5) return 'A cron has five fields: minute, hour, day of month, month, weekday.';
  for (let i = 0; i < 5; i += 1) {
    const f = FIELDS[i];
    for (const piece of parts[i].split(',')) {
      const m = /^(\*|([a-z0-9]+)(?:-([a-z0-9]+))?)(?:\/(\d+))?$/i.exec(piece);
      if (!m) return `“${piece}” isn’t something the ${f.label} field understands.`;
      if (m[4] !== undefined && Number(m[4]) < 1) return `A step in the ${f.label} field has to be 1 or more.`;
      if (m[1] === '*') continue;
      const a = toInt(m[2], f.names);
      const b = m[3] === undefined ? a : toInt(m[3], f.names);
      if (!Number.isInteger(a) || !Number.isInteger(b)) return `“${piece}” isn’t something the ${f.label} field understands.`;
      if (a < f.min || a > f.max || b < f.min || b > f.max) return `The ${f.label} field takes ${f.min}–${f.max}; “${piece}” is outside that.`;
      if (b < a) return `A range in the ${f.label} field runs low to high (“${piece}”).`;
    }
  }
  return null;
}
