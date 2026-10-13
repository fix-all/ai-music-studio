# 第一阶段搭建结果

完成日期：2026-10-13。工程：AI Music Studio。已达到第一阶段基础链路验收标准；未创作游戏音乐，未关联游戏项目。本文记录初次本地验证；公开仓库不分发原始日志、机器报告和生成音频，公开结果见 validation.md。

## 交付和安装

项目目录、配置、模块、Agent 说明、安装脚本、锁文件、环境/引擎/架构文档均已建立。实际安装 Python 3.12.13 项目环境、FluidSynth 2.6.1、FFmpeg/ffprobe 9.0.2、TimGM6mb 1.3 SF2、NumPy/SciPy/soundfile/mido/pyloudnorm 等。官方工具包和 SF2 归档/解包文件校验通过，来源和许可见 engines.md 及 evidence/。

安装均在用户或工程目录。bootstrap.ps1 已运行，复用校验后的资产、同步锁定依赖，doctor 返回 structured_pipeline_ready=true；没有管理员安装或系统 PATH 修改。实际核心资产下载/解包/调用已验证；全新家中电脑上的重装尚待执行。

CLI 已可用：doctor、list-engines、list-instruments、compose、render、analyze、mix、export、generate。后者在模型未部署时真实返回 ENGINE_DISABLED，退出码 2；不会输出伪造音乐文件。

## 实测证据

pytest 最终 **24 passed**（4.58 秒），包括配置/时序/通道、文件保护、音源哈希/缺失库、静音/削波/静音声道、EQ 测量、效果尾音、立体声、JSON 错误、ACE-Step 模拟 HTTP 契约/失败/超时，以及官方 downloader 的下载阻断与接口漂移检查。原始 JUnit：`docs/evidence/pytest-complete.xml`。

最新真实 smoke test **16/16 检查通过**：8 小节、两条独立音轨/通道、56 个 note-on；MIDI 16 秒，释放尾音 2 秒；SF2 136 个预置实际加载。WAV、MP3、FLAC 均完整解码成功、非静音、无削波。详细 summary 和 evidence/validation-summary.json 快照仅保留在原验证电脑本地，公开结果见 validation.md。

| 结果 | 时长 | 采样率 / 声道 | 采样峰值 | Integrated loudness | 削波 |
|---|---|---|---|---|---|
| mixed.wav | 18.000 秒 | 44,100 Hz / 2 | -3.000 dBFS | -13.733 LUFS | 0 |
| validation.mp3 | 18.000 秒（解码后） | 44,100 Hz / 2 | -3.223 dBFS | -13.997 LUFS | 0 |
| validation.flac | 18.000 秒 | 44,100 Hz / 2 | 以分析 JSON 为准，接近 WAV | 以分析 JSON 为准 | 0 |

WAV 真峰值约 -2.994 dBTP（4×重采样估算）。响度是测试混音的测量结果，未承诺固定 LUFS 母带目标。

SF2 专项：相同音符 velocity 40→110，前段 RMS 0.00309→0.02347；延长 note-on 的持续段 RMS 约为短音符释放段的 18.25 倍。短音符释放尾音 RMS 0.00105；同时播放 C4/E4/G4，各自频带均显著高于邻域底噪。具体探针文件和数值在测试目录，验证的是采样音源行为，不是作品听感。

## 实际产物位置

初次本地目录：`outputs/validation-20261013T035322Z-f4645e/`（未提交）。重新运行 smoke-test.py 会生成新的唯一目录：

- `validation.mid`：8 小节、两条独立轨道。
- `dry.wav` / `mixed.wav`：原始 SF2 渲染和经过 EQ/混响/延迟/立体声/淡入淡出的结果。
- `validation.mp3` / `validation.flac`：最终测试导出。
- `soft/loud/long/poly.mid` 和对应 `.wav`：力度、时值、尾音、多声部探针。
- `summary.json`、每条 CLI 的 `.stdout.json` / `.stderr.log`；另外 `outputs/logs/` 保存 run_id 日志和结果。

较早验证目录及初次 `outputs/validation-dry.wav` 仍保留。没有删除测试文件。播放器兼容性通过 ffprobe 和 FFmpeg 全文件解码验证；未宣称人工试听、扬声器播放或主观音乐质量已验收。

## 明确状态

| 功能 | 状态 / 原因 |
|---|---|
| 可编辑音符计划、自动 MIDI、SF2 WAV | 已实现并实测 |
| EQ、混响、延迟、立体声、淡入淡出 | 已实现并实测；长效果尾部需足够 render tail |
| WAV/FLAC/MP3，峰值/LUFS/QC | 已实现并实测 |
| ACE-Step REST 插件接口 | 已实现；模拟服务测试通过，真实推理未验证 |
| 家中 3060 12 GB 适配 | 评估与部署说明完成；家中驱动/内存/速度未测 |
| ACE-Step 依赖、权重、生成测试 | 未执行，按用户安排留待家中，且大型下载需确认 |
| 自然语言→结构化作曲模型 | 未部署；当前 Agent 可生成可编辑 YAML，由 compose 执行 |
| SFZ / VST3 宿主、MusicXML | 可选，未实现；不能通过 registry 标签冒充能力 |
| Ardour / MuseScore / sfizz GUI | 已评估，未安装；基础链路无需依赖它们 |
| 高质量正式乐器库 / 人工混音母带 | 第二阶段按编制和授权选择；小型 GM 仅用于验证 |

## 启动与第二阶段输入

在工程目录运行 `.\.venv\Scripts\music-studio.exe doctor`，按 README 命令生成/渲染/检测。整体验证：`.\.venv\Scripts\python.exe scripts/smoke-test.py`，每次写新目录，无需启动后台服务。

在另一台电脑拉取公开仓库后运行 bootstrap.ps1 重建环境；模型环境始终独立，部署步骤见 `acestep-3060.md`。GitHub 仅发布源码、配置和文档，测试音频、原始机器报告、模型及工具文件留在本地。

制作具体音乐前提供：用途/风格/参考、时长、BPM、拍号/调式、段落结构、乐器、情绪、循环要求、是否人声及歌词、MIDI 可编辑性需求、输出格式和响度目标。生成式结果可以导入 DAW 编辑音频，不视为可无损转回音符。
