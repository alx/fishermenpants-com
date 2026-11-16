// Phase A — fetch pages with Playwright Firefox (gets through Shopify's bot layer).
// Usage: node tools/crawl_browser.mjs
import { firefox } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CR = path.join(ROOT, '_crawl');
const HTML_DIR = path.join(CR, 'html');
const BASE = 'https://www.fishermenpants.com';
const PACE_MS = 12000;      // quiet pace between page loads
const RETRY_WAIT_MS = 70000; // wait on 429 (retry-after 60 + margin)
const MAX_RETRY = 4;

fs.mkdirSync(HTML_DIR, { recursive: true });
const jobs = JSON.parse(fs.readFileSync(path.join(CR, 'jobs.json'), 'utf8'));
const log = (m) => console.log(new Date().toISOString().slice(11, 19), m);

const pending = jobs.filter(([p, name]) => {
  const f = path.join(HTML_DIR, name + '.html');
  return !(fs.existsSync(f) && fs.statSync(f).size > 2000);
});
log(`phase A: ${pending.length} urls to fetch (of ${jobs.length})`);

const browser = await firefox.launch({ headless: true });
const ctx = await browser.newContext({
  userAgent: 'Mozilla/5.0 (X11; Linux x86_64; rv:159.0) Gecko/20100101 Firefox/159.0',
  viewport: { width: 1440, height: 900 },
  locale: 'en-US',
});
const page = await ctx.newPage();

let done = jobs.length - pending.length;
let still = pending;
for (let pass = 0; pass < 4 && still.length; pass++) {
  log(`PASS ${pass + 1}: ${still.length} urls`);
  const left = [];
  for (let i = 0; i < still.length; i++) {
    const [p, name] = still[i];
    const url = p === '/' ? BASE + '/' : BASE + p;
    let got = null;
    for (let attempt = 0; attempt < MAX_RETRY; attempt++) {
      let status = 0, body = '';
      try {
        const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 });
        status = resp ? resp.status() : 0;
        body = await page.content();
      } catch (e) {
        log(`  ${p}: nav error ${String(e).slice(0, 80)}`);
        status = 0;
      }
      if (status === 200 && body.length > 2000 && !body.includes('local_rate_limited')) {
        got = body;
        break;
      }
      log(`  ${p}: status=${status} size=${body.length} -> wait ${RETRY_WAIT_MS / 1000}s (try ${attempt + 1}/${MAX_RETRY})`);
      await new Promise(r => setTimeout(r, RETRY_WAIT_MS));
    }
    if (got) {
      fs.writeFileSync(path.join(HTML_DIR, name + '.html'), got);
      done++;
      log(`saved ${name}.html (${got.length}b)  progress ${done}/${jobs.length}`);
    } else {
      left.push([p, name]);
    }
    await new Promise(r => setTimeout(r, PACE_MS));
  }
  still = left;
}
await browser.close();
log(still.length ? `PHASE A finished with ${still.length} FAILED: ${still.map(x => x[0]).join(', ')}` : 'PHASE A complete');
process.exit(still.length ? 2 : 0);
