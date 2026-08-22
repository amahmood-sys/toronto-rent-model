# `listings_real.csv`

Real Toronto apartment/condo/house rental listings scraped from Kijiji.

- **Source:** https://www.kijiji.ca/b-apartments-condos/city-of-toronto/c37l1700273
- **Scraped:** 2026-08-22
- **Method:** `ml/scraper.py` (requests + BeautifulSoup against Kijiji's
  server-rendered listing cards; `ml/scrape.js`, a Puppeteer + stealth
  scraper, is an automatic fallback if the plain-HTTP path returns 0 results)
- **Rows:** 420 unique listings (deduplicated by URL)
- **Columns:** `title, price, bedrooms, bathrooms, size_sqft, neighbourhood,
  property_type, has_parking, has_laundry, furnished, pets_allowed, url`

This file is committed to git (not `.gitignore`d) specifically so the model's
reported metrics can always be re-derived from the raw data — see
`ml/model.py` and `ml/baseline.py`.
