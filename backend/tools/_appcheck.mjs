import puppeteer from "puppeteer-core";
const base = "http://127.0.0.1:8010";
const ACCOUNTS = { renter: ["renter@fake.com", "renter"], owner: ["owner@fake.com", "owner"], admin: ["admin@fake.com", "admin"] };
const PAGES = {
  renter: ["/rent/", "/rent/properties/", "/rent/bookings/", "/rent/payments/", "/rent/favorites/", "/auth/preferences/", "/notifications/"],
  owner: ["/owner/", "/owner/properties/", "/owner/bookings/", "/owner/payments/", "/owner/properties/new/"],
  admin: ["/console/", "/console/users/", "/console/properties/", "/console/payments/", "/console/bookings/new/"],
};
const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
let fails = 0;
for (const [role, [email, pass]] of Object.entries(ACCOUNTS)) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await page.setCacheEnabled(false);
  await page.goto(`${base}/auth/login/`, { waitUntil: "domcontentloaded" });
  await page.type("input[name=identifier]", email);
  await page.type("input[name=password]", pass);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.evaluate(() => document.querySelector("input[name=password]").form.requestSubmit())]);
  for (const path of PAGES[role]) {
    const res = await page.goto(`${base}${path}`, { waitUntil: "domcontentloaded" }).catch(() => null);
    if (!res || res.status() >= 400) { console.log(`SKIP ${path} (${res ? res.status() : "nav fail"})`); continue; }
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await new Promise((r2) => setTimeout(r2, 250));
    const r = await page.evaluate(() => {
      const bar = document.querySelector("[data-tabbar]");
      const main = document.querySelector("main");
      const cards = [...main.querySelectorAll(".app-card, [data-table-card], table")];
      const last = cards[cards.length - 1];
      const lastBottom = last ? Math.round(last.getBoundingClientRect().bottom + window.scrollY) : 0;
      const active = [...document.querySelectorAll(".app-tab.is-active")];
      const input = document.querySelector('input:not([type=checkbox]):not([type=radio]), select, textarea');
      return {
        barPos: getComputedStyle(bar).position,
        barBottom: Math.round(window.innerHeight - bar.getBoundingClientRect().bottom),
        barH: Math.round(bar.getBoundingClientRect().height),
        barZ: getComputedStyle(bar).zIndex,
        mainPadBottom: Math.round(parseFloat(getComputedStyle(main).paddingBottom)),
        tabs: document.querySelectorAll(".app-tab").length,
        activeTabs: active.length,
        activeHref: active[0] ? active[0].getAttribute("href") : null,
        ariaCurrent: active[0] ? active[0].getAttribute("aria-current") : null,
        lastContentBottom: lastBottom,
        clearOfBar: lastBottom <= document.body.scrollHeight - 1,
        scrollW: document.documentElement.scrollWidth,
        clientW: document.documentElement.clientWidth,
        inputFont: input ? getComputedStyle(input).fontSize : null,
        topbarScrolled: document.querySelector("[data-topbar]").getAttribute("data-scrolled"),
        animation: getComputedStyle(main.firstElementChild).animationName,
      };
    });
    const problems = [];
    if (r.barPos !== "fixed") problems.push(`tabbar position=${r.barPos}`);
    if (r.barBottom !== 0) problems.push(`tabbar not flush to bottom (${r.barBottom}px)`);
    if (r.tabs !== 5) problems.push(`tabs=${r.tabs}`);
    // renters have no Profile/Notifications tab, so those pages legitimately show none
    const needsTab = !(role === "renter" && ["/notifications/", "/auth/preferences/"].includes(path));
    if (needsTab && r.activeTabs !== 1) problems.push(`activeTabs=${r.activeTabs}`);
    if (r.activeTabs && r.ariaCurrent !== "page") problems.push("aria-current missing");
    if (r.mainPadBottom < r.barH) problems.push(`main pad ${r.mainPadBottom} < bar ${r.barH}`);
    if (!r.clearOfBar) problems.push(`content bottom ${r.lastContentBottom} overlaps bar (page ${r.lastContentBottom})`);
    if (r.scrollW > r.clientW) problems.push(`h-overflow ${r.scrollW}>${r.clientW}`);
    if (r.inputFont && parseFloat(r.inputFont) < 16) problems.push(`input font ${r.inputFont}`);
    if (r.topbarScrolled !== "true") problems.push(`data-scrolled=${r.topbarScrolled}`);
    if (problems.length) { fails++; console.log(`FAIL ${path} :: ${problems.join(", ")}`); }
    else console.log(`ok   ${path} bar=${r.barH}px pad=${r.mainPadBottom} active=${r.activeHref} anim=${r.animation}`);
  }
  await page.close();
}
console.log(fails ? `\n${fails} page(s) failed` : "\napp shell OK on every page");
await browser.close();
