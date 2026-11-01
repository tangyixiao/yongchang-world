# KOR《经筵之外的议论》Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task; follow root's separately assigned source/test ownership and source gates. Steps use checkbox syntax for tracking. This document authorizes no production or Git mutation by its planning author.

**Goal:** 将批准目录的王室廷议、地方代表、保守申诉三项完整政策落实为有真实职业承办、反对答复和当前合法渠道的8事件/2JE，并保留任何政体可执行的明确有限出口。

**Architecture:** 第五条实际KOR arc，依次经过受理费、职业见证、王室/地方责任签署、实际答复渠道、连续观察和当前裁决。所有岗位及旧省税联合合同绑定开线时一次保存的原始自有StateRef；正向旧合同提供可追溯且持续重核的承办/价格差异，历史成熟付款证据与当前可执行资格分开。

**Tech Stack:** authored country JSON、Clausewitz scripted triggers/effects、原生typed StateRef、KorRevenueWorld/PartnerWorld/LanPublicWorld、strict literal movement扩展、Python unittest、root-owned inline adapter/generator。

**Spec:** [批准目录3.3与共同规则](../specs/2026-10-14-v0.3-十国长线内容目录.md)；[草稿纠偏裁决](../../../.scratch/kor-court-public-design-ruling.md)。`.scratch/kor-court-public-design.md`仅为未接受输入；冲突以本计划及root后续明确裁决为准。

## Global Constraints

- 基线B HEAD `ce03a2f8a6f328788475d5692ec1eed1749095c4`，含PR93/8222计数初始化及旧军事2goal+2goalsha修复；保留已有四arc完整JSON、两个手写helper原始字节前缀、39candidate/served1..4/8JE/5direct_add以及其他国家输出。新卡append-only；workshops尚未实现，不计完成，不占本次candidate；将来另排48..55。
- 本卡 `v03_kor_court_public`、middle、`ywc_kor.1120`..`.1127`恰8事件，目录1128/1129不使用；新增candidate40..47、served5、总10JE。JE1=`ywc_je_v03_kor_court_public_deliberation`(1120..23)，JE2=`ywc_je_v03_kor_court_public_review`(1124..27)。不增加直接add数量，第二JE由真实签署及原生possible承接。
- 明确 `mode=1/2/3` 均可 `target=1 → outcome1`；独立 `finite_petition` 选项设mode3/target2，任何现行政体/税法可用。outcome1完整、2有限、3诚实受挫、4撤回，不能把mode3直接当有限或失败。
- 新业务前缀 `ywc_kor_public_`，本线唯一pending=`ywc_kor_public_pending_event`，phase1/2，stage1120..1127。不得复用revenue pilot、receipt、费用、运行标记，不借任何旧active JE/queue判定历史成立。
- 只读当前法律/政府/IG/就业/动荡/运动事实；不自动改法、进政府、改变approval/clout、建组织、补岗位、给学校或港口、生成外国同意或外国款项。无强制年份、前线结局、工业化、学校、外国合作入口。
- 新生产作者仅country JSON和两个authored helper及本人report；root拥有metadata、adapter、generated、Git与静态门。新arc省略整个inline_delivery_adapter键，root按实际源绑定；不能填空对象冒充metadata。

## Review Focus

1. 首个自有州只捕获一次；多个州、后来换主/消失、同区域外方分州和他州健康岗位不能换掉原StateRef（Task1/3）。
2. 各阶段只读之前实际赚取的证据；见证不依赖未来签名/受理，1123必须建立真实1124请求，不能删除队列后等未来自己出现（Task3）。
3. 同一IG满足type/government/clout/approval；替代支持者用OR。实际反对意见与真实受压运动分别记录，不把disapproval称地下组织（Task1/3）。
4. 两笔实付与成熟证据不会因晚期战争消失，但所有完整/有限申请与关闭都因当前失效而拒绝，诚实受挫只在真实晚期丢失时可达（Task3/4）。
5. 缺/零mode、target、phase、stage、receipt、paid_amount以及缓存旧withdraw均无效果；paid recount有真实免费UI，并从零再数6月（Task3/4）。

