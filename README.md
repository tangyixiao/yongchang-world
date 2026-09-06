# The Yongchang World

《永昌世界》是面向 Victoria 3 1.13.11 的架空历史 Mod。当前仓库已经完成十国内容垂直切片：大顺（SHU）、靖海国（JHG）、东明（DMG）、北清（NQG）、卫拉特（OIR）、喀尔喀（MNG）、吐蕃（TIB）、朝鲜（KOR）、兰芳（LAN）和新明（NMG）。每国都有 1836 内容入口、主/辅助日志、事件、两条路线、AI 策略、双语文本、政治身份、动态国名、地图颜色与纯色 CoA 旗帜占位。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
```

将开发描述文件安装到本地启动器 Mod 目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_dev_mod.ps1
```

之后用 `victoria3.exe -debug_mode` 启动，在启动器启用 `The Yongchang World`，检查十国是否出现在选国界面并能进入 1836。自动化验收使用隐藏窗口启动并读取日志，不切换桌面、不截图、不点击 UI；退出游戏后采集日志：

```powershell
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
```

日志摘要写入 `artifacts/smoke/latest-summary.txt`，十国内容汇总写入 `artifacts/smoke/core-country-summary.json`；原版游戏目录保持只读，仓库只保存摘要而不保存大型日志或存档。

进入已有战局后，可用本体的 `scripted_tests` 命令启用 `yongchang_world/tools/scripted_tests/ywc_release_smoke.txt`，执行只读的 1900 年发布烟测：十国存在、NMG 的墨西哥属国关系以及启动兼容路径均会被检查。

剩余的人工验收门槛（五配置启动、逐国进入 1836、烟测执行、观察矩阵回填）的逐步操作见 [docs/release/manual-acceptance-playbook.md](docs/release/manual-acceptance-playbook.md)。

## 当前边界

本阶段已完成十国内容、DLC 挂载兼容和 AI 策略接线的静态/隐藏启动验收；仍未完成完整 UI 逐国选国与 1836—1900 长期观察局，因此尚未宣称 AI 长期平衡已达标。游戏脚本以本体 1.13.11（Build ID 24799966）为基线，Province ID 来自本体快照。
