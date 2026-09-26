# 桌面/命令行自动化试点记录（§5.0）

> 本文件记录试点**实测**结果，不是计划。每条结论都附带证据路径或命令。执行者：Agent（WorkBuddy），方式：隐藏窗口启动，未注入键鼠、未占用前台。

## 试点 1：命令行无人开局（结论：不成立）

命令（脚本 `tools/pilot_cli_run.ps1`）：

```
victoria3.exe -handsoff -debug_mode -no_notifications -start_tag=SHU -run_until 1846.1.1 -userdir artifacts/observe/_pilot/userdata
```

结果（90 秒，证据：`artifacts/observe/_pilot/userdata/logs/`）：

- Mod 挂载与版本匹配成功：`debug.log` 有 `Mounted Data: .../game` 与 `Mod The Yongchang World ... successfully matched game version 1.13.11.`。
- 约 36 秒后进入主菜单（gui.log 加载字体、settings 写入、`Unlocalized text ... custom_tooltip.gui` 出现在 22:59:19）。
- **未进入任何战局**：日志中没有任何 `start_tag` / `run_until` / `handsoff` / 开局相关行；`save games/` 为空。
- 日志里也没有"参数无效/未知参数"类诊断，因此无法从日志区分"参数被忽略"还是"需要其它前置条件"。

## 试点 2：延长到 120 秒（结论：同试点 1）

证据：`artifacts/observe/_pilot/userdata2/`，`pilot2.txt`。同样只到主菜单，无存档、无战局。

**结论：1.13.11 下 `-handsoff` / `-start_tag=` / `-run_until` 不能在无 UI 的情况下自动开局。**要进战局必须走 GUI（启动器/主菜单/选国），即桌面自动化。

## 从本体文件核实到的游戏侧事实（新增，非照抄指南）

来源均为本机 `E:\SteamLibrary\steamapps\common\Victoria 3`：

| 事实 | 证据 |
| --- | --- |
| 控制台命令 `observe`（别名 `ob`）真实存在，说明为 "start observing the game" | `binaries/victoria3.exe` 字符串表（命令+描述表内），并有 `Going to observe mode...` / `Ending observe mode...` 运行时文本 |
| 控制台命令 `tag`（切换控制国家）真实存在 | 同上；且本体自带 `game/common/console_command_macros/00_macros.txt` 里直接写了 `tag FRA` |
| 存在"改当前日期"的控制台命令（描述 `Changes current date`，参数格式 `yyyy.mm.dd.hh`），命令名待实机确认 | 同上字符串表 |
| **`human_ai` 在本体二进制中 0 命中**——AI 生成指南附录 J 的这条不可依赖 | 全量扫描 96,872,568 字节，0 命中 |
| 命令行参数集合存在：`handsoff`、`run_until`、`start_tag=`、`no_notifications`、`scripted_tests`、`no_save_after_failed_test`、`save_before_failed_test`、`ui_validation`、`gamestate_validation`、`host_server`、`join_server`、`gamestate_generation_test`、`disable_renderframeifneeded` 等 | 同上（参数表片段） |
| `no_notifications` 的说明是"抑制通知与事件弹窗，且不为它们自动暂停" | 同上；对无人长跑很有用 |
| `scripted_tests` 的合法用法是 `scripted_tests after`（参数可选，默认失败后存档） | 二进制内错误提示文本，与 `scripted_tests.md` 一致 |
| 观察者模式概念与入口真实存在 | `localization/english/concepts_l_english.yml` 的 `concept_observer_mode`；`icon_observer` 出现在 `gui/multiplayer_lobby.gui`、`gui/multiplayer_types.gui` |

## 试点 3：桌面 GUI 路线（2026-09-20 起）

**注入时段登记（纪律要求，先登记再注入）**

- 起：2026-09-20 19:23（+08:00）。用户已明示"最好一直到做完"，同意占用桌面。
- 注入范围：仅 Victoria 3 启动器（`dowser.exe` / `launcher-x64.exe`）与游戏窗口 `victoria3.exe`，以及它们自己的确认框。
- 收尾：按 PID 结束本会话启动的进程，确认无残留 `victoria3.exe` / 启动器窗口。
- 前置备份：`artifacts/launcher-backup/launcher-v2.before-agent-automation.sqlite`（sha256 `0d4305d1…042b6`，126976 字节）。
- 侦察（只读，未注入）：桌面可见窗口 21 个，**没有**启动器或游戏窗口；`launcher-x64.exe`（PID 6472）位于 Session 0（Services）且只有 7MB，是无窗口的残留进程，不可点击。分辨率为 2560x1600。
- 起点基线：`inspect_playsets.py` 报告五个 Playset 均不存在，当前激活的是 `mods`。

