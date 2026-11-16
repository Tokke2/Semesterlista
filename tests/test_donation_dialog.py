"""Fixed destinations, read-only UI and bundled resources."""
from pathlib import Path
import unittest
from unittest.mock import patch
from test_settings_dialog import HAVE_QT

ROOT = Path(__file__).resolve().parent.parent


class DonationAssetsTests(unittest.TestCase):
    def test_license_and_qr_bundled(self):
        self.assertTrue((ROOT / 'assets/donation/swish.png').read_bytes().startswith(b'\x89PNG'))
        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertIn('kommersiell', license_text)
        self.assertIn('oförändrade originalpaketet', license_text)
        self.assertIn('Tredjepartskomponenter', license_text)


@unittest.skipUnless(HAVE_QT, 'Qt unavailable')
class DonationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_no_editable_recipient_and_no_automatic_browser(self):
        from core.donation_dialog import DonationDialog
        from PySide6.QtWidgets import QLineEdit
        with patch('core.donation_dialog.QDesktopServices.openUrl') as opened:
            dialog = DonationDialog()
            self.addCleanup(dialog.deleteLater)
            self.assertFalse(dialog.qr.pixmap().isNull())
            self.assertEqual(dialog.findChildren(QLineEdit), [])
            opened.assert_not_called()

    def test_only_fixed_destinations_open(self):
        from core.donation_dialog import DonationDialog, PAYPAL_URL, KOFI_URL
        dialog = DonationDialog()
        self.addCleanup(dialog.deleteLater)
        with patch('core.donation_dialog.QDesktopServices.openUrl', return_value=True) as opened:
            dialog._open_payment('https://example.com/changed')
            opened.assert_not_called()
            for url in (PAYPAL_URL, KOFI_URL):
                dialog._open_payment(url)
                self.assertEqual(opened.call_args.args[0].toString(), url)

    def test_failed_browser_is_reported(self):
        from core.donation_dialog import DonationDialog, PAYPAL_URL
        dialog = DonationDialog()
        self.addCleanup(dialog.deleteLater)
        with patch('core.donation_dialog.QDesktopServices.openUrl', return_value=False), \
             patch('core.donation_dialog.QMessageBox.warning') as warning:
            dialog._open_payment(PAYPAL_URL)
            warning.assert_called_once()
