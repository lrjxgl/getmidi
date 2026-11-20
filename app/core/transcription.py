"""MIDI 数据模型：音轨 / 音符，以及与 MIDI 文件的互转。"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Iterable

import mido

TICKS_PER_BEAT = 480
DEFAULT_BPM = 120.0

GM_PROGRAMS = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

TRACK_COLORS = [
    "#5b8def", "#f2994a", "#27ae60", "#bb6bd9", "#eb5757", "#56ccf2",
    "#f2c94c", "#2d9cdb", "#9b51e0", "#6fcf97", "#ff8fb1", "#4ecdc4",
]


def note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def program_name(program: int, is_drum: bool) -> str:
    if is_drum:
        return "Drums"
    return GM_PROGRAMS[program] if 0 <= program < len(GM_PROGRAMS) else f"Program {program}"


@dataclass
class Note:
    pitch: int
    start: float
    end: float
    velocity: int = 100


@dataclass
class Track:
    name: str
    program: int = 0
    is_drum: bool = False
    notes: list[Note] = field(default_factory=list)
    color: str = TRACK_COLORS[0]
    muted: bool = False
    solo: bool = False
    volume: float = 1.0

    @property
    def pitch_range(self) -> tuple[int, int]:
        if not self.notes:
            return 60, 60
        pitches = [n.pitch for n in self.notes]
        return min(pitches), max(pitches)


@dataclass
class Transcription:
    tracks: list[Track]
    duration: float = 0.0
    source_name: str = ""
    engine: str = ""
    bpm: float = DEFAULT_BPM

    @property
    def note_count(self) -> int:
        return sum(len(t.notes) for t in self.tracks)

    def audible_tracks(self) -> list[Track]:
        soloed = [t for t in self.tracks if t.solo]
        if soloed:
            return [t for t in soloed if not t.muted]
        return [t for t in self.tracks if not t.muted]

    def player_signature(self) -> tuple:
        """用于判断是否需要重新渲染音频的静音/独奏/音量签名。"""
        return tuple(
            (bool(t.muted), bool(t.solo), round(float(t.volume), 2)) for t in self.tracks
        )

    # ------------------------------------------------------------- midi out
    def to_midi_bytes(self, tracks: Iterable[Track] | None = None) -> bytes:
        tracks = list(self.tracks if tracks is None else tracks)
        # 使用 UTF-8 写入文本元数据，避免中文曲名/音轨名触发 latin-1 编码错误
        mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT, charset="utf-8")
        conductor = mido.MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(mido.MetaMessage("track_name", name=self.source_name or "GetMIDI", time=0))
        conductor.append(mido.MetaMessage("set_tempo", tempo=int(60_000_000 / max(1.0, self.bpm)), time=0))
        conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))

        ticks_per_sec = TICKS_PER_BEAT * max(1.0, self.bpm) / 60.0
        melodic_channels = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]

        for index, track in enumerate(tracks):
            midi_track = mido.MidiTrack()
            mid.tracks.append(midi_track)
            channel = 9 if track.is_drum else melodic_channels[index % len(melodic_channels)]
            midi_track.append(mido.MetaMessage("track_name", name=track.name, time=0))
            if not track.is_drum:
                midi_track.append(mido.Message("program_change", program=int(track.program) & 0x7F,
                                               channel=channel, time=0))
            volume = max(0.0, min(1.0, float(track.volume)))
            midi_track.append(mido.Message("control_change", channel=channel, control=7,
                                           value=int(round(volume * 127)), time=0))

            events: list[tuple[float, int, mido.Message]] = []
            for note in track.notes:
                start = max(0.0, float(note.start))
                end = max(start + 0.005, float(note.end))
                velocity = max(1, min(127, int(note.velocity)))
                events.append((start, 1, mido.Message("note_on", note=int(note.pitch) & 0x7F,
                                                      velocity=velocity, channel=channel)))
                events.append((end, 0, mido.Message("note_off", note=int(note.pitch) & 0x7F,
                                                    velocity=0, channel=channel)))
            # 同一时刻先 note_off 再 note_on，避免同音高重叠被吞掉
            events.sort(key=lambda item: (item[0], item[1]))
            last_tick = 0
            for when, _order, message in events:
                tick = int(round(when * ticks_per_sec))
                if tick < last_tick:
                    tick = last_tick
                message.time = tick - last_tick
                last_tick = tick
                midi_track.append(message)
            midi_track.append(mido.MetaMessage("end_of_track", time=0))

        buffer = io.BytesIO()
        mid.save(file=buffer)
        return buffer.getvalue()


def transcription_from_midi_bytes(data: bytes, source_name: str = "", engine: str = "") -> Transcription:
    """解析 MIDI（含 tempo map）为秒制的音轨数据。"""
    try:
        mid = mido.MidiFile(file=io.BytesIO(data), charset="utf-8")
    except UnicodeDecodeError:
        mid = mido.MidiFile(file=io.BytesIO(data))
    ticks_per_beat = mid.ticks_per_beat or TICKS_PER_BEAT

    events: list[tuple[int, int, mido.Message]] = []
    for track_index, midi_track in enumerate(mid.tracks):
        tick = 0
        for message in midi_track:
            tick += message.time
            events.append((tick, track_index, message))
    events.sort(key=lambda item: item[0])

    tempo = 500_000
    last_tick = 0
    now = 0.0
    end_time = 0.0
    meta: dict[int, dict] = {}
    open_notes: dict[tuple[int, int, int], list[tuple[float, int]]] = {}
    collected: dict[tuple[int, int], list[Note]] = {}

    for tick, track_index, message in events:
        now += (tick - last_tick) * tempo / 1_000_000.0 / ticks_per_beat
        last_tick = tick
        end_time = max(end_time, now)
        info = meta.setdefault(track_index, {"name": "", "program": 0})

        if message.type == "set_tempo":
            tempo = message.tempo
        elif message.type == "track_name":
            info["name"] = message.name.strip()
        elif message.type == "program_change" and message.channel != 9:
            info["program"] = message.program
        elif message.type == "note_on" and message.velocity > 0:
            key = (track_index, message.channel, message.note)
            open_notes.setdefault(key, []).append((now, message.velocity))
        elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
            key = (track_index, message.channel, message.note)
            starts = open_notes.get(key)
            if not starts:
                continue
            start, velocity = starts.pop(0)
            collected.setdefault((track_index, message.channel), []).append(
                Note(pitch=message.note, start=start, end=max(now, start + 0.01), velocity=velocity)
            )

    tracks: list[Track] = []
    for (track_index, channel), notes in collected.items():
        if not notes:
            continue
        info = meta.get(track_index, {"name": "", "program": 0})
        is_drum = channel == 9
        name = info["name"] or program_name(info["program"], is_drum)
        notes.sort(key=lambda n: (n.start, n.pitch))
        tracks.append(Track(name=name, program=info["program"], is_drum=is_drum, notes=notes))

    tracks.sort(key=lambda t: (t.is_drum, -len(t.notes)))
    for index, track in enumerate(tracks):
        track.color = TRACK_COLORS[index % len(TRACK_COLORS)]

    duration = max([end_time, max((n.end for t in tracks for n in t.notes), default=0.0)])
    return Transcription(tracks=tracks, duration=duration, source_name=source_name, engine=engine)
