# 大顺《谁能向朝廷发言》实施计划

> For agentic workers: use superpowers:subagent-driven-development; source writers own only the three country inputs. Root owns actual binding, adapter, generation and Git.

**Goal:** 实现已批准 middle 卡 `v03_shu_public_deliberation`，8 独立事件1120—1127、2个责任JE4/4；在真实财政旧约与当前法律、集团、岗位下确定预算发言与申诉责任。

**Architecture:** 复用SHU既有native v3投递与严格事实解释器，追加国别业务；保留四旧卡完整JSON及两手写helper物理前缀。基线8222a4c；不要求年份、工业化、外国参与或旧卡完成。

**Spec:** `docs/superpowers/specs/2026-10-14-v0.3-十国长线内容目录.md` 共同规则与3.1；本文件裁决 `.scratch/shu-public-deliberation-workbuddy-design.md` 的未定数值、错误结果编码、过多receipt、阶段矛盾，冲突以本文件为准。全目录设计与持续开发已获用户批准，本次为其明确实现切片，无新范围审批。

## 边界与当前事实

- 只追加 `countries/shu.json` 新arc与 `ywc_v03_shu_effects.txt` / `...triggers.txt` 末尾；作者写本人scratch报告。旧4卡/8JE/39candidate、1direct_add、native immediate/源哈希不变。1128/29不用。无新modifier、自动改法/政府/建筑/人口/主权、外国资金或第二套经济分数。
- `claim` 按四川/重庆/云南/贵州顺序挑第一个当前真正自有州，记录本线pilot=1/2/3/4，之后不静默换州。所有公务pop必须实际就业于同一仍自有原州政府官署、occupancy达到阈值且无短缺；不借别州/外国分州。复用现有四地区与owner=ROOT形状，不能引用省契约业务pilot作为本线供给前置。
- 全部mode、target、stage、phase与责任快照精确存在和值匹配，缺席或0不当有限。原生未知命令先查本机定义；禁止业务ready stub。`ShuPublicWorld`事实层由测试作者独立提供；不改共享Strict/LanPublicWorld。

三种完整政策只读现行事实，不替玩家立法：

| mode | 当前法律/国情 | 同一实际集团与公务 |
|---|---|---|
| 1朝议咨询 | monarchy、appointed_bureaucrats；censorship/right_of_assembly/protected_speech之一；bureaucracy>=0、legitimacy>=25 | intelligentsia在政府、clout>=.10、approval>=0；原州公务>=.8 |
| 2财产代表 | wealth_voting/census_voting/universal_suffrage之一；right_of_assembly/protected_speech之一；net_fixed_income>=0、legitimacy>=25 | industrialists或rural_folk中的同一组在政府、clout>=.10、approval>=0；原州公务>=.5 |
| 3密议加申诉 | autocracy/oligarchy；outlawed_dissent/censorship之一；authority>=50、legitimacy>=25 | landowners或armed_forces中同一组在政府、clout>=.10、approval>=0；原州公务>=.5 |

全部完整执行/观察/终态还要求和平、非default/破产、当前真实责任。有限target2适用于任一政体/法律，只需原州公务>=.25、bureaucracy>=0、legitimacy>=20、和平与财务安全；1120有限选择显式mode3+target2，不靠mode3完整法律。全线无新外国投入，不虚构对方同意。

## 两责任JE与八个独立矛盾

1. `ywc_je_v03_shu_deliberation_eligibility`：1120—23，议事资格、预算册与核账见证，目标为1123真实预算签字。1122不是提前JE终局。
2. `ywc_je_v03_shu_deliberation_appeal_execution`：1124—27，谁接申诉、真实连续履责与最终答复，目标为完整1/有限2/诚实受挫3；退出4只fail，goal/fail互斥。

| ID/题目 | 实际行动与后续责任 |
|---|---|
|1120《先问谁能说话》| `court_consultation`/`property_representation`/`sealed_appeal`选mode、target1，或`limited_appeal`明确target2。claim已挑原州；当前mode条件不足不允许选完整。|
|1121《一份能被查问的预算》|`pay_register`即时实付登记新费，记录正金额及来源；海商旧钱不是新费。|
|1122《核账人的座次》|`reuse_local_witness`实际沿用完整旧地方核账/省共议证明且当前本州公务>=.5；`new_witness`新公务>=.8；target2专有`local_witness`只需.25。写witness_source/mode/target/pilot；当前来源持续复核。|
|1123《户部必须答复哪一页》|`sign_budget`核即时法律/集团/原州岗位、已付登记、当前见证与全部快照后签budget责任，才交接JE2。|
|1124《申诉递给谁》|按当前mode选择`register_public_appeal`(mode1/2)、`register_sealed_appeal`(mode3)、`register_local_appeal`(target2)，真实记录受理范围/承办公务与mode/target/pilot，启动1125六个月观察；不收未批准额外款。|
|1125《旧债不能代替新答复》|六次真实monthly成熟才`pay_review`即时实扣复核费并进入1126。实际中断后`restart_review`明确刷新真实记录从零再数；`narrow_and_recount`显式重签有限见证/受理与全部快照，保留实付、清请求/成熟、六个新月份。没有学校/旧史也能有限。|
|1126《把答复写进下期预算》|`request_full`/`request_limited`/`request_setback`按当前事实提出；`recount`回1125重数，已付不重扣。已恢复时缓存受挫按钮不能提出或执行。|
|1127《谁来对这份答复负责》|`close_full`/`close_limited`/`close_setback`实际当前双重检查后写outcome1/2/3，一次释放；`recount`可回1125。|

