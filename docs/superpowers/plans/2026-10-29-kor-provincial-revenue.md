# 朝鲜《各道留用的那一份》实施约束

2026-10-30 真实旧历史复核裁决：独立PR93已在旧军事入口补齐缺席数值计数器的显式零初始化，保留现有计数/收入快照；收入卡以该新基线继续。真实1006退出揭示旧军事两个JE的goal可能与arc_abandoned失败同时成立，准许仅在这两个旧goal外加NOT arc_abandoned，保留原内部正常目标；root只同步对应两项goal_sha256。这四项旧catalog叶子及独立初始化是原文“旧三卡保持”的明确窄例外，其余旧脚本/31源/5directadd/国别内容不变。新收入卡1104明确缩小必须实际更新有限责任快照并重数六个月，实付保留；旧书院联合资格必须含实际第二次旧账读取。精确反例与本轮源修复约束见`.scratch/kor-revenue-fix-round2-brief.md`。

批准目录的 `v03_kor_provincial_revenue`，middle，8事件1100—1107、2日志4/4。基线9980153；本文件裁决两个scratch设计/预检稿的冲突，不把研究猜测当代码合同。保留旧3卡完整语义、catalog文本前缀、手写helper原始字节前缀。既有KOR v2、31sender/candidate、6JE与5direct_add不变，收入追加32—39、served4、8总JE。

## 三项财政政策有不同的现实承办者

不造地方税权法律，不自动通过税法、不改政府/人口/建筑/外国协议，不新增全局静态修正。全国当前税法只是执行这项预算协议的现实条件，协议变量不声称已改变游戏引擎的税收分配。

一次挑选当前自有朝鲜试点州，所有后续岗位、就业、机构与动荡限定该仍自有的原始试点；他州或外国分州不得借用。优先复用旧国别已证明的原生state变量保存/比较；若无法在严格world解释，先报告具体缺口，不能写恒真has_pilot。入口不依赖旧线已完成、年代、战争、工业化或外国同意。

三完整mode：

1. 成文分税：当前proportional_taxation/graduated_taxation，真实官署在职公务>=.8、bureaucracy>=0、legitimacy>=25，选中州turmoil<=.25；同一个rural_folk或intelligentsia在政府、clout>=.10、approval>=0。当前学校机构>=1，试点有实际在职教育/公务岗位，不凭文本称“学校已获拨款”。
2. 中央统收：当前per_capita_based_taxation/proportional_taxation/graduated_taxation，appointed_bureaucrats、真实官署公务>=.8、同州真实军营在职soldiers/officers>=.8且无短缺；同一个armed_forces在政府、clout>=.10、approval>=0，bureaucracy>=0、legitimacy>=25、turmoil<=.25。
3. 项目拨款：当前land_based_taxation/per_capita_based_taxation，真实官署公务>=.5、实际农业就业（rice/wheat/millet农场的farmers/laborers>=.5且无短缺）；同一个landowners或devout在政府、clout>=.10、approval>=0，bureaucracy>=0、legitimacy>=25、turmoil<=.25。此模式是独立完整策略，不自动称有限。

显式target2保守有限目标适用于任何税法/现行政体：原试点自有、真实官署在职公务>=.25、bureaucracy>=0、legitimacy>=20、turmoil<=.40、和平、非default/破产、净收入>=0。无需学校/港口/军营/改革税法/现任特殊集团/外国合作；仍有真实岗位与费用。不能缺变量当target2。完整策略失去条件后可明确缩小重数；不能自动换税法或偷偷换试点续观察。

native `turmoil` 已核安装本体 `events/agitators_events/agitators_law_events.txt:146—148`（state scope）；新测试world仅在真实state_scope解释数值0..1，未知scope/缺值/非数值拒绝。IG联合条件复用LanPublicWorld。税法原生键已核 `common/laws/01_taxation.txt`，人头税准确名为 `law_per_capita_based_taxation`。

## 八次不同责任争论和两日志

- JE1=`ywc_je_v03_kor_provincial_revenue_settlement`，1100—1103。1100《留用先写在谁的账上 / Whose Ledger Records the Retained Share》选择mode1/2/3或显式有限并挑试点；1101《一道税票，两套抄本 / One Tax Receipt, Two Copies》真正付立契/官署账；1102《学校、营房与田间的领款人 / Claimants from School, Barracks and Fields》根据政策当前真实承办岗位设地方核账/中央查核/项目名册，旧地方报账权可沿用而新核账要求更多公务；1103《印封之前谁来签字 / Who Signs Before the Seal》复核当前责任、已付与试点/政策/目标快照，再真实交接第二JE。
- JE2=`ywc_je_v03_kor_provincial_revenue_review`，1104—1107。1104《六个月里没有写出的欠账 / Arrears Absent from Six Monthly Ledgers》真实连续六次观察后缴复核账；中断/缩小/等待/明确restart保留可达。1105《没有加税的那一页 / The Page Without a New Levy》当前税法/任职集团/岗位/动荡重审，记录公共责任：完整、明确有限或真实受挫请求；1106《留用权不是第二次收款 / Retention Rights Are Not a Second Bill》核验已付、责任来源与当前状态，可明确recount回1104而不重收两费；1107《府库关账以后 / After the Treasury Closes Its Books》执行当前核验后的唯一终态。