### 试点 3 结果

**结论一：官方启动器在本机当前完全起不来（阻塞门槛一与门槛四的 DLC 维度）。**

试过的入口，全部失败：

| 入口 | 结果 |
| --- | --- |
| `launcher/dowser.exe`（Steam 目录里的引导器） | 退出，`launcher-dowser.log` 今天无任何新行 |
| `D:\Paradox Interactive\launcher\bootstrapper-v2.exe`（开始菜单快捷方式的目标） | 自身能跑（`launcher-bootstrapper.log` 有 19:30 记录），但子进程立刻死 |
| `launcher-v2.2026.11.1\Paradox Launcher.exe`（带日志原文的完整参数 `--pdxlLauncherInvokedTimestamp --pdxlGameDir --gameDir`） | **0.26 秒退出，退出码 9**，今天不产生 `launcher-2026-09-20.log` |
| 同上 + `--user-data-dir` 换目录 | 同样退出码 9 |

关键证据：`launcher-bootstrapper.log` 里今天的命令行是
`Paradox Launcher.exe --pdxlLauncherInvokedTimestamp 1789903812514`，**没有** `--pdxlGameDir/--gameDir`；而 2026-09-14 成功那次是带全参数的。但即使我手工补全参数，`Paradox Launcher.exe` 仍在 0.26 秒内以退出码 9 退出、且**在写自己的日志之前就死**——它连 `[main]: Setting 'userData'` 那行都没来得及写。这是原生层早退，不是我们参数的问题。

顺带排除的项：端口 11000（启动器与 cpatch 通信用的）空闲；`dlc_signature` 文件在真实与隔离用户目录里都存在；`chromium-data` 下没有残留 Singleton 锁文件；`%LOCALAPPDATA%\Paradox Interactive\launcher-v2` 里没有今天的崩溃 dump。另有一个 **PID 6472 的 `launcher-x64.exe` 僵尸进程挂在 Session 0（Services）**，7MB、0 CPU、无窗口、属主"暂缺"，非本会话启动，未处理。

**结论二：不经启动器时，DLC 后端当前不可用，一个 DLC 都不挂（阻塞门槛四的配置维度）。**

`tools/probe_dlc_gating.py`（隐藏窗口、独立 userdir、不注入输入）跑了两次：

| 配置 | `content_load.json` 的 `disabledDLC` | 引擎声明 DLC | 实际挂载 dlc 目录 |
| --- | --- | --- | --- |
| `none` | 三个门槛 DLC 全禁用 | 18 | **0**（只有 Mod） |
| `all` | 空 | 18 | **0**（只有 Mod） |

两次日志里各有 14 行 `[dlc.cpp:822]: Could not find item in store backend.`。对照 2026-09-19 的试点日志（同样直接启动 exe、`disabledDLC` 为空）：**18 个 dlc 目录全部挂载**，且 0 行 store backend 错误。也就是说后端状态在"全拥有"与"全不可用"之间切换，今天处于后者。

因此今天无法从这条路径得到任何一种 DLC 配置，也无法判断 `disabledDLC` 是否被尊重——禁用与不禁用两次的结果完全一样（都是 0）。这印证了记忆里那条"直接启动 exe 时所有权后端会波动"，也说明 **DLC 配置只能靠启动器**这条约束是真的。

**结论三：游戏本体可以跑、可以抓图，但被宿主的 job object 管着进程树。**

- `binaries/victoria3.exe -debug_mode -userdir <隔离目录>` 能正常启动并到达主菜单：窗口标题 `Victoria 3`、尺寸 2560x1600、**非独占全屏**（`ImageGrab` 能抓到画面，实测截到了 V3 作品画与"Compiling shaders"进度条）。日志在 19:41:59 出现 `Unlocalized text ... custom_tooltip.gui`，与 2026-09-19 试点"看到这行即到主菜单"一致。
- **陷阱：谁启动它，谁的命令一结束就被整棵杀掉。** `subprocess.DETACHED_PROCESS` 不够，`CREATE_BREAKAWAY_FROM_JOB` 被拒（WinError 5 拒绝访问），所以游戏留在宿主 job object 里：命令一结束，游戏在内容枚举中途消失（`debug.log` 停在 `Starting pre-enumerating ...`，无 error.log、无 crash dump）。
- **解法**：`tools/keep_game_alive.py` 作为长期后台任务运行，自己启动游戏并保持存活，游戏就不会被回收；收到 `artifacts/automation/stop.flag` 或超时后由它 `taskkill` 收尾。本会话用它把游戏稳定保持在主菜单。

