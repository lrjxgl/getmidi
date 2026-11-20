"""转录引擎封装：dettato 与 MuScriptor。"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path
from typing import Callable

from .. import config
from .transcription import TRACK_COLORS, Note, Track, Transcription, transcription_from_midi_bytes

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, str], None]


def resolve_device(device: str) -> str:
    if device in ("auto", "", None):
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    if device.startswith("cuda"):
        try:
            import torch

            if not torch.cuda.is_available():
                return "cpu"
        except Exception:
            return "cpu"
    return device


class _StreamToLog(io.TextIOBase):
    def __init__(self, log: LogFn):
        self._log = log
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._log(line)
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            self._log(self._buffer.strip())
        self._buffer = ""


@contextlib.contextmanager
def capture_output(log: LogFn):
    """把第三方库写到 stdout/stderr 的进度信息转成界面日志。"""
    stream = _StreamToLog(log)
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = stream
        sys.stderr = stream
        yield
    finally:
        stream.flush()
        sys.stdout, sys.stderr = old_out, old_err


class TranscriptionEngine:
    label = "Base"

    def __init__(self, device: str = "auto"):
        self.device = resolve_device(device)

    def load(self, log: LogFn) -> None:
        raise NotImplementedError

    def transcribe(self, audio: Path, progress: ProgressFn, log: LogFn) -> Transcription:
        raise NotImplementedError


# ------------------------------------------------------------------ dettato
_DETTATO_CACHE: dict[str, object] = {}


class DettatoEngine(TranscriptionEngine):
    label = "Dettato"

    def load(self, log: LogFn) -> None:
        config.apply_hf_env()
        if config.dettato_local_ready():
            os.environ["DETTATO_WEIGHTS"] = str(config.DETTATO_DIR)
            config.set_hf_offline(False)
            log(f"使用本地模型：{config.DETTATO_DIR}")
        elif all(config.hub_cached(repo) for repo in config.DETTATO_REPOS.values()):
            config.set_hf_offline(True)
            log("使用 Hugging Face 本地缓存中的 Dettato 模型")
        else:
            config.set_hf_offline(False)
            log("本地未找到完整模型，将从 Hugging Face 下载（首次运行需要一些时间）")

        cached = _DETTATO_CACHE.get(self.device)
        if cached is not None:
            self.model = cached
            return

        import torch

        from dettato import Dettato

        log(f"加载 Dettato 模型（设备：{self.device}）…")
        model = Dettato.from_pretrained(self.device)
        _DETTATO_CACHE[self.device] = model
        self.model = model
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def transcribe(self, audio: Path, progress: ProgressFn, log: LogFn) -> Transcription:
        progress(15, "识别音符与乐器…")
        result = self.model.transcribe(str(audio))
        progress(90, "整理多音轨结果…")

        tracks: list[Track] = []
        for item in result.tracks:
            notes = [
                Note(pitch=int(row[2]), start=float(row[0]), end=float(row[1]), velocity=int(row[3]))
                for row in item.notes
            ]
            if not notes:
                continue
            tracks.append(Track(name=item.name, program=int(item.program), is_drum=bool(item.is_drum), notes=notes))

        tracks.sort(key=lambda t: (t.is_drum, -len(t.notes)))
        for index, track in enumerate(tracks):
            track.color = TRACK_COLORS[index % len(TRACK_COLORS)]
        transcription = Transcription(
            tracks=tracks,
            duration=float(result.seconds),
            source_name=audio.stem,
            engine=self.label,
        )
        log(f"完成：{len(tracks)} 条音轨，{transcription.note_count} 个音符")
        return transcription


# --------------------------------------------------------------- muscriptor
_MUSCRIPTOR_CACHE: dict[tuple[str, str], object] = {}


class MuscriptorEngine(TranscriptionEngine):
    def __init__(self, size: str = "small", device: str = "auto"):
        super().__init__(device)
        self.size = size
        self.label = f"MuScriptor {size}"

    def load(self, log: LogFn) -> None:
        config.apply_hf_env()
        config.set_hf_offline(False)
        key = (self.size, self.device)
        cached = _MUSCRIPTOR_CACHE.get(key)
        if cached is not None:
            self.model = cached
            return

        from muscriptor import TranscriptionModel

        local = config.muscriptor_local_path(self.size)
        if local is not None:
            weights = str(local / "model.safetensors")
            log(f"使用本地模型：{local}")
        else:
            weights = self.size
            log("本地未找到模型，将从 Hugging Face 下载。"
                "MuScriptor 需要先在模型页接受 CC BY-NC 4.0 协议并配置 HF Token。")

        log(f"加载 {self.label}（设备：{self.device}）…")
        self.model = TranscriptionModel.load_model(weights_path=weights, device=self.device)
        _MUSCRIPTOR_CACHE[key] = self.model

    def transcribe(self, audio: Path, progress: ProgressFn, log: LogFn) -> Transcription:
        progress(15, "识别音符并检测节拍…")
        midi_bytes, _grid = self.model.transcribe_and_postprocess(str(audio))
        progress(90, "整理多音轨结果…")
        transcription = transcription_from_midi_bytes(
            midi_bytes, source_name=audio.stem, engine=self.label
        )
        if not transcription.duration:
            transcription.duration = 0.0
        log(f"完成：{len(transcription.tracks)} 条音轨，{transcription.note_count} 个音符")
        return transcription


def create_engine(model_key: str, device: str = "auto") -> TranscriptionEngine:
    if model_key.startswith("muscriptor"):
        size = model_key.split("-", 1)[1] if "-" in model_key else "small"
        return MuscriptorEngine(size=size, device=device)
    return DettatoEngine(device=device)
