# The Yongchang World

《永昌世界》是面向 Victoria 3 1.13.11 的架空历史 Mod。当前仓库已经完成十国内容垂直切片：大顺（SHU）、靖海国（JHG）、东明（DMG）、北清（NQG）、卫拉特（OIR）、喀尔喀（场景逻辑名 MNG，本体运行标签 MGL）、吐蕃（TIB）、朝鲜（KOR）、兰芳（LAN）和新明（NMG）。每国都有 1836 内容入口、主/辅助日志、事件、两条路线、AI 策略、双语文本、政治身份、动态国名与地图颜色；六国使用复用本体纹样图集的几何 CoA，MNG/TIB/KOR/LAN 沿用本体旗帜定义，避免重复数据库键。MNG 复用本体 MGL 的国家定义和动态国名列表，避免与本体 Minas Gerais 标签 MNG 冲突。

## 十国特色内容扩展（2026-09-14）

当前开发批次在原有十国主日志、辅助日志和路线之外，加入了十套独立的国家状态与三段式特色事件链：

- 大顺：朝廷平衡；靖海：护航承诺；东明：华菲契约；北清：岛屿补给；
- 卫拉特：旗盟协作；喀尔喀：南北商路平衡；西藏：寺院地产改革；
- 朝鲜：朝廷改革信用；兰芳：矿业特许契约；新明：联邦谈判度。

每套机制使用 0—100 状态、三个按月承接的日志事件和高低档反馈，既有路线会读取这些状态。当前静态合同与提交态隐藏预加载已经通过；十国真实战局交互和长期平衡仍待人工验收。

## 大型内容包：三章十国战役与五场跨国危机（2026-09-25）

按照 [2026-09-25 大型内容包实施计划](docs/superpowers/plans/2026-09-25-大型内容包实施计划.md) 完成了内容开发：在既有地图、路线与共享变量接口之上，新增 150 个国家事件（`ywc_<tag>.100`—`.114`，每国三章、每章五节）和 30 个跨国危机事件（`ywc_crisis.1`—`.30`，五场危机各六阶段），原有 30 个特色事件降级为各章前奏，原有日志 ID 与 `resolved`/`failed` 结果标记保持可读，但改在章末结算时写入。每章末事件读取实际状态（风味状态、章节记录与 `docs/superpowers/specs/2026-09-25-大型内容包十国事件卡.md` 的章末门槛）落进"制度确立 / 脆弱妥协 / 受挫改道"三种互斥结局之一，并启动下一章；第三章只保留有上限的余波修正。五场危机由章末结算按条件启动，持有人 journal 逐阶段推进，每个阶段由设计指定的参与国自行作答，超时或国家缺席记为"无人代表"并收窄协议；结算永远不直接送领土、和平条约或属邦变更。

实现要点：

- `data/content/large_campaign_event_catalog.json` 是 180 个事件的唯一结构化清单（双语文案、选项、成本、章节/阶段标记、章末门槛与危机作答国），由 `tools/build_campaign_content.py` 确定性生成事件脚本与中英文本地化三份文件；`--check` 模式校验三份文件没有漂移。
- `yongchang_world/events/ywc_large_campaign_events.txt`（生成）、`common/scripted_effects/ywc_campaign_effects.txt`（章节结算、危机作答与五条阶段推进）、`common/journal_entries/ywc_large_campaign_crises.txt`（五条危机 journal）、十个国家 journal 文件的三章串接，以及 `common/static_modifiers/ywc_static_modifiers.txt` 的十个限时修正。
- `tools/ywc_campaign_check.py` 校验清单→事件→journal→效果→本地化的整条链：180 个唯一 ID、章节顺序、双语文案、选项数、章末门槛与结局写入、危机阶段可达、修正声明与生成文件新鲜度；`tests/test_campaign_content.py` 17 项覆盖清单不变量、生成器拒绝路径与校验器的变异测试。
- 静态门禁全部通过（358 项单元测试、`ywc_check`、`content_reachability` events=272 journals=79、修正审计、preflight 四项静态检查）。新档三章推进、AI 应答、危机启动与长期平衡仍未有真实战局证据，按 [docs/release/manual-acceptance-playbook.md](docs/release/manual-acceptance-playbook.md) 的门槛二/三/四执行。

## v1.0「受命于天，既寿永昌」先行层：天命霸权（2026-09-26）

