# 参考资料：V3 Mod 开发指南（本地 clone）

## 位置与更新

- 本地路径：`refs/v3_mod_guide_cn/`（已加入 `.gitignore`，不要提交进本仓库）
- 来源：<https://github.com/tangyixiao/v3_mod_guide_cn>
- 更新：`git -C refs/v3_mod_guide_cn pull`
- 内容是两部分：
  - `v3_mod_guide_cn/`：AI 生成的中文教程（约 600 页，chapters 五部分 + appendices A—L）；
  - `v3_wiki_docs/`：打包进去的官方 wiki Markdown（`Documentation/`、`Scripted_Types/`、`Map/`、`Graphics/` 等）。

## 使用纪律（重要）

该指南在 README 里**自述为 AI 生成、未经人工审查、代码示例未经实测**。因此：

- 用它做**导航、术语、章节定位**，不要直接拿它的代码当结论；
- 任何技术结论必须以**本机 1.13.11 本体文件**或**本仓库可运行的测试**为准；
- 引用它的具体规则时，在文档里注明已用本体核对（例如下面的三条）。

## 已从这份资料中提取并核对的结论

| 结论 | 在本体的核对方式 |
| --- | --- |
| 修正类型（modifier type）的权威清单在 `game/common/modifier_type_definitions/*.txt`；1.13.11 共 2364 个键；`12_ip4_script_modifiers.txt` 与 `13_ep2_script_modifiers.txt` 属于 DLC 内容 | 已实现为 `tools/modifier_audit.py`：逐一校验本仓库 118 个修正键与 58 个静态修正，并检查 `add_modifier` 引用是否有声明 |
| 日志（journal entry）的本地化键**就是日志 id 本身**，说明用 `_reason`，不是 `journal_entry_<id>` | 本体 `je_unify_afghanistan` + `je_unify_afghanistan_reason`（`localization/english/sphere_of_influence_lobbies_great_game_l_english.yml`） |
| `on_game_started_after_lobby` 是本体存在的 on_action 钩子 | 本体 `common/on_actions/00_code_on_actions.txt` |
| 本地化文件格式：`l_english:` / `l_simp_chinese:` 头 + `key:version "text"`，且 JSON/描述文件必须无 BOM | 与本体 `localization/english/*.yml` 一致；本仓库安装器与观察运行器已按此约束写 BOM-free 文件 |

## 2026-09-19 补充：从本体二进制核实的控制台/启动参数（比指南可靠）

指南附录 J 的控制台命令清单是 AI 生成、未经实测的，逐条以本体二进制字符串表为准（`binaries/victoria3.exe`，96,872,568 字节全量扫描）：

- **已坐实**：`observe`（别名 `ob`，描述 "start observing the game"）、`tag`（切换控制国家；本体 `common/console_command_macros/00_macros.txt` 里就写了 `tag FRA`）、以及一个改日期的命令（描述 `Changes current date`，格式 `yyyy.mm.dd.hh`，命令名待实机确认）。
- **已否决**：`human_ai` 在二进制中 **0 命中**——指南这条不可依赖，全 AI 观察局不能建在它上面。
- **命令行参数（与 `-debug_mode` 同级）**：`handsoff`、`run_until`、`start_tag=`、`no_notifications`、`scripted_tests`、`no_save_after_failed_test`、`save_before_failed_test`、`ui_validation`、`gamestate_validation`、`host_server`、`join_server`、`gamestate_generation_test`、`disable_renderframeifneeded` 等。其中 `no_notifications` 的说明是"抑制通知与事件弹窗，且不为它们自动暂停"。
- **实测反例**：`-handsoff -start_tag=SHU -run_until 1846.1.1` **不能**在无 UI 情况下自动开局（两次试点，只到主菜单、无存档），详见 `docs/release/automation-pilot-log.md`。

教训：指南（AI 生成）可当导航，但每条命令/参数必须先在本体文件或二进制里找到出处，再实机验证。

## 2026-09-20 补充：common/history 的根键是唯一且按目录固定的（实测）

**本体事实**：`common/history/<目录>/` 下的脚本文件只认一个根键，且目录名与根键一一对应。根键不对的文件被**整份静默丢弃**——`error.log` 里一个字都没有。

从本体 `common/history` 全量扫描得到的对照表（22 个目录，每目录恰好一个根键）：

| 目录 | 根键 | 目录 | 根键 |
| --- | --- | --- | --- |
| `ai` | `AI` | `population` | `POPULATION` |
| `buildings` | `BUILDINGS` | `power_blocs` | `POWER_BLOCS` |
| `characters` | `CHARACTERS` | `production_methods` | `PRODUCTION_METHODS` |
| `conscription` | `CONSCRIPTION` | `states` | `STATES` |
| `countries` | `COUNTRIES` | `trade` | `TRADE` |
| `cultures` | `CULTURES` | `treaties` | `TREATIES` |
| `diplomacy` | `DIPLOMACY` | `global` | `GLOBAL` |
| `diplomatic_plays` | `DIPLOMATIC_PLAYS` | `government_setup` | `GOVERNMENT_SETUP` |
| `governments` | `GOVERNMENT` | `lobbies` | `LOBBIES` |
| `military_deployments` | `MILITARY_DEPLOYMENTS` | `military_formations` | `MILITARY_FORMATIONS` |
| `political_movements` | `POLITICAL_MOVEMENTS` | `pops` | `POPS` |

注意**不是**目录名大写就完事：`governments`→`GOVERNMENT`、`population`→`POPULATION`、`pops`→`POPS` 都是特例。

**易踩的坑**：`DIPLOMATIC_PACTS` 这个字符串在本体里**确实存在**（`localization/*/interfaces_l_*.yml` 的预算面板措辞、`gui/budget_panel.gui` 的控件名、以及 `trigger_localization` 的分类名），所以它看起来像个合法根键——但它**不是**任何 history 根键。同理 `RELATIONS` 也不是。用它们写 `common/history/diplomacy/*.txt` 会得到"静态检查全绿、游戏里毫不知情"的效果。

**已落地的防复发**：`tools/ywc_check.py` 的 `_history_root_key_diagnostics` 按目录校验根键（有 `--game-root` 时从本体推导对照表，否则用内置基线），同时报"未知 history 目录"和"整份没有根键的文件"；回归测试在 `tests/test_history_root_keys.py`。

**属邦条约的方向（实测坐实）**：`pacts.database` 里每条 `targets={ first=… second=… }`，`first` 是**宗主**、`second` 是**属邦**。依据是本体 `common/history/diplomacy/00_subject_relationships.txt` 的 `c:CHI ?= { create_diplomatic_pact = { country = c:TIB type = vassal } }`，而一份真实存档里记录为 `vassal first=156 second=167`（156=CHI、167=TIB）。属邦类型集合可由本体 `common/subject_types/*.txt` 的 `diplomatic_action` 推导，不要把猜测写死。

## 后续内容开发时可以查的章节

- `chapters/part3_content/chapter11_event.md`、`chapter13_journal.md`、`chapter12_decision.md`、`chapter14_modifier.md`：事件/日志/决议/修正的写法与常见坑；
- `appendices/appendix_c_effect.md`、`appendix_b_trigger.md`、`appendix_e_variable.md`、`appendix_g_on_actions.md`：效果、触发器、变量、on_action 速查；
- `appendices/appendix_k_errors.md`：常见报错与排查表（可用来扩充 `ywc_check.py` 的静态诊断）；
- `v3_wiki_docs/Documentation/`：Scope、Trigger、Script_value、Modifier_types、On_actions、Localization 的官方说明。
