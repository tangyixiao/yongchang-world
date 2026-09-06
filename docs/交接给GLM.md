# 《永昌世界》交接给 GLM

更新时间：2026-09-06  
仓库：`E:\Victoria3 Mod`  
当前分支：`codex/yongchang-world-bootstrap`  
当前提交：`b608b3c docs: sync release evidence after GLM handoff`

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
- NMG 外交动作：`ywc_nmg_autonomy_negotiation`，在满足属邦和主日志条件时可向墨西哥提议自治谈判，接受后解决对应主日志。
- 安装描述文件和开发安装脚本；当前用户数据中的 Mod 路径是 `E:\Victoria3 Mod\yongchang_world`。

## 3. 已验证证据

最近一次验证结果：

```text
python -m unittest discover -s tests -q  -> 97 tests passed
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
- 观察 runner 的原始问题已修复：PowerShell 5.1 的 `Set-Content -Encoding UTF8` 写入 BOM，游戏解析失败后会静默回退为“全 DLC、无 Mod”；现在改为紧凑无 BOM JSON，并把 Mod/DLC 挂载证据写入 `run.json`。
- 直接启动 exe 时，`disabledDLC` 不能稳定控制已拥有 DLC；所有权后端在不同启动间会出现全拥有/不可用两种状态。因此单 DLC 配置仍不能在无启动器 UI 条件下宣称完成。

## 5. 建议接手顺序

### A. 复核观察工具的证据边界

阅读并核对：

- `tools/run_observation_matrix.ps1`
- `tools/summarize_observation.py`
- `tools/check_release.py`
- `tests/test_observation_schema.py`
- `tests/test_release_gate.py`

先复核无 BOM 修复后的 `mod_mount`、`version_match_evidence`、`observed_mounted_dlc`、`dlc_ownership_backend` 和 `dlc_state_matches_config` 字段。`hidden_preload_only` 只表示启动预加载，不表示进入战局或完成观察局。

本体提供的 `scripted_tests` 只能在已经进入战局后检查日期和触发器；`ywc_release_smoke.txt` 是只读不改战局的检查套件，但当前没有证明它已经被实际执行。

### B. NMG 外交动作运行时验收状态

已实现 `ywc_nmg_autonomy_negotiation`，本地化、触发条件、主日志前置条件和隐藏启动解析日志均已复核：`common/diplomatic_actions` 枚举成功，Unknown trigger/effect、Invalid database object、缺失本地化和数据库冲突均为零。烟测套件新增 `ywc_nmg_autonomy_action_ready` 只读检查；仍需进入真实战局后执行套件，才能获得运行时执行证据。所有新键继续使用 `ywc_` 前缀。

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
