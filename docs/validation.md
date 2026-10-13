# 已验证结果

2026-10-13，Windows 11 x64，CPython 3.12.13。以下是本地真实执行的验证记录，不代表所有硬件已经适配。

- pytest：24 passed，0 failed，0 skipped。
- 真实音频验证：16/16 检查通过。
- MIDI：8 小节、两条独立音轨和通道、56 个 note-on、16 秒。
- FluidSynth 2.6.1 加载 TimGM6mb 1.3，枚举 136 个真实预置。
- WAV/MP3/FLAC：18 秒（包含两秒尾音），44,100 Hz，双声道，非静音，无削波，FFmpeg 全文件解码通过。
- 初次混音 WAV：采样峰值约 -3.000 dBFS，integrated loudness -13.733 LUFS，4×重采样真峰值估计 -2.994 dBTP。
- SF2 探针验证了力度响应、时值变化、释放尾音及三个同时发声的音高。
- ACE-Step HTTP 适配器通过模拟服务契约/失败/超时测试；下载阻断对保存的官方 helper 已实测。没有运行真实模型。

开源发布前另从 Git 暂存源码导出到干净目录，重新创建 `.venv`，复用经固定 SHA-256 校验的下载缓存重新解包工具和 SF2，再执行 bootstrap/doctor、pytest 和真实 smoke test：24 项测试、16 项音频检查再次全部通过。该复核使用同一台 Windows 电脑，其他电脑硬件和网络仍需重新检测。

原始机器报告、JUnit、运行日志和测试音频只保留在本地。仓库仅包含可复现脚本和这份结果摘要。重新执行：

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke-test.py
```

检查新建 `outputs/validation-*/summary.json` 的 passed、各项 checks 和实际文件。脚本保留 MIDI、音频、CLI JSON 和 stderr 日志。全文件解码已验证；人工试听、物理输出设备和主观音乐质量不在此记录的验收范围。
