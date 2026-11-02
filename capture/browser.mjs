// The gallery in a real browser, from the published site, for the "whole apps in a browser tab" block.
//   PLAYWRIGHT_MODULE=<path to playwright> node capture/browser.mjs [base url]
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const out = fileURLToPath(new URL('../src/img/browser-gallery.png', import.meta.url));
const base = process.argv[2] || 'https://jflib.org/';
const b = await chromium.launch({ channel: 'chrome', headless: true });
const ctx = await b.newContext({ viewport: { width: 1000, height: 560 }, locale: 'en-US', colorScheme: 'light' });
const p = await ctx.newPage();
await p.goto(base + 'gallery/index.html?theme=light', { waitUntil: 'networkidle' });
await p.waitForTimeout(5000);
await p.screenshot({ path: out });
await b.close();
console.log('browser-gallery: ' + out);
