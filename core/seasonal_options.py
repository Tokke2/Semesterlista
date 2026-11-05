"""Shared local image / seasonal print settings for the three PDF types."""
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QFormLayout, QCheckBox, QComboBox, QPushButton, QFileDialog, QLabel
from core import i18n
from core.seasonal_pdf import image_files


class SeasonalOptions(QWidget):
    changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        form = QFormLayout(self)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.enabled = QCheckBox(i18n.t("season.enable"))
        self.enabled.setChecked(bool(settings.get("seasonal_pdf", False)))
        self.monochrome = QCheckBox(i18n.t("season.monochrome"))
        self.monochrome.setChecked(bool(settings.get("pdf_monochrome", False)))
        form.addRow(self.enabled)
        form.addRow(self.monochrome)
        self.folder = str(settings.get("season_image_folder", ""))
        self.folder_label = QLabel(self.folder or i18n.t("season.no_folder"))
        self.folder_label.setWordWrap(True)
        choose = QPushButton(i18n.t("season.folder"))
        choose.clicked.connect(self._choose_folder)
        form.addRow(choose, self.folder_label)
        self.combos = {}
        for key in ("winter", "spring", "summer", "autumn"):
            combo = QComboBox()
            combo.setMinimumContentsLength(12)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.combos[key] = combo
            form.addRow(i18n.t(f"season.{key}"), combo)
        self.preview = QLabel(i18n.t("season.no_image"))
        self.preview.setMinimumHeight(70)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow(self.preview)
        self._fill()
        self.enabled.toggled.connect(lambda *_: self.changed.emit())
        self.monochrome.toggled.connect(lambda *_: self.changed.emit())
        for combo in self.combos.values():
            combo.currentIndexChanged.connect(lambda *_, selected=combo: self._preview(selected))

        self._preview(self.combos["winter"])

    def _preview(self, combo):
        path = combo.currentData() or ""
        picture = QPixmap(path) if path else QPixmap()
        if picture.isNull():
            self.preview.setText(i18n.t("season.no_image"))
        else:
            self.preview.setPixmap(picture.scaled(320, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
        self.changed.emit()

    def _fill(self):
        files = image_files(self.folder)
        for key, combo in self.combos.items():
            selected = combo.currentData() or self.settings.get("season_images", {}).get(key, "")
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(i18n.t("season.no_image"), "")
            for path in files:
                combo.addItem(path.name, str(path))
            if selected and combo.findData(selected) < 0:
                combo.addItem(Path(selected).name, selected)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, i18n.t("season.folder"), self.folder)
        if folder:
            self.folder = folder
            self.folder_label.setText(folder)
            self._fill()
            self.changed.emit()

    def values(self):
        return {"seasonal_pdf": self.enabled.isChecked(), "pdf_monochrome": self.monochrome.isChecked(),
                "season_image_folder": self.folder,
                "season_images": {key: combo.currentData() or "" for key, combo in self.combos.items()}}


def edit_seasonal_options(settings, parent=None):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
    from core.ui_layout import scroll_page
    dialog = QDialog(parent)
    dialog.setWindowTitle(i18n.t("season.settings"))
    layout = QVBoxLayout(dialog)
    options = SeasonalOptions(settings)
    layout.addWidget(scroll_page(options))
    actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    actions.accepted.connect(dialog.accept)
    actions.rejected.connect(dialog.reject)
    layout.addWidget(actions)
    area = dialog.screen().availableGeometry()
    dialog.resize(min(560, area.width() - 48), min(560, area.height() - 80))
    if dialog.exec() == QDialog.DialogCode.Accepted:
        settings.update(options.values())
        return True
    return False
