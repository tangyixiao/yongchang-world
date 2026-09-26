# 《永昌世界》v0.1 人工验收手册

> 目标读者：可以在本机操作桌面与游戏 UI 的验收人。2026-09-19 当前工作树的静态自动验证已通过；最近的干净隐藏预加载 `artifacts/observe/none/919` 只覆盖提交态 HEAD `3cba19e`，不覆盖后续未提交改动。本手册覆盖真实进入战局的启动、选国、烟测执行与观察矩阵证据回填，并要求验收前为当前工作树重新生成隔离运行证据。

## 0. 准备

0. 开工前先跑一次总自检，它会列出每个门禁当前的状态（静态三项、五个 Playset、十国、两套 scripted test、15 个 run）：

   ```powershell
   python tools/acceptance_preflight.py --root . --user-data-dir "<用户数据目录>" --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
   ```

   输出里 `ok` 才是通过，`incomplete`/`blocked`/`not-run` 都表示还差证据；全部为 `ok` 时命令返回 0。每完成一个门槛后再跑一次，就能看到剩余项。

1. 安装开发描述文件（已验证可在 Windows PowerShell 5.1 运行）：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_dev_mod.ps1
   ```

2. 用启动器（Steam → Victoria 3）启动游戏并确认 Playset 中已启用 `The Yongchang World`。**不要**用直接双击 `victoria3.exe` 的方式做需要 DLC 配置的验收（见下文平台限制）。
3. 调试验收统一加 `-debug_mode`（启动器 → 游戏设置 → 启动选项，或快捷方式参数）。

## 1. 门槛一：五配置启动证据

**平台事实**（已由探针证实）：直接启动 exe 时，`content_load.json` 里的 `disabledDLC` 会被无视，且 DLC 所有权后端在不同启动间在"全拥有"与"不可用"之间波动。因此逐配置 DLC 开关只能依赖**官方启动器 UI 的 Playset DLC 开关**，并且每次启动后都要用挂载行核实实际生效的 DLC 集合，不要假设配置已生效。

操作步骤（每个配置一轮）：

1. 在启动器中创建五个 Playset：`none`、`sphere`、`charters`、`wave`、`all`，均启用 `The Yongchang World`。
2. 按 Playset 开关三个内容 DLC：
   - `none`：全部关闭；`sphere`：仅 Sphere of Influence；`charters`：仅 Charters of Commerce；`wave`：仅 The Great Wave；`all`：三个全开。
3. 从启动器启动，进入主菜单即可（本门槛不需要进战局）。
4. 采集证据：关闭游戏后运行 `powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch`，`latest-summary.txt` 会给出 `status`、`finding_count`、`mod_mount=mounted` 与挂载原文行。
5. 在 `debug.log` 中核对三条门禁 DLC 的 `Mounted Data:` 行：出现的即"该轮实际启用的 DLC"，与 Playset 意图比对（这是 runner 的 `dlc_state_matches_config` 逻辑的人工版）。
6. 每轮把 `run.json`、`debug.log` 挂载行和 smoke 摘要归档到对应的 `artifacts/observe/<config>/<run>/`；这些运行日志与下一步生成的结构化 Playset JSON 一起构成证据。
7. 结构核对（只读，不写用户数据目录）：

   ```powershell
   python tools/inspect_playsets.py --user-data-dir "<用户数据目录>" --output artifacts/observe/launcher-evidence.json
   ```

   该工具以只读 URI 打开启动器的 `launcher-v2.sqlite`，核对五个 Playset 是否存在、`The Yongchang World` 是否启用、三个门禁 DLC 的开关是否与配置一致，并标出会污染战局的其他已启用 Mod。全部一致时 exit 0；否则 exit 1 并逐条列出原因。启动器从未写入过的 DLC 行记为 `unknown`（不会假设为关闭），需要在 UI 里拨动一次再复查。

   填完门槛一表格后，可以让校验器直接用这份 JSON 复核表格（只在 `--require-complete` 下生效，且要求该行引用同一份 JSON 文件）：

   ```powershell
   python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md --require-complete --playset-evidence artifacts/observe/launcher-evidence.json
   ```

   若某个配置在启动器里没有被确认（Playset 不存在、Mod 未启用、DLC 集合不符、混入其他 Mod），即使表格填了 `verified` 也会被拒绝。

预期：五个配置都应 `mod_mount=mounted`，且 `inspect_playsets.py` 对五个配置均报告 `match=yes`；若某配置的实际 DLC 集合与 Playset 意图不符，**如实记录**差异（例如归档所有权后端波动），不要标注为通过。

## 2. 门槛二：逐国选国并进入 1836

0. **进战局之前先跑一次开局数据审计**（pops 与建筑历史只在开局读取，一个坏键要花真实开局才能发现）：

   ```powershell
   python tools/startup_data_audit.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
   ```

   它校验州区域、建筑类型、pops 的文化/宗教/人口类型是否存在、等级是否为正，并用本体 `map_data/state_regions` 的 `arable_resources`/`capped_resources` 查**零容量建筑**——当年 KUC 伐木营、外满洲麦田、西澳渔港就是这类错误，只在真实开局才暴露。当前仓库 1588 个开局建筑、2180 个 pop 字段全部通过。

对十个国家（SHU、JHG、DMG、NQG、OIR、MGL、TIB、KOR、LAN、NMG）各执行一轮；其中 `MGL` 是界面、外交和观察记录使用的喀尔喀运行时标签，对应内容目录中的逻辑名 `MNG`：

1. 选国 → 进入 1836 → 暂停。
2. 打开日志面板，核对该国开局持有的 journal（名称应与下表一致，全部为已接线状态）：

   | 国家 | 主日志 | 辅助/路线（节选） |
   | --- | --- | --- |
   | SHU | 永昌世纪、永恒永昌 | 士商、黑水边疆、鸦片之问；士绅官僚整合、海关商政改革 |
   | JHG | 靖海自治（bootstrap） | 海上网络、继承之诏、行商议事会；藩屏水师、南洋商会 |
   | DMG | 东明存续（bootstrap） | 南明法统、西班牙边患、本地契约；华菲王权、地方共和 |
   | NQG | 黑水世纪（bootstrap） | 流亡、亲俄之择、岛屿社会；库页光复、多族之邦 |
   | OIR | 准噶尔遗业 | 俄国之压、伊犁商路、虚位之鞍；文法之汗国、牧地之盟 |
   | MGL | 大漠南北 | 茶马之市、庇护者之影、泛蒙之会；南向商路、帝俄之翼 |
   | TIB | 无主高地 | 寺院庄园、康区之问、商队之门；庄园之革、康区同盟 |
   | KOR | 谁承中华（朝鲜） | 三司之革、鸭绿之问、南海之书；小中华之志、建国之基 |
   | LAN | 兰芳公司共和 | 股东之议、矿工边疆、荷兰最后通牒；矿工之共和、矿业立国 |
   | NMG | 新明—墨西哥链条 | 下加州边疆、花茂教群、一国两都；自治教会、半岛联邦派 |

3. 推进到首个整月（1836-02-01 前后）：每个未决 journal 会弹出对应的决策事件（双语）。路线的第一个选项只会启动并推进路线，不会直接完成；继续按月选择路线选项，直到进度达到 100 后选择成功，或在进度达到 60 后选择失败，或随时选择放弃。放弃后确认恢复负担修正出现；路线在 365 天冷却期内不再弹出，冷却结束后可重新开始。成功和失败则分别显示对应结果状态。
4. NMG 附加检查：确认开局与墨西哥的附属关系（外交面板）；选中 NMG 后对墨西哥使用外交动作"自治谈判"（`ywc_nmg_autonomy_negotiation`），分别记录墨西哥接受与拒绝：接受后确认 `新明—墨西哥链条` 主日志完成，并观察自治压力/属邦自由欲望沿共享减压路径下降；拒绝后确认关系下降、自治压力上升、主日志仍未完成，且动作在 365 天内不可再次发起，冷却结束后恢复可发起。
5. DLC 增强检查（`all` 配置下重复任一国家）：确认三个门禁能力（势力范围/投资、公司特许、水师旗舰）随 DLC 开关出现或消失，无"无 DLC 报错"。
6. 记录：每国的检查结果（journal 清单核对、事件弹出、完成/失败状态、NMG 外交动作）写入 `docs/release/manual-acceptance-log.md`（自建）。

## 3. 门槛三：在真实战局中执行原生 scripted_tests 套件

0. **进战局之前先跑一次静态词汇校验**，避免因为一个拼错的触发器名字白跑一轮（套件里未知名字不会被报成解析错误，只会永远无法满足）：

   ```powershell
   python tools/scripted_test_audit.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
   ```

   默认使用窄语料（本体 scripted_triggers / scripted_effects / on_actions / journal_entries / decisions / events 与本体自带套件，约 10 秒）；若报告未知键，先加 `--full` 搜整个本体脚本树再确认是不是真错。

   引擎自带 `game/tools/scripted_tests/scripted_tests.md` 是格式权威来源，几个对验收有用的事实：
   - `success` 先判定；同一天 `success` 与 `fail` 都成立时按通过计；
   - 到达 `last_date` 时若 `success`/`fail` 都没成立，该用例记为 **skipped**（不是 pass，也不能记为 pass）；
   - `run_count` 可控制每个用例跑几次（默认 1，小于 0 为无限；最终结果按所有次运行结果判定）；
   - 控制台参数：`scripted_tests`、`scripted_tests before`、`scripted_tests none`；命令行还有 `no_save_after_failed_test`、`save_before_failed_test`；
   - 结果除了用户目录下的 `tests.txt`，还会在游戏 `binaries` 目录写一份 XML。

1. 在任意已进入的战局中打开调试控制台（`-debug_mode` 下按 `` ` ``）。
2. 在 1836 新局推进到首月后执行 `scripted_tests`，记录 `ywc_startup_smoke.txt` 的结果：十国存在、JHG/NMG 开局属邦边界、SHU 的 DLC 基础路径，以及十国主日志和两条路线入口。
3. 在观察局的检查年执行 `scripted_tests`，选择 `ywc_longrun_invariants.txt`：它只检查无负人口、无存活国家孤立首都、共享变量范围和 DLC 兼容日志，不要求十国继续存在，也不要求 NMG 永远保持属邦。
4. `scripted_tests after` 可作为失败后自动存档的变体（具体表现以实机为准）。把控制台输出截图或抄录，连同使用的套件、种子、日期和存档路径记入验收日志；静态扫描和隐藏预载不能替代这一步。
5. 退出该轮游戏后，针对同一个用户目录运行：

   ```powershell
   powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot <userdir> -RequireScriptedTests
   ```

   摘要现在区分 `missing`、`empty`、`present`、`pass` 和 `fail`：只有 `scripted_tests=pass` 才能作为套件通过证据；`present` 只表示有无法识别的非空文本，`missing`、`empty` 和 `fail` 都必须保持为未通过。一次直接隔离启动到 1836.2.2 的实测曾生成空结果，因此不能仅凭 `-scripted_tests` 参数或到达目标日期宣称套件已执行。若要把摘要保存在本轮证据目录而不是覆盖默认文件，可附加 `-SummaryPath <summary.txt>`；单元测试使用临时摘要路径，不会污染交接用的最新摘要。

