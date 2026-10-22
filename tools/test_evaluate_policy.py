import unittest
from evaluate_policy import evaluate


class PolicyEvaluationTests(unittest.TestCase):
    def test_mixed(self):
        rows = [
            {"truth_id": "p1", "best_id": "p1", "best_similarity": ".9", "second_similarity": ".2"},
            {"truth_id": "", "best_id": "p1", "best_similarity": ".4", "second_similarity": ".2"},
            {"truth_id": "", "best_id": "p1", "best_similarity": ".8", "second_similarity": ".1"},
            {"truth_id": "p2", "best_id": "p1", "best_similarity": ".59", "second_similarity": ".1"},
        ]
        self.assertEqual(evaluate(rows, .6, .1), dict(correct_accepts=1, wrong_accepts=1,
                    known_abstentions=1, unknown_abstentions=1, evaluated=4))


    def test_no_identity_is_never_a_positive_match(self):
        rows = [
            {"truth_id": "", "best_id": "", "best_similarity": ".99", "second_similarity": "-2"},
            {"truth_id": "person_a", "best_id": "", "best_similarity": ".95", "second_similarity": "-2"},
            {"truth_id": "", "best_id": "", "best_similarity": "-2", "second_similarity": "-2"},
        ]
        result = evaluate(rows, .6, .1)
        self.assertEqual(result["wrong_accepts"], 0)
        self.assertEqual(result["known_abstentions"], 1)
        self.assertEqual(result["unknown_abstentions"], 2)

    def test_near_tie_abstains_but_missing_runner_up_is_allowed(self):
        near = [{"truth_id": "p1", "best_id": "p1",
                 "best_similarity": ".8", "second_similarity": ".75"}]
        no_runner_up = [{"truth_id": "p1", "best_id": "p1",
                         "best_similarity": ".8", "second_similarity": "-2"}]
        self.assertEqual(evaluate(near, .6, .1)["known_abstentions"], 1)
        self.assertEqual(evaluate(no_runner_up, .6, .1)["correct_accepts"], 1)

    def test_invalid_scores_and_policies_fail_closed(self):
        row = {"truth_id": "p1", "best_id": "p1",
               "best_similarity": ".8", "second_similarity": ".3"}
        invalid_rows = [
            dict(row, best_similarity="1.1"),
            dict(row, second_similarity="-1.8"),
            dict(row, second_similarity="nan"),
        ]
        for invalid in invalid_rows:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate([invalid], .6, .1)
        for threshold, margin in [(float("nan"), .1), (.6, -1), (1.1, .1)]:
            with self.subTest(threshold=threshold, margin=margin), self.assertRaises(ValueError):
                evaluate([row], threshold, margin)


if __name__ == "__main__":
    unittest.main()