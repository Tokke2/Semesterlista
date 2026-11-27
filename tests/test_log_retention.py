import tempfile
import unittest
from datetime import date
from pathlib import Path
from core.logging_setup import prune_archived_logs


class RetentionTests(unittest.TestCase):
    def test_seven_day_boundary_and_protected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'arkiv'
            archive.mkdir()
            for name in ('app-2026-10-26.log', 'app-2026-10-27.log',
                         'fel-2026-10-01.log', 'app-invalid.log', 'other-2026-10-01.log'):
                (archive / name).write_text('keep unless expired app archive')
            (root / 'fel.log').write_text('active error')
            self.assertEqual(prune_archived_logs(root / 'app.log', date(2026, 11, 2)), 1)
            self.assertFalse((archive / 'app-2026-10-26.log').exists())
            self.assertEqual(len(list(archive.iterdir())), 4)
            self.assertTrue((root / 'fel.log').exists())
            self.assertEqual(prune_archived_logs(root / 'fel.log', date(2026, 11, 2)), 0)
            self.assertEqual(prune_archived_logs(root / 'app.log', date(2026, 11, 2)), 0)
