# 《永昌世界》交接给 Workbuddy

> 2026-09-19 晚：实机验收的**分工**已被 `docs/交接给下一会话.md` 的「Agent 自主验收」协议取代——实机门槛由 Agent 桌面自动化执行，用户只保留一次最终验收。本文的已验证事实与工具说明仍然有效，但分工、验收预算与完成定义以新文件为准。

更新时间：2026-09-19
仓库：`E:\Victoria3 Mod`
分支：`codex/yongchang-world-bootstrap`
当前 HEAD：`3cba19e feat: bias flavor events toward country directions`
游戏基线：Victoria 3 `1.13.11 (Matcha)`，Build ID `24799966`

> 这是当前工作区快照。请以当前 Git 状态、本文和最新生成证据为准；旧的 `docs/交接给GLM.md`、README 或计划文件中的旧测试数字不能覆盖本快照。

## 一句话结论

《永昌世界》的十国内容和特色事件实现已经写入当前代码，当前工作树的静态合同通过，提交态 HEAD 的隐藏预加载通过；用户三张截图只证明东北、西域、下加州和西婆罗洲的局部地图显示。真实发布验收仍未完成：五种 Playset、十国逐国 1836 战局、原生 `scripted_tests`、15 组长期观察矩阵和路线平衡都不能宣称通过。

## 1. 工作区与保护边界

- 当前工作树不是干净树：32 个已跟踪文件有修改，26 项未跟踪，共 58 项。它们属于当前工作，不要 `git reset --hard`、`git checkout --`、`git clean`、`git add -A` 或擅自提交。
- 重要的未跟踪文件包括（承接时的 7 个 + 本轮新增）：
  - 工具：`tools/ownership_topology.py`、`tools/scenario_tag_audit.py`、`tools/validate_manual_acceptance.py`、`tools/record_checkpoint.py`、`tools/observation_status.py`、`tools/inspect_playsets.py`、`tools/content_reachability.py`、`tools/modifier_audit.py`、`tools/scripted_test_audit.py`、`tools/startup_data_audit.py`、`tools/acceptance_preflight.py`
  - 测试：`tests/test_manual_acceptance.py`、`tests/test_ownership_topology.py`、`tests/test_scenario_tag_audit.py`、`tests/test_record_checkpoint.py`、`tests/test_observation_status.py`、`tests/test_inspect_playsets.py`、`tests/test_content_reachability.py`、`tests/test_modifier_audit.py`、`tests/test_scripted_test_audit.py`、`tests/test_startup_data_audit.py`、`tests/test_acceptance_preflight.py`
  - 数据与文档：`data/content/reachability_allowlist.json`、`docs/reference/v3-mod-guide-notes.md`、`docs/release/manual-acceptance-log.md`、`docs/交接给Workbuddy.md`
  - `refs/v3_mod_guide_cn/` 与 `.workbuddy/` 已加入 `.gitignore`，不要提交
- 当前修改主要涉及发行门禁、观察证据 schema、人工验收模板、场景 ownership 重排、SHD/MGL 标签审计、启动建筑回归和原生 scripted-test 契约；不要为了整理交接而回退这些改动。
- Victoria 3 本体目录只读：`E:\SteamLibrary\steamapps\common\Victoria 3`。用户数据目录：`D:\Documents\Paradox Interactive\Victoria 3`。不要修改本体或兼容层 DLL。

## 2. 当前内容范围

十国核心内容为 SHU、JHG、DMG、NQG、OIR、MNG、TIB、KOR、LAN、NMG。注意两个标签约定：

- 目录逻辑名是 `MNG`，但本体 `MNG` 是 Minas Gerais；喀尔喀在选国、脚本和观察记录中必须使用运行时标签 `MGL`。
- 本体 `SHN` 是 Shanxi；掸邦联盟已经迁移到新标签 `SHD`。任何新脚本不得恢复 `MNG` 或 `SHN` 的旧场景用法。

本轮特色扩展已完成代码写入：每国一个 0—100 特色变量、3 个承接 journal、3 个特色事件，共 30 个事件；同时有高/低档静态修正、双语本地化、内容目录合同和现有路线反馈。

