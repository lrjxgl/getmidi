"""导出：单个 MIDI、单个 WAV，或含分轨的 ZIP 包。"""
from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

from .render import render_wav
from .transcription import Transcription

_INVALID = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

Progress = Callable[[str], None] | None


def safe_stem(name: str, fallback: str = "output") -> str:
    cleaned = _INVALID.sub("_", (name or "").strip())
    cleaned = re.sub(r"\s*_\s*", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
    return cleaned[:60] or fallback


def export_midi(transcription: Transcription, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(transcription.to_midi_bytes())
    return path


def export_wav(
    transcription: Transcription, tracks, soundfont: Path, path: Path, progress: Progress = None
) -> Path:
    if progress:
        progress("正在渲染音频…")
    return render_wav(transcription, tracks, soundfont, Path(path))


def export_bundle(
    transcription: Transcription,
    tracks,
    soundfont: Path,
    path: Path,
    progress: Progress = None,
) -> Path:
    """导出 ZIP：混音 MIDI/WAV，以及每条音轨单独的 MIDI/WAV。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = safe_stem(transcription.source_name)
    current = [t for t in transcription.tracks if t.notes]

    def report(message: str) -> None:
        if progress:
            progress(message)

    with tempfile.TemporaryDirectory(prefix="getmidi_export_") as tmp:
        root = Path(tmp)
        (root / "tracks").mkdir()
        (root / f"{stem}.mid").write_bytes(transcription.to_midi_bytes())
        report("正在渲染混音 WAV…")
        render_wav(transcription, tracks, soundfont, root / f"{stem}.wav")

        for index, track in enumerate(current):
            track_stem = f"{index + 1:02d}_{safe_stem(track.name, 'track')}"
            report(f"正在导出分轨 {index + 1}/{len(current)}：{track.name}")
            (root / "tracks" / f"{track_stem}.mid").write_bytes(
                transcription.to_midi_bytes([track])
            )
            render_wav(transcription, [track], soundfont, root / "tracks" / f"{track_stem}.wav")

        report("正在打包…")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(root.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(root))
    return path
