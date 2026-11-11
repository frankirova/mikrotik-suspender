// Records the demo video for the README.
//
// Drives the real UI (http://127.0.0.1:8002) against the RouterOS simulator
// (http://127.0.0.1:8729 console) and keeps the raw webm for ffmpeg to encode.
//
//   APP_URL=http://127.0.0.1:8002/ ROUTER_IP=172.19.0.99 node record.mjs
//
// Expects: demo app up, simulator up on :8728/:8729 with an empty
// address-list, and the demo CSV already loaded inside the app container.
// Playwright does not draw a pointer in its recordings, so this script paints
// one and animates it before every click.

import { chromium } from 'playwright';
import { mkdirSync, rmSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const rawDir = resolve(here, '../demo/raw');
const APP = process.env.APP_URL ?? 'http://127.0.0.1:8002/';
const CONSOLE = process.env.CONSOLE_URL ?? 'http://127.0.0.1:8729/';
const ROUTER_IP = process.env.ROUTER_IP ?? '172.19.0.99';
const DATE = process.env.SUSPENSION_DATE ?? '2025-11-10';
const TITLE = resolve(here, '../demo/title.html');

rmSync(rawDir, { recursive: true, force: true });
mkdirSync(rawDir, { recursive: true });

const CURSOR_SCRIPT = () => {
  const mount = () => {
    const style = document.createElement('style');
    style.textContent = `
      #__ptr { position: fixed; left: 0; top: 0; width: 20px; height: 20px;
        border-radius: 50%; background: #10131c; border: 2px solid #ffffff;
        box-shadow: 0 2px 10px rgba(0,0,0,.45);
        transform: translate(-50%,-50%); pointer-events: none;
        z-index: 2147483647; display: none; }
      #__ptr.on { display: block; }
      #__ptr.click { animation: __pulse .5s ease-out; }
      @keyframes __pulse {
        0%   { box-shadow: 0 0 0 0 rgba(255,255,255,.85), 0 2px 10px rgba(0,0,0,.45); }
        100% { box-shadow: 0 0 0 26px rgba(255,255,255,0), 0 2px 10px rgba(0,0,0,.45); }
      }`;
    document.head.appendChild(style);
    const dot = document.createElement('div');
    dot.id = '__ptr';
    document.body.appendChild(dot);
    addEventListener('mousemove', (event) => {
      dot.classList.add('on');
      dot.style.left = `${event.clientX}px`;
      dot.style.top = `${event.clientY}px`;
    });
    addEventListener('mousedown', () => {
      dot.classList.remove('click');
      void dot.offsetWidth;
      dot.classList.add('click');
    });
  };
  if (document.readyState === 'loading') {
    addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
};

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
await page.goto(`file://${TITLE}`);
await hold(4500);

// ── Scene 2: preview (simulation, nothing suspended) ───────────────
await page.goto(APP, { waitUntil: 'networkidle' });
await hold(3000);

await moveTo('#ip');
await page.locator('#ip').click();
await page.locator('#ip').pressSequentially(ROUTER_IP, { delay: 105 });
await hold(1000);

await moveTo('#date');
await page.locator('#date').click();
await page.locator('#date').fill(DATE);
await hold(1600);

await moveTo('#btn-preview');
await page.locator('#btn-preview').click();
await page.locator('#result-body tr').first().waitFor({ state: 'visible', timeout: 30_000 });
await page.mouse.move(720, 610, { steps: 10 });
await hold(6000);

await context.close();
await browser.close();
console.log(video ? await video.path() : rawDir);
process.exit(0);

// ── Scene 4: execute (apply the suspension) ────────────────────────
await page.goto(APP);
await hold(1600);
await moveTo('#ip');
await page.locator('#ip').fill('');
await page.locator('#ip').pressSequentially(ROUTER_IP, { delay: 85 });
await hold(900);

await moveTo('#btn-exec');
await page.locator('#btn-exec').click();
await page.waitForFunction(
  () => {
    const result = document.querySelector('#exec-result');
    const alert = document.querySelector('#alert-msg');
    return Boolean(
      (result && result.textContent.trim()) ||
        (alert && /ejecutad|éxito/i.test(alert.textContent)),
    );
  },
  null,
  { timeout: 30_000 },
);
await page.mouse.move(700, 690, { steps: 10 });
await hold(4200);

// ── Scene 5: the router after execute — every entry enabled ────────
await page.goto(CONSOLE, { waitUntil: 'load' });
await hold(10_000);

await context.close();
await browser.close();

console.log(video ? await video.path() : rawDir);
