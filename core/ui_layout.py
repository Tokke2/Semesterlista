"""Shared spacing and wrapping action rows for compact desktop layouts."""
from pathlib import Path
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QScrollArea, QWidgetItem

SPACING = 8
MARGIN = 12


class FlowLayout(QLayout):
    """Wrap controls in reading order instead of forcing a wide window."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(SPACING)

    def addItem(self, item):
        self.items.append(item)

    def addWidget(self, widget):
        self.addChildWidget(widget)
        self.addItem(QWidgetItem(widget))

    def addStretch(self, *_):
        pass

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, measure):
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            if item.isEmpty():
                continue
            size = item.sizeHint()
            width = min(size.width(), max(rect.width(), item.minimumSize().width()))
            if item.hasHeightForWidth():
                size.setHeight(max(item.minimumSize().height(), item.heightForWidth(width)))
            if x > rect.x() and x + width > rect.right() + 1:
                x = rect.x()
                y += height + self.spacing()
                height = 0
            if not measure:
                item.setGeometry(QRect(x, y, width, size.height()))
            x += width + self.spacing()
            height = max(height, size.height())
        return y + height - rect.y()


def scroll_page(widget):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    if widget.layout():
        widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    scroll.setWidget(widget)
    return scroll


def design_styles(colors):
    c = colors
    root = (Path(__file__).resolve().parent / "ui_icons").as_posix()
    arrows = "black" if c["button_fg"].upper() == "#000000" else "white"
    check = "black" if c["tab_selected_fg"].upper() == "#000000" else "white"
    return f'''
QMenuBar {{ padding: 4px 8px; }}
QMenuBar::item {{ padding: 7px 12px; border-radius: 6px; }}
QMenu {{ padding: 6px; border: 1px solid {c['input_border']}; }}
QMenu::item {{ padding: 8px 30px 8px 12px; border-radius: 5px; }}
QMenu::separator {{ height: 1px; background: {c['input_border']}; margin: 6px 10px; }}
QPlainTextEdit, QTextEdit {{ background: {c['input_bg']}; color: {c['input_fg']}; border: 1px solid {c['input_border']}; border-radius: 8px; padding: 8px; }}
QPushButton, QToolButton {{ border-radius: 8px; }}
QPushButton:disabled, QToolButton:disabled {{ background: {c['button_disabled_bg']}; color: {c['button_disabled_fg']}; }}
QTabWidget::pane {{ border: none; padding-top: 8px; }}
QTabBar::tab {{ margin-right: 4px; border-radius: 7px; }}
QTabBar::tab:selected {{ border-bottom: 3px solid {c['accent']}; }}
QComboBox::down-arrow, QSpinBox::down-arrow {{ image: url("{root}/down-{arrows}.svg"); width: 14px; height: 14px; }}
QSpinBox::up-arrow {{ image: url("{root}/up-{arrows}.svg"); width: 14px; height: 14px; }}
QSpinBox, QComboBox {{ padding-right: 28px; }}
QCheckBox::indicator:checked {{ image: url("{root}/check-{check}.svg"); }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ color: {c['tab_selected_fg']}; }}
QPushButton, QToolButton {{ min-width: 0px; min-height: 22px; padding: 6px 12px; border-width: 1px; }}
QPushButton[primary="true"] {{ background: {c['accent']}; color: {c['tab_selected_fg']}; }}
QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus {{ border: 2px solid {c['accent']}; }}
QTabBar::tab {{ padding: 8px 16px; min-width: 70px; min-height: 22px; border-width: 1px; }}
QGroupBox {{ border: 1px solid {c['input_border']}; border-radius: 10px; margin-top: 20px; padding: 18px 12px 12px 12px; }}
QGroupBox::title {{ color: {c['window_fg']}; padding: 0px 4px; }}
QLabel[role="muted"] {{ color: {c['muted']}; background: transparent; }}
QLabel[role="title"] {{ font-size: 18pt; font-weight: bold; }}
QLabel[role="row"] {{ padding: 4px 8px; background: {c['input_bg']}; color: {c['input_fg']}; }}
QComboBox, QLineEdit, QSpinBox, QDateEdit {{ min-height: 24px; padding: 3px 6px; }}
QAbstractItemView, QComboBox QAbstractItemView, QCalendarWidget QAbstractItemView {{
 background: {c['input_bg']}; color: {c['input_fg']}; alternate-background-color: {c['window_bg']};
 selection-background-color: {c['accent']}; selection-color: {c['tab_selected_fg']};
}}
QHeaderView::section {{ background: {c['window_bg']}; color: {c['window_fg']}; padding: 5px; border: 1px solid {c['input_border']}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {c['window_bg']}; }}
QCalendarWidget QToolButton {{ background: {c['button_bg']}; color: {c['button_fg']}; }}
QFrame[status] {{ background: {c['input_bg']}; border: 1px solid {c['input_border']}; border-left: 4px solid {c['accent']}; border-radius: 5px; }}
QFrame[status] QLabel {{ background: transparent; color: {c['window_fg']}; border: none; }}
QLabel[role="status"] {{ font-weight: bold; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ width: 14px; }}
QCheckBox, QRadioButton {{ spacing: 7px; padding: 3px 0; }}
'''


class AdaptiveColumns(QLayout):
    """Two equal columns when both fit their minimum width, one column otherwise."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(16)

    def addItem(self, item):
        self.items.append(item)

    def addWidget(self, widget):
        self.addChildWidget(widget)
        self.addItem(QWidgetItem(widget))

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def hasHeightForWidth(self):
        return True

    def minimumSize(self):
        return QSize(max((i.minimumSize().width() for i in self.items), default=0), 0)

    def sizeHint(self):
        return QSize(760, self.heightForWidth(760))

    def columns(self, width):
        minimum = max(340, self.minimumSize().width())
        return 2 if width >= minimum * 2 + self.spacing() else 1

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, False)

    def _arrange(self, rect, measure):
        columns = self.columns(rect.width())
        width = max(1, (rect.width() - self.spacing() * (columns - 1)) // columns)
        y = rect.y()
        visible = [item for item in self.items if not item.isEmpty()]
        for start in range(0, len(visible), columns):
            row = visible[start:start + columns]
            height = max((i.heightForWidth(width) if i.hasHeightForWidth() else i.sizeHint().height()) for i in row)
            for column, item in enumerate(row):
                if not measure:
                    item.setGeometry(QRect(rect.x() + column * (width + self.spacing()), y, width, height))
            y += height + self.spacing()
        return max(0, y - rect.y() - self.spacing())
