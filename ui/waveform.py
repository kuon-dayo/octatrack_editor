from typing import Optional
import numpy as np
from PySide6.QtWidgets import QWidget, QScrollBar
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPixmap
from PySide6.QtCore import Qt, QEvent

HORIZONTAL = Qt.Orientation.Horizontal

class WaveformView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 波形データ
        self.data = np.zeros(1, dtype=np.float32)
        self.sr = 44100
        self.samples_pp = 256
        self.offset = 0
        self.marker_ratio = 0.0
        self.playhead_sample: Optional[int] = None
        self._pixmap: Optional[QPixmap] = None

        # 水平スクロールバー (WaveformView 内部)
        self.scrollbar = QScrollBar(HORIZONTAL, self)
        self.scrollbar.valueChanged.connect(self._on_scroll_changed)
        self._update_scrollbar_range()

        # ピンチジェスチャー有効化
        self.grabGesture(Qt.GestureType.PinchGesture)

    def set_data(self, data: np.ndarray, sr: int):
        """
        オーディオ波形データをセット。表示オフセット、マーカー、プレイヘッドをリセット。
        """
        self.data = data.astype(np.float32)
        self.sr = sr
        self.offset = 0
        self.marker_ratio = 0.0
        self.playhead_sample = None
        self._update_scrollbar_range()
        self._render_waveform()
        self.update()

    def _update_scrollbar_range(self):
        total = len(self.data)
        visible = max(1, self.width() * self.samples_pp)
        max_off = max(0, total - visible)
        self.scrollbar.setRange(0, max_off)
        self.scrollbar.setPageStep(visible)

    def _on_scroll_changed(self, val: int):
        self.offset = val
        self._render_waveform()
        self.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        sb_h = self.scrollbar.sizeHint().height()
        # スクロールバーをウィジェット底部に配置
        self.scrollbar.setGeometry(0, self.height() - sb_h, self.width(), sb_h)
        self._update_scrollbar_range()
        self._render_waveform()

    def _render_waveform(self):
        """
        波形を QPixmap に描画してキャッシュする
        """
        w = self.width()
        h_total = self.height()
        sb_h = self.scrollbar.sizeHint().height()
        h = max(1, h_total - sb_h)

        pixmap = QPixmap(w, h)
        # 背景を透明に（親ウィジェットの背景色が透ける）
        try:
            pixmap.fill(QColor(0, 0, 0, 0))
        except Exception:
            pass

        painter = QPainter(pixmap)
        mid = h / 2
        scale = h * 0.45
        step = max(1, int(self.samples_pp))

        end = min(len(self.data), self.offset + w * step)
        idx = np.arange(self.offset, end, step)
        seg = self.data[idx] if idx.size > 0 else np.zeros(w, dtype=np.float32)

        path = QPainterPath()
        path.moveTo(0, mid)
        for x, s in enumerate(seg):
            path.lineTo(x, mid - s * scale)
        painter.setPen(QPen(QColor("lightgray"), 1))
        painter.drawPath(path)
        painter.end()

        self._pixmap = pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap:
            painter.drawPixmap(0, 0, self._pixmap)

        w = self.width()
        h_total = self.height()
        sb_h = self.scrollbar.sizeHint().height()
        h = max(1, h_total - sb_h)

        # マーカーライン（ここを修正）
        if len(self.data) > 0:
            marker_sample = int(self.marker_ratio * len(self.data))
            start_sample = self.offset
            samples_per_pixel = self.samples_pp
            if start_sample <= marker_sample < start_sample + w * samples_per_pixel:
                mx = int((marker_sample - start_sample) / samples_per_pixel)
                painter.setPen(QPen(QColor("blue"), 1))
                painter.drawLine(mx, 0, mx, h)

        # プレイヘッドライン（現状のままでOK）
        if self.playhead_sample is not None:
            px = (self.playhead_sample - self.offset) / self.samples_pp
            if 0 <= px < w:
                painter.setPen(QPen(QColor("red"), 1))
                painter.drawLine(int(px), 0, int(px), h)
        painter.end()

    def mousePressEvent(self, ev):
        x = ev.position().x() if hasattr(ev, "position") else ev.x()
        # 現在の表示範囲の先頭サンプル
        start_sample = self.offset
        # 1ピクセルあたりのサンプル数
        samples_per_pixel = self.samples_pp
        # クリック位置が指すサンプル番号（全体に対して）
        sample_pos = start_sample + int(x * samples_per_pixel)
        # 全体長に対する割合
        self.marker_ratio = sample_pos / len(self.data) if len(self.data) > 0 else 0.0
        self.update()

    def zoom(self, factor: float):
        w = self.width()
        old_samples_pp = self.samples_pp
        old_visible = w * old_samples_pp
        center_sample = self.offset + old_visible // 2

        # 最大値: 全体が1画面に収まるまで
        max_samples_pp = max(1, len(self.data) // w) if w > 0 else 1
        new_samples_pp = int(old_samples_pp / factor)
        new_samples_pp = min(max_samples_pp, max(1, new_samples_pp))
        self.samples_pp = new_samples_pp

        new_visible = w * new_samples_pp
        new_offset = max(0, center_sample - new_visible // 2)
        max_off = max(0, len(self.data) - new_visible)
        self.offset = min(new_offset, max_off)

        self._update_scrollbar_range()
        self._render_waveform()
        self.update()

    def zoom_in(self):
        self.zoom(1.2)  # 細かく拡大

    def zoom_out(self):
        self.zoom(0.83)  # 細かく縮小

    def wheelEvent(self, event):
        # Ctrl+ホイールでズーム、それ以外はスクロール
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # 横スクロール（2本指横スワイプ）で左右に動かす
            delta_x = event.angleDelta().x()
            delta_y = event.angleDelta().y()
            step = int(self.width() * self.samples_pp * 0.1)
            if abs(delta_x) > abs(delta_y):  # 横スクロール優先
                if delta_x > 0:
                    self.offset = max(0, self.offset - step)
                else:
                    self.offset = min(len(self.data) - self.width() * self.samples_pp, self.offset + step)
            else:  # 縦スクロールは無視（または必要なら上下移動に割り当ててもOK）
                pass
            self._update_scrollbar_range()
            self._render_waveform()
            self.update()

    def event(self, ev):
        # ピンチジェスチャーでズーム
        if ev.type() == QEvent.Type.Gesture:
            return self.gestureEvent(ev)
        return super().event(ev)

    def gestureEvent(self, ev):
        pinch = ev.gesture(Qt.GestureType.PinchGesture)
        if pinch:
            scale = pinch.scaleFactor()
            if scale > 1.01:
                self.zoom_in()
            elif scale < 0.99:
                self.zoom_out()
            return True
        return False





# テスト用スタンドアロン起動
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    import numpy as np
    import soundfile as sf

    app = QApplication(sys.argv)

    w = WaveformView()
    
    wav_path = "/Users/tokushigekuon/Documents/03_My OctaTrack/Tracks/Cropped/142_Controlled Chaos .wav"
    data, sr = sf.read(wav_path, always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)  # モノラル化

    w.set_data(data, sr)
  

    w.resize(800, 200)
    w.show()

    sys.exit(app.exec())


    """"""
    # テスト用サイン波（1秒間の440Hz）
    test_wave = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
    w.set_data(test_wave, 44100)
    """"""