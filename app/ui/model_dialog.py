"""模型管理对话框：镜像 / Token / 下载到 models 目录。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from .. import config
from ..core.downloader import DownloadTask, DownloadWorker


@dataclass
class ModelItem:
    label: str
    repo: str
    dest: Path
    note: str = ""


def _items() -> list[ModelItem]:
    items = [
        ModelItem("Dettato · 转录器", config.DETTATO_REPOS["dettato"], config.DETTATO_WEIGHTS["dettato"]),
        ModelItem("Dettato · 证据修复", config.DETTATO_REPOS["dettato-evidence"], config.DETTATO_WEIGHTS["dettato-evidence"]),
        ModelItem("Dettato · 分轨", config.DETTATO_REPOS["dettato-grouper"], config.DETTATO_WEIGHTS["dettato-grouper"]),
        ModelItem("Dettato · 鼓组", config.DETTATO_REPOS["dettato-drums"], config.DETTATO_WEIGHTS["dettato-drums"]),
    ]
    for size, note in (("small", "约 103M 参数"), ("medium", "约 307M 参数"), ("large", "约 1.4B 参数")):
        items.append(ModelItem(
            f"MuScriptor · {size}", config.MUSCRIPTOR_REPOS[size],
            config.MODELS_DIR / f"muscriptor-{size}", note,
        ))
    return items


def _ready(dest: Path) -> bool:
    return all((dest / name).exists() for name in config.MODEL_FILES)


class ModelRow(QFrame):
    def __init__(self, item: ModelItem):
        super().__init__()
        self.item = item
        self.setObjectName("ModelRow")
        self.setStyleSheet(
            "QFrame#ModelRow { background: #1b1f2a; border: 1px solid #262b38; border-radius: 9px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        title = QLabel(item.label)
        title.setStyleSheet("font-size: 12.5px; font-weight: 600;")
        detail = QLabel(item.repo + (f" · {item.note}" if item.note else ""))
        detail.setStyleSheet("font-size: 11px; color: #7d8598;")
        text_box.addWidget(title)
        text_box.addWidget(detail)
        layout.addLayout(text_box, 1)

        self.status = QLabel("")
        self.status.setObjectName("Chip")
        layout.addWidget(self.status)
        self.button = QPushButton("下载")
        self.button.setFixedWidth(108)
        self.button.clicked.connect(lambda: self.window().download_one(self.item))
        layout.addWidget(self.button)
        self.refresh()

    def refresh(self) -> None:
        if _ready(self.item.dest):
            self.status.setText("已就绪")
            self.status.setStyleSheet(
                "background:#1d3327; border:1px solid #2a5a3c; border-radius:9px; "
                "padding:2px 9px; color:#6fcf97; font-size:11px;"
            )
            self.button.setText("重新下载")
        elif config.hub_cached(self.item.repo):
            self.status.setText("已缓存")
            self.status.setToolTip("已存在于 Hugging Face 缓存，可直接使用")
            self.status.setStyleSheet(
                "background:#1c2b3f; border:1px solid #2f4c70; border-radius:9px; "
                "padding:2px 9px; color:#7fb4ff; font-size:11px;"
            )
            self.button.setText("存到 models")
        else:
            self.status.setText("未下载")
            self.status.setStyleSheet(
                "background:#2a2333; border:1px solid #463a55; border-radius:9px; "
                "padding:2px 9px; color:#b49ad6; font-size:11px;"
            )
            self.button.setText("下载")


class ModelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模型管理")
        self.resize(760, 740)
        self._worker: DownloadWorker | None = None
        self._rows: dict[str, ModelRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        title = QLabel("模型管理")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        endpoint_row = QHBoxLayout()
        endpoint_row.setSpacing(8)
        endpoint_row.addWidget(QLabel("下载源"))
        self.endpoint_combo = QComboBox()
        self.endpoint_combo.addItem("HuggingFace 官方", config.HF_OFFICIAL)
        self.endpoint_combo.addItem("国内镜像 hf-mirror.com", config.HF_MIRROR)
        self.endpoint_combo.addItem("自定义", "custom")
        current = config.hf_endpoint()
        index = self.endpoint_combo.findData(current)
        if index >= 0:
            self.endpoint_combo.setCurrentIndex(index)
        else:
            self.endpoint_combo.setCurrentIndex(self.endpoint_combo.count() - 1)
        self.endpoint_combo.currentIndexChanged.connect(self._on_endpoint_changed)
        endpoint_row.addWidget(self.endpoint_combo, 1)
        self.custom_endpoint = QLineEdit(current if index < 0 else "")
        self.custom_endpoint.setPlaceholderText("https://…")
        self.custom_endpoint.setVisible(index < 0)
        endpoint_row.addWidget(self.custom_endpoint, 1)
        layout.addLayout(endpoint_row)

        token_row = QHBoxLayout()
        token_row.setSpacing(8)
        token_row.addWidget(QLabel("HF Token"))
        self.token_edit = QLineEdit(config.hf_token())
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("可选；MuScriptor 需要（先在模型页接受 CC BY-NC 4.0）")
        token_row.addWidget(self.token_edit, 1)
        layout.addLayout(token_row)

        hint = QLabel(
            "Dettato 使用 Apache-2.0 权重，可直接下载；MuScriptor 为受限模型，需要 HF Token。"
            "镜像源可能无法访问受限模型。也可手动把模型文件放入 models 目录后点击“刷新状态”。"
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        rows_layout = QVBoxLayout(container)
        rows_layout.setContentsMargins(0, 0, 6, 0)
        rows_layout.setSpacing(7)
        for item in _items():
            row = ModelRow(item)
            self._rows[item.label] = row
            rows_layout.addWidget(row)
        rows_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        dir_label = QLabel(f"模型目录：{config.MODELS_DIR}")
        dir_label.setObjectName("Hint")
        dir_row.addWidget(dir_label, 1)
        open_dir = QPushButton("打开目录")
        open_dir.setObjectName("Ghost")
        open_dir.clicked.connect(self._open_models_dir)
        dir_row.addWidget(open_dir)
        layout.addLayout(dir_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)
        self.log.setMaximumBlockCount(800)
        self.log.hide()
        layout.addWidget(self.log)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("Hint")
        buttons.addWidget(self.progress_label, 1)
        refresh = QPushButton("刷新状态")
        refresh.clicked.connect(self._refresh_rows)
        self.download_button = QPushButton("下载缺失模型")
        self.download_button.setObjectName("Primary")
        self.download_button.clicked.connect(self._download_missing)
        self.cancel_button = QPushButton("取消下载")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        buttons.addWidget(refresh)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.download_button)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------- helpers
    def _current_endpoint(self) -> str:
        data = self.endpoint_combo.currentData()
        if data == "custom":
            return self.custom_endpoint.text().strip() or config.HF_OFFICIAL
        return str(data)

    def _on_endpoint_changed(self, _index: int) -> None:
        self.custom_endpoint.setVisible(self.endpoint_combo.currentData() == "custom")

    def _save_settings(self) -> None:
        store = config.settings()
        store.setValue("hf/endpoint", self._current_endpoint())
        store.setValue("hf/token", self.token_edit.text().strip())

    def _open_models_dir(self) -> None:
        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.MODELS_DIR)))

    def _refresh_rows(self) -> None:
        for row in self._rows.values():
            row.refresh()

    def _missing(self) -> list[ModelItem]:
        return [
            row.item for row in self._rows.values()
            if not _ready(row.item.dest) and not config.hub_cached(row.item.repo)
        ]

    # ------------------------------------------------------------- download
    def download_one(self, item: ModelItem) -> None:
        self._start([item])

    def _download_missing(self) -> None:
        missing = self._missing()
        if not missing:
            self.log.appendPlainText("所有模型均已就绪。")
            return
        self._start(missing)

    def _start(self, items: list[ModelItem]) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._save_settings()
        endpoint = self._current_endpoint()
        token = self.token_edit.text().strip()
        tasks = [DownloadTask(item.label, item.repo, item.dest) for item in items]
        worker = DownloadWorker(tasks, endpoint, token)
        worker.log.connect(self.log.appendPlainText)
        worker.task_started.connect(lambda label: self.progress_label.setText(f"正在下载 {label}"))
        worker.task_finished.connect(self._on_task_finished)
        worker.all_finished.connect(self._on_all_finished)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        for row in self._rows.values():
            row.button.setEnabled(False)
        self.log.appendPlainText(f"下载源：{endpoint}")
        self.log.show()
        worker.start()

    def _on_task_finished(self, label: str, ok: bool, _message: str) -> None:
        row = self._rows.get(label)
        if row is not None:
            row.refresh()

    def _on_all_finished(self, ok: bool) -> None:
        self.progress_label.setText("下载完成" if ok else "下载结束（存在失败项）")
        self._refresh_rows()
        self.log.appendPlainText("全部任务结束。可点击“刷新状态”确认结果。")

    def _on_worker_finished(self) -> None:
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        for row in self._rows.values():
            row.button.setEnabled(True)

    def _cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.progress_label.setText("正在取消…")

    def closeEvent(self, event):
        self._save_settings()
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
