# 新明《教区钟声与会馆课表》实施计划

> For agentic workers: use superpowers:subagent-driven-development. Source author owns only the three NMG inputs; root binds actual sources, maintains adapter, generates and commits.

**Goal:** 落实已批准 middle 卡 `v03_nmg_parish_school`，8个独立事件1110—1117、2JE4/4，以当前宗教/教育法律、学校投资、在职人员与真实预算确定教区—会馆—公共机关的教学责任。

**Architecture:** NMG现有native v2旧3卡之后追加本卡；原3卡完整JSON/6JE/36候选/0direct_add、两手写helper物理前缀不变。基线00ccb058/PR94。使用已验证 `NmgSchoolWorld`：LanPublicWorld→NmgPartnerWorld→PartnerWorld→Strict，constructor前提供真实states注册StateRef；所有低层方法显式tag=NMG。

**Spec:** 批准目录4.3及共同规则。本文件裁决 `.scratch/nmg-parish-school-workbuddy-design.md`：拒绝以现金门槛+标记冒充教区实际转账、拒绝仅mode1可完整、拒绝额外12/36notice、未知teachers/building_school、任意自动补齐或退化。现有设计与持续实现已获用户批准，本文件冻结其实现切片。

## 当前事实与三完整策略

claim选择第一个当前真正自有state，原生save_scope_as+set_variable保存真实StateRef，本线始终读取同一原州；丢失或消失不能借其他州/外国分州，不静默换州。入口只读初始化/容量/自有州/未开始，不绑定旧史、日期、外国、工业化。旧官署没有自己的statepilot，不能虚构它原来保存了本线州身份。

所有在职者必须在原州实际employment，其workplace为真实对应building type、occupancy达阈值、无短缺。禁止独立“teachers”职业/“school”建筑；本机真实pop是academics、clergymen、bureaucrats/clerks，教学机构是学校investment与真实大学。法键已按本机`00_church_and_state.txt`/`01_education_system.txt`核对：state_religion/freedom_of_conscience/total_separation、religious_schools/public_schools。

| mode | 当前法律/学校 | 真实在职及同IG支持 |
|---|---|---|
|1共办公学|religious_schools或public_schools；freedom_of_conscience；school investment>=1；bureaucracy>=0、net_fixed_income>=0、legitimacy>=25|本州公务>=.5及大学academics>=.5；intelligentsia或petty_bourgeoisie中同一组在政府/clout>=.10/approval>=0|
|2宗教分办|religious_schools；state_religion或freedom_of_conscience；investment>=1；bureaucracy>=0、legitimacy>=25|本州公务>=.5及大学clergymen>=.5；同一个devout在政府/clout>=.10/approval>=0|
|3世俗统筹|public_schools与total_separation；investment>=2；bureaucracy>=0、net_fixed_income>=0、legitimacy>=25|本州公务>=.8及大学academics>=.8；同一个intelligentsia在政府/clout>=.10/approval>=0|

三完整策略还须和平、非default/破产、当前实际责任。角色按职务与当前集团，不绑定永生人物/固定政体；天主教化华墨背景保留为本国历史语境，不声称当前永远不能换宗教法。mode不改法律、机构投资或政府组成。

显式target2有限本地课堂适用任一政体/法律，只需原州真实在职公务>=.25、bureaucracy>=0、legitimacy>=20、和平/财务安全；无大学/学校投资/旧史/特殊IG也可。1110 finite明确mode2+target2，不能把mode/target缺失或0当有限。mode1/2/3均可完整outcome1；outcome2仅显式有限，3诚实受挫、4退出，与旧office3确立/2妥协/1退出严格区分。

## 两个责任JE、八个矛盾

JE1 `ywc_je_v03_nmg_parish_school`，1110—13：课程选择、开课预算、两种聘书与签署责任；只有1113真实签署才goal并handoff。

JE2 `ywc_je_v03_nmg_parish_settlement`，1114—17：实际工资、承办核验、连续履责和下学年结案。handoff/possible只核真实已签，不再要求owner或新容量；签后失州仍能进JE2并退出。一arc只占一个active/visible。

|事件|明确选项与实际责任|
|---|---|
|1110《钟声和课表谁先开始》|`joint_school`/`parish_split`/`secular_coordination`选mode与target1，或`limited_classroom`显式target2。pilot在claim一次选定。|
|1111《谁出第一笔开课钱》|`pay_register`实扣国库登记/课程抄本费，写正paid_amount。没有教区虚构捐款。|
|1112《一位先生的两份聘书》|mode1可`reuse_bilingual_roster`沿用完整真实旧双语编制，本州旧公务>=.8+academics>=.5；否则mode1/3 `hire_academic`需当前大学academics>=.8；mode2 `appoint_clergy`需大学clergymen>=.5；target2 `local_instructor`只需原州公务.25。明确teacher_kind、mode/target/pilot快照，源资格持续读取。|
|1113《三处签押的一张课表》|`sign_curriculum`即时当前政策/在岗/旧源/实付与快照一致才签课程、交接；宗教分办也能完整，不能自动降到有限。|
|1114《缺勤簿上还有一份工资》|`pay_wages`第二笔国库实扣，当前岗位/合同/现金即时同价；不是教区账户或外国到账。|
|1115《教区与会馆各自该做什么》|`audit_teaching_duties`检查实际聘任/雇主和现行制度，记录承办公务/教师/课程mode-target-pilot责任并开始1116观察。没有私有捐款“核验即到账”标记。|
|1116《连续六个月的考勤》|真正六monthly成熟后`request_full`/`request_limited`进入1117；若真实成熟且两费实付而当前义务丢失可`request_setback`。中断后`restart_review`明确当前恢复、从零再六；`narrow_and_recount`真实换本地教师kind4并同步所有责任快照、保留实付、清请求/成熟、六个新月份。|
|1117《下一学年的责任人》|`close_full`/`close_limited`/`close_setback`当前再次重核后outcome1/2/3，一次释放；`recount`返回1116从零再六，不重收费。|

