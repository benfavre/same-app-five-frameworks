// Head-to-head client-side measurer. Uniform across frameworks:
//   - client JS = every JS resource the page loads, gzipped BY US at a fixed
//     level (so we compare bytes-over-an-equal-encoder, not each server's choice),
//     plus inline <script> bodies gzipped the same way.
//   - TTI proxy = ms from the load event until the "Count: N" button actually
//     increments when clicked (resumable ~ instant/short; hydration = after hydrate).
//   - interaction checks: counter increments, theme toggles <html> class, search
//     hides cards. Plus the SSR card count in the delivered HTML.
// Usage: node h2h-measure.mjs <url> <label>
import puppeteer from "puppeteer";
import { gzipSync } from "node:zlib";

const URL = process.argv[2];
const LABEL = process.argv[3] || URL;
// Override with CHROME=/path/to/chrome; otherwise use puppeteer's bundled browser.
const CHROME = process.env.CHROME || undefined;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: "new",
  ...(CHROME ? { executablePath: CHROME } : {}),
  args: ["--no-sandbox", "--ignore-certificate-errors", "--disable-dev-shm-usage"],
});

try {
  // SSR card count from the raw delivered HTML (separate fetch — no contention
  // with puppeteer's body reads). data-name marks each card across frameworks.
  const ssrHtml = await fetch(URL).then((r) => r.text()).catch(() => "");
  const ssrCards = (ssrHtml.match(/data-name=/gi) || []).length ||
                   (ssrHtml.match(/Nimbus Speaker 1|Vertex Watch 2|Aero Lamp 3/g) || []).length;

  const page = await browser.newPage();
  let extJsGz = 0, extJsRaw = 0, jsReqs = 0, htmlGz = 0;
  const seen = new Set();
  const jsUrls = [];
  page.on("response", async (r) => {
    try {
      const ct = (r.headers()["content-type"] || "").toLowerCase();
      const u = r.url();
      if (seen.has(u)) return;           // dedup — count each resource once
      const isJs = ct.includes("javascript") || /\.(m?js)(\?|$)/.test(u);
      const isHtml = ct.includes("text/html");
      if (!isJs && !isHtml) return;
      const buf = await r.buffer().catch(() => null);
      if (!buf) return;
      seen.add(u);
      if (isJs) { extJsRaw += buf.length; extJsGz += gzipSync(buf).length; jsReqs++; jsUrls.push(u); }
      else if (isHtml) { htmlGz += gzipSync(buf).length; }
    } catch {}
  });

  // single navigation; networkidle0 so eager island bundles / hydration chunks settle
  const resp = await page.goto(URL, { waitUntil: "networkidle0", timeout: 60000 });
  const status = resp ? resp.status() : 0;
  const ttfbMs = await page.evaluate(() =>
    Math.round(performance.timing.responseStart - performance.timing.requestStart)).catch(() => -1);
  await sleep(300);

  // inline <script> bodies, gzipped uniformly
  const inlineJsGz = await page.evaluate(() => {
    let s = "";
    for (const el of document.querySelectorAll("script:not([src])")) s += el.textContent || "";
    return s;
  }).then((s) => (s ? gzipSync(Buffer.from(s)).length : 0));

  // --- interaction: counter ---
  const tLoad = Date.now();
  let counterOk = false, ttiMs = -1;
  try {
    const btn = await page.evaluateHandle(() => {
      const els = [...document.querySelectorAll("button, [role=button], a")];
      return els.find((e) => /count:\s*\d+/i.test(e.textContent || "")) || null;
    });
    if (btn && (await btn.evaluate((e) => !!e))) {
      const readN = () => btn.evaluate((e) => {
        const m = (e.textContent || "").match(/count:\s*(\d+)/i); return m ? +m[1] : NaN;
      });
      const start = await readN();
      const deadline = Date.now() + 8000;
      while (Date.now() < deadline) {
        await btn.click({ delay: 1 }).catch(() => {});
        await sleep(40);
        const now = await readN();
        if (Number.isFinite(now) && Number.isFinite(start) && now > start) { counterOk = true; ttiMs = Date.now() - tLoad; break; }
      }
    }
  } catch {}

  // --- interaction: theme toggle ---
  let themeOk = false;
  try {
    const before = await page.evaluate(() => document.documentElement.className);
    const tbtn = await page.evaluateHandle(() => {
      const els = [...document.querySelectorAll("button, [role=button]")];
      return els.find((e) => /dark|light|theme/i.test(e.textContent || "")) || null;
    });
    if (tbtn && (await tbtn.evaluate((e) => !!e))) {
      await tbtn.click().catch(() => {});
      await sleep(150);
      const after = await page.evaluate(() => document.documentElement.className);
      themeOk = before !== after;
    }
  } catch {}

  // --- interaction: search filter ---
  let searchOk = false;
  try {
    const visBefore = await page.evaluate(() =>
      [...document.querySelectorAll('[data-name], .card, article')].filter((e) => e.offsetParent !== null).length);
    const inp = await page.$('input[type=search]') || await page.$('input');
    if (inp) {
      await inp.click();
      await inp.type("nimbus", { delay: 8 });
      await sleep(250);
      const visAfter = await page.evaluate(() =>
        [...document.querySelectorAll('[data-name], .card, article')].filter((e) => e.offsetParent !== null).length);
      searchOk = visAfter < visBefore && visAfter > 0;
    }
  } catch {}

  const out = {
    label: LABEL, url: URL, status,
    ssrCards,
    htmlGzB: htmlGz,
    extJsGzB: extJsGz, extJsRawB: extJsRaw, jsReqs,
    inlineJsGzB: inlineJsGz,
    clientJsGzB: extJsGz + inlineJsGz,
    ttfbMs,
    ttiMs, counterOk, themeOk, searchOk,
    jsUrls: jsUrls.map((u) => u.replace(/^https?:\/\/[^/]+/, "")),
  };
  console.log(JSON.stringify(out));
} finally {
  await browser.close();
}
