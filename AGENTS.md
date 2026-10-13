# AI Music Studio Agent 工作约定

本工程独立于任何游戏项目。默认 Windows / PowerShell；优先 CLI、Python 和 native API。先读 README、docs/status.json 和目标模块，不要重复下载工具。

- 基础环境 `.venv` 使用 Python 3.12；`uv sync --frozen --extra dev` 复现。ACE-Step 使用外部仓库自己的 `.venv`，不得把 torch/CUDA/vLLM 加入本工程依赖。
- 流水线 A：配置→MIDI→FluidSynth SF2→混音→检测→导出。流水线 B：配置→独立 ACE-Step HTTP 服务→音频→检测。B 失败不能影响 A。
- `compose` 是确定性的音符计划执行器，尚无内置自然语言模型。Agent 可根据需求生成音符配置；不得称当前实现为已部署的 AI 作曲模型。
- 相对路径基于工程根目录；外部音源可使用绝对路径或环境变量。`config/local.yaml` 是整份配置覆盖，默认被忽略；从 `config/studio.yaml` 复制后再编辑。
- 所有公开命令输出 JSON envelope：schema_version、run_id、status、result、error；日志写 stderr 和 `outputs/logs`。退出码 0 成功，2 参数/运行错误，3 检测不通过，130 中断。帮助为常规文本。
- 不覆盖已有用户文件。每次测试使用新输出目录；部分失败的渲染文件须按失败日志识别，不得当成合格产物。不自动删除历史测试。
- 安装管理员程序、修改系统环境变量、下载大型模型、购买软件、删除/覆盖已有用户文件或执行来源无法核实的二进制，必须先说明影响并取得用户确认。
- 模型、SF2/SFZ、便携工具、虚拟环境和生成音频不提交 Git。音源必须记录作者、来源、许可证、SHA-256；不混淆音源许可与代码许可。
- 新引擎遵循 `src/music_studio/generation/GenerationEngine` 接口，保持独立服务边界。接入 SFZ/VST3 必须新增真实宿主/渲染适配，不能只改 ready 标签。
- 行为变更运行相关 pytest；渲染/混音/导出变更必须运行 `scripts/smoke-test.py`，检查 summary.json 和实际解码，保留证据。测试通过不代表听感、设备播放或模型质量已验证。
- 外部 API 包装以 `docs/evidence/acestep-api-v0.1.8.md` 为已测契约。升级时先核实官方文档及响应，不盲改状态或重提已排队任务。
- 功能状态以 docs/status.json 和真实测试证据为准；文档未验证项保持明确。不要承诺完整音频能无损转为 MIDI。
