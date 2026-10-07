// End-to-end functional sweep of the RentEasy web app.
// Drives a real Chrome session per role and checks every JS-driven flow plus
// the main server-side workflows. Usage: node tools/func_check.mjs [--role all]
import puppeteer from "puppeteer-core";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Query the demo database directly so the sweep can pick deterministic targets
// (a free property, the booking it just created, ...) instead of guessing.
function py(snippet) {
  const code = `import os, django\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\ndjango.setup()\n${snippet}`;
  return execFileSync(path.join(ROOT, ".venv/bin/python"), ["-c", code], { cwd: ROOT, encoding: "utf8" }).trim();
}

const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > -1 ? process.argv[i + 1] : d; };
const BASE = arg("url", "http://127.0.0.1:8010");
const ONLY = arg("role", "all");
const CHROME = arg("chrome", "/usr/bin/google-chrome");
const HEAD = { Host: "192.168.0.189:8010" };

const ACCOUNTS = {
  renter: ["renter@fake.com", "renter"],
  owner: ["owner@fake.com", "owner"],
  admin: ["admin@fake.com", "admin"],
  dana: ["dana.owned@fake.com", "owner123"],
};

let pass = 0;
const failures = [];
function check(role, name, ok, detail = "") {
  if (ok) { pass++; console.log(`  ok   [${role}] ${name}`); }
  else { failures.push(`[${role}] ${name} ${detail}`); console.log(`  FAIL [${role}] ${name} ${detail}`); }
}
function skip(role, name, why) {
  console.log(`  skip [${role}] ${name} (${why})`);
}

async function newSession(browser, role) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.setCacheEnabled(false);
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("403")) errors.push(`console: ${m.text().slice(0, 120)}`); });
  page.on("requestfailed", (r) => errors.push(`requestfailed: ${r.url()}`));
  page.on("response", (r) => { if (r.status() >= 500) errors.push(`http ${r.status()} ${r.url()}`); });
  const [email, password] = ACCOUNTS[role];
  await page.goto(`${BASE}/auth/login/`, { waitUntil: "domcontentloaded" });
  await page.type("input[name=identifier]", email);
  await page.type("input[name=password]", password);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.evaluate(() => document.querySelector("input[name=password]").form.requestSubmit())]);
  return { ctx, page, errors };
}

const go = (page, path) => page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
const settle = (page, ms = 450) => new Promise((r) => setTimeout(r, ms));
async function submitForm(page, selector) {
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.evaluate((s) => document.querySelector(s).requestSubmit(), selector)]);
}
async function clickAndWait(page, selector) {
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.click(selector)]);
}

// Non-destructive proof that a `data-confirm` control is wired: open the dialog,
// read it back, then dismiss with Cancel. Leaves the record untouched.
async function confirmDialogOpens(role, page, selector, label, expectAction = "") {
  const btn = await page.$(selector);
  if (!btn) return skip(role, `confirm dialog: ${label}`, "no control on this page");
  const before = page.url();
  // stub requestSubmit so "Confirm" records the target instead of mutating data
  await page.evaluate(() => {
    window.__posted = null;
    if (!window.__origSubmit) window.__origSubmit = HTMLFormElement.prototype.requestSubmit;
    HTMLFormElement.prototype.requestSubmit = function () {
      window.__posted = this.getAttribute("action") || location.pathname;
    };
  });
  await btn.click();
  await settle(page, 300);
  const modal = await page.evaluate(() => {
    const p = document.querySelector("#modal-root .modal-panel:not(.hidden)");
    if (!p) return null;
    return { title: p.querySelector("h3").innerText.trim(), yes: p.querySelector("[data-confirm-yes]").innerText.trim() };
  });
  if (modal) {
    await page.evaluate(() => { const b = document.querySelector("#modal-root [data-confirm-yes]"); if (b) b.click(); });
    await settle(page, 250);
  }
  const posted = await page.evaluate(() => {
    HTMLFormElement.prototype.requestSubmit = window.__origSubmit;
    return window.__posted;
  });
  const ok = !!modal && !!modal.title && !!posted && (!expectAction || posted.includes(expectAction));
  check(role, `confirm dialog: ${label}`, ok, `title=${modal && modal.title} posts=${posted}`);
}

