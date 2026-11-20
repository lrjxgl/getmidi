"""基于 QtMultimedia 的 WAV 播放器。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class Player(QObject):
    positionChanged = Signal(float)
    durationChanged = Signal(float)
    playingChanged = Signal(bool)
    finished = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._output = QAudioOutput(self)
        self._output.setVolume(0.85)
        self._player.setAudioOutput(self._output)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._source: Path | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    def load(self, path: Path, autoplay: bool = False) -> None:
        self._source = Path(path)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        if autoplay:
            self.play()

    def loaded_path(self) -> Path | None:
        return self._source

    def play(self) -> None:
        self._player.play()
        self._timer.start()

    def pause(self) -> None:
        self._player.pause()
        self._timer.stop()

    def toggle(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            if self._player.mediaStatus() == QMediaPlayer.EndOfMedia:
                self._player.setPosition(0)
            self.play()

    def stop(self) -> None:
        self._player.stop()
        self._timer.stop()
        self.positionChanged.emit(0.0)

    def seek(self, seconds: float) -> None:
        self._player.setPosition(int(max(0.0, seconds) * 1000))

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState

    def position(self) -> float:
        return self._player.position() / 1000.0

    def duration(self) -> float:
        return self._player.duration() / 1000.0

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        self.positionChanged.emit(self.position())

    def _on_position(self, ms: int) -> None:
        self.positionChanged.emit(ms / 1000.0)

    def _on_duration(self, ms: int) -> None:
        self.durationChanged.emit(ms / 1000.0)

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlayingState
        self.playingChanged.emit(playing)
        if not playing:
            self._timer.stop()

    def _on_status(self, status) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self._timer.stop()
            self.finished.emit()
