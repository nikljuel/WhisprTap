from abc import ABC, abstractmethod
from pathlib import Path


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> str:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...


class FasterWhisperTranscriber(Transcriber):
    def __init__(self, model_size: str = "medium", language: str = "de", model_dir: str | None = None):
        self._model = None
        self._model_size = model_size
        self._language = language
        self._model_dir = model_dir
        self._ready = False

    def load(self) -> None:
        from faster_whisper import WhisperModel

        kwargs = {"device": "cpu", "compute_type": "int8"}
        if self._model_dir:
            kwargs["download_root"] = self._model_dir

        self._model = WhisperModel(self._model_size, **kwargs)
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def transcribe(self, audio_path: Path) -> str:
        if not self._model:
            raise RuntimeError("Modell nicht geladen")

        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self._language if self._language != "auto" else None,
            beam_size=5,
            condition_on_previous_text=True,
            no_speech_threshold=0.6,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
