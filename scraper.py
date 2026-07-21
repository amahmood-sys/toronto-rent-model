"""
Kijiji Toronto rental listing scraper.

Fetches apartment/condo listings from Kijiji and saves them to CSV.
Run directly or import KijijiScraper for use in other modules.

Usage:
    python scraper.py --pages 5 --output data/listings.csv
    python scraper.py --sample --output data/listings.csv   # generate synthetic data
"""

import argparse
import csv
import json
import logging
import random
import re
import subprocess
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://www.kijiji.ca"
SEARCH_URL = (
    "https://www.kijiji.ca/b-apartments-condos/city-of-toronto/c37l1700273"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Toronto neighbourhoods used both by the scraper and the sample generator
TORONTO_NEIGHBOURHOODS = [
    "Downtown Core", "Annex", "Kensington Market", "Distillery District",
    "Liberty Village", "King West", "Queen West", "Roncesvalles",
    "Leslieville", "Riverside", "Beaches", "Danforth", "Greektown",
    "Scarborough", "North York", "Etobicoke", "Yorkville", "Midtown",
    "Forest Hill", "Rosedale", "Cabbagetown", "St. Lawrence Market",
    "Financial District", "Harbourfront", "Little Italy", "Bloordale",
    "Junction", "High Park", "Parkdale", "Swansea",
]

PROPERTY_TYPES = [
    "Apartment", "Condo", "Basement Apartment", "House", "Townhouse",
    "Bachelor/Studio", "Semi-Detached",
]


@dataclass
class Listing:
    title: str
    price: float                  # monthly rent in CAD
    bedrooms: float               # 0 = bachelor/studio
    bathrooms: float
    size_sqft: Optional[float]
    neighbourhood: str
    property_type: str
    has_parking: bool
    has_laundry: bool
    furnished: bool
    pets_allowed: bool
    url: str


def _parse_price(text: str) -> Optional[float]:
    """Extract numeric monthly rent from a Kijiji price string."""
    text = text.replace("\xa0", " ").strip()
    # Reject non-numeric placeholders
    if re.search(r"please contact|swap|free", text, re.I):
        return None
    digits = re.sub(r"[^\d.]", "", text)
    try:
        value = float(digits)
        # Kijiji shows annual rent for some listings – normalise
        return value / 12 if value > 15_000 else value
    except ValueError:
        return None


def _parse_bedrooms(text: str) -> Optional[float]:
    text = text.lower().strip()
    if any(k in text for k in ("bachelor", "studio", "0")):
        return 0.0
    m = re.search(r"(\d+)\s*\+\s*(\d+)", text)  # e.g. "2 + 1"
    if m:
        return float(m.group(1)) + 0.5 * float(m.group(2))
    m = re.search(r"(\d+)", text)
    return float(m.group(1)) if m else None


def _parse_bathrooms(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _parse_size(text: str) -> Optional[float]:
    m = re.search(r"([\d,]+)\s*(?:ft²|sq\.?\s*ft)", text, re.I)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _flag_in_text(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k in lower for k in keywords)


class KijijiScraper:
    """Scrapes rental listings from Kijiji Toronto apartments/condos."""

    REQUEST_DELAY = (1.5, 3.0)  # seconds between page requests

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, url: str, params: dict | None = None) -> BeautifulSoup:
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")

    def _parse_listing_card(self, card) -> Optional[Listing]:
        """Extract a Listing from a single search-result card element."""
        try:
            # ── price ──────────────────────────────────────────────────────
            price_el = (
                card.select_one("[class*='price']")
                or card.select_one("div.price")
            )
            if not price_el:
                return None
            price = _parse_price(price_el.get_text())
            if price is None or price < 300 or price > 25_000:
                return None

            # ── title / URL ────────────────────────────────────────────────
            anchor = card.select_one("a[class*='title'], a[href*='/v-']")
            if not anchor:
                return None
            title = anchor.get_text(strip=True)
            href = anchor.get("href", "")
            url = href if href.startswith("http") else BASE_URL + href

            # ── bedrooms / bathrooms / size ────────────────────────────────
            detail_spans = card.select(
                "[class*='bedrooms'] span, [class*='bedroom'] span, "
                "[class*='bed'] span, [data-testid*='bed']"
            )
            bed_text = " ".join(s.get_text() for s in detail_spans) or title
            bedrooms = _parse_bedrooms(bed_text) or 1.0

            bath_spans = card.select(
                "[class*='bathroom'] span, [class*='bath'] span"
            )
            bath_text = " ".join(s.get_text() for s in bath_spans)
            bathrooms = _parse_bathrooms(bath_text) or 1.0

            size_text = card.get_text()
            size_sqft = _parse_size(size_text)

            # ── location ───────────────────────────────────────────────────
            loc_el = card.select_one(
                "[class*='location'] span, "
                "[class*='address'], "
                "[data-testid*='location']"
            )
            neighbourhood = loc_el.get_text(strip=True) if loc_el else "Toronto"
            neighbourhood = neighbourhood.split(",")[0].strip()

            # ── property type from title ───────────────────────────────────
            property_type = "Apartment"
            for pt in PROPERTY_TYPES:
                if pt.lower() in title.lower():
                    property_type = pt
                    break

            full_text = card.get_text()
            has_parking = _flag_in_text(full_text, ["parking", "garage"])
            has_laundry = _flag_in_text(full_text, ["laundry", "washer"])
            furnished = _flag_in_text(full_text, ["furnished"])
            pets_allowed = _flag_in_text(full_text, ["pet", "dog", "cat"])

            return Listing(
                title=title,
                price=price,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                size_sqft=size_sqft,
                neighbourhood=neighbourhood,
                property_type=property_type,
                has_parking=has_parking,
                has_laundry=has_laundry,
                furnished=furnished,
                pets_allowed=pets_allowed,
                url=url,
            )
        except Exception as exc:
            log.debug("Skipping card: %s", exc)
            return None

    def _scrape_page(self, page: int) -> list[Listing]:
        params = {"page": page} if page > 1 else {}
        log.info("Fetching page %d …", page)
        try:
            soup = self._get(SEARCH_URL, params=params)
        except requests.RequestException as exc:
            log.warning("Failed to fetch page %d: %s", page, exc)
            return []

        # Kijiji renders listings in <li data-listing-id="..."> or <article>
        cards = (
            soup.select("li[data-listing-id]")
            or soup.select("article[data-listing-id]")
            or soup.select("[class*='search-item']")
        )
        log.info("  Found %d cards on page %d", len(cards), page)

        listings = []
        for card in cards:
            listing = self._parse_listing_card(card)
            if listing:
                listings.append(listing)
        return listings

    def scrape(self, pages: int = 5) -> list[Listing]:
        """Scrape via requests/BS4; fall back to Puppeteer if JS-blocked."""
        all_listings: list[Listing] = []
        for page in range(1, pages + 1):
            batch = self._scrape_page(page)
            all_listings.extend(batch)
            if page < pages:
                delay = random.uniform(*self.REQUEST_DELAY)
                log.info("  Sleeping %.1fs …", delay)
                time.sleep(delay)

        if not all_listings:
            log.info("requests/BS4 returned 0 listings — trying Puppeteer …")
            all_listings = self._scrape_puppeteer(pages)

        log.info("Scraped %d valid listings total.", len(all_listings))
        return all_listings

    def _scrape_puppeteer(self, pages: int) -> list[Listing]:
        """Run scrape.js (Puppeteer + stealth) and parse its JSON output."""
        script = Path(__file__).parent / "scrape.js"
        if not script.exists():
            log.error("scrape.js not found — cannot use Puppeteer fallback.")
            return []

        log.info("Launching headless browser via scrape.js …")
        try:
            result = subprocess.run(
                ["node", str(script), "--pages", str(pages)],
                capture_output=True,
                text=True,
                timeout=pages * 45 + 30,
            )
        except FileNotFoundError:
            log.error("node not found — install Node.js to use Puppeteer fallback.")
            return []
        except subprocess.TimeoutExpired:
            log.error("Puppeteer scrape timed out.")
            return []

        if result.returncode != 0:
            log.error("scrape.js exited with code %d", result.returncode)
            log.debug("stderr: %s", result.stderr)
            return []

        # stderr is progress output; stdout is the JSON array
        for line in result.stderr.splitlines():
            log.info("[puppeteer] %s", line)

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            log.error("Failed to parse scrape.js output: %s", exc)
            return []

        listings = []
        for item in raw:
            try:
                bed_text = item.get("bedrooms") or item.get("title", "")
                bedrooms = _parse_bedrooms(bed_text) or 1.0
                price = float(item["price"])
                listings.append(
                    Listing(
                        title=item.get("title", ""),
                        price=price,
                        bedrooms=bedrooms,
                        bathrooms=1.0,
                        size_sqft=float(item["size_sqft"]) if item.get("size_sqft") else None,
                        neighbourhood=item.get("location", "Toronto"),
                        property_type=_infer_property_type(item.get("title", "")),
                        has_parking=_flag_in_text(item.get("title", ""), ["parking", "garage"]),
                        has_laundry=_flag_in_text(item.get("title", ""), ["laundry", "washer"]),
                        furnished=_flag_in_text(item.get("title", ""), ["furnished"]),
                        pets_allowed=_flag_in_text(item.get("title", ""), ["pet", "dog", "cat"]),
                        url=item.get("url", ""),
                    )
                )
            except Exception as exc:
                log.debug("Skipping puppeteer item: %s", exc)

        return listings


def _infer_property_type(title: str) -> str:
    title_lower = title.lower()
    for pt in PROPERTY_TYPES:
        if pt.lower() in title_lower:
            return pt
    return "Apartment"


def save_listings(listings: list[Listing], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    col_names = [f.name for f in fields(Listing)]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=col_names)
        writer.writeheader()
        for lst in listings:
            row = {f.name: getattr(lst, f.name) for f in fields(lst)}
            writer.writerow(row)
    log.info("Saved %d listings → %s", len(listings), path)


# ── Synthetic data generator ──────────────────────────────────────────────────

def _base_rent(bedrooms: float, neighbourhood: str, property_type: str) -> float:
    """Return a realistic base rent for the given combination."""
    # Neighbourhood price index (rough Toronto tiers)
    premium = {
        "Yorkville": 1.40, "Rosedale": 1.35, "Forest Hill": 1.30,
        "Financial District": 1.25, "Downtown Core": 1.22, "Harbourfront": 1.20,
        "King West": 1.18, "Queen West": 1.15, "Liberty Village": 1.12,
        "Distillery District": 1.10, "Annex": 1.08, "Midtown": 1.06,
        "High Park": 1.02, "Leslieville": 1.00, "Danforth": 0.98,
        "Greektown": 0.97, "Beaches": 0.97, "Cabbagetown": 0.96,
        "Scarborough": 0.85, "Etobicoke": 0.88, "North York": 0.88,
    }
    hood_mult = premium.get(neighbourhood, 1.0)

    type_mult = {
        "Bachelor/Studio": 0.60, "Basement Apartment": 0.72,
        "Apartment": 1.00, "Condo": 1.10,
        "Semi-Detached": 1.15, "Townhouse": 1.20, "House": 1.30,
    }.get(property_type, 1.0)

    bed_base = {0: 1_500, 1: 2_100, 2: 2_800, 3: 3_600, 4: 4_400}.get(
        int(bedrooms), 5_000
    )
    return bed_base * hood_mult * type_mult


def generate_sample_data(n: int = 500, seed: int = 42) -> list[Listing]:
    """Generate synthetic Toronto rental listings with realistic pricing."""
    rng = random.Random(seed)
    listings = []
    for i in range(n):
        neighbourhood = rng.choice(TORONTO_NEIGHBOURHOODS)
        property_type = rng.choices(
            PROPERTY_TYPES,
            weights=[35, 25, 15, 8, 7, 7, 3],
        )[0]

        bedrooms = rng.choices(
            [0, 1, 2, 3, 4],
            weights=[8, 35, 35, 15, 7],
        )[0]
        # Occasionally add den (e.g. 1+1 → 1.5)
        if rng.random() < 0.15 and bedrooms >= 1:
            bedrooms += 0.5

        bathrooms = max(1.0, min(bedrooms + rng.choice([-1, 0, 0, 1]), 3.0))
        sqft_per_bed = rng.gauss(550, 80)
        size_sqft = round(max(300.0, (bedrooms or 0.5) * sqft_per_bed / 1.0))

        has_parking = rng.random() < 0.45
        has_laundry = rng.random() < 0.65
        furnished = rng.random() < 0.20
        pets_allowed = rng.random() < 0.35

        base = _base_rent(bedrooms, neighbourhood, property_type)
        # Add premiums
        if has_parking:
            base += rng.uniform(100, 200)
        if furnished:
            base += rng.uniform(150, 350)
        # Size adjustment (~$1.50/sqft relative to expected)
        expected_sqft = (bedrooms or 0.5) * 550
        base += (size_sqft - expected_sqft) * 1.50

        noise = rng.gauss(0, base * 0.06)
        price = max(800.0, round(base + noise, -1))  # round to $10

        listings.append(
            Listing(
                title=f"{neighbourhood} – {bedrooms}BR {property_type}",
                price=price,
                bedrooms=float(bedrooms),
                bathrooms=float(bathrooms),
                size_sqft=float(size_sqft),
                neighbourhood=neighbourhood,
                property_type=property_type,
                has_parking=has_parking,
                has_laundry=has_laundry,
                furnished=furnished,
                pets_allowed=pets_allowed,
                url=f"https://www.kijiji.ca/sample/{i}",
            )
        )
    return listings


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scrape Toronto rental listings from Kijiji."
    )
    p.add_argument(
        "--pages", type=int, default=5,
        help="Number of Kijiji result pages to scrape (default: 5).",
    )
    p.add_argument(
        "--output", default="data/listings.csv",
        help="Output CSV path (default: data/listings.csv).",
    )
    p.add_argument(
        "--sample", action="store_true",
        help="Generate synthetic sample data instead of hitting Kijiji.",
    )
    p.add_argument(
        "--sample-n", type=int, default=500,
        help="Number of synthetic listings to generate (default: 500).",
    )
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.sample:
        log.info("Generating %d synthetic listings …", args.sample_n)
        listings = generate_sample_data(n=args.sample_n)
    else:
        scraper = KijijiScraper()
        listings = scraper.scrape(pages=args.pages)
        if not listings:
            log.warning(
                "No listings scraped from Kijiji. "
                "Try --sample to use synthetic data."
            )
            return

    save_listings(listings, args.output)


if __name__ == "__main__":
    main()