每事件有精确at_N显示和相同执行limit的wait/defer与withdraw。旧阶段、错/零receipt、缺/零phase的任何旧按钮必须不改业务、钱或队列，尤其withdraw不能只调用泛live_stage helper。wait允许以后再议；月度不得把1126/27阶段或queue改回1125。JE1签后立即失州/容量满，JE2仍能handoff并真实退出；arc只占一个active/visible，只释放自己一次，不清全局reservation/witness/他线queue，不退款或免旧债。

## 精确新费与真正跨期差异

B在claim捕获yearly_gross_income/52，clamp100..1e9，不随弹窗重算。只两笔新费：

| 费用 | mode1完整 | mode2完整 | mode3完整 | target2有限 |
|---|---:|---:|---:|---:|
|1121登记|B|1.5B；真实旧地方核账权则B|.5B|.5B|
|1125复核|B|1.5B；真实已还清本金的海商咨询源则B|.5B|.5B|

显示、外effectlimit、helper各自即时核同一当前价格/cash/default/破产，不透支。费用分支互斥，完整特惠不能覆盖有限价格。先扣后写paid+正paid_amount；已付缩小/重算真实保留原金额，不退款、不补收、不重复扣。

**地方核账源**必须真正执行旧财政政策赚取：fiscal started/settled、outcome2、first_audit、local_audit_right/真实地方结算mode2、非withdrawn/abandoned，旧pilot和本线pilot同号且当前仍自有。不得直接调用带prov业务pilot依赖的 `ywc_shu_v03_prior_local_right`；复制其真实产者联合字段并改用本线pilot。它在1121完整mode2费与1122/1123/连续观察见证至少两节点产生差异。无该权的新见证须.8，真实沿用.5；当前新政策mode2本来允许.5，差异确实可见。旧受挫/保守/退出/未参加不被当好历史，但都有明确有限入口。

**海商咨询源**可复用原生 `ywc_shu_merchant_consultation_source`，同时要求实际advance_repaid、无advance_unpaid及原本金>0；咨询/本金/实还缺一不能领取尚未支付的完整mode2复核优惠。还本并不抹咨询权；原债始终由原合同收款，本线不清债。新费仍实扣B，不把旧借入钱当支付本线。

**省共议/中央责任**在1122/23与1126复核实际已结案province合同及原始paid/share/relief/meeting(或真实旧地方权豁免)和pilot一致；不能仅province_outcome。沿用省共议可作为local witness的另一真实来源，中央责任写实际budget承办来源/文本并在后续继续检查，不虚构免费财政收益。未签或缺史不是正向许可。

## 时钟、快照、结果

phase1/stage1120..23；phase2/stage1124..27。1123handoff只核已真实签字，不再核容量或owner。1124真实受理后才在1125 running；创建日ticked days1，真实月度五次不成熟/六次成熟，同日不双计。当前mode+原州+见证来源+预算/受理快照+和平/财务任一失效即清streak/mature/running、记interrupted；恢复不自动续数。restart与recount须当前基础义务可履行并更新记录，六个新月份。

outcome1显式target1/当前完整策略、两正额实付/当前见证与受理来源/同mode-target-pilot快照/成熟6；outcome2同样显式target2+当前本地有限责任。outcome3只有真正成熟且复核已付、当前完整或有限义务丢失时可提出与结算；恢复旧受挫按钮不合法。outcome4主动退出。mode与outcome绝不混用，不采用草稿5/6结果码。不得用缺旧历史作成功；有限重签可真实换本地见证与承办、更新快照、清旧源引用并重数。

## SHU v3 接线与分工

本卡native immediate精确三句：mark_major；`ywc_v03_shu_event_dispatch=1120..1127`；`ywc_shu_delib_last_event=1120..1127`。保持原SHU v3形状，同时新candidate/ACK使用本arc独立delib_last_event而非其他卡共享回执；**不用设计稿的第四个序号receipt，也不把事件号和序号混用**。at_N核自己的last_event=N及pending缺席/本N。私有queue=`ywc_shu_delib_pending_event`，8sender exactnormal、4/4，两JE不新增direct_add。旧39之后40..47、served5、10总JE；固定旧四卡顺序再追加。

新arc `inline_delivery_adapter` 整键由source作者省略。root在终端后使用 `_kor_source_binding(... candidate_parser=_shu_queue_candidates)` / `_kor_direct_adds` 与实际JE/goal/exit算v3 metadata，维护精确新JE源与immediate哈希、selector及新receipt注册，保留原硬冻结源/不把新哈希泛化绕过检查。测试先RED后GREEN，生产作者不得伪写metadata/生成物。

## 验收任务

- [ ] 先完成literal能力RED/GREEN，同world执行真实旧海商本金12月、财政地方/中央、省共议，不能注入positive outcome/paid/settled。
- [ ] 新业务、旧跨期、adapter三独立测试模块：三完整政策当前法/同IG/原州pop、无旧史有限，两笔即时费/临界/旧按钮；同当前事实现金两节点差异、源字段删除/当前来源丢失。
- [ ] 六monthly/daygate/dup/五六、战争/失州/破产/换法/IG失效中断+明确重启，有限重新签六新月，晚paid受挫恢复/recount、签后失州handoff/容量幂等。
- [ ] 每stage全部withdraw/defer旧阶段/错receipt/phase负控；两JEgoal-fail互斥；三线两native顺序公平≥90days，receipt fault不ACK，旧4完整/source/1directadd/39candidate/另外8国渲染不变。
- [ ] 源作者终端后root绑定生成/check/catalog/总静态/旧相关回归、独立审查与精确暂存草稿PR。不宣称游戏/存档/UI/AI/平衡或全版1290/342完成。
