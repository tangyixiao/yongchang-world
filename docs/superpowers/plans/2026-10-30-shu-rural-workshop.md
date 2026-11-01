# 大顺《田亩旁的机房》实施计划

> **For agentic workers:** use superpowers:subagent-driven-development task by task. Source authors own only three country inputs; root owns binding, generation, adapter and Git. Execute the literal and genuine-history gates before dispatching production.

**Goal:** 实现已批准 `v03_shu_rural_workshop`，用真实原州工农业岗位、职业生活水平、土地制度、市场粮价和城市中心规模，形成乡村加工、城市集中、保护旧作三条完整政策和明确有限出口。

**Architecture:** 在接受基底 `39187884b0084fa29e9194507ee59fd1f26a2927` 的旧五卡后追加第六卡，采用严格SHUv3原生投递。新事实只在本卡局部world扩展，不修改共享Strict或旧卡；一次捕获实际州对象，全部职责留在该对象。两笔真实国家行政支出与六个当前履责月份形成可审查结果，不把行政费称为私人投资或工厂贷款。

**Tech Stack:** JSON国别源、Clausewitz scripted effects/triggers、Python严格解释器与unittest、已有v0.3生成器和source-bound adapter。

**Spec:** `docs/superpowers/specs/2026-10-14-v0.3-十国长线内容目录.md` 共同规则与3.1。全目录与自主接续已获用户批准，本文件明确实现切片；优先于scratch ZCode草案。原生事实审计、独立设计复核与root七项裁决用于确定本文件，不将草案代理指标追认为实机事实。

## Global Constraints

- 8个独立本国事件 `ywc_shu.1110..1117`，仅占本卡已登记1110..1119范围，1118/19留空；不挪用未分配1130。两JE各4事件，候选48..55/served6/总12JE；旧五卡完整JSON、42events/10JE/47sender/1directadd及两手写helper既有Git字节前缀与AST保留；作者FileWrite的换行变化由root按格式裁决机械规范化，不声称原物理checkout哈希未变。
- 不启动游戏、Steam、启动器、游戏UI；不合并、发布、关机或改其他项目。没有引擎、存档、自然战局、AI、性能、平衡或完整v0.3声明。
- 源作者仅追加 `data/content/v03/countries/shu.json` 新arc、`ywc_v03_shu_effects.txt` 和 `ywc_v03_shu_triggers.txt` 新helper，写本人scratch报告。新arc整个 `inline_delivery_adapter` 键省略；不手写哈希、generated、registry、manifest、adapter、tests或Git。
- 命名统一 `ywc_shu_workshop_*`；queue=`ywc_shu_workshop_pending_event`，原州=`ywc_shu_workshop_pilot`，本线收据=`ywc_shu_workshop_last_event`，stage=1110..1117/phase1或2。原生immediate恰三句：mark_major、共享 `ywc_v03_shu_event_dispatch=<实际事件号>`、本线收据=<实际事件号>，不用ordinal或第四句。
- mode1/2/3与target1为三完整；有限显式mode3/target2。结果固定1完整、2有限、3诚实受挫、4退出，mode与outcome分开。所有完整路线在当下事实满足时无旧史可行。
- 不自动改法律、集团、建筑、就业、PM、主权；不虚构私人资本、定向投资或迁居数量。JHG/KOR/LAN是可连接对象，本片无新外国投入，不制造虚假同意或强制外交前置。

## Review Focus

1. 同region另一个自有州、外国分州、被替换/消失的原对象不能拼接岗位或接替原州；StateRef不是1..4地区编号。
2. 缺粮价不能落零；国家市场价不能称本州价，州平均SoL不能替代实际工人/农户SoL；旧业须真peasants、实际homePM，不能用office代替。
3. 部分旧字段在未结案时可赚取，旧“已付”旗也可能由免付程序产生；只能消费实际完成的联合历史，真会议实付和合法waiver分开证明。
4. 已付recount和有限重签仍须六个新月，不能被全局NOTpaid跳过；晚已付当前丢条件保留真实历史供诚实受挫，恢复使缓存受挫无效。
5. 责任快照按阶段赚取，完整/有限申请、关闭、免费推进检查全部已赚身份和两笔正额付款；签前不能要求未来受理/复核付款。所有等待/退出也有精确origin guard。

## 一、事实与政策的冻结值

