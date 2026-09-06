# 《永昌世界》交接给 GLM

更新时间：2026-09-06
仓库：`E:\Victoria3 Mod`
分支：`codex/yongchang-world-bootstrap`
代码验收基线：`91d5f54 feat: wire Shun and Jinhai journals to decision events`

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

真实隐藏启动证据表明：Mod 已挂载并匹配 1.13.11；`none/47` 中请求无 DLC 时观察到无 DLC，`dlc_state_matches_config=yes`。`wave/11` 与 `all/23` 中所有权后端不可用，观察到的 DLC 为空，故如实记录 `dlc_state_matches_config=no`，而不是伪造成功。

runner 还带有实证守护：对已持有真实启动证据（`status=hidden_preload_only` 且 `mod_mount=mounted`）的配置/种子组合重跑 `-NoLaunch` 时，会原样保留现有 `run.json`，不会覆盖成 `not_evaluated_no_launch` 空壳。已用 `-NoLaunch -Config none -Seed 47` 重跑验证文件哈希不变。

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

### D. 本地化审计与烟测收集器

- 新增 `tests/test_localization_parity.py`：双语键集合必须对齐，且禁止“键名小写化”式占位标题。
- 审计发现并修复 57 个占位 journal/路线标题（十国全部主日志与路线，两种语言，共 114 行），例如 `ywc_je_new_ming_mexican_chain:0 "new ming mexican chain"` → `"The New Ming-Mexico Chain"` / `"新明—墨西哥链条"`。
- `tools/collect_smoke_logs.ps1` 的 `latest-summary.txt` 现在报告 `mod_mount=mounted|not_mounted|unknown_no_debug_log` 并附挂载原文行；该字段只作记录，不改变 clean/error 判定。fixture 级测试覆盖三种情形。
- 已用默认用户目录的一次真实隐藏启动端到端复核：`status=clean`、`finding_count=0`、`mod_mount=mounted`（挂载行时间戳 09:38:42）。

### E. 烟测套件静态验证与安装脚本修复

- 烟测套件（从未被游戏解析过）的触发器词汇已静态对齐先例：`game_date` 与 `is_subject_of = c:X` 有本体用法先例，`exists = c:X` 出现在 mod 自身解析干净的颜色脚本中；带引号的日期字面量已规范化为本体的裸字面量形式（`game_date > 1836.2.1`、`last_date = 1900.1.1`）并用测试锁定。真实执行证据仍需进入战局。
- `tools/install_dev_mod.ps1` 在本机默认的 Windows PowerShell 5.1 下会因 `-Encoding utf8NoBOM`（PS6+ 值）参数绑定失败而无法运行；已改为 `UTF8Encoding($false)` 写无 BOM 描述符，并实际运行验证（真实用户目录的 `yongchang_world.mod` 内容不变）。
- 探针目录的 `shadercache`（纯游戏缓存，约 3.4G）已清理；`run.json`、日志等证据文件保留。

### F. 静态事实核验（本轮）

- 启动钩子：`on_game_started_after_lobby` 在本体 `00_code_on_actions.txt:13` 真实定义，mod 用子 on_action `ywc_on_game_started_after_lobby` 挂接，未覆盖原版 effect；四个 AI 修正（SHU/JHG/DMG/NQG）与 `guardrails.json` 一致。
- DLC 门禁：`ep1_content`、`mp1_content`、`ep2_content` 三个 ID 在本体对应 DLC 的成就文件中原样使用（`has_dlc_feature = ep1_content` 等），mod 引用的门禁 ID 真实有效。
- 基线快照：重跑 `tools/export_vic3_baseline.py` 导出的 `country_tags`、`state_regions`、`states` 与仓库 `data/baseline/vic3-1.13.11.json` 逐键完全一致，测试基线与已安装的 1.13.11 同步。

### G. 计划锁定清单与引用完整性审计（本轮）

- 计划 01–03 的锁定文件路径逐项审计：7 个路径（`ywc_regional_*` 系列、`ywc_core_country_events.txt`）不存在，但全部以按区域拆分的形式实现（如 `ywc_regional_buildings.txt` → `ywc_northeast/inner_asia/southwest/ocean_buildings.txt`），是计划文档的命名漂移，不是内容缺失。
- 新增 `tests/test_reference_integrity.py`：`set_strategy`、`add_modifier`、journal、事件和 yes 式 `ywc_` 引用必须解析到定义——全部通过。
- **重要发现**：71 个 journal 完成变量中 58 个没有设置者。事件链记录的是 `ywc_<tag>.N_success/_failure` 序号变量，从未桥接到 journal 的 `*_resolved` 完成条件，导致大多数主日志/路线既不能完成也不能失败，违反计划 03“主日志可完成、失败并进入分支”的设计约束。58 项以显式豁免清单固化在测试中：新增缺口会让测试变红，补一条接线即可从清单移除。逐国接线需要确认 journal↔事件映射与设计意图，本轮未臆改。
- **桥接前提的进一步核实（本轮）**：映射不是“丢失”而是“不存在”——62 个事件中仅 5 个（bootstrap 4 个、shared 1 个）有 journal pulse 触发者，其余 57 个（`ywc_dmg.1-8`、`ywc_nqg.1-8`、shu/jhg 与 steppe/highland 文件、`ywc_dlc.1`）无触发、无 journal 锚点、共用同一占位标题（"A Crisis of Direction"）。接线的前置任务是为十国撰写真实事件内容，属大内容工程；已写入验收记录的已知限制。
- `ywc_je_new_ming_mexican_chain` 与 `ywc_je_eternal_yongchang` 是已接线的例外（分别由外交动作与 bootstrap 事件完成）。
- `.metadata/metadata.json` 的 short_description 仍停留在四国阶段的“四国垂直切片”，已改为“十国垂直切片”并用测试锁定；随后一次真实隐藏启动复核 `status=clean`、`finding_count=0`、`mod_mount=mounted`（挂载行时间戳 11:06:38）。

