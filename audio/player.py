 # 再生／停止／ループ制御 (sounddevice)
import sounddevice as sd, numpy as np

def play(buf: np.ndarray, sr: int, start_sample: int = 0):
    sd.stop()
    sd.play(buf[start_sample:], sr)

def stop():
    """再生停止"""
    sd.stop()