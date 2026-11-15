"""Strict C1-C4 regressions using the extracted SHU/KOR production world-fact adapter."""
import unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shu_kor_strict_review_runtime import Strict, facts, M1_PLAN, runplan, field
from clausewitz_harness import parse


def play(world, arc, event_no, choice):
    event = world.deliver(arc, f"ywc_shu.{event_no}")
    world.choose(arc, event, choice)
    return event


def start_m1(world):
    arc = world.cat["arcs"][0]
    runplan(world, arc)
    assert world.countries[world.tag].get("ywc_v03_shu_v03_shu_fiscal_register_outcome") == 1
    assert world.history[world.tag][arc["journals"][0]["id"]] == "complete"


def start_port(world, route):
    arc = world.cat["arcs"][2]
    route_options = {
        1: [(1018, "unified_customs"), (1019, "publish_books"), (1020, "refuse_credit"),
            (1021, "current_law_review"), (1022, "pay_verification"), (1023, "central_form")],
        2: [(1018, "merchant_share"), (1019, "split_books"), (1020, "consult_only"),
            (1021, "current_law_review"), (1022, "pay_verification"), (1023, "share_form")],
    }
    for event_no, choice in route_options[route]: play(world, arc, event_no, choice)
    burden = "central_burden" if route == 1 else "shared_burden"
    play(world, arc, 1024, burden)
    state = world.countries[world.tag]
    assert state["ywc_shu_port_fee_paid"] == 1
    assert state["ywc_shu_port_route"] == route
    return arc


