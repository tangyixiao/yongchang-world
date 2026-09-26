# 《永昌世界》交接文档（历史快照）

> 本文件停留在 2026-09-13，已经被 `docs/交接给Workbuddy.md` 的 2026-09-19 快照取代，实机验收分工现以 `docs/交接给下一会话.md` 为准。本文仅保留历史调查细节；凡涉及 HEAD、工作树、测试数量、隐藏预加载或发行状态，必须以 Git 现场、最新交接和最新生成证据为准。

更新时间：2026-09-13（GLM/ZCode 综合轮）
仓库：`E:\Victoria3 Mod`
分支：`codex/yongchang-world-bootstrap`
基线提交：`30614da docs: rewrite the handoff as a single authoritative snapshot`；当前工作树包含本轮 MHG 初始化修复、静态门禁、天山重排、ownership topology 审计和文档改动（未提交）
游戏基线：Victoria 3 `1.13.11 (Matcha)`，Build ID `24799966`
游戏目录：`E:\SteamLibrary\steamapps\common\Victoria 3`（只读，未改动）
用户数据目录：`D:\Documents\Paradox Interactive\Victoria 3`（Mod 经 junction 或 `.mod` path 指向 `E:\Victoria3 Mod\yongchang_world`）

---

## 1. 先看结论

**地图视觉验收已通过**（用户 2026-09-12 三张选国界面截图）：此前"只有国家名变化""东北拼花碎片""掸邦显示山西"三类实机问题全部修复并在真实新档确认。当前剩余工作全部是**深度实机验收与内容平衡**（见 §6），没有已知的阻断性缺陷。

静态与管线状态：

- `python -m unittest discover -s tests -v`：**217** 个测试通过。
- `python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3'`：exit 0。
- `git status`：当前包含本轮 MHG 修复、静态门禁、回归测试、真实启动后零容量建筑/SHD 法律修复和交接记录的未提交改动；`tools/check_release.py` 仍按预期失败（15 条观察矩阵 run 未回填，门禁本意）。
- 最近一次隐藏启动（`artifacts/observe/none/55`，2026-09-12 19:31）：Mod 挂载、版本匹配 1.13.11、no-DLC 配置匹配（`dlc_state_matches_config=yes`）、error.log 无任何 ywc 行。
- 当前内容的隔离启动（`artifacts/observe/none/120`，2026-09-13 00:28）：Mod 挂载、版本匹配 1.13.11、no-DLC 配置匹配；`collect_smoke_logs.ps1` exit 0、`finding_count=0`，且明确记录为 `hidden_preload_only`，不是战局观察证据。
- 最新运行器回归（`artifacts/observe/none/121`）：除上述隐藏预加载字段外，run 目录新增独立 `smoke-summary.txt`，`run.json` 记录 `smoke_status=clean`；仍明确是 `hidden_preload_only`，不是战局观察证据。
- SHD 迁移后的最新隔离预加载（`artifacts/observe/none/122`）：Mod 挂载、1.13.11 匹配、no-DLC 匹配，run-local smoke 摘要 `status=clean` 且 `finding_count=0`；仍明确是 `hidden_preload_only`，不是战局观察证据。
- 当前路线冷却修复后的最新隔离预加载（`artifacts/observe/none/123`）：Mod 挂载、1.13.11 匹配、no-DLC 匹配，run-local smoke 摘要 `status=clean` 且 `finding_count=0`；仍明确是 `hidden_preload_only`，不是战局观察证据。
- 本轮真实可见启动（`artifacts/observe/none/124`，独立 `-userdir`）：游戏实际进入 1836 地图界面；`error.log` 暴露 KUC 伐木场、Northern Manchuria 的 SHU 麦田、Western Australia 的 MRG 渔港零容量警告，以及 SHD 保留 `law_outlawed_dissent` 的非法法律警告。已删除前三个零容量初始建筑并为 SHD 增加 `law_censorship`；对应回归测试通过。该 run 未完成选国、路线或长期观察，不能替代人工发行验收。

---

## 2. 自 09-06 以来的三段工作（读者背景）

