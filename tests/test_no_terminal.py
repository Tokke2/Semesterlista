"""Terminal-free background conversion and native entry-point regression checks."""
import ast
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent


class NoTerminalTests(unittest.TestCase):
    def test_ghostscript_is_started_without_a_console(self):
        # Exercise the real function without requiring optional PDF/Qt packages.
        tree = ast.parse((ROOT / 'core/pdf_assets.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'convert_eps_to_png')
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'test.eps'
            source.write_text('%!PS-Adobe-3.0 EPSF-3.0')
            cached = Path(temporary) / 'cached.png'
            scope = dict(Path=Path, resolve_path=lambda p: Path(p), subprocess=subprocess, CONVERT_DPI=150,
                         AssetError=RuntimeError, find_ghostscript=lambda: 'gswin64c.exe',
                         ghostscript_hint=lambda: '', _logo_cache_path=lambda *a, **k: cached,
                         logger=Mock())
            # Postponed annotations keep this test independent of typing imports.
            exec(compile(ast.Module(body=[ast.parse('from __future__ import annotations').body[0], function], type_ignores=[]),
                 'core/pdf_assets.py', 'exec'), scope)
            def converted(*args, **kwargs):
                cached.write_bytes(b'PNG')
                return subprocess.CompletedProcess(args[0], 0, '', '')
            with patch.object(subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                 patch.object(subprocess, 'run', side_effect=converted) as run:
                scope['convert_eps_to_png'](source)
                self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)
                self.assertTrue(run.call_args.kwargs['capture_output'])

    def test_windows_entry_point_hides_console_before_creation(self):
        source = (ROOT / 'Starta Semesterlista.vbs').read_text()
        self.assertIn('shell.Run(command, 0, True)', source)
        self.assertIn('-WindowStyle Hidden', source)

    def test_swish_has_no_external_scanner_process(self):
        source = (ROOT / 'core/donation_dialog.py').read_text(encoding='utf-8')
        self.assertNotIn('subprocess', source)
        self.assertNotIn('api.qrserver.com', source)
        self.assertIn('assets/donation/swish.png', source)
