# 《永昌世界》交接给 GLM

更新时间：2026-09-06
仓库：`E:\Victoria3 Mod`
分支：`codex/yongchang-world-bootstrap`
代码验收基线：`4253ebb test: add autonomy action readiness to in-game smoke suite`

## 1. 任务目标与硬约束

继续执行以下计划，目标是交付 Victoria 3 1.13.11（Matcha，Build ID `24799966`）可游玩的《永昌世界》v0.1：

- `docs/superpowers/plans/2026-09-04-00-永昌世界实施总路线.md`
- `docs/superpowers/plans/2026-09-04-01-基础骨架与四国垂直切片.md`
- `docs/superpowers/plans/2026-09-04-02-区域场景扩展.md`
- `docs/superpowers/plans/2026-09-04-03-十国内容与共享系统.md`
- `docs/superpowers/plans/2026-09-04-04-AI平衡DLC与发行验收.md`

硬约束：

1. 不操作桌面，不切换窗口、不截图、不点击 UI；只能使用文件、日志和隐藏进程验证。
2. 不修改或覆盖 `E:\SteamLibrary\steamapps\common\Victoria 3` 本体目录。
3. 不修改 `Juij_Steam.dll`、`version.dll`、`winmm.dll` 三个兼容层 DLL。
4. 不伪造 1846、1866、1900 检查点；没有真实证据就保持 `pending`。
5. 不使用 `git reset --hard` 或 `git checkout --`，保留已有工作。

## 2. 当前已实现内容

- 十个核心国家：`SHU`、`JHG`、`DMG`、`NQG`、`OIR`、`MNG`、`TIB`、`KOR`、`LAN`、`NMG`。
- 东北、内亚、西南、南洋、太平洋和新明相关区域的州、人口、建筑、外交事实与场景数据。
- 十国主日志、辅助日志、事件、两条路线、AI 策略、动态国名、地图颜色、政治身份和纯色 CoA 占位。
- AI 护栏，包括大顺早期有限吞并、靖海不殖民非洲、墨西哥不能在 1846 年前吞并 `NMG` 等规则。
- DLC 兼容层：`ep1_content`、`mp1_content`、`ep2_content`；无 DLC 路径先执行，增强路径再门禁。
- 启动接线：`yongchang_world/common/on_actions/ywc_startup_hooks.txt` 通过子 on_action 链接原版 `on_game_started_after_lobby`，不要改回直接覆盖原版 effect。
- 原生发布烟测：`yongchang_world/tools/scripted_tests/ywc_release_smoke.txt`。
- NMG 外交动作：`ywc_nmg_autonomy_negotiation`。NMG 作为墨西哥属邦且持有 `ywc_je_new_ming_mexican_chain` 时可提议自治谈判，接受后解决该主日志。
- 安装描述文件与开发安装脚本。当前用户数据中的 Mod 路径为 `E:\Victoria3 Mod\yongchang_world`。

## 3. 本轮已完成的复核

### A. 观察 runner 证据字段

已通读 `tools/run_observation_matrix.ps1`，确认无悬空引用，且 `hidden_preload_only` 没有被解释成进入战局或完成长期观察。

runner 现在使用无 BOM 的紧凑 JSON 写入 `content_load.json`，并从隔离 debug 日志记录：

- `mod_mount`
- `version_match_evidence`
- `dlc_mount_evidence`
- `expected_mounted_dlc`
- `observed_mounted_dlc`
- `dlc_ownership_backend`
- `store_backend_failure_count`
- `dlc_state_matches_config`

真实隐藏启动证据表明：Mod 已挂载并匹配 1.13.11；`none/47` 中请求无 DLC 时观察到无 DLC，`dlc_state_matches_config=yes`。`wave/11` 中请求 `dlc018_ep2`，但所有权后端不可用，观察到的 DLC 为空，故如实记录 `dlc_state_matches_config=no`，而不是伪造成功。

已知根因：PowerShell 5.1 的 `Set-Content -Encoding UTF8` 会写入 UTF-8 BOM，游戏拒绝带 BOM 的 `content_load.json` 后静默回退到“全 DLC、无 Mod”。该问题已修复，Mod 挂载证据已连续多次成功。

### B. NMG 外交动作

已确认主日志 `ywc_je_new_ming_mexican_chain` 在开局加给 `NMG`，外交动作门禁前提成立。

隐藏启动日志成功枚举 `common/diplomatic_actions`；以下错误均为零：

- Unknown trigger
- Unknown effect
- Invalid database object
- 缺失本地化
- 数据库冲突

英文和简体中文本地化均已提供，使用 `ywc_` 前缀。

### C. 原生 scripted_tests 烟测套件

