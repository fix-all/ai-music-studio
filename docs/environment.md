# 环境要求和检测

基础流水线当前支持 Windows x64，使用 uv 管理的 CPython 3.12.13。需要 Git、uv、Windows tar、PowerShell 和访问官方资源的网络；bootstrap 在工程内安装便携工具和 Python 依赖，不修改系统 PATH。

基础 MIDI/SF2 流程只使用 CPU，不需要 NVIDIA GPU。请为工具、虚拟环境、下载缓存和测试结果预留至少 2 GB 可用空间；模型所需空间另行计算。已在 Windows 11 / Intel x64 的 CPU 环境验证，其他系统尚未验证，不能直接使用本仓库的 Windows DLL 路径。

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\music-studio.exe doctor
.\scripts\inspect-environment.ps1 -Output docs/environment-report.local.json
```

环境脚本记录系统、CPU、GPU、磁盘、工具、常用音源/模型目录。GPU 名称和 WMI AdapterRAM 不能直接等同于可用独立显存。脚本仅扫描常用位置，不代表整台电脑不存在其他便携工具或模型。

环境报告可能包含用户名路径、设备信息和本地资产位置，仅在本地保存，分享前应检查内容。公开仓库不包含原始开发机器报告，已测结果见 [validation.md](validation.md)。

生成式引擎使用另一个仓库和虚拟环境；RTX 3060 12 GB 参考方案、模型体积和待验证项见 [acestep-3060.md](acestep-3060.md)。基础 doctor 成功不代表生成模型可运行。
