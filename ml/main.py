"""
Toronto Rental Market Predictor — CLI entry point.

Commands
--------
scrape      Scrape Kijiji (or generate synthetic data with --sample).
train       Train the XGBoost model on a CSV dataset.
predict     Predict monthly rent for a given set of listing attributes.

Examples
--------
# Generate synthetic data, train, then predict
python main.py scrape --sample --output data/listings.csv
python main.py train  --data data/listings.csv --output models/rent_model.joblib
python main.py predict --model models/rent_model.joblib \\
    --bedrooms 2 --bathrooms 1 --size 750 \\
    --neighbourhood "Liberty Village" --type Condo --parking

# Scrape real Kijiji listings (5 pages) then train
python main.py scrape --pages 5 --output data/listings.csv
python main.py train  --data data/listings.csv --tune
"""

import argparse
import sys


def _scrape(args):
    from scraper import KijijiScraper, generate_sample_data, save_listings

    if args.sample:
        listings = generate_sample_data(n=args.sample_n)
    else:
        scraper = KijijiScraper()
        listings = scraper.scrape(pages=args.pages)
        if not listings:
            print(
                "ERROR: No listings scraped. "
                "Try --sample to use synthetic data.",
                file=sys.stderr,
            )
            sys.exit(1)

    save_listings(listings, args.output)
    print(f"Saved {len(listings)} listings → {args.output}")


def _train(args):
    from model import train

    results = train(
        csv_path=args.data,
        model_path=args.output,
        do_tune=args.tune,
        plot_dir=args.plots,
    )
    print("\n=== Training Results ===")
    print(f"  CV  MAE  : ${results['mae_mean']:,.0f} ± ${results['mae_std']:,.0f}")
    print(f"  CV  RMSE : ${results['rmse_mean']:,.0f} ± ${results['rmse_std']:,.0f}")
    print(f"  CV  R²   : {results['r2_mean']:.3f} ± {results['r2_std']:.3f}")
    print(f"\n  Train MAE  : ${results['train_mae']:,.0f}")
    print(f"  Train RMSE : ${results['train_rmse']:,.0f}")
    print(f"  Train R²   : {results['train_r2']:.3f}")
    print(f"\nModel saved → {args.output}")
    print(f"Plots saved → {args.plots}/")


def _predict(args):
    from model import predict

    rent = predict(
        model_path=args.model,
        bedrooms=args.bedrooms,
        bathrooms=args.bathrooms,
        size_sqft=args.size,
        neighbourhood=args.neighbourhood,
        property_type=args.type,
        has_parking=args.parking,
        has_laundry=args.laundry,
        furnished=args.furnished,
        pets_allowed=args.pets,
    )
    print(f"\nPredicted monthly rent: ${rent:,.0f} CAD")
    print()
    print("  Input summary:")
    print(f"    Neighbourhood : {args.neighbourhood}")
    print(f"    Type          : {args.type}")
    print(f"    Bedrooms      : {args.bedrooms}")
    print(f"    Bathrooms     : {args.bathrooms}")
    print(f"    Size          : {args.size} sqft")
    print(f"    Parking       : {'yes' if args.parking else 'no'}")
    print(f"    In-unit laundry: {'yes' if args.laundry else 'no'}")
    print(f"    Furnished     : {'yes' if args.furnished else 'no'}")
    print(f"    Pets allowed  : {'yes' if args.pets else 'no'}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toronto-rental",
        description="Toronto rental market predictor (Kijiji + XGBoost).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── scrape ────────────────────────────────────────────────────────────
    sp = sub.add_parser("scrape", help="Scrape or generate rental listings.")
    sp.add_argument("--pages", type=int, default=5,
                    help="Kijiji pages to scrape (default: 5).")
    sp.add_argument("--output", default="data/listings.csv",
                    help="Output CSV path.")
    sp.add_argument("--sample", action="store_true",
                    help="Generate synthetic data instead of hitting Kijiji.")
    sp.add_argument("--sample-n", type=int, default=500,
                    help="Number of synthetic listings (default: 500).")
    sp.set_defaults(func=_scrape)

    # ── train ─────────────────────────────────────────────────────────────
    tp = sub.add_parser("train", help="Train the XGBoost model.")
    tp.add_argument("--data", default="data/listings.csv", help="Input CSV.")
    tp.add_argument("--output", default="models/rent_model.joblib",
                    help="Model output path.")
    tp.add_argument("--tune", action="store_true",
                    help="Run hyperparameter grid search.")
    tp.add_argument("--plots", default="plots",
                    help="Directory for output plots.")
    tp.set_defaults(func=_train)

    # ── predict ───────────────────────────────────────────────────────────
    pp = sub.add_parser("predict", help="Predict rent for a listing.")
    pp.add_argument("--model", default="models/rent_model.joblib",
                    help="Trained model path.")
    pp.add_argument("--bedrooms", type=float, required=True)
    pp.add_argument("--bathrooms", type=float, default=1.0)
    pp.add_argument("--size", type=float, required=True,
                    help="Size in square feet.")
    pp.add_argument("--neighbourhood", required=True,
                    help='e.g. "Liberty Village", "Annex", "Scarborough"')
    pp.add_argument("--type", default="Apartment",
                    choices=[
                        "Apartment", "Condo", "Basement Apartment",
                        "House", "Townhouse", "Bachelor/Studio", "Semi-Detached",
                    ])
    pp.add_argument("--parking", action="store_true", help="Includes parking.")
    pp.add_argument("--laundry", action="store_true", help="In-unit laundry.")
    pp.add_argument("--furnished", action="store_true")
    pp.add_argument("--pets", action="store_true", help="Pets allowed.")
    pp.set_defaults(func=_predict)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
