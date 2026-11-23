"""Hold Alt to display registered shortcuts without intercepting menu navigation."""
from PySide6.QtCore import QObject, QEvent, Qt, QPoint
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QToolTip
from core import i18n


class ShortcutHints(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
            window = QApplication.activeWindow()
            if window is not None:
                lines = []
                for action in window.findChildren(QAction):
                    if action.isEnabled() and not action.shortcut().isEmpty():
                        text = action.text().replace('&', '')
                        lines.append(action.shortcut().toString(QKeySequence.SequenceFormat.NativeText) + ' — ' + text)
                if lines:
                    QToolTip.showText(window.mapToGlobal(QPoint(16, 48)),
                                     i18n.t("display.shortcuts") + '\n' + '\n'.join(dict.fromkeys(lines)), window)
        elif event.type() in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            QToolTip.hideText()
        elif event.type() == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Alt:
            QToolTip.hideText()
        return False
