import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.qq_conversation import _dump_parse_failure


class SnapshotTests(unittest.TestCase):
    def test_snapshot_is_local_bounded_and_retention_limited(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.data_paths.runtime_root', return_value=Path(folder)):
            for i in range(22):
                _dump_parse_failure(f'{i:010x}', 'test '*20000, 'first error')
            files = list((Path(folder)/'qq-parse-fail').glob('*.txt'))
            self.assertEqual(len(files), 20)
            self.assertTrue(all(p.stat().st_size < 68000 for p in files))
            self.assertIn('first_error: first error', files[-1].read_text())
            _dump_parse_failure('../escape', 'raw', 'error')
            self.assertFalse((Path(folder)/'escape.txt').exists())
