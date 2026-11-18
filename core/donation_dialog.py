"""Fixed donation destinations; no settings, network requests or payment collection."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from core import i18n
from core.app_icon import app_icon

PAYPAL_URL = "https://paypal.me/Rickard3dPrint"
KOFI_URL = "https://ko-fi.com/tokke2"
SWISH_PAYLOAD = "C0721817177;;Semesterlista;6"
ROOT = Path(__file__).resolve().parent.parent


class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("donation.title"))
        self.setWindowIcon(app_icon())
        self.resize(580, 740)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        page = QWidget()
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        hero = QFrame()
        hero.setObjectName("donationHero")
        hero.setStyleSheet("#donationHero {background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #143958,stop:1 #087e86); border-radius:18px;} #donationHero QLabel {color:white;background:transparent;}")
        header = QVBoxLayout(hero)
        header.setContentsMargins(24, 24, 24, 24)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(64, 64))
        header.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        title = QLabel(i18n.t("donation.title"))
        title.setStyleSheet("font-size:24px;font-weight:700;")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)
        intro = QLabel(i18n.t("donation.intro"))
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(intro)
        layout.addWidget(hero)
        purpose = QFrame()
        purpose.setObjectName("donationPurpose")
        purpose.setStyleSheet("#donationPurpose {border-left:4px solid #159b88; border-radius:8px;}")
        purpose_layout = QVBoxLayout(purpose)
        purpose_layout.setContentsMargins(16, 12, 16, 12)
        purpose_title = QLabel(i18n.t("donation.purpose_title"))
        purpose_title.setWordWrap(True)
        purpose_title.setStyleSheet("font-weight:700;font-size:16px;")
        purpose_layout.addWidget(purpose_title)
        purpose_text = QLabel(i18n.t("donation.purpose"))
        purpose_text.setWordWrap(True)
        purpose_layout.addWidget(purpose_text)
        layout.addWidget(purpose)
        heading = QLabel(i18n.t("donation.swish"))
        heading.setStyleSheet("font-size:19px;font-weight:700;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        self.qr = QLabel()
        self.qr.setObjectName("swishQr")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setAccessibleName(i18n.t("donation.qr_accessible"))
        image = QPixmap(str(ROOT / "assets/donation/swish.png"))
        if image.isNull():
            self.qr.setText(i18n.t("donation.qr_missing"))
        else:
            self.qr.setPixmap(image.scaled(264, 264, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.FastTransformation))
        layout.addWidget(self.qr)
        for key in ("donation.instructions", "donation.voluntary"):
            label = QLabel(i18n.t(key))
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        buttons = QHBoxLayout()
        for key, url, color in (("donation.paypal", PAYPAL_URL, "#0868ac"),
                                ("donation.kofi", KOFI_URL, "#b73748")):
            button = QPushButton(i18n.t(key))
            button.setObjectName(key.replace(".", "_"))
            button.setMinimumHeight(46)
            button.setStyleSheet("QPushButton {background:" + color + ";color:white;border-radius:10px;padding:10px;font-weight:700;} QPushButton:focus {border:3px solid #efb745;}")
            button.clicked.connect(lambda checked=False, target=url: self._open_payment(target))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        privacy = QLabel(i18n.t("donation.privacy"))
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        other = QLabel(i18n.t("donation.other"))
        other.setStyleSheet("font-weight:700;")
        layout.addWidget(other)
        thanks = QLabel(i18n.t("donation.thanks"))
        thanks.setWordWrap(True)
        layout.addWidget(thanks)
        license_button = QPushButton(i18n.t("donation.license"))
        license_button.clicked.connect(self._show_license)
        layout.addWidget(license_button)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        outer.addWidget(close)

    def _open_payment(self, url):
        if url not in (PAYPAL_URL, KOFI_URL):
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, i18n.t("donation.title"), i18n.t("donation.open_failed"))

    def _show_license(self):
        from PySide6.QtWidgets import QPlainTextEdit
        dialog = QDialog(self)
        dialog.setWindowTitle(i18n.t("donation.license"))
        dialog.resize(660, 530)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        try:
            text.setPlainText((ROOT / "LICENSE").read_text(encoding="utf-8"))
        except OSError:
            text.setPlainText(i18n.t("donation.license_missing"))
        layout.addWidget(text)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()
