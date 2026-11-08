"""Production opening admission, payment eligibility, AI fallback, and content accuracy."""
import json
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import parse
import test_v03_nmg_foundation_lifecycle as lifecycle

NQG = json.loads((ROOT / "data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
MOD = ROOT / "yongchang_world"
NMG_MECHANICS_SHA256 = "b98ded6918d2ac6e5d4a1c0efbdf743f0ca70aa1d4f5f6ed10a58c694c50bafa"
NQG_MECHANICS_SHA256 = "bbd5a57c8483efb664977bd4a0de4d439ffe5de3b55d7aa92d352f97c5646c17"
NMG_OPENING_POLICY = {
    "ywc_nmg.1000": {"mixed":"ywc_nmg_land_mixed_ready", "unified":"ywc_nmg_land_unified_ready", "old":"ywc_nmg_land_old_ready"},
    "ywc_nmg.1010": {"bilingual":"ywc_nmg_office_bilingual_ready", "local":"ywc_nmg_office_local_ready", "single":"ywc_nmg_office_single_ready"},
    "ywc_nmg.1020": {"fixed":"ywc_nmg_revenue_fixed_ready", "joint":"ywc_nmg_revenue_joint_ready", "arrears":"ywc_nmg_revenue_arrears_ready"},
}
NMG_FEE_GATES = {
    "ywc_nmg.1000": ("ywc_nmg_land_fee_paid", "ywc_nmg_land_affordable"),
    "ywc_nmg.1010": ("ywc_nmg_office_fee_paid", "ywc_nmg_office_affordable"),
    "ywc_nmg.1020": ("ywc_nmg_revenue_quota_paid", "ywc_nmg_revenue_quota_affordable"),
}

def _event_projection(doc, nmg=False):
    rows=[]
    for arc in doc["arcs"]:
        for event in arc["events"]:
            opts=[]
            for option in event["options"]:
                trigger=option.get("trigger")
                ai=option.get("ai_chance")
                if nmg and event["id"] in NMG_FEE_GATES and option["key"] in NMG_OPENING_POLICY[event["id"]]:
                    trigger="<authorized captured-fee/receipt gate>"
                if nmg and event["id"] in NMG_FEE_GATES and option["key"]=="wait_for_funds":
                    ai="<authorized positive wait fallback>"
                opts.append([option["key"],trigger,option.get("effect"),ai])
            rows.append([event["id"],event.get("trigger"),event.get("immediate"),opts])
    data=json.dumps(rows,ensure_ascii=False,separators=(",",":"),sort_keys=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

class NmgOpeningAiTest(unittest.TestCase):
    cases = ((0, "ywc_nmg.1000", "ywc_je_v03_nmg_land_arbitration", "land_fee_paid", "land_affordable", "mixed"),
             (1, "ywc_nmg.1010", "ywc_je_v03_nmg_bilingual_office", "office_fee_paid", "office_affordable", "bilingual"),
             (2, "ywc_nmg.1020", "ywc_je_v03_nmg_revenue_opening", "revenue_quota_paid", "revenue_quota_affordable", "fixed"))

    def setUp(self):
        self.lifecycle = lifecycle.NmgLifecycleTest("test_world_fact_fixture_rejects_missing_state_shortage_and_unknown_primitives")

    def ai_base(self, option):
        ai = lifecycle.field(option, "ai_chance")
        self.assertIsInstance(ai, list, "AI chance must parse as Clausewitz, not a string assertion")
        self.assertEqual([key for key,_,_ in ai],["base"],"unsupported AI chance syntax must fail closed")
        return float(lifecycle.field(ai, "base"))

    def event_for_admitted_je(self, arc_index, je_id, settings):
        world = lifecycle.NmgWorld(lifecycle.fixture())
        v = world.countries["NMG"]
        v.update(settings)
        self.lifecycle.activate(world, je_id)
        self.assertIn(je_id, world.active_journals)
        eid = self.lifecycle.pulse_until_event(world, je_id)
        self.assertTrue(eid.startswith("ywc_nmg."))
        event = lifecycle.GENERATED_EVENTS[eid]
        self.assertTrue(world.conditions(lifecycle.field(event, "trigger"), "NMG"), eid)
        return world, eid, event

    def test_all_three_openings_have_actual_legal_positive_ai_and_fee_boundaries(self):
        # Stress cases remove every route except a positive-weight wait response.
        for arc_i,eid,je,receipt,affordable,paid_route in self.cases:
            for condition,settings in (("default", {"in_default": True}),
                                       ("bankrupt", {}),
                                       ("war", {"is_at_war": True}),
                                       ("cash0", {"gold_reserves": 0}),
                                       ("fee_minus_one", {"gold_reserves": 999})):
                with self.subTest(event=eid, condition=condition):
                    world,actual,event=self.event_for_admitted_je(arc_i,je,settings)
                    if condition == "bankrupt": world.modifiers.append(("NMG", {"modifier":"declared_bankruptcy"}))
                    options=[b for k,_,b in event if k=="option"]
                    legal=[b for b in options if world.conditions(lifecycle.field(b,"trigger"),"NMG")]
                    weights=[self.ai_base(b) for b in legal]
                    self.assertTrue(legal, (actual, condition))
                    self.assertGreater(sum(weights),0, (actual, condition, weights))
                    self.assertIn("wait_for_funds",[lifecycle.field(b,"name").split(".")[-1] for b in legal])
                    self.assertGreater(self.ai_base(lifecycle.event_option(actual,"wait_for_funds")),0)
                    self.assertFalse(any(lifecycle.field(b,"name").endswith("."+paid_route) for b in legal), condition)
            with self.subTest(event=eid, condition="exact_fee_paid_then_cash0"):
                world,actual,event=self.event_for_admitted_je(arc_i,je,{"gold_reserves":1000})
                self.assertTrue(world.conditions(lifecycle.field(lifecycle.event_option(actual,paid_route),"trigger"),"NMG"))
                before=world.countries["NMG"]["gold_reserves"]
                self.lifecycle.choose(world,actual,paid_route)
                v=world.countries["NMG"]
                self.assertEqual(v.get("ywc_nmg_"+receipt),1)
                self.assertEqual(before-v["gold_reserves"],1000)
                # The sunk opening fee is represented by its receipt; later events cannot demand it again.
                self.assertEqual(v["gold_reserves"],0)
                self.assertEqual(v.get("ywc_nmg_"+receipt),1)
            with self.subTest(event=eid, condition="exact_fee_route_is_legal"):
                world,actual,event=self.event_for_admitted_je(arc_i,je,{"gold_reserves":1000})
                paid=[b for b in (x for k,_,x in event if k=="option") if world.conditions(lifecycle.field(b,"trigger"),"NMG")
                      and lifecycle.field(b,"name").endswith("."+paid_route)]
                self.assertEqual(len(paid),1)
                fee_var = "revenue_quota" if arc_i == 2 else "office_fee" if arc_i == 1 else "land_fee"
                self.assertEqual(world.countries["NMG"]["ywc_nmg_"+fee_var],1000)


    def test_nmg_opening_ai_gates_match_locked_semantic_baseline(self):
        self.assertEqual(_event_projection(lifecycle.CATALOG,nmg=True),NMG_MECHANICS_SHA256)
        for eid,choices in NMG_OPENING_POLICY.items():
            receipt,affordable=NMG_FEE_GATES[eid]
            for key,ready in choices.items():
                option=next(o for a in lifecycle.CATALOG["arcs"] for e in a["events"] if e["id"]==eid for o in e["options"] if o["key"]==key)
                old=f"{ready} = yes"
                self.assertEqual(option["trigger"],f"{{ AND = {{ {old} OR = {{ has_variable = {receipt} {affordable} = yes }} }} }}",(eid,key))
            wait=next(o for a in lifecycle.CATALOG["arcs"] for e in a["events"] if e["id"]==eid for o in e["options"] if o["key"]=="wait_for_funds")
            self.assertEqual(wait["ai_chance"],"{ base = 10 }")

    def test_paid_receipt_at_zero_cash_still_continues_and_new_fees_stay_guarded(self):
        cases=(
            ("ywc_je_v03_nmg_land_arbitration","mixed","rule_register","ywc_nmg.1002","finish_survey"),
            ("ywc_je_v03_nmg_bilingual_office","bilingual","hire_thin","ywc_nmg.1011","hire_full"),
            ("ywc_je_v03_nmg_revenue_opening","fixed","audit_strict","ywc_nmg.1025","carry_heavy"),
        )
        for je,paid_key,free_key,fee_event,fee_key in cases:
            with self.subTest(je=je):
                world=lifecycle.NmgWorld(lifecycle.fixture());world.countries["NMG"]["gold_reserves"]=1000
                self.lifecycle.activate(world,je)
                opening=self.lifecycle.pulse_until_event(world,je)
                self.assertTrue(world.conditions(lifecycle.field(lifecycle.event_option(opening,paid_key),"trigger"),"NMG"))
                self.lifecycle.choose(world,opening,paid_key)
                v=world.countries["NMG"];v["gold_reserves"]=0
                self.assertTrue(v.get("ywc_nmg_"+({"mixed":"land_fee_paid","bilingual":"office_fee_paid","fixed":"revenue_quota_paid"}[paid_key])))
                self.assertTrue(world.conditions(lifecycle.field(lifecycle.event_option(opening,paid_key),"trigger"),"NMG"),"paid receipt branch must keep the original option eligible at zero cash")

                arc=next(a for a in lifecycle.CATALOG["arcs"] if a["journals"][0]["id"]==je)
                order=[j["id"] for j in arc["journals"]]
                def choose_next(key):
                    if world.active_journal is None:
                        self.lifecycle.activate(world,order[len(world.completed_journals)])
                    actual=self.lifecycle.pulse_until_event(world,world.active_journal)
                    option=lifecycle.event_option(actual,key)
                    self.assertTrue(world.conditions(lifecycle.field(option,"trigger"),"NMG"),(actual,key))
                    self.lifecycle.choose(world,actual,key)
                    status=self.lifecycle.reconcile_active_je(world)
                    if status=="complete" and len(world.completed_journals)<len(order):
                        self.lifecycle.activate(world,order[len(world.completed_journals)])
                    return actual

                if je=="ywc_je_v03_nmg_bilingual_office":
                    actual=self.lifecycle.pulse_until_event(world,world.active_journal)
                    self.assertEqual(actual,"ywc_nmg.1011")
                    self.assertFalse(world.conditions(lifecycle.field(lifecycle.event_option(actual,"hire_full"),"trigger"),"NMG"),"second opening fee must remain gated")
                    self.assertTrue(world.conditions(lifecycle.field(lifecycle.event_option(actual,free_key),"trigger"),"NMG"))
                    self.lifecycle.choose(world,actual,free_key)
                    self.lifecycle.reconcile_active_je(world)
                else:
                    choose_next(free_key)
                # Continue the no-fee revenue phase to its later separately billed option.
                if je=="ywc_je_v03_nmg_revenue_opening":
                    choose_next("close_account")
                    choose_next("press_quota")
                    choose_next("use_temperature")
                if world.active_journal is None:
                    self.lifecycle.activate(world,order[len(world.completed_journals)])
                actual=self.lifecycle.pulse_until_event(world,world.active_journal)
                if je=="ywc_je_v03_nmg_land_arbitration":
                    self.assertEqual(actual,"ywc_nmg.1002")
                    fee_option=fee_key
                elif je=="ywc_je_v03_nmg_bilingual_office":
                    self.assertEqual(actual,"ywc_nmg.1012")
                    fee_option=None
                else:
                    self.assertEqual(actual,fee_event)
                    fee_option=fee_key
                if fee_option:
                    self.assertFalse(world.conditions(lifecycle.field(lifecycle.event_option(actual,fee_option),"trigger"),"NMG"),"a genuinely new fee remains gated by current captured-fee affordability")

    def test_later_revenue_copy_matches_recorded_domestic_effects(self):
        nmg=lifecycle.CATALOG
        arc=nmg["arcs"][2]
        events={e["id"]:e for e in arc["events"]}
        forbidden=("Mexico City brings ships", "first instalment leaves this quarter",
                   "Mexico City reply is awaited", "commissioner brings two sheets",
                   "overlord officer sees it", "interest keeps running", "billed at the current share",
                   "remittance is larger", "costs and influence are each split in two",
                   "becomes a line in the debt")
        narrative=" ".join(v for eid in (f"ywc_nmg.{n}" for n in range(1020,1030))
                           for v in events[eid].get("desc",{}).values())
        for event in events.values():
            if event["id"] in (f"ywc_nmg.{n}" for n in range(1020,1030)):
                narrative += " " + " ".join(v for option in event["options"]
                                               for field in ("cost_note","consequence_note")
                                               for v in option.get(field,{}).values())
        folded=narrative.casefold()
        for phrase in forbidden:
            self.assertNotIn(phrase,folded)
        self.assertIn("adds 1 bureaucracy for ten years",events["ywc_nmg.1020"]["options"][1]["consequence_note"]["en"])
        self.assertIn("no payment",next(o for o in events["ywc_nmg.1025"]["options"] if o["key"]=="share_even")["cost_note"]["en"].casefold())
        for lang,file in (("en","ywc_v03_country_nmg_l_english.yml"),("zh","ywc_v03_country_nmg_l_simp_chinese.yml")):
            rendered=(MOD/"localization"/("english" if lang=="en" else "simp_chinese")/file).read_text(encoding="utf-8-sig")
            for eid in (f"ywc_nmg.{n}" for n in range(1020,1030)):
                event=events[eid]
                self.assertIn(f'{eid}.d:0 "{event["desc"][lang]}"',rendered)
                for option in event["options"]:
                    for field in ("cost_note","consequence_note"):
                        if field in option:
                            self.assertIn(f'{eid}.{option["key"]}.{field.replace("_note","_tooltip")}:0 "{option[field][lang]}"',rendered)

    def test_unpaid_opening_real_12_to_36_notice_can_withdraw_without_refund(self):
        cases=((0,"ywc_je_v03_nmg_land_arbitration","ywc_nmg.1007","land"),
               (1,"ywc_je_v03_nmg_bilingual_office","ywc_nmg.1015","office"),
               (2,"ywc_je_v03_nmg_revenue_opening","ywc_nmg.1029","revenue"))
        for arc_i,je,notice36,lane in cases:
            with self.subTest(lane=lane):
                world=lifecycle.NmgWorld(lifecycle.fixture())
                v=world.countries["NMG"];v["is_at_war"]=True;v["gold_reserves"]=0
                self.lifecycle.activate(world,je)
                notices=set(); reached=False
                for _ in range(24):
                    status=self.lifecycle.reconcile_active_je(world)
                    if status: break
                    actual=self.lifecycle.pulse_until_event(world,je)
                    if actual==notice36:
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_notice12_delivered"),1)
                        before=v["gold_reserves"]
                        self.lifecycle.choose(world,actual,"withdraw")
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_notice36_delivered"),1)
                        self.assertEqual(v["gold_reserves"],before)
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_withdrawn"),1)
                        self.assertEqual(v.get("ywc_v03_active_arc_count"),0)
                        self.assertEqual(v.get("ywc_v03_visible_task_count"),0)
                        self.assertEqual(self.lifecycle.reconcile_active_je(world),"fail")
                        self.assertFalse(world.active_journals)
                        reached=True;break
                    opts=[lifecycle.field(b,"name").split(".")[-1] for k,_,b in lifecycle.GENERATED_EVENTS[actual] if k=="option"]
                    notice12_event={"land":"ywc_nmg.1006","office":"ywc_nmg.1014","revenue":"ywc_nmg.1028"}[lane]
                    if actual==notice12_event:
                        key="keep_route" if lane=="office" else "defer"
                        self.assertIn(key,opts)
                        self.lifecycle.choose(world,actual,key)
                        self.assertEqual(v.get(f"ywc_nmg_{lane}_notice12_delivered"),1)
                        notices.add(actual)
                    elif "wait_for_funds" in opts:
                        self.lifecycle.choose(world,actual,"wait_for_funds")
                    elif "defer" in opts:
                        self.lifecycle.choose(world,actual,"defer")
                    else:
                        self.fail(f"unexpected legal opening continuation: {actual} {opts}")
                self.assertTrue(reached,(lane,world.calendar_month,notices,v))
                self.assertTrue(notices,(lane,"the actual 12-month response card was not visited"))


class NqgContentAccuracyTest(unittest.TestCase):
    def event(self,eid): return next(e for a in NQG["arcs"] for e in a["events"] if e["id"]==eid)
    def option(self,eid,key): return next(o for o in self.event(eid)["options"] if o["key"]==key)

    def test_selected_contract_copy_is_truthful_and_bilingual_in_generated_files(self):
        cases=(("ywc_nqg.1020","exclusive_lease","no cash transfer","没有现银汇入"),
               ("ywc_nqg.1015","settle_full","co-management","共同管理"),
               ("ywc_nqg.1027","settle_full","exclusive lease","独占租约"))
        for eid,key,en,zh in cases:
            note=self.option(eid,key)["consequence_note"]
            self.assertIn(en,note["en"].casefold())
            self.assertIn(zh,note["zh"])
        lease=self.option("ywc_nqg.1020","exclusive_lease")["consequence_note"]
        self.assertIn("Northern Qing pays the filing fee",lease["en"])
        self.assertIn("北清国库支付",lease["zh"])
        self.assertNotIn("Xinming",lease["en"])
        self.assertNotIn("新明国库",lease["zh"])
        for lang,file in (("en","ywc_v03_country_nqg_l_english.yml"),("zh","ywc_v03_country_nqg_l_simp_chinese.yml")):
            rendered=(MOD/"localization"/("english" if lang=="en" else "simp_chinese")/file).read_text(encoding="utf-8-sig")
            for eid,key,_,_ in cases:
                value=self.option(eid,key)["consequence_note"][lang]
                self.assertIn(f'{eid}.{key}.consequence_tooltip:0 "{value}"',rendered)
        # NQG narrative edits leave the entire event/option mechanics projection at its locked baseline.
        self.assertEqual(_event_projection(NQG),NQG_MECHANICS_SHA256)

if __name__ == "__main__": unittest.main()
