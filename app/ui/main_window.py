"""主窗口：顶部彩带 + 钢琴卷工作区。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
    QProgressDialog, QPushButton, QVBoxLayout, QWidget,
)

from .. import config
from ..core import exporter
from ..core.audio_utils import AUDIO_EXTENSIONS, human_time, is_supported
from ..core.worker import ExportWorker
from .piano_page import PianoPage
from .settings_dialog import SettingsDialog
from .transcribe_dialog import TranscribeDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GetMIDI · 音频转 MIDI")
        self.resize(1360, 860)
        self.setMinimumSize(1080, 700)
        self.setAcceptDrops(True)

        shell = QWidget()
        shell.setObjectName("Shell")
        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_ribbon())

        self.piano_page = PianoPage()
        root.addWidget(self.piano_page, 1)
        self.setCentralWidget(shell)

        self.piano_page.importRequested.connect(self._import_audio)
        self.piano_page.contentChanged.connect(self._on_content_changed)

        import_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        import_shortcut.activated.connect(self._import_audio)

        self._restore_geometry()

    # ---------------------------------------------------------------- ribbon
    def _build_ribbon(self) -> QWidget:
        band = QFrame()
        band.setObjectName("Ribbon")
        row = QHBoxLayout(band)
        row.setContentsMargins(16, 8, 16, 6)
        row.setSpacing(14)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        logo = QLabel("GetMIDI")
        logo.setObjectName("Logo")
        sub = QLabel("音频转 MIDI")
        sub.setObjectName("LogoSub")
        brand.addWidget(logo)
        brand.addWidget(sub)
        row.addLayout(brand)
        row.addWidget(self._vline())

        self.import_button = QPushButton("导入音频")
        self.import_button.setObjectName("Primary")
        self.import_button.setMinimumSize(104, 32)
        self.import_button.clicked.connect(self._import_audio)

        self.export_button = QPushButton("导出")
        self.export_button.setMinimumHeight(32)
        self.export_button.setEnabled(False)
        menu = QMenu(self.export_button)
        menu.addAction("导出 MIDI…", self._export_midi)
        menu.addAction("导出 WAV…", self._export_wav)
        menu.addAction("导出 ZIP（含分轨）…", self._export_zip)
        self.export_button.setMenu(menu)

        row.addWidget(self._ribbon_group([self.import_button, self.export_button]))
        row.addWidget(self._vline())

        self.project_name = QLabel("未打开工程")
        self.project_name.setObjectName("ProjectName")
        self.project_stats = QLabel("导入一段音频开始转录")
        self.project_stats.setObjectName("Hint")
        self.project_stats.setStyleSheet("font-size: 11.5px;")
        info = QVBoxLayout()
        info.setSpacing(1)
        info.addWidget(self.project_name)
        info.addWidget(self.project_stats)
        row.addLayout(info, 1)

        settings = QPushButton("设置")
        settings.setObjectName("Ghost")
        settings.clicked.connect(self._open_settings)
        row.addWidget(settings)
        return band

    def _ribbon_group(self, buttons: list[QWidget]) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        line = QHBoxLayout()
        line.setSpacing(6)
        for button in buttons:
            line.addWidget(button)
        layout.addStretch(1)
        layout.addLayout(line)
        layout.addStretch(1)
        return box

    def _vline(self) -> QFrame:
        line = QFrame()
        line.setObjectName("VLine")
        return line

    # --------------------------------------------------------------- window
    def _restore_geometry(self) -> None:
        geometry = config.settings().value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        config.settings().setValue("window/geometry", self.saveGeometry())
        worker = getattr(self, "_export_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if urls and is_supported(Path(urls[0].toLocalFile())):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if is_supported(path):
                event.acceptProposedAction()
                self._import_path(path)

    # ------------------------------------------------------------ 状态刷新
    def _on_content_changed(self, loaded: bool) -> None:
        self.export_button.setEnabled(loaded)
        transcription = self.piano_page.transcription
        if loaded and transcription is not None:
            self.project_name.setText(transcription.source_name or "未命名")
            self.project_stats.setText(
                f"{len(transcription.tracks)} 轨 · {transcription.note_count} 音符 · "
                f"{human_time(transcription.duration)} · {transcription.engine}"
            )
        else:
            self.project_name.setText("未打开工程")
            self.project_stats.setText("导入一段音频开始转录")

    # --------------------------------------------------------------- actions
    def _import_audio(self) -> None:
        last_dir = str(config.settings().value("paths/last_audio_dir", str(Path.home())))
        patterns = "音频文件 (" + " ".join(f"*{ext}" for ext in AUDIO_EXTENSIONS) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "导入音频", last_dir, patterns)
        if path:
            config.settings().setValue("paths/last_audio_dir", str(Path(path).parent))
            self._import_path(Path(path))

    def _import_path(self, path: Path) -> None:
        if not path.exists() or not is_supported(path):
            QMessageBox.warning(self, "无法导入", "请选择 WAV / MP3 / FLAC / M4A / OGG 音频文件。")
            return
        dialog = TranscribeDialog(path, self)
        dialog.exec()
        transcription = dialog.transcription
        if transcription is None:
            return
        if not transcription.tracks or transcription.note_count == 0:
            QMessageBox.information(
                self, "没有识别到音符",
                "这段音频没有识别出可用音符，可以换一个模型或使用更清晰的音频再试。",
            )
            return
        self.piano_page.load(transcription)

    # -------------------------------------------------------------- 导出
    def _export_dir(self) -> Path:
        return Path(str(config.settings().value("paths/last_export_dir", str(Path.home()))))

    def _choose_export_path(self, title: str, suffix: str, file_filter: str) -> Path | None:
        transcription = self.piano_page.transcription
        if transcription is None:
            return None
        stem = exporter.safe_stem(transcription.source_name, "output")
        default = str(self._export_dir() / f"{stem}{suffix}")
        path, _ = QFileDialog.getSaveFileName(self, title, default, file_filter)
        if not path:
            return None
        target = Path(path)
        if target.suffix.lower() != suffix:
            target = target.with_name(target.name + suffix)
        config.settings().setValue("paths/last_export_dir", str(target.parent))
        return target

    def _audible_tracks(self):
        transcription = self.piano_page.transcription
        if transcription is None:
            return None
        tracks = [track for track in transcription.audible_tracks() if track.notes]
        if not tracks:
            QMessageBox.information(self, "无法导出", "当前没有可导出的音轨（可能都被静音了）。")
            return None
        return tracks

    def _export_midi(self) -> None:
        transcription = self.piano_page.transcription
        path = self._choose_export_path("导出 MIDI", ".mid", "MIDI 文件 (*.mid)")
        if transcription is None or path is None:
            return
        try:
            exporter.export_midi(transcription, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self.piano_page.status_label.setText(f"已导出 {path.name}")

    def _export_wav(self) -> None:
        transcription = self.piano_page.transcription
        tracks = self._audible_tracks()
        path = self._choose_export_path("导出 WAV", ".wav", "WAV 音频 (*.wav)")
        if transcription is None or tracks is None or path is None:
            return
        soundfont = config.soundfont_path()
        self._run_export(
            "正在导出 WAV…",
            lambda progress: exporter.export_wav(
                transcription, tracks, soundfont, path, progress
            ),
        )

    def _export_zip(self) -> None:
        transcription = self.piano_page.transcription
        tracks = self._audible_tracks()
        path = self._choose_export_path("导出 ZIP", ".zip", "ZIP 压缩包 (*.zip)")
        if transcription is None or tracks is None or path is None:
            return
        soundfont = config.soundfont_path()
        self._run_export(
            "正在导出 ZIP…",
            lambda progress: exporter.export_bundle(
                transcription, tracks, soundfont, path, progress
            ),
        )

    def _run_export(self, title: str, job) -> None:
        self._export_progress = QProgressDialog(title, "", 0, 0, self)
        self._export_progress.setWindowTitle("导出")
        self._export_progress.setCancelButton(None)
        self._export_progress.setWindowModality(Qt.WindowModal)
        self._export_progress.setMinimumDuration(150)
        self._export_progress.show()

        self._export_worker = ExportWorker(job, self)
        self._export_worker.log.connect(self._export_progress.setLabelText)
        self._export_worker.succeeded.connect(self._on_export_done)
        self._export_worker.failed.connect(self._on_export_failed)
        self._export_worker.start()

    def _on_export_done(self, path: str) -> None:
        self._export_progress.close()
        self.piano_page.status_label.setText(f"已导出 {Path(path).name}")
        QMessageBox.information(self, "导出完成", f"已保存到：\n{path}")

    def _on_export_failed(self, message: str) -> None:
        self._export_progress.close()
        QMessageBox.warning(self, "导出失败", message)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.piano_page.refresh_soundfont()
