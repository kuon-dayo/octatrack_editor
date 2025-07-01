 # 1 サンプルのメタ＋波形を保持
from pathlib import Path
import numpy as np

class SampleItem:
    def __init__(self, name: str, data: np.ndarray, sr: int, path: Path):
        self.name, self.data, self.sr, self.path = name, data, sr, path
