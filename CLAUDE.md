# CLAUDE.md

## Persistent Memory System

At the **start of every session**, read all four memory files before doing anything else:

```
memory/decisions.md   — past technical decisions
memory/people.md      — people and their roles
memory/preferences.md — coding/workflow preferences to apply
memory/user.md        — background context about the user
```

Use the contents to personalise responses, honour stated preferences, and avoid
re-litigating settled decisions.

At the **end of every session** (or whenever something noteworthy happens), update
the relevant file(s):

- `decisions.md` — record any significant technical or architectural decision made
  today, with the date and a one-line rationale.
- `people.md` — add or update anyone newly mentioned (name, role, context).
- `preferences.md` — capture any new preference the user expressed (style, tools,
  workflow).
- `user.md` — update background facts about the user that should carry forward.

Keep entries concise. Append; do not delete history unless the user asks you to.

## Project Overview

This repo contains a Toronto rental market predictor that scrapes Kijiji listings
and uses XGBoost to forecast prices. Key files:

- `scraper.py` — Kijiji scraping logic
- `model.py` — XGBoost model definition and training
- `main.py` — entry point
- `data/` — scraped and processed datasets