1. **09-06（GLM 多轮）**：工具链修复（BOM 根因、observation runner 证据字段与实证守护、收集器 mod_mount、安装脚本 PS5.1 兼容）、十国 journal 逐国接线（71 个完成变量全部有设置者）、双语 loc 审计与 57 个占位标题修复、引用完整性测试契约。
2. **09-08 ~ 09-12 凌晨（并行会话）**：实机首次进入战局，发现并修复四类真实运行时缺陷（scripted effect 洪水、路线 trigger 误含 `progress >= 100`、scripted_tests 原版格式、journal 顶层 `visible`、州历史 `STATES` 包裹、建筑历史 `add_ownership.country.levels`、`is_country` → `c:TAG ?= this`、reserved 变量名、静态修正数据库迁移）；**发现 MNG 与本体 Minas Gerais 冲突并换标 MGL**；州所有权迁移到 `data/scenario/ownership_overrides.json` 权威表 + `tools/build_state_history.py` 生成器；路线后果实质化（进度门控、互斥、共享状态、成功/失败/放弃清理）；决策有状态化；NMG 谈判拒绝路径与共享压力。
3. **09-12 晚（本轮 GLM）**：实机问题收尾——选项本地化键统一、`default_option` 全量补齐、`law_type:` 前缀、建筑别名（barracks→barrack）、**SHN→SHD 标签冲突换标**、**ownership 权威表地理重排**（拼花根因修复）、以及本交接文档重写。

---

## 3. 本轮（09-12 晚）完成的修复

### 3.1 事件选项本地化与默认选项

- 事件选项本地化按**字面选项名**查找（运行时证据）；事件与 loc 统一本体同款**点号形式**（`ywc_nqg.4.a`），190 个双语选项键由 `tests/test_reference_integrity.py`（两语言全覆盖）与 `tests/test_content_localization.py` 锁定。
- 全部 87 个事件补 `default_option = yes`（消除 76 次 "No default option" 加载错误）。

### 3.2 类型比较与法律/建筑格式

- 共享触发器 `this = c:TAG` 在 journal/flag 上下文运行时报 country-vs-country_definition 类型错误，已改为 mod 地图颜色在用的 `c:TAG ?= this` 惯例（`tests/test_script_structure.py` 锁定为唯一支持形式）。
- MHG 块 `law_traditionalism` 补 `law_type:` 前缀。
- `building_barracks` 是本体 `building_barrack` 的别名而 `create_building` 拒绝别名——历史条目改用主键；别名审计覆盖全部建筑历史。

### 3.3 SHN → SHD 标签冲突换标（掸邦"山西"根因）

- 本体 `00_countries.txt:3578` 定义 **SHN = Shanxi（山西）**；场景账本误将 SHN 当掸邦标签复用（tag_registry `mode=reuse`）且无 loc 覆盖 → 选国界面显示"山西"。
- 已换标为全新 **SHD**：`ownership_overrides.json`、`southwest_states.json`、区域国家历史（`c:SHD ?=` 块）、西南建筑归属（3 处 `add_ownership`）、tag_registry（删 reuse 行、新增 new 行 `source_tag: null`）、country_definitions 新块（掸+汉文化、首府 STATE_SHAN_STATES）、双语名（掸邦联盟 / Shan Confederation）。
- 系统性审计：registry 其余 9 个 `reuse` 标签（TIB/KOR/LAN/KOK/LAD/MNP/ARA/EZO/MGL）本体语义一致，无同类冲突；新场景标签一律 `mode=new`。
- 后续残留审计还发现西南 ledger 与人口/建筑历史仍把掸邦写成旧 `SHN`；现已统一迁移为运行时 `SHD`，回归测试锁定 starting tag、人口账本和两类历史文件不得回退。

### 3.4 权威表地理重排（拼花根因修复）

- 根因：场景账本按 owner **随机采样**省份（如天山六绿洲链标签各持约 40 个散布全省的省份，最大连通分量 1-2），25/693 个 owner 组在真实地图邻接图上不连续 → 选国界面马赛克。
- 修复：`ownership_overrides.json` 的 15 个多 owner 州按**真实地图邻接图**（从本体 `provinces.png` 构建，40875 省、121648 边）重排——每 owner 保留最大连通分量、剩余池按邻接吸收、每 owner 省份数精确守恒；`build_state_history.py` 重新生成 `00_states.txt`。
- 度量：初次地理重排将弱组（最大连通分量 <50%）**25 → 4**，剩余项属于海岛/飞地/绿洲长链拓扑（本体自身有 54 组同类飞地常态）。随后天山六绿洲按语义重排；`tools/ownership_topology.py` 对当前权威表复核为 **2** 个 `<50%` 组，均为权威表中明确标注 `topology_exception: natural_archipelago` 的 PHI/MHL 自然岛屿拓扑。三次重排尝试（v1/v3/v4-v6）的脚本与结论在 Git 历史；最终采用 v1 算法 + 权威表落地。