**本会话新增的自动化资产**（都在 `tools/`）：`recon_desktop.py`（只读窗口清单+截图）、`game_ui.py`（launch/shot/click/key/list/kill，点击前先校验坐标落在游戏窗口矩形内）、`keep_game_alive.py`、`launch_launcher.py`、`diagnose_launcher.py`、`probe_dlc_gating.py`。

**为什么停在"到主菜单"**：19:45 起用户已回到前台使用电脑（开始菜单与浏览器可见），而游戏窗口的矩形就是整个屏幕（0,0,2560,1600），此时任何一次点击都会落到用户的窗口上——`game_ui.py` 的"坐标在窗口内"校验在这种情况下形同虚设。按纪律"用户正在使用电脑（前台不是我们的窗口）时暂停自动化"，在拿到一个不被打断的桌面时段之前不再注入。

**结论四：命令行进战局也已彻底证伪（第二次独立验证）。**

`tools/probe_campaign_launch.py` 把一份真实的本 Mod 1836 存档放进隔离 userdir 的 `save games/`，用 `-debug_mode -continue -no_notifications` 隐藏窗口跑 165 秒：

| 采样点 | debug.log 行数 |
| --- | --- |
| 15s / 30s | 261 / 261 |
| 45s 起直到 165s | **279 恒定** |

279 行正是主菜单的签名（与试点 1/2 一致），且 `code_on_actions` 命中 **0**、`Transition *->Game` **0 次**——存档根本没被加载。结合交接 §5.0 已记录的 `-handsoff -start_tag=SHU -run_until` 失败，**1.13.11 下不存在任何"无 UI 直接进战局"的命令行路径**。（未再跑 `-continue -handsoff` 变体：`-continue` 单独已证明存档不加载，叠加 `-handsoff` 不会让存档加载。）

**进入战局的日志判据**（后续脚本自我验证用）：主菜单稳定在 ~279 行且不再增长；战局中 `debug.log` 会持续增长，并出现 `common/on_actions/00_code_on_actions` 命中与 `Transition ...->Game`。用户上次真实战役的 `debug.log` 是 4416 行、46 次 on_action 命中，可直接对照。

**结论五：工具 Mod 的控制台按钮是本项目既有的可靠注入通道。**

`tools/ywc_test_gui/gui/console.gui` 用 `onclick = "[ExecuteConsoleCommand('...')]"` 实现按钮，已有一个 `scripted_tests` 按钮。需要 `tag XXX` / `observe` / `speed 5` 这类命令时，往这个 Mod 加按钮即可，不必往控制台文本框注入文本。**注意**：它是第二个 Mod，会让"只启用 The Yongchang World"的配置要求不再成立，所以只用于门槛三的套件执行，不能混进门槛四的观察局。

**下一步（需要用户）**：①先让启动器能起来（用户侧动作，见交接 §1.1）；②给一个不被打断的桌面时段，把"进战局 → 选国 → 截图 journal/事件 → 控制台 observe"跑通，之后才是门槛二与门槛三。执行步骤见 `docs/release/tonight-runbook.md`。

## 待实机核对（标 ⚠ 未消）

- `observe` 命令在**单人局**内是否可切换（二进制证明命令存在，未证明单人可用）。
- `speed [1-5]`、`pause`、改日期命令的准确名称。
- 剪贴板粘贴（Ctrl+V）注入控制台是否可靠（历史逐键注入不可靠）。

## 下一步（需要桌面窗口）

1. pyautogui 试点：截图定位启动器 Playset 下拉并点击（证明启动器可自动化）。
2. 进一局 1836：选国 → 暂停 → 截图选国界面与 journal 面板 → 试 `observe` 与速度控制 → 退出。
3. 试点结果回写本文件；失败（附证据）才触发交接 §2 的第 0 次用户批次。

---

# 试点 4（2026-09-21 17:33–17:45）：DLC 后端已恢复，但 `disabledDLC` 被引擎完全忽略

上一轮（2026-09-20）记的是"DLC 后端不可用、一个都不挂"（14 行 `Could not find item in store backend`）。今天复测，**后端恢复了**，但暴露出一个更要紧的事实：不经启动器时，`content_load.json` 的 `disabledDLC` 对一个 DLC 都拦不住。

