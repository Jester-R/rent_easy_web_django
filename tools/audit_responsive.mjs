// Mobile/desktop overflow + console-error audit for the RentEasy web app.
// Usage: node tools/audit_responsive.mjs [--width 360] [--url http://127.0.0.1:8010]
import puppeteer from "puppeteer-core";

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : fallback;
};

const BASE = arg("url", "http://127.0.0.1:8010");
const WIDTHS = arg("width", "360,414,768,1280")
  .split(",")
  .map(Number);
const CHROME = arg("chrome", "/usr/bin/google-chrome");

const ACCOUNTS = {
  admin: { email: "admin@fake.com", password: "admin" },
  owner: { email: "owner@fake.com", password: "owner" },
  renter: { email: "renter@fake.com", password: "renter" },
};

async function login(page, creds) {
  await page.goto(`${BASE}/auth/login/`, { waitUntil: "domcontentloaded" });
  await page.type("input[name=identifier]", creds.email);
  await page.type("input[name=password]", creds.password);
  await Promise.all([
    page.waitForNavigation({ waitUntil: "domcontentloaded" }),
    page.evaluate(() => document.querySelector("input[name=password]").form.requestSubmit()),
  ]);
  const authed = await page.$("a[href*='logout'], form[action*='logout']");
  if (!authed) throw new Error(`login failed for ${creds.email} (landed on ${page.url()})`);
}

async function collectUrls(page) {
  const urls = new Set(["/core/landing/", "/auth/login/", "/auth/register/"]);
  const gather = async (root) => {
    for (const a of await page.$$eval(`${root} a[href]`, (els) => els.map((e) => e.getAttribute("href")))) {
      if (a && a.startsWith("/") && !a.startsWith("//") && !a.startsWith("/static") && !a.startsWith("/dj-admin")) {
        urls.add(a.split("#")[0]);
      }
    }
  };
  for (const path of ["/rent/", "/owner/", "/console/", "/rent/properties/", "/rent/bookings/", "/rent/payments/",
                      "/owner/properties/", "/owner/bookings/", "/owner/payments/",
                      "/console/users/", "/console/properties/", "/console/bookings/", "/console/payments/",
                      "/notifications/", "/auth/preferences/"]) {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
    await gather("main");
    await gather("nav");
  }
  return [...urls];
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const page = await browser.newPage();
await page.setCacheEnabled(false);
const problems = [];
page.on("console", (msg) => {
  if (msg.type() === "error") problems.push(`console-error: ${msg.text().slice(0, 160)}`);
});
page.on("pageerror", (err) => problems.push(`page-error: ${String(err).slice(0, 160)}`));

await login(page, ACCOUNTS.admin);
const urls = await collectUrls(page);
console.log(`auditing ${urls.length} urls across widths ${WIDTHS.join(", ")}`);

for (const width of WIDTHS) {
  await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
  for (const url of urls) {
    await page.goto(`${BASE}${url}`, { waitUntil: "domcontentloaded" });
    const result = await page.evaluate(() => {
      const de = document.documentElement;
      const overflow = de.scrollWidth - de.clientWidth;
      const offenders = [];
      if (overflow > 1) {
        const bad = [];
        for (const el of document.querySelectorAll("body *")) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          if (r.right > de.clientWidth + 1 || r.left < -1) {
            if (getComputedStyle(el).position === "fixed") continue;
            bad.push(el);
          }
        }
        // keep only leaves: elements with no offending descendant are the real cause
        for (const el of bad) {
          if (bad.some((other) => other !== el && el.contains(other))) continue;
          const r = el.getBoundingClientRect();
          offenders.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className || "").toString().slice(0, 80),
            text: (el.textContent || "").trim().slice(0, 30),
            left: Math.round(r.left),
            right: Math.round(r.right),
          });
        }
      }
      return { overflow, offenders };
    });
    if (result.overflow > 1) {
      problems.push(
        `overflow ${width}px ${url} (+${result.overflow}px) :: ` +
          result.offenders
            .map((o) => `${o.tag}.${o.cls}[${o.left}..${o.right}]"${o.text}"`)
            .join(" | "),
      );
    }
  }
}

await browser.close();
console.log(`\nPROBLEMS: ${problems.length}`);
for (const p of [...new Set(problems)]) console.log("  - " + p);
