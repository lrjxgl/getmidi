"""模型下载：在独立子进程中调用 huggingface_hub，支持镜像与 Token。"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

_DOWNLOAD_SCRIPT = r"""
import sys
from huggingface_hub import snapshot_download

repo, dest, token, endpoint = sys.argv[1:5]
snapshot_download(
    repo_id=repo,
    local_dir=dest,
    token=token or None,
    endpoint=endpoint or None,
    allow_patterns=["*.json", "*.safetensors", "*.txt", "*.md", "*.model", "*.yaml"],
    max_workers=4,
)
print("DOWNLOAD_OK")
"""


@dataclass
class DownloadTask:
    label: str
    repo: str
    dest: Path


class DownloadWorker(QThread):
    log = Signal(str)
    task_started = Signal(str)
    task_finished = Signal(str, bool, str)
    all_finished = Signal(bool)

    def __init__(self, tasks: list[DownloadTask], endpoint: str, token: str, parent=None):
        super().__init__(parent)
        self._tasks = tasks
        self._endpoint = endpoint
        self._token = token
        self._cancelled = False
        self._process: subprocess.Popen | None = None

    def cancel(self) -> None:
        self._cancelled = True
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def run(self) -> None:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        if self._endpoint:
            env["HF_ENDPOINT"] = self._endpoint
        if self._token:
            env["HF_TOKEN"] = self._token
        env.pop("HF_HUB_OFFLINE", None)

        all_ok = True
        for task in self._tasks:
            if self._cancelled:
                all_ok = False
                break
            self.task_started.emit(task.label)
            self.log.emit(f"=== 开始下载 {task.label} → {task.dest}")
            task.dest.mkdir(parents=True, exist_ok=True)
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            try:
                self._process = subprocess.Popen(
                    [sys.executable, "-u", "-c", _DOWNLOAD_SCRIPT, task.repo, str(task.dest),
                     self._token or "", self._endpoint or ""],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creation_flags,
                )
                assert self._process.stdout is not None
                for line in self._process.stdout:
                    line = line.strip()
                    if line:
                        self.log.emit(line)
                    if self._cancelled:
                        self._process.terminate()
                        break
                code = self._process.wait()
            except Exception as exc:  # pragma: no cover - 依赖外部环境
                code = -1
                self.log.emit(f"下载进程启动失败：{exc}")

            ok = code == 0 and not self._cancelled
            if not ok:
                all_ok = False
                self.log.emit(f"=== {task.label} 下载失败（退出码 {code}）")
            else:
                self.log.emit(f"=== {task.label} 下载完成")
            self.task_finished.emit(task.label, ok, "")

        self.all_finished.emit(all_ok and not self._cancelled)