## 证据一：DLC 后端已恢复

`python tools/probe_dlc_gating.py --config all --seconds 60`：

| 项 | 结果 |
| --- | --- |
| 引擎声明 DLC | 18 |
| 实际挂载 dlc 目录 | **17**（含全部三个门槛 DLC） |
| 三个门槛 DLC | `dlc010_ep1`(势力范围)、`dlc013_mp1`(商业特许)、`dlc018_ep2`(滔天巨浪) 全部挂载 |
| `Could not find item in store backend` | **0 行**（2026-09-20 是 14 行） |

`dlc_signature` = `14b575738ba9cc9012517158f833a369`，与真实用户目录 `D:/Documents/Paradox Interactive/Victoria 3/dlc_signature` **完全一致**。也就是说引擎现在认为隔离目录的 DLC 集合与日常游戏相同——这是"全拥有"态。

## 证据二：`disabledDLC` 不起作用（本次的核心结论）

同一命令跑 `--config none`（请求禁用那三个门槛 DLC）：

| 配置 | `disabledDLC` 内容 | 实际挂载门槛 DLC |
| --- | --- | --- |
| `none` | `["dlc010_ep1","dlc013_mp1","dlc018_ep2"]` | **全部三个，一个没少** |
| `all` | `[]` | 全部三个 |

`content_load.json` 文件确认写对了（无 BOM、键名拼写正确、路径为绝对路径）：

```json
{"enabledMods":[{"path":"E:\Victoria3 Mod\yongchang_world"}],"disabledDLC":["dlc010_ep1","dlc013_mp1","dlc018_ep2"],"enabledUGC":[]}
```

从本体二进制里查到引擎**确实认识**这些键——`dlc.cpp`（`pdx_mod_dlc_manager`）里有相邻字符串 `paradoxAppId` / `disabledDLC` / `enabledMods` / `orderedListMods` / `Error reading dlcs/mods arrays.` / `Could not read enabled mods/disabled DLC, launcher-generated format v1/1.1 file '{}' doesn't exist.`。所以这不是拼写问题，是**没有启动器的 `paradoxAppId` 授权上下文时，禁用名单不生效**。

## 证据三：反证实验——补 `paradoxAppId` 会更糟

| 变体 | `content_load.json` 形状 | 结果 |
| --- | --- | --- |
| A | mod 条目加 `"paradoxAppId":"529340"` | 挂载 **0** 个 dlc 目录（Mod 本身仍挂上了） |
| B | `disabledDLC` 改成对象数组 `[{"id":...,"paradoxAppId":"2411231"}]` | 挂载 **17** 个，仍然全部 |

日志里每次运行都有 3 行 `[dlc.cpp:195]: Missing paradoxAppId for dlc/mod`。变体 A 让引擎把带 appId 的条目当成"有授权的一条"、反而把其余全部排除——**方向错了，不能用**。变体 B 说明 `disabledDLC` 只接受字符串数组，且照样被忽略。

## 对验收的影响

- **门槛四的 DLC 配置维度仍然产不出**，但原因从"后端不可用"变成"后端可用、开关不生效"。五个配置（`none/sphere/charters/wave/all`）里，`sphere/charters/wave` 这三个**要求部分挂载**的配置，不经启动器无论如何都做不到——它们会全部退化成 `all`。
- **门槛一不变**：它的定义就是"启动器里存在五个 Playset 且 `inspect_playsets.py` exit 0"，本来就绕不开启动器。
- 好消息：既然引擎现在能挂到全部 DLC，**只要启动器能起来并配上 Playset，五个配置就都能产出了**。昨天那条"后端不可用"的硬阻塞已经解除了一半。

## 工具改动

`tools/probe_dlc_gating.py` 原来的判据是"挂载集合 == 期望集合"，这在 `disabledDLC` 被忽略时会**误报"符合"**（`all` 配置两边都是全集，恰好相等）。已改为：只要 `disabledDLC` 非空却仍挂载全部门槛 DLC，就直接判定"被完全忽略"并退出 1，同时打印 `Missing paradoxAppId` 计数。

## 启动器现状（复测）

