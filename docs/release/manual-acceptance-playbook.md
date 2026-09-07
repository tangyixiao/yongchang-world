# 《永昌世界》v0.1 人工验收手册

> 目标读者：可以在本机操作桌面与游戏 UI 的验收人。自动化轮次已完成全部静态与隐藏启动验证（测试数量以本次 `python -m unittest discover -s tests -v` 输出为准，引用完整、双语对齐、解析零错误）；本手册覆盖仅剩的人工门槛：真实进入战局的启动、选国、烟测执行与观察矩阵证据回填。

## 0. 准备

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
6. 每轮把摘要与挂载行复制到 `artifacts/observe/<config>/launcher-evidence.txt`（自建目录，命名自由但需含配置名）。

预期：五个配置都应 `mod_mount=mounted`；若某配置的实际 DLC 集合与 Playset 意图不符，**如实记录**差异（例如归档所有权后端波动），不要标注为通过。

## 2. 门槛二：逐国选国并进入 1836

对十个国家（SHU、JHG、DMG、NQG、OIR、MNG、TIB、KOR、LAN、NMG）各执行一轮：

1. 选国 → 进入 1836 → 暂停。
2. 打开日志面板，核对该国开局持有的 journal（名称应与下表一致，全部为已接线状态）：

   | 国家 | 主日志 | 辅助/路线（节选） |
   | --- | --- | --- |
   | SHU | 永昌世纪、永恒永昌 | 士商、黑水边疆、鸦片之问；士绅官僚整合、海关商政改革 |
   | JHG | 靖海自治（bootstrap） | 海上网络、继承之诏、行商议事会；藩屏水师、南洋商会 |
   | DMG | 东明存续（bootstrap） | 南明法统、西班牙边患、本地契约；华菲王权、地方共和 |
   | NQG | 黑水世纪（bootstrap） | 流亡、亲俄之择、岛屿社会；库页光复、多族之邦 |
   | OIR | 准噶尔遗业 | 俄国之压、伊犁商路、虚位之鞍；文法之汗国、牧地之盟 |
   | MNG | 大漠南北 | 茶马之市、庇护者之影、泛蒙之会；南向商路、帝俄之翼 |
   | TIB | 无主高地 | 寺院庄园、康区之问、商队之门；庄园之革、康区同盟 |
   | KOR | 谁承中华（朝鲜） | 三司之革、鸭绿之问、南海之书；小中华之志、建国之基 |
   | LAN | 兰芳公司共和 | 股东之议、矿工边疆、荷兰最后通牒；矿工之共和、矿业立国 |
   | NMG | 新明—墨西哥链条 | 下加州边疆、花茂教群、一国两都；自治教会、半岛联邦派 |

3. 推进到首个整月（1836-02-01 前后）：每个未决 journal 会弹出对应的决策事件（双语）。任选一个选项，确认 journal 面板中该日志变为"已完成"（成功/放弃路径）或"已失败"。
4. NMG 附加检查：确认开局与墨西哥的附属关系（外交面板）；选中 NMG 后对墨西哥使用外交动作"自治谈判"（`ywc_nmg_autonomy_negotiation`），接受后确认 `新明—墨西哥链条` 主日志完成。
5. DLC 增强检查（`all` 配置下重复任一国家）：确认三个门禁能力（势力范围/投资、公司特许、水师旗舰）随 DLC 开关出现或消失，无"无 DLC 报错"。
6. 记录：每国的检查结果（journal 清单核对、事件弹出、完成/失败状态、NMG 外交动作）写入 `docs/release/manual-acceptance-log.md`（自建）。

## 3. 门槛三：在真实战局中执行原生 scripted_tests 套件

