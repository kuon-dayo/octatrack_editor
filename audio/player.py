 # 再生／停止／ループ制御 (sounddevice)
import sounddevice as sd, numpy as np

def play(buf: np.ndarray, sr: int):
    sd.stop(); sd.play(buf, sr)
