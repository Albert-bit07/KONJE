"""Dependency-free tests for calibration separation and conservative selection."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_policy import calibrate, bound95


def row(truth, prediction, best, second=-2):
    return {"truth_id": truth, "best_id": prediction,
            "best_similarity": str(best), "second_similarity": str(second)}

class CalibrationTests(unittest.TestCase):
    def test_requires_unknown_negative_cases_in_both_sets(self):
        with self.assertRaises(ValueError):
            calibrate([row("x", "x", .9)], [row("", "x", .1)])
        with self.assertRaises(ValueError):
            calibrate([row("x", "x", .9), row("", "x", .1)], [row("x", "x", .9)])

    def test_no_feasible_policy_fails_closed(self):
        training = [row("a", "a", .5), row("", "a", .9)]
        with self.assertRaises(ValueError):
            calibrate(training, [row("", "a", .2)])

    def test_only_development_data_used_for_threshold(self):
        training = [row("a", "a", .91), row("b", "b", .83), row("", "a", .65)]
        a = calibrate(training, [row("", "a", .6)])
        b = calibrate(training, [row("", "a", .99)])
        self.assertEqual((a["threshold"], a["margin"]), (b["threshold"], b["margin"]))
        self.assertEqual(a["holdout"]["wrong_accepts"], 0)
        self.assertEqual(b["holdout"]["wrong_accepts"], 1)

    def test_wilson_upper_bound_nonzero_even_no_observed_errors(self):
        self.assertIsNone(bound95(0, 0))
        self.assertGreater(bound95(0, 10), 0.0)
        self.assertLessEqual(bound95(10, 10), 1.0)

if __name__ == "__main__":
    unittest.main()