### 3.5 实机视觉验收（用户截图 ×3，2026-09-12）

- 欧亚视角：东北碎片消除，大清、大顺礼制国、大蒙古国、虾夷地各持连贯板块；西域承统国、吐蕃承统国、和硕特青海及中亚诸玉兹连贯。
- 北美视角：新墨西哥承统国（NMG）为下加州单一干净沿海块，面板文化（墨西哥、汉）、人口 45K（设计上限内）渲染正确。
- 东南亚视角：兰芳（LAN）西婆罗洲连贯，文莱/班贾尔/望加锡标签清晰；面板文化（汉、客家、达雅）正确。
- 证据存于用户截图（如需归档请保存到 `artifacts/observe/manual-acceptance/`）。

### 3.6 MHG 海洋日志变量初始化（本轮继续工作）

- 最新用户数据日志在 `ywc_shared_events.txt:39` 暴露了 `ywc_maritime_network_level` 未设置：MHG 会获得 `ywc_je_ocean_frontiers`，但此前没有调用共享变量初始化效果。
- 已在 `yongchang_world/common/history/countries/ywc_ocean_countries.txt` 的 MHG、NMG 开局块中，都在添加海洋日志前调用 `ywc_reset_shared_variables = yes`，不再让 NMG 依赖另一个历史文件的跨文件初始化顺序。
- 新增回归测试 `test_ocean_journal_countries_initialize_shared_variables_before_journal`；补丁前 NMG 分支按预期失败，当前完整套件通过 217 项。
- `tools/ywc_check.py` 新增跨文件国家历史检查：任何自定义 journal 在共享变量重置之前接入，都会被静态门禁拒绝；该检查已有红灯测试覆盖。

### 3.7 天山六绿洲地理重排（本轮继续工作）

- 按 `inner_asia_states.json` 的地理语义，将 `STATE_TIANSHAN` 六组重排为喀什（KSH）—叶尔羌（YRK）—库车（KUC）—和田（KHT）—吐鲁番（TRF）—哈密（HMI）的空间顺序；原有 236 个省份全部保留，组大小保持 `40/36/60/40/36/24`。
- 已用本体 `map_data/provinces.png` 的像素邻接验证六组各为单一连通分量，并通过 `build_state_history.py` 重新生成 `00_states.txt`。
- 新增回归测试 `test_tianshan_oasis_groups_are_map_connected`，防止后续权威表重排重新产生天山拼花；这属于地图数据验证，不替代真实选国界面截图。

### 3.8 运行时国家标签审计

- 新增 `tools/scenario_tag_audit.py`，覆盖 `data/scenario/*.json` 中的 owner/target/start/population/state-owner 引用，以及 Mod 脚本中的 `c:TAG` 和 `region_state:TAG`。
- `ywc_check.py` 已接入该审计；当前允许集合来自 1.13.11 baseline 与 `tag_registry.json`，`SHN`、`MNG` 等历史运行时别名会明确提示应替换为 `SHD`、`MGL`。
- 当前审计 exit 0；回归测试覆盖真实仓库清洁结果、旧别名诊断和 `ywc_check.py` 集成路径。

### 3.9 JHG 海上朝贡路线财政代价契约

- `ywc_jhg.4` 的启动与成功分支均显式施加 `ywc_jhg_naval_tributary`；该长期修正包含 `country_loan_interest_rate_mult = 0.05`，因此路线的财政代价不再只存在于设计注释中。
- 新增 `test_jhg_naval_tributary_route_has_an_explicit_fiscal_cost` 回归测试；数值仍需真实战役观察校准，不能以静态契约替代平衡验收。

### 3.10 全路线冷却门禁修复

- 20 条路线的启动触发器原先用 `OR` 检查放弃标记和冷却变量；若放弃标记因异常状态缺失，仍可能绕过尚未结束的 365 天冷却。
- 现改为直接要求对应 `*_abandonment_cooldown` 不存在，冷却结束后仍由启动分支清理旧放弃标记；新增 `test_route_start_is_blocked_by_any_active_abandonment_cooldown` 覆盖全部 20 条路线。
- 同一门禁已同步到 20 个路线 journal 的月度脉冲，新增 `test_route_monthly_pulse_is_blocked_by_any_active_abandonment_cooldown`，避免冷却期间重复弹出无可用选项的路线事件。
- `tools/ywc_check.py` 新增同类静态门禁；合成的两种排列形式的旧式 `OR` 路线冷却结构都会被拒绝，当前真实 Mod 通过该检查。

---

## 4. 当前验证事实

