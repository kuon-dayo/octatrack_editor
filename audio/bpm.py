# librosa を使った BPM 推定
import librosa, numpy as np

def detect(data: np.ndarray, sr: int) -> int:
    tempo, _ = librosa.beat.beat_track(y=data, sr=sr)
    return round(float(tempo))