开线只需已初始化、有容量、有任一当前自有STATE；首先在真实state scope捕获一次对象到ROOT国别变量，不要求四旧地区、年份、旧史、工业或外国。此后不静默换点。原州所有岗位均为 `is_employed=yes` 的实际POP、其实际workplace；各岗位无输入短缺、occupancy满足下列值。更换持有人或换成同region别州不能补位。

通用当前条件：原州仍自有、和平、非default/破产、bureaucracy>=0、net_fixed_income>=0。完整政策的集团条件必须由同一个当前集团同时满足类型、在政府、clout>=.10、approval>=0；三完整并非必须变法，读取已存在的法和就业即可。

| 策略 | 原州真实生产与国情 | 市场/生活/行政与政治责任 |
|---|---|---|
| mode1乡村加工,target1 | tenant_farmers/homesteading/commercialized_agriculture之一；rice/wheat/millet农场的farmers或laborers，另有food_industry或textile_mill的laborers/machinists，两类实际workplace各occupancy>=.5 | 两类目标POP各SoL>=10；本国mg:grain market_goods_pricier<=.25；原州market_access>=.5；当前office就业>=.5；legitimacy>=20；同RuralFolk或Landowners合格集团 |
| mode2城市集中,target1 | food_industry/textile_mill/tooling_workshop实际laborers/machinists/engineers，occupancy>=.5；同州urban_center真实level>=3，不强制特定土地法 | 工业目标POP SoL>=12；国家grain pricier<=.40；原州market_access>=.75；office>=.5；legitimacy>=25；同Industrialists或Intelligentsia合格集团 |
| mode3保护旧作,target1 | serfdom或tenant_farmers；真实peasants在subsistence_farm或subsistence_rice_farm就业，occupancy>=.5且该workplace当前启用与自身buildingtype对应的home_workshops PM | 目标peasants SoL>=8；国家grain pricier<=.50；market_access>=.30；office>=.5；legitimacy>=20；同Landowners或RuralFolk合格集团。保守路线是完整政策，不自动记有限 |
| mode3本地准备,target2 | 任意政体/土地法，无工业/学校/特殊IG/旧史要求；实际farmers/laborers/peasants在上述真实农业或自给农业workplace就业，occupancy>=.25、无短缺 | 目标农业POP SoL>=5；国家grain pricier<=.75；原州office>=.25、market_access>=.25、legitimacy>=15；其余通用财政和平条件相同 |

office均须实际bureaucrats→government_administration，不能只看楼或从外州借。粮价原生命令为COUNTRY `market_capital.market={mg:grain={market_goods_pricier<=X}}`，X保持本体原生相对价格刻度；不是英镑绝对价或州本地价。城市中心level只称规模，不称城市化率/迁居人数。PM与canonical singular building键使用31项安装原文审计的确切名称；不实现猜测的urbanization或state_goods_pricier。

## 二、费用、角色和两个真实旧合同

B开线一次记录yearly_gross_income/52，clamp100..1e9。1111行政登记和1115调查复核各独立实扣：三完整各B，有限各.5B。显示、effect外limit和helper重核同一当前资格、原州、准确cash与价格；先扣后paid=1+positive paid_amount。不得透支、退款、补差、重复扣款、将旧免付当新付款或将钱称进入工厂。已付recount/改签保留真实原金额，免费推进没有新cash门。

1111实付后建立handler的kind/mode/target/实际pilot快照；1112建立witness_source/mode/target/pilot，1113建立sign三元组，1114建立accept_kind/mode/target/pilot。1115实付建立review责任快照。完整新witness需同原州office>=.8；明确沿用下列真实已结案A/B可用office>=.5，有限专属witness只需.25。三完整基础office=.5，所以真实复用差异不会被另一个更严全局门槛抵消。

只采用两项旧来源，不使用草案signed-only公议或错误settled键：

**A财政地方核账权：** 实际执行1000..1009的shared路径得到generic fiscal outcome2、started+settled、fiscal_outcome_provincial_share、register_resolved、first_audit、second_audit、settlement_review_mature、local_audit_right、settlement_mode2，非withdrawn_breach。旧商人无advance_unpaid，且真正拒绝advance且无advance，或真实consultation+advance+principal>0+advance_repaid；不清任何仍承担的旧军事/借款责任。不发明fiscal_paid_amount，旧second_audit_installment_paid可能是免付程序记录，不能称实付。

