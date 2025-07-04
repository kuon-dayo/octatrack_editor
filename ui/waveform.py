from typing import Optional, Any
import numpy as np
import weakref
from functools import lru_cache
from PySide6.QtWidgets import QWidget, QScrollBar
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QPixmap
from PySide6.QtCore import Qt, QEvent
import math

HORIZONTAL = Qt.Orientation.Horizontal

class WaveformView(QWidget):
    # buf_id → 実データを弱参照で保持するマップ
    _buf_map = weakref.WeakValueDictionary()

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

    @staticmethod
    @lru_cache(maxsize=256)
    def _peak_envelope(buf_id: int, start: int, end: int, step: int):
        """
        buf_id   : id(self.data) でキャッシュ切替を検知
        start/end: サンプル範囲
        step     : 1ピクセルあたりのサンプル数
        戻り値   : (mins[width], maxs[width])
        """
        # マップから実データを取り出す（キーがなければ空配列）
        buf = WaveformView._buf_map.get(buf_id, np.zeros(0, dtype=np.float32))
        seg = buf[start:end]
        total = (len(seg) // step) * step
        if total == 0:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
        seg = seg[:total].reshape(-1, step)
        return seg.min(axis=1), seg.max(axis=1)

    def set_data(self, data: np.ndarray, sr: int):
        """
        オーディオ波形データをセット。表示オフセット、マーカー、プレイヘッドをリセット。
        """
        self.data = data.astype(np.float32)
        self.sr = sr
        self.offset = 0
        self.marker_ratio = 0.0
        self.playhead_sample = None

        # データをマップに登録してキャッシュをクリア
        WaveformView._buf_map[id(self.data)] = self.data
        self._peak_envelope.cache_clear()

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
        self.scrollbar.setGeometry(0, self.height() - sb_h, self.width(), sb_h)
        self._update_scrollbar_range()
        self._render_waveform()

    def _render_waveform(self):
        """ピーク・エンベロープを QPixmap に描画してキャッシュ"""
        w_px  = self.width()
        sb_h  = self.scrollbar.sizeHint().height()
        h_px  = max(1, self.height() - sb_h)

        if w_px <= 0 or h_px <= 0 or len(self.data) == 0:
            self._pixmap = None
            return

        step  = max(1, int(self.samples_pp))
        start = self.offset
        end   = min(len(self.data), start + w_px * step)

        # Peak 抽出（キャッシュ利用）
        mins, maxs = self._peak_envelope(id(self.data), start, end, step)

        # 描画
        pixmap = QPixmap(w_px, h_px)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        mid   = h_px / 2.0
        scale = h_px * 0.45

        path = QPainterPath()
        for x, (lo, hi) in enumerate(zip(mins, maxs)):
            y_hi = mid - hi * scale
            y_lo = mid - lo * scale
            if hi == lo:
                painter.drawPoint(x, int(y_hi))      # ★ 点描画
            else:
                path.moveTo(x, float(y_hi))
                path.lineTo(x, float(y_lo))
        painter.setPen(QPen(QColor("black"), 1))
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

        # マーカーライン
        if len(self.data) > 0:
            marker_sample = int(self.marker_ratio * len(self.data))
            start_sample = self.offset
            spp = self.samples_pp
            if start_sample <= marker_sample < start_sample + w * spp:
                mx = (marker_sample - start_sample) // spp
                painter.setPen(QPen(QColor("blue"), 1))
                painter.drawLine(mx, 0, mx, h)

        # プレイヘッドライン
        if self.playhead_sample is not None:
            px = (self.playhead_sample - self.offset) / self.samples_pp
            if 0 <= px < w:
                painter.setPen(QPen(QColor("red"), 1))
                painter.drawLine(int(px), 0, int(px), h)
        painter.end()

    def mousePressEvent(self, ev):
        x = ev.position().x() if hasattr(ev, "position") else ev.x()
        sample_pos = self.offset + int(x * self.samples_pp)
        self.marker_ratio = sample_pos / len(self.data) if len(self.data) > 0 else 0.0
        self.update()


    def zoom(self, factor: float):
        """
        factor > 1 : 拡大 (ズームイン)
        factor < 1 : 縮小 (ズームアウト)
        """
        w = self.width()
        if w <= 0 or len(self.data) == 0:
            return

        old_spp = self.samples_pp
        # 最小ズーム（最も細かく）：１サンプル／ピクセル
        min_spp = 1
        # 最大ズーム（最も粗く）：ウィジェット幅に対してデータ全長が１ピクセル以上を保つ
        max_spp = max(1, len(self.data) // w)

        # ──────────── ここで拡大・縮小の上限チェック ────────────
        # ズームイン（factor>1）してももう最小に達していたら抜ける
        if factor > 1 and old_spp <= min_spp:
            return
        # ズームアウト（factor<1）してももう最大に達していたら抜ける
        if factor < 1 and old_spp >= max_spp:
            return

        # ──────────── 新しい samples_pp を計算 ────────────
        raw = old_spp / factor
        if factor < 1:
            new_spp = math.ceil(raw)
        else:
            new_spp = math.floor(raw)
        # clamp
        new_spp = max(min_spp, min(new_spp, max_spp))

        # 変化がなければ何もしない
        if new_spp == old_spp:
            return

        # ──────────── 更新 ────────────
        self.samples_pp = new_spp

        # 中心点を維持してオフセットを再計算
        center = self.offset + (w * old_spp) // 2
        new_vis = w * self.samples_pp
        # データ範囲最終チェック
        self.offset = min(
            max(0, center - new_vis // 2),
            max(0, len(self.data) - new_vis)
        )

        self._update_scrollbar_range()
        self._render_waveform()
        self.update()



    def zoom_in(self):
        self.zoom(1.2)

    def zoom_out(self):
        self.zoom(0.83)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            dx = event.angleDelta().x()
            step = int(self.width() * self.samples_pp * 0.1)
            if abs(dx) > abs(event.angleDelta().y()):
                self.offset = max(0, self.offset - step) if dx > 0 else min(len(self.data) - self.width() * self.samples_pp, self.offset + step)
                self._update_scrollbar_range()
                self._render_waveform()
                self.update()

    def event(self, ev):
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
    from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
    import numpy as np
    import soundfile as sf

    app = QApplication(sys.argv)

    # レイアウト用ウィジェット
    root = QWidget()
    layout = QVBoxLayout(root)

    w = WaveformView()
    layout.addWidget(w)

    # Print Sizeボタン
    def print_waveform_size():
        w_px = w.width()
        sb_h = w.scrollbar.sizeHint().height()
        h_px = max(1, w.height() - sb_h)
        print(f"Waveform pixmap size: {w_px} x {h_px}")

    btn = QPushButton("Print Size")
    btn.clicked.connect(print_waveform_size)
    layout.addWidget(btn)

    wav_path = "/Users/tokushigekuon/Documents/03_My OctaTrack/Tracks/Cropped/142_Controlled Chaos .wav"
    data, sr = sf.read(wav_path, always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)  # モノラル化

    w.set_data(data, sr)

    root.resize(800, 240)
    root.show()

    sys.exit(app.exec())


    """"""
    # テスト用サイン波（1秒間の440Hz）
    test_wave = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
    w.set_data(test_wave, 44100)
    """"""