`python tools/launch_launcher.py` 能起来又立刻退出；直接跑 `Paradox Launcher.exe` 退出码 **9**、耗时 **0.02–0.26 s**。试过四种进程创建标志（plain / detached / newgroup 全部 rc=0 秒退；`breakaway` 被拒 WinError 5），换过 `--user-data-dir`，都无效。它死在写自己日志之前，`launcher-2026-09-21.log` 根本没生成，WER 与 `Local\CrashDumps` 里也没有对应报告——原生层早退。**结论不变：启动器仍需要用户侧修。**

## 启动器：2026-09-21 追加排查（仍未解决，但排除了一个假设）

**假设"第三方注入 DLL 导致启动器早退"已被证伪。** 做法是非破坏性的：把 `launcher-v2.2026.11.1\` 整个复制到 `artifacts/automation/launcher-probe/`（复制完即删），副本的**父目录里没有** `version.dll`/`winmm.dll`/`Juij_Steam.dll`，然后在副本里直接跑 `Paradox Launcher.exe`。结果仍是 **0.30 秒退出、退出码 9**。所以注入层不是原因——又确认了一处：启动器目录 `launcher-v2.2026.11.1\` 里本来就没有那几个 DLL，它们只在上层 `launcher\` 里。

**9-14 成功那次与今天的差异（从日志看）**：9-14 的启动器跑到了 `[LaunchExecutable]: Starting game: ../binaries/victoria3.exe`，并且给游戏传了 `--pdx-launcher-session-token,<redacted>,--paradox-account-userid,ccfc6d86-...`；今天连自己的第一行日志都写不出来。也就是说 9-14 时启动器**有有效的 Paradox 账号会话**。现在 `%APPDATA%\Paradox Interactive\launcher-v2\` 下只有 `cache/`、`game-metadata/`、`session.js`（64 字节、9-05 写），**没有 `userSettings.json`**——而 9-14 的日志里明确读过 `userSettingsHandler: Loading user settings succeeded`。`pdx_settings.json` 的 `Account` 节点也是空数组 `[]`。

这两点合起来提示"会话/设置文件缺失导致原生层早退"，但**没有验证手段**（启动器连日志都不写，无法观察它读到哪一步）。仍在启动器自己的错误处理之前死掉，所以无法从外部继续缩小范围。

**给用户的判断**：按代价从低到高——① 启动 Steam 客户端后重试（`D:\Steam\steam.exe` 存在，当前没运行）；② 重启电脑；③ 用 `launcher\launcher-installer-windows_2026.10.exe` 重装启动器。重装是最可能有效的，因为它会重建启动器的整个目录树与设置文件。**在此之前门槛一与门槛四的 DLC 维度都无法产出。**

---

# 试点 5（2026-09-21 18:51）：★ 启动器解封 —— 必须经 Steam 拉起

用户启动 Steam 客户端后复测，**阻塞解除**。

## 关键对比

| 入口 | 结果 |
| --- | --- |
| `tools/launch_launcher.py`（补全 `--pdxlLauncherInvokedTimestamp/--pdxlGameDir/--gameDir`） | 仍 **秒退**，退出码 9，不写日志 |
| **`os.startfile("steam://rungameid/529340")`（经 Steam 协议）** | **成功**：`bootstrapper-v2.exe` → `Paradox Launcher.exe`，存活 30s+，窗口 `[Chrome_WidgetWin_1] Victoria 3` 1956x1052 |

两者唯一的差别是 **Steam 提供的会话上下文**。此前所有失败都卡在这里：启动器在 `[main]: Setting 'userData'` 之前就死，所以什么都不写。走 Steam 协议后 `launcher-2026-09-21.log` 正常写出（24,610 字节），其中：

```
[SettingsService]: Initialized SettingsService for ~\...\session.js (encrypted, encoding: binary)
[UserSettingsHandler]: Loading user settings succeeded
[MetadataFormatService]: Metadata structure verified          <- 读到三个 mod（含 yongchang_world）
[SteamDlcAdapter]: Getting Dlc from Steam                     <- DLC 授权来自 Steam
[GenericDlcSignatureService]: Generating and saving DLC signature
[GamesHandler]: Setting activationSets to true for game victoria3
```

注意 `session.js` 那行——直接启动时缺的正是这个会话；`appDataPath` 解析到 `~\AppData\Roaming\Paradox Interactive\launcher-v2`（不是 `paradox-launcher-v2`，两个目录容易混）。

## 影响

- **门槛一解封**：启动器 UI 可用（窗口非全屏，1956x1052，比游戏全屏安全）。
- **门槛四的 DLC 维度解封**：`[SteamDlcAdapter]: Getting Dlc from Steam` 说明启动器现在能从 Steam 拿到完整授权，五个 Playset 的 DLC 开关才有意义。此前"不经启动器 `disabledDLC` 被忽略"的问题因此不再是死路——配置由启动器应用，而不是靠 `content_load.json`。
- **已证伪的旧假设记录在此**：不是第三方兼容层（`version.dll`/`winmm.dll`/`Juij_Steam.dll`）；把启动器整目录复制到无这些 DLL 的路径仍 0.30s 秒退。
- `launcher-2026-09-21.log` 里仍有 `launcher-x64.exe` 遗留目录扫描与 `Found 2 compatible launcher version(s)`，属正常。

## 现状与下一步

启动器可随时用 `steam://rungameid/529340` 重新拉起（**不需要用户配合**）。DB 已备份到 `artifacts/launcher-backup/launcher-v2.before-playsets-20260921.sqlite`。

