"""Shared, palette-aware SVG icons for controls, tabs and menus (no emoji fonts)."""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QByteArray, QEvent, QObject, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPalette, QAction
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QPushButton, QToolButton, QTabWidget, QWidget
from core import i18n

ROOT = Path(__file__).resolve().parent.parent / 'assets' / 'ui'
TAB_ICONS = {'kalender': 'calendar', 'lista': 'leave', 'fordon': 'car', 'hyra': 'home'}
EMOJI = {'📅': 'calendar', '🏠': 'home', '🚗': 'car', '🖨': 'pdf', '📁': 'folder',
         '📝': 'edit', '🔄': 'refresh', '✅': 'check', '❌': 'close', '🧪': 'check'}
KEYS = {
    'pdf': ('calendar.export', 'lista.button.generate', 'hyra.button.generate'),
    'folder': ('lista.button.browse', 'lista.button.open_documents', 'settings.open_log_folder'),
    'edit': ('lista.manage_list', 'hyra.button.edit', 'vacation.title'),
    'settings': ('menu.file.settings', 'tray.settings'),
    'refresh': ('hyra.button.reload', 'menu.help.check_updates', 'tray.check_updates',
                'update.check', 'update.install'),
    'palette': ('season.settings',),
    'close': ('common.close', 'common.cancel', 'menu.file.quit', 'tray.quit', 'tray.hide'),
    'save': ('common.save',),
    'check': ('common.ok', 'lista.button.tests', 'menu.file.autostart'),
    'open': ('update.release_page', 'settings.open_error_log', 'tray.show'),
    'copy': ('settings.copy_log',),
    'delete': ('settings.clear_error_log',),
    'info': ('menu.help.about', 'tray.about'),
}


def clean_label(text):
    text = text.strip()
    if text[:1] in EMOJI:
        text = text[1:].lstrip('\ufe0f ')
    return text


def normalize(text):
    return clean_label(text).replace('&', '').strip(' .…').casefold()


@lru_cache(maxsize=4)
def labels(language):
    result = {}
    for name, keys in KEYS.items():
        for key in keys:
            value = i18n.t(key, app='Semesterlista', version='', file='')
            if value != key:
                result[normalize(value)] = name
    for text, name in [('Semesterlista', 'leave'), ('Vacation Schedule', 'leave'),
                       ('Kalender', 'calendar'), ('Calendar', 'calendar'),
                       ('Fordon', 'car'), ('Vehicles', 'car'), ('Hyra', 'home'), ('Rent', 'home')]:
        result[normalize(text)] = name
    return result


@lru_cache(maxsize=256)
def icon(name, color):
    path = ROOT / f'{name}.svg'
    if not path.is_file():
        return QIcon()
    source = path.read_text(encoding='utf-8').replace('#16324f', color)
    renderer = QSvgRenderer(QByteArray(source.encode('utf-8')))
    result = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


class IconController(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.busy = False

    def decorate(self, obj):
        palette = obj.palette() if isinstance(obj, QWidget) else QApplication.palette()
        role = (QPalette.ColorRole.ButtonText if isinstance(obj, (QPushButton, QToolButton))
                else QPalette.ColorRole.WindowText)
        color = palette.color(role).name()
        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                page = obj.widget(index)
                name = page.property('semesterlistaIcon')
                if name:
                    signature = f"{name}:{color}"
                    if page.property('semesterlistaTabIconSignature') != signature:
                        page.setProperty('semesterlistaTabIconSignature', signature)
                        obj.setTabIcon(index, icon(name, color))
        if not isinstance(obj, (QPushButton, QToolButton, QAction)):
            return
        text = obj.text()
        name = (obj.property('semesterlistaIcon') or
                labels(i18n.current_language()).get(normalize(text)) or EMOJI.get(text[:1]))
        if not name:
            return
        obj.setProperty('semesterlistaIcon', name)
        signature = f"{name}:{color}:{text}"
        if obj.property('semesterlistaIconSignature') == signature:
            return
        # Mark before setIcon, which can itself emit ActionChanged/LayoutRequest.
        obj.setProperty('semesterlistaIconSignature', signature)
        obj.setIcon(icon(name, color))
        if isinstance(obj, QAction):
            obj.setIconVisibleInMenu(True)
        if clean_label(text) != text:
            obj.setText(clean_label(text))

    def eventFilter(self, obj, event):
        if self.busy:
            return False
        kind = event.type()
        relevant = (QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.LayoutRequest,
                    QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange,
                    QEvent.Type.ActionAdded, QEvent.Type.ActionChanged)
        if kind not in relevant:
            return False
        self.busy = True
        try:
            self.decorate(obj)
            if isinstance(obj, QWidget):
                for child in obj.findChildren(QWidget):
                    self.decorate(child)
                for action in obj.actions():
                    self.decorate(action)
            if kind in (QEvent.Type.ActionAdded, QEvent.Type.ActionChanged):
                self.decorate(event.action())
        finally:
            self.busy = False
        return False


def install_ui_icons(app):
    controller = getattr(app, '_semesterlista_icon_controller', None)
    if controller is None:
        controller = IconController(app)
        app._semesterlista_icon_controller = controller
        app.installEventFilter(controller)
    return controller
