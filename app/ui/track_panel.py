"""左侧音轨列表（静音 / 独奏 / 选择）。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider, QToolButton, QVBoxLayout,
    QWidget,
)

from ..core.transcription import Track, program_name


class ElidedLabel(QLabel):
    """宽度不足时自动以省略号截断。"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(10, self.width())))


class TrackRow(QFrame):
    muteToggled = Signal(int, bool)
    soloToggled = Signal(int, bool)
    selected = Signal(int)
    volumeChanged = Signal(int, int)
    volumeCommitted = Signal(int, int)

    def __init__(self, index: int, track: Track, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("TrackRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            """
            QFrame#TrackRow { background: #1b1f2a; border: 1px solid #262b38; border-radius: 9px; }
            QFrame#TrackRow[active="true"] { background: #222839; border: 1px solid #3d5480; }
            """
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 7, 8, 7)
        outer.setSpacing(4)

        layout = QHBoxLayout()
        layout.setSpacing(9)

        self._bar = QFrame()
        self._bar.setFixedSize(4, 30)
        self._bar.setStyleSheet(f"background: {track.color}; border-radius: 2px;")
        layout.addWidget(self._bar)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        name = ElidedLabel(track.name)
        name.setStyleSheet("font-weight: 600; font-size: 12.5px;")
        subtitle = ElidedLabel("打击乐" if track.is_drum else program_name(track.program, False))
        subtitle.setObjectName("Muted")
        subtitle.setStyleSheet("font-size: 11px; color: #7d8598;")
        text_box.addWidget(name)
        text_box.addWidget(subtitle)
        layout.addLayout(text_box, 1)

        self.mute_button = self._toggle_button("M", "静音此音轨")
        self.solo_button = self._toggle_button("S", "独奏此音轨")
        self.mute_button.toggled.connect(lambda checked: self.muteToggled.emit(self.index, checked))
        self.solo_button.toggled.connect(lambda checked: self.soloToggled.emit(self.index, checked))
        layout.addWidget(self.mute_button)
        layout.addWidget(self.solo_button)
        outer.addLayout(layout)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(6)
        tag = QLabel("音量")
        tag.setStyleSheet("font-size: 10.5px; color: #7d8598;")
        percent = int(round(max(0.0, min(1.0, float(track.volume))) * 100))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(percent)
        self.volume.setFixedHeight(16)
        self.volume.setCursor(Qt.PointingHandCursor)
        self.volume.setToolTip("音轨音量")
        self.volume_label = QLabel(f"{percent}%")
        self.volume_label.setStyleSheet("font-size: 10.5px; color: #7d8598;")
        self.volume_label.setFixedWidth(32)
        self.volume_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        volume_row.addWidget(tag)
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_label)
        outer.addLayout(volume_row)

        self.volume.valueChanged.connect(self._on_volume)
        self.volume.sliderReleased.connect(
            lambda: self.volumeCommitted.emit(self.index, self.volume.value())
        )

        self._name = name

    def _on_volume(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.volumeChanged.emit(self.index, value)
        if not self.volume.isSliderDown():
            self.volumeCommitted.emit(self.index, value)

    def _toggle_button(self, text: str, tip: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.setToolTip(tip)
        button.setFixedSize(26, 24)
        button.setStyleSheet(
            """
            QToolButton { border: 1px solid #2f3546; border-radius: 6px; color: #8b93a7;
                          font-size: 11px; font-weight: 700; background: transparent;
                          padding: 0px; }
            QToolButton:hover { color: #e8eaf2; border-color: #3f475c; }
            QToolButton:checked { background: #3a4d76; border-color: #5b8def; color: #dbe7ff; }
            """
        )
        return button

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.selected.emit(self.index)
        super().mousePressEvent(event)


class TrackPanel(QWidget):
    changed = Signal()
    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(252)
        self.setMaximumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("音轨")
        title.setObjectName("SectionTitle")
        self._count = QLabel("0")
        self._count.setObjectName("Chip")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._count)
        layout.addLayout(header)

        self._empty = QLabel("尚未导入音频\n\n点击顶部「导入音频」\n或把音频拖入窗口")
        self._empty.setObjectName("Hint")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet("font-size: 11.5px; color: #6b7385; padding-top: 24px;")
        layout.addWidget(self._empty, 1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._container.setObjectName("TrackList")
        self._rows_layout = QVBoxLayout(self._container)
        self._rows_layout.setContentsMargins(0, 0, 6, 0)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch(1)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        self._hint = QLabel("M 静音 · S 独奏 · 双击空处加音符")
        self._hint.setObjectName("Hint")
        self._hint.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._hint)

        self._tracks: list[Track] = []
        self._rows: list[TrackRow] = []
        self._active: int | None = None

    def set_tracks(self, tracks: list[Track]) -> None:
        self._tracks = tracks
        self._active = None
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []
        for index, track in enumerate(tracks):
            row = TrackRow(index, track)
            row.muteToggled.connect(self._on_mute)
            row.soloToggled.connect(self._on_solo)
            row.selected.connect(self._on_selected)
            row.volumeChanged.connect(self._on_volume)
            row.volumeCommitted.connect(lambda _index, _value: self.changed.emit())
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._rows.append(row)
        self._count.setText(str(len(tracks)))
        self._hint.setVisible(bool(tracks))
        self._empty.setVisible(not tracks)
        self._scroll.setVisible(bool(tracks))

    def set_active(self, index: int) -> None:
        self._active = index if index is not None and index >= 0 else None
        for row_index, row in enumerate(self._rows):
            row.set_active(row_index == self._active)

    def _on_mute(self, index: int, checked: bool) -> None:
        self._tracks[index].muted = checked
        self.changed.emit()

    def _on_solo(self, index: int, checked: bool) -> None:
        self._tracks[index].solo = checked
        self.changed.emit()

    def _on_volume(self, index: int, percent: int) -> None:
        if 0 <= index < len(self._tracks):
            self._tracks[index].volume = max(0, min(100, percent)) / 100.0

    def _on_selected(self, index: int) -> None:
        if self._active == index:
            self._active = None
        else:
            self._active = index
        for row_index, row in enumerate(self._rows):
            row.set_active(row_index == self._active)
        self.selected.emit(self._active if self._active is not None else -1)