`inspect_playsets.py` 目前仍 exit 1：DB 里只有 `mods`（active）与 `Yongchang World` 两个 playset，五个门槛配置（`none`/`sphere`/`charters`/`wave`/`all`）都还没建。表结构已摸清（`playsets` / `playsets_mods` / `playsets_dlcs`），两条路可选：① 启动器 UI 手工建（门槛原文要求）；② 直接写 DB（不占桌面，但需在证据里写明方法，并以"五配置启动后 DLC 挂载确实不同"来佐证其有效性）。

---

## 2026-09-25 非 GUI 状态刷新：预检与现有日志采集（不计作试点）

本节记录本轮真实运行结果。没有启动游戏或启动器，没有执行桌面输入；以下内容是静态预检和用户数据目录中现存日志的诊断采集，不是实机验收证据。

### 桌面与 Playset 状态

- `steam` 正在运行（PID `32620`，Session 1）；未发现 `victoria3.exe`。`launcher-x64.exe` PID `6808` 位于 Session 0。
- `python tools/game_ui.py list` 显示当前桌面有 Chrome/Gmail 等用户窗口；前台是 Chrome。本轮没有注入键鼠。
- `python tools/inspect_playsets.py --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3'`：exit 1。活动 Playset 为 `mods`；`none`、`sphere`、`charters`、`wave`、`all` 五个 Playset 均不存在。

### 静态预检

命令：

```powershell
python tools/acceptance_preflight.py --root . --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3' --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
```

结果：`ywc_check`、`scenario_tag_audit`、`content_reachability`（92 events / 74 journals）、`startup_data`（1588 buildings / 2180 pop fields）均为 `ok`；scripted-test vocabulary 为 `ok`（12 keys）。四项未完成门槛仍是 Playsets `0/5`、十国验收 `0/36`、scripted tests `0/2`、观察点 `0/450`（`0/15` runs ready）。命令 exit 1 是因为这些验收门槛 incomplete，不是上述静态检查失败。

### 现有游戏日志采集

命令（`-NoLaunch`，输出到新文件，不覆盖旧摘要）：

```powershell
powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot 'D:\Documents\Paradox Interactive\Victoria 3' -SummaryPath 'artifacts/smoke/2026-09-25-no-launch-summary.txt'
```

采集到的用户数据日志时间：`game.log` / `error.log` 为 2026-09-25 11:28，`debug.log` 为 12:34。摘要为 `status=error`、`finding_count=261`、`mod_mount=not_mounted`、`scripted_tests=not_requested`。261 条全部是 `game.log` 中 `remove_building` 的 `Invalid database object` 诊断；没有 `ywc_`、`yongchang_world`、`Unknown trigger` 或 `Unknown effect` 命中。

同一时点的 `content_load.json` 列出两个 Workshop Mod 和 Yongchang World，但收集器没有在 `debug.log` 中找到 Yongchang World 的挂载行。因此这批历史日志无法证明当前工作树已进入游戏，也不能把这些诊断归因给 Yongchang World；它们只作为待隔离复现的环境基线。完整汇总见 `artifacts/smoke/2026-09-25-no-launch-summary.txt`。`docs/release/manual-acceptance-log.md` 保持原状，36 项仍全部 pending。

### 后续

桌面空闲后再经 Steam 协议启动官方启动器，创建并核对五个 Playset；随后用只启用 Yongchang World 的隔离运行采集新的 `debug.log`、`game.log`、`error.log` 和 `tests.txt`。在这些真实战局日志和 PASS 输出产生之前，不更新任何 `verified` 状态。