### H. DMG 事件链接线（本轮，模式样板）

- **DMG（东明）成为第一个 journal 全部可玩的国家**：3 个辅助日志（南明法统、西班牙边患、本地契约）经 `ywc_dmg.1-3` 决策事件完成或失败；2 条路线按 `content_catalog` 的三态契约（success/abandon 完成、failure 失败）经 `ywc_dmg.4-5` 接线，并新增第三个“放弃”选项。
- journal 采用已验证的 bootstrap 模式：`on_monthly_pulse` 在未决时触发决策事件。事件文本双语，遵循计划 03 约束（对西班牙停战/战争选择、本地文化整合、不自动夺取全吕宋）。事件 6-8 保留为后续链深预留。
- 豁免清单 58 → 53；隐藏启动验证 `common/events` 枚举干净（0 Unknown/Invalid/缺失本地化）。
- **后续轮次的标准任务模板**：按同一模式逐国接线——读 `data/content/content_catalog.json` 该国条目（journal/事件/路线三态契约）→ 撰写该国决策事件（双语）→ journal 加 pulse/complete/fail → 豁免清单减项 → 全量测试 + 隐藏启动。剩余九国：SHU、JHG、NQG、OIR、MNG、TIB、KOR、LAN、NMG。

### I. NQG 事件链接线（本轮，第二个国家）

- **NQG（北清）journal 全部可玩**：流亡日志经 `ywc_nqg.1` 完成或失败；亲俄之择为决策型日志——两个选项都完成并记录所择路径（`ywc_nqg_russia_aligned` / `ywc_nqg_russia_refused`）；岛屿社会日志经 `ywc_nqg.3` 完成或失败；两条路线（库页光复、多族之邦）按三态契约经 `ywc_nqg.4-5` 接线并带放弃选项，遵循计划 03“扩张不得把北清变成满洲大国”的约束（catalog：forbidden become_great_power / mass_settler_colonization）。
- 事件 6-8 保留；豁免清单 53 → 48；隐藏启动（`none/23`）验证解析干净且 `dlc_state_matches_config=yes`。
- 下一个建议国家：SHU 或 JHG（`ywc_shu_jhg_events.txt` 每国 8 个事件）。

### J. SHU + JHG 事件链接线（本轮，第三、四个国家）

- **SHU（大顺）journal 可玩**：士商（`ywc_shu.1`）、黑水边疆（`.2`）、鸦片之问（`.3`）成败型接线；士绅官僚整合与海关商政改革两条路线按三态契约经 `.4-5` 接线（事件 6-8 保留）。
- **JHG（靖海）journal 可玩**：海上网络、继承之诏、行商议事会（`ywc_jhg.1-3`）成败型；藩屏水师与南洋商会两条路线经 `.4-5` 接线。计划 03 约束“提高自治必须加重大顺猜忌与财政成本”已在事件描述中体现，实质后果效果留给平衡轮。
- **新发现的 catalog 漂移**：SHU 主日志键名不一致——bootstrap 实际接线 `ywc_je_eternal_yongchang`（SHU 开局持有、可玩），而 catalog 声明的 `ywc_je_yongchang_century` 是 `ywc_shu.txt` 中从未被添加的死键（保留在豁免清单）。后续统一时二选一：改 catalog 或删死键。
- 豁免清单 48 → 38；隐藏启动（`sphere/47`）解析干净。剩余六国：OIR、MNG、TIB（steppe/highland 文件 24 事件）、KOR、LAN、NMG（各 8 事件）。

## 4. 当前验证结果

```text
python -m unittest discover -s tests -q  -> Ran 112 tests; OK
python tools/ywc_check.py                 -> exit 0
git diff --check                           -> pass
隐藏启动 Victoria 3                       -> Mod mounted，匹配 1.13.11
相关脚本错误关键词                         -> none
独立隐藏启动证据                         -> status=clean，finding_count=0，mod_mount=mounted
工作树                                     -> clean
```

注意：`artifacts/smoke/latest-summary.txt` 是被 `.gitignore` 忽略的生成文件；全量单元测试会依次运行多个 fixture，最后可能留下 `userdata-broken` 的预期 error 摘要。因此它不能单独作为最新隐藏启动 clean 证据，验收时应以独立隐藏启动的日志或配置/种子专属 `artifacts/observe/*/run.json` 为准。

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
- 48 个 journal 完成变量未接线（见 3.G）：DMG 与 NQG 已各完成 5 个 journal 接线；其余国家的大多数主日志/路线在 v0.1 中不可完成，需逐国确认 journal↔事件映射后补桥接。

`artifacts/observe/matrix-summary.json` 的 15 条记录仍为 `not_run_no_desktop_interaction`，总体状态为 `pending_manual_ui_observation`。`tools/check_release.py` 因此应继续返回未通过；不要通过改写矩阵状态绕过门禁。

直接启动 exe 时，`disabledDLC` 无法稳定控制已拥有 DLC：所有权后端会在不同启动间出现“全拥有”和“不可用”两种状态。单 DLC 配置在没有官方启动器 UI 的条件下不能宣称完成。

## 6. 建议 GLM 接手顺序

1. 先运行 112 个 Python 测试和 `ywc_check.py`，确认接手时基线未漂移。
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
