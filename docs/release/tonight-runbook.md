# 自动化执行手册（2026-09-25 状态刷新）

> 本文件是**给执行者（Agent）用的操作序列**，不是计划书。每一步都写明命令、判据和失败回退。
> 纪律：注入只作用于 Victoria 3 启动器与 `victoria3.exe` 窗口；游戏不在前台时**禁止点击**（游戏窗口矩形＝整屏，点偏就落到用户窗口上）；每阶段结束按 PID 收尾。

## 0. 前置检查（任何时候都能跑，不占桌面）

```powershell
Set-Location 'E:\Victoria3 Mod'
python -m unittest discover -s tests                      # 记录当前完整通过数；341/341 是 2026-09-20 的历史计数
python tools/acceptance_preflight.py --root . --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3' --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'
Get-Process victoria3,launcher-x64 -ErrorAction SilentlyContinue   # 必须为空/只有 Session 0 那个僵尸
```

若上一轮留下 `artifacts/automation/stop.flag`，先删掉。

## 阶段 A：启动器（门槛一的唯一入口）

1. 确认 Steam 客户端已运行：`Get-Process steam -ErrorAction SilentlyContinue`。
2. 经 Steam 协议启动 Victoria 3：`python -c "import os; os.startfile('steam://rungameid/529340')"`。2026-09-21 试点 5 实测该入口能启动 `bootstrapper-v2.exe` 和 Paradox Launcher，并稳定显示窗口。不要使用 `python tools/launch_launcher.py`：本机直接启动仍以退出码 9 秒退、不写日志。
3. 若出现启动器窗口，**门槛一解封**；若 Steam 协议启动失败，记录本次新证据到 `docs/release/automation-pilot-log.md`。
4. 启动器 UI 可自动化后（`python tools/recon_desktop.py` 确认窗口与矩形，`python tools/game_ui.py list` 同理）：
   - 创建 `none`/`sphere`/`charters`/`wave`/`all` 五个 Playset，每个只启用 `The Yongchang World`，按配置拨三个 DLC 开关；
   - `python tools/inspect_playsets.py --user-data-dir 'D:/Documents/Paradox Interactive/Victoria 3' --output artifacts/observe/launcher-evidence.json` 到 **exit 0**；
   - 每配置从启动器启动一次到主菜单，`powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch` 采证。
5. **失败回退**：Steam 协议启动器仍起不来 → 记录本次证据，跳到阶段 B，只做门槛二/三。

## 阶段 B：进战局（这是所有 GUI 工作的总闸）

命令行已两次证伪（`-handsoff -start_tag -run_until` 与 `-continue`），**只能走 GUI**。

1. 用 keeper 持有游戏进程（关键：宿主的 job object 会连坐杀进程，`DETACHED_PROCESS` 不够、breakaway 被拒）：

   ```powershell
   # 以后台任务方式运行，不要用前台命令
   python tools/keep_game_alive.py --userdir 'artifacts/observe/_gui/userdata' --minutes 480
   ```

2. 等主菜单：判据是 `debug.log` 稳定在 ~279 行、窗口标题为 `Victoria 3`。首次新 userdir 要编译着色器，可能几分钟。
3. **UI 侦察（必须由 Agent 看图决定点击位置）**：
   - `python tools/game_ui.py shot --label b1-mainmenu` → 查看 `artifacts/automation/b1-mainmenu-window.png`
   - 确认游戏在前台（`bg` 截图里看到的是游戏画面而不是用户的浏览器）后才允许点击；
   - `python tools/game_ui.py click --x <窗口内X> --y <窗口内Y> --label b2-singleplayer`
   - 重复"截图→判读→点击"，直到进入选国界面。
4. 选国：**MGL 必须按运行时标签 `MGL` 选**（目录逻辑名是 `MNG`）。选 SHU 做首轮。
5. 进战局后立刻暂停（空格），`python tools/game_ui.py shot --label b9-ingame` 存档证据。

## 阶段 C：门槛二（十国 1836）

每国一轮，全部写进 `docs/release/manual-acceptance-log.md`（`verified` 行 + 证据路径，执行者如实写 Agent 自动化）：

1. 选国进入 1836 → 暂停 → 截图：选国界面、journal 面板、首月事件弹窗（双语选项）。
2. 路线按月推进至少一个选项，确认 进度/成功/失败/放弃 分支之一实机可见。
3. **NMG 加做自治谈判两支**：存档-读档法分别取接受/拒绝，确认主日志、关系/压力与 365 天冷却。
4. 换国优先用控制台按钮（见阶段 D 的按钮方案），避免反复走选国界面。
5. 截图判读可用子代理复核内容后再归档。