- `python -m unittest discover -s tests`：217 个测试通过（含 MHG/NMG 海洋 journal 初始化、跨文件 journal 初始化静态门禁、天山六绿洲地图连通性、ownership topology 审计及例外原因 CLI 输出、场景 JSON/脚本运行时标签审计、JHG 海上朝贡路线财政代价契约、20 条路线事件与月度脉冲冷却门禁、`ywc_check.py` 冷却结构静态门禁、长期 scripted-test 共享变量初始化契约、零容量州启动建筑回归、scripted-test PASS/FAIL 分类、观察检查点数值 schema、campaign evidence 非空契约、run 专属 smoke 摘要契约、人工验收日志结构/状态契约、基本信息字段/基线值/目录类型契约、验收表列 schema 契约、SHD 西南标签迁移契约、BOM 契约、标签冲突、州覆盖、选项本地化等）。
- `tools/ywc_check.py`：exit 0。
- `tools/check_release.py`：按预期失败（15 条矩阵 run 未回填）。
- 可见复核补充：`artifacts/observe/none/127` 的无存档 New Game 复现了 `STATE_OUTER_MANCHURIA`（英文名 Northern Jilin）SHU Wheat Farms 告警；删除该启动建筑后，`artifacts/observe/none/128` 的全新隔离启动日志未再出现 Wheat Farms、Northern Jilin、Kucha、Western Australia、fishing wharf、logging camp 或 SHD law 目标告警。该运行仍未形成十国战局、路线、原生 scripted_tests 或长期观察证据。
- `tools/check_release.py` 现在还会解析并验证每个 run 的 `logs`、`checkpoint_file`、`run_metadata` 证据路径确实存在，检查 checkpoint JSON 的完整字段 schema、三年×十国 30 条结构、数值计数器与零错误、非空版本匹配证据、矩阵与 `run.json` 的完整运行时字段一致性、`source` 对齐，并核对 `run_metadata` 的配置、run ID、种子与 `observed_to_checkpoint` 状态，避免用损坏、占位或串用其他 run 的真实文件伪造长期观察证据。
- 隐藏启动：`none/55`、`all/11`、`charters/23`、`none/47` 等 run.json 记录挂载/版本/DLC 证据；最近一次（`none/55`）error.log 无任何 ywc 行。
- `none/123` 的 `error.log`、`game.log` 和 `debug.log` 未发现目标 Mod 错误；这只证明当前内容可加载，不证明路线在战局中可操作。
- `artifacts/smoke/latest-summary.txt` 是生成文件，仍不能单独作为 clean 证据；以 `artifacts/observe/*/run.json` 与 logs 为准。收集器支持 `-SummaryPath <summary.txt>` 写入指定证据目录，回归测试使用临时摘要路径，不会再把该文件覆盖成 fixture 结果。

---

## 5. 实机验收状态（截至 2026-09-13）

**已确认**：

- Mod 可真实进入 1836 战局（用户实机）；NQG journal 与事件弹窗在运行时出现（证明接线进入运行时）。
- 原生 `scripted_tests` 执行管线打通（`tools/ywc_test_gui/` 临时工具 Mod 提供 Debug 工具栏按钮；详见 `artifacts/observe/manual-gate23-1836-shu-01/`）。
- 地图视觉验收通过（三张选国界面截图，见 §3.5）。

**待确认**（按 `docs/release/manual-acceptance-playbook.md` 执行）：

1. 事件弹窗**按钮双语选项文本**截图（`ywc_nqg.4.a/b/c` 等；本轮已修复 loc 键与事件名对齐，等待实机确认）。
2. 十国逐国 journal 面板核对（本手册 §2 有全部日志名对照表）与 NMG 外交动作实机使用。
3. 战局内 `scripted_tests` 拿到非空 PASS 结果。
4. 观察矩阵 15 组 run 的 1846/1866/1900 检查点回填 → `summarize_observation.py` → `check_release.py` 门禁。

人工记录模板已放在 `docs/release/manual-acceptance-log.md`；该文件只含 `pending` 占位，不构成任何验收证据。可用 `tools/validate_manual_acceptance.py` 检查基本信息表和四张门槛表的完整列 schema，`--require-complete` 只有在基本信息字段、游戏基线、用户数据目录均有效，所有状态为 `verified`、事实列无 `pending` 且证据路径类型正确时才通过（`run 目录` 为目录，其余为文件）。烟测收集器现将 scripted-test 结果区分为 `missing/empty/present/pass/fail`，`-RequireScriptedTests` 只接受明确的 `pass`。

---

