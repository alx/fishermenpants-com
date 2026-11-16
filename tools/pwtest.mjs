import { firefox, chromium } from 'playwright';

const urls = process.argv.slice(2);
const browser = await firefox.launch({ headless: true });
const page = await (await browser.newContext()).newPage();
for (const url of urls) {
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  const body = await page.content();
  const status = resp ? resp.status() : 0;
  console.error(`${url} -> ${status} (${body.length}b)`);
  const fs = await import('fs');
  const out = '/tmp/pw_' + url.replace(/[^a-z0-9]/gi, '_') + '.html';
  fs.writeFileSync(out, body);
  await page.waitForTimeout(1500);
}
await browser.close();