## 1. 当前政策、职业与承办职责

下列数字是本卡实施选择，不声称安装本体已存在这些事件规则。所有完整路线还须原pilot owner=ROOT、turmoil<=.25、bureaucracy>=0、和平、net_fixed_income>=0、非default/declared_bankruptcy；同一支持IG须在政府、clout>=.10、approval>=0。

| mode / 选项 | 当前政治法律（全部逐项真实读取） | 同一支持IG的替代项 | 基本岗位与其他门槛 | 承办责任 |
|---|---|---|---|---|
| 1 `court_open` 廷议公开 | monarchy + appointed_bureaucrats；power为autocracy/oligarchy/technocracy之一；speech为censorship/right_of_assembly/protected_speech之一 | intelligentsia OR landowners | 原州在职bureaucrats→government_administration、occupancy>=.8、无shortage；legitimacy>=30 | handler1王室官署：公开的是朝廷审定奏议，不宣称取得自由结社或选举权 |
| 2 `local_delegates` 地方代表 | power为wealth_voting/census_voting/universal_suffrage之一；speech为right_of_assembly/protected_speech之一 | rural_folk OR industrialists | 同原州真实官署公务>=.5、legitimacy>=25 | handler2地方承办；新名册需要官署>=.8，有下述同pilot旧省税合同可沿用>=.5 |
| 3 `conservative_petition` 保守申诉，完整 | monarchy + power autocracy/oligarchy之一 + speech outlawed_dissent/censorship之一 | landowners OR devout | 同原州真实公务>=.5、authority>=50、legitimacy>=25 | handler3王室封存申诉：完整履行登记、转呈与答复职责，不宣称公开议会 |
| 显式 `finite_petition`，mode3/target2 | 任意当前regime/power/speech/tax；不要求特殊IG | 无 | 原州真实公务>=.25、bureaucracy>=0、legitimacy>=20、turmoil<=.40、和平与财政安全 | handler4有限官署登记，不声称政府认可公开结社 |

`office(x)`只可来自原pilot的`any_scope_pop { is_pop_type=bureaucrats is_employed=yes workplace ?= { is_building_type=building_government_administration occupancy>=x building_has_goods_shortage=no } }`。不得只查建筑占用率。通用岗位不加文化primary/acceptance限制。

1122职业见证选择及持续职责：mode1/2新见证kind1是原州实际academics→university，或bureaucrats/clerks→government_administration，occupancy>=.8无短缺；真实旧合办书院kind2可用当前同原州academics→university>=.5；旧官学kind3可用当前同原州bureaucrats/clerks→government_administration>=.5。kind2/3还须旧正向合同每次重核。mode3完整kind4为原州公务>=.5；有限kind5为原州公务>=.25。这保证保守完整不被强迫工业化或建大学。见证人与政策支持IG是不同职责，两者都要真实满足。

## 2. 两笔全国财政实付与真正旧合同

claim时捕获B=yearly_gross_income/52、clamp[100,1e9]一次；以后收入改变不重算。仅1121受理费和1125答复复核费，两个独立receipt记录paid=1与正数paid_amount：

| 当前目标/路线 | 1121 petition | 1125 review |
|---|---:|---:|
| full mode1，无下述旧书院合同 | B | B |
| full mode1，真实旧书院合同及当前原州承办仍有效 | B | .75B |
| full mode2，无下述旧省税合同 | 2B | 1.5B |
| full mode2，有同原pilot旧成文分税合同且当前仍有效 | B | B |
| full mode3 | .5B | .5B |
| 显式target2 | .5B | .5B |

两次费用均在UI、effect外guard和付款helper内核当前selected policy、原pilot、当前承办/见证（若该阶段已产生）、和平、财政、当前价格与gold_reserves。先真实扣国库，再写paid+正数amount；无实际扣款不能承认服务已发生。不能以价格不足走else有限，不能缺target视为2，不能给已付重算/追补/退款。尚未支付的账单读取当前旧合同；优惠失效只改变未付价格和当前职责，不追补历史实付。

