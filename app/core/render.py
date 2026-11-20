"""使用 tinysoundfont + SoundFont 把转录结果渲染为可播放的 WAV。

纯 Python 依赖（pip 安装时自带 TinySoundFont 动态库），无需安装 fluidsynth 等外部程序。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
import tinysoundfont

from .transcription import Transcription

BLOCK_SIZE = 64      # 每块采样数，越小事件越精确（64 ≈ 1.45 ms）
TAIL_SECONDS = 2.0   # 末尾留白，用于释放音符尾音
MELODIC_CHANNELS = [channel for channel in range(16) if channel != 9]


class RenderError(RuntimeError):
    pass


def _collect_events(synth, tracks, soundfont_id: int) -> tuple[list[tuple], float]:
    """给每个音轨分配通道并生成按时间排序的 MIDI 事件列表。"""
    events: list[tuple] = []
    end = 0.0
    melodic_order = 0
    prepared: set[int] = set()

    for track in tracks:
        if not track.notes:
            continue
        channel = 9 if track.is_drum else MELODIC_CHANNELS[melodic_order % len(MELODIC_CHANNELS)]
        if not track.is_drum:
            melodic_order += 1
        else:
            melodic_order += 1

        if channel not in prepared:
            synth.program_select(
                channel, soundfont_id, 0, int(track.program) & 0x7F, is_drums=track.is_drum
            )
            volume = max(0.0, min(1.0, float(track.volume)))
            synth.control_change(channel, 7, int(round(volume * 127)))
            prepared.add(channel)

        for note in track.notes:
            pitch = max(0, min(127, int(note.pitch)))
            velocity = max(1, min(127, int(note.velocity)))
            events.append((float(note.start), 1, channel, pitch, velocity))
            events.append((float(note.end), 0, channel, pitch, 0))
            end = max(end, float(note.end))

    events.sort(key=lambda item: (item[0], item[1]))
    return events, end


def render_wav(
    transcription: Transcription,
    tracks,
    soundfont: Path,
    out_path: Path,
    gain: float = 1.8,
    sample_rate: int = 44100,
) -> Path:
    """把指定音轨渲染成 WAV。失败时抛出 RenderError（内含中文提示）。"""
    if not tracks or not any(t.notes for t in tracks):
        raise RenderError("没有可播放的音轨")
    if not Path(soundfont).exists():
        raise RenderError(f"未找到音色库文件：{soundfont}")

    try:
        synth = tinysoundfont.Synth(gain=0.0, samplerate=sample_rate)
        soundfont_id = synth.sfload(str(soundfont))
    except Exception as exc:  # noqa: BLE001 - 统一转换为中文错误
        raise RenderError(f"无法加载音色库：{exc}") from exc

    events, end = _collect_events(synth, tracks, soundfont_id)
    total = max(1, int((end + TAIL_SECONDS) * sample_rate))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    position = 0
    event_index = 0
    try:
        with sf.SoundFile(
            str(out_path), mode="w", samplerate=sample_rate, channels=2, subtype="PCM_16"
        ) as handle:
            while position < total:
                chunk = min(BLOCK_SIZE, total - position)
                limit = (position + chunk) / sample_rate
                while event_index < len(events) and events[event_index][0] < limit:
                    _, kind, channel, pitch, velocity = events[event_index]
                    if kind:
                        synth.noteon(channel, pitch, velocity)
                    else:
                        synth.noteoff(channel, pitch)
                    event_index += 1
                buffer = synth.generate(chunk)
                block = np.frombuffer(buffer, dtype=np.float32).reshape(-1, 2)
                block = np.clip(block * np.float32(gain), -1.0, 1.0)
                handle.write(block)
                position += block.shape[0]
    except Exception as exc:  # noqa: BLE001
        raise RenderError(f"音频渲染失败：{exc}") from exc
    finally:
        synth.stop()

    return out_path
