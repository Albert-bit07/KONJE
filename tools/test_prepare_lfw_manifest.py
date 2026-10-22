import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prepare_lfw_manifest import select_people, write_manifest
from benchmark_faces import load_manifest

class LFWManifestTests(unittest.TestCase):
    def test_distinct_identity_splits_and_anonymization(self):
        with tempfile.TemporaryDirectory() as dirname:
            root=Path(dirname); src=root/'lfw_funneled'; src.mkdir()
            for ident in range(9):
                folder=src/f'Celebrity_Name_{ident:02d}'; folder.mkdir()
                for n in range(7 if ident < 4 else 2):
                    (folder/f'photo_{n:02d}.jpg').write_bytes(b'example')
            rows=select_people(src,known=3,unknown_per_split=2)
            self.assertEqual(rows,select_people(src,known=3,unknown_per_split=2))
            original_iterdir = Path.iterdir
            def reversed_iterdir(path):
                items = list(original_iterdir(path))
                if path == src:
                    items.reverse()
                return iter(items)
            with patch.object(Path, "iterdir", reversed_iterdir):
                self.assertEqual(rows,select_people(src,known=3,unknown_per_split=2))
            manifest=root/'private'/'manifest.csv'
            write_manifest(rows,manifest)
            parsed=load_manifest(manifest)
            self.assertEqual(sum(row['role']=='enroll' for row in parsed),9)
            self.assertEqual(len(parsed),3*7+2*2)
            self.assertFalse(any('Celebrity_Name_' in row['identity'] for row in parsed))
            self.assertEqual(os.stat(manifest).st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):
                write_manifest(rows,manifest)

if __name__=='__main__':
    unittest.main()