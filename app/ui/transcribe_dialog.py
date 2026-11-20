"""转录进度对话框：显示进度与引擎日志，完成后返回转录结果。"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QVBoxLayout,
)

from .. import config
from ..core.audio_utils import human_size, human_time, audio_duration
from ..core.transcription import Transcription
from ..core.worker import TranscribeWorker

_DEVICE_LABELS = {"auto": "自动", "cuda": "GPU（CUDA）", "cpu": "CPU"}


class TranscribeDialog(QDialog):
    """模态进度框：音频 → MIDI。成功时 accept()，结果在 transcription 属性。"""

    def __init__(self, audio: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在转录")
        self.setModal(True)
        self.setMinimumWidth(580)

        self.transcription: Transcription | None = None
        self._worker: TranscribeWorker | None = None
        self._audio = audio
        self._started_at = 0.0

        model_key = config.current_model()
        device = config.current_device()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)

        title = QLabel("正在转录音频")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        name = QLabel(audio.name)
        name.setObjectName("FileName")
        detail = f"{human_size(audio.stat().st_size) if audio.exists() else ''}"
        duration = audio_duration(audio)
        if duration:
            detail += f" · 时长 {human_time(duration)}"
        detail += f" · {config.model_label(model_key)} · {_DEVICE_LABELS.get(device, device)}"
        meta = QLabel(detail)
        meta.setObjectName("Hint")
        layout.addWidget(name)
        layout.addWidget(meta)
        layout.addSpacing(4)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        self.status = QLabel("准备中…")
        self.status.setObjectName("Muted")
        layout.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        self.log.setMaximumBlockCount(500)
        layout.addWidget(self.log)

        footer = QHBoxLayout()
        self.elapsed = QLabel("")
        self.elapsed.setObjectName("Hint")
        footer.addWidget(self.elapsed)
        footer.addStretch(1)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self._on_cancel)
        footer.addWidget(self.cancel_button)
        layout.addLayout(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

        QTimer.singleShot(0, self._start)

    # ------------------------------------------------------------- running
    def _start(self) -> None:
        self._started_at = time.monotonic()
        self._timer.start()
        worker = TranscribeWorker(self._audio, config.current_model(), config.current_device())
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._append_log)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _on_progress(self, value: int, message: str) -> None:
        if value <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(value)
        if message:
            self.status.setText(message)

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_succeeded(self, transcription: Transcription) -> None:
        self._timer.stop()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status.setText("转换完成")
        self.transcription = transcription
        if self._worker is not None:
            self._worker.wait(3000)
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._timer.stop()
        if self._worker is not None:
            self._worker.wait(3000)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        short = message.strip().splitlines()[0][:220] if message.strip() else "未知错误"
        self.status.setObjectName("Error")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(f"转换失败：{short}")
        self.cancel_button.setText("关闭")
        if "huggingface" in message.lower() or "connect" in message.lower():
            self._append_log("提示：无法访问 Hugging Face 时，可在“设置 → 模型管理”中切换到 hf-mirror 镜像。")

    def _tick(self) -> None:
        if not self._started_at:
            return
        elapsed = time.monotonic() - self._started_at
        self.elapsed.setText(f"已用时 {int(elapsed)} 秒")

    # ------------------------------------------------------------- closing
    def _worker_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _confirm_stop(self) -> bool:
        answer = QMessageBox.question(
            self, "正在转录", "模型仍在处理中，停止后会丢失当前结果，确定停止吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _stop_worker(self) -> None:
        if self._worker_running():
            self._worker.terminate()
            self._worker.wait(1500)

    def _on_cancel(self) -> None:
        if self._worker_running() and not self._confirm_stop():
            return
        self._stop_worker()
        self.reject()

    def closeEvent(self, event):
        if self._worker_running():
            if not self._confirm_stop():
                event.ignore()
                return
            self._stop_worker()
        super().closeEvent(event)
