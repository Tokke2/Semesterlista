"""Start overview and keyboard command palette, reading current module files."""
from datetime import date
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget)
from core import i18n
from core.roster import RosterError
from core.workbench_data import SearchEntry, read_overview, search_entries


def snapshot(window):
    entries, summaries = [], []
    for name, plugin in window._plugin_manager.get_all_plugins().items():
        display = i18n.plugin_display_name(plugin.get_name())
        entries.append(SearchEntry(name, display))
        view = getattr(plugin, "_main_view", None)
        manager = getattr(plugin, "tenant_manager", None)
        if manager is not None:
            path = Path(manager.tenant_file)
        elif view is not None and hasattr(view, "_current_list_path"):
            path = view._current_list_path()
        else:
            continue
        try:
            if not path.exists():
                raise FileNotFoundError(str(path))
            rows, periods, errors = read_overview(path, name,
                getattr(plugin, "FIXED_MODE", "") == "Semesterlista")
            entries.extend(rows)
            text = i18n.t("work.count", name=display, count=len(rows))
            for person, start, end in periods:
                text += "\n" + f"{person}: {start.isoformat()} – {end.isoformat()}"
            if errors:
                text += "\n" + i18n.t("work.invalid", count=len(errors))
        except (OSError, ValueError, RosterError) as exc:
            text = i18n.t("work.read_error", name=display, error=str(exc))
        summaries.append(text)
    return entries, summaries


class StartPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.title = QLabel()
        self.title.setStyleSheet("font-size:26px;font-weight:700;")
        layout.addWidget(self.title)
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        layout.addWidget(self.explanation)
        self.summary = QListWidget()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        self.search = QPushButton()
        self.search.clicked.connect(window._show_search)
        buttons.addWidget(self.search)
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        self.title.setText(i18n.t("work.welcome", date=date.today().isoformat()))
        self.explanation.setText(i18n.t("work.scope"))
        self.search.setText(i18n.t("work.search"))
        self.refresh_button.setText(i18n.t("work.refresh"))
        self.summary.clear()
        _, summaries = snapshot(self.window)
        self.summary.addItems(summaries or [i18n.t("work.empty")])


class SearchDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(i18n.t("work.search"))
        self.resize(660, 480)
        layout = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setPlaceholderText(i18n.t("work.placeholder"))
        layout.addWidget(self.query)
        self.results = QListWidget()
        layout.addWidget(self.results)
        self.entries, _ = snapshot(window)
        self.commands = {
            i18n.t("work.settings"): window._open_settings,
            i18n.t("donation.title"): window._show_donation,
            i18n.t("work.home"): window._show_start,
        }
        self.entries.extend(SearchEntry("", key) for key in self.commands)
        self.query.textChanged.connect(self.filter)
        self.query.returnPressed.connect(self.activate)
        self.results.itemActivated.connect(self.activate)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.filter()
        self.query.setFocus()

    def filter(self):
        self.results.clear()
        for entry in search_entries(self.entries, self.query.text()):
            text = entry.label
            if entry.module:
                text += "  ·  " + i18n.plugin_display_name(entry.module)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(entry.detail)
            self.results.addItem(item)
        if not self.results.count():
            item = QListWidgetItem(i18n.t("work.no_results"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        else:
            self.results.setCurrentRow(0)

    def activate(self, *args):
        item = self.results.currentItem()
        entry = item.data(Qt.ItemDataRole.UserRole) if item else None
        if entry is None:
            return
        self.accept()
        if not entry.module:
            self.commands[entry.label]()
            return
        self.window._show_tab(entry.module)
        index = self.window._tab_index(entry.module)
        self.window._tab_widget.setCurrentIndex(index)
        if entry.detail:
            message = QMessageBox(self.window)
            message.setWindowTitle(entry.label)
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.setText(entry.detail)
            message.exec()