**B省共议成文分担：** 实际旧province generic outcome2+business prov_outcome2/mode2、started+settled、charter_ready、share_terms、terms_pilot与旧prov_pilot有效且相同、review_mature/streak>=6、非interrupted/withdrawn。relief_local是实际自筹承诺，或relief_paid与正captured prov_fee_amount对应真实国库支出，文本分开；会议真实paid与正captured prov_meeting_fee，或真正waived且完整A同区域来源，矛盾同时paid/waived拒绝。不发明旧meeting_paid_amount，不用裸OR取得许可。

A/B都保存旧1..4地区码。必须在**新exactpilot内部**核state_region对应旧码与新原州的当前office，不能直接将旧整数与StateRef比较，不能把区域权利声称为旧特定fragment身份，也不能借区域内别州岗位。1112显式采用A/B后，1113签署、1114受理、观察、1115费用、1116申请和1117关闭均消费同一联合历史与新pilot当前岗位；无史可选真实newwitness。采用的旧源丢失，未付观察中断；晚实付阻完整，历史身份保留供诚实受挫。新有限重签须明确换本地witness并清旧源依赖。source reader不调用旧open/JE/queue/pilot业务条件。

旧产者联合在真实native故事中先证明全部可保留字段；若某草案字段实际被producer清除，先向root报告真实输出及最小等价证明，不能注入字段或悄悄降低合约。

## 三、两个JE、八个独立节点

JE1=`ywc_je_v03_shu_workshop_ground`：1110..13，目标为真实签署新劳作责任；JE2=`ywc_je_v03_shu_workshop_yields`：1114..17，目标为实际履责后完整/有限/受挫，withdraw只fail。目标与退出互斥。JE1签字后真实phase2/stage1114/pending1114，JE2 native possible只接签字，不再owner/capacity/newslot；隐藏新addJE为零。

| 节点 | 独立行动 |
|---|---|
|1110《谁的地里建机房》| rural_processing/urban_concentration/protect_home_workshops三完整与limited_local_preparation显式有限；纯pre-choice当前条件不要求未来handler/见证 |
|1111《登记费不能当厂本》| pay_admin实际扣B或.5B，写真实handler责任；只称国家登记支出 |
|1112《谁能为两种劳作作证》| new_witness或真实reuse_fiscal_witness/reuse_province_witness；有限local_witness；按当前实际岗位与联合旧史建立见证，不赠资本 |
|1113《把土地与工钱写进责任》| sign_responsibility核已赚handler+witness及当前经济事实、登记实付，再签字并真实交接；不读未来accept/review付款 |
|1114《农户、机工与旧作户》| 按mode真实读取对应生产者与粮价/城市/PM，record_rural_duties/record_urban_duties/record_home_duties/record_local_duties，建立accept责任并在1115启动观察 |
|1115《调查员第二次回来》| 六个真实新月成熟后pay_survey实扣第二费进1116；中断后restart_review，明确narrow_and_recount重签全部角色/三元组+mode3target2；已付重数成熟后有真实advance_paid_review免费选项 |
|1116《账面之外仍有人上工》| request_full/request_limited/request_setback以当前事实+全部历史身份+两费+六个月提出；recount回1115六fresh，保留实付与原州 |
|1117《留下的是岗位还是请愿》| close_full/limited/setback再核当前，写标准outcome并只释放本线一次；recount仍回1115，wait保留终局阶段 |

每节点有精确at_N等待和退出，显示与执行同guard：open/正确phase/正确JE/实际stage/本线actualID收据/ownpending缺或本N。缺失/零/错收据、旧phase、过期按钮包括withdraw/wait不得改钱、业务、他线queue或reservation。

## 四、观察、身份与终态

1114真实受理才在stage1115创建running/streak0和days1门闩。每个真实日历月只加一次，创建日与同月重调不加，5不成熟/6成熟即停running。当前经济岗位、POPSoL、土地法、实际PM、grainprice、citylevel、同IG、原州、财务、handler/witness/accept和已采用旧源都持续重核；失效清streak/mature/running，标interrupted，恢复后须明确restart六fresh。

未付成熟1115继续监控当前失效；已付recount/有限重签回1115的running也必须真实计六个月，不能全局NOTpaid禁用。晚1116/17两费真实已付者保留赚得成熟与历史，但当前失效阻full/finite、允许历史完整的诚实setback；恢复使缓存setback不可请求/关闭。monthly不回写1116/17到1115。

