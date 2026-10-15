# DMG 首卡 runtime review 修复记录

本轮针对 `review-runtime-cards.md` 的 DMG #3、#4、#6、#9 修复，并补正 JE1 goal 的 Clausewitz OR 语法。修复范围为 DMG 卡片、DMG 本国 effects/triggers、旧 DMG JE 的单一脉冲 guard、DMG modifiers/localizations，以及定向离线测试。

## 修复

- **#3 接纳与实际任职分离**：完全接纳门槛使用 `acceptance_status_5`；第 4 档仅为二等公民，不能表述为完全平等。政府任职检查把非主流文化、完整接纳、bureaucrat 人群、就业状态和同一 pop 的 workplace（政府行政）放在同一人群 scope 内，并检查该建筑 occupancy ≥ 0.8、无短缺。军事任职对应士兵/军官 pop、实际就业与 `building_barrack`（本机官方 `common/buildings/05_military.txt` 的真实键为单数）及相同 occupancy/短缺条件。法律资格、真实岗位和政治代表仍是不同事实。
- **#4 撤回即失信**：E1008 撤回选项立即调用 breach 收束，保留已经支付的费用，不再把撤回留给 E1009 覆盖。E1009 仍有无条件有限结局及失信退出，条件结局另由触发器与 close effect 双重约束，避免消费一次终局事件后悬空。
- **#6 地区契约落到本地能力**：三种申诉机制均由各自 effect 产生，均需一次收入比例付款（`yearly_gross_income / 52`，最低 100），并施加互斥的 24 月政治/行政 modifier。地区契约结果要求自有州、实际任职的非主流官僚、已支付的本地 rollout 费用，以及申诉机制、继承先例、公共语言三项相匹配；还要满足对应的 legitimacy、bureaucracy/net fixed income 或 authority 条件。后续触发器读取这三项选择及政治条件，终局 effect 再验证地区结局，事件选择本身不会写“已执行成功”。王权可选共同听证，不强制共和或选举法。
- **#9 关键选项有后续机制读取**：申诉机制影响地区契约可达性、地区订单匹配与有限期 modifier；继承先例和公共语言在审查效果中各生成互斥的 24 月 modifier，地区容量与订单检查再次读取其选择。modifier 体现有限权威、正当性或官僚行政代价/收益，不是永久万能奖励。英文与简体中文本地化均提供。
- **JE1 goal 语法**：增加解析并执行真实 goal 的测试，先复现旧 goal 在去除外层 JSON block 后解析成 4 个顶层项，无法构成合法 OR；修为 `OR = { ... }` 后，解析为单一 OR block，成功/失信两种终止标志各自可完成，无标志时不完成。
- **旧线衔接**：只在旧 `ywc_je_flavor_dmg_compact_1` 的 monthly pulse 加新首卡 started guard；初始化本身不会让旧 JE 停止。新结果映射为新 1→旧 c1 outcome 1，新 2/3→旧 outcome 2，新 4/5→旧 outcome 3；已有旧 outcome 不覆盖。release 内幂等打开旧 compact 2，且只在旧 JE 未活动、未 resolved、未 failed 时打开。

## 节奏与费用

6 个月是**条件连续满足的最低观察期**，中断即清计时器并需重新累计；不是十个事件的总交付截止。9 个月为 review 等待期。主线仍经共享 90 天门控，卡片没有绕过；队列等待不计为受阻。12 月提示仅由真实 route condition 不满足触发，36 月提供有限结局/撤回退出而不强制失败。事件链最短约 27 个月的说明保留。rollout 费用依本国快照的年度总收入除以 52、最低 100，并有已付标志防重复扣款；没有改成 GDP 或同额固定费。

## 离线验证和边界

- `python -m unittest tests.test_v03_dmg_content -v`：18/18 通过，覆盖真实脚本解析的 OR goal、费用重入、连续计时与中断重启、同一 pop/真实 workplace 条件、地区契约门槛与选择后读取、旧结果映射/幂等、失信收束及所有结局可退出。
- `python tools/build_v03_content.py --check`：catalog schema 未报错；命令因并行 SHU 生成文件与当前 catalog 不一致、以及 DMG/KOR 生成文件尚不存在而返回 stale/missing。未运行生成器；共享 pipeline 与生成产物由 controller 统一处理。
- 官方源核对为本机只读：接纳阈值 `common/acceptance_statuses/00_acceptance_statuses.txt`；单数 `building_barrack` 在 `common/buildings/05_military.txt`；同一 pop employment/workplace 语法见 `events/soi_events/00_lobbies_events_03.txt` 与 `events/brazil/brazilian_slavery.txt`。收入年值用于财政计算的依据见 `common/history/global/00_global.txt`。测试对官方安装路径采用存在才运行的条件检查，不把 `E:` 路径写成必需环境。
- 脚本谓词的离线测试注入 engine facts，用来确认条件组合和 scope 结构；它不是 Clausewitz 引擎、整场战役或存档兼容性测试。未启动 Steam、游戏、启动器或 UI。新任务结果对旧线路的承接已通过 PulseWorld 对本国 bridge 的映射/幂等执行验证，但真实旧存档加载仍未实机验证。