| 国家 | 运行时 TAG | 特色变量 | 主题 |
| --- | --- | --- | --- |
| SHU 大顺 | `SHU` | `ywc_flavor_shu_court_balance` | 朝廷中士绅、军功与官僚的平衡 |
| JHG 靖海 | `JHG` | `ywc_flavor_jhg_convoy_commitment` | 护航承诺与藩贡预算 |
| DMG 东明 | `DMG` | `ywc_flavor_dmg_huafei_compact` | 华菲地方契约与代表性 |
| NQG 北清 | `NQG` | `ywc_flavor_nqg_island_supply` | 岛屿补给与流亡声望 |
| OIR 卫拉特 | `OIR` | `ywc_flavor_oir_banner_cohesion` | 旗盟协作与牧地防务 |
| MNG 喀尔喀 | `MGL` | `ywc_flavor_mng_south_north_balance` | 南北商路权重 |
| TIB 西藏 | `TIB` | `ywc_flavor_tib_estate_reform` | 寺院地产与地方供役 |
| KOR 朝鲜 | `KOR` | `ywc_flavor_kor_court_reform` | 三司、边镇与海学改革信用 |
| LAN 兰芳 | `LAN` | `ywc_flavor_lan_company_charter` | 矿场股东、矿工与村社契约 |
| NMG 新明 | `NMG` | `ywc_flavor_nmg_federal_bargain` | 华墨自治与墨西哥联邦谈判 |

实现与设计入口：

- 设计：`docs/superpowers/specs/2026-09-14-十国特色事件与机制扩展设计.md`
- 实施计划：`docs/superpowers/plans/2026-09-14-十国特色事件与机制扩展.md`
- 共享特色效果：`yongchang_world/common/scripted_effects/ywc_flavor_effects.txt`
- 特色静态修正：`yongchang_world/common/static_modifiers/ywc_static_modifiers.txt`
- 内容目录：`data/content/content_catalog.json`
- 四个区域事件文件：`yongchang_world/events/ywc_shu_jhg_events.txt`、`ywc_dmg_nqg_events.txt`、`ywc_steppe_highland_events.txt`、`ywc_kor_lan_nmg_events.txt`

## 3. 已验证事实（2026-09-19 复核）

- `python -m unittest discover -s tests -v`：**306/306 通过**，无失败、无错误，本轮耗时 119.588 秒；使用的是本机 `D:\Python\314\python.exe`，地图拓扑用例实际执行而非跳过。
- 新增三个只读/校验工具（详见第 4 节 D）：
  - `tools/inspect_playsets.py`：只读打开启动器 `launcher-v2.sqlite`，核对五个 Playset 是否存在、Mod 是否启用、三个门禁 DLC 开关是否与配置一致，并标出会污染战局的其他 Mod；全部一致 exit 0，否则 exit 1。
  - `tools/record_checkpoint.py`：把某一检查年的十国 CSV/JSON 校验后合并进 `checkpoints.json`，已记录的 `(year,country)` 只有 `--replace` 才覆盖；三年齐全并给出真实战役描述与日志后才允许 `--finalize` 提升为 `observed_to_checkpoint`。
  - `tools/observation_status.py`：只读打印 15 个 run 的进度与缺口。
- `python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'`：exit 0。
- `python tools/scenario_tag_audit.py --root .`：exit 0。
- `python tools/ownership_topology.py --baseline data/baseline/vic3-1.13.11.json --overrides data/scenario/ownership_overrides.json --provinces-map 'E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png' --weak-only`：exit 0；仅报告 PHI/Luzon 和 MHL/West Micronesia 两个已声明的 `natural_archipelago` 岛屿拓扑例外。
- `python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md`：exit 0；当前记录为 `verified=0`、`pending=36`、`failed=0`。
- `python tools/acceptance_preflight.py --root . --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3' --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'`：exit 1，输出即当前的门禁全貌——静态四项 `ok`（含 `startup_data` 1588 个开局建筑 / 2180 个 pop 字段全通过、`scripted_test_vocabulary` 12 个键全部有本体依据）；门槛一 `0/5`、门槛二 `0/10`、门槛三 `0/2`、门槛四 `0/450` 行 `0/15` run 全部 `incomplete`。这一条命令可以替代逐个手跑检查。
- `python tools/observation_status.py --root artifacts/observe`：15 个 run 全部 `0/30` 检查点、`0/15` ready、共 `0/450` 条记录；`charters/47` 连 `run.json` 都没有。这是门槛四的真实起点。
- `python tools/inspect_playsets.py --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3'`：exit 1——启动器里只有 `mods`（当前激活）和 `Yongchang World` 两个 Playset，五个验收用 Playset 都还不存在；`mods` 里还启用了两个 Steam Mod（作弊工具与建造顾问），用它跑观察局会污染证据。三个门禁 DLC 在两个既有 Playset 里都是全开。
- `git diff --check`：exit 0。
- 当前特色内容最近一次隐藏预加载是 `artifacts/observe/none/919`：它在 HEAD `3cba19e` 提交后生成，Mod 挂载、版本匹配、无 DLC 配置匹配、run-local smoke clean，三个日志中没有目标 Mod 错误；它不覆盖 9 月 18—19 日的未提交工作树，状态也明确是 `hidden_preload_only`，不是进入战局或长期观察证据。
- `artifacts/observe/none/915` 也是同类干净隐藏预加载；DLC ownership backend 显示 unavailable，不能据此证明单 DLC Playset。
- 局部地图视觉验收：用户于 2026-09-12 提供三张新 1836 选国界面截图，确认东北、西域、下加州和西婆罗洲的拼花/错标问题已修复。截图尚未作为标准文件归档到仓库，不能替代十国逐国 1836 与动态 UI 验收。