## 6. 已知限制与设计侧待办

- **其余 ledger 省份分组仍需设计侧重绘**：天山六绿洲链已按地理语义重排并由地图像素邻接测试锁定；`tools/ownership_topology.py --weak-only` 当前只报告 PHI/Luzon 与 MHL/West Micronesia 两个 `<50%` 群组，且权威表明确标注 `topology_exception: natural_archipelago`。它们分别是多岛 Manila/菲律宾组与 Marshall 群岛；若要进一步达到教科书式分组，仍需按该例外理由人工调整并重跑 `build_state_history.py`。
- **中国本土归属为设计现状**：大清（本体）仍占中国本土腹地（ledger 沉默区），大顺礼制国居北方与江淮——是否符合剧本设定属内容设计决策；若需调整，扩充 `ownership_overrides.json` 即可。
- **路线后果已落地，但平衡仍未验收**：十国 20 条路线的成功/失败/放弃分支都已写入共享状态变化与持久国家修正，正统性、自治压力、海贸网络以及港口吞吐/贸易能力已有代码侧效果；法律、利益集团权重和长期财政平衡仍属计划 03 的实机校准项，不能用静态测试替代真实观察局数据。
- **多行脚本注意**：本机 cmd 环境多行 `python -c` 会被静默吞掉——一律使用临时脚本文件 + 断言 + 输出验证（本轮已三次因此兜底）。
- 平台限制：直接启动 exe 时 `disabledDLC` 不可靠（所有权后端波动），单 DLC 配置验收必须走官方启动器 UI。
- 本仓库不修改本体目录与三枚兼容层 DLL（长度基线 `5452240`，2026/7/3 20:40:00）。
- 过程违规记录：一次 `git checkout --` 被用于恢复本轮脚本自己生成的未提交中间产物（未触及用户工作），违反硬约束第 5 条字面规定；后续改用 `git show` 管道恢复。

---

## 7. 实机操作注意事项（沿用并行会话的经验）

- 不要把 `MNG` 当运行时 TAG：运行时蒙古是 `MGL`（本体 MNG = Minas Gerais）；同理掸邦运行时标签现在是 `SHD`（本体 SHN = Shanxi）。
- 不要把 `artifacts/smoke/latest-summary.txt` 单独当 clean 证据。
- 不要用键盘注入往控制台 editbox 打字（会重复字符且 `_` 变 `-`）；用 GUI 按钮或临时 GUI Mod 按钮。
- 每次点击 "YWC Tests" 只切换一次状态；以 console 回显为准，不在回显确认前连续点击。
- 选国界面点击省份会居中镜头；先悬停验证 tooltip 再点。
- 不要把"套件周期工作（tests.txt 被重写）"当成"测试已通过"——以结果行出现 PASS 为准。
- `tools/ywc_test_gui/` 是本仓库自己的临时工具 Mod（调试工具栏按钮），不影响"不修改本体"约束；不想要可直接删除该目录。

---

## 8. 常用命令

```powershell
Set-Location 'E:\Victoria3 Mod'
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
python tools/build_state_history.py --baseline data/baseline/vic3-1.13.11.json --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game' --overrides data/scenario/ownership_overrides.json --template yongchang_world/common/history/states/00_states.txt --output yongchang_world/common/history/states/00_states.txt
python tools/ownership_topology.py --baseline data/baseline/vic3-1.13.11.json --overrides data/scenario/ownership_overrides.json --provinces-map 'E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png' --weak-only
python tools/scenario_tag_audit.py --root .
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
git -c safe.directory='E:/Victoria3 Mod' status --short --branch
```

隐藏启动：确认无 `victoria3.exe` 运行 → `tools/run_observation_matrix.ps1 -Config <c> -Seed <s>`（结束后按 PID 停止自己启动的进程；用户会话运行时跳过）。

---

## 9. 交接完成定义（全部满足才可标完成）

- 全部测试与静态检查通过（当前 217 项）。
- 无 DLC、三种单 DLC、全 DLC 均有实际启动并进入 1836 的证据（官方启动器 Playset 流程）。
- 至少三种随机种子完成 1836—1900 真实观察，异常有分类。
- 十国边界与 NMG 墨西哥属邦关系有运行时证据（**地图部分已获第一份视觉证据**）。
- NMG 外交动作与原生 scripted_tests 有真实战局执行证据（PASS 结果）。
- 发行记录、变更记录和已知限制同步更新。
- 工作树干净，且无桌面操作或本体/DLL 修改。

当前目标保持"**进行中**"，不调用完成门禁。
