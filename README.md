# Toronto Rent Model

What should a Toronto rental cost, and which features and neighbourhoods drive the price?

This project scrapes Kijiji listings, trains a rent-prediction model and serves it in a small app: enter a neighbourhood, property type, size and amenities, and get a predicted monthly rent plus what the same unit would cost in other neighbourhoods.

## Findings

- On 420 Toronto listings ($650–$15,000/month), XGBoost predicts rent with a cross-validated **MAE of $460/month vs. $556 for a linear baseline (17% lower error)** and an **R² of 0.63**.
- R² swings widely between folds (±0.25). That is expected with about 84 test rows per fold and a long tail of luxury listings, and it is worth keeping in mind when reading any single prediction.
- I used SHAP to explain which features and neighbourhoods drive rent, and published the takeaways on LinkedIn.

## How it works

- **Data:** a scraper pulls Kijiji rental listings (requests + BeautifulSoup, with a Puppeteer fallback). Listings are deduplicated by URL and the raw data is committed in `data/listings_real.csv`.
- **Model:** a 400-tree XGBoost regressor in a scikit-learn pipeline. Inputs are neighbourhood (148), property type, bedrooms, bathrooms, square footage, parking, in-suite laundry, furnished and pets allowed.

## Decisions & tradeoffs

- **XGBoost over linear regression**, because it cut MAE by 17% on identical folds. I report the fold-to-fold spread rather than a single best score.
- **Model exported to plain JSON.** Both front ends predict by walking the exported trees directly (pure Python in Streamlit, JavaScript in the Next.js API), so deployment needs no ML runtime. The two implementations produce identical predictions.
- **Raw data is committed** so the metrics can be re-derived rather than taken on faith.
- **The one public endpoint (`/api/predict`) is locked down:** inputs are validated, payloads are capped at 4 KB and requests are rate-limited to 30 per minute per IP.

## What I'd do next

- Collect more listings over time to shrink the fold-to-fold variance.
- Commit the training code (scraper, model, baseline and SHAP notebook) so the full pipeline is reproducible from this repo.

## Run it

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py    # http://localhost:8501

# or the Next.js version
npm install
npm run dev                       # http://localhost:3000
```

Built with Python, XGBoost, scikit-learn, pandas, Streamlit and Next.js. Developed with Claude Code as a pair programmer.