## 4. 门槛四：观察矩阵与检查点回填

对十五个组合（配置 × 种子 11/23/47），在 1846、1866、1900 三个检查年各采集一次十国数据：

1. 数据来源（任选其一，均需真实）：
   - 战局内读取：国家面板（rank、人口）、市场面板（market）、外交面板（wars、subjects）、错误计数（本轮 error.log 行数）；
   - 存档导出：`save games` 内联文本中检索对应字段。
2. 按 `tools/summarize_observation.py` 的模式写入 `artifacts/observe/<config>/<seed>/checkpoints.json`（与 `run_observation_matrix.ps1` 和 `record_checkpoint.py` 使用的目录一致）：

   ```json
   [
     {"year": 1846, "country": "SHU", "rank": "great_power", "population": 0,
      "market": "SHU", "wars": 0, "subjects": 0, "error_count": 0}
   ]
   ```

   每个 run 必须有 3 年 × 10 国、共 30 条唯一 `(year, country)` 记录；年份必须覆盖 1846/1866/1900、country 仅限十国、population/wars/subjects 非负、error_count 为 0（有脚本错误则如实填写并先修复）。
3. 检查点可以逐年写入，不必一次凑齐 30 条：

   ```powershell
   python tools/record_checkpoint.py --config none --seed 11 --year 1846 --emit-template 1846.csv
   python tools/record_checkpoint.py --config none --seed 11 --year 1846 --input 1846.csv
   python tools/observation_status.py --root artifacts/observe
   ```

   `--emit-template` 会写出只有 `year,country` 已填的 CSV 骨架（实测列留空），照着手填即可；留空的行会被校验拒绝，不会当成占位数据收进去。

   `record_checkpoint.py` 接受 CSV（`year,country,rank,population,market,wars,subjects,error_count`，`year` 列可省略）或同样字段的 JSON 列表。它会校验年份匹配、十国齐全、数值非负、无重复 `(year,country)`、`error_count` 为 0，然后把该年合并进 `checkpoints.json`；已记录的 `(year,country)` 只有加 `--replace` 才会被覆盖，避免真证据被后来的导出冲掉。它不会估算或补写任何数字，所有数值都来自操作者提供的文件。

   三年齐全后，用同一工具提升 run 状态（需要真实战役描述、存在的日志路径，且 `run.json` 里已有 `mod_mount=mounted` 与 `dlc_state_matches_config=yes`）：

   ```powershell
   python tools/record_checkpoint.py --config none --seed 11 --finalize --campaign "..." --logs <debug.log> [--observed-seed 11] [--screenshot <png>]
   ```

   `observation_status.py` 只读地打印 15 个 run 的进度（状态、记录条数、缺哪些 `(year,country)`、DLC 证据是否齐），可加 `--json` 输出机器可读报告；它不改变任何状态。
