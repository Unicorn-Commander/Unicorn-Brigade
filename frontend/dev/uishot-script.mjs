/**
 * uishot --script for the mock-backed verification runs.
 *
 *   node ~/.claude/tools/uishot/uishot.mjs --url http://localhost:5190 --routes /dashboard,/command,... \
 *        --script frontend/dev/uishot-script.mjs --wait-ms 2500 --no-fail
 *
 * Runs after the route has loaded and `--wait-ms` has elapsed, right before the
 * screenshot. It is route-aware:
 *   - every route: if the first-run Getting Started wizard is up, mark it
 *     completed (localStorage) and reload so the page underneath is captured;
 *   - /chat: type a question and press Enter so the streamed markdown reply and
 *     its tool-call card are in the shot (proves the chat SSE contract);
 *   - /command: take an extra "activity" shot of the Activity view, then return
 *     to the org chart for the main capture.
 * Env: UISHOT_SETTLE_MS (ms to wait after a reload / before capture, default 2500).
 */
const SETTLE = Number(process.env.UISHOT_SETTLE_MS || 2500);

async function dismissWizard(page, helpers) {
  // The tour is a ui Modal titled "Welcome to Unicorn Brigade" (older builds: aria-label "Getting started…").
  const hasWizard = await page.evaluate(() =>
    [...document.querySelectorAll('[role="dialog"]')].some(
      (d) => /^Getting started/.test(d.getAttribute('aria-label') || '') || /Welcome to Unicorn Brigade/.test(d.textContent || '')
    )
  );
  await page.evaluate(() => { try { localStorage.setItem('wizard-completed', 'true'); } catch {} });
  if (hasWizard) {
    helpers.log('wizard present — marking completed and reloading');
    await page.reload({ waitUntil: 'networkidle2' });
    await helpers.sleep(SETTLE);
  }
}

async function clickTab(page, label) {
  const tabs = await page.$$('[role="tab"]');
  for (const t of tabs) {
    const text = (await page.evaluate((el) => el.textContent, t)) || '';
    if (text.trim().toLowerCase().includes(label.toLowerCase())) { await t.click(); return true; }
  }
  return false;
}

export async function run(page, helpers) {
  await dismissWizard(page, helpers);
  const route = helpers.route || '';

  if (route === '/chat') {
    const ta = await page.$('textarea');
    if (ta) {
      await ta.click();
      await page.type('textarea', 'What is our runway if revenue stays flat?');
      await page.keyboard.press('Enter');
      helpers.log('chat message sent — waiting for the stream');
      await helpers.sleep(5500);
    } else {
      helpers.log('no chat textarea found (empty roster?)');
    }
  }

  if (route === '/command') {
    if (await clickTab(page, 'Activity')) {
      await helpers.sleep(1500);
      await helpers.shot('activity');
      await clickTab(page, 'Org Chart');
      await helpers.sleep(1500);
    }
  }
}

export default run;
