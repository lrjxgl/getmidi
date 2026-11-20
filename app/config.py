"""全局路径、模型仓库与持久化配置。"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_SF2 = MODELS_DIR / "GeneralUser-GS.sf2"

DETTATO_DIR = MODELS_DIR / "dettato_weights"
DETTATO_WEIGHTS = {
    "dettato": DETTATO_DIR / "dettato",
    "dettato-evidence": DETTATO_DIR / "dettato-evidence",
    "dettato-grouper": DETTATO_DIR / "dettato-grouper",
    "dettato-drums": DETTATO_DIR / "dettato-drums",
}

DETTATO_REPOS = {
    "dettato": "kobimusic/dettato",
    "dettato-evidence": "kobimusic/dettato-evidence",
    "dettato-grouper": "kobimusic/dettato-grouper",
    "dettato-drums": "kobimusic/dettato-drums",
}

MUSCRIPTOR_SIZES = ("small", "medium", "large")
MUSCRIPTOR_REPOS = {
    size: f"MuScriptor/muscriptor-{size}" for size in MUSCRIPTOR_SIZES
}

HF_OFFICIAL = "https://huggingface.co"
HF_MIRROR = "https://hf-mirror.com"

MODEL_FILES = ("config.json", "model.safetensors")

MODEL_OPTIONS = [
    ("dettato", "Dettato（推荐 · 多乐器分轨）"),
    ("muscriptor-small", "MuScriptor Small"),
    ("muscriptor-medium", "MuScriptor Medium"),
    ("muscriptor-large", "MuScriptor Large"),
]

_ORG = "GetMIDI"
_APP = "GetMIDI"


def settings() -> QSettings:
    return QSettings(_ORG, _APP)


# ---------------------------------------------------------------- settings
def hf_endpoint() -> str:
    stored = settings().value("hf/endpoint", "")
    if stored:
        return str(stored)
    return os.environ.get("HF_ENDPOINT", HF_OFFICIAL)


def hf_token() -> str:
    return str(settings().value("hf/token", ""))


def soundfont_path() -> Path:
    value = settings().value("audio/soundfont", "")
    if value and Path(value).exists():
        return Path(value)
    return DEFAULT_SF2


def apply_hf_env() -> None:
    """在导入 huggingface_hub / 模型库之前设置镜像与 Token。"""
    endpoint = hf_endpoint()
    token = hf_token()
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    if token:
        os.environ["HF_TOKEN"] = token


def set_hf_offline(offline: bool) -> None:
    """模型已完整缓存时切到离线模式，避免 huggingface_hub 发起联网 HEAD 请求。"""
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)
    try:
        import huggingface_hub.constants as constants

        constants.HF_HUB_OFFLINE = bool(offline)
    except Exception:
        pass


# ------------------------------------------------------------ local models
def dettato_local_ready() -> bool:
    return all(all((d / f).exists() for f in MODEL_FILES) for d in DETTATO_WEIGHTS.values())


def hub_cached(repo: str) -> bool:
    """检查 Hugging Face 缓存中是否已有该模型权重。"""
    base = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    folder = base / ("models--" + repo.replace("/", "--"))
    return any((snap / "model.safetensors").exists() for snap in folder.glob("snapshots/*"))


def dettato_ready() -> bool:
    return dettato_local_ready() or all(hub_cached(repo) for repo in DETTATO_REPOS.values())


def muscriptor_local_path(size: str) -> Path | None:
    path = MODELS_DIR / f"muscriptor-{size}"
    if all((path / f).exists() for f in MODEL_FILES):
        return path
    return None


def model_status() -> str:
    if dettato_ready():
        return "Dettato 模型已就绪"
    return "首次转换时会自动下载 Dettato 模型"


# --------------------------------------------------------------- 转录设置
def current_model() -> str:
    key = str(settings().value("transcribe/model", "dettato"))
    valid = {item[0] for item in MODEL_OPTIONS}
    return key if key in valid else "dettato"


def current_device() -> str:
    return str(settings().value("transcribe/device", "auto") or "auto")


def model_label(key: str) -> str:
    return dict(MODEL_OPTIONS).get(key, key)


def model_hint(key: str) -> str:
    if key.startswith("muscriptor"):
        size = key.split("-", 1)[1]
        if muscriptor_local_path(size) or hub_cached(MUSCRIPTOR_REPOS[size]):
            return f"MuScriptor {size} 模型已就绪"
        return "MuScriptor 需要 HF Token，并在模型页接受 CC BY-NC 4.0 协议"
    return model_status()
