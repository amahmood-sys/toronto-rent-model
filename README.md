# 🏙️ Toronto Rental Predictor

**Estimate the monthly rent of a Toronto apartment, condo, or house from its
features — powered by a gradient-boosted model trained on real Kijiji listings.**

Pick a neighbourhood, property type, size, and amenities, and the app predicts a
market rent in dollars per month. It also shows how the same unit would price
across every Toronto neighbourhood in the dataset.

---

## What it does

Given a listing's attributes:

- **Neighbourhood** — one of 35 real, geocoded Toronto neighbourhoods
- **Property type** — Apartment, Condo, or House
- **Bedrooms, bathrooms, size (sq ft)**
- **Amenities** — parking, in-suite laundry, furnished, pets allowed

…it returns an **estimated monthly rent** and a ranked comparison of that unit
across neighbourhoods, so you can see where it would be cheaper or pricier.

## How it works

1. **Data collection.** A Puppeteer + stealth scraper (`ml/scrape.js`) collects
   live Kijiji rental listings, parsed into structured features. The training set
   is **440 real listings** (`data/listings_real.csv`), priced $800–$4,500/mo.
2. **Model.** An **XGBoost regressor** (400 trees) inside a scikit-learn
   `Pipeline` — `ColumnTransformer` + `OrdinalEncoder` for the categorical
   neighbourhood/property-type fields, numeric features passed through. Trained
   in `ml/model.py`. Cross-validated **R² ≈ 0.97** on the real data.
3. **Portable inference.** The trained model is exported to a plain JSON file
   (`model/model_export.json`: tree structure + categories + base score). Both
   front-ends run inference by walking those trees directly — **no Python ML
   runtime, no joblib/version matching needed to deploy.**
4. **Interpretability.** `ml/analysis.ipynb` explores the data (neighbourhood
   price ladder, amenity premiums, size curves) and explains the model with SHAP
   (beeswarm + per-prediction waterfalls) and a linear-regression baseline.

## Two ways to run it

Same model, same math — pick whichever platform you like.

### Option A — Streamlit (pure Python, easiest)

`streamlit_app.py` loads the model JSON and predicts with a pure-Python tree
traversal.

- **Streamlit Community Cloud (free):** https://share.streamlit.io → *New app* →
  this repo → branch `main` → main file `streamlit_app.py`.
- **Render (free):** the included `render.yaml` is auto-detected as a Blueprint.
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
| -------------------------- | --------------------------------------------------------- |
| `streamlit_app.py`         | Streamlit UI + pure-Python inference                      |
| `pages/index.js`           | Next.js prediction UI                                     |
| `pages/api/predict.js`     | Pure-JS inference — validated, rate-limited (see SECURITY) |
| `model/model_export.json`  | Exported trees + real neighbourhoods + base score         |
| `model/rent_model.joblib`  | Trained scikit-learn/XGBoost pipeline                     |
| `render.yaml`              | Render Blueprint for one-click deploy                     |
| `SECURITY.md`              | Security audit & hardening notes                          |
| `ml/` *(local only)*       | Training pipeline: scraper, model, analysis notebook      |

The `ml/` training code and raw data live locally and are intentionally **not
committed** — the deployed app only needs the exported model JSON.

## Tech stack

- **ML:** Python, XGBoost, scikit-learn, pandas, SHAP
- **Scraping:** Node.js, Puppeteer + stealth
- **Web:** Streamlit *(Python)* and Next.js 14 + React 18 + Tailwind CSS *(JS)*
- **Deploy:** Streamlit Community Cloud, Render, or Vercel

## Security

The one public endpoint (`/api/predict`) is input-validated, payload-capped
(4 KB), and rate-limited (30 req/min per IP). No secrets, auth, or user data are
involved. Full audit in [`SECURITY.md`](./SECURITY.md).

---

*Built as a data-science portfolio project. Predictions are model estimates, not
appraisals — actual rents vary.*
