"""
XGBoost model for predicting Toronto rental prices.

Usage:
    python model.py --data data/listings.csv --output models/rent_model.joblib
    python model.py --data data/listings.csv --output models/rent_model.joblib --tune
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from xgboost import XGBRegressor

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

CATEGORICAL_FEATURES = ["neighbourhood", "property_type"]
NUMERIC_FEATURES = [
    "bedrooms", "bathrooms", "size_sqft",
    "has_parking", "has_laundry", "furnished", "pets_allowed",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "price"

DEFAULT_XGB_PARAMS = dict(
    n_estimators=400,
    learning_rate=0.05,
    max_depth=5,
    min_child_weight=3,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=-1,
)


# ── Data loading & preprocessing ──────────────────────────────────────────────

def load_data(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    log.info("Loaded %d rows from %s", len(df), csv_path)
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and type-cast the raw listings DataFrame."""
    df = df.copy()

    # Boolean columns may arrive as strings
    for col in ("has_parking", "has_laundry", "furnished", "pets_allowed"):
        if col in df.columns:
            df[col] = df[col].map(
                {"True": 1, "False": 0, True: 1, False: 0}
            ).fillna(0).astype(int)

    df["bedrooms"] = pd.to_numeric(df["bedrooms"], errors="coerce").fillna(1.0)
    df["bathrooms"] = pd.to_numeric(df["bathrooms"], errors="coerce").fillna(1.0)
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")

    # Impute missing size with per-bedroom median
    if "size_sqft" in df.columns:
        df["size_sqft"] = pd.to_numeric(df["size_sqft"], errors="coerce")
        median_size = df.groupby("bedrooms")["size_sqft"].transform("median")
        df["size_sqft"] = df["size_sqft"].fillna(median_size).fillna(600.0)

    # Drop rows without a target or valid price range
    df = df.dropna(subset=[TARGET])
    df = df[(df[TARGET] >= 500) & (df[TARGET] <= 20_000)]

    log.info("After preprocessing: %d rows", len(df))
    return df


# ── Model pipeline ────────────────────────────────────────────────────────────

def build_pipeline(xgb_params: Optional[dict] = None) -> Pipeline:
    params = {**DEFAULT_XGB_PARAMS, **(xgb_params or {})}

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="passthrough",  # numeric features pass through unchanged
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", XGBRegressor(**params)),
        ]
    )


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    cv: int = 5,
) -> dict:
    kf = KFold(n_splits=cv, shuffle=True, random_state=42)

    neg_mae = cross_val_score(pipeline, X, y, cv=kf, scoring="neg_mean_absolute_error")
    neg_rmse = cross_val_score(pipeline, X, y, cv=kf, scoring="neg_root_mean_squared_error")
    r2 = cross_val_score(pipeline, X, y, cv=kf, scoring="r2")

    results = {
        "mae_mean": -neg_mae.mean(),
        "mae_std": neg_mae.std(),
        "rmse_mean": -neg_rmse.mean(),
        "rmse_std": neg_rmse.std(),
        "r2_mean": r2.mean(),
        "r2_std": r2.std(),
    }

    log.info(
        "CV (%d-fold)  MAE=%.0f±%.0f  RMSE=%.0f±%.0f  R²=%.3f±%.3f",
        cv,
        results["mae_mean"], results["mae_std"],
        results["rmse_mean"], results["rmse_std"],
        results["r2_mean"], results["r2_std"],
    )
    return results


# ── Hyperparameter tuning (simple grid) ──────────────────────────────────────

def tune(X: pd.DataFrame, y: pd.Series) -> dict:
    """Brute-force grid search over key XGBoost hyperparameters."""
    from itertools import product

    log.info("Running hyperparameter grid search …")
    grid = {
        "n_estimators": [200, 400],
        "max_depth": [4, 5, 6],
        "learning_rate": [0.05, 0.10],
        "subsample": [0.8, 1.0],
    }
    keys = list(grid.keys())
    combos = list(product(*grid.values()))
    log.info("Evaluating %d parameter combinations …", len(combos))

    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    best_mae = float("inf")
    best_params = {}

    for vals in combos:
        params = dict(zip(keys, vals))
        pipe = build_pipeline(params)
        scores = cross_val_score(pipe, X, y, cv=kf, scoring="neg_mean_absolute_error")
        mae = -scores.mean()
        log.info("  %s  →  MAE=%.0f", params, mae)
        if mae < best_mae:
            best_mae = mae
            best_params = params

    log.info("Best params: %s  (MAE=%.0f)", best_params, best_mae)
    return best_params


# ── Plots ─────────────────────────────────────────────────────────────────────

