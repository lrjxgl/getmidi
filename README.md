# GetMIDI

本地运行的音频转 MIDI 桌面应用。导入音频后由 AI 模型自动转录为多音轨 MIDI，直接落在钢琴卷上编辑、试听，并导出 MIDI / WAV / 分轨压缩包。

界面基于 PySide6，转录使用 [Dettato](https://github.com/kobimusic/dettato)（默认）或 MuScriptor，播放与渲染由内置 SoundFont 合成器完成，不需要安装 FluidSynth 等外部程序。

> 产品介绍页：[html/index.html](html/index.html)

## 功能

- **多音轨转录**：旋律、低音、鼓组自动分离成独立音轨，颜色区分
- **钢琴卷主界面**：缩放、点击标尺跳转、播放头跟随、音高标签（黑白键均标注）
- **音轨控制**：独立静音（M）、独奏（S）、音量滑块（0–100%），钢琴卷同步过滤显示
- **内置合成播放**：加载 SoundFont 即可试听；渲染在后台线程进行，不阻塞界面
- **导出**：MIDI、WAV，或含混音与分轨的 ZIP 包
- **模型管理**：Hugging Face 官方源 / hf-mirror 镜像 / 自定义端点；本地缓存完整时自动离线运行

## 环境要求

- Windows 10 / 11
- Python 3.10（推荐 conda 环境 `py310`）
- 可选：NVIDIA GPU（CUDA 加速转录；纯 CPU 可用但更慢）
- 磁盘：模型权重约数百 MB 起，视所选模型而定

## 安装

```powershell
# 创建并激活环境（已存在 py310 可跳过）
conda create -n py310 python=3.10 -y
conda activate py310

# 安装依赖（requirements.txt 已包含 PyTorch CUDA 源）
pip install -r requirements.txt
```

## 启动

双击 `run.bat`，或：

```powershell
conda run -n py310 python -m app.main
```

`run.bat` 会依次尝试 conda 环境 `py310`、`F:\program\miniconda3\envs\py310\python.exe` 和系统 `python`。

## 使用流程

1. **导入音频**：点击顶部「导入音频」、按 `Ctrl+O`，或把文件拖进窗口。支持 `.wav .mp3 .flac .ogg .oga .m4a .aac .aiff .aif .wma .opus`
2. **选择模型与设备**：打开「设置 → 转录」，模型可选 Dettato 或 MuScriptor Small / Medium / Large，设备可选自动 / GPU / CPU
3. **转录**：导入后自动开始，进度窗口中可查看日志并取消
4. **调整**：左侧音轨卡片切换 M / S、拖动音量；钢琴卷支持缩放与跳转
5. **导出**：顶部「导出 ▾」菜单选择 MIDI、WAV 或 ZIP

### 快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl+O` | 导入音频 |
| `Space` | 播放 / 暂停 |
| `Ctrl + 滚轮`、`+` / `-` | 钢琴卷缩放 |
| `Shift + 滚轮` | 横向滚动 |

### 导出内容

| 格式 | 内容 |
| --- | --- |
| MIDI | 全部音轨（含音色、鼓通道、通道音量） |
| WAV | 按当前静音 / 独奏 / 音量设置渲染的混音（44.1 kHz） |
| ZIP | `项目名.mid`、`项目名.wav`，以及 `tracks/01_音轨名.mid/.wav` 分轨文件 |

## 模型

| 模型 | 说明 |
| --- | --- |
| **Dettato**（默认） | 多乐器分轨转录，无需 Token。权重位于 4 个 Hugging Face 仓库，首次使用时下载 |
| **MuScriptor** | 可选钢琴转录模型，三档规模。权重为门控模型，需在 Hugging Face 接受 CC BY-NC 4.0 许可并填写 Token |

- 模型权重默认下载到 `models/dettato_weights/`（Dettato）与 `models/muscriptor-<size>/`（MuScriptor）
- 也可手动把权重放入上述目录，程序优先使用本地文件
- 下载源在「设置 → 模型管理」中切换；也可在启动前设置环境变量：

```powershell
set HF_ENDPOINT=https://hf-mirror.com
set HF_TOKEN=hf_xxx
```

- 检测到 Hugging Face 缓存或本地权重完整时，程序自动进入离线模式，不会发起联网请求

## 音色库与播放

- 默认音色库：`models/GeneralUser-GS.sf2`
- 可在「设置 → 音频」中更换为任意 `.sf2` / `.sf3` 文件
- 合成器内置于程序（tinysoundfont），无需安装 fluidsynth；未找到音色库时会在导出 / 播放时给出提示

## 目录结构

```
getmidi/
├─ app/
│  ├─ main.py              # 入口
│  ├─ config.py            # 路径、设置、模型状态
│  ├─ core/
│  │  ├─ engines.py        # Dettato / MuScriptor 封装
│  │  ├─ transcription.py  # 音轨数据模型与 MIDI 读写
│  │  ├─ render.py         # SoundFont 离线渲染
│  │  ├─ player.py         # 播放控制
│  │  ├─ exporter.py       # MIDI / WAV / ZIP 导出
│  │  ├─ downloader.py     # 模型下载线程
│  │  └─ worker.py         # 转录线程
│  └─ ui/                  # 主窗口、钢琴卷、音轨面板、设置与对话框
├─ models/                 # 模型权重与默认音色库
├─ html/                   # 推广主页与 getmidi.zip
├─ requirements.txt
├─ run.bat
└─ README.md
```

## 常见问题

**首次转录卡在下载模型**
网络无法直连 huggingface.co 时，在设置里把下载源切换为 hf-mirror，或先设置 `HF_ENDPOINT` 环境变量后重启程序。

**MuScriptor 下载失败（401 / 403）**
该模型为门控模型：先登录 Hugging Face 接受 CC BY-NC 4.0 许可，再在「模型管理」中填写具备读取权限的 Token。

**显存不足 / 速度太慢**
在设置中把设备改为 CPU 可避免显存不足；追求速度则选择 GPU，并确认已安装 CUDA 版 PyTorch。

**播放没有声音**
确认 `models/GeneralUser-GS.sf2` 存在，或在设置中指向其他 `.sf2` / `.sf3` 文件；检查系统音量与音频输出设备。

## 说明

- 音频与转录结果均在本地处理，不会上传
- Dettato 与 MuScriptor 模型分别遵循其各自的仓库许可，使用前请阅读对应模型页面
