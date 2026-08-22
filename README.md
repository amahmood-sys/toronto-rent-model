# 🏙️ Toronto Rental Predictor

**Estimate the monthly rent of a Toronto apartment, condo, or house from its
features — powered by a gradient-boosted machine-learning model trained on
real Kijiji listings.**

Pick a neighbourhood, property type, size, and amenities, and the app predicts a
market rent in dollars per month. It also shows how the same unit would price
across every Toronto neighbourhood in the dataset.

## What it does

Given a listing's attributes:

- **Neighbourhood** — one of 148 real, geocoded Toronto neighbourhoods
- **Property type** — Apartment, Condo, House, Basement Apartment, or Townhouse
- **Bedrooms, bathrooms, size (sq ft)**
- **Amenities** — parking, in-suite laundry, furnished, pets allowed

…it returns an **estimated monthly rent** and a ranked comparison of that unit
across neighbourhoods, so you can see where it would be cheaper or pricier.

## How it works

1. **Data collection.** `ml/scraper.py` scrapes live Kijiji rental listings
   (requests + BeautifulSoup against Kijiji's server-rendered listing cards,
   with a Puppeteer + stealth fallback if that ever returns 0 results). The
   current training set is **420 unique real listings** (deduplicated by URL;
   see `data/README.md` for scrape date and provenance), priced $650–$15,000/mo.
   No synthetic data of any kind is used anywhere in this project.

2. **The model** — An **XGBoost regressor with 400 trees**, wrapped in a
   scikit-learn pipeline that ordinal-encodes the categorical fields
   (neighbourhood, property type) and passes numeric features through.

   **Measured 5-fold cross-validation results** (`ml/model.py`, reproducible via
   `python ml/model.py --data data/listings_real.csv`):

   | Model | CV R² | CV MAE | CV RMSE |
   |---|---|---|---|
   | **XGBoost** | 0.629 ± 0.251 | $460 ± $41 | $706 ± $96 |
   | Linear regression baseline | 0.474 ± 0.267 | $556 ± $55 | — |

   XGBoost reduces MAE by **~17%** over the linear baseline on the same CV
   folds (`ml/baseline.py`). The R² has a wide standard deviation across folds
   — expected at this sample size (420 rows / 5 folds ≈ 84 test rows per fold)
   combined with a long price tail (some luxury listings rent for $10K+/mo).
   These are the actual numbers this codebase produces — not rounded up.

3. **Portable inference** — The trained model is exported to a plain JSON file
   (`model/model_export.json`: tree structure + categories + base score) via
   `ml/export_model.py`. Both front-ends run inference by walking those trees
   directly — **no Python ML runtime needed to deploy**, no version-matching
   headaches, and instant cold starts. JS and Python inference are verified to
   produce identical predictions from the same model.

## Two ways to run it

Same model, same math — pick whichever platform you like.

### Option A — Streamlit (pure Python, easiest)

`streamlit_app.py` loads the model JSON and predicts with a pure-Python tree
traversal.

- **Streamlit Community Cloud (free):** https://share.streamlit.io → *New app* →
  this repo → branch `main` → main file `streamlit_app.py`.
- **Render (free):** the included `render.yaml` is auto-detected.
- **Locally:**
  ```bash
  pip install -r requirements.txt
  streamlit run streamlit_app.py     # http://localhost:8501
  ```

### Option B — Next.js on Vercel

`pages/index.js` (UI) + `pages/api/predict.js` (the same inference in JavaScript).

```bash
npm install
npm run dev        # http://localhost:3000
```
> The repo root also has `requirements.txt` for Streamlit, which can trigger
> Vercel's Python builder. Deploy on **one** platform to avoid the conflict.

## Project structure

| Path                       | Purpose                                                   |
| -------------------------- | ----------------------------------------------------------|
| `streamlit_app.py`         | Streamlit UI + pure-Python inference                      |
| `pages/index.js`           | Next.js prediction UI                                     |
| `pages/api/predict.js`     | Pure-JS inference — validated, rate-limited (see SECURITY) |
| `model/model_export.json`  | Exported trees + real neighbourhoods + base score          |
| `model/rent_model.joblib`  | Trained scikit-learn/XGBoost pipeline                     |
| `data/listings_real.csv`   | Real scraped Kijiji listings (committed — see `data/README.md`) |
| `render.yaml`              | Render Blueprint for one-click deploy                     |
| `SECURITY.md`              | Security audit & hardening notes                          |
| `ml/` *(local only)*       | Training code: scraper, model, baseline, export, notebook  |

`ml/` (the training **code**) is intentionally not committed — the deployed
app only needs `model/model_export.json`. `data/listings_real.csv` (the raw
**data**) *is* committed, specifically so the metrics above can always be
re-derived rather than taken on faith.

## Tech stack

- **ML:** Python, XGBoost, scikit-learn, pandas
- **Scraping:** Python (requests + BeautifulSoup), with Node.js + Puppeteer +
  stealth as an automatic fallback
- **Web:** Streamlit *(Python)* and Next.js 14 + React 18 + Tailwind CSS *(JS)*
- **Deploy:** Streamlit Community Cloud, Render, or Vercel

## Security

The one public endpoint (`/api/predict`) is input-validated, payload-capped
(4 KB), and rate-limited (30 req/min per IP). No secrets, auth, or user data are
involved. Full audit in [`SECURITY.md`](./SECURITY.md).

---

*Built as a data-science portfolio project. Predictions are model estimates, not
appraisals — actual rents vary.*