4. 在同一目录放置 `run.json`，至少包含 `config`、`run_id`（如 `run-11`）、`requested_seed`、`observed_seed`（无法从证据读回时为 `null`）、`status: "observed_to_checkpoint"`、`game_version: "1.13.11 (Matcha)"`、`mod_mount: "mounted"`、非空 `version_match_evidence`、与配置相符的 `expected_mounted_dlc`/`observed_mounted_dlc`、`dlc_state_matches_config: "yes"` 和非空 `evidence` 对象。`evidence` 必须包含非空 `campaign` 描述，以及 `logs`、`checkpoint_file`、`run_metadata` 三个真实存在的文件路径；`source` 必须与 `checkpoint_file` 相同，检查点 JSON 必须正好覆盖三年×十国的 30 条唯一记录，population/wars/subjects 为非负整数且 error_count 为 0；发布门禁还会核对 `run_metadata` 的配置、run ID、种子和 `observed_to_checkpoint` 状态是否与矩阵一致。预加载状态不能写成观察状态。
5. 运行 `python tools/summarize_observation.py --input artifacts/observe --output artifacts/observe/matrix-summary.json` 汇总（校验失败会返回 1 并说明原因；只有汇总器会把合格 run 变成 `status: "verified"`）。
6. `python tools/check_release.py --matrix artifacts/observe/matrix-summary.json --mod-root yongchang_world`：15 条 run 全部 `verified` 且证据字段一致前它会继续失败——**这是门禁本意，不要改写矩阵状态绕过**。
7. 异常分类沿用计划 04：`script_error`、`state_overlap`、`diplomacy_cycle`、`ai_collapse`、`performance`、`content_unreachable`；同一异常在三个种子重复出现才进入平衡修订。

