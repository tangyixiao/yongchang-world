# 大明《印玺与议席》实施约束

2026-10-29 首轮真实测试裁决：旧生产者合同必须由本线直接读取，不能调用带市场试点业务依赖的market_prior helper；原文允许复用仅在无此依赖时适用。明确有限听证应有独立kind3的.25公务路径，1117明确缩小重算可真实重签为这种本地有限程序、更新全部责任快照并重新观察，保留实付不退款。真实已付复核账在重算后能无重复扣款继续。第二JE必须等1116条款真实签完才结束；1115预算说明不能替代1116。实际在野反对的出现应影响公共说明/连续性，支持集团与反对集团均读当前同IG事实。精确反例和本轮修复清单在`.scratch/crown-fix-round1-brief.md`；这些裁决优先于早先helper复用和未指定有限听证的歧义。

既有批准目录 `v03_dmg_representative_crown`，middle，10事件1110—1119、3日志。本计划是对 `.scratch/resume-20261029-dmg-crown-design.md` 的裁决；冲突时以本文件为准。基线9980153，school、market与三foundation卡、原始helper前缀全部保留。只追加本卡，不自动改法律、政府组成、土地、人口、主权、外国同意或外资，不复活人物，不加无关静态修正。

## 实际国情与政策差别

入口是当前自有吕宋、初始化与现有容量、未开始/未结案；不要求完成任何旧卡，不要求年份、工业化、战争或外国参与。1110实际选择试点。全部岗位限定同一个仍自有的原始吕宋试点；其他州或外国分州不能充数。

三种完整策略必须在执行、观察和终态持续核验当前事实：

- mode1立宪王权：当前monarchy，实际选举法（landed/wealth/census/universal之一）、完整官署在职公务占用>=.8、bureaucracy>=0、legitimacy>=25；同一个intelligentsia须在政府、clout>=.10、approval>=0。不得用旧章程替代当前选举法。
- mode2地方联合共和：当前presidential或parliamentary republic、universal_suffrage、官署公务>=.5、净收入>=0、legitimacy>=25；同一个rural_folk在政府、clout>=.10、approval>=0；本州有实际在职、完全接受且非主流文化公务人口。写协议不把君主国改成共和。
- mode3咨询王权：当前monarchy且autocracy/oligarchy、官署公务>=.5、authority>=50；landowners或armed_forces中同一组在政府、clout>=.10、approval>=0。三条完整策略不得共用一组ready条件。

明确target2有限咨询适用于任何现行政体，只需要本州真实在职公务/官署>=.25、bureaucracy>=0、legitimacy>=20、和平、财务安全；无需学校/军工/大学/选举/共和/伙伴。不能将缺席变量或值0当有限目标。完整的当前制度失效后可显式缩小重算，不自动升格或假称议会已成立。

只解释已有native事实，使用 `LanPublicWorld(Strict)` 已验证的同IG查询/在职/职权/人口/法律能力。新命令先找安装本体源码，不猜词，不stub业务ready/mode/fee/clock。

## 三日志与十事件责任

1. `ywc_je_v03_dmg_crown_representation`，1110—1113共4sender：1110《印玺与席位的次序 / The Seal and the Order of Seats》选三mode或明确有限；1111《任命簿的抄本 / Copies of the Appointment Roll》实际登记扣款；1112《谁能在税官面前申诉 / Who Can Appeal Before the Tax Officer》沿用真实旧地契申诉或用当前.5公务新听证；1113《任命落款的两只手 / Two Hands Beneath the Appointment》检查当前策略/有限与已付/听证快照，签任命责任并交接第二JE。
2. `ywc_je_v03_dmg_crown_budget`，1114—1116共3sender：1114《哪本预算负担新席 / Which Budget Funds the Seats》实际分摊；1115《反对者也有一页账 / A Ledger Page for the Opposition》核验当前在任支持集团与反对集团（完整依各mode，有限只需本地事实），写公共说明/有限说明；1116《让下一届接着记账 / Let the Next Session Keep the Accounts》核验真实paid/责任及当前资格并交接第三JE，启动连续观察。
3. `ywc_je_v03_dmg_crown_continuity`，1117—1119共3sender：1117《六个月后的官印 / The Seal After Six Months》真正连续六次monthly后才可缴复核账；中断时能明确restart/缩小/退出；1118《缺席的席位与到场的人 / Empty Seats and Those Present》根据当前条件请求完整1/有限2/诚实受挫3；1119《下一届不能重收的账 / A Bill the Next Session Cannot Collect Twice》即时复核同一目标/试点/当前事实后结算。两后段均有明确recount返回1117，不能由月度tracker覆写阶段/队列。

JE2与JE3的handoff/possible只核本线先前真实交接，不再要求当前自有州或新容量。一个arc始终只占一个active/visible，任一节点失州仍可投递等待/退出。每个事件都须有真实当前stage/JE/receipt限定的defer或退出；不是always无条件执行旧按钮。三JE的goal/fail互斥，退出4不完成目标。

