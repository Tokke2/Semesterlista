"""Real IPC regression: second launches activate, never become a second owner."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QProcess
from core.single_instance import SingleInstanceLock


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.name = 'Semesterlista-test-' + uuid.uuid4().hex

    def drain(self):
        loop = QEventLoop()
        QTimer.singleShot(150, loop.quit)
        loop.exec()

    def child(self, fallback=False):
        code = '''import sys
from PySide6.QtCore import QCoreApplication
from core import single_instance as module
app = QCoreApplication([])
if sys.argv[2] == 'True': module._HAS_SHARED_MEMORY = False
lock = module.SingleInstanceLock(sys.argv[1])
secondary = lock.is_running()
sent = lock.send_to_existing() if secondary else False
lock.release()
sys.exit(0 if secondary and sent else 2)
'''
        # Windows named-pipe handshakes require the primary Qt event loop to
        # run while the secondary connects. Blocking subprocess.run would
        # deadlock the test rather than model an already-running application.
        process = QProcess()
        process.setWorkingDirectory(str(Path(__file__).resolve().parent.parent))
        loop = QEventLoop()
        process.finished.connect(lambda *_: loop.quit())
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(20000)
        process.start(sys.executable, ['-c', code, self.name, str(fallback)])
        loop.exec()
        timer.stop()
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(5000)
            self.fail('Secondary process did not finish')
        self.assertEqual(process.exitCode(), 0, bytes(process.readAllStandardError()).decode(errors='replace'))

    def test_multiple_launches_signal_same_owner_and_keep_lock_file(self):
        primary = SingleInstanceLock(self.name)
        self.addCleanup(primary.release)
        self.assertFalse(primary.is_running())
        calls = []
        primary.set_activation_handler(lambda: calls.append(True))
        for _ in range(3):
            self.child()
            self.drain()
            self.assertTrue(primary._lock_file.exists())
            self.assertEqual(primary._lock_file.read_text(), str(os.getpid()))
        self.assertEqual(len(calls), 3)

    def test_signal_during_startup_is_delivered_after_window_is_ready(self):
        primary = SingleInstanceLock(self.name)
        self.addCleanup(primary.release)
        self.child()
        self.drain()
        self.assertTrue(primary._pending_show)
        calls = []
        primary.set_activation_handler(lambda: calls.append(True))
        self.drain()
        self.assertEqual(calls, [True])

    def test_new_owner_after_release(self):
        first = SingleInstanceLock(self.name)
        first.release()
        second = SingleInstanceLock(self.name)
        self.addCleanup(second.release)
        self.assertFalse(second.is_running())

    def test_socket_fallback_is_exclusive_and_activates(self):
        with patch('core.single_instance._HAS_SHARED_MEMORY', False):
            primary = SingleInstanceLock(self.name)
        self.addCleanup(primary.release)
        calls = []
        primary.set_activation_handler(lambda: calls.append(True))
        self.child(fallback=True)
        self.drain()
        self.assertEqual(calls, [True])
        import socket
        with socket.create_connection(('127.0.0.1', primary._socket_port), timeout=1) as client:
            client.sendall(b'show')
        self.drain()
        self.assertEqual(calls, [True, True])

    def test_pid_probe_does_not_terminate_process(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            self.assertTrue(SingleInstanceLock._is_pid_alive(child.pid))
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=10)

    def test_minimized_window_activation_restores_visibility(self):
        # Execute the actual main-window method without importing the app entry point.
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        from PySide6.QtCore import Qt
        source = (Path(__file__).resolve().parent.parent / 'main.pyw').read_text(encoding='utf-8')
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'show_application')
        tree = ast.Module(body=[method], type_ignores=[])
        scope = {'Qt': Qt, 'sys': SimpleNamespace(platform='linux')}
        exec(compile(tree, 'main.pyw', 'exec'), scope)
        window = Mock()
        window.windowState.return_value = Qt.WindowState.WindowMinimized | Qt.WindowState.WindowMaximized
        scope['show_application'](window)
        window.setWindowState.assert_called_once_with(Qt.WindowState.WindowMaximized)
        window.show.assert_called_once()
        window.activateWindow.assert_called_once()
