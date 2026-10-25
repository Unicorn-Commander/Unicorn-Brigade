/**
 * uishot --script for the autonomy catalogue lane (P-00092, task e7816874).
 *
 *   node ~/.claude/tools/uishot/uishot.mjs --url http://localhost:5121 \
 *     --routes "/command?view=autonomous,/agent/the-general,/agent/maj-devops,/scheduled-runs,/docs" \
 *     --viewport desktop --viewport mobile --script frontend/dev/uishot-autonomy.mjs \
 *     --out <dir> --no-fail --wait-ms 3000
 *
 * Every route: dismiss the first-run wizard (localStorage + reload).
 * /command (Autonomous view): the default "Needs attention" view (lower half),
 *   "All" with healthy groups folded, the unclaimed jobs by owner and host, the
 *   host filter, a search, the Register dialog (blank → human validation errors
 *   → filled, with "How a script reports its runs" open), an outside job's
 *   run-history sheet, the org chart with its clock badges (+ a tooltip), and a
 *   badge click landing on that agent's card. Nothing is submitted, so the
 *   mock's state is untouched.
 * /scheduled-runs: the New dialog (Responsibility field) and a run's sheet.
 * /docs: the "Autonomous jobs" guide section and the PUT endpoint.
 * Every step is optional: a missing control (empty / error scenario) is
 * logged and skipped, never fatal.
 */
const SETTLE = Number(process.env.UISHOT_SETTLE_MS || 1200);

async function dismissWizard(page, helpers) {
  const hasWizard = await page.evaluate(() =>
    [...document.querySelectorAll('[role="dialog"]')].some(
      (d) => /^Getting started/.test(d.getAttribute('aria-label') || '') || /Welcome to Unicorn Brigade/.test(d.textContent || '')
    )
  );
  await page.evaluate(() => {
    try {
      localStorage.setItem('wizard-completed', 'true');
    } catch {}
  });
  if (hasWizard) {
    helpers.log('wizard present — marking completed and reloading');
    await page.reload({ waitUntil: 'networkidle2' });
    await helpers.sleep(2500);
  }
}

/** Click the first visible element matching `selector` whose text (or aria-label) includes — or, with exact, equals — `text`. */
async function clickText(page, selector, text, { exact = false } = {}) {
  return page.evaluate(
    (sel, t, ex) => {
      const want = t.toLowerCase();
      const el = [...document.querySelectorAll(sel)].find((e) => {
        const r = e.getBoundingClientRect();
        if (!(r.width > 0 && r.height > 0)) return false;
        const textOf = (e.textContent || '').trim().toLowerCase();
        const aria = (e.getAttribute('aria-label') || '').toLowerCase();
        return ex ? textOf === want || aria === want : `${textOf} ${aria}`.includes(want);
      });
      if (!el) return false;
      el.scrollIntoView({ block: 'center' });
      el.click();
      return true;
    },
    selector,
    text,
    exact
  );
}

/** A CSS selector for the control a <label> with this text points at (inside the open dialog). */
async function fieldSelector(page, labelText) {
  return page.evaluate((t) => {
    const dialog = [...document.querySelectorAll('[role="dialog"]')].pop() || document;
    const label = [...dialog.querySelectorAll('label')].find((l) => l.textContent.replace('*', '').trim() === t);
    return label && label.htmlFor ? `#${CSS.escape(label.htmlFor)}` : null;
  }, labelText);
}

async function typeInto(page, labelText, value, { clear = true } = {}) {
  const sel = await fieldSelector(page, labelText);
  if (!sel) return false;
  await page.focus(sel);
  if (clear) {
    await page.$eval(sel, (el) => el.select?.());
    await page.keyboard.press('Backspace');
  }
  await page.type(sel, value, { delay: 2 });
  return true;
}

async function scrollDialogTo(page, text) {
  await page.evaluate((t) => {
    const dialog = [...document.querySelectorAll('[role="dialog"]')].pop();
    const el = dialog && [...dialog.querySelectorAll('button, label, p, h2')].find((e) => (e.textContent || '').includes(t));
    el?.scrollIntoView({ block: 'start' });
  }, text);
}

const press = async (page, key, helpers) => {
  await page.keyboard.press(key);
  await helpers.sleep(400);
};