class StrictSHUKORReturns(unittest.TestCase):
    def world(self, landowner_approval=-2):
        w = Strict("shu")
        w.countries[w.tag] = facts(landowner_approval=landowner_approval)
        w.modifiers = [(w.tag, {"modifier": "military_wages_medium"})]
        return w

    def test_port_routes_keep_90_day_notice_queued_then_apply_full_terminal(self):
        for route, outcome, terminal in ((1, 1, "settle_unified"), (2, 2, "settle_share")):
            with self.subTest(route=route):
                w = self.world(); start_m1(w); arc = start_port(w, route)
                state = w.countries[w.tag]
                initial_fee = w.treasury[w.tag]
                self.assertEqual(state.get("ywc_shu_port_review_due"), 1)
                self.assertEqual(w.days_until_expiry[w.tag]["ywc_shu_port_review_due"], 180)
                w.advance_months(3); w.elapsed_months += 3; w.pulse(arc)
                self.assertNotIn("ywc_shu_port_review_mature", state)
                self.assertEqual(w.days_until_expiry[w.tag]["ywc_shu_port_review_due"], 90)
                self.assertEqual(state.get("ywc_shu_port_pending_event"), 1025)
                self.assertFalse(any(eid == "ywc_shu.1025" for _, eid in w.events))
                popup = w.event_defs["ywc_shu.1025"]
                self.assertFalse(w.conditions(field(popup, "trigger"), w.tag))
                self.assertFalse(next(o["legal"] for o in w.options(popup) if o["option"] == terminal))
                event = w.deliver(arc, "ywc_shu.1025")
                self.assertTrue(state.get("ywc_shu_port_review_mature"))
                self.assertEqual(state["ywc_shu_port_route"], route)
                w.choose(arc, event, terminal)
                self.assertEqual(state.get("ywc_v03_shu_v03_shu_port_treasury_outcome"), outcome)
                self.assertEqual(w.history[w.tag][arc["journals"][0]["id"]], "complete")
                self.assertEqual(w.treasury[w.tag], initial_fee)

    def test_port_real_loss_clears_old_clock_and_starts_fresh_180_day_watch(self):
        for route, outcome, terminal in ((1, 1, "settle_unified"), (2, 2, "settle_share")):
            with self.subTest(route=route):
                w = self.world(); start_m1(w); arc = start_port(w, route)
                state = w.countries[w.tag]
                w.advance_months(3); w.elapsed_months += 3; w.pulse(arc)
                state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if b["type"] != "building_port"]
                w.pulse(arc)
                self.assertNotIn("ywc_shu_port_review_due", state)
                self.assertNotIn("ywc_shu_port_review_mature", state)
                self.assertEqual(state.get("ywc_shu_port_review_interrupted"), 1)
                notice = w.deliver(arc, "ywc_shu.1024")
                state["states"][0]["buildings"].append({'type':'building_port','occupancy':1,'shortage':False,'groups':[]})
                w.choose(arc, notice, "retry_after_repair")
                self.assertEqual(w.days_until_expiry[w.tag]["ywc_shu_port_review_due"], 180)
                w.advance_months(5); w.elapsed_months += 5; w.pulse(arc)
                self.assertNotIn("ywc_shu_port_review_mature", state)
                self.assertEqual(w.days_until_expiry[w.tag]["ywc_shu_port_review_due"], 30)
                final = w.deliver(arc, "ywc_shu.1025")
                self.assertTrue(state.get("ywc_shu_port_review_mature"))
                w.choose(arc, final, terminal)
                self.assertEqual(state.get("ywc_v03_shu_v03_shu_port_treasury_outcome"), outcome)
                self.assertEqual(w.history[w.tag][arc["journals"][0]["id"]], "complete")

    def test_service_both_routes_joint_option_eligibility_and_terminal_are_live(self):
        for route, setup, terminal in (
            (1, [(1010,"court_seal"),(1011,"cap_arrears"),(1012,"professional_list"),(1013,"professional"),(1014,"check_supply")], "settle_service"),
            (2, [(1010,"garrison_seal"),(1011,"local_ledger"),(1012,"incumbents_only"),(1013,"provincial_compact"),(1014,"check_supply")], "settle_service"),
        ):
            with self.subTest(route=route):
                w=self.world();start_m1(w);arc=w.cat["arcs"][1]
                for n,key in setup:play(w,arc,n,key)
                e=w.deliver(arc,"ywc_shu.1015")
                opts={r["option"]:r["legal"] for r in w.options(e)}
                self.assertEqual(opts["joint_recheck"],route==2)
                joint=next(o for k,_,o in e if k=="option" and field(o,"name").endswith(".joint_recheck"))
                with self.assertRaises(AssertionError):
                    w.condition(("any_interest_group","=",[("is_interest_group_type","=","ig_landowners"),("shu_unknown_source_predicate","=","yes")]),w.tag)
                self.assertTrue(opts["accept_appointments"])
                if route==2:
                    w.choose(arc,e,"joint_recheck")
                    e=w.deliver(arc,"ywc_shu.1015")
                    self.assertTrue(next(r["legal"] for r in w.options(e) if r["option"]=="accept_appointments"))
                w.choose(arc,e,"accept_appointments")
                final=w.deliver(arc,"ywc_shu.1017")
                w.choose(arc,final,terminal)
                state=w.countries[w.tag]
                self.assertEqual(state.get("ywc_v03_shu_v03_shu_service_compact_outcome"),route)
                self.assertEqual(w.history[w.tag][arc["journals"][0]["id"]],"complete")

    def test_compensation_weights_evaluate_actual_cash_receipt_default_and_landowner_stance(self):
        w=self.world(landowner_approval=-2);arc=w.cat["arcs"][0]
        play(w,arc,1000,"pilot_state_sichuan")
        play(w,arc,1001,"central_register")
        event=w.deliver(arc,"ywc_shu.1002")
        options={r["option"]:r for r in w.options(event)}
        comp=options["collect_with_compensation"]
        self.assertEqual(w.countries[w.tag]["ywc_shu_fiscal_cost"],1000)
        self.assertEqual(comp["weight"],100)
        # The weight reads actual treasury + reserves against the captured cost; cash-zero leaves both free alternatives available.
        cash0=copy_world(w); cash0.countries[cash0.tag]["gold_reserves"]=-cash0.treasury[cash0.tag]
        got={r["option"]:r for r in cash0.options(event)}
        self.assertEqual(got["collect_with_compensation"]["weight"],0)
        self.assertTrue(got["time_limited_exemption"]["legal"])
        self.assertTrue(got["retain_exemption"]["legal"])
        default=copy_world(w); default.countries[default.tag]["in_default"]=True
        self.assertEqual({r["option"]:r["weight"] for r in default.options(event)}["collect_with_compensation"],0)
        positive=copy_world(w)
        positive.countries[positive.tag]["igs"][0]["approval"]=2
        positive_options={r["option"]:r["weight"] for r in positive.options(event)}
        self.assertEqual(positive_options["collect_with_compensation"],0)
        self.assertEqual(positive_options["retain_exemption"],100)
        before=w.treasury[w.tag]
        w.choose(arc,event,"collect_with_compensation")
        self.assertEqual(w.treasury[w.tag]-before,-2000)
        w.countries[w.tag]["gold_reserves"]=-w.treasury[w.tag]
        self.assertEqual({r["option"]:r["weight"] for r in w.options(event)}["collect_with_compensation"],0)
        self.assertIn("ywc_shu_compensation_paid",w.countries[w.tag])
        before_retry=w.treasury[w.tag]
        w.choose(arc,event,"collect_with_compensation")
        self.assertEqual(w.treasury[w.tag],before_retry)

    def test_ai_evaluator_rejects_unknown_nodes_and_malformed_children(self):
        w=self.world();
        for ai in ([('base','=','1'),('modifier','=',[('trigger','=',[('any_interest_group','=',[('mystery','=', 'yes')])]),('add','=','100')])],
                   [('base','=','1'),('modifier','=',[('trigger','=',[]),('mystery','=','100')])],
                   [('base','=','1'),('modifier','=',[('trigger','=',[]),('add','=',{'bad':1})])],
                   [('base','>=','1')]):
            with self.assertRaises(AssertionError):w.strict_ai_weight(ai)


