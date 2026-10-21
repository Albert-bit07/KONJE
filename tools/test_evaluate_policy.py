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


if __name__ == "__main__":
    unittest.main()