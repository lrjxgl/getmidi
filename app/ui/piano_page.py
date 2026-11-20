"""主工作区：多音轨钢琴卷、走带控制与导出。"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QSplitter,
    QToolButton, QVBoxLayout, QWidget,
)

from .. import config
from ..core.audio_utils import human_time
from ..core.player import Player
from ..core.transcription import Transcription
from ..core.worker import RenderWorker
from .piano_roll import PianoRoll
from .track_panel import TrackPanel


class _TransportBar(QFrame):
    """底部走带栏：左状态、中间播放控件（严格水平居中）、右侧音色库与缩放。"""

    MARGIN = 16

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Transport")
        self.setFixedHeight(50)
        self._left = None
        self._center = None
        self._right = None

    def set_sections(self, left: QWidget, center: QWidget, right: QWidget) -> None:
        self._left, self._center, self._right = left, center, right
        for widget in (left, center, right):
            widget.setParent(self)
            widget.show()
        self.rebalance()

    def rebalance(self) -> None:
        if self._center is None or self.width() <= 0:
            return
        height = self.height()

        center_hint = self._center.sizeHint()
        cw, ch = center_hint.width(), min(center_hint.height(), height)
        cx = (self.width() - cw) // 2
        self._center.setGeometry(cx, (height - ch) // 2, cw, ch)

        right_hint = self._right.sizeHint()
        rw, rh = right_hint.width(), min(right_hint.height(), height)
        right_x = max(self.width() - self.MARGIN - rw, cx + cw + 8)
        self._right.setGeometry(right_x, (height - rh) // 2, rw, rh)

        left_hint = self._left.sizeHint()
        lh = min(left_hint.height(), height)
        left_w = max(0, cx - self.MARGIN - 8)
        self._left.setGeometry(self.MARGIN, (height - lh) // 2, left_w, lh)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.rebalance()


class PianoPage(QWidget):
    contentChanged = Signal(bool)
    importRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._transcription: Transcription | None = None
        self._player = Player(self)
        self._render_worker: RenderWorker | None = None
        self._rendered_sig = None
        self._render_sig = None
        self._wav_path: Path | None = None
        self._pending_seek: float | None = None
        self._position = 0.0
        self._render_dir = Path(tempfile.gettempdir()) / "getmidi_preview"

        self._build_ui()
        self._wire_player()
        self.clear()

    @property
    def transcription(self) -> Transcription | None:
        return self._transcription

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 14, 16, 12)
        workspace_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        self.track_panel = TrackPanel()
        self.roll = PianoRoll()

        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 10, 10)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(self.track_panel)

        splitter.addWidget(panel)
        splitter.addWidget(self.roll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([272, 1030])
        workspace_layout.addWidget(splitter, 1)

        layout.addWidget(workspace, 1)
        layout.addWidget(self._build_transport())

        self.track_panel.changed.connect(self._on_tracks_changed)
        self.track_panel.selected.connect(self.roll.set_active_track)
        self.roll.seekRequested.connect(self._seek)
        self.roll.playToggleRequested.connect(self._toggle_play)

        shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._toggle_play)

        self.refresh_soundfont()

    def _build_transport(self) -> QWidget:
        bar = _TransportBar()

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.status_label)
        left_layout.addStretch(1)

        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self.play_button = QPushButton("▶ 播放")
        self.play_button.setObjectName("Primary")
        self.play_button.setFixedWidth(96)
        self.play_button.clicked.connect(self._toggle_play)
        self.stop_button = QPushButton("■ 停止")
        self.stop_button.setObjectName("Ghost")
        self.stop_button.clicked.connect(self._stop)
        center_layout.addWidget(self.play_button)
        center_layout.addWidget(self.stop_button)
        center_layout.addSpacing(6)

        self.time_label = QLabel("00:00.0 / 00:00.0")
        self.time_label.setObjectName("Timecode")
        center_layout.addWidget(self.time_label)

        self.soundfont_chip = QLabel("")
        self.soundfont_chip.setObjectName("Chip")
        self.soundfont_chip.setToolTip("在“设置”中更换音色库")
        zoom_out = self._icon_button("−", "缩小 (Ctrl+滚轮 / 减号)", self.roll.zoom_out)
        zoom_in = self._icon_button("+", "放大 (Ctrl+滚轮 / 加号)", self.roll.zoom_in)
        right = QWidget()
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(self.soundfont_chip)
        right_layout.addWidget(zoom_out)
        right_layout.addWidget(zoom_in)

        bar.set_sections(left, center, right)
        self._transport_bar = bar
        self._transport_widgets = [self.play_button, self.stop_button, zoom_out, zoom_in]
        return bar

    def _icon_button(self, text: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tip)
        button.setFixedSize(28, 28)
        button.clicked.connect(slot)
        return button

    def _wire_player(self) -> None:
        self._player.positionChanged.connect(self._on_position)
        self._player.playingChanged.connect(self._on_playing)
        self._player.finished.connect(self._on_finished)

    # -------------------------------------------------------------- loading
    def load(self, transcription: Transcription) -> None:
        self._transcription = transcription
        self._player.stop()
        self._rendered_sig = None
        self._wav_path = None
        self._pending_seek = None
        self._position = 0.0

        self.track_panel.set_tracks(transcription.tracks)
        self.roll.set_transcription(transcription)
        self._update_time_label()
        self.status_label.setText("")
        self.play_button.setText("▶ 播放")
        self.refresh_soundfont()
        self._set_transport_enabled(True)
        self.contentChanged.emit(True)

    def clear(self) -> None:
        self._player.stop()
        self._transcription = None
        self._rendered_sig = None
        self._wav_path = None
        self._pending_seek = None
        self._position = 0.0
        self.track_panel.set_tracks([])
        self.roll.clear()
        self._update_time_label()
        self.status_label.setText("")
        self._set_transport_enabled(False)
        self.contentChanged.emit(False)

    def refresh_soundfont(self) -> None:
        path = config.soundfont_path()
        name = path.name if path.exists() else "未设置音色库"
        self.soundfont_chip.setText(f"音色库 {name}")
        self._transport_bar.rebalance()

    def _set_transport_enabled(self, enabled: bool) -> None:
        for widget in self._transport_widgets:
            widget.setEnabled(enabled)

    # ------------------------------------------------------------- playback
    def _toggle_play(self) -> None:
        if self._transcription is None:
            return
        if self._player.is_playing():
            self._player.pause()
            return
        audible = [t for t in self._transcription.audible_tracks() if t.notes]
        if not audible:
            self.status_label.setText("当前没有可播放的音轨")
            return
        if self._rendered_sig != self._transcription.player_signature() or not self._wav_path:
            self._start_render(audible, autoplay=True)
            return
        if self._player.loaded_path() != self._wav_path:
            self._player.load(self._wav_path, autoplay=True)
        else:
            self._player.play()
        if self._pending_seek is not None:
            self._player.seek(self._pending_seek)
            self._pending_seek = None

    def _start_render(self, tracks, autoplay: bool) -> None:
        if self._render_worker is not None and self._render_worker.isRunning():
            return
        self._player.stop()
        self.status_label.setText("正在使用 SoundFont 合成音频…")
        self.play_button.setEnabled(False)
        self._render_dir.mkdir(parents=True, exist_ok=True)
        out = self._render_dir / f"preview_{uuid.uuid4().hex[:8]}.wav"
        self._render_sig = self._transcription.player_signature()
        worker = RenderWorker(self._transcription, tracks, config.soundfont_path(), out)
        worker.succeeded.connect(lambda path: self._on_render_ok(path, autoplay))
        worker.failed.connect(self._on_render_failed)
        worker.finished.connect(lambda: self.play_button.setEnabled(self._transcription is not None))
        self._render_worker = worker
        worker.start()

    def _on_render_ok(self, path: str, autoplay: bool) -> None:
        old = self._wav_path
        self._wav_path = Path(path)
        self._rendered_sig = self._render_sig
        self.status_label.setText("")
        self._player.load(self._wav_path, autoplay=autoplay)
        if self._pending_seek is not None:
            pending = self._pending_seek
            self._pending_seek = None
            QTimer.singleShot(200, lambda: self._player.seek(pending))
        if old and old != self._wav_path:
            try:
                old.unlink(missing_ok=True)
            except OSError:
                pass

    def _on_render_failed(self, message: str) -> None:
        self.status_label.setText("合成失败")
        QMessageBox.warning(self, "无法播放", message)

    def _stop(self) -> None:
        self._player.stop()
        self._position = 0.0
        self._pending_seek = None
        self.roll.set_position(0.0, follow=False)
        self._update_time_label()

    def _seek(self, seconds: float) -> None:
        if self._transcription is None:
            return
        seconds = max(0.0, min(seconds, self._transcription.duration))
        self._position = seconds
        self.roll.set_position(seconds, follow=False)
        self._update_time_label()
        if self._wav_path is not None and self._rendered_sig == self._transcription.player_signature():
            self._player.seek(seconds)
            self._pending_seek = None
        else:
            self._pending_seek = seconds

    def _on_position(self, seconds: float) -> None:
        self._position = seconds
        self.roll.set_position(seconds, follow=self._player.is_playing())
        self._update_time_label()

    def _on_playing(self, playing: bool) -> None:
        self.play_button.setText("暂停" if playing else "▶ 播放")

    def _on_finished(self) -> None:
        self._position = 0.0
        self.roll.set_position(0.0, follow=True)
        self._update_time_label()
        self.play_button.setText("▶ 播放")

    def _update_time_label(self) -> None:
        duration = self._transcription.duration if self._transcription else 0.0

        def fmt(seconds: float) -> str:
            minutes, rest = divmod(max(0.0, seconds), 60.0)
            return f"{int(minutes):02d}:{rest:04.1f}"

        self.time_label.setText(f"{fmt(self._position)} / {fmt(duration)}")

    def _on_tracks_changed(self) -> None:
        self._player.stop()
        self._rendered_sig = None
        self.status_label.setText("音轨已更新，播放时将重新合成")
        self.roll.viewport().update()
