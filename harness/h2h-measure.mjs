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
import { readFileSync } from "node:fs";

const products = JSON.parse(readFileSync(new globalThis.URL("../products.json", import.meta.url), "utf8"));

const URL = process.argv[2];
const LABEL = process.argv[3] || URL;
// Override with CHROME=/path/to/chrome; otherwise use puppeteer's bundled browser.
const CHROME = process.env.CHROME || undefined;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: true,
  ...(CHROME ? { executablePath: CHROME } : {}),
  args: ["--no-sandbox", "--ignore-certificate-errors", "--disable-dev-shm-usage"],
});

try {
  // SSR card count from the raw delivered HTML (separate fetch — no contention
  // with puppeteer's body reads). data-name marks each card across frameworks.
  const ssrHtml = await fetch(URL).then((r) => r.text()).catch(() => "");
  const ssrCards = [...ssrHtml.matchAll(/<(?:article|div)\b[^>]*>/gi)].filter(([tag]) =>
    /\bdata-name=/.test(tag) || /\bclass="[^"]*\bcard\b/.test(tag)).length;
  const ssrProducts = products.filter(({ name }) => ssrHtml.includes(`>${name}<`)).length;

  const page = await browser.newPage();
  let extJsGz = 0, extJsRaw = 0, jsReqs = 0, htmlGz = 0;
  const seen = new Set();
  const jsUrls = [];
  const pending = [];
  const resourceErrors = [];
  let collecting = true;
  page.on("response", (r) => {
    if (!collecting) return;
    pending.push((async () => {
    try {
      const ct = (r.headers()["content-type"] || "").toLowerCase();
      const u = r.url();
      if (seen.has(u)) return;           // dedup — count each resource once
      const isJs = ct.includes("javascript") || /\.(m?js)(\?|$)/.test(u);
      const isHtml = ct.includes("text/html");
      if (!isJs && !isHtml) return;
      if (isJs && !r.ok()) resourceErrors.push(`${r.status()} ${u}`);
      const buf = await r.buffer().catch(() => null);
      if (!buf) return;
      seen.add(u);
      if (isJs) { extJsRaw += buf.length; extJsGz += gzipSync(buf).length; jsReqs++; jsUrls.push(u); }
      else if (isHtml) { htmlGz += gzipSync(buf).length; }
    } catch (error) { resourceErrors.push(String(error)); }
    })());
  });

  // single navigation; networkidle0 so eager island bundles / hydration chunks settle
  const resp = await page.goto(URL, { waitUntil: "networkidle0", timeout: 60000 });
  const status = resp ? resp.status() : 0;
  const ttfbMs = await page.evaluate(() =>
    Math.round(performance.timing.responseStart - performance.timing.requestStart)).catch(() => -1);
  await sleep(300);
  await Promise.all(pending);

  // inline <script> bodies, gzipped uniformly
  const inlineJsGz = await page.evaluate(() => {
    let s = "";
    for (const el of document.querySelectorAll("script:not([src])")) s += el.textContent || "";
    return s;
  }).then((s) => (s ? gzipSync(Buffer.from(s)).length : 0));
  const initialClientJsGzB = extJsGz + inlineJsGz;

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
        if (Number.isFinite(now) && Number.isFinite(start) && now === start + 1) { counterOk = true; ttiMs = Date.now() - tLoad; break; }
      }
    }
  } catch {}

  // --- interaction: theme toggle ---
  let themeOk = false;
  try {
    const before = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    const tbtn = await page.evaluateHandle(() => {
      const els = [...document.querySelectorAll("button, [role=button]")];
      return els.find((e) => /dark|light|theme/i.test(e.textContent || "")) || null;
    });
    if (tbtn && (await tbtn.evaluate((e) => !!e))) {
      await tbtn.click().catch(() => {});
      await sleep(150);
      const after = await page.evaluate(() => ({
        dark: document.documentElement.classList.contains("dark"),
        stored: localStorage.getItem("theme"),
      }));
      themeOk = before !== after.dark && after.stored === (after.dark ? "dark" : "light");
    }
  } catch {}

  // --- interaction: search filter ---
  let searchOk = false;
  let searchCounts = null;
  try {
    const visBefore = await page.evaluate(() =>
      [...document.querySelectorAll('[data-name], .card, article')].filter((e) => e.offsetParent !== null).length);
    const inp = await page.$('input[type=search]') || await page.$('input');
    if (inp) {
      await inp.click();
      // Use the same typing rate for every entry and wait for the asserted DOM
      // state instead of assuming a fixed 250 ms sleep is always sufficient.
      await inp.type("NiMbUs", { delay: 50 });
      const expected = products.filter((p) => p.name.toLowerCase().includes("nimbus")).length;
      await page.waitForFunction((expected) =>
        [...document.querySelectorAll('[data-name], .card, article')]
          .filter((e) => e.offsetParent !== null).length === expected,
        { timeout: 5000 }, expected).catch(() => {});
      const visAfter = await page.evaluate(() =>
        [...document.querySelectorAll('[data-name], .card, article')].filter((e) => e.offsetParent !== null).length);
      const filteredQuery = await inp.evaluate((e) => e.value);
      await inp.focus();
      await page.keyboard.down("Control");
      await page.keyboard.press("a");
      await page.keyboard.up("Control");
      await inp.press("Backspace");
      await page.waitForFunction(() =>
        [...document.querySelectorAll('[data-name], .card, article')]
          .filter((e) => e.offsetParent !== null).length === 24,
        { timeout: 5000 }).catch(() => {});
      const visReset = await page.evaluate(() =>
        [...document.querySelectorAll('[data-name], .card, article')].filter((e) => e.offsetParent !== null).length);
      searchCounts = { before: visBefore, filtered: visAfter, expected, reset: visReset, filteredQuery };
      searchOk = visBefore === 24 && visAfter === expected && visReset === 24 && filteredQuery.toLowerCase() === "nimbus";
    }
  } catch {}

  // Finish counting lazily fetched interaction code before reloading for the
  // persistence check. Reloads must not inflate the first-visit JS measurement.
  await page.waitForNetworkIdle({ idleTime: 500, timeout: 10000 });
  await Promise.all(pending);
  collecting = false;
  let themePersistOk = false;
  try {
    const stored = await page.evaluate(() => localStorage.getItem("theme"));
    await page.reload({ waitUntil: "networkidle0" });
    await sleep(300);
    const after = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    const toggle = await page.evaluateHandle(() => [...document.querySelectorAll("button")].find(
      (e) => /dark|light|theme/i.test(e.textContent || "")));
    await toggle.click();
    await sleep(150);
    const toggled = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    themePersistOk = stored === (after ? "dark" : "light") && after !== toggled;
  } catch {}

  const out = {
    label: LABEL, url: URL, status,
    ssrCards, ssrProducts,
    htmlGzB: htmlGz,
    extJsGzB: extJsGz, extJsRawB: extJsRaw, jsReqs,
    inlineJsGzB: inlineJsGz,
    clientJsGzB: extJsGz + inlineJsGz,
    initialClientJsGzB,
    ttfbMs,
    clickLatencyMs: ttiMs, counterOk, themeOk, themePersistOk, searchOk,
    resourceErrors, searchCounts, browserVersion: await browser.version(),
    jsUrls: jsUrls.map((u) => u.replace(/^https?:\/\/[^/]+/, "")),
  };
  console.log(JSON.stringify(out));
  if (resourceErrors.length) process.exitCode = 1;
} finally {
  await browser.close();
}