### 旧书院联合证据（至少1122与1124/1126两处消费）

直接按B旧源的两个既存正向谓词 `ywc_kor_revenue_prior_school_coop` / `..._office` 的语义建立本线私有reader；可调用这两个不依赖revenue open/queue的已证明predicate，但禁止调用旧selected_current_ready作为settled历史入口。每项要求school started/settled，generic school outcome1或2，route1或2与对应coop_paid或office_paid、filing_fee_paid、old_invoice_paid、old_account_read_2=1、funding_decided、appointment_decided、six_months_complete、established、employer_confirmed=1及employer1/2一致、NOTwithdrawn、当前university/office及selected_employer_ready。还需`school_old_contracts_clear`重核既有债务：未参加是无欠账，不是正向合同。

不要虚构旧school_paid_amount；该旧源实际是按archive_fee/office_fee实扣后记对应paid字段。测试以原生1010付款路径和treasury差额证明真实支付。新线同时要求本卡原pilot当前见证岗位，旧country-wide岗位不能从另一州替代；coop还须原pilot真实university>=.8无短缺，office须原pilot真实官署>=.8无短缺，保留旧source自身较严门槛。因此上文见证局部.5不等于完整旧source可以整体降到.5；禁止测试只留.5却忽略旧.8。本线另使完整mode1的未付1125复核账B→.75B，提供实际可执行的第二节点差异。本线记录witness_kind、school_route_snapshot及mode/target/pilot；1124、观察期间、1126/1127继续核同一真实source与当前岗位。丢old_account_read_2、当前任用岗位或原route，沿用立即失效；可恢复后明确重启或重新签有限。若1122选新见证则不沿用school witness职责，1125实际取得school优惠仍记录并持续核其真实source；已付不追补。

### 旧省税联合证据（1121/1125两笔价格及1123/1126当前承办）

仅同原StateRef的实际完整成文分税：generic revenue started/settled、outcome1、业务outcome1、mode1、target1、NOTfinite_chosen/withdrawn；charter_paid与review_paid及两正数amount、review_mature、review_streak>=6、NOTinterrupted；charter_pilot/reviewer_pilot均等于revenue_pilot_state且等于public_pilot_state；charter_mode/target与旧当前mode/target一致。重读既存`revenue_both_snapshots_match`、`revenue_full_conditions`、`revenue_finance_safe`、`revenue_reviewer_current_duty`、pilot_owned；这些reader不要求旧arc仍open，也不要求旧JE/queue。

旧revenue_mode1_full当前基本官署仍>=.8，因此本合同**不**自称放宽所有旧公务到.5：本卡handler2沿用门槛为.5，但旧合同自身当前更严岗位必须照实满足。可比较无旧史的新承办者.8与已有旧史时本卡局部handler门槛；若全合同仍要求.8，测试不可伪造整体.5可达收益。可执行的必选差异是1121的2B→B和1125的1.5B→B，以及持续读取原有分税与核账责任；不会用一个永远无法达到的优惠门槛充数。

military和ports旧线不作为本卡完整入口；其真实未付旧债仍由旧school reader按原规则处理。无历史、旧有限/撤回/受挫、省税其他完整mode均可从当前新承办或显式有限进入，不赠任何旧合同。

## 3. 真实反对与合法申诉渠道

1122逐类记录实际**非政府、clout>=.05、approval<0**的同一个IG：八个原生类型landowners/devout/armed_forces/intelligentsia/industrialists/rural_folk/petty_bourgeoisie/trade_unions分别0/1。0只表示这次真实查询未发现该类，不是替代world事实。1124真实答复时记录同组清单及channel；持续观察期间出现以前未记录的新反对类型、原答复渠道在当前法下不合法、支持集团退出或岗位失效，均中断；不改任何IG事实。现有不满集团不要求变满意才能完成：本卡承担的是让真实反对者有与所选制度一致的送达/答复渠道。