每事件均有stage-bound wait/defer与withdraw，显示与effect内同一个完整at_N守卫（含phase、JE、stage、独立receipt与本线pending缺席/本ID）。缓存旧按钮、错/零receipt、缺/零phase不得改钱/业务/queue，withdraw不能只用泛live_stage。release仅本线、幂等归还容量，不手清全局witness/reservation/他线queue，不退费免旧债。1118/19空置，无新增notice。

## 两笔精确实付与真实旧官署差异

B在claim捕获yearly_gross_income/52，clamp100..1e9，一次固定。1111登记：mode1完整B，合格真实旧office完整编制则.5B；mode2完整.5B；mode3完整B；target2恒.5B。1114工资：mode1完整B、mode2完整.5B、mode3完整1.5B、target2恒.5B。显示/外effect/helper即时重查同一当前费用与现金/破产，不透支；费用分支互斥，旧优惠不能覆盖有限价。

先扣后标paid与正paid_amount，各自一次。缩小或晚重算保留真实原金额，不退款、不补收、不重复扣；旧office花过的钱绝不充当两笔新费。

`prior_bilingual_contract`联合读取真实旧started/settled、**outcome3**、office_established/closed、route1、office_fee_paid且oldfee>0、roster_full、schools、parish_recorded、six_months_complete，排除limited_selected/withdrawn；具体字段按真实旧source，不编造hire_full_paid。当前同一新试点还须官署在职公务>=.8、实际学校investment>=1与literacy_rate>=.4，保持原完整双语编制当前资格；不能调用带旧业务live/queue依赖的ready。旧roster_full单flag不足，因为薄编制/借用也可能写它。

这个真实联合合同在至少两节点改变本线：1111 mode1登记1000→500；1112/1113允许复用已在岗双语公务编制（大学academics.5）而新聘须大学academics.8。相同当前office.8/academics.5/学校与现金下可比较。登记后当前源丢失，不追补已付，但1112/1113及观察/终结不得缓存尚未兑现的编制特权。可通过恢复原资格、或明确有限重签真实换kind4重新六个月，不得静默降格。旧office2妥协、1退出或未参与，都能从当前有限课堂起步。

旧1010收费1000、1011真实完整聘员另扣1000；1013 fund_schools已实测扣款0，仅程序/采用记录。**本线不得把schools/parish_recorded/pledge/现金门槛+新flag当教区捐款、私人资助或外国同意。** 所有本线款项明示为真实国库支出；教区/会馆只承担教学、课程与承办责任，当前实际员工与机构证明其行为，不模拟另一账户。

## 连续性、当前结算与接线

phase1/stage1110..13，phase2/stage1114..17；1115实际核验后才stage1116 running，创建日days1防重复，真实五次未成熟/六次成熟。同一原pilot、当前法/机构/同IG/真实岗位、采用旧源/全部合同快照、和平和财务任一丢失清streak/mature/running、记interrupted；恢复不自动续数。显式restart/narrow/recount从零六新月，保留真实两费。阶段1117不被月度tracker覆写或重排queue。

request与close都核显式target/当前供应/两正额实付/teacher与课程承办快照/成熟6。诚实受挫3须真正成熟且两费实付、当前运行义务丢失；恢复后旧受挫请求和按钮无效，不能自动把成熟失败写3。主动退出4只fail，两个JEgoal/fail互斥。

native immediate EXACT2句：mark_major后 `ywc_v03_nmg_v03_nmg_parish_school_last_event=1..8`（序号非1110..17）；业务全在选项/helper，独占queue `ywc_nmg_school_pending_event`。root终端后从实际2JE源、goal/exit、8sender、真实directadds0绑定v2 metadata；作者新arc整键省略inline_delivery_adapter，禁止手填hash。固定旧三arc后本middle，旧36之后37..44、served4、总8JE；严格receipt送进candidate/postproof/ACK，不以mark/cooldown代替，未知/重复/missing基础arc与别线queue别名继续拒绝。

## 验收任务

- [x] literal与真实旧历史基座10methodsGREEN，原生office3/2/1同world产生、真实38/35月及两收费节点，未注入positive业务状态。
- [ ] 业务/跨期测试先真正RED：三当前政策、任意保守有限、实际StateRef/owner/就业/学校/法律/同IG负控；2费临界、单旗假历史、旧3/2/1/未参与、相同当前事实两节点差异。
- [ ] 创建日/重复/五六、中断与恢复明确重启、有限新签六新月、晚paid诚实受挫/恢复/recount保留账；全stage旧withdraw/receipt/phase负控、签后失州交接、一次释放与goal/fail互斥。
- [ ] 新线+office+foundation三原native两顺序公平≥90天、前九各三、全部新候选ACK、receipt fault不ACK；旧3完整/v2/source/0direct_add/36候选及其余8国渲染不变。
- [ ] 终端后root绑定生成/check/catalog/总静态/旧适用回归，独立源码复审，精确暂存draft PR。不称引擎/UI/存档/AI/平衡或全版完成。
