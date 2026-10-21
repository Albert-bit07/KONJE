#!/usr/bin/env python3
"""Evaluate candidate matching thresholds from volunteer-authorized, DE-IDENTIFIED scores.

No face images or embeddings required. Input CSV columns:
truth_id,best_id,best_similarity,second_similarity
Unknown people have an empty truth_id. Scores are cosine similarities,
NOT probabilities. This is an evaluation aid, not an accuracy guarantee.
"""
import argparse
import csv
import math


def evaluate(rows, threshold: float, margin: float):
    tp = fp = fn = tn = 0
    for row in rows:
        score = float(row["best_similarity"])
        second = float(row["second_similarity"])
        if not all(map(math.isfinite, (score, second))):
            raise ValueError("nonfinite similarity")
        accepted = score >= threshold and score - second >= margin
        correct = accepted and row["truth_id"] and row["best_id"] == row["truth_id"]
        if correct:
            tp += 1
        elif accepted:
            fp += 1
        elif row["truth_id"]:
            fn += 1
        else:
            tn += 1
    return dict(correct_accepts=tp, wrong_accepts=fp, known_abstentions=fn,
                unknown_abstentions=tn, evaluated=len(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Authorized de-identified CSV, keep outside Git")
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument("--margin", type=float, default=0.10)
    args = parser.parse_args()
    with open(args.csv, newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    print(evaluate(rows, args.threshold, args.margin))


if __name__ == "__main__":
    main()