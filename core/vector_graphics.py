"""Paint original SVGs at the requested device resolution, never enlarge small PNGs."""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


class VectorIconEngine(QIconEngine):
    def __init__(self, source):
        super().__init__()
        self.source = bytes(source)
        self.renderer = QSvgRenderer(QByteArray(self.source))

    def clone(self):
        return VectorIconEngine(self.source)

    def isNull(self):
        return not self.renderer.isValid()

    def paint(self, painter, rect, mode, state):
        painter.save()
        if mode.name == 'Disabled':
            painter.setOpacity(painter.opacity() * 0.5)
        self.renderer.render(painter, QRectF(rect))
        painter.restore()

    def pixmap(self, size, mode, state):
        image = QPixmap(size)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, image.rect(), mode, state)
        painter.end()
        return image


class VectorMark(QWidget):
    """App mark painted directly on Qt's DPI-aware backing store on every screen."""
    def __init__(self, source, logical_size, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(QByteArray(source.encode('utf-8')), self)
        self.setFixedSize(logical_size, logical_size)

    def paintEvent(self, event):
        painter = QPainter(self)
        self.renderer.render(painter, QRectF(self.rect()))
        painter.end()
