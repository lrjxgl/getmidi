"""音频文件预处理。"""
from __future__ import annotations

from pathlib import Path

AUDIO_EXTENSIONS = (
    ".wav", ".mp3", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".aiff", ".aif", ".wma", ".opus",
)


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


def audio_duration(path: Path) -> float:
    """尽量用 soundfile 读取时长；失败时返回 0（不阻塞流程）。"""
    try:
        import soundfile as sf

        info = sf.info(str(path))
        return float(info.frames) / float(info.samplerate)
    except Exception:
        return 0.0


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def human_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes, sec = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"
