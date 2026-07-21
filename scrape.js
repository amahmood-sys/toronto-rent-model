/**
 * scrape.js — Kijiji Toronto rental scraper
 *
 * Uses puppeteer-extra + stealth plugin with human-like behaviour:
 *   - Randomised viewport dimensions
 *   - Random mouse movements before and between interactions
 *   - Randomised delays that mimic natural reading/scrolling cadence
 *   - Stealth evasions (removes navigator.webdriver, spoofs plugins, etc.)
 *
 * Output: JSON array of { title, price, bedrooms, size, location, url }
 * written to stdout so Python can consume it via subprocess.
 *
 * Usage:
 *   node scrape.js [--pages N] [--out listings.json]
 */

const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const fs = require("fs");

puppeteer.use(StealthPlugin());

// ── Config ────────────────────────────────────────────────────────────────────

const BASE_URL =
  "https://www.kijiji.ca/b-apartments-condos/city-of-toronto/c37l1700273";

const VIEWPORTS = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1536, height: 864 },
  { width: 1920, height: 1080 },
  { width: 1280, height: 800 },
];

const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (min, max) => Math.random() * (max - min) + min;
const randInt = (min, max) => Math.floor(rand(min, max));
const pick = (arr) => arr[randInt(0, arr.length)];

/** Move the mouse along a curved path to (x, y) over ~400–900 ms. */
async function humanMouseMove(page, x, y) {
  const steps = randInt(8, 20);
  const { width, height } = page.viewport();
  let cx = randInt(100, width - 100);
  let cy = randInt(100, height - 100);

  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    // Quadratic bezier-ish curve with a control point offset
    const cpx = (cx + x) / 2 + rand(-80, 80);
    const cpy = (cy + y) / 2 + rand(-80, 80);
    const nx = (1 - t) * (1 - t) * cx + 2 * (1 - t) * t * cpx + t * t * x;
    const ny = (1 - t) * (1 - t) * cy + 2 * (1 - t) * t * cpy + t * t * y;
    await page.mouse.move(nx, ny);
    await sleep(rand(15, 45));
  }
}

/** Scroll down in human-like increments with random pauses. */
async function humanScroll(page) {
  const { height } = page.viewport();
  const scrolls = randInt(4, 9);
  for (let i = 0; i < scrolls; i++) {
    const delta = randInt(120, 380);
    await page.evaluate((d) => window.scrollBy({ top: d, behavior: "smooth" }), delta);
    await sleep(rand(300, 900));
    // Occasional brief upward scroll (mimics re-reading)
    if (Math.random() < 0.2) {
      await page.evaluate((d) => window.scrollBy({ top: -d, behavior: "smooth" }), randInt(40, 100));
      await sleep(rand(200, 500));
    }
  }
}

/** Parse a price string like "$2,200.00" → 2200 or null. */
function parsePrice(text) {
  if (!text) return null;
  const clean = text.replace(/[^\d.]/g, "");
  const val = parseFloat(clean);
  if (isNaN(val) || val < 300 || val > 25000) return null;
  return val > 15000 ? Math.round(val / 12) : val; // normalise annual → monthly
}

// ── Scrape a single page ──────────────────────────────────────────────────────

