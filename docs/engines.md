# 引擎评估与选型

核实日期：2026-10-13。版本来自官方 release/API；许可证按仓库文件和模型卡分别核对。这里只安装最小可复现链路。

| 项目 / 核实版本 | 许可证 | Windows 与编程能力 | 依赖和本阶段选择 |
|---|---|---|---|
| FluidSynth 2.6.1（2026-09-19） | LGPL-2.1；以官方 LICENSE 为准 | 官方 x64 ZIP；C API、CLI、离线 MIDI render | 本地解包 DLL/CLI，含 SDL3/libsndfile；ctypes 调用无声卡渲染，已实测 |
| FFmpeg 9.0.2 | 取决于构建；本次 Gyan 启用 GPL/version3 | ffmpeg/ffprobe CLI；转换、解码、过滤器 | 官网列出的 Gyan Essentials 便携包，固定 SHA-256；已实测 MP3/FLAC |
| sfizz-ui 1.2.3（2024-01-15） | BSD-2-Clause，第三方依赖另列 | 官方 win64 installer；SFZ、VST3/LV2；底层 sfizz 提供 C/C++ API | 需要 native renderer 或插件宿主；未安装，SFZ registry-only。公开 release 较旧，不能因源码更新就宣称已适配 |
| MuseScore Studio 4.7.5（2026-09-08） | GPL-3.0，字体有独立说明 | Windows MSI/portable；MIDI/MusicXML、命令行导出、插件 | Qt/C++ 桌面应用，适合乐谱编辑；本阶段没有 MusicXML/GUI 需求，不安装、不宣称其音频自动化已测 |
| Ardour 9.8（2026-08-23） | GPL-2.0-or-later，第三方组件另列 | Windows DAW；OSC/Lua，可导入音频和 MIDI | 官方成品下载存在付费/试用渠道，源码可构建；不购买、不安装。DAW 作为后续人工编辑端，不作为批处理必需依赖 |
| ACE-Step 1.5，release v0.1.8（2026-05-18），Python package 1.5.0 | 仓库 MIT；官方主权重和 0.6B LM 模型卡 MIT | Windows；Python API、异步 REST、CLI/Gradio；CUDA/CPU/XPU 等不同环境 | Python >=3.11,<3.13；本次 release Windows 默认 torch 2.7.1+cu128、torchaudio、transformers 等。独立服务接口已实现，未安装模型依赖/权重 |

FluidSynth 有稳定、较小的官方便携发行物和 C API，可精确控制 MIDI 调度并验证 SF2。FFmpeg 负责解码/格式，不引入 DAW 宿主依赖。这条链路完全使用 CPU，迁移至 3060 后仍独立可用。

当前基础包：NumPy 2.5.4、SciPy 1.18.1、soundfile 0.13.1、mido 1.3.3、PyYAML 6.0.3、pyloudnorm 0.1.1；真实安装版本由 doctor 返回，依赖固定在 uv.lock。使用 mido 而未叠加 pretty_midi，减少重复 MIDI 栈。基础 Python 3.12.13，不复用全局 3.13。

## 音源

TimGM6mb 1.3，5,969,788 字节，136 个真实预置（GM 乐器加鼓组）。作者 Tim Brechbill / David Bolton；Debian 官方镜像提供上游归档，copyright 说明 SF2 为 GPL-2。压缩包 SHA-256 来自 Debian .dsc，解包后 SF2 哈希在 config/studio.yaml 中固定。

已验证加载、力度、音长、尾音和多声部。它是小型验证音源，音色质量不代表最终制作水准。升级采样库时应记录每个库的作者、来源、许可、版本和哈希，按实际编制选择；不通过增加轨道数量宣称音质提升。

## 官方依据

- [FluidSynth release](https://github.com/FluidSynth/fluidsynth/releases/tag/v2.6.1) / [C API](https://www.fluidsynth.org/api/) / `evidence/FluidSynth-LICENSE.txt`
- [FFmpeg Windows 下载来源](https://ffmpeg.org/download.html) / [Gyan 构建](https://www.gyan.dev/ffmpeg/builds/) / `evidence/ffmpeg-download.json`
- [sfizz-ui release](https://github.com/sfztools/sfizz-ui/releases/tag/1.2.3) / [BSD 许可](https://github.com/sfztools/sfizz-ui/blob/1.2.3/LICENSE) / [底层 sfizz](https://github.com/sfztools/sfizz)
- [MuseScore release](https://github.com/musescore/MuseScore/releases/tag/v4.7.5) / [许可](https://github.com/musescore/MuseScore/blob/v4.7.5/LICENSE.txt)
- [Ardour 9.8](https://ardour.org/whatsnew.html) / [FAQ](https://ardour.org/faq.html) / [OSC](https://manual.ardour.org/using-control-surfaces/controlling-ardour-with-osc/)
- [ACE-Step release](https://github.com/ACE-Step/ACE-Step-1.5/releases/tag/v0.1.8) / [安装](https://github.com/ACE-Step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md) / [API](https://github.com/ACE-Step/ACE-Step-1.5/blob/v0.1.8/docs/en/API.md) / [主模型](https://huggingface.co/ACE-Step/Ace-Step1.5)
- [TimGM 包来源](https://packages.debian.org/sid/timgm6mb-soundfont) / [授权记录](https://metadata.ftp-master.debian.org/changelogs/main/t/timgm6mb-soundfont/timgm6mb-soundfont_1.3-5_copyright)

代码采用本工程 MIT 许可证；上述工具/模型/音源保持各自许可证，不能统一标为 MIT。这里的 GPL/MIT 标签是上游授权记录，不等于对未来作品全部素材权利的统一判断。