full/finite申请、关闭和免费advance必须有两笔真实paid=1及正金额、精确mode/target、所有已经赚取handler/witness/sign/accept/review的mode-target-pilot/kind身份和六fresh证明。纯历史身份与当前能力分开，不能为了honestsetback要求丢失的当前岗位；也不能把缺身份当真实已履责。有限重签一次性写mode3/target2及全部新local角色、清旧来源/旧request/mature/streak，保留金额，六个新月后才可继续。release只调用本arc真实release一次，不手清global witness/reservation/其他queue，不退旧费、不免旧债。

## 五、按门实施与验证

### Task1: 严格事实与对象身份

**Files:** 新`tests/shu_rural_runtime.py`、`test_v03_shu_rural_runtime.py`；新`shu_rural_state_runtime.py`及对应test。不改旧runtime。

- [ ] 保留已实际演示的旧RED：POPSoL/activePM unknown、missinggrain默认0、异常good_scope泄漏、多goods ANY。新wrapper只读取显式finite事实，True/False/exception恢复scope、多goods AND、country隔离。
- [ ] 修复自有fixture错误后的root实际23方法+旧public13方法绿色记录保留；不将作者文字保证当执行。
- [ ] StateRef先实际baseline RED，再证明ROOT保存PREV、精确对象读取/比较、换主/消失/同region另州/foreignsplit不能替换、未知对象类型拒绝、scope在异常后恢复，最后与RuralWorld组合回归。此门不绿不派生产。

### Task2: 真实旧产者与新业务RED

**Files:** 新`tests/test_v03_shu_rural_workshop.py`、`test_v03_shu_rural_cross_era.py`，仅供新卡使用的fixture允许放测试模块。

- [ ] 原生赚A、B会议实付、B合法waiver及旧保守/受挫/退出/未参与，记录真实Treasury差额与保留字段，无positive flags注入。
- [ ] 新arc不存在先RED；写三full+finite、两即时精确费、真实岗位/SoL/PM/粮价/城市与同IG当前变化、StateRef不借州、stage收据缓存、6月/recount/finite身份、诚实受挫恢复/仅自身释放的真实业务用例。
- [ ] 新source作者与测试作者独立所有权；测试不自定义业务ready/helper，不忽略未知命令。

### Task3: 源实现与SHUv3接线

**Files:** 三国别源，`tools/v03_inline_delivery_adapter.py`与新`test_v03_shu_rural_adapter.py`由不同作者维护。

- [ ] 本机live已验证ZCode StartPlan GLM-5.3-Flash原生goal+社区重试有界写三source和诚实not_run报告；新metadata整键省略，旧5与两份原Git前缀/AST精确保留，换行差异单独列证。
- [ ] Adapter先隔离RED/合法合成sender GREEN；严格只接受注册第六slug、8源sender、4/4phase、actualID三句receipt、候选48..55/served6，未知/重哈希畸形拒绝。旧5输入独立renderer与接受版完整相等；完整新catalog允许明确coordinator新增清理范围，不要求旧协调块全bytes不变。
- [ ] 作者终端后root检查括号不负/最终0、完整helper唯一、无隐藏newaddJE；从实际JE/goal/exit/branch绑定metadata和pins，生成/check/catalog，再放行真实业务/跨期/adapter。

### Task4: Scoped fix loops and final delivery

- [ ] 每轮保留原RED、实际覆盖命令、源码前后哈希与独立ADDRESSED/NOT判定；前三轮原作者、四五轮fresh更强实现者，最多五轮，minor公开登记。控制器不写生产行为修复。
- [ ] 真实8ACK与错误收据、三线两native顺序首九次每线三次/至少90日和终态、旧5与其他八国完整renderer与OIR原拒绝边界、旧财政军费海关省朝公议/生成/owner精确变量scope回归。
- [ ] 全部修改冻结后选定相关模块一次各运行、去重输入SHA前后无漂移，另执行总静态；全套/选择集/多批汇总区分。开发记录列机制、实测、已知minor与未做引擎验收。
- [ ] 精确暂存任务文件，排除其他未提交内容，提交推送并建立挂到PR97的草稿PR；不合并、发布或把国别定义数当完整配额。
