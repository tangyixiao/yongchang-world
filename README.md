# The Yongchang World

《永昌世界》是面向 Victoria 3 1.13.11 的架空历史 Mod。当前仓库阶段是四国可启动垂直切片，包含大顺（SHU）、靖海国（JHG）、东明（DMG）和北清（NQG）的 1836 基础国家、State 所有权、人口、建筑、外交与引导日志。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
```

将开发描述文件安装到本地启动器 Mod 目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_dev_mod.ps1
```

之后用 `victoria3.exe -debug_mode` 启动，在启动器启用 `The Yongchang World`，检查四国是否出现在选国界面并能进入 1836。退出游戏后采集日志：

```powershell
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
```

日志摘要写入 `artifacts/smoke/latest-summary.txt`；原版游戏目录保持只读，仓库只保存摘要而不保存大型日志或存档。

## 当前边界

本阶段只建立四国垂直切片，不代表十国内容、区域扩展、AI 平衡、DLC 兼容层或 1836—1900 观察局已经完成。游戏脚本以本体 1.13.11（Build ID 24799966）为基线，Province ID 来自本体快照。
