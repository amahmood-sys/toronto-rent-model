# Toronto Rental Predictor

A Next.js web app that predicts Toronto monthly rent from listing features
(neighbourhood, property type, bedrooms, bathrooms, size, amenities) using an
XGBoost model trained on real Kijiji listings.

## Deploy (Vercel)

- **Framework:** Next.js (auto-detected)
- **Root Directory:** `./`
- **Build Command:** `next build` (default)
- No Python runtime is used. Model inference runs in pure JavaScript in
  `pages/api/predict.js`, reading the exported model at `model/model_export.json`.

## Local development

```bash
npm install
npm run dev        # http://localhost:3000
```

## Structure

| Path                     | Purpose                                        |
| ------------------------ | ---------------------------------------------- |
| `pages/index.js`         | Prediction UI                                  |
| `pages/api/predict.js`   | Pure-JS XGBoost inference (no Python)          |
| `model/model_export.json`| Exported trees + categories + base score       |

The ML training pipeline (scraper, model training, analysis notebook) lives
locally under `ml/` and is intentionally not committed — the deployed app only
needs the exported model JSON.
