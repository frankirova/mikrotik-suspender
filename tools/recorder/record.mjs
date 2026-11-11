import { chromium } from 'playwright';
import { mkdirSync, rmSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const rawDir = resolve(here, '../demo/raw');
const APP = process.env.APP_URL ?? 'http://127.0.0.1:8002/';
const ALIAS = process.env.ROUTER_ALIAS ?? 'lab';
const TOKEN = process.env.API_TOKEN ?? 'demo-token-123';
const DATE = process.env.SUSPENSION_DATE ?? '2025-11-11';

const CURSOR_SCRIPT = () => {
  const mount = () => {
    const style = document.createElement('style');
    style.textContent = `
      #__ptr { position: fixed; left: 0; top: 0; width: 20px; height: 20px;
        border-radius: 50%; background: #10131c; border: 2px solid #ffffff;
        box-shadow: 0 2px 10px rgba(0,0,0,.45);
        transform: translate(-50%,-50%); pointer-events: none;
        z-index: 2147483647; display: none; }
      #__ptr.on { display: block; }`;
    document.head.appendChild(style);
    const dot = document.createElement('div');
    dot.id = '__ptr';
    document.body.appendChild(dot);
    addEventListener('mousemove', (event) => {
      dot.classList.add('on');
      dot.style.left = `${event.clientX}px`;
      dot.style.top = `${event.clientY}px`;
    });
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', mount);
  else mount();
};


rmSync(rawDir, { recursive: true, force: true });
mkdirSync(rawDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: rawDir, size: { width: 1440, height: 900 } },
  locale: 'es-AR',
  timezoneId: 'America/Argentina/Buenos_Aires',
});
await context.addInitScript(CURSOR_SCRIPT);
const page = await context.newPage();
const hold = (ms) => page.waitForTimeout(ms);
const video = page.video();

async function moveTo(selector, steps = 18) {
  const box = await page.locator(selector).boundingBox();
  if (!box) throw new Error(`no box for ${selector}`);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps });
  await hold(350);
}

// ── Scene 1: title card ────────────────────────────────────────────
await page.goto(`file://${resolve(here, '../demo/title.html')}`);
await hold(4500);

// ── Scene 2: plan (read-only) ──────────────────────────────────────
await page.goto(APP, { waitUntil: 'networkidle' });
await hold(2800);

await moveTo('#router');
await page.locator('#router').click();
await page.locator('#router').pressSequentially(ALIAS, { delay: 130 });
await hold(900);

await moveTo('#date');
await page.locator('#date').click();
await page.locator('#date').fill(DATE);
await hold(1100);

await moveTo('#token');
await page.locator('#token').click();
await page.locator('#token').pressSequentially(TOKEN, { delay: 70 });
await hold(1400);

await moveTo('#btn-preview');
await page.locator('#btn-preview').click();
await page.locator('#result-body tr').first().waitFor({ state: 'visible', timeout: 30_000 });
await page.mouse.move(720, 610, { steps: 10 });
await hold(7000);

await context.close();
await browser.close();
console.log(video ? await video.path() : rawDir);
