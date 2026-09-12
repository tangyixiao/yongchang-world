# 《永昌世界》交接给 GLM

> 这是一份以当前工作区为准的交接快照。旧版交接内容中若与本文件、当前 Git 状态或新生成证据冲突，以当前工作区为准。

更新时间：2026-09-12（GLM/ZCode 实机会话轮）
仓库：`E:\Victoria3 Mod`
分支：`codex/yongchang-world-bootstrap`
HEAD：`080aefa docs: record the mosaic fix and ownership regroup`（其后为 4cf632a 地理重排与本文件）（工作树 clean；`docs/交接给GLM.md` 即本文件）
游戏基线：Victoria 3 `1.13.11 (Matcha)`，Build ID `24799966`
游戏目录：`E:\SteamLibrary\steamapps\common\Victoria 3`

## 1. 先看结论

本轮（2026-09-11/12 实机会话）完成了历史性突破：**首次真实进入 Mod 战局并打通了原生 scripted_tests 的执行管线**，同时发现并修复了四个真实 Mod 运行时缺陷。静态与管线状态：

- `python -m unittest discover -s tests`：`190` 个测试通过。
- `python tools/ywc_check.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3'`：exit 0。
- 已提交：AI 策略修复 `colonization_rights` → `colonial_interest_ratio`（提交 `3d20820`，已对照原版 1.13.11 文件验证字段存在）。
- 未提交（本轮新增，全部经过 190 测试 + ywc_check 验证）：→ **已全部提交于 `b7254b7`**，清单如下：
  - `yongchang_world/common/scripted_effects/ywc_shared_effects.txt`：三处 refresh 效果的 `remove_modifier` 加 `has_modifier` 守卫（修复实机 error.log 中 338 次脚本错误洪水）。
  - `yongchang_world/events/ywc_shu_jhg_events.txt`：ywc_shu.4.b、ywc_shu.5.b、ywc_jhg 两条路线共 4 处"继续/成功"选项的 trigger 误含 `progress >= 100`（导致路线卡死在 20、AI 每月只能选放弃、事件无有效选项刷 113 次错误），已按其他国家路线模板修正。
  - `yongchang_world/tools/scripted_tests/ywc_startup_smoke.txt`、`ywc_longrun_invariants.txt`：改为原版加载器格式（无 BOM、日期带引号、4 空格缩进），并新增 `ywc_probe.txt` 最小探针套件。
  - `tests/test_metadata.py`、`tests/test_scripted_release_suite.py`：契约随引擎真实格式更新（scripted_tests 目录豁免 BOM 规则、断言引号日期）。这不是删契约，而是修正与引擎相反的旧契约。
  - `tools/ywc_test_gui/`：**临时测试工具 Mod**（覆盖 `gui/console.gui`，在调试工具栏 Debug|Misc 列加一个 "YWC Tests" 按钮）。仅用于实机验收，不随发行版发布；不想要可直接删除该目录。
  - `artifacts/observe/manual-gate23-1836-shu-01/`：本轮实机会话的隔离 userdir 与全部运行证据（logs、tests.txt、console_history、截图脚本等）。

仍不能宣称完成（见 §6）：十国逐国 UI 验收、scripted tests 拿到非空 PASS 结果、观察矩阵、`check_release.py` 门禁。

### 1.1 后续轮：选国界面拼花已修复（ownership 权威表地理重排）