## 预算、旧事实与两处真实跨期差异

B在claim时按yearly_gross_income/52捕获，最低100，之后不随弹窗重算。三个扣款节点：登记1111按mode1=B、mode2=B、mode3=.5B；分摊1114按mode1=B、mode2=1.5B、mode3=.5B；复核1117按mode1=B、mode2=B、mode3=.5B。有限target2三个节点均为.5B（不靠mode特惠绕过）。每笔写真实paid及正数paid_amount；原子地重查当前cash/default/bankruptcy，先扣后标，一次性。三费互不充当，已付重算不重扣。

旧身份优惠只在mode1完整登记：复用market_prior_common的真实多条件生产者合同（不能只outcome1）及当前岗位成立，登记从B降为.5B并记来源。旧地契沿用听证复用market_prior_land的实际登记/赔偿/村社/来民条款及当前试点条件；否则当前.5官署新听证。旧朝省共同任命/预算/代表/否决/继任的真实联合合同（market_prior_court）使mode2完整分摊1.5B降为.75B；不是免费旧账或新外资。新helper可调用这些现有原生谓词，但不得读market业务运行状态/queue/receipt/positive outcome来冒充旧生产者。任何2/3/4/5或未参与历史均有有限通路。旧条款在1112和1113/观察当前条件两处持续读取，mode/target/pilot快照一致；优惠实际支付后不追补，资格丢失不能给尚未支付者缓存优惠。

## 时钟、快照与终态

新变量统一 `ywc_dmg_crown_*`，phase=1/2/3，stage=1110..1119；独占queue=`ywc_dmg_crown_pending_event`。选任命、听证、预算责任均按当前mode/target/pilot保存，执行与观察重核。claim挑真正自有吕宋pilot；无silent reselection借新州供给。cap含义沿用现有共享helper。

1116交接后stage1117才运行review；creation day写days=1防重复tick，五次不成熟、六次成熟。观察只在phase3/stage1117/running运行，条件失效即清连续数、mature/running并记interrupted；恢复必须明确restart，不自动续数。全部monthly读取真实当前策略/任命/听证/预算/财务。1117支付后到1118并停running但保留成熟证据，使后续真实丢条件可诚实受挫；1118/1119不被monthly重排。recount明确清requested/mature/streak，回1117重数，已付三费保留。

outcome1要求显式target1、当前完整策略与真实责任/三费/六次成熟；outcome2要求显式target2及当前有限条件/责任/三费/成熟；outcome3只能在已真实成熟且复核费已付、当前运行条件失效时请求与结算，恢复后旧受挫按钮不可结算。outcome4明确退出。所有release幂等，仅清本线业务并一次归还active/visible，不手写清全局reservation/witness/他线queue，不返费免债。不得另造notice12/36或未批准事件。

## 生成与所有权

生产作者只改 `data/content/v03/countries/dmg.json` 与两个手写DMG helper，及本人scratch报告。新arc的`inline_delivery_adapter`整键暂不填；root在作者结束后从真实script绑定metadata。保留旧五卡完整JSON语义与catalog文本前缀、helper物理字节前缀。所有本地化双语、10独立矛盾、三责任JE与实际选项，不复制市场/学堂套路文案。

每事件native immediate精确两句：`ywc_v03_mark_major_delivered = yes` 后 `set_variable = { name = ywc_v03_dmg_v03_dmg_representative_crown_last_event value = 1..10 }`。回执值为序号，绝非1110..1119；事件业务at谓词核序号及同stage/JE/pending缺席或本ID，旧按钮不可推进。发送绑定只在本JE按4/3/3分区，只有crown_pending_event的normal/exact队列。

root独占sharedadapter、新测试、metadata、6份DMG生成物、Git。保持v1与原五arc的43sender/62candidate，新增10sender/candidate63—72、served_6，12总JE。旧前62sender/candidate元数据与另外国家渲染不变。精确native receipt AST拒绝额外效果、错误字段/顺序、school/market别名；未知/重复/missing baseline middle继续拒绝。

## 验收

先真实RED后GREEN：三完整策略当下法律/同IG/岗位各异及现金3次；任一旧策略在相同当前事实/现金下至少两节点差异（登记半价+沿用听证）；真实旧court预算差价；旧受挫/退出/有限/未参加仍可保守有限。旧结果必须执行真实原始事件/JE赚取，不注入正向outcome/paid/settled。创建日/同日dup/五六次、战争/破产/失州/换政体/失去集团、恢复显式重启、两交接后失州出口、当前现金3次、晚付重算/受挫/恢复旧按钮/释放幂等均要实际源测试。三线(本线+school+foundation)正反native顺序公平>=90days且前九次各三。sourcefault native receipt不能ACK。旧国别/共享与生成静态适用检查，独立源码审查；全版配额、引擎/UI/存档/AI/平衡不因此完成。