## 阶段 D：门槛三（两套原生 scripted_tests）

1. `python tools/scripted_test_audit.py --mod-root yongchang_world --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game'`（期望 ok，12 键全部有本体依据）。
2. **别往控制台文本框打字**（历史实测重复字符、`_` 变 `-`）。用 `tools/ywc_test_gui/gui/console.gui` 的 `ExecuteConsoleCommand` 按钮：已有 `scripted_tests` 按钮，需要就再加。
3. 1836 首月跑 `ywc_startup_smoke.txt`，检查年跑 `ywc_longrun_invariants.txt`；要求回显出现真实 `PASS` 并截图。
   - **必看**：`c:JHG ?= { is_subject_of = c:SHU }` 与 `c:NMG ?= { is_subject_of = c:MEX }`——2026-09-20 修掉了属邦根键（`DIPLOMATIC_PACTS`/`RELATIONS` → `DIPLOMACY`）后这两条才第一次可能成立。
4. 退出后 `powershell -NoProfile -File tools/collect_smoke_logs.ps1 -NoLaunch -UserDataRoot <userdir> -RequireScriptedTests`，必须是 `scripted_tests=pass`（`missing/empty/present` 都不算）。
5. **注意**：这个工具 Mod 是第二个 Mod，**只用于本阶段**，不能混进门槛四的观察局。

## 阶段 E：门槛四长跑（15 run × 3 检查点）

**前置阻塞（2026-09-21 更新）**：DLC 后端**已恢复**（`probe_dlc_gating.py --config all` 挂载 17 个 dlc 目录、0 行 store backend 错误），但复测发现**不经启动器时 `disabledDLC` 被完全忽略**——`--config none` 照样全挂载。所以 `sphere`/`charters`/`wave` 三个"部分挂载"配置不经启动器产不出，会全部退化成 `all`。**必须先让启动器起来配上 Playset 再开跑**，否则 15 个 run 的证据全都是"全 DLC"状态，等于白跑。详见 `docs/release/automation-pilot-log.md` 试点 4。

每 run：

1. 用对应 Playset 启动（保证 DLC 集合）→ 进战局 → `observe` 切观察者 → 速度 5。
2. 1846/1866/1900：暂停 → 存档 → 跑 `ywc_longrun_invariants.txt` → 继续或退出。
3. 从存档导出检查点（不需要人对面板抄数）：

   ```powershell
   python tools/save_checkpoint_export.py --save "<userdir>/save games/autosave.v3" --game-root 'E:/SteamLibrary/steamapps/common/Victoria 3/game' --error-log "<userdir>/logs/error.log" --output 1846.csv --format csv
   python tools/record_checkpoint.py --config <c> --seed <s> --year 1846 --input 1846.csv
   ```

   存档日期不在检查年会被拒绝（`--any-date` 只用于诊断，且输出自标 `checkpoint_eligible=false`）。

4. 三年齐 → `--finalize` → `summarize_observation.py` → `check_release.py`，期望 15 条 `verified`、exit 0。
5. `run.json` 的 `desktop_interaction` 如实改写（如 `agent_desktop_automation`）。
6. 墙钟预算：速度 5 下 1836→1900 约 1–3 小时/run；15 run 串行 1–3 天，跨会话后台跑，**一次只跑 1 个游戏实例**。

## 收尾（每阶段结束都做）

```powershell
New-Item -ItemType File -Force artifacts/automation/stop.flag   # 让 keeper 结束并 taskkill 游戏
Remove-Item artifacts/automation/stop.flag
Get-Process victoria3 -ErrorAction SilentlyContinue             # 必须为空
```

- 更新 `CHANGELOG.md`；`docs/release/automation-pilot-log.md` 记本轮实测；工作树**不要提交、不要清理**，按用户指示处理。
- 不修改本体目录与三枚兼容层 DLL；`launcher-v2.sqlite` 只读（已备份在 `artifacts/launcher-backup/`）。

## 已知环境坑（踩过的，别再踩）

- **默认命令超时 120 秒**：任何 `sleep 150` 级的前台命令会被 SIGTERM 切断，长任务一律明确加长超时或走后台。
- **别解析 `tasklist` 的文本输出**：中文 Windows 下是 GBK，`text=True` 按 UTF-8 解码会在读取线程里抛异常、`.stdout` 变成 `None`，进而把长跑任务一起带走（`keep_game_alive.py` 就因此崩过一次）。用 `tools/game_ui.py::process_alive`（ctypes `OpenProcess`+`WaitForSingleObject`）。
- **`reg.exe` 被安全策略禁止**，不要用注册表查询做诊断。
- **为游戏写的 JSON 必须无 BOM**，否则被静默拒绝。
