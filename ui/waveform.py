# ズーム・スクロール波形ビュー
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QPainterPath
from PySide6.QtCore import Qt
import numpy as np

class WaveformView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None; self.sr = 44100
        self.samples_pp = 256; self.offset = 0
        self.marker_ratio = 0.0

    def set_data(self, data: np.ndarray, sr: int):
        self.data, self.sr = data.astype(np.float32), sr
        self.offset, self.marker_ratio = 0, 0.0
        self.update()

    def paintEvent(self, _):
        if self.data is None: return
        p = QPainter(self); w,h = self.width(), self.height()
        mid, scale = h/2, h*0.45
        step = max(1, int(self.samples_pp))
        idx = np.arange(self.offset, min(len(self.data), self.offset+w*step), step)
        seg = self.data[idx]
        path = QPainterPath(); path.moveTo(0, mid)
        for x, s in enumerate(seg): path.lineTo(x, mid - s*scale)
        p.setPen(QPen(Qt.lightGray, 1)); p.drawPath(path)
        # マーカー
        p.setPen(QPen(Qt.red, 1)); p.drawLine(int(self.marker_ratio*w), 0, int(self.marker_ratio*w), h)

    # クリックでマーカー
    def mousePressEvent(self, ev):
        if self.data is None: return
        self.marker_ratio = ev.position().x()/self.width()
        self.update()
