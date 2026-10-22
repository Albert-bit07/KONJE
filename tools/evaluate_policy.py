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
    """Mirror the C++ score/margin decision; never accept an empty person ID.

    -2 is the C++ sentinel for no candidate/no runner-up, not a cosine score.
    Wrong accepts include known-person misidentification and accepted strangers.
    """
    if not (-1.0 <= threshold <= 1.0 and 0.0 <= margin <= 2.0):
        raise ValueError("invalid threshold or margin")
    tp = fp = fn = tn = 0
    evaluated = 0
    for row in rows:
        evaluated += 1
        score = float(row["best_similarity"])
        second = float(row["second_similarity"])
        truth_id = row["truth_id"].strip()
        best_id = row["best_id"].strip()
        if not all(map(math.isfinite, (score, second))):
            raise ValueError("nonfinite similarity")
        if not ((-1.0 <= score <= 1.0) or (score == -2.0 and not best_id)):
            raise ValueError("invalid best similarity")
        if second != -2.0 and not (-1.0 <= second <= 1.0):
            raise ValueError("invalid runner-up similarity")
        accepted = (bool(best_id) and score >= threshold
                    and (second == -2.0 or score - second >= margin))
        if accepted and truth_id and best_id == truth_id:
            tp += 1
        elif accepted:
            fp += 1
        elif truth_id:
            fn += 1
        else:
            tn += 1
    return dict(correct_accepts=tp, wrong_accepts=fp, known_abstentions=fn,
                unknown_abstentions=tn, evaluated=evaluated)


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