三章战役结算后的天下，进入天命霸权阶段。按 [2026-09-26 受命于天实施计划](docs/superpowers/plans/2026-09-26-受命于天实施计划.md)（设计见 [specs/2026-09-26-受命于天-天命霸权设计.md](docs/superpowers/specs/2026-09-26-受命于天-天命霸权设计.md)）：

- **触发**：大顺第三章"制度确立"结算，或危机一"天下名分"全协议签订，且正统性 ≥60、核心参与国存续——满足即颁行朝贡新籍（钩子由生成器写入 `ywc_shu.114` 与 `ywc_crisis.6` 结算选项）。
- **霸权线**（`ywc_hegemony.1`–`.6`）：颁诏（宽仁/威严定权威起点）→ 应答期（九国按季逐一接到各自成文的诏使事件）→ 四方震动 → 酬顺之政 → 问罪逆藩 → 朝会天宪 → 天命所归。
- **参与国线**（每国 `.200`–`.202`，共 27 个）：诏使至国（入贡/观望/拒诏，三国抉择、按各国处境单独撰文）；顺服者收到"顺者之昌"（加贡请封或谨守本分），拒诏者收到"逆者之亡"（硬抗到底或转而入贡）。
- **机制**：`ywc_hegemony_authority` 0–100 权威 + 顺/逆/观三计数；入贡是真实国库转移（按国规模分级）+ 自主压力；拒诏招致限时孤立修正与关系崩坏——**拒诏不产生征服权**，倾覆只经由既有外交博弈与战争系统；权威不足或逆多顺少时新制受挫乃至崩解，霸权承受余波修正。
- `data/content/hegemony_event_catalog.json`（33 事件双语）为唯一实现输入，`tools/build_hegemony_content.py` 生成事件与双语文案；`tools/ywc_hegemony_check.py` 与 `tests/test_hegemony_content.py` 守门（可达性 events=305 / journals=80）。
- 静态门禁全部通过（375 项单元测试、`ywc_check` 对照游戏根目录零诊断、preflight 四项静态 ok）；霸权节奏、AI 顺逆倾向与长期平衡仍无实机证据。

## v0.2「六六大顺」：西南六国（2026-09-26）

v0.2 给西南六国各补一条核心日志与三个双语事件（设计见 [specs/2026-09-26-六六大顺-西南六国设计.md](docs/superpowers/specs/2026-09-26-六六大顺-西南六国设计.md)，计划见 [plans/2026-09-26-六六大顺实施计划.md](docs/superpowers/plans/2026-09-26-六六大顺实施计划.md)）：

- **丽江 LJG《茶马引盐》**：引盐之争 → 藏商入城 → 木氏继嗣——大顺藩属在引权、德格僧商与土司继承之间取舍；
- **西双版纳 SIP《十二版纳》**：茶山之约 → 缅使西来 → 十二版纳分担——车里宣慰在两个朝廷之间求全；
- **德格 DER《印经银钱》**：印经院的债 → 护商之约 → 僧俗之争——康区主邦以印经立国，僧俗商三面相争；
- **嘉绒 GYL《戎马屯田》**：屯田与牧场 → 练军之请 → 盟主之争——大顺缓冲联盟的均势难题；
- **掸邦 SHD《三十七土司》**：土司联席 → 设官之请 → 茶叶与罂粟——土司邦联的贡额、流官与生计；
- **若开 ARA《两属之邦》**：驻扎官的账单 → 缅甸流亡者 → 稻米专约——英国保护下的门面工夫。

机制契约：区域国家保持轻量——效果只有国库、关系（大顺/英国/西藏/德格/缅甸）、事件标记与八个限时修正（茶马新章、互市开城、护商之约、练军之效、摊派之累、烟祸蔓延、稻米专约、流亡之累），不触碰共享三变量，不发核心不送地；六条日志开局即挂（先 `ywc_reset_shared_variables` 后挂日志），三节按序投递，末节写 resolved/failed 收束。`data/content/southwest_event_catalog.json` 唯一清单 → `tools/build_southwest_content.py` 生成 → `tools/ywc_southwest_check.py` 与 `tests/test_southwest_content.py` 守门（可达性 events=323 / journals=86）。
静态门禁全部通过（390 项单元测试、`ywc_check` 对照游戏根目录零诊断、preflight 四项静态 ok）；西南节奏与 AI 行为仍无实机证据。

## 开发验证