async function commandCenter(page, helpers) {
  const sleep = helpers.sleep;
  await sleep(SETTLE);
  const panel = '[aria-labelledby="cc-view-autonomous"]';
  if (!(await page.$(panel))) {
    helpers.log('autonomous panel not found');
    return;
  }
  const scrollPanel = (to) =>
    page.evaluate(
      (p, t) => {
        const el = document.querySelector(p);
        if (el) el.scrollTop = t === 'end' ? el.scrollHeight : 0;
      },
      panel,
      to
    );
  const scrollToId = (id) => page.evaluate((x) => document.getElementById(x)?.scrollIntoView({ block: 'start' }), id);

  // the default view ("Needs attention" when anything is failing, stale or flagged), lower half
  await scrollPanel('end');
  await sleep(500);
  await helpers.shot('attention-end');
  await scrollPanel(0);

  // "All": at scale, groups with nothing wrong start folded
  if (await clickText(page, '[role="tab"]', 'All')) {
    await sleep(700);
    // the first group that starts folded (nothing wrong in it), in the middle of the screen
    await page.evaluate((p) => {
      const folded = document.querySelector(`${p} h3 > button[aria-expanded="false"]`); // a fold header, not a row menu
      folded?.scrollIntoView({ block: 'center' });
    }, panel);
    await sleep(400);
    await helpers.shot('all-folded');
    // the unclaimed jobs, sub-grouped by owner and host
    await scrollToId(`autonomy-group-${encodeURIComponent('__no-agent__')}`);
    await sleep(500);
    await helpers.shot('unclaimed-by-owner-host');
    await scrollPanel(0);
    // host filter and search
    if (await page.$('select[aria-label="Filter by host"]')) {
      await page.select('select[aria-label="Filter by host"]', 'gpu-01');
      await sleep(600);
      await helpers.shot('host-gpu-01');
      await page.select('select[aria-label="Filter by host"]', '');
      await sleep(300);
    }
    const search = 'input[aria-label="Search autonomous jobs"]';
    if (await page.$(search)) {
      await page.type(search, 'backup', { delay: 10 });
      await sleep(600);
      await helpers.shot('search-backup');
      await page.$eval(search, (el) => el.select());
      await page.keyboard.press('Backspace');
      await sleep(300);
    }
  } else helpers.log('no "All" tab (empty / error scenario?)');

  // Register dialog: blank → validation → filled with the reporting help open
  if (await clickText(page, 'button', 'Register an outside job')) {
    await sleep(700);
    await helpers.shot('register');
    await typeInto(page, 'Name', 'Disk guard');
    await typeInto(page, 'Command', 'backup.sh --token=abc123');
    await clickText(page, '[role="dialog"] button[type="submit"]', 'Register job');
    await sleep(500);
    await scrollDialogTo(page, 'Name');
    await sleep(300);
    await helpers.shot('register-validation');
    await typeInto(page, 'Name', 'Kokoro warm-up');
    await typeInto(page, 'Responsibility', 'Keeps the Kokoro voice server warm so the first spoken line of the morning is not a cold start.');
    await typeInto(page, 'Host', 'edge-01');
    await typeInto(page, 'Schedule (cron)', '*/30 6-22 * * *');
    await typeInto(page, 'Command', '/opt/kokoro/bin/warm --voice af_heart');
    await typeInto(page, 'Notes', 'Found in: edge-01 crontab (root) line 5.');
    await clickText(page, '[role="dialog"] button', 'How a script reports its runs');
    await sleep(400);
    await scrollDialogTo(page, 'Schedule (cron)');
    await sleep(300);
    await helpers.shot('register-filled');
    await scrollDialogTo(page, 'How a script reports its runs');
    await sleep(300);
    await helpers.shot('register-reporting');
    await press(page, 'Escape', helpers);
  } else helpers.log('no Register button');

  // an outside job's run history (unfold everything so a healthy job is on screen)
  await clickText(page, 'button', 'Unfold every group');
  await sleep(500);
  if (await clickText(page, 'button', 'More for Build Log refresh')) {
    await sleep(400);
    if (await clickText(page, '[role="menuitem"]', 'Run history')) {
      await sleep(900);
      await helpers.shot('run-history');
      await press(page, 'Escape', helpers);
    }
  } else helpers.log('no Build Log refresh menu (empty / error scenario?)');

  // the org chart with its clock badges, a badge tooltip, and a badge jump
  if (await clickText(page, '[role="tab"]', 'Org Chart')) {
    await sleep(2500);
    await helpers.shot('chart-badges');
    const badge = '[data-org-node="maj-devops"] button[aria-label*="Show them in Autonomous"]';
    if (await page.$(badge)) {
      await page.hover(badge);
      await sleep(700);
      await helpers.shot('chart-badge-tooltip');
      await page.click(badge);
      await sleep(1500);
      await helpers.shot('badge-jump');
    } else helpers.log('no badge on maj-devops (folded or no jobs)');
  }
  // back to the Autonomous view through the chart, so it remounts on its default filter, at the top, for the main capture
  await clickText(page, '[role="tab"]', 'Org Chart');
  await sleep(600);
  await clickText(page, '[role="tab"]', 'Autonomous'); // its count badge rides in the text, so not exact
  await sleep(900);
  await scrollPanel(0);
  await page.mouse.move(2, 2);
  await sleep(500);
}

async function scheduledRuns(page, helpers) {
  const sleep = helpers.sleep;
  await sleep(SETTLE);
  if (await clickText(page, 'button', 'New', { exact: true })) {
    await sleep(700);
    await helpers.shot('new-run');
    await press(page, 'Escape', helpers);
  }
  if (await clickText(page, 'button', 'Morning brief')) {
    await sleep(900);
    await helpers.shot('run-detail');
    await press(page, 'Escape', helpers);
  }
}

async function docs(page, helpers) {
  const sleep = helpers.sleep;
  await sleep(SETTLE);
  for (const [id, name] of [
    ['autonomy', 'autonomy-guide'],
    ['autonomy-register', 'autonomy-endpoint'],
  ]) {
    const found = await page.evaluate((x) => {
      const el = document.getElementById(x);
      el?.scrollIntoView({ block: 'start' });
      return Boolean(el);
    }, id);
    if (found) {
      await sleep(500);
      await helpers.shot(name);
    }
  }
  await page.evaluate(() => document.getElementById('quick-start')?.scrollIntoView({ block: 'start' }));
}

export async function run(page, helpers) {
  await dismissWizard(page, helpers);
  const route = helpers.route || '';
  try {
    if (route.startsWith('/command')) await commandCenter(page, helpers);
    else if (route.startsWith('/scheduled-runs')) await scheduledRuns(page, helpers);
    else if (route.startsWith('/docs')) await docs(page, helpers);
    else await helpers.sleep(SETTLE);
  } catch (err) {
    helpers.log(`step failed (non-fatal): ${err?.message || err}`);
  }
}

export default run;