发行汇总的正确验证方式是：

```powershell
python tools/summarize_observation.py --input artifacts/observe --output artifacts/observe/matrix-summary.json
python tools/check_release.py --matrix artifacts/observe/matrix-summary.json --mod-root yongchang_world
```

当前没有 `checkpoints.json`，汇总器会退出 1；发行门禁也会明确拒绝 15 个 `not_run_no_desktop_interaction` run。这是预期的未完成状态，不要手改 `status=verified`。

## 4. 仍需 Workbuddy 完成的工作

### A. 审计与自动化收口（2026-09-19 已完成）

已核对 `git status --short --branch`、`git diff --stat` 与 HEAD `3cba19e`：当前 32 个已跟踪修改和 26 个未跟踪文件全部保留，未做 reset、clean、暂存或提交。全量 306 项测试、静态总检、标签审计、拓扑审计与差异检查均重新运行；自动化侧没有新增阻塞。十国特色子计划的自动验证和提交步骤已按现有提交链标记完成，真实战局验收继续由本计划 Gate 1—4 管理。

### B. 完成真实人工验收

按 `docs/release/manual-acceptance-playbook.md` 操作，并把可回溯路径写入 `docs/release/manual-acceptance-log.md`：

1. 使用官方启动器建立 `none`、`sphere`、`charters`、`wave`、`all` 五个 Playset，并逐一确认实际 DLC 挂载。直接启动 exe 时 `disabledDLC` 不可靠，不能替代启动器 UI。
2. 逐国进入 1836，检查十国开局 journal、首月特色事件和路线事件；MNG 必须按 `MGL` 选国和记录。NMG 还要验证与 MEX 的自治谈判接受/拒绝两支及 365 天冷却。
3. 在真实战局中执行 `ywc_startup_smoke.txt` 与 `ywc_longrun_invariants.txt`，必须取得原生非空 `PASS` 结果。仅有静态扫描、隐藏预加载或 `tests.txt` 中的 `Tests:` 标题都不算通过。
4. 对 5 配置 × 种子 `11/23/47` 的 15 个 run，各记录 1846、1866、1900 三个检查点；每个 run 必须有 30 条十国记录、真实 campaign 描述、日志、`run_metadata` 和 `checkpoints.json`。再运行上面的汇总器和 `check_release.py`。
5. 根据真实观察记录区分 `script_error`、`state_overlap`、`diplomacy_cycle`、`ai_collapse`、`performance`、`content_unreachable`；不要把一次预加载结果写成长期平衡结论。

门槛一的前置事实（本轮实测）：启动器里五个验收 Playset 尚未创建，当前激活的 `mods` Playset 还带着两个 Steam Mod。开工前先在启动器 UI 里建好 `none`/`sphere`/`charters`/`wave`/`all`（只启用 `The Yongchang World`），再用 `tools/inspect_playsets.py` 复核到 exit 0，之后每轮启动仍要按手册用 `debug.log` 的 `Mounted Data:` 行核对实际挂载，因为直接启动 exe 时 `disabledDLC` 不可靠。

### C. 内容与平衡复核

