"""Content comparison against a release, without modifying user files."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import updater
from test_updater import make_release_zip


class DeltaUpdateTests(unittest.TestCase):
    def test_prefers_complete_release_asset(self):
        url = 'https://github.com/Tokke2/Semesterlista/releases/download/v0.0.35/Semesterlista-alla-OS.zip'
        release = {'tag_name': 'v0.0.35', 'zipball_url': 'source', 'assets': [
            {'name': 'Semesterlista-alla-OS.zip', 'state': 'uploaded', 'browser_download_url': url}]}
        with patch.object(updater, 'fetch_latest_release', return_value=release), \
             patch.object(updater, 'fetch_version_at_tag', return_value='2.26.0'):
            self.assertEqual(updater.check_for_update('2.25.2').zip_url, url)

    def test_hash_comparison_skips_unchanged_even_if_timestamp_differs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / 'app'
            (app / 'core').mkdir(parents=True)
            (app / 'main.pyw').write_text('old')
            unchanged = app / 'core/updater.py'
            unchanged.write_text('# updater\n')
            stamp = unchanged.stat().st_mtime_ns
            release = make_release_zip(root / 'release.zip')
            plan = updater.install_from_zip(release, app, local_version='2.8.1', dry_run=True)
            self.assertIn('core/updater.py', plan.unchanged)
            self.assertIn('main.pyw', plan.changed)
            self.assertIn('config.json', plan.added)
            self.assertEqual((app / 'main.pyw').read_text(), 'old')
            result = updater.install_from_zip(release, app, local_version='2.8.1')
            self.assertEqual(result.unchanged, plan.unchanged)
            self.assertNotIn('core/updater.py', result.files)
            self.assertEqual(stamp, unchanged.stat().st_mtime_ns)

    def test_same_size_different_bytes_are_changed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, app = root / 'source', root / 'app'
            source.mkdir()
            app.mkdir()
            (source / 'file').write_text('abc')
            (app / 'file').write_text('xyz')
            result = updater.compare_payload(source, app, [Path('file')])
            self.assertEqual(result.changed, ['file'])

    def test_failed_backup_aborts_before_any_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / 'app'
            app.mkdir()
            (app / 'main.pyw').write_text('old')
            release = make_release_zip(root / 'release.zip')
            with patch.object(updater, '_make_backup', return_value=None):
                with self.assertRaises(updater.UpdateError):
                    updater.install_from_zip(release, app, local_version='2.8.1')
            self.assertEqual((app / 'main.pyw').read_text(), 'old')
            self.assertFalse((app / 'config.json').exists())

    def test_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, app = root / 'source', root / 'app'
            source.mkdir()
            app.mkdir()
            outside = root / 'outside'
            outside.write_text('keep')
            (source / 'file').write_text('new')
            try:
                (app / 'file').symlink_to(outside)
            except OSError:
                self.skipTest('Symlinks unavailable')
            with self.assertRaises(updater.UpdateError):
                updater.compare_payload(source, app, [Path('file')])
            self.assertEqual(outside.read_text(), 'keep')