完整mode1答复channel1=`court_read_reply`：当前speech为censorship可由官署审定、进入王室记录；assembly/protected_speech允许同一答复公开留档；须handler1与职业见证。mode2 channel2=`local_open_reply`只在assembly/protected_speech与实际投票power下允许，须handler2。mode3完整channel3=`sealed_royal_reply`在其当前保守法律下由handler3封存接收/答复。有限channel4=`bounded_clerk_reply`是本卡内部个案登记，任何政体可用，不称自由结社或官民政治代表权。

另读取**已经存在的实际政治运动**：native`any_political_movement { is_being_suppressed=yes political_movement_radicalism>=.25 }`，同一个movement满足两条件。记录当前有无受压运动的类别事实并在1124/1126重读；这是受压事实，不等于“地下组织成立”。公开答复不得声称代表或解除该组织的镇压；有受压运动时另记`sealed_case_reply`承办条款（与mode1/2的公开IG答复并存，由原州公务>=.5；finite>=.25），1124须显式`record_sealed_case_reply`选项先登记此条款再完成其本路线答复；无该运动则该额外选项不可点。观察中原来不存在而新出现该类别须明确restart并重新登记当前条款后重数6。只记录existential类别，不声称持有任何特定movement对象身份或所有成员授权。

**边界裁决：**本卡不创建/镇压/解散政治运动，不将上述case答复说成运动已获合法结社。安装源证明的is_being_suppressed也不能自动译为地下。若root要求目录文字必须落为“实际地下组织网络”机制，此项仍是NEEDS_CONTEXT：需补其精确原生身份/合法性/效果证据与strict primitive后再另裁，不能用IG不满或本卡flag代替；本计划采用当前合法/封存个案渠道与真实受压事实的保守实现选择，供root评审，不冒称地下玩法已完成。

## 4. 八事件与分阶段证据

每一事件均有`wait_at_N`/`withdraw_at_N`，UI和效果都用同一个精确`at_N`，等待重新排当前请求而不改变阶段；withdraw使用变量presence正确语法，绝不把`..._started=yes`当未定义trigger。

| stage / JE | 中文 / English | 实际动作与后续读取 |
|---|---|---|
|1120 / JE1|《经筵门外递来的奏议》 / The Memorial at the Lecture Door|`court_open`/`local_delegates`/`conservative_petition`/`finite_petition`选择真实policy；写mode/target，原pilot由claim已捕获，不再捕获；pending1121。无费。|
|1121 / JE1|《王室抄本与各道回执》 / Royal Copies and Provincial Receipts|`pay_petition`核当前handler与旧省税价、实付第一费，记录handler kind及mode/target/pilot；pending1122。没有付费，不得声明已经答复反对者。|
|1122 / JE1|《译学生、书院先生与在岗书吏》 / Translators, Scholars and Serving Clerks|`new_professional_witness`/`reuse_coop_witness`/`reuse_office_witness`/`conservative_clerk_witness`/`finite_clerk_witness`按真实岗位选见证；捕获witness三元组、school route和当前反对清单/受压类别；pending1123。|
|1123 / JE1|《谁负责把反对意见送到御前》 / Who Must Carry the Objections|`sign_responsibility`仅核已赚handler/witness、第一费与当前law/IG/owner；写signature三元组+signed，phase2/stage1124/pending1124。JE1只有signed且未withdrawn才完成；JE2激活不看容量或仍有州。|
|1124 / JE2|《公开的答复，封存的来函》 / The Public Answer and the Sealed Letter|必要时先`record_sealed_case_reply`；再选本路线`court_read_reply`/`local_open_reply`/`sealed_royal_reply`/`bounded_clerk_reply`，重核当前见证旧source、反对清单与法定公开边界；记录accept三元组/channel/当前反对答复，真正start_review，stage/pending1125。|
|1125 / JE2|《六次月报之后的答复账》 / The Reply Account After Six Reports|六次当前有效月报后`pay_review`实际付第二费→1126；已实付后另有`advance_paid_review`，positiveamount+mature+current，无cash门且不再扣；`restart_review`明确刷新当前反对答复/受压条款、从0重数；`narrow_and_resign`明确mode3/target2新签有限、重写全部职责快照及channel4并重数6；等待可达。|
|1126 / JE2|《名单还在，承办人是否仍在》 / The Names Remain; Do the Stewards|重核原pilot、职业witness source、旧省税条款、当前反对及channel：`request_full`/`request_finite`或真正paid+mature当前失效的`request_setback`写请求→1127；`recount`清请求/成熟再回1125、保实付，重数6。|
|1127 / JE2|《经筵以后，谁必须作答》 / Who Must Answer After the Lecture|`close_full`/`close_finite`/`close_setback`再次核对应request、当前资格及历史证据，只产生唯一1/2/3；`recount`或withdraw4均可；不授予法律、组织、approval、建筑或税权。|