async function scrapePage(page, url) {
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });

  // Random mouse wander after load
  for (let i = 0; i < randInt(2, 5); i++) {
    const { width, height } = page.viewport();
    await humanMouseMove(page, randInt(100, width - 100), randInt(100, height - 100));
    await sleep(rand(200, 600));
  }

  await humanScroll(page);
  await sleep(rand(800, 1600));

  // Wait for listing cards to appear (stable data-testid selectors)
  try {
    await page.waitForSelector('[data-testid="listing-card-list-item-0"]', { timeout: 10000 });
  } catch (_) {
    // Continue anyway — will return empty if cards not present
  }

  const listings = await page.evaluate(() => {
    const results = [];
    // Each listing is a <li data-testid="listing-card-list-item-N">
    const cards = document.querySelectorAll('li[data-testid^="listing-card-list-item"]');

    cards.forEach((card) => {
      try {
        const titleEl = card.querySelector('[data-testid="listing-title"]') ||
                        card.querySelector('[data-testid="listing-link"]');
        const title = titleEl ? titleEl.textContent.trim() : null;

        const linkEl = card.querySelector('[data-testid="listing-link"]') ||
                       card.querySelector('a[href*="/v-"]');
        const href = linkEl ? linkEl.getAttribute("href") : null;
        const url = href
          ? href.startsWith("http") ? href : "https://www.kijiji.ca" + href
          : null;

        const priceEl = card.querySelector('[data-testid="listing-price"]');
        const priceText = priceEl ? priceEl.textContent.trim() : null;

        const locEl = card.querySelector('[data-testid="listing-location"]');
        const location = locEl
          ? locEl.textContent.trim().split(",")[0].trim()
          : "Toronto";

        // Bedroom count from details badges (e.g. "2 Bedrooms") or title
        const allText = card.textContent;
        const bedMatch = allText.match(/(\d+(?:\.\d+)?)\s*(?:\+\s*\d+\s*)?Bed(?:room)?s?/i) ||
                         allText.match(/Bachelor|Studio/i);
        const bedrooms = bedMatch ? bedMatch[0].trim() : title;

        const sizeMatch = allText.match(/([\d,]+)\s*(?:ft²|sq\.?\s*ft)/i);
        const size = sizeMatch ? sizeMatch[1].replace(",", "") : null;

        if (title && priceText) {
          results.push({ title, priceText, bedrooms, size, location, url });
        }
      } catch (_) {}
    });

    return results;
  });

  return listings;
}

// ── Pagination ────────────────────────────────────────────────────────────────

function pageUrl(page) {
  return page === 1 ? BASE_URL : `${BASE_URL}?page=${page}`;
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  // Parse CLI args
  const args = process.argv.slice(2);
  const pagesArg = args.indexOf("--pages");
  const outArg = args.indexOf("--out");
  const totalPages = pagesArg >= 0 ? parseInt(args[pagesArg + 1], 10) : 5;
  const outFile = outArg >= 0 ? args[outArg + 1] : null;

  const viewport = pick(VIEWPORTS);
  const userAgent = pick(USER_AGENTS);

  const browser = await puppeteer.launch({
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-blink-features=AutomationControlled",
      "--ignore-certificate-errors",
      "--ignore-certificate-errors-spki-list",
      `--window-size=${viewport.width},${viewport.height}`,
    ],
  });

  const page = await browser.newPage();
  await page.setViewport(viewport);
  await page.setUserAgent(userAgent);

  // Extra headers to look like a real browser
  await page.setExtraHTTPHeaders({
    "Accept-Language": "en-CA,en;q=0.9",
    Accept:
      "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
  });

  const allListings = [];

  for (let p = 1; p <= totalPages; p++) {
    process.stderr.write(`Scraping page ${p}/${totalPages} …\n`);
    try {
      const raw = await scrapePage(page, pageUrl(p));
      const parsed = raw
        .map((item) => ({
          title: item.title,
          price: parsePrice(item.priceText),
          bedrooms: item.bedrooms,
          size_sqft: item.size ? parseFloat(item.size) : null,
          location: item.location,
          url: item.url,
        }))
        .filter((item) => item.price !== null);

      process.stderr.write(`  Found ${parsed.length} valid listings\n`);
      allListings.push(...parsed);
    } catch (err) {
      process.stderr.write(`  Error on page ${p}: ${err.message}\n`);
    }

    if (p < totalPages) {
      const delay = rand(3000, 6000);
      process.stderr.write(`  Sleeping ${(delay / 1000).toFixed(1)}s …\n`);
      await sleep(delay);
    }
  }

  await browser.close();

  process.stderr.write(`\nTotal: ${allListings.length} listings\n`);

  const json = JSON.stringify(allListings, null, 2);
  if (outFile) {
    fs.writeFileSync(outFile, json);
    process.stderr.write(`Saved → ${outFile}\n`);
  } else {
    process.stdout.write(json);
  }
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err.message}\n`);
  process.exit(1);
});