已新增只读检查 `ywc_nmg_autonomy_action_ready`：

- NMG 持有自治谈判主日志，或已经有 `ywc_nmg_autonomy_negotiation_opened` 变量时通过。
- 超过 `1836.2.1` 仍未满足时失败。
- 不修改战局数据。

从游戏引擎字符串确认，Mod 内路径 `tools/scripted_tests` 是正确的查询路径，并存在 `scripted_tests after` 执行命令。但目前没有真实进入战局并执行该套件的证据，不能宣称烟测已运行。

## 4. 当前验证结果

```text
python -m unittest discover -s tests -q  -> Ran 97 tests; OK
python tools/ywc_check.py                 -> exit 0
git diff --check                           -> pass
隐藏启动 Victoria 3                       -> Mod mounted，匹配 1.13.11
相关脚本错误关键词                         -> none
tools/collect_smoke_logs.ps1 -NoLaunch    -> status=clean，finding_count=0
工作树                                     -> clean
```

证据文件：

- [发行验收记录](release/v0.1-acceptance.md)
- [隐藏启动摘要](../artifacts/smoke/latest-summary.txt)
- [十国汇总](../artifacts/smoke/core-country-summary.json)
- [观察矩阵摘要](../artifacts/observe/matrix-summary.json)
- [外交动作定义](../yongchang_world/common/diplomatic_actions/ywc_diplomatic_actions.txt)
- [原生发布烟测](../yongchang_world/tools/scripted_tests/ywc_release_smoke.txt)

典型 Mod 挂载日志：

```text
Mounted Data: E:/Victoria3 Mod/yongchang_world
Mod The Yongchang World (the_yongchang_world) version 1.13.* successfully matched game version 1.13.11.
```

三枚本体兼容层 DLL 未被本仓库修改；此前核验的长度均为 `5452240`，最后写入时间为 `2026/7/3 20:40:00`。

## 5. 尚未完成、不可宣称完成的门槛

- 五配置（`none`、`sphere`、`charters`、`wave`、`all`）× 三种子（11、23、47）× 1846/1866/1900 的真实观察局。
- 十国逐国选国、进入 1836 和完整 DLC UI 检查。
- 在真实战局中实际执行 `ywc_release_smoke.txt`。
- NMG 墨西哥属邦关系、外交动作可用性和主日志完成效果的进入战局运行时证据。

`artifacts/observe/matrix-summary.json` 的 15 条记录仍为 `not_run_no_desktop_interaction`，总体状态为 `pending_manual_ui_observation`。`tools/check_release.py` 因此应继续返回未通过；不要通过改写矩阵状态绕过门禁。

直接启动 exe 时，`disabledDLC` 无法稳定控制已拥有 DLC：所有权后端会在不同启动间出现“全拥有”和“不可用”两种状态。单 DLC 配置在没有官方启动器 UI 的条件下不能宣称完成。

## 6. 建议 GLM 接手顺序

1. 先运行 97 个 Python 测试和 `ywc_check.py`，确认接手时基线未漂移。
2. 复核 `run_observation_matrix.ps1` 与 `tests/test_observation_schema.py`、`tests/test_release_gate.py`，重点检查上述证据字段的语义边界。
3. 检查 NMG 外交动作定义、本地化和隐藏启动日志；不要把日志解析成功等同于真实外交动作执行成功。
4. 若获得真实战局、存档导出或受支持的 headless 证据，再更新矩阵；否则保持 pending。
5. 所有改动完成后同步更新 `docs/release/v0.1-acceptance.md`、`CHANGELOG.md` 和本交接文档。

## 7. 常用命令

```powershell
Set-Location 'E:\Victoria3 Mod'
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:\SteamLibrary\steamapps\common\Victoria 3\game'
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
git -c safe.directory='E:/Victoria3 Mod' status --short --branch
```

隐藏启动前先确认没有已有 `victoria3.exe`，结束时只按 PID 停止本次创建的进程；不要停止用户原本运行的进程。

## 8. 交接完成标准

只有在以下证据齐全后才能把目标标为完成：

- 全部测试和静态检查通过。
- 无 DLC、三种单 DLC、全 DLC 均有实际启动并进入 1836 的证据。
- 至少三种随机种子完成 1836—1900 真实观察，异常有分类。
- 十国边界与 `NMG` 墨西哥属邦关系有运行时证据。
- NMG 外交动作和原生 scripted_tests 有真实战局执行证据。
- 发行记录、变更记录和已知限制同步更新。
- 工作树干净，且无桌面操作、无本体目录和 DLL 修改。

当前目标必须保持为“进行中”，不要调用完成门禁。
