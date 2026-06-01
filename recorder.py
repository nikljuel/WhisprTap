import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
MIN_DURATION_SECONDS = 0.5


class Recorder:
    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        with self._lock:
            self._recording = True

    def stop(self) -> Path | None:
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
        self._stream.stop()
        self._stream.close()
        self._stream = None

        with self._lock:
            frames = self._frames.copy()

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION_SECONDS:
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return Path(tmp.name)

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())
