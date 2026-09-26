# 《永昌世界》v0.1 人工验收记录

> 这是空白记录模板，不是验收证据。所有条目初始为 `pending`；只有在官方启动器、真实战局、控制台输出或存档原文可回溯时，才可填写 `verified` 或 `failed`。不得用隐藏预加载、静态测试或预填数据替代人工证据。

结构检查：`python tools/validate_manual_acceptance.py --log docs/release/manual-acceptance-log.md`；只有全部真实证据填写完毕后，才运行附加 `--require-complete`，该选项不会把 `pending` 自动转换为通过。

## 基本信息

| 项目 | 记录 |
| --- | --- |
| 验收人 | pending |
| 开始时间 | pending |
| 游戏版本 | `1.13.11 (Matcha)` |
| Build ID | `24799966` |
| Mod 版本/工作树 | pending |
| 用户数据目录 | pending |

## 门槛一：五种 Playset 启动

每行应附 `run.json`、`debug.log` 挂载行和同一份 `launcher-evidence.json` 路径。JSON 由 `inspect_playsets.py --output` 生成并供校验器交叉核对；实际 DLC 集合仍以该轮日志为准。

| 配置 | 预期 DLC | 实际 DLC | Mod 挂载 | 版本匹配 | 证据路径 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| none | 无 | pending | pending | pending | pending | pending |
| sphere | `dlc010_ep1` | pending | pending | pending | pending | pending |
| charters | `dlc013_mp1` | pending | pending | pending | pending | pending |
| wave | `dlc018_ep2` | pending | pending | pending | pending | pending |
| all | `dlc010_ep1`, `dlc013_mp1`, `dlc018_ep2` | pending | pending | pending | pending | pending |

## 门槛二：十国 1836 战局

每行至少记录选国、进入日期、开局 Journal 清单、首月事件、截图或日志路径。MGL 是运行时标签；内容目录中的逻辑名仍为 MNG。

| 国家 | 运行时 TAG | 进入 1836 | Journal/事件核对 | 附加动作 | 证据路径 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| SHU | SHU | pending | pending | — | pending | pending |
| JHG | JHG | pending | pending | — | pending | pending |
| DMG | DMG | pending | pending | — | pending | pending |
| NQG | NQG | pending | pending | — | pending | pending |
| OIR | OIR | pending | pending | — | pending | pending |
| MNG | MGL | pending | pending | — | pending | pending |
| TIB | TIB | pending | pending | — | pending | pending |
| KOR | KOR | pending | pending | — | pending | pending |
| LAN | LAN | pending | pending | — | pending | pending |
| NMG | NMG | pending | pending | 自治谈判接受/拒绝两支 | pending | pending |

## 门槛三：原生 `scripted_tests`

结果必须来自进入战局后实际执行的套件；`tests.txt` 只有 `Tests:` 标题时记为 `empty`，不能记为通过。

| 套件 | 战局配置/种子 | 游戏日期 | PASS 结果 | 输出路径 | 状态 |
| --- | --- | --- | --- | --- | --- |
| `ywc_startup_smoke.txt` | pending | pending | pending | pending | pending |
| `ywc_longrun_invariants.txt` | pending | pending | pending | pending | pending |

## 门槛四：观察矩阵

每个 run 必须有 1846、1866、1900 三个检查点，每个检查点包含十国、人口、市场、排名、战争、属邦和错误计数。填写后运行：

```powershell
python tools/summarize_observation.py --input artifacts/observe --output artifacts/observe/matrix-summary.json
python tools/check_release.py --matrix artifacts/observe/matrix-summary.json --mod-root yongchang_world
```

| 配置 | 种子 | run 目录 | checkpoints.json | 异常分类 | 状态 |
| --- | ---: | --- | --- | --- | --- |
| none | 11 | pending | pending | pending | pending |
| none | 23 | pending | pending | pending | pending |
| none | 47 | pending | pending | pending | pending |
| sphere | 11 | pending | pending | pending | pending |
| sphere | 23 | pending | pending | pending | pending |
| sphere | 47 | pending | pending | pending | pending |
| charters | 11 | pending | pending | pending | pending |
| charters | 23 | pending | pending | pending | pending |
| charters | 47 | pending | pending | pending | pending |
| wave | 11 | pending | pending | pending | pending |
| wave | 23 | pending | pending | pending | pending |
| wave | 47 | pending | pending | pending | pending |
| all | 11 | pending | pending | pending | pending |
| all | 23 | pending | pending | pending | pending |
| all | 47 | pending | pending | pending | pending |

## 最终复核

- [ ] 五种 Playset 的实际 DLC 挂载与意图逐行核对。
- [ ] 十国 1836 Journal、事件和边界证据齐全。
- [ ] NMG 自治谈判接受/拒绝两支均有证据。
- [ ] 两个原生 scripted-test 套件均得到非空 PASS 结果。
- [ ] 15 个观察 run 均为 `observed_to_checkpoint`，汇总后为 `verified`。
- [ ] `python tools/check_release.py ...` exit 0。
- [ ] 异常分类与变更记录已同步。
