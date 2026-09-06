# 《永昌世界》交接给 GLM

更新时间：2026-09-06  
仓库：`E:\Victoria3 Mod`  
当前分支：`codex/yongchang-world-bootstrap`  
当前提交：`7f935d7 test: add in-game release smoke suite`

## 1. 目标与硬约束

继续执行以下计划，目标是交付 Victoria 3 1.13.11（Matcha，Build ID `24799966`）可游玩的《永昌世界》v0.1：

- `docs/superpowers/plans/2026-09-04-00-永昌世界实施总路线.md`
- `docs/superpowers/plans/2026-09-04-01-基础骨架与四国垂直切片.md`
- `docs/superpowers/plans/2026-09-04-02-区域场景扩展.md`
- `docs/superpowers/plans/2026-09-04-03-十国内容与共享系统.md`
- `docs/superpowers/plans/2026-09-04-04-AI平衡DLC与发行验收.md`

必须遵守：

1. 不操作桌面，不切换窗口、不截图、不点击 UI。只能用文件、日志和隐藏进程做验证。
2. 不修改或覆盖本体目录 `E:\SteamLibrary\steamapps\common\Victoria 3`。
3. 不修改这三个兼容层 DLL：`Juij_Steam.dll`、`version.dll`、`winmm.dll`。
4. 不伪造 1846/1866/1900 检查点；证据不足就保持 pending。
5. 不使用 `git reset --hard`、`git checkout --`，保留已有工作。

## 2. 已完成内容

仓库中已经有：

- 十个核心国家：`SHU`、`JHG`、`DMG`、`NQG`、`OIR`、`MNG`、`TIB`、`KOR`、`LAN`、`NMG`。
- 区域场景：东北、内亚、西南、南洋、太平洋及新明相关州、人口、建筑和外交事实表。
- 十国主日志、辅助日志、事件、两条路线、AI 策略、动态国名、地图颜色、政治身份和纯色 CoA 占位。
- AI 护栏：大顺早期有限吞并、靖海不殖民非洲、墨西哥不能在 1846 年前吞并 `NMG` 等。
- DLC 兼容层：`ep1_content`、`mp1_content`、`ep2_content`；无 DLC 路径先执行，增强路径再门禁。
- 启动接线：`yongchang_world/common/on_actions/ywc_startup_hooks.txt` 通过子 on_action 链接原版 `on_game_started_after_lobby`，不要改回直接覆盖原版 effect。
- 原生发布烟测：`yongchang_world/tools/scripted_tests/ywc_release_smoke.txt`。
- 安装描述文件和开发安装脚本；当前用户数据中的 Mod 路径是 `E:\Victoria3 Mod\yongchang_world`。

## 3. 已验证证据

最近一次验证结果：

```text
python -m unittest discover -s tests -v  -> 86 tests passed
python tools/ywc_check.py ...            -> exit 0
git diff --check                         -> pass
隐藏启动 Victoria 3                   -> Mod mounted，匹配 1.13.11
相关脚本错误关键词                      -> none
tools/collect_smoke_logs.ps1 -NoLaunch  -> status=clean，finding_count=0
```

相关记录：

- [发行验收记录](release/v0.1-acceptance.md)
- [隐藏启动摘要](../artifacts/smoke/latest-summary.txt)
- [十国汇总](../artifacts/smoke/core-country-summary.json)
- [观察矩阵摘要](../artifacts/observe/matrix-summary.json)

游戏 debug 日志曾记录 Mod 挂载：

```text
Mounted Data: E:/Victoria3 Mod/yongchang_world
Mod The Yongchang World (the_yongchang_world) version 1.13.* successfully matched game version 1.13.11.
```

本体目录中的三个 DLL 当前均为长度 `5452240`，最后写入时间 `2026/7/3 20:40:00`；本仓库没有改动它们。

## 4. 目前不能宣称完成的事项

这些是发布门槛，不要用静态测试替代：

- 五配置 × 三种子 × 1846/1866/1900 的真实观察局没有完成。
- 十国逐国选国、进入 1836 和完整 DLC UI 检查没有完成。
- `artifacts/observe/matrix-summary.json` 中 15 条记录仍是 `not_run_no_desktop_interaction`；`tools/check_release.py` 预期会因此返回失败。
- `yongchang_world/common/diplomatic_actions/ywc_diplomatic_actions.txt` 在计划的锁定文件结构中，但当前仓库尚未找到；接手时先判断它是应该实现的实际外交动作，还是计划遗漏，不要用空文件掩盖。
- `tools/run_observation_matrix.ps1` 的 `-userdir` 只把日志等部分输出放入隔离目录；实测隔离目录中的 `content_load.json` 没有使 Mod 挂载，隔离日志中的 `Mod:` 为空，只挂载了本体。因此不能把现有 runner 的 `hidden_preload_only` 当成“该 DLC 配置已加载”或“观察局已运行”。

## 5. 建议接手顺序

### A. 先修正观察工具的证据边界

阅读并核对：

- `tools/run_observation_matrix.ps1`
- `tools/summarize_observation.py`
- `tools/check_release.py`
- `tests/test_observation_schema.py`
- `tests/test_release_gate.py`

优先找到不碰桌面的真实启动方式。如果本体/兼容层不支持在 `-userdir` 下读取 Mod 配置，就让 runner 明确记录 `mod_mount=false` 和原因，或实现可恢复、不会覆盖用户存档的替代方案；不能只改状态字符串。

本体提供的 `scripted_tests` 只能在已经进入战局后检查日期和触发器；`ywc_release_smoke.txt` 是只读不改战局的检查套件，但当前没有证明它已经被实际执行。

### B. 补齐计划中遗漏的外交接口

先从本体 `game/common/diplomatic_actions` 中选最小、已验证的 pact 结构，再写失败测试和最小实现。所有新键使用 `ywc_` 前缀，DLC 能力仍须用已核验的三个 `has_dlc_feature` ID 门禁。完成后必须跑静态检查并用隐藏启动检查日志。

### C. 只在有真实证据时更新矩阵

合法检查点必须来自真实进入战局后的游戏状态、存档导出或受支持的 headless 流程。没有这样的来源时，保留 `not_run_no_desktop_interaction`，并在文档写明限制；不要把 20 秒启动日志、静态 JSON 或预填的空检查点称为长期平衡结果。

## 6. 常用验证命令

在 Windows PowerShell 中：

```powershell
Set-Location 'E:\Victoria3 Mod'
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:\SteamLibrary\steamapps\common\Victoria 3\game'
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
git -c safe.directory='E:/Victoria3 Mod' status --short --branch
```

隐藏启动时只启动自己创建的进程，并在结束时按 PID 停止；启动前先确认没有已有 `victoria3.exe`。不要停止用户原本已经运行的进程。

## 7. 交接完成标准

接手者只有在以下证据齐全后，才能把目标标为完成：

- 全部测试和静态检查通过。
- 无 DLC、三种单 DLC、全 DLC 的实际启动/进入 1836 证据齐全。
- 至少三种随机种子的 1836—1900 真实观察结果齐全，且异常有分类。
- 十国边界与 `NMG` 墨西哥属邦关系有运行时证据。
- 发行记录、变更记录和已知限制同步更新。
- 工作树干净，且没有桌面操作或 DLL 修改。

当前应把目标保持为“进行中”，不要调用完成门禁。