- 用户选国界面截图确认：东北（蜀汉礼制国）、西域、川滇的**马赛克碎片**根因是场景账本按 owner 随机采样省份（25/693 个 owner 组在真实地图邻接图上不连通，如天山六绿洲链标签各持 40 个散布全省的省份）。
- **修复**：`data/scenario/ownership_overrides.json` 已按真实地图邻接图（从本体 `provinces.png` 构建，40875 省）地理重排——每个 owner 保留其最大连通分量、剩余省份按邻接吸收、每 owner 省份数精确守恒；`tools/build_state_history.py` 已从重排后的权威表重新生成 `00_states.txt`。弱组（<50% 连通）从 25 降到 4，剩余 4 个为海岛/飞地/绿洲链拓扑（本体自身有 54 组同类）。
- **需实机复核**：新开 1836 后确认①东北/西域/川滇边界连贯无碎片；②NQG 等国事件按钮显示双语选项文本；③journal 完成流转。
- **✅ 实机复核通过（2026-09-12 用户截图 ×3）**：重排后新开 1836 选国界面三个视角（欧亚大陆、北美、海洋东南亚）确认——①东北碎片消除：大清、大顺礼制国、大蒙古国、虾夷地各持连贯板块；②西域承统国/吐蕃承统国/和硕特青海及中亚诸玉兹连贯；③下加州的新墨西哥承统国（NMG）为单一干净沿海块；④西婆罗洲兰芳（LAN）连贯，文莱/班贾尔/望加锡等岛国标签清晰。选国面板的国名、文化（阿伊努/大和、墨西哥/汉、汉/客家/达雅）、政体与自定义 flavor 文本渲染正确。**地图视觉验收通过**；事件按钮双语文本仍待事件弹窗截图确认。

## 2. 实机会话已确认的事实（本轮新证据）

以下全部来自真实游戏窗口操作与隔离 userdir 日志，不是推测：

