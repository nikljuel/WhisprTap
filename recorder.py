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
    def __init__(self, device: int | None = None):
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._device = device

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        with self._lock:
            self._frames = []
        channels = self._resolve_channels()
        self._channels = channels
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=channels,
            dtype="int16",
            callback=self._callback,
            device=self._device,
        )
        self._stream.start()
        with self._lock:
            self._recording = True

    def _resolve_channels(self) -> int:
        """Gibt 1 zurück wenn möglich, sonst die native Kanalanzahl des Geräts."""
        try:
            sd.check_input_settings(device=self._device, channels=1, samplerate=SAMPLE_RATE)
            return 1
        except Exception:
            if self._device is not None:
                return max(1, int(sd.query_devices(self._device)["max_input_channels"]))
            return 1

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

        # Stereo → Mono mischen wenn nötig
        if audio.ndim == 2 and audio.shape[1] > 1:
            audio = audio.mean(axis=1).astype(np.int16)
        elif audio.ndim == 2:
            audio = audio[:, 0]

        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_DURATION_SECONDS:
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return Path(tmp.name)

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())