pre-sign staged predicate只要求handler/witness已产生；1123不得要求自己才写的signature或1124才写的accept。1124要求签名但不要求未来accept；1125以后才要求全部三元组匹配。handler/witness/sign/accept全部含mode,target,pilot（pilot为typedStateRef）；三元组不能跨mode或target偷渡。

## 5. 时钟、历史证据、late current与幂等

- 只在phase2/stage1125且running时计观察；1124创建即streak0，days1的ticked gate，创建日/同日多pulse不加，真实月进一次，5不成熟6成熟后停running。合法source不得在nativeimmediate之外调用clock加月。
- 运行期间任何当前selected law/IG、owner/availability、岗位、旧source、channel、反对清单新增、受压类别新增、war/default/bankruptcy/负收入/低legitimacy失效，清streak/mature/running并标interrupted；恢复不自动续，合法明确restart从0。restart允许在otherwise-valid current事实下刷新反对记录，不能要求先匹配失效旧反对快照而死锁。
- 1125实际付款后1126/27不运行观察、不改stage/pending、不清历史mature/paid。`historical_completion`只证明真实六次成熟+两费；`current_execution`单独包括当前和平/财政/政策/原pilot/岗位/source/channel/opposition。
- full申请与close要求target1及完整current_execution；finite申请与close要求显式target2及有限current_execution。战争、破产、失州、当前source或岗位损失都必须在1126就拒完整/有限申请；不得等1127才拒。`request_setback`和`close_setback`只要求真实paid+mature历史、快照身份未伪造且当前对应execution已失效；恢复后缓存受挫按钮无效。已失州仍可wait、withdraw；有历史证据时可honestsetback，不要求先恢复当前owner才能承认失州。
- late recount/finite重签保留已付金额，清request/streak/mature、reset tick gate，建立真实1125请求；第二六个月后免费advance可达。finite重签明确重签mode3/target2、handler4/witness5/channel4与所有快照，不能悄悄降低旧full duties后沿用成熟。
- release一次：只有尚未settled的本线关闭才写generic outcome/settled、active/visible各减1并clamp，清本线pending；重复close/helper无效果。不得手清generated reservation/live witness，任何他线queue、已付旧债或旧合同。

## 6. claim与投递ABI

JE1入口只有KOR/initialized、notstarted/notsettled、capacity(active<3,visible<6)、至少一个当前自有州；无虚构`kor_v03_unsettled`。首个州在**claim**一次捕获：同一`every_scope_state`的limit同时要求owner=ROOT和`NOT exists scope:ywc_kor_public_first_pilot`再save_scope_as；迭代后保存变量`public_pilot_state`。不得无guard遍历覆盖成最后一个州；重复claim/重新显示不重捕。state对象换主/消失后不以region或另一个州重选。

新card沿用KOR native v2，immediate冻结恰2节点：`ywc_v03_mark_major_delivered=yes`，set `ywc_v03_kor_v03_kor_court_public_last_event=I`，I为序号1..8，对应实际event1120..1127。没有共享dispatch第三节点、额外ACK标记或native addJE；SHU v3的actualN三节点ABI不适用于KOR。旧39candidate与其既有1..8receipt/mark-only/notice例外保持。root必须在metadata、candidate、postproof及ACK所有层注册本卡receipt与精确序号，不能只放宽validator regex。