- 特色事件的静态实现已经有合同测试，也已用可达性审计复核（92 事件 / 74 日志全部有人触发或发放，30 个特色 journal 的双语名称与理由、30 个特色事件的标题/描述/选项文本齐全，十国特色状态在开局各自初始化）。仍需在游戏内确认的是动态行为：三段事件按月依次触发、选项文本双语正确、状态确实改变且高/低反馈可见。另有一个静态发现：`ywc_is_chinese_heritage_country`、四个共享阈值 helper、三个 DLC 门禁 trigger 全项目零引用（DLC 门禁实际走 `ywc_apply_dlc_compatibility` 里的 inline `has_dlc_feature`），已登记进 `data/content/reachability_allowlist.json`；要删要留需要你拍板。
- 20 条路线的成功/失败/放弃清理、共享变量和冷却门禁已有代码契约；法律、利益集团、港口、财政和长期 AI 平衡仍需真实战局校准。
- PHI/Luzon、MHL/West Micronesia 的弱连通组是已声明的自然群岛例外；若要继续重绘，改权威表后必须重新生成 `00_states.txt` 并重跑 topology、全套测试和实机截图。
- 天山六组的地图像素质心从西到东大体对应 KSH/YRK、KUC、TRF/KHT、HMI；本轮已把生成文件中沿用旧分组顺序的误导注释改为与当前 owner TAG 一致。连通性和大体方向已有自动证据，但 KHT/TRF 的精细边界仍应由你在选国地图上目视确认，未把它写成人工验收通过。

### D. 本轮新增的验收工具（均已测试，全部只读或只写自己的证据文件）

| 工具 | 作用 | 硬约束 |
| --- | --- | --- |
| `tools/inspect_playsets.py` | 只读读取启动器 `launcher-v2.sqlite`，核对五个 Playset 的 Mod 启用与门禁 DLC 开关 | 只读 URI 打开，绝不写用户数据目录；未记录的 DLC 记为 `unknown` 而不是假设关闭 |
| `tools/record_checkpoint.py` | 校验并逐年合并检查点，齐全后 `--finalize` 提升 run 状态 | 不生成/估算任何数字；已记录行只有 `--replace` 才覆盖；`--finalize` 要求 `mod_mount=mounted`、`dlc_state_matches_config=yes`、真实 campaign 描述与存在的日志 |
| `tools/observation_status.py` | 只读打印 15 个 run 的记录进度与缺口 | 不改任何状态；`--json` 可输出机器可读报告 |
| `tools/content_reachability.py` | 全 token 引用计数：92 个事件、74 个日志是否都有人触发/发放，悬空引用，以及零引用的 scripted helper（已接线进 `ywc_check.py`） | 已声明但无引用的 helper 必须写进 `data/content/reachability_allowlist.json` 并给理由，否则 exit 1；不会自动删除内容 |
| `tools/modifier_audit.py` | 用本体 `common/modifier_type_definitions/*.txt`（1.13.11 共 2364 个键）校验本仓库 118 个修正键与 58 个静态修正，并检查 `add_modifier`/`remove_modifier` 引用是否有声明（已接线进 `ywc_check.py`，需要 `--game-root`） | 没有 game root 时不猜、直接跳过；DLC 定义文件里的键单独报告，不当作错误 |
| `ywc_check.py` 内嵌的 on_action 钩子检查 | 我们挂接的钩子必须存在于本体 `common/on_actions`；`on_actions = { ... }` 里调用的名字必须已声明 | 拼错的钩子在游戏里静默不执行，所以这条是有 game root 时强制检查的 |
| `tools/scripted_test_audit.py` | 校验两套原生 scripted-test 套件里用到的每个键：必须是 `scripted_tests.md` 记录的格式键、本体脚本中出现过的标识符，或本仓库声明的名字 | 门槛三要花一轮真实战局，而未知触发器不会报解析错误、只会永远无法满足，所以跑之前必查；默认窄语料约 10 秒，`--full` 搜全本体 |
| `tools/startup_data_audit.py` | 校验开局数据：州区域、建筑类型、pops 的文化/宗教/人口类型是否存在、等级是否为正；并用本体 `map_data/state_regions` 的 `arable_resources`/`capped_resources` 查**零容量建筑** | 城市建筑的豁免是从本体建筑历史推导出来的，不是硬编码；`level`（单数，纪念碑写法）与省略 `level` 都合法，只报显式非正值；本仓库自定义建筑不查本体容量 |
| `tools/acceptance_preflight.py` | 一条命令汇总全部门禁：静态三项 + 门槛一启动器 Playset + 门槛二/三的日志 verified 行数 + 门槛四观察矩阵 | 只读；`skipped` 不算通过（缺启动器数据库就不算 ready）；子检查抛异常时降级为 blocked 而不是崩掉 |

