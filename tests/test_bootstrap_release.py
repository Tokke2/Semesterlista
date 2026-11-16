"""No Python offer when installed; no changes on refusal; one complete release ZIP."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from tools import build_release

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = (ROOT / 'tools/start_posix.sh').read_text(encoding='utf-8')


@unittest.skipIf(os.name == 'nt', 'POSIX shell required')
class PosixBootstrapTests(unittest.TestCase):
    def run_case(self, functions):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'app å & with spaces'
            root.mkdir()
            result = subprocess.run(['/bin/sh', '-c', PAYLOAD + '\n' + functions + '\nmain',
                                     'starter', str(root)],
                                    env=dict(os.environ, SEMESTERLISTA_BOOTSTRAP_TEST='functions'),
                                    capture_output=True, text=True, timeout=15)
            events = (root / 'events').read_text() if (root / 'events').exists() else ''
            return result, events

    def test_existing_python_never_prompts_or_installs(self):
        result, events = self.run_case('''
find_python() { PYTHON=/usr/bin/true; SEEN=1; return 0; }
install_missing_python() { echo forbidden >> "$ROOT/events"; return 99; }
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, '')

    def test_broken_or_old_python_never_prompts_or_installs(self):
        result, events = self.run_case('''
find_python() { SEEN=1; return 1; }
fail() { echo error >> "$ROOT/events"; }
install_missing_python() { echo forbidden >> "$ROOT/events"; return 99; }
''')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(events, 'error\n')

    def test_declined_offer_exits_without_an_installation_retry(self):
        result, events = self.run_case('''
find_python() { SEEN=0; echo discovery >> "$ROOT/events"; return 1; }
install_missing_python() { echo declined >> "$ROOT/events"; return 2; }
''')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(events, 'discovery\ndeclined\n')

    def test_successful_install_is_rediscovered_then_app_starts(self):
        result, events = self.run_case('''
COUNT=0
find_python() { COUNT=$((COUNT + 1)); SEEN=0; if [ "$COUNT" -eq 1 ]; then return 1; fi; PYTHON=/usr/bin/true; return 0; }
install_missing_python() { echo approved_install >> "$ROOT/events"; return 0; }
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, 'approved_install\n')

    def test_shell_launcher_handles_crlf_and_special_paths_without_python(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "å & $ ' path"
            (root / 'tools').mkdir(parents=True)
            (root / 'tools/start_posix.sh').write_bytes(b'printf done > "$1/started"\r\n')
            subprocess.run(['/bin/sh', '-c', build_release.SHELL_CODE, 'starter', str(root)],
                           check=True, timeout=15)
            self.assertEqual((root / 'started').read_text(), 'done')

    @unittest.skipUnless(shutil.which('gio'), 'native desktop launcher unavailable')
    def test_native_linux_desktop_launcher(self):
        if sys.platform != 'linux':
            self.skipTest('Linux desktop required')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'app å with spaces'
            (root / 'tools').mkdir(parents=True)
            (root / 'tools/start_posix.sh').write_bytes(b'printf done > "$1/started"\r\n')
            desktop = root / build_release.LINUX_DESKTOP
            desktop.write_text(build_release.linux_launcher(), encoding='utf-8', newline='\r\n')
            # gio launch is asynchronous. Fake payload emits no GUI and modifies only tmp.
            subprocess.run(['gio', 'launch', str(desktop)], check=True, capture_output=True, timeout=15)
            import time
            deadline = time.monotonic() + 5
            while not (root / 'started').exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual((root / 'started').read_text(), 'done')


class ReleasePackagingTests(unittest.TestCase):
    def test_sources_have_no_standalone_python_installer(self):
        self.assertFalse(list(ROOT.glob('Installera senaste Python.*')))
        self.assertFalse((ROOT / 'Starta Semesterlista.cmd').exists())
        self.assertNotIn('python3', build_release.macos_source())
        self.assertIn('%k', build_release.linux_launcher())
        self.assertIn('Terminal=false', build_release.linux_launcher())

    @unittest.skipUnless(sys.platform == 'darwin', 'native macOS compilation required')
    def test_complete_archive_has_one_launcher_per_os_and_print_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'Semesterlista-alla-OS.zip'
            build_release.build(output)
            build_release.verify_archive(output)
            with zipfile.ZipFile(output) as archive:
                self.assertGreater(archive.getinfo('Semesterlista/' + build_release.MAC_APP + '/Contents/MacOS/applet').external_attr >> 16 & 0o111, 0)
                self.assertIn(b'--default-cancel', archive.read('Semesterlista/tools/start_posix.sh'))