def plot_feature_importance(pipeline: Pipeline, out_dir: str | Path = "plots") -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model: XGBRegressor = pipeline.named_steps["model"]
    # Column order after ColumnTransformer: categoricals first, then remainder
    col_order = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    importances = model.feature_importances_

    fig, ax = plt.subplots(figsize=(8, 5))
    sorted_idx = np.argsort(importances)
    ax.barh(
        [col_order[i] for i in sorted_idx],
        importances[sorted_idx],
        color=sns.color_palette("Blues_d", len(importances)),
    )
    ax.set_xlabel("XGBoost feature importance (gain)")
    ax.set_title("Toronto Rental Price — Feature Importances")
    plt.tight_layout()
    out = out_dir / "feature_importance.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Saved feature importance plot → %s", out)


def plot_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    out_dir: str | Path = "plots",
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Actual vs Predicted
    ax = axes[0]
    ax.scatter(y_true, y_pred, alpha=0.35, s=15, color="steelblue")
    lo, hi = min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())
    ax.plot([lo, hi], [lo, hi], "r--", lw=1.5)
    ax.set_xlabel("Actual rent (CAD/month)")
    ax.set_ylabel("Predicted rent (CAD/month)")
    ax.set_title("Actual vs Predicted")

    # Residuals
    ax = axes[1]
    residuals = y_pred - y_true
    ax.scatter(y_pred, residuals, alpha=0.35, s=15, color="steelblue")
    ax.axhline(0, color="r", lw=1.5, linestyle="--")
    ax.set_xlabel("Predicted rent (CAD/month)")
    ax.set_ylabel("Residual (predicted − actual)")
    ax.set_title("Residual Plot")

    plt.tight_layout()
    out = out_dir / "predictions.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("Saved prediction plot → %s", out)


# ── Train & save ─────────────────────────────────────────────────────────────

def train(
    csv_path: str | Path,
    model_path: str | Path,
    do_tune: bool = False,
    plot_dir: str | Path = "plots",
) -> dict:
    df = preprocess(load_data(csv_path))

    # Guard against missing columns
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in data: {missing}")

    X = df[FEATURES]
    y = df[TARGET]

    xgb_params: dict = {}
    if do_tune:
        xgb_params = tune(X, y)

    pipeline = build_pipeline(xgb_params)

    # Cross-validation metrics
    cv_results = evaluate(pipeline, X, y)

    # Fit on full dataset before saving
    pipeline.fit(X, y)

    # In-sample stats for the plots
    y_pred = pipeline.predict(X)
    plot_feature_importance(pipeline, out_dir=plot_dir)
    plot_predictions(y.to_numpy(), y_pred, out_dir=plot_dir)

    in_sample = {
        "train_mae": mean_absolute_error(y, y_pred),
        "train_rmse": mean_squared_error(y, y_pred) ** 0.5,
        "train_r2": r2_score(y, y_pred),
    }
    log.info(
        "In-sample  MAE=%.0f  RMSE=%.0f  R²=%.3f",
        in_sample["train_mae"],
        in_sample["train_rmse"],
        in_sample["train_r2"],
    )

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    log.info("Model saved → %s", model_path)

    return {**cv_results, **in_sample}


# ── Prediction helper ─────────────────────────────────────────────────────────

def load_model(model_path: str | Path) -> Pipeline:
    return joblib.load(model_path)


def predict(
    model_path: str | Path,
    bedrooms: float,
    bathrooms: float,
    size_sqft: float,
    neighbourhood: str,
    property_type: str,
    has_parking: bool = False,
    has_laundry: bool = False,
    furnished: bool = False,
    pets_allowed: bool = False,
) -> float:
    pipeline = load_model(model_path)
    row = pd.DataFrame([{
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "size_sqft": size_sqft,
        "has_parking": int(has_parking),
        "has_laundry": int(has_laundry),
        "furnished": int(furnished),
        "pets_allowed": int(pets_allowed),
        "neighbourhood": neighbourhood,
        "property_type": property_type,
    }])
    return float(pipeline.predict(row[FEATURES])[0])


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train the XGBoost rent predictor.")
    p.add_argument("--data", default="data/listings.csv", help="Input CSV.")
    p.add_argument(
        "--output", default="models/rent_model.joblib", help="Where to save the model."
    )
    p.add_argument(
        "--tune", action="store_true", help="Run hyperparameter grid search."
    )
    p.add_argument(
        "--plots", default="plots", help="Directory for output plots."
    )
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    train(
        csv_path=args.data,
        model_path=args.output,
        do_tune=args.tune,
        plot_dir=args.plots,
    )


if __name__ == "__main__":
    main()
