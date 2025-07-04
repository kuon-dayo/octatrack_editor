# メインウィンドウ＋メニュー
# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QHBoxLayout,QFileDialog   
)
from ui.waveform import WaveformView
from model.sample_item import SampleItem
from audio import player, bpm, ot_writer
import soundfile as sf
import numpy as np
from pathlib import Path
import time
from PySide6.QtCore import QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChainSmith")
        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        # 波形ウィジェット（スクロールバー込み）
        self.wave = WaveformView(self)
        self.wave.setMinimumHeight(200)
        v.addWidget(self.wave)

        # サンプルリスト
        self.list = QListWidget()
        v.addWidget(self.list)

        # 再生コントロール
        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("▶ Marker")
        self.btn_stop = QPushButton("■ Stop")
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop)
        v.addLayout(ctrl)

        # エクスポート
        export_btn = QPushButton("Export .ot")
        v.addWidget(export_btn)

        # 情報ラベル
        self.info = QLabel()
        v.addWidget(self.info)

        # 「Load…」ボタンをサンプルリストの直前に配置
        load_btn = QPushButton("Load…")
        v.insertWidget(2,load_btn)
        # サンプルファイルを読み込むためのボタンをリストの上に配置
        load_btn.clicked.connect(self.load_files)
        self.btn_play.clicked.connect(self.play_from_marker)
        self.btn_stop.clicked.connect(self.stop_playback)
        export_btn.clicked.connect(self.export_ot)

        # ズームイン・ズームアウトボタン
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        v.addWidget(zoom_in_btn)
        v.addWidget(zoom_out_btn)
        zoom_in_btn.clicked.connect(self.wave.zoom_in)
        zoom_out_btn.clicked.connect(self.wave.zoom_out)

        # タイマー（プレイヘッド更新用）
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_playhead)

        # 状態
        self.samples: list[SampleItem] = []
        self.current: SampleItem | None = None

    def load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open", filter="Audio (*.wav *.aif *.flac)"
        )
        for p in paths:
            data, sr = sf.read(p, always_2d=False)
            if data.ndim == 2:
                data = data.mean(axis=1)
            item = SampleItem(Path(p).name, data, sr, Path(p))
            self.samples.append(item)
            self.list.addItem(item.name)
        if self.samples:
            self.select(0)

    def select(self, row: int):
        self.current = self.samples[row]
        self.wave.set_data(self.current.data, self.current.sr)
        self.info.setText(f"{self.current.name}  {len(self.current.data)/self.current.sr:.2f}s")

    def play_from_marker(self):
        if not self.current:
            return
        self.play_start = int(len(self.current.data) * self.wave.marker_ratio)
        player.play(self.current.data, self.current.sr, start_sample=self.play_start)
        self.start_time = time.time()
        self.timer.start()

    def update_playhead(self):
           # ── self.current が None なら何もしない ──
       if not self.current:
            return
       elapsed = time.time() - self.start_time
       pos = self.play_start + int(elapsed * self.current.sr)
       self.wave.playhead_sample = pos
       self.wave.update()

    def stop_playback(self):
        player.stop()
        self.timer.stop()
        self.wave.playhead_sample = None
        self.wave.update()

    def export_ot(self):
        if not self.current:
            return
        bpm_val = bpm.detect(self.current.data, self.current.sr)
        ot_path = ot_writer.write(self.current, bpm_val)
        self.info.setText(f"Saved {ot_path.name}  (BPM {bpm_val})")