所有`at_N`须presence+精确phase/正确activeJE/stage=N、本线receipt=I（I=N-1119）、mode/target合法（1120选择前例外）、ownpending缺席或实际eventN、open/notsettled。全选项包括wait/withdraw及免费advance都带该精确阶段外内双guard。source真实1123handoff和所有late返回都建立下一请求；不得测试补queue进度。阶段恢复只重排当前本线请求，不能每月覆盖晚期stage或清其他queue。

## 7. 文件职责与分任务RED→GREEN

### Task1：先证明所需literal primitive，再开业务作者

**Files:** Create `tests/kor_public_runtime.py`、`tests/test_v03_kor_public_runtime.py`；现有KorRevenueWorld/PartnerWorld/Strict保持不变。本任务只扩展当前事实，不实现业务helper。

**Interface:** `KorPublicWorld(KorRevenueWorld)`，构造时注册完整KOR/CHI等country；继承真实KOR inline source、StateRef、Gregorian月份、同州pop/workplace、turmoil。新增country `any_political_movement`迭代，movement-scope的`is_being_suppressed=yes/no`与`political_movement_radicalism`有限数值比较；局部strict current IG验证不允许缺政府/clout/approval默认为0。未知/malformed/缺事实/NaN/错误scope拒绝；true/false/exception都恢复movement及原country/state/building/pop/stack。不模拟movement创建或世界政治。

- [ ] 写`test_existing_movement_suppression_and_radicalism_are_same_object`：两个movement各满足一半不得拼接；显式bool和finite0..1字段；缺事实/NaN/非法op拒绝；证明继承基线实际RED。
- [ ] 写`test_original_first_owned_state_is_saved_once`：按本计划带scope guard的真实Clausewitz迭代选第一个，第二州不得覆盖；换主、消失、foreign同region负控；现有StateRef能解释则不重复实现。
- [ ] 实现最小literal分支并跑`python -B -X utf8 -m unittest discover -s tests -p test_v03_kor_public_runtime.py -v`；只接受真实GREEN+独立RED日志，不以当前无movement等于primitive通过。

### Task2：独立业务/跨期测试先留真实RED

**Files:** Create `tests/test_v03_kor_court_public.py`、`tests/test_v03_kor_court_public_cross_era.py`，各自独占；reuse旧producer只读。

**Interface:** 业务导出`new_world(route='court'|'local'|'conservative',bare=False)`,`current_facts(...)`,`play(world,arc,N,key)`,`month(world,arc,count=1)`,`ready_for_review(world,route='court',limited=False,witness=None)`,`finish_review(world,arc,outcome=1)`；真实旧史复用`test_v03_kor_revenue_cross_era.py`的native_month/native_play/earn_school/revenue_open/revenue_sign/revenue_finish。不得把公共legacyfixture当赚取历史。

- [ ] 新arc当前不存在时先跑库存/入口方法，保存真实RED；不写假的ready/mode/receipt/fee/paid/outcome。
- [ ] 写三full+anyregimefinite、无学校无工业、同IG拆分/OR替代、政治权利非税法、原州职业就业、反对答复与运动literal、全部cachedwithdraw/phase/receipt负控。
- [ ] 跨期真实赚书院coop与office：1010 co_manage/court_office→1011 record_old_invoice→1012 share_review→1013 university_post/office_post→1014 keep_docket→1015 start_review→1016 establish(wait真实成熟)→1017 settle_established；无旧军债则不伪造任何外方同意，若有旧合同按真实country monthly支付完。
- [ ] 真实省税：1100 written_shares→1101 pay_charter→1102 settle_reviewer→1103 sign→实际6month→1104 pay_review/submit→1105 review_responsibility→1106 verify→1107 request_full；在**同world相同当前法律/税法/现金**下比较新mode2的两价2000/1500与旧史1000/1000。真实school与absence在同当前court事实下比较1122职业来源及1125复核750/1000，二次消费时移除earned receipt或失当前岗位/source后优惠消失。旧source原.8不被局部.5门槛绕过。真实旧finite、withdraw、absence至少各一例走新finite；school与revenue可在同world并存。

