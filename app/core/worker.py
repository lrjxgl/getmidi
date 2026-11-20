"""后台线程：转录与音频渲染。"""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .engines import capture_output, create_engine
from .render import RenderError, render_wav


class TranscribeWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, audio: Path, model_key: str, device: str, parent=None):
        super().__init__(parent)
        self._audio = audio
        self._model_key = model_key
        self._device = device

    def run(self) -> None:
        try:
            with capture_output(self.log.emit):
                engine = create_engine(self._model_key, self._device)
                self.progress.emit(5, f"准备 {engine.label}…")
                engine.load(self.log.emit)
                self.progress.emit(12, "开始转录…")
                transcription = engine.transcribe(self._audio, self.progress.emit, self.log.emit)
                if not transcription.duration:
                    transcription.duration = max(
                        (note.end for track in transcription.tracks for note in track.notes), default=0.0
                    )
            self.succeeded.emit(transcription)
        except Exception as exc:  # pragma: no cover - 依赖外部模型
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(exc) or exc.__class__.__name__)


class RenderWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, transcription, tracks, soundfont: Path, out_path: Path, parent=None):
        super().__init__(parent)
        self._transcription = transcription
        self._tracks = tracks
        self._soundfont = soundfont
        self._out_path = out_path

    def run(self) -> None:
        try:
            path = render_wav(self._transcription, self._tracks, self._soundfont, self._out_path)
            self.succeeded.emit(str(path))
        except RenderError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"音频渲染失败：{exc}")


class ExportWorker(QThread):
    """执行导出任务（渲染 WAV / 打包 ZIP），job 接收进度回调并返回输出路径。"""

    log = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        try:
            path = self._job(self.log.emit)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.succeeded.emit(str(path))
