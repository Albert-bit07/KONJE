"""Offline benchmark logic tests; no model dependency or real face images."""
import csv
import tempfile
from pathlib import Path
import unittest
from benchmark_faces import load_manifest, measure, summarize, cosine, BLUR_SIGMAS


class BenchmarkTests(unittest.TestCase):
    def fixture(self, root):
        names = [
            ('a1', 'person-a', 'enroll'), ('b1','person-b','enroll'),
            ('a2','person-a','dev_known'), ('b2','person-b','dev_known'),
            ('u1','unknown-1','dev_unknown'), ('a3','person-a','holdout_known'),
            ('b3','person-b','holdout_known'), ('u2','unknown-2','holdout_unknown')]
        csvpath = root / 'manifest.csv'
        with csvpath.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(('path','identity','role','pose'))
            for name, identity, role in names:
                (root / (name + '.jpg')).write_bytes(b'JPEGplaceholder')
                writer.writerow((name+'.jpg', identity, role, 'frontal'))
        return csvpath

    def test_splits_and_corrupt_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.fixture(root)
            self.assertEqual(len(load_manifest(manifest)), 8)
            with manifest.open('a') as out:
                out.write('a1.jpg,person-a,dev_known,frontal\n')
            with self.assertRaisesRegex(ValueError, 'multiple splits'):
                load_manifest(manifest)

    def test_development_only_tuning_and_blur_grouping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = load_manifest(self.fixture(root))
            def extract(path, blur):
                if path.name.startswith('a'):
                    return [1.0, 0.0]
                if path.name.startswith('b'):
                    return [0.0, 1.0]
                return [0.7,0.7]
            results,timing = measure(rows,extract)
            report = summarize(results,timing)
            self.assertEqual(report['gallery']['enrolled_identities'],2)
            self.assertEqual(report['development_rows'], len(BLUR_SIGMAS)*3)
            self.assertIn('3.0', report['holdout'])
            self.assertEqual(report['holdout']['0.0']['wrong_accepts'],0)
            self.assertIsNotNone(report['policy'])
            self.assertNotIn('person-a', str(report))

    def test_invalid_vectors_reject(self):
        self.assertEqual(cosine([1.0,0.0],[0.0]),-2.0)
        self.assertEqual(cosine([float('nan')],[1.0]),-2.0)

if __name__ == '__main__':
    unittest.main()