def copy_world(world):
    import copy
    return copy.deepcopy(world)

if __name__ == "__main__":
    unittest.main()

class StrictPredicateShapeTest(unittest.TestCase):
    def setUp(self):
        self.w=Strict('shu')
        self.tag=self.w.tag
        self.w.countries[self.tag]=facts(-2)

    def test_complete_predicate_shapes_reject_eight_adversarial_cases(self):
        bad=[
            ('gold unknown child',('gold_reserves','>=',[('value','=','0'),('source_unknown','=','yes')])),
            ('gold duplicate value',('gold_reserves','>=',[('value','=','0'),('value','=','9999999')])),
            ('gold value bad operator',('gold_reserves','>=',[('value','>=','0')])),
            ('gold multiply bad operator',('gold_reserves','>=',[('value','=','1000'),('multiply','!=','2')])),
            ('IG false type then unknown',('any_interest_group','=',[('is_interest_group_type','=','ig_nonexistent'),('source_unknown','=','yes')])),
            ('IG false approval then unknown',('any_interest_group','=',[('ig_approval','>','99999'),('source_unknown','=','yes')])),
            ('IG type bad operator',('any_interest_group','=',[('is_interest_group_type','>=','ig_landowners')])),
            ('IG scope bad operator',('any_interest_group','!=',[('is_interest_group_type','=','ig_landowners')])),
        ]
        for label,node in bad:
            with self.subTest(case=label), self.assertRaises(AssertionError):
                self.w.condition(node,self.tag)

    def test_known_true_gold_and_interest_group_comparisons_still_evaluate(self):
        self.assertTrue(self.w.condition(('gold_reserves','>=',[('value','=','1'),('multiply','=','2')]),self.tag))
        self.assertTrue(self.w.condition(('any_interest_group','=',[('is_interest_group_type','=','ig_landowners'),('ig_approval','<=','-2')]),self.tag))

    def test_invalid_ig_shape_is_checked_even_without_world_groups(self):
        self.w.countries[self.tag]['igs']=[]
        with self.assertRaises(AssertionError):
            self.w.condition(('any_interest_group','=',[('is_interest_group_type','=','ig_landowners'),('source_unknown','=','yes')]),self.tag)