本轮已完成的两条后续项：`record_checkpoint.py --emit-template`（已做）与 `inspect_playsets.py` 证据接进 `validate_manual_acceptance.py --playset-evidence`（已做）。

仍然值得做的方向（按性价比排序）：清理 `data/content/reachability_allowlist.json` 里 8 个零引用 trigger（**需要你拍板**：其中 3 个 DLC 门禁 trigger 与 inline `has_dlc_feature` 完全重复，删掉零功能影响；另外 5 个是共享阈值/设定 helper，删不删是内容取舍）；等门槛二/三有真实证据后，用真实战役日志反推平衡结论；`appendix_k_errors.md` 里的报错表还可以继续转化成 `ywc_check.py` 的静态诊断。

## 5. 参考资料（本地 clone，必读）

- **`refs/v3_mod_guide_cn/`**：V3 Mod 开发中文指南（<https://github.com/tangyixiao/v3_mod_guide_cn>），已 clone 到本仓库下并加入 `.gitignore`（不要提交）。它包含两部分：AI 生成的中文教程（`v3_mod_guide_cn/`，chapters + appendices A—L）和打包的官方 wiki Markdown（`v3_wiki_docs/`，含 `Documentation/Modifier_types.md`、`On_actions.md`、`Trigger.md`、`Scope.md` 等）。
- **纪律**：该指南自述为 AI 生成、未经人工审查、示例未经实测，只能当导航与术语参考；任何技术结论必须用本机 1.13.11 本体文件或本仓库可运行的测试核对。已核对的结论、可查章节与更新方式见 `docs/reference/v3-mod-guide-notes.md`。
- 本轮已按它给出的线索落地了一条真实检查：修正类型清单在本体 `common/modifier_type_definitions/*.txt`（2364 个键），据此新增 `tools/modifier_audit.py`；同时用它纠正了「日志本地化键带 `journal_entry_` 前缀」的错误假设（本体约定是键 = 日志 id + `_reason`）。
- 后续做事件/日志/决议/修正内容时可先读 `chapters/part3_content/`，排查报错可读 `appendices/appendix_k_errors.md`。

## 6. 常用命令与禁忌

```powershell
Set-Location 'E:\Victoria3 Mod'
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
python tools/scenario_tag_audit.py --root .
python tools/ownership_topology.py --baseline data/baseline/vic3-1.13.11.json --overrides data/scenario/ownership_overrides.json --provinces-map 'E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png' --weak-only
python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md
python tools/observation_status.py --root artifacts/observe
python tools/content_reachability.py --root yongchang_world
python tools/modifier_audit.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
python tools/inspect_playsets.py --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3'
python tools/acceptance_preflight.py --root . --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3' --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
python tools/record_checkpoint.py --config none --seed 11 --year 1846 --input 1846.csv
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
```

注意：

- PowerShell 5.1 写 BOM-free JSON/descriptor 要使用 `[System.Text.UTF8Encoding]($false)`；不要改回 `utf8NoBOM` 参数。
- `artifacts/smoke/latest-summary.txt` 可能被测试 fixture 覆盖，不能单独作为最新证据；优先使用配置/种子专属的 `artifacts/observe/*/*/run.json` 和日志。
- 不要把 `MNG` 当运行时喀尔喀，也不要把 `SHN` 当掸邦；正确运行时标签分别是 `MGL`、`SHD`。
- 不要修改 Victoria 3 本体、兼容层 DLL 或用户未授权的工作树内容。

## 7. 完成定义

只有以下事项全部完成，才可以把任务标记为发布完成：静态测试和检查保持通过；五种 Playset 实际 DLC 与 Mod 挂载证据齐全；十国 1836 进入和特色内容证据齐全；NMG 谈判两支有真实证据；两个原生 scripted-test 套件均为非空 PASS；15 个观察 run 均为 `observed_to_checkpoint` 并由汇总器生成 `verified`；长期异常分类与平衡结论已记录；最后工作树按用户指示处理且本体/DLL 未被修改。

当前状态：**实现和静态验证完成，真实发行验收进行中，不能宣称发布完成。**