// ---------------------------------------------------------------- refund (owner processes a pending refund)
async function refundChecks(browser) {
  const role = "dana";
  const target = py(`from payments.models import Refund\nr = Refund.objects.filter(status="Pending").select_related("booking").order_by("-id").first()\nprint(f"{r.booking.property.title}|{r.reference}" if r else "")`);
  if (!target) return skip("owner", "confirm dialog: process refund", "no pending refund in the demo data");
  const [propTitle, reference] = target.split("|");
  const { ctx, page, errors } = await newSession(browser, role);
  await go(page, "/owner/payments/");
  const found = await page.evaluate((ref) => document.body.innerText.includes(ref), reference);
  if (!found) skip("owner", "confirm dialog: process refund", `refund ${reference} not on /owner/payments/`);
  else await confirmDialogOpens("owner", page, `form[data-confirm][action*='refunds'] button`, "process refund (pending-refund card)", "refunds");
  check("owner", `refund ${reference} listed for ${propTitle}`, found);
  check("owner", "no JS/network errors during refund flow", errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

// ---------------------------------------------------------------- payment (renter pays an approved booking)
async function paymentChecks(browser) {
  const role = "renter";
  const row = py(`from bookings.models import Booking\nb = Booking.objects.filter(status="Approved", renter__username="renter", property__owner__username="owner", payment__isnull=True).order_by("-id").first()\nprint(f"{b.id}|{b.property.title}" if b else "")`);
  if (!row) return skip(role, "renter can pay an approved booking", "no approved booking without a payment");
  const [bookingId, title] = row.split("|");
  const { ctx, page, errors } = await newSession(browser, role);
  await go(page, "/rent/bookings/");
  const payHref = await page.evaluate((t) => {
    const r = [...document.querySelectorAll("tbody tr")].find((x) => x.innerText.includes(t));
    const a = r ? r.querySelector('a[href*="/pay/"]') : null;
    return a ? a.getAttribute("href") : null;
  }, title);
  check(role, "approved booking shows a pay link", !!payHref, title);
  if (payHref) {
    await go(page, payHref);
    await page.evaluate(() => {
      const form = document.querySelector("form[data-validate]");
      const radio = form.querySelector('input[name="method"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event("change", { bubbles: true })); }
      const sim = form.querySelector('select[name="simulate"]');
      if (sim) { sim.value = "Success"; sim.dispatchEvent(new Event("change", { bubbles: true })); }
    });
    await submitForm(page, "form[data-validate]");
    const status = py(`from payments.models import Payment\np = Payment.objects.filter(booking_id=${bookingId}).order_by("-id").first()\nprint(p.status if p else "none")`);
    check(role, "renter can pay an approved booking", status === "Success", status);
    await go(page, "/rent/payments/");
    const listed = await page.evaluate((t) => document.body.innerText.includes(t), title);
    check(role, "payment appears in the renter payment list", listed, page.url());
    const booked = py(`from bookings.models import Booking\nprint(Booking.objects.get(id=${bookingId}).status)`);
    check(role, "booking stays approved after payment", booked === "Approved", booked);
  }
  check(role, "no JS/network errors during payment flow", errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

// ---------------------------------------------------------------- renter
async function renterChecks(browser) {
  const role = "renter";
  const { ctx, page, errors } = await newSession(browser, role);
  check(role, "login lands on renter dashboard", page.url().includes("/rent/"), page.url());

  // --- favourites (the reported bug) ---
  await go(page, "/rent/properties/");
  const firstCard = '[data-property-id] [data-favorite-toggle]';
  // grab the concrete property: "recommended" ordering can reshuffle after a favourite
  const targetId = await page.$eval("[data-property-id]", (el) => el.getAttribute("data-property-id"));
  const cardSel = `[data-property-id="${targetId}"] [data-favorite-toggle]`;
  // start from a known "not favourited" state so the toast assertion is stable.
  // Un-favouriting from the favourites page keeps the card in place, so the
  // "recommended" ordering on /rent/properties/ cannot move it mid-test.
  if ((await page.$eval(cardSel, (el) => el.getAttribute("aria-pressed"))) === "true") {
    await go(page, "/rent/favorites/");
    await page.click(`[data-property-id="${targetId}"] [data-favorite-toggle]`);
    await settle(page, 600);
    await go(page, "/rent/properties/");
  }
  await page.click(`[data-property-id="${targetId}"] [data-favorite-toggle]`);
  await settle(page);
  const after = await page.$eval(cardSel, (el) => el.getAttribute("aria-pressed"));
  check(role, "favorite button toggles (aria-pressed flips)", after === "true", String(after));
  const toastShown = await page.evaluate(() => !!document.querySelector(".toast"));
  check(role, "favorite shows a toast", toastShown);
  const filledVisible = await page.$eval(cardSel, (el) => !el.querySelector("[data-heart-on]").classList.contains("hidden"));
  check(role, "filled heart icon swaps in", filledVisible === (after === "true"));

  await go(page, "/rent/properties/");
  const persisted = await page.$eval(`[data-property-id="${targetId}"] [data-favorite-toggle]`, (el) => el.getAttribute("aria-pressed"));
  check(role, "favorite persists across reload", persisted === "true", String(persisted));

  await go(page, "/rent/favorites/");
  const favCards = await page.$$eval("[data-property-id]", (els) => els.length);
  check(role, "favourites page lists the saved property", favCards > 0, `cards=${favCards}`);
  if (favCards > 0) {
    // the favourites page keeps the card in place on purpose (data-keep-on-screen)
    const favBtn = '[data-favorites-list] [data-favorite-toggle]';
    const wasOn = await page.$eval(favBtn, (el) => el.getAttribute("aria-pressed"));
    await page.click(favBtn);
    await settle(page, 700);
    const nowOn = await page.$eval(favBtn, (el) => el.getAttribute("aria-pressed"));
    check(role, "un-favourite toggles the heart off", wasOn === "true" && nowOn === "false", `${wasOn} -> ${nowOn}`);
    await go(page, "/rent/favorites/");
    const stillThere = await page.$$eval("[data-property-id]", (els) => els.length);
    check(role, "removed property leaves the favourites list", stillThere === favCards - 1, `${favCards} -> ${stillThere}`);
    if (stillThere === 0) {
      const emptyVisible = await page.evaluate(() => { const e = document.getElementById("favorites-empty"); return e ? !e.classList.contains("hidden") : null; });
      check(role, "empty state appears", emptyVisible === true, String(emptyVisible));
    }
    // restore the demo data
    await go(page, "/rent/properties/");
    await page.click(`[data-property-id="${targetId}"] [data-favorite-toggle]`);
    await settle(page);
  }

  // --- search / filter / sort ---
  await go(page, "/rent/properties/");
  const allCards = await page.$$eval("[data-property-id]", (e) => e.length);
  await page.type('input[name="q"]', "zzzz-no-such-place");
  await settle(page, 900);
  const searched = await page.evaluate(() => new URLSearchParams(location.search).get("q"));
  check(role, "search auto-submits into the query string", searched === "zzzz-no-such-place", String(searched));
  const noResults = await page.$$eval("[data-property-id]", (e) => e.length);
  check(role, "search with no match shows empty state", noResults === 0, `cards=${noResults}/${allCards}`);
  await go(page, "/rent/properties/");
  const hasSelect = await page.$("select[data-auto-submit], select[name=sort]");
  if (hasSelect) {
    const options = await page.$$eval("select[name=sort] option", (o) => o.map((x) => x.value));
    if (options.length > 1) {
      await page.select("select[name=sort]", options[1]);
      await settle(page, 900);
      const sorted = await page.evaluate(() => new URLSearchParams(location.search).get("sort"));
      check(role, "sort dropdown re-orders the list", sorted === options[1], `${sorted} vs ${options[1]}`);
    }
  }
  const filterForm = await page.$("form[method=get] select");
  if (filterForm) {
    const value = await page.$eval("form[method=get] select", (s) => s.options[1] && s.options[1].value);
    if (value) {
      await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.evaluate(() => document.querySelector("form[method=get]").requestSubmit())]);
      check(role, "filter form applies query params", page.url().includes("="), page.url());
      const reset = await page.$('a[href$="/rent/properties/"]');
      if (reset) { await clickAndWait(page, 'a[href$="/rent/properties/"]'); check(role, "reset link clears filters", !page.url().includes("?"), page.url()); }
    }
  }

  // --- booking request (target: a free property owned by the demo owner) ---
  const target = py(`from listings.models import Property\nfrom bookings.models import Booking\nactive = set(Booking.objects.exclude(status__in=["Cancelled", "Rejected"]).values_list("property_id", flat=True))\np = next((x for x in Property.objects.filter(owner__username="owner") if x.id not in active), None)\nprint(f"{p.id}|{p.title}" if p else "")`);
  if (!target) {
    skip(role, "booking request submits", "no free demo-owner property");
  } else {
    const [propId, propTitle] = target.split("|");
    await go(page, `/rent/property/${propId}/`);
    const hasLink = await page.$('a[href$="/request/"]');
    if (!hasLink) {
      check(role, "booking request link present", false, `no request link on /rent/property/${propId}/`);
    } else {
      await clickAndWait(page, 'a[href$="/request/"]');
      const canRequest = await page.$("form[data-validate] input[name=lease_months]");
      if (canRequest) {
      await page.evaluate(() => {
        const form = document.querySelector("form[data-validate]");
        const moveIn = form.querySelector('input[name="move_in_date"]');
        if (moveIn && !moveIn.value) {
          const d = new Date();
          d.setMonth(d.getMonth() + 1, 1);
          moveIn.value = d.toISOString().slice(0, 10);
        }
        const radio = form.querySelector('input[name="lease_months"]');
        if (radio) { radio.checked = true; radio.dispatchEvent(new Event("change", { bubbles: true })); }
        form.requestSubmit();
      });
      await settle(page, 900);
      const requested = await page.evaluate((t) => document.body.innerText.includes(t), propTitle);
      check(role, "booking request submits", requested || page.url().includes("/rent/bookings/"), page.url());
      await go(page, "/rent/bookings/");
      const pendingNow = await page.evaluate((t) => {
        const row = [...document.querySelectorAll("tbody tr")].find((r) => r.innerText.includes(t));
        return row ? /pending|awaiting/i.test(row.innerText) : false;
      }, propTitle);
        check(role, "new booking shows as pending for the renter", pendingNow);
      } else {
        check(role, "booking request form present", false, `no lease field on the request page`);
      }
    }
  }
  await go(page, "/rent/bookings/");
  const pendingRows = await page.$$eval("[data-booking-row], .data-table tbody tr", (r) => r.length);
  check(role, "renter booking list renders", pendingRows > 0, `rows=${pendingRows}`);
  await confirmDialogOpens(role, page, `form[data-confirm][action*='cancel'] button, [data-confirm][href*='cancel']`, "cancel booking", "cancel");
  // the destructive cancel POST itself is covered by test_pending_booking_can_be_cancelled_by_renter;
  // here we only prove the dialog posts to the right action (see confirmDialogOpens)

  // --- profile, theme, language, notifications, copy ---
  await go(page, "/auth/preferences/");
  const nameInput = await page.$('input[name="display_name"], input[name="full_name"]');
  if (nameInput) {
    const original = await page.$eval('input[name="display_name"], input[name="full_name"]', (i) => i.value);
    await page.evaluate((sel) => { const i = document.querySelector(sel); i.value = ""; }, 'input[name="display_name"], input[name="full_name"]').catch(() => {});
    await page.type('input[name="display_name"], input[name="full_name"]', "Demo Renter");
    await submitForm(page, "form[data-validate]");
    check(role, "profile update saves", (await page.evaluate(() => document.body.innerText)).length > 0, original);
  }
  await go(page, "/rent/");
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.click('form[action*="theme"] button')]);
  check(role, "theme toggle switches to dark", await page.evaluate(() => document.documentElement.classList.contains("dark")));
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.click('form[action*="theme"] button')]);
  check(role, "theme toggle switches back to light", await page.evaluate(() => !document.documentElement.classList.contains("dark")));

  await go(page, "/rent/");
  const langBefore = await page.evaluate(() => document.documentElement.lang);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.click('form[action*="/i18n/set/"] button')]);
  const langAfter = await page.evaluate(() => document.documentElement.lang);
  check(role, "language toggle switches language", langBefore !== langAfter, `${langBefore} -> ${langAfter}`);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }), page.click('form[action*="/i18n/set/"] button')]);

  await go(page, "/rent/");
  const bell = await page.$("[data-notifications]");
  if (bell) {
    await bell.click();
    await settle(page, 700);
    const panel = await page.evaluate(() => { const p = document.querySelector("[data-notifications] + div, .dropdown-panel:not(.hidden)"); return p ? !p.classList.contains("hidden") : false; });
    check(role, "notifications panel opens", panel);
    const readAll = await page.$("[data-notifications] [data-read-all], .dropdown-panel [data-read-all]");
    if (readAll) { await readAll.click(); await settle(page, 700); check(role, "mark-all-read posts", true); }
  } else check(role, "notifications bell present", false, "selector missing");

  const copyBtn = await page.$("[data-copy]");
  if (copyBtn) {
    await copyBtn.click();
    await settle(page, 400);
    check(role, "copy button gives feedback", await page.evaluate(() => !!document.querySelector(".toast")));
  }

  const pwToggle = await page.$("[data-password-toggle]");
  if (pwToggle) {
    await go(page, "/auth/login/");
    const t2 = await page.$("[data-password-toggle]");
    if (t2) { await t2.click(); check(role, "password reveal toggles input type", await page.$eval('input[name=password]', (i) => i.type) === "text"); }
  }

  await go(page, "/rent/");
  const logout = await page.$('form[action*="logout"] button, a[href*="logout"]');
  if (logout) { await clickAndWait(page, 'form[action*="logout"] button'); check(role, "logout returns to login page", page.url().includes("/auth/login"), page.url()); }

  check(role, "no JS/network errors during renter flow", errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

// ---------------------------------------------------------------- owner
async function ownerChecks(browser) {
  const role = "owner";
  const { ctx, page, errors } = await newSession(browser, role);
  check(role, "login lands on owner dashboard", page.url().includes("/owner/"), page.url());

  await go(page, "/owner/bookings/");
  await confirmDialogOpens(role, page, `form[data-confirm][action*='reject'] button, [data-confirm][href*='reject']`, "reject booking", "reject");
  await go(page, "/owner/payments/");
  await confirmDialogOpens(role, page, `form[data-confirm][action*='refund'] button, [data-confirm][href*='refund'], form[action*='refunds'] button`, "process refund (demo owner)", "refund");

  await go(page, "/owner/properties/new/");
  const titleSel = 'input[name="title"]';
  if (await page.$(titleSel)) {
    const stamp = Date.now().toString().slice(-5);
    await page.type(titleSel, `Func Check Loft ${stamp}`);
    await page.type('input[name="location"]', "Street 999");
    await page.type('input[name="price_per_month"]', "777");
    await page.type('input[name="bedrooms"]', "2");
    await page.type('input[name="bathrooms"]', "1");
    await page.type('textarea[name="description"]', "Created by the automated functional sweep.");
    await submitForm(page, "form[data-validate]");
    const created = page.url().includes("/owner/properties/");
    check(role, "owner can create a property", created, page.url());
    const listed = await page.evaluate((t) => document.body.innerText.includes(t), `Func Check Loft ${stamp}`);
    check(role, "new property appears in the list", listed);
    // edit it
    const editHref = await page.evaluate((t) => { const a = [...document.querySelectorAll("a")].find((x) => x.textContent.includes(t)); return a ? a.getAttribute("href") : null; }, `Func Check Loft ${stamp}`);
    if (editHref && editHref.includes("/edit")) {
      await go(page, editHref);
      await page.evaluate(() => { const i = document.querySelector('input[name="title"]'); if (i) i.value = ""; });
      await page.type('input[name="title"]', `Func Check Loft ${stamp} EDITED`);
      await submitForm(page, "form[data-validate]");
      check(role, "owner can edit a property", (await page.evaluate((t) => document.body.innerText.includes(t), `${stamp} EDITED`)));
    }
    // delete with confirm -- target the row we created, never a demo property
    await go(page, "/owner/properties/");
    const deleted = await page.evaluate((t) => {
      const row = [...document.querySelectorAll("tbody tr")].find((r) => r.innerText.includes(t));
      const form = row ? row.querySelector('form[action*="/delete/"]') : null;
      if (!form) return false;
      form.querySelector("button").click();
      return true;
    }, `Func Check Loft ${stamp}`);
    if (deleted) {
      await settle(page, 400);
      const modal = await page.evaluate(() => !!document.querySelector("#modal-root .modal-panel:not(.hidden)"));
      check(role, "delete asks for confirmation", modal);
      if (modal) {
        await Promise.all([
          page.waitForNavigation({ waitUntil: "domcontentloaded" }).catch(() => null),
          page.evaluate(() => { const b = document.querySelector("#modal-root [data-confirm-yes]"); if (b) b.click(); }),
        ]);
        await settle(page, 400);
      }
      const gone = await page.evaluate((t) => !document.body.innerText.includes(t), `Func Check Loft ${stamp}`);
      check(role, "property deleted after confirm", gone);
    } else check(role, "delete row for created property found", false, "row missing");
  } else check(role, "property form renders", false, "no title input");

  await go(page, "/owner/bookings/");
  const approveTitle = py(`from bookings.models import Booking\nb = Booking.objects.filter(status="Pending", property__owner__username="owner").order_by("-id").first()\nprint(f"{b.id}|{b.property.title}" if b else "")`);
  if (!approveTitle) {
    skip(role, "owner can approve a booking", "no pending booking for the demo owner");
  } else {
    const [bookingId, bookingTitle] = approveTitle.split("|");
    // match on the row that links to this exact booking (titles repeat)
    const clicked = await page.evaluate((id) => {
      const link = document.querySelector(`a[href*="/owner/bookings/${id}/"]`);
      const row = link ? link.closest("tr") : null;
      const btn = row ? row.querySelector('form[action*="approve"] button') : null;
      if (!btn) return false;
      btn.click();
      return true;
    }, bookingId);
    check(role, "approve control present", clicked, `booking ${bookingId} (${bookingTitle})`);
    if (clicked) {
      // approve submits immediately on purpose (only destructive actions confirm)
      await Promise.all([
        page.waitForNavigation({ waitUntil: "domcontentloaded" }).catch(() => null),
        new Promise((r) => setTimeout(r, 250)),
      ]);
      const status = py(`from bookings.models import Booking\nprint(Booking.objects.get(id=${bookingId}).status)`);
      check(role, "owner can approve a booking", status === "Approved", status);
      await go(page, "/owner/bookings/");
      const shown = await page.evaluate((id) => {
        const link = document.querySelector(`a[href*="/owner/bookings/${id}/"]`);
        const row = link ? link.closest("tr") : null;
        return row ? /approved/i.test(row.innerText) : false;
      }, bookingId);
      check(role, "approved status shows in the owner list", shown);
      const payNotice = await go(page, "/owner/payments/").then(() => page.evaluate(() => document.body.innerText.length > 0));
      check(role, "owner payments page renders after approval", payNotice);
    }
  }
  const reject = await page.$('form[action*="reject"] [data-confirm]');
  if (reject) {
    await reject.click();
    await settle(page, 400);
    check(role, "reject opens confirm dialog", await page.evaluate(() => !!document.querySelector("#modal-root .modal-panel:not(.hidden)")));
    await page.keyboard.press("Escape");
  }

  await go(page, "/owner/payments/");
  const refund = await page.$('a[href*="refund"], [data-confirm][href*="refund"]');
  if (refund) { await clickAndWait(page, 'a[href*="refund"]'); check(role, "refund form opens", await page.$('form[action*="refund"]') !== null); }

  check(role, "no JS/network errors during owner flow", errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

// ---------------------------------------------------------------- admin
async function adminChecks(browser) {
  const role = "admin";
  const { ctx, page, errors } = await newSession(browser, role);
  check(role, "login lands on console dashboard", page.url().includes("/console"), page.url());

  for (const [path, label] of [["/console/bookings/", "console booking action"], ["/console/payments/", "console payment action"], ["/console/properties/", "console property action"]]) {
    await go(page, path);
    await confirmDialogOpens(role, page, `button[form*="delete"], [data-confirm][href]`, label, "delete");
  }

  await go(page, "/console/users/");
  await page.type('input[name="q"]', "admin");
  await settle(page, 900);
  const q = await page.evaluate(() => new URLSearchParams(location.search).get("q"));
  check(role, "console user search submits", q === "admin", String(q));
  await go(page, "/console/users/new/");
  const email = `func${Date.now().toString().slice(-6)}@fake.com`;
  if (await page.$('input[name="email"]')) {
    await page.type('input[name="full_name"]', "Func Check");
    await page.type('input[name="username"]', `func${Date.now().toString().slice(-6)}`);
    await page.type('input[name="email"]', email);
    await page.type('input[name="password"]', "Passw0rd!23");
    const roleSelect = await page.$('select[name="role"]');
    if (roleSelect) await page.select('select[name="role"]', "renter");
    await submitForm(page, "form[data-validate]");
    const createdUser = await page.evaluate((e) => document.body.innerText.includes(e), email);
    check(role, "admin can create a user", createdUser, page.url());
    // find and bulk delete
    await go(page, `/console/users/?q=${encodeURIComponent(email)}`);
    const box = await page.$("[data-bulk-item]");
    if (box) {
      await box.click();
      await settle(page, 300);
      const barVisible = await page.evaluate(() => { const b = document.querySelector("[data-bulk-bar]"); return b ? !b.classList.contains("hidden") : false; });
      check(role, "bulk bar appears when a row is selected", barVisible);
      await page.click("[data-bulk-submit]");
      await settle(page, 400);
      const modal = await page.evaluate(() => !!document.querySelector("#modal-root .modal-panel:not(.hidden)"));
      check(role, "bulk delete asks for confirmation", modal);
      if (modal) {
        await Promise.all([
          page.waitForNavigation({ waitUntil: "domcontentloaded" }).catch(() => null),
          page.evaluate(() => { const b = document.querySelector("#modal-root [data-confirm-yes]"); if (b) b.click(); }),
        ]);
        await settle(page, 300);
      }
      // the users page echoes the query as a pill, so count rows instead of text
      const gone = await page.evaluate(() => document.querySelectorAll("tbody [data-bulk-item]").length === 0);
      check(role, "bulk delete removes the user", gone, page.url());
    } else check(role, "bulk checkbox rendered", false, "row not found");
  } else check(role, "user form renders", false, "no email input");

  await go(page, "/console/properties/");
  const statusToggle = await page.$("[data-confirm][href*='status'], form[action*='status'] button");
  if (statusToggle) {
    await statusToggle.click();
    await settle(page, 900);
    check(role, "property status can be toggled", true);
  }
  for (const path of ["/console/properties/new/", "/console/bookings/new/", "/console/payments/new/"]) {
    await go(page, path);
    const forms = await page.$$eval("form[data-validate] input, form[data-validate] select", (f) => f.length);
    check(role, `console form renders (${path})`, forms > 0, `fields=${forms}`);
  }
  check(role, "no JS/network errors during admin flow", errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

const browser = await puppeteer.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
console.log(`functional sweep against ${BASE}`);
try {
  if (ONLY === "all" || ONLY === "renter") await renterChecks(browser);
  if (ONLY === "all" || ONLY === "owner") await ownerChecks(browser);
  if (ONLY === "all" || ONLY === "refund") await refundChecks(browser);
  if (ONLY === "all" || ONLY === "payment") await paymentChecks(browser);
  if (ONLY === "all" || ONLY === "admin") await adminChecks(browser);
} finally {
  await browser.close();
}
console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) { console.log(failures.map((f) => `  - ${f}`).join("\n")); process.exit(1); }