## 5. 证据规则与已知限制速查

- 未经真实战局验证的事项保持 `pending`；不要把预填数据、20 秒预加载日志或静态 JSON 称为长期结果。
- 验收记录填写后先运行 `python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md` 检查基本信息表、四张表的完整列 schema、行数与状态；只有所有真实证据均已填写，才运行同命令附加 `--require-complete`。该工具不会把 `pending` 自动视为通过，也不会接受错误游戏基线、非目录用户数据路径、基本信息或事实列仍为 `pending` 的 `verified` 行；`run 目录` 必须是目录，其余证据路径必须是文件。
- `artifacts/smoke/latest-summary.txt` 是生成文件，不能单独作为 clean 证据；以配置/种子专属的 `artifacts/observe/*/run.json` 与 `logs` 为准。单元测试通过 `-SummaryPath` 使用临时摘要文件，不会覆盖该生成文件。
- `-userdir` 隔离目录中的 JSON 必须无 BOM（游戏会静默拒绝带 BOM 的 `content_load.json`）；observation runner 已内置该修复，不要改回 `Set-Content -Encoding UTF8`。
- 本仓库不修改本体目录与三枚兼容层 DLL；DLL 指纹基线：长度 `5452240`，2026/7/3 20:40:00。
- 路线结果和共享状态已经接入国家修正：正统性、自治压力、海贸网络以及路线成功/失败/放弃修正都会产生代码侧效果；法律、利益集团权重、港口与财政的长期平衡仍需真实观察局数据驱动，不能用静态测试代替。