### Task3：三源追加、root绑定与业务可达闭环

**Files:** Append `data/content/v03/countries/kor.json`、`yongchang_world/common/scripted_triggers/ywc_v03_kor_triggers.txt`、`.../scripted_effects/ywc_v03_kor_effects.txt`。root单独维护 `tools/v03_inline_delivery_adapter.py`、相应adapter测试、metadata和六generated输出。

- [ ] 写pre-sign staged、claim-first、两价current付款、反对/channel reader、精确at_N与release helper，按1..6节闭环实施8event/2JE；每个当前trigger都有真实否定用例。
- [ ] 原生逐步1120..27全路径、不注任何签字/queue；1123签署前断言无sign/accept且可签，签后phase2+pending1124；失州/满capacity仍JE2可达并能退出。
- [ ] root保存旧4arc语义/两rawprefixhash，绑定新8branches/2phase/candidate40..47/served5/10JE，验证dupdefs0、KORv2 nativeexact2（mark_major+own ordinal1..8）、无共享dispatch或新directadd；刷新actualpins，再生成/check/catalog。source writer必须terminal后测试作者才读/run，修复期间关gate。
- [ ] 确认完整三mode不同law/IG/handler/channel真实作用；不得只更换SHU文本且保留付款时钟。

### Task4：定向验收与独立审查

**Files:** 上述owned tests、root-owned `tests/test_v03_kor_court_public_adapter.py`及本人scratch evidence；公共说明另由root分配。

- [ ] 两费exact/below cash、war/default/bankruptcy、非法target0/missing/phase0/missing；receipt只接受正确ordinal1..8，缺席/0/另一ordinal/实际eventID1120..1127均拒绝，即使mark_major也不得ACK；旧stage全部按钮强制执行无效。
- [ ] 创建日、同日重复、5/6月；九类当前丢失中断；恢复不自动续；明确restart更新真实反对/受压记录，finite重签/1126及1127late recount都六fresh；两费paid0/amount0无免费advance、真实paid零cash可advance。
- [ ] latewar/default/失州/source/岗位丢失保历史6+paid，拒request_full/finite且能真实request/close_setback；恢复缓存setback拒；早期未成熟/未付不能受挫。
- [ ] exactlyonce release：另一真实arc仍占容量且有queue/reservation，重复close不靠clamp掩盖重复释放；不清他线或generated witness。
- [ ] 新court+旧school+military两种入场顺序fairness、90日冷却、首九各三、全部8ACK、receipt fault、foreign/notice兼容。记录适用模块逐项结果，不把分批定向总数写成freshwhole。
- [ ] 新源、baseline旧4、adapter、runtime、generator/catalog等相关门通过并独立审查；root仅在授权范围创建可评审checkpoint/PR，不在本计划任务自行merge/publish。

## 8. 已核原文与明确未决项

批准目录实际8/2、非必然历史及独立路径见目录25..35、77..87。安装本体 `common/laws/00_distribution_of_power.txt:5,240,344,745,886,1017`证明power键；`02_free_speech.txt:5,34,63,86`证明四项speech都属于同一lawgroup，禁止同时要求censorship+assembly，禁止捏造freedom_of_association法律。bureaucracy/governance键复用已证实际source。

`events/peoples_springtime.txt:720..730`实际同movement查询type/support/is_being_suppressed；`common/scripted_triggers/00_ai_triggers.txt:88..100`实际movement radicalism>=.25/.75；`00_scripted_triggers.txt:1112..1127`存在anymovement及is_revolutionary/is_insurrectionary。但这些均没有证明“地下组织”身份，创建movement虽有本体用例也不在本卡执行范围。最小literal任务只实现本卡真正消费的三原语，不泛化movement效果/API。

不存在需要作者自行猜测的费用/mode/target/阶段决策；尚未获得的是新movement literal的RED/GREEN证据和真实新增card运行结果，必须先做Task1/2。地下组织机制不被本计划伪装成已实现；root评审本合法/受压渠道选择后才发生产任务。整版v0.3、引擎/UI/存档/AI/平衡验收不在本计划已完成范围。