1. **Mod 挂载与运行**：直启 exe（无 Steam）+ `-debug_mode -userdir <隔离目录>` + 无 BOM `content_load.json` 时，主菜单显示 `MP Checksum: xxx (Modified)`；选国界面可见 Shun Ritual State、Great Qing、Great Mongolian State、Tibetan Successor State 等十国布局与专属描述文本（"The Yongchang Era is an age of industry and expedition..."）。
2. **选国并进入 1836 战局**：SHU（多次）、Kengtung/Shan States、Touggourt、Uruguay 均可进入；SHU 面板显示 Fragile Unity 独有日志；战局内 outliner 可见 SHU 全套 journal（The Yongchang Century、The Opium Question、The Blackwater Marches、A Customs Board、Yongchang Unfinished Work 等），Mod 事件弹出（`Event ID: ywc_shu.3`）且带双语/DEBUG 选项。
3. **-debug_mode 生效**：地图悬停显示省份调试信息；右下角 error 计数弹窗出现。
4. **控制台可以打开**：` 键（PostMessage WM_KEYDOWN VK_OEM_3 可触发）；控制台与调试工具栏是同一窗口（gui/console.gui 的 console_window + toolbars_window）。战局内注入键盘（SendInput/WM_CHAR 文本）大多不进 editbox，但 **GUI 按钮点击可靠**。
5. **scripted_tests 机制（读 `game/tools/scripted_tests/scripted_tests.md` + 实测）**：
   - 启用方式两种：启动参数 `-scripted_tests`（boot 时武装）或控制台命令 `scripted_tests`（可再加 `before`/`none`/`after`；再执行一次=禁用）。
   - 套件 = `tools/scripted_tests/` 下每个 .txt；`last_date` 到达即套件结束并**把结果写入 userdir 的 `tests.txt`**；到 last_date 都没 success/fail 的测试记为 skipped。
   - **实测确认**：无参数时退出游戏也会写 header-only 的 `tests.txt`；带 `-scripted_tests` 参数 + 测试启用 + 真实战局跑到 last_date 时，`tests.txt` 会在套件结束日被**就地重写**（mtime 多次验证）。
   - **已定位的边界（本轮终点）**：套件元数据（last_date）被引擎读取并驱动周期，但 `tests` 块始终零记录。已排除：BOM、无引号日期、TAB 缩进、观察者模式、参数缺失、未武装（双击切换）、套件内容复杂度——包括新增的 `ywc_probe.txt`（单个 `always = yes` 成功测试、独立 last_date）也在其结束日零记录。结论：该 1.13.11 直启构建在无更多内部条件下不评估套件内的测试（可能需要 PDX CI 使用的额外参数如 `-handsoff`/`-run_until`，或仅内部构建支持）。后续若要继续，先试 `-handsoff` 组合，再考虑联系/查 PDX 内部资料；`collect_smoke_logs.ps1 -RequireScriptedTests` 的门禁语义保持不变。
6. **键盘注入的边界（自动化复用要点）**：
   - 方向键、空格：`PostMessage WM_KEYDOWN/WM_KEYUP`（带扫描码 lParam）可靠——空格可暂停/继续，方向键可平移地图（注意惯性极大，每次平移后必须截图确认）。
   - **点击选国会把镜头居中到所点省份**，点海会把镜头带去海上；选国界面务必"先 mouse_move 悬停 → 看 debug tooltip 显示目标国 → 再点击"。
   - Random Country 按钮：随机选一个可玩国家并居中放大——是绕过地图导航的最稳路径；scripted tests 只查世界状态，**用哪个国家开局都行**。
7. **实机错误计数**：debug 弹窗计数为进程累计；隔离 userdir 的 `error.log` 才可分类。修复前每局数万~数十万计数全部来自 §3 的两类 bug；修复后开局仅 16-21 个（原版军事部署/法律警告 + 少量 mod 州建筑提示），运行数周不增长。

## 3. 本轮发现并修复的 Mod 缺陷（未提交）

| 文件 | 缺陷 | 实机证据 | 修复 |
| --- | --- | --- | --- |
| `common/scripted_effects/ywc_shared_effects.txt` | `ywc_refresh_heritage_legitimacy_modifier`、`ywc_refresh_maritime_network_modifier`、`ywc_refresh_autonomy_pressure_modifier` 无条件 `remove_modifier` 不存在的修正 | error.log：`remove_modifier effect [ Timed modifier ywc_... not found ]` ×338，且每 tick 重复触发（游戏内计数飙到 23 万+，Slow Ticks） | 三处都改为 `if = { limit = { has_modifier = ... } remove_modifier = ... }` |
| `events/ywc_shu_jhg_events.txt` | ywc_shu.4.b / ywc_shu.5.b / ywc_jhg 两条路线的"继续"选项 trigger 误含 `var:..._progress >= 100`（其他国家的路线模板没有） | error.log：`Out of the 3 scripted options for event ywc_shu.4, none were valid` ×113（同一秒内每 tick 刷）；路线永远停在 20，AI 只能选放弃 | trigger 删去 `>= 100` 行（if/limit 内的成功判断保留） |

另有观察（未修，需上游决策）：
- `events/ywc_shared_events.txt:39`（月度共享事件）会对未初始化共享变量的国家调用 `ywc_open_trade_route` 等效果，产生 `change_variable [ Variable not of the 'value' scope type ]` / `Failed to fetch variable 'ywc_maritime_network_level'` 错误（本轮乌拉圭局 8 次）。建议在该事件效果前加 `has_variable` 守卫或限制作用域为十国。
- SHU 海关事件（ywc_shu.3）弹出的插画是粉色占位图形，疑似缺 event picture 资源。
- `tools/ywc_test_gui/` 触发一条 `Mod metadata read error ... .metadata/metadata.json` 无害告警；如需消除，补一个最小 metadata.json 即可。
- `collect_smoke_logs.ps1` 只扫 `logs/debug.log`，而长会话的启动期挂载行会轮转进 `logs/debug.1.log`——本轮 `mod_mount=not_mounted` 即此工具盲点（实际挂载与版本匹配证据在 debug.1.log:94-96）。下轮可让采集器一并扫 `debug.*.log`。

## 4. 复现本轮实机管线的最小步骤（下轮直接照做）

1. 隔离 userdir：`artifacts/observe/<name>/userdata`，写无 BOM `content_load.json`（enabledMods 用 `\\` 转义路径，参考现有文件）。
2. 启动：`binaries/victoria3.exe -debug_mode -userdir "<ud>" -scripted_tests`（WorkingDirectory=游戏根）。直启无 Steam 可进战局，不影响证据。
3. 主菜单（约 2-3 分钟，首次编译着色器更久）→ New Game → Sandbox → **Random Country** → Start。
4. 等开局初始化完成（开局 1-10 分钟内 UI 点击无响应属正常，等 FPS 恢复、错误弹窗稳定）。
5. PostMessage `` ` ``（脚本 `artifacts/observe/manual-gate23-1836-shu-01/post_key.ps1`，改 hwnd 参数）打开调试工具栏。
6. 点 "YWC Tests"（137,613@1280x800）→ zoom 左上角 console 确认最后一行是 `Scripted tests enabled.`（每次点击只切换一次；若 disabled 再点一次）。
7. PostMessage VK_SPACE（`post_space.ps1`）解除暂停；速度 1 下约 60-80 秒到达 1836.2.1，套件结束并写 `tests.txt`。
8. 检查 `<ud>/tests.txt`；随后菜单 → Exit Game → Exit to Desktop（正常退出保证日志完整）。
9. 采集：`powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot <ud> -RequireScriptedTests`——`scripted_tests=present` 才算数。

