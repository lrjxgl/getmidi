"""设置：转录模型、计算设备、音色库与播放引擎。"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from .. import config
from .model_dialog import ModelDialog


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        layout.addWidget(self._divider())

        # ---------------------------------------------------------- 转录
        layout.addWidget(self._section("转录"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(self._label("转录模型"), 0, 0)
        self.model_combo = QComboBox()
        for key, label in config.MODEL_OPTIONS:
            self.model_combo.addItem(label, key)
        index = self.model_combo.findData(config.current_model())
        self.model_combo.setCurrentIndex(max(0, index))
        self.model_combo.setMinimumWidth(280)
        self.model_combo.currentIndexChanged.connect(self._refresh_hint)
        grid.addWidget(self.model_combo, 0, 1)

        grid.addWidget(self._label("计算设备"), 0, 2)
        self.device_combo = QComboBox()
        self.device_combo.addItem("自动", "auto")
        if shutil.which("nvidia-smi"):
            self.device_combo.addItem("GPU（CUDA）", "cuda")
        self.device_combo.addItem("CPU", "cpu")
        index = self.device_combo.findData(config.current_device())
        self.device_combo.setCurrentIndex(max(0, index))
        self.device_combo.setMinimumWidth(140)
        grid.addWidget(self.device_combo, 0, 3)

        self._hint = QLabel("")
        self._hint.setObjectName("Hint")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("font-size: 11.5px;")

        manage = QPushButton("模型管理…")
        manage.setObjectName("Ghost")
        manage.clicked.connect(self._manage_models)

        grid.addWidget(self._hint, 1, 0, 1, 3)
        grid.addWidget(manage, 1, 3, Qt.AlignRight)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        layout.addWidget(self._divider())

        # ---------------------------------------------------------- 音频
        layout.addWidget(self._section("音频"))
        self._soundfont = QLineEdit(str(config.soundfont_path()))
        self._soundfont.setReadOnly(True)
        layout.addLayout(self._path_row("SoundFont 音色库", self._soundfont, self._browse_soundfont))

        audio_hint = QLabel(
            "播放时用内置合成器把 MIDI 渲染为音频，无需安装 fluidsynth。"
            "默认音色库为 soundfont/GeneralUser-GS.sf2，也可换成任意 .sf2 / .sf3 文件。"
        )
        audio_hint.setObjectName("Hint")
        audio_hint.setWordWrap(True)
        audio_hint.setStyleSheet("font-size: 11.5px;")
        layout.addWidget(audio_hint)

        layout.addStretch(1)
        layout.addWidget(self._divider())

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        self._refresh_hint()

    # ------------------------------------------------------------- helpers
    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        return label

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        return line

    def _path_row(self, label: str, field: QLineEdit, browse_slot) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        tag = QLabel(label)
        tag.setFixedWidth(140)
        row.addWidget(tag)
        row.addWidget(field, 1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(browse_slot)
        row.addWidget(browse)
        return row

    def current_model_key(self) -> str:
        return str(self.model_combo.currentData())

    def _refresh_hint(self) -> None:
        self._hint.setText(config.model_hint(self.current_model_key()))

    def _manage_models(self) -> None:
        ModelDialog(self).exec()
        self._refresh_hint()

    def _browse_soundfont(self) -> None:
        current = self._soundfont.text()
        start = str(Path(current).parent) if current else str(config.DEFAULT_SF2.parent)
        path, _ = QFileDialog.getOpenFileName(self, "选择 SoundFont", start, "SoundFont (*.sf2 *.sf3)")
        if path:
            self._soundfont.setText(path)

    def _save(self) -> None:
        store = config.settings()
        store.setValue("transcribe/model", self.current_model_key())
        store.setValue("transcribe/device", str(self.device_combo.currentData()))
        store.setValue("audio/soundfont", self._soundfont.text().strip())
        store.remove("audio/fluidsynth")
        self.accept()
