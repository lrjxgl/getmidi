"""多音轨钢琴卷帘绘制控件。"""
from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QFrame, QWidget

from ..core.audio_utils import human_time
from ..core.transcription import Transcription, note_name

KEY_W = 62
RULER_H = 24
MIN_NOTE_H = 4
MAX_NOTE_H = 22

_BLACK_KEYS = {1, 3, 6, 8, 10}


class PianoRoll(QAbstractScrollArea):
    seekRequested = Signal(float)
    playToggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

        corner = QWidget()
        corner.setAutoFillBackground(True)
        palette = corner.palette()
        palette.setColor(corner.backgroundRole(), QColor("#141720"))
        corner.setPalette(palette)
        self.setCornerWidget(corner)

        self._transcription: Transcription | None = None
        self._pps = 110.0
        self._note_h = 9
        self._position = 0.0
        self._active_track: int | None = None
        self._seeking = False

        self.horizontalScrollBar().valueChanged.connect(lambda _: self.viewport().update())
        self.verticalScrollBar().valueChanged.connect(lambda _: self.viewport().update())

    # ------------------------------------------------------------- public
    def set_transcription(self, transcription: Transcription) -> None:
        self._transcription = transcription
        self._active_track = None
        self._position = 0.0
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._edit_scale(100.0, keep_time=self._time_at(KEY_W))
        self._update_scrollbars()
        melodic = [n.pitch for t in transcription.tracks if not t.is_drum for n in t.notes]
        pitches = melodic or [n.pitch for t in transcription.tracks for n in t.notes]
        if pitches:
            top = min(127, max(pitches) + 5)
            bottom = max(0, min(pitches) - 5)
            self._note_h = 9
            self._fit_pitch_view(top, bottom)
        self.viewport().update()

    def clear(self) -> None:
        self._transcription = None
        self._active_track = None
        self._position = 0.0
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.horizontalScrollBar().setValue(0)
        self._update_scrollbars()
        self._fit_pitch_view(84, 36)
        self.viewport().update()

    def set_position(self, seconds: float, follow: bool = True) -> None:
        self._position = max(0.0, seconds)
        if follow and self._transcription is not None:
            x = self._x_for_time(self._position)
            width = self.viewport().width() - KEY_W
            if x < KEY_W + 30 or x > self.viewport().width() - 60:
                target = int(self._position * self._pps - width * 0.25)
                self.horizontalScrollBar().setValue(max(0, target))
        self.viewport().update()

    def set_active_track(self, index: int | None) -> None:
        self._active_track = index
        self.viewport().update()

    def zoom_in(self) -> None:
        self._zoom(1.25)

    def zoom_out(self) -> None:
        self._zoom(0.8)

    # ------------------------------------------------------------- helpers
    def _zoom(self, factor: float) -> None:
        anchor = self.viewport().width() / 2
        time = self._time_at(anchor)
        self._edit_scale(self._pps * factor, keep_time=time, anchor_x=anchor)

    def _edit_scale(self, new_pps: float, keep_time: float = 0.0, anchor_x: float = KEY_W) -> None:
        self._pps = max(18.0, min(900.0, new_pps))
        self._update_scrollbars()
        target = int(keep_time * self._pps - max(0.0, anchor_x - KEY_W))
        self.horizontalScrollBar().setValue(max(0, target))
        self.viewport().update()

    def _time_at(self, x: float) -> float:
        return (x - KEY_W + self.horizontalScrollBar().value()) / self._pps

    def _x_for_time(self, seconds: float) -> float:
        return KEY_W + seconds * self._pps - self.horizontalScrollBar().value()

    def _fit_pitch_view(self, top_pitch: int, bottom_pitch: int) -> None:
        available = max(60, self.viewport().height() - RULER_H)
        span = max(12, top_pitch - bottom_pitch + 1)
        self._note_h = int(max(MIN_NOTE_H, min(MAX_NOTE_H, available / span)))
        self._update_scrollbars()
        center = (top_pitch + bottom_pitch) / 2
        top_y = RULER_H + available / 2 - (127 - center) * self._note_h
        self.verticalScrollBar().setValue(int(max(0, RULER_H - top_y)))

    def _update_scrollbars(self) -> None:
        duration = self._transcription.duration if self._transcription else 0.0
        content_w = int(max(duration * self._pps, 1))
        content_h = 128 * self._note_h
        viewport = self.viewport()

        hbar = self.horizontalScrollBar()
        hbar.setRange(0, max(0, content_w - (viewport.width() - KEY_W)))
        hbar.setPageStep(max(50, viewport.width() - KEY_W))
        hbar.setSingleStep(40)

        vbar = self.verticalScrollBar()
        vbar.setRange(0, max(0, content_h - (viewport.height() - RULER_H)))
        vbar.setPageStep(max(50, viewport.height() - RULER_H))
        vbar.setSingleStep(max(1, self._note_h))

    # -------------------------------------------------------------- events
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._transcription is None:
            self._fit_pitch_view(84, 36)
        else:
            self._update_scrollbars()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space:
            self.playToggleRequested.emit()
            return
        if key in (Qt.Key_Left, Qt.Key_Right):
            step = 5.0 if event.modifiers() & Qt.ShiftModifier else 1.0
            self.seekRequested.emit(max(0.0, self._position + (-step if key == Qt.Key_Left else step)))
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_in()
            return
        if key == Qt.Key_Minus:
            self.zoom_out()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is not self.viewport():
            return super().eventFilter(obj, event)
        etype = event.type()
        if etype in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.Wheel):
            if etype == QEvent.Wheel:
                return self._handle_wheel(event)
            if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                pos = event.position()
                if pos.y() <= RULER_H and pos.x() > KEY_W:
                    self._seeking = True
                    self.seekRequested.emit(max(0.0, self._time_at(pos.x())))
                    return True
                if pos.y() > RULER_H:
                    self.setFocus()
            elif etype == QEvent.MouseMove and self._seeking:
                self.seekRequested.emit(max(0.0, self._time_at(event.position().x())))
                return True
            elif etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._seeking:
                    self._seeking = False
                    return True
        return super().eventFilter(obj, event)

    def _handle_wheel(self, event) -> bool:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            x = event.position().x()
            time = self._time_at(x)
            self._edit_scale(self._pps * (1.15 if delta > 0 else 1 / 1.15), keep_time=time, anchor_x=x)
            return True
        if event.modifiers() & Qt.ShiftModifier:
            hbar = self.horizontalScrollBar()
            hbar.setValue(hbar.value() - delta)
            return True
        return False

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.viewport().width()
        height = self.viewport().height()
        painter.fillRect(0, 0, width, height, QColor("#141720"))

        hscroll = self.horizontalScrollBar().value()
        vscroll = self.verticalScrollBar().value()
        note_h = self._note_h
        pps = self._pps
        top_y = RULER_H - vscroll

        view = QRectF(KEY_W, RULER_H, width - KEY_W, height - RULER_H)
        painter.setClipRect(view)
        self._draw_rows(painter, view, top_y, note_h)
        self._draw_grid(painter, view, pps, hscroll)

        if self._transcription is not None:
            audible = {id(track) for track in self._transcription.audible_tracks()}
            for index, track in enumerate(self._transcription.tracks):
                if id(track) not in audible:
                    continue
                self._draw_track(painter, track, index, top_y, note_h, pps, hscroll, view)
            self._draw_playhead(painter, view, pps, hscroll)
        painter.setClipping(False)

        self._draw_ruler(painter, width, pps, hscroll)
        self._draw_keys(painter, height, top_y, note_h)
        self._draw_corner(painter)

        painter.setPen(QPen(QColor("#2b3040"), 1))
        painter.drawLine(KEY_W, 0, KEY_W, height)
        painter.drawLine(KEY_W, RULER_H, width, RULER_H)

        if self._transcription is None:
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            painter.setPen(QColor("#5c6478"))
            painter.drawText(
                view, Qt.AlignCenter,
                "等待导入音频\n点击顶部「导入音频」，或把音频拖进窗口",
            )

    def _draw_rows(self, painter, view, top_y, note_h):
        painter.setPen(Qt.NoPen)
        for pitch in range(128):
            y = top_y + (127 - pitch) * note_h
            if y > view.bottom() or y + note_h < view.top():
                continue
            if pitch % 12 in _BLACK_KEYS:
                color = QColor("#171b24")
            else:
                color = QColor("#1b1f29") if pitch % 2 == 0 else QColor("#191d26")
            painter.fillRect(QRectF(KEY_W, y, view.width(), note_h), color)
            if pitch % 12 == 0 and note_h >= 7:
                painter.setPen(QPen(QColor("#242a37"), 1))
                painter.drawLine(QPointF(KEY_W, y + note_h - 0.5), QPointF(view.right(), y + note_h - 0.5))
                painter.setPen(Qt.NoPen)

    def _draw_grid(self, painter, view, pps, hscroll):
        duration = self._transcription.duration if self._transcription else 0
        beat = 0.5
        if pps < 26:
            beat = 2.0
        painter.setPen(QPen(QColor("#20252f"), 1))
        t = 0.0
        while t <= duration + 1:
            x = KEY_W + t * pps - hscroll
            if x > view.right():
                break
            if x >= view.left():
                painter.drawLine(QPointF(x, view.top()), QPointF(x, view.bottom()))
            t += beat
        painter.setPen(QPen(QColor("#2a3140"), 1))
        t = 0.0
        while t <= duration + 1:
            x = KEY_W + t * pps - hscroll
            if x > view.right():
                break
            if x >= view.left():
                painter.drawLine(QPointF(x, view.top()), QPointF(x, view.bottom()))
            t += 2.0
        if pps >= 220:
            painter.setPen(QPen(QColor("#1b202a"), 1))
            t = 0.0
            while t <= duration + 1:
                x = KEY_W + t * pps - hscroll
                if x > view.right():
                    break
                if x >= view.left():
                    painter.drawLine(QPointF(x, view.top()), QPointF(x, view.bottom()))
                t += 0.125

    def _draw_track(self, painter, track, index, top_y, note_h, pps, hscroll, view):
        if track.muted:
            base = QColor("#3a3f4d")
        else:
            base = QColor(track.color)
            if self._active_track is not None and self._active_track != index:
                base.setAlpha(80)

        painter.setRenderHint(QPainter.Antialiasing, True)
        for note in track.notes:
            x = KEY_W + note.start * pps - hscroll
            note_w = max(2.5, (note.end - note.start) * pps)
            if x > view.right() or x + note_w < view.left():
                continue
            y = top_y + (127 - note.pitch) * note_h
            if y > view.bottom() or y + note_h < view.top():
                continue
            rect = QRectF(x, y + 0.5, note_w, max(2.0, note_h - 1.5))
            color = QColor(base)
            if not track.muted:
                color.setAlpha(150 + int(105 * min(1.0, note.velocity / 110.0)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            radius = min(3.0, rect.height() / 2)
            painter.drawRoundedRect(rect, radius, radius)
        painter.setBrush(Qt.NoBrush)

    def _draw_playhead(self, painter, view, pps, hscroll):
        x = KEY_W + self._position * pps - hscroll
        if view.left() <= x <= view.right():
            painter.setPen(QPen(QColor("#ff6b6b"), 1.6))
            painter.drawLine(QPointF(x, view.top()), QPointF(x, view.bottom()))

    def _draw_ruler(self, painter, width, pps, hscroll):
        rect = QRectF(KEY_W, 0, width - KEY_W, RULER_H)
        painter.fillRect(rect, QColor("#191c25"))
        painter.setPen(QPen(QColor("#2b3040"), 1))
        painter.drawLine(QPointF(KEY_W, RULER_H - 0.5), QPointF(width, RULER_H - 0.5))

        steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300]
        step = next((s for s in steps if s * pps >= 64), steps[-1])
        duration = self._transcription.duration if self._transcription else 0
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)

        t = math.floor((hscroll / pps) / step) * step
        while t <= duration + step:
            x = KEY_W + t * pps - hscroll
            if x > width:
                break
            if x >= KEY_W:
                painter.setPen(QPen(QColor("#3a4254"), 1))
                painter.drawLine(QPointF(x, RULER_H - 6), QPointF(x, RULER_H))
                painter.setPen(QColor("#8b93a7"))
                painter.drawText(QPointF(x + 4, RULER_H - 8), human_time(t))
            t += step

        play_x = KEY_W + self._position * pps - hscroll
        if KEY_W <= play_x <= width:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ff6b6b"))
            path = QPainterPath()
            path.moveTo(play_x - 5, 2)
            path.lineTo(play_x + 5, 2)
            path.lineTo(play_x, 9)
            path.closeSubpath()
            painter.drawPath(path)
            painter.setBrush(Qt.NoBrush)

    def _draw_keys(self, painter, height, top_y, note_h):
        painter.fillRect(QRectF(0, RULER_H, KEY_W, height - RULER_H), QColor("#1a1d26"))
        font = QFont(painter.font())
        font.setPointSize(7)
        painter.setFont(font)
        for pitch in range(128):
            y = top_y + (127 - pitch) * note_h
            if y > height or y + note_h < RULER_H:
                continue
            is_black = pitch % 12 in _BLACK_KEYS
            rect = QRectF(0, y, KEY_W, note_h)
            if is_black:
                painter.fillRect(QRectF(0, y, KEY_W * 0.62, note_h), QColor("#0e1117"))
                painter.setPen(QPen(QColor("#242a37"), 1))
                painter.drawLine(QPointF(KEY_W * 0.62, y), QPointF(KEY_W * 0.62, y + note_h))
            else:
                painter.fillRect(rect, QColor("#d7dce7"))
                painter.setPen(QPen(QColor("#aeb5c4"), 1))
                painter.drawLine(QPointF(0, y + note_h - 0.5), QPointF(KEY_W, y + note_h - 0.5))

            if note_h >= 8:
                painter.setPen(QColor("#949db0") if is_black else QColor("#4a5162"))
                painter.drawText(
                    QRectF(KEY_W * 0.64, y, KEY_W * 0.36 - 3, note_h),
                    Qt.AlignRight | Qt.AlignVCenter, note_name(pitch),
                )
            elif note_h >= 5 and pitch % 12 == 0:
                font.setPointSize(6)
                painter.setFont(font)
                painter.setPen(QColor("#4a5162"))
                painter.drawText(
                    QRectF(KEY_W * 0.64, y, KEY_W * 0.36 - 3, note_h),
                    Qt.AlignRight | Qt.AlignVCenter, note_name(pitch),
                )
                font.setPointSize(7)
                painter.setFont(font)
        painter.setPen(QPen(QColor("#2b3040"), 1))
        painter.drawLine(QPointF(KEY_W - 0.5, RULER_H), QPointF(KEY_W - 0.5, height))

    def _draw_corner(self, painter):
        painter.fillRect(QRectF(0, 0, KEY_W, RULER_H), QColor("#20242f"))
        painter.setPen(QColor("#6b7385"))
        font = QFont(painter.font())
        font.setPointSize(7)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, KEY_W, RULER_H), Qt.AlignCenter, "音高")
