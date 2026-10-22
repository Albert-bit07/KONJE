#!/usr/bin/env python3
"""Calibrate a candidate cosine policy on de-identified development scores.

Requires an independent holdout CSV. This tool NEVER automatically enables
recognition or claims clinical/biometric safety based on small samples.
"""
import argparse
import csv
import json
import math
import os
from pathlib import Path

from evaluate_policy import evaluate


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expected = {"truth_id", "best_id", "best_similarity", "second_similarity"}
        if not reader.fieldnames or set(reader.fieldnames) != expected:
            raise ValueError("CSV columns must be truth_id,best_id,best_similarity,second_similarity")
        rows = list(reader)
    if not rows:
        raise ValueError("Evaluation CSV must not be empty")
    return rows


def bound95(errors, trials):
    """Wilson 95% upper bound (independent binomial assumption, not guaranteed)."""
    if trials == 0:
        return None
    z = 1.96
    p = errors / trials
    divisor = 1 + z*z/trials
    center = p + z*z/(2*trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z*z/(4*trials*trials))
    return round(min(1.0, (center + spread)/divisor), 6)


def calibrate(development, holdout, maximum_wrong_accepts=0, model_id="unverified-model"):
    if maximum_wrong_accepts < 0:
        raise ValueError("maximum_wrong_accepts must be nonnegative")
    if not any(row["truth_id"].strip() for row in development):
        raise ValueError("Development data has no consenting known-person rows")
    if not any(not row["truth_id"].strip() for row in development):
        raise ValueError("Development data has no unknown-person rows")
    if not any(not row["truth_id"].strip() for row in holdout):
        raise ValueError("Holdout data has no unknown-person rows")
    # No fitting or score normalization on holdout. Test is evaluated once.
    eligible = []
    for n in range(0, 101):
        threshold = round(n / 100, 2)
        for m in range(0, 51):
            margin = round(m / 100, 2)
            counts = evaluate(development, threshold, margin)
            if (counts["wrong_accepts"] <= maximum_wrong_accepts and
                    counts["correct_accepts"] > 0):
                eligible.append((counts["correct_accepts"], threshold, margin, counts))
    if not eligible:
        raise ValueError("No candidate meets wrong-accept constraint while recognizing a known sample")
    # Maximize correct development accepts; break ties toward more conservative settings.
    correct, threshold, margin, development_counts = max(eligible, key=lambda row: row[:3])
    holdout_counts = evaluate(holdout, threshold, margin)
    unknowns = sum(not row["truth_id"].strip() for row in holdout)
    return {
        "status": "EXPERIMENTAL_REQUIRES_INDEPENDENT_REVIEW",
        "model_id": model_id,
        "threshold": threshold,
        "margin": margin,
        "development": development_counts,
        "holdout": holdout_counts,
        "holdout_wrong_accept_rate_upper_bound_95": bound95(holdout_counts["wrong_accepts"], len(holdout)),
        "holdout_unknown_count": unknowns,
        "note": "Requires multiple consented identities, diverse lighting, unknown bystanders, independent sessions and manual safety approval before any announcements",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("development_csv", type=Path)
    parser.add_argument("independent_holdout_csv", type=Path)
    parser.add_argument("--max-wrong-accepts", type=int, default=0)
    parser.add_argument("--model-id", required=True, help="exact embedding model identity used to generate scores")
    parser.add_argument("--out", type=Path, help="write a private NEW JSON report")
    args = parser.parse_args(argv)
    try:
        report = calibrate(load_csv(args.development_csv), load_csv(args.independent_holdout_csv), args.max_wrong_accepts, args.model_id)
        value = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.out:
            with os.fdopen(os.open(args.out, os.O_CREAT | os.O_WRONLY | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as out:
                out.write(value)
        else:
            print(value, end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Calibration unavailable: {error}\n")

if __name__ == "__main__":
    main()