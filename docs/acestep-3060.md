# 家中 RTX 3060 12 GB 部署方案

当前状态：适配评估完成、REST 适配器完成并通过模拟服务契约测试；没有下载权重、安装 torch 或运行真实 AI 生成。以下是待在家中执行的步骤，不能视为已验证安装结果。

## 硬件与下载预算

RTX 3060 12 GB 在 [官方普通版 Turbo 的推荐区间](https://github.com/ACE-Step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md)。采用普通 2B Turbo，第一次仅 DiT，`thinking: false`，10 秒、batch=1；成功后再用 0.6B LM / `pt` backend / CPU offload。官方也支持 Intel XPU 和 CPU，本次没有在办公电脑上实测，不将其标为不兼容。

官方主权重仓库 `ACE-Step/Ace-Step1.5`，模型卡 MIT；核实 revision `19671f406d603126926c1b7e2adc169acbcade22`。当前文件合计 10,092,102,593 bytes，包含 1.7B LM。只下载 Turbo（约 4.79 GB）+ VAE（0.34 GB）+ embedding（1.21 GB）约 6.34 GB；可选 0.6B LM 另约 1.37 GB，revision `148d8ea0225bdab342ee1ae3a354275ccd60ca80`，模型卡 MIT。数字按官方文件树求和，不是运行显存，也不包含包缓存；元数据保存在 `evidence/acestep-model-metadata.json`。

推理依赖另需数 GB，建议预留 25–35 GB 磁盘作为部署/缓存/结果预算；这是规划估算。建议至少 16 GB 内存，32 GB 更适合 CPU offload，此为工程建议，并非本次测得最低门槛。家中先运行 `nvidia-smi`、环境脚本核实驱动/显存/内存/磁盘。v0.1.8 的 Windows 默认 torch 2.7.1+cu128，驱动必须兼容该 wheel；不默认安装 CUDA Toolkit。Python 需要 >=3.11,<3.13，固定单独 3.12 环境。

## 先迁移基础工程

同步源代码、config、docs、scripts、tests、pyproject.toml、uv.lock、requirements.txt。不要复制 `.venv`（启动器含本机路径）。模型和音源可留在工程外；便携工具可重新由 bootstrap 安装。

```powershell
Set-Location E:\myProjects\musician
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe scripts/smoke-test.py
```

这里已能运行全部 MIDI/SF2 流程，与模型是否安装无关。

## 确认大型下载后再执行

下面会下载独立依赖及至少约 6.34 GB 模型。应先明确批准下载范围。第一阶段没有执行这些命令。

```powershell
# 新目录，不能覆盖已有 checkout。官方 release v0.1.8。
git clone --depth 1 --branch v0.1.8 https://github.com/ACE-Step/ACE-Step-1.5.git E:\AI\ACE-Step-1.5
Set-Location E:\AI\ACE-Step-1.5
git rev-parse HEAD
# 应为 dce621408bee8c31b4fcf4811682eb9359e1bc94
uv sync --python 3.12 --frozen
uv run --no-sync python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
# 仅选必要权重；不执行 --all，不先启动会自动下载模型的上游 UI。
uv run --no-sync python -c "from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/Ace-Step1.5', revision='19671f406d603126926c1b7e2adc169acbcade22', local_dir=r'E:\AI\models\ace-step-1.5', allow_patterns=['config.json','acestep-v15-turbo/*','vae/*','Qwen3-Embedding-0.6B/*'])"
```

若依赖冲突或 CUDA 不可用，保留安装日志并停止模型启动，不改动基础 `.venv`。官方 Windows 依赖包含版本敏感的 torchao/torchcodec 等，不能仅凭版本表保证兼容。不要盲目升级整套包或改系统环境变量；先记录实际错误再处理。

从本平台根目录启动：

```powershell
Set-Location E:\myProjects\musician
.\scripts\start-acestep.ps1 -Repository E:\AI\ACE-Step-1.5 -Checkpoints E:\AI\models\ace-step-1.5 -Device cuda
```

启动脚本检查必要本地权重，使用独立 `.venv`、loopback:8001、offload、HF/Transformers offline；默认不启用 LM。`acestep_offline_server.py` 额外阻断已核实的上游 Hugging Face/ModelScope 自动下载函数，缺资源时明确失败，避免上游 fallback 继续下载。对官方保存的 downloader 已实测此阻断；真实模型启动尚待实测。升级后若下载 API 名称变化，启动器会拒绝运行，需重新审阅。环境变量只作用于当前进程，退出后恢复。

## 连接与验收

新 PowerShell 终端，复制 `config/studio.yaml` 为不存在的 `config/local.yaml`，保留整份配置，仅把 `generation.enabled` 改为 true，必要时修改端口。`config/generation.yaml` 默认十秒中性功能测试，未绑定游戏。

```powershell
.\.venv\Scripts\music-studio.exe list-engines
.\.venv\Scripts\music-studio.exe generate --config config/generation.yaml --output outputs/home-ai-test.wav
.\.venv\Scripts\music-studio.exe analyze --input outputs/home-ai-test.wav --report outputs/home-ai-test.analysis.json
```

确认 service_healthy，再检查真实生成的时长、采样率、声道、非静音、削波、完整解码与人工试听。service_healthy 仅表示健康端点成功。提交回执 `.task.json` 保存 task_id；超时后查询原任务，不重复提交。首次验收通过后再更新 docs/status.json，记录家中环境、模型 revision、测得显存/耗时和结果文件。

可选 LM：另行确认约 1.37 GB 下载后，用相同 snapshot_download 下载 `ACE-Step/acestep-5Hz-lm-0.6B` 到 `E:\AI\models\ace-step-1.5\acestep-5Hz-lm-0.6B`，固定上文 revision。启动时加 `-EnableLlm`，生成配置改为 `thinking: true`；先维持十秒、单任务。12 GB 上 LM 与长音频仍可能引发显存不足；回到 DiT-only 配置继续验证。

源码和模型的 MIT 标签分别来自 [官方仓库](https://github.com/ACE-Step/ACE-Step-1.5/blob/v0.1.8/LICENSE)、[主模型](https://huggingface.co/ACE-Step/Ace-Step1.5)、[0.6B LM](https://huggingface.co/ACE-Step/acestep-5Hz-lm-0.6B)。当前接口契约见 `evidence/acestep-api-v0.1.8.md`；升级版本前应重新核实。