```powershell
python -m unittest discover -s tests -v
python tools/ywc_check.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
python tools/scenario_tag_audit.py --root .
python tools/content_reachability.py --root yongchang_world
python tools/modifier_audit.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
python tools/scripted_test_audit.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
python tools/startup_data_audit.py --mod-root yongchang_world --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md
```

进入战局执行原生 `scripted_tests` 之前，建议先跑 `tools/scripted_test_audit.py`：套件里的未知触发器名不会被当成解析错误，只会让用例永远无法满足，白花一轮真实战局。

全部发行门禁的当前状态可以用一条只读命令查看（静态检查、五个 Playset、十国、两套 scripted test、15 个观察 run）：

```powershell
python tools/acceptance_preflight.py --root . --user-data-dir "D:\Documents\Paradox Interactive\Victoria 3" --game-root "E:\SteamLibrary\steamapps\common\Victoria 3\game"
```

`incomplete` / `blocked` / `not-run` 都表示证据还不齐，只有全部 `ok` 才会返回 0。

本地参考资料：`refs/v3_mod_guide_cn/`（V3 Mod 开发中文指南，已 gitignore，仅作导航与术语参考，技术结论一律以本体文件为准；小结见 [docs/reference/v3-mod-guide-notes.md](docs/reference/v3-mod-guide-notes.md)）。

将开发描述文件安装到本地启动器 Mod 目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_dev_mod.ps1
```

之后用 `victoria3.exe -debug_mode` 启动，在启动器启用 `The Yongchang World`，检查十国是否出现在选国界面并能进入 1836。自动化验收使用隐藏窗口启动并读取日志，不切换桌面、不截图、不点击 UI；退出游戏后采集日志：

```powershell
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch
```

日志摘要写入 `artifacts/smoke/latest-summary.txt`，十国内容汇总写入 `artifacts/smoke/core-country-summary.json`；原版游戏目录保持只读，仓库只保存摘要而不保存大型日志或存档。

`latest-summary.txt` 可能被回归 fixture 覆盖，不能单独作为最新启动或发行证据；正式证据以 `artifacts/observe/<config>/<run>/run.json` 及同目录日志为准。

进入已有战局后，可用本体的 `scripted_tests` 命令分别执行 `yongchang_world/tools/scripted_tests/ywc_startup_smoke.txt`（1836 开局硬约束）和 `yongchang_world/tools/scripted_tests/ywc_longrun_invariants.txt`（长期数据健康）。两套测试均为只读；长期套件不要求十国继续存在，也不要求 NMG 永远保持墨西哥属邦。

原生烟测结束后，应对同一个隔离用户目录运行 `powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot <userdir> -RequireScriptedTests`。摘要中的 `scripted_tests=pass` 才是可接受的套件通过证据；`present` 只表示发现无法识别的非空文本，`missing`、`empty`、`fail` 都不能算通过。隐藏预加载（例如 `artifacts/observe/none/123`）只能证明 Mod 挂载、版本匹配和日志加载，不等于进入战局或执行 scripted tests。

剩余的人工验收门槛（五配置启动、逐国进入 1836、烟测执行、观察矩阵回填）的逐步操作见 [docs/release/manual-acceptance-playbook.md](docs/release/manual-acceptance-playbook.md)。

回填观察矩阵时可用三个只读/校验工具降低手工出错概率（均不写入用户数据目录，也不自动生成任何观察数值）：

```powershell
python tools/inspect_playsets.py --user-data-dir "D:\Documents\Paradox Interactive\Victoria 3"
python tools/record_checkpoint.py --config none --seed 11 --year 1846 --input 1846.csv
python tools/observation_status.py --root artifacts/observe
```

`inspect_playsets.py` 核对启动器五个 Playset 的 Mod 与门禁 DLC 开关（全部一致才 exit 0）；`record_checkpoint.py` 逐年校验并合并检查点，齐全后 `--finalize` 才允许把 run 提升为 `observed_to_checkpoint`；`observation_status.py` 只读显示 15 个 run 还缺哪些记录。

## 当前边界

此前批次和本次特色事件扩展已完成静态复核；HEAD `3cba19e` 的提交态隐藏预加载也已通过。当前未提交工作树尚无对应的隐藏或实机运行证据，完整 UI 逐国选国与 1836—1900 长期观察局仍未完成，因此不能宣称 AI 长期平衡或 v0.1 已通过发行验收。游戏脚本以本体 1.13.11（Build ID 24799966）为基线，Province ID 来自本体快照。