唯一队列 `ywc_kor_revenue_pending_event`，phase1/2、stage1100..1107。每事件有独立中英文矛盾、可执行行动/成本、延迟读取，不复制DMG市场/学堂文案。等待与退出必须核当下本线stage/JE/receipt，旧按钮不得重开、重付或二次释放。JE1交接/JE2 possible不要求当前仍有州或新容量；失州后同一事件仍能等待收复或退出，不能静默换州。goal与fail互斥，退出4不完成JE。

## 两笔真正扣款、旧联合合同与两处跨期消费

B=claim时yearly_gross_income/52、最低100，一次捕获。立契1101收费mode1=B、mode2=2B、mode3=.5B；复核1104收费mode1=B、mode2=1.5B、mode3=.5B。显式target2两笔均.5B。每笔原子重核当前现金/default/破产、实扣才写paid+正数paid_amount；重复、重算、旧弹窗不重扣，不退款、不免旧债。

旧军门“地方报账”合同：真实military_accounts_started/settled、outcome2、supply_route2、reporting_mode2、provincial_report_right/outcome_provincial_supply、audit_paid、invoice_review_paid、supply_account_accepted、audit_public、review_complete、service_review_complete、six+nine_months_complete，当前route_execution_ready，排除abandoned/scope_narrowed。要声称已支付本地翻译/退伍合同，还必须实际对应started/funded与paid_months>=12，不能把pay_monthly_supply计数当真实扣款。此真实合同使mode1完整立契B降为.5B；同时在1102和其后持续当前审查中允许沿用地方核账，公务阈值.5（仍须真实现任/学校/税法/动荡等，不能凭旧flag免掉当前事实），没有此合同的新核账需.8公务。优惠已实付不追补，尚未实付不能沿用失效旧合同。

真实旧中央查核版对应outcome1、supply_route1、reporting_mode1、court_inspection_right/court_command_commitment/outcome_court_supply及同一真实底座，使mode2完整复核1.5B降为B，并在1105当前查核时读取原承诺/当前军营，不能只标“中央派”。本线不调用旧release、改旧outcome或写假foreign consent。

旧书院与港市还须在1102/1103及1105/1106两个后续节点读取联合真实合同，影响采用的核账人/责任条款与文本：学校已付相应coop/office、filing/old_invoice、任用、employer_confirmed=1、复核/旧账清/当前供给，及具体route；港市已付相应designated/general和filing、prior_contracts_checked、真实六个月/当前route/auditor/old_contracts_clear，排除withdrawn/compromise；无所谓ports_review_authorized flag。未有这些合同就以当下政策新核账，不赠资、不冒领资格。若采用沿用学校核价者必须保持school_route_snapshot与当前route/实在岗位一致。历史未签/已清OR只作无欠账守卫，不能单独当正向付费合同。

跨期测试必须通过原始事件/JE真实赚取；两个不同真实军事政策、相同当前世界和现金，应该在登记价和核账公务要求两个节点得到差异；学校/港市也要实际赚取与当前损失负控。旧2/3/4/未参加可凭当下有限目标完成，军事outcome2本来是合法地方供给，不能误叫失败。

## 连续性、两费后的当前结算与幂等

1103交接时begin_review，phase2/stage1104/running，创建日days1防重复。五次未成熟、六次成熟；只在1104运行观察，当前税法/同IG/试点/责任/岗位/动荡/和平与财务任一失效即清streak/mature/running并记interrupted，恢复必须明确restart，从零六次。缩小与late recount同样重数，已付两费保留。

1104缴后停running保留成熟证明，1105..07不被monthly覆写stage或queue。outcome1完整要求显式target1+当前完整条件+两笔真实paid+核账/签字mode/target/pilot一致+真实六次成熟；outcome2明确target2与当前有限事实；outcome3仅在已成熟且复核费已实付、当前运行资格丢失时请求和执行，恢复后旧受挫按钮不合法；outcome4主动退出。请求与最终执行双重核验，late回1104清requested/streak重数但不重扣。

release幂等只清本线业务，active/visible各减一次并clamp；不手清generated witness、reservation或任何他线queue。保留旧债/合同付款，不把余额不足变免费完成。

## 所有权与投递ABI

生产作者只改KOR catalog与两手写helper及本人scratch报告。新arc inline_delivery_adapter整键省略；root绑定实际v2 metadata、生成6输出、维护sharedadapter/tests/Git。旧3卡完整JSON与文本/字节前缀保留。

新native immediate严格mark_major=yes后写独立 `ywc_v03_kor_v03_kor_provincial_revenue_last_event=1..8`（序号，不是事件ID）；at谓词同phase/JE/stage/receipt/pending缺席或本ID。sharedadapter只注册这一可选middle，固定三foundation后revenue；v2 branch12字段/priorchain/queue_exclusions与实际direct_adds均从源推导。receipt须真实送入candidate/postproof/ACK，新KOR收入错receipt即使mark_major也不ACK；不得只改regex，却遗漏当前只对DMG/NMG加receipt的ACK guard。旧KOR mark-only/notice/外国协议body例外原样保留。

验收要真实RED/GREEN、三政策/有限/税法与同IG差别/在职与原试点/动荡边界/.5沿用与.8新核账/真实旧生产者/六次与重启/交接后失州/即时现金与旧弹窗/晚期受挫和recount/一次释放；新线+学校+军门三原生source两种顺序公平推进，至少90日冷却、首九各三，所有新候选32..39真实ACK，receipt fault负控。旧3卡metadata/5direct_add/31candidate/另外八国渲染保持。独立审查与适用静态检查；不据此宣称引擎/UI/存档/AI/平衡或整版v0.3完成。
