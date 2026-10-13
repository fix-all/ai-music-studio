# AI Music Studio

本地音乐制作平台，当前可执行：可编辑 YAML 音符计划 → MIDI → SF2 采样渲染 → 混音 → WAV / FLAC / MP3 → 自动检测。独立 ACE-Step 接口已经实现，模型尚未部署；提供 RTX 3060 12 GB 参考部署方案。

这是平台搭建阶段，附带音频只用于功能验证，不属于具体音乐作品。`compose` 执行确定性的音符计划，未来可由 Agent 按需求生成配置；目前没有内置自然语言作曲模型。

## 安装

Windows x64，已安装 uv。打开工程目录：

```powershell
git clone https://github.com/fix-all/ai-music-studio.git
Set-Location ai-music-studio
.\scripts\bootstrap.ps1
```

脚本使用官方 FluidSynth 发行包、FFmpeg 官网列出的 Gyan 构建、Debian 官方镜像中的 TimGM6mb SF2；校验固定 SHA-256。创建 `.venv` 和便携工具，不改系统 PATH，不下载 AI 权重。依赖由 `uv.lock` 固定；`requirements.txt` 提供同版基础包清单。若 PowerShell 的执行策略阻止脚本，可只对本次进程使用 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1`。

## 使用

无需激活环境。相对输入/输出路径基于工程目录，已有输出文件会被拒绝覆盖。

```powershell
.\.venv\Scripts\music-studio.exe doctor
.\.venv\Scripts\music-studio.exe list-engines
.\.venv\Scripts\music-studio.exe list-instruments
.\.venv\Scripts\music-studio.exe compose --config config/example.yaml --output projects/my-test.mid
.\.venv\Scripts\music-studio.exe render --input projects/my-test.mid --output outputs/my-test-dry.wav --tail 2
.\.venv\Scripts\music-studio.exe mix --input outputs/my-test-dry.wav --output outputs/my-test.wav --config config/mixing.yaml
.\.venv\Scripts\music-studio.exe export --input outputs/my-test.wav --output outputs/my-test.mp3
.\.venv\Scripts\music-studio.exe analyze --input outputs/my-test.mp3 --report outputs/my-test.analysis.json
```

也可用 `.\scripts\music-studio.ps1 doctor`，或激活 `.venv\Scripts\Activate.ps1` 后直接调用 `music-studio`。命令支持 `--help`。JSON 写 stdout，日志写 stderr 和 `outputs/logs/`；退出码 0 成功，2 执行错误，3 质量/就绪检查不通过，130 中断。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke-test.py
```

每次 smoke test 创建唯一的 `outputs/validation-*/`，保留 MIDI、WAV、MP3、FLAC、测量结果及日志。检查 `summary.json` 的 `passed`；仅命令退出不等于音频合格。已测结果见 [验证记录](docs/validation.md)。原始环境报告、日志和测试音频保留在本地，不随公开仓库分发；拉取后运行测试即可重新生成。

## 配置与后续

- 音符、节奏、时值、力度、声部和乐器：`config/example.yaml`；说明见 [架构](docs/architecture.md)。
- EQ、混响、延迟、立体声宽度、淡入淡出和峰值：`config/mixing.yaml`。响度为测量值，没有自动承诺广播级母带。
- 外部 SF2：复制 `config/studio.yaml` 为 `config/local.yaml`，保留整份配置，修改音源路径、作者、来源、许可和哈希。SFZ 目前只支持注册信息，不支持渲染。
- 部署生成模型：[RTX 3060 12 GB 操作说明](docs/acestep-3060.md)。尚未启动模型时 `generate` 返回 ENGINE_DISABLED。
- [环境要求和检测](docs/environment.md) · [引擎选型](docs/engines.md) · [机器状态](docs/status.json) · [Agent 约定](AGENTS.md)

第二阶段提供：用途、风格/参考、时长、BPM、拍号/调式、结构、乐器、情绪、是否循环、是否人声/歌词、输出格式和响度目标。选择 MIDI 可编辑控制或生成式音频；后者可以导入 DAW，不能保证转换为可编辑 MIDI。

## 许可证

原创源码采用 [MIT](LICENSE)。模型、音源及外部工具不打包进仓库，各自保留上游许可证；详见 [第三方说明](THIRD_PARTY_NOTICES.md)。