## 5. 当前验证事实（静态）

- 全量测试：`Ran 190 tests ... OK`（含更新后的契约测试）。
- `ywc_check.py`：exit 0。
- 本次会话创建的实机证据目录：`artifacts/observe/manual-gate23-1836-shu-01/`（含 userdata/logs 全套、console_history、多个失败/成功切换的控制台记录、errors 分类输入）。
- 旧结论仍有效：观察矩阵 15 个 run 全部诚实 pending；`check_release.py` 必须失败是门禁设计。

## 6. 接下来按这个顺序做

1. **scripted tests 证据（当前硬卡点）**：本轮已把管线推到极限——套件加载、周期、冲洗全部验证，但测试零记录（含 `always = yes` 探针）。下一轮先试 `-handsoff -run_until 1836.3.1 -scripted_tests` 组合（PDX CI 风格）；仍不行则该门槛对本构建不可自动化，向用户如实说明并请示（人工在真机点控制台执行是备选）。`collect_smoke_logs.ps1 -RequireScriptedTests` 语义不变。
2. **提交本轮修复**（§3 全部文件 + 本文档），提交信息建议 `fix: guard remove_modifier, repair SHU/JHG route option triggers, adopt vanilla scripted-test suite format`。
3. **十国 UI 验收**（手册门槛二）：逐国选国进 1836、核对 journal 表、首月事件双语选项、路线月度选项推进（现在 trigger 修复后"继续"选项可用了）、NMG 自治谈判两分支、DLC 开关增强项。结果写入 `docs/release/manual-acceptance-log.md`。
4. **五配置启动证据**（手册门槛一）：官方启动器 Playset 五配置，采集 `launcher-evidence.txt`。
5. **观察矩阵与门禁**（手册门槛四）：15 run × 3 检查年 × 10 国，`summarize_observation.py` + `check_release.py`。
6. 事件贴图：SHU 海关事件（ywc_shu.3）弹出的插画显示为粉色占位图形，确认是否缺 event picture 资源。

## 7. 常见误区（沿用并更新）

- 不要把 `MNG` 当运行时 TAG；运行时是 `MGL`。
- 不要把 `artifacts/smoke/latest-summary.txt` 单独当 clean 证据。
- 不要用键盘注入往控制台 editbox 打字（会重复字符且 `_` 变 `-`）；用 GUI 按钮或临时 GUI Mod 按钮。
- 每次点击 "YWC Tests" 只切换一次状态；以 console 回显为准，不在回显确认前连续点击。
- 选国界面点击省份会居中镜头；先悬停验证 tooltip 再点。
- 不要把"套件周期工作（tests.txt 被重写）"当成"测试已通过"——以结果行出现 PASS 为准。
- 本仓库不修改本体目录与三枚兼容层 DLL；`tools/ywc_test_gui/` 是本仓库自己的临时工具 Mod，不影响该约束。

## 8. 交接后的完成定义

与上一版一致：静态全绿 + 十国 UI 验收 + 两套原生 scripted tests 非空结果 + 15 run 观察证据 + `check_release.py` 通过 + 文档如实记录。本轮已把最后一项的前置管线全部打通，卡点只剩 §6.1 的测试记录问题。
