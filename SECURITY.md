# Security Audit & Hardening

_Last reviewed: 2026-08-22_

This document records the security review of the Toronto Rental Predictor and
the hardening applied to it.

## Scope — what this app actually is

The deployed application has a **very small attack surface**:

- **One HTTP endpoint:** `pages/api/predict.js` (accepts a JSON body, returns a
  predicted rent).
- **One Streamlit UI:** `streamlit_app.py` (inputs come from constrained widgets).
- **Static assets:** the exported model (`model/model_export.json`) and configs.

There is **no authentication, no user accounts, no sessions, no database, no
payment flow, and no secrets.** The model and its predictions are public by
design. Several items on a generic security checklist therefore do not apply
here, and we did not invent systems (e.g. an auth layer) just to secure them.

## Findings

| # | Area | Result |
|---|------|--------|
| 1 | Hardcoded API keys / tokens / passwords in source | **None found** |
| 2 | Cloud key patterns (AWS `AKIA`, Google `AIza`, GitHub `ghp_`, Stripe/OpenAI `sk-`, Slack `xox`, JWTs, PEM private keys) | **None found** |
| 3 | `.env` / credential files committed to Git | **None** |
| 4 | Secrets read from environment (`process.env` / `os.environ`) | **None** — the app has no secrets to manage |
| 5 | Auth routes needing rate limiting (login/signup/etc.) | **None exist** |
| 6 | Sensitive data exposed to the frontend or in Git | **None** — only a public model is shipped |
| 7 | `/api/predict` input validation | **Was missing → fixed** |
| 8 | `/api/predict` payload-size limit | **Was missing → fixed** |
| 9 | `/api/predict` rate limiting | **Was missing → fixed** |
| 10 | Error responses leaking internals | **Was leaking `err.message` → fixed** |

## Hardening applied — `pages/api/predict.js`

1. **Input validation / sanitization.** Every field is whitelisted:
   - `neighbourhood` and `property_type` must exactly match a known category
     from the model (no reflection, so no injection surface).
   - `bedrooms` (0–10), `bathrooms` (1–10), `size_sqft` (100–10 000) are coerced
     to numbers and bounds-checked.
   - The four amenity flags accept only boolean forms.
   - Non-object bodies, arrays, missing fields, wrong types, and out-of-range
     values are rejected with `400` and a specific message. Verified against
     malicious payloads (unknown category, out-of-range, `"DROP TABLE"` as a
     number, array body, missing field) — all correctly rejected.

2. **Payload limits.** `bodyParser: { sizeLimit: '4kb' }` rejects oversized
   bodies before parsing; malformed JSON is rejected by the parser.

3. **Rate limiting.** In-memory sliding-window limiter keyed by client IP:
   **30 requests / 60 s**, returning `429` + `Retry-After` when exceeded.
   > Caveat: this is **per-instance**. On serverless (Vercel), each warm
   > instance keeps its own counter, so the effective global limit scales with
   > the number of instances. For a strict global limit, back the limiter with a
   > shared store (Redis / Upstash). For this app's scale, in-memory is adequate.

4. **No internal leakage.** `500` responses now return generic messages instead
   of `err.message`.

## Streamlit app

`streamlit_app.py` takes input only from `st.selectbox`/`st.slider` widgets,
which constrain values to the model's own categories and to fixed numeric
ranges. There is no free-form input and no HTTP body to sanitize, so no
injection surface exists. No change required.

## Note on `requirements.txt` + Vercel

The repo root contains `requirements.txt` (needed by Streamlit Cloud / Render).
If deploying the Next.js app on Vercel, this can trigger Vercel's Python builder.
Deploy the app on **one** platform (Streamlit/Render **or** Vercel) to avoid the
conflict; `.vercelignore` lists the Python files as a safeguard.

## Residual risk

- **Distributed / high-volume abuse** of `/api/predict` is only partially
  mitigated by the per-instance limiter (see caveat above). Acceptable for a
  public demo; upgrade to a shared-store limiter if traffic grows.
- **No secrets exist today.** If any are introduced later (e.g. a real scraping
  API), they must go in environment variables and never be committed — the
  `.gitignore` already excludes `.env`.