1. 在任意已进入的战局中打开调试控制台（`-debug_mode` 下按 `` ` ``）。
2. 在 1836 新局推进到首月后执行 `scripted_tests`，记录 `ywc_startup_smoke.txt` 的结果：十国存在、JHG/NMG 开局属邦边界、SHU 的 DLC 基础路径，以及十国主日志和两条路线入口。
3. 在观察局的检查年执行 `scripted_tests`，选择 `ywc_longrun_invariants.txt`：它只检查无负人口、无存活国家孤立首都、共享变量范围和 DLC 兼容日志，不要求十国继续存在，也不要求 NMG 永远保持属邦。
4. `scripted_tests after` 可作为失败后自动存档的变体（具体表现以实机为准）。把控制台输出截图或抄录，连同使用的套件、种子、日期和存档路径记入验收日志；静态扫描和隐藏预载不能替代这一步。
5. 退出该轮游戏后，针对同一个用户目录运行：

   ```powershell
   powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot <userdir> -RequireScriptedTests
   ```

   只有摘要中的 `scripted_tests=present` 才能作为结果文件存在的证据；`scripted_tests=missing` 或 `scripted_tests=empty`（文件只有 `Tests:` 标题）都必须保持为未通过。一次直接隔离启动到 1836.2.2 的实测曾生成空结果，因此不能仅凭 `-scripted_tests` 参数或到达目标日期宣称套件已执行。

## 4. 门槛四：观察矩阵与检查点回填

对十五个组合（配置 × 种子 11/23/47），在 1846、1866、1900 三个检查年各采集一次十国数据：

1. 数据来源（任选其一，均需真实）：
   - 战局内读取：国家面板（rank、人口）、市场面板（market）、外交面板（wars、subjects）、错误计数（本轮 error.log 行数）；
   - 存档导出：`save games` 内联文本中检索对应字段。
2. 按 `tools/summarize_observation.py` 的模式写入 `artifacts/observe/<config>/run-<seed>/checkpoints.json`：

   ```json
   [
     {"year": 1846, "country": "SHU", "rank": "great_power", "population": 0,
      "market": "SHU", "wars": 0, "subjects": 0, "error_count": 0}
   ]
   ```

   每个 run 必须有 3 年 × 10 国、共 30 条唯一 `(year, country)` 记录；年份必须覆盖 1846/1866/1900、country 仅限十国、population/wars/subjects 非负、error_count 为 0（有脚本错误则如实填写并先修复）。
3. 在同一目录放置 `run.json`，至少包含 `config`、`run_id`（如 `run-11`）、`requested_seed`、`observed_seed`（无法从证据读回时为 `null`）、`status: "observed_to_checkpoint"`、`game_version: "1.13.11 (Matcha)"`、`mod_mount: "mounted"`、非空 `version_match_evidence`、与配置相符的 `expected_mounted_dlc`/`observed_mounted_dlc`、`dlc_state_matches_config: "yes"` 和非空 `evidence` 对象。预加载状态不能写成观察状态。
4. 运行 `python tools/summarize_observation.py --input artifacts/observe --output artifacts/observe/matrix-summary.json` 汇总（校验失败会返回 1 并说明原因；只有汇总器会把合格 run 变成 `status: "verified"`）。
5. `python tools/check_release.py --matrix artifacts/observe/matrix-summary.json --mod-root yongchang_world`：15 条 run 全部 `verified` 且证据字段一致前它会继续失败——**这是门禁本意，不要改写矩阵状态绕过**。
6. 异常分类沿用计划 04：`script_error`、`state_overlap`、`diplomacy_cycle`、`ai_collapse`、`performance`、`content_unreachable`；同一异常在三个种子重复出现才进入平衡修订。

## 5. 证据规则与已知限制速查

- 未经真实战局验证的事项保持 `pending`；不要把预填数据、20 秒预加载日志或静态 JSON 称为长期结果。
- `artifacts/smoke/latest-summary.txt` 是生成文件且被单元测试覆盖，不能单独作为 clean 证据；以配置/种子专属的 `artifacts/observe/*/run.json` 与 `logs` 为准。
- `-userdir` 隔离目录中的 JSON 必须无 BOM（游戏会静默拒绝带 BOM 的 `content_load.json`）；observation runner 已内置该修复，不要改回 `Set-Content -Encoding UTF8`。
- 本仓库不修改本体目录与三枚兼容层 DLL；DLL 指纹基线：长度 `5452240`，2026/7/3 20:40:00。
- 事件后果（法律、利益集团权重、港口与财政的实质变化）目前仅记录为变量；平衡轮应在不违反计划 03 约束的前提下添加，并以本手册的观察局数据驱动。
