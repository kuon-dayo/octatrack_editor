# メインウィンドウ＋メニュー
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QVBoxLayout, QWidget,
    QPushButton, QLabel, QListWidget
)
from ui.waveform import WaveformView
from model.sample_item import SampleItem
from audio import player, bpm, ot_writer
import soundfile as sf
import numpy as np
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChainSmith")          # ★商標回避の別名
        central = QWidget(); self.setCentralWidget(central)
        v = QVBoxLayout(central)

        self.wave = WaveformView(self)
        v.addWidget(self.wave)

        self.list = QListWidget(); v.addWidget(self.list)
        self.list.currentRowChanged.connect(self.select)

        load_btn = QPushButton("Load…"); v.addWidget(load_btn)
        load_btn.clicked.connect(self.load_files)

        play_btn = QPushButton("Play from Marker"); v.addWidget(play_btn)
        play_btn.clicked.connect(self.play)

        export_btn = QPushButton("Export .ot"); v.addWidget(export_btn)
        export_btn.clicked.connect(self.export_ot)

        self.info = QLabel(); v.addWidget(self.info)

        # 状態
        self.samples: list[SampleItem] = []
        self.current: SampleItem | None = None

    # ---------- I/O ----------
    def load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open", filter="Audio (*.wav *.aif *.flac)")
        for p in paths:
            data, sr = sf.read(p, always_2d=False)
            if data.ndim == 2: data = data.mean(axis=1)
            item = SampleItem(Path(p).name, data, sr, Path(p))
            self.samples.append(item)
            self.list.addItem(item.name)
        if self.samples:
            self.select(0)

    def select(self, row: int):
        self.current = self.samples[row]
        self.wave.set_data(self.current.data, self.current.sr)
        self.info.setText(f"{self.current.name}  {len(self.current.data)/self.current.sr:.2f}s")

    def play(self):
        if not self.current: return
        start = int(len(self.current.data) * self.wave.marker_ratio)
        player.play(self.current.data[start:], self.current.sr)

    def export_ot(self):
        if not self.current: return
        bpm_val = bpm.detect(self.current.data, self.current.sr)
        ot_path = ot_writer.write(self.current, bpm_val)
        self.info.setText(f"Saved {ot_path.name}  (BPM {bpm_val})")
