# Toronto Rental Predictor

Predicts Toronto monthly rent from listing features (neighbourhood, property
type, bedrooms, bathrooms, size, amenities) using an **XGBoost model trained on
440 real Kijiji listings** scraped with a Puppeteer stealth scraper. All 35
neighbourhoods are real, geocoded Toronto neighbourhood names — no synthetic data.

There are two ways to run the app. Pick one.

## Option A — Streamlit (easiest, pure Python)

Runs `streamlit_app.py`, which loads `model/model_export.json` and predicts via a
pure-Python tree traversal (no joblib/xgboost version matching needed).

**Streamlit Community Cloud** (free):
1. Push this repo to GitHub.
2. Go to https://share.streamlit.io → **New app**.
3. Pick this repo, branch `main`, main file `streamlit_app.py`. Deploy.

**Render** (free web service): the included `render.yaml` is auto-detected.
1. Go to https://render.com → **New** → **Blueprint** → pick this repo.
2. Render reads `render.yaml` and runs:
   `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`

**Locally:**
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py     # http://localhost:8501
```

## Option B — Next.js (Vercel)

Runs `pages/index.js` with JS inference in `pages/api/predict.js` (same model,
same math, in JavaScript). Framework: Next.js, Root Directory `./`.
```bash
npm install
npm run dev        # http://localhost:3000
```
> Note: because this repo also contains `requirements.txt` (for Streamlit),
> Vercel may try to run a Python build. If you deploy on Vercel, either remove
> `requirements.txt` on the deployed branch or use Streamlit/Render instead.

## Structure

| Path                      | Purpose                                         |
| ------------------------- | ----------------------------------------------- |
| `streamlit_app.py`        | Streamlit UI + pure-Python inference            |
| `pages/index.js`          | Next.js UI                                       |
| `pages/api/predict.js`    | Pure-JS inference (Vercel)                        |
| `model/model_export.json` | Exported trees + real neighbourhoods + base score|
| `render.yaml`             | Render Blueprint for one-click deploy            |

The ML training pipeline (scraper, training, analysis notebook) lives locally
under `ml/` and is intentionally not committed — the deployed app only needs the
exported model JSON.
