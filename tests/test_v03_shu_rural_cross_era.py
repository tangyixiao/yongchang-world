"""Actual closed SHU fiscal/provincial producers adopted by rural workshop.

Only two approved contracts are consumed. Old numeric region codes are bridged
to the new actual saved StateRef; old paid/waived histories are earned, not seeded.
"""
import copy
import unittest

from test_v03_cross_era import early_result, enter_from_prior
from test_v03_shu_public_runtime import merchant_offer
from test_v03_shu_merchant_obligations import repay
from test_v03_shu_provincial_contract import (
    play as old_play, choose as old_choose, month as old_month,
)
from test_v03_shu_withdrawal_terminals import PREFIX
from test_v03_shu_rural_workshop import (
    P, L, JES, PAID, IDENTITIES, ROUTES, DUTIES, StateRef,
    current_facts, new_world, workshop_arc, state, pilot, office, pop,
    cash, set_cash, world_facts, deliver, play, month, choose, option_legal,
    through_witness, ready_for_review, finish_review,
)


F = "ywc_v03_shu_v03_shu_fiscal_register_"
V = "ywc_v03_shu_v03_shu_provincial_contract_"
A_POSITIVE = (F + "started", F + "settled", F + "outcome",
              "ywc_shu_fiscal_outcome_provincial_share", "ywc_shu_register_resolved",
              "ywc_shu_first_audit", "ywc_shu_second_audit", "ywc_shu_settlement_review_mature",
              "ywc_shu_local_audit_right", "ywc_shu_settlement_mode", "ywc_shu_v03_pilot_state",
              "ywc_shu_merchant_advance_refused")
B_POSITIVE = (V + "started", V + "settled", V + "outcome", "ywc_shu_prov_outcome",
              "ywc_shu_prov_mode", "ywc_shu_prov_charter_ready", "ywc_shu_prov_share_terms",
              "ywc_shu_prov_terms_pilot", "ywc_shu_v03_prov_pilot_state",
              "ywc_shu_prov_review_mature", "ywc_shu_prov_review_streak",
              "ywc_shu_prov_relief_local")


def earned(world):
    return copy.deepcopy({k: v for k, v in state(world).items() if k.startswith("ywc_")})


def set_current(world, route="rural", *, bare=False, staffing=.8, balance=100000):
    """Change ordinary facts in the SAME registered state object, keep all history."""
    s = state(world); prior = earned(world); original = s["states"][0]
    facts = current_facts(route, bare)
    original.clear(); original.update(copy.deepcopy(facts["states"][0]))
    for key, value in facts.items():
        if key != "states" and key != "gold_reserves" and not key.startswith("ywc_"):
            s[key] = copy.deepcopy(value)
    office(world)["occupancy"] = staffing
    set_cash(world, balance)
    assert all(s[k] == value for k, value in prior.items())
    assert s["states"][0] is original


def fiscal_world(kind="shared"):
    w = new_world(); early_result(w, kind)
    self_result = {"shared": 2, "central": 1, "capped": 3, "withdrawn": 4}[kind]
    assert state(w)[F + "outcome"] == self_result and state(w)[F + "settled"] == 1
    set_current(w)
    return w


def earn_province(world, *, national=False, setback=False):
    a = enter_from_prior(world); rows = []
    for n, key in ((1101, "provincial_funding"),
                   (1102, "pay_relief_once" if national else "provincial_self_raise"),
                   (1104, "write_share_terms")):
        before = world.treasury[world.tag]; old_play(world, a, n, key)
        rows.append((n, key, world.treasury[world.tag] - before))
    old_month(world, a, 6); old_play(world, a, 1106, "settle_on_time")
    event = world.deliver(a, "ywc_shu.1107")
    if setback: state(world)["bureaucracy"] = -1
    old_choose(world, a, event, "close_setback" if setback else "close_compromise")
    assert state(world)[V + "settled"] == 1
    assert state(world)[V + "outcome"] == state(world)["ywc_shu_prov_outcome"] == (3 if setback else 2)
    assert state(world)["ywc_shu_prov_mode"] == 2
    return rows


def province_world(waived=False, *, national=False):
    w = fiscal_world("shared" if waived else "central")
    before = w.treasury[w.tag]; rows = earn_province(w, national=national)
    assert w.treasury[w.tag] - before == (-1000 if national else 0) + (0 if waived else -500)
    s = state(w)
    assert s["ywc_shu_prov_meeting_fee"] == 500
    assert s.get("ywc_shu_prov_meeting_fee_waived", 0) == int(waived)
    assert s.get("ywc_shu_prov_meeting_fee_paid", 0) == int(not waived)
    set_current(w)
    w.actual_province_charges = rows
    return w


def preserved_contract(world):
    s = state(world)
    names = set(A_POSITIVE + B_POSITIVE)
    names.update(k for k in s if "compatibility" in k or k.startswith("ywc_shu_merchant_"))
    names.update(("ywc_shu_prov_meeting_fee_paid", "ywc_shu_prov_meeting_fee_waived",
                  "ywc_shu_prov_relief_paid", "ywc_shu_prov_fee_amount"))
    return copy.deepcopy({k: s[k] for k in names if k in s})


class ShuRuralCrossEra(unittest.TestCase):
    def assert_closed(self, w, outcome):
        s = state(w)
        self.assertEqual((s[P + "outcome"], s[L + "outcome"], s[L + "settled"]), (outcome, outcome, 1))
        self.assertTrue(all(j not in w.active[w.tag] for j in JES))

    def assert_old_preserved(self, w, prior):
        self.assertEqual({k: state(w)[k] for k in prior}, prior)

    def test_real_closed_fiscal_local_right_changes_witness_and_signature_at_same_current_half_office(self):
        worlds = [fiscal_world("shared"), fiscal_world("central")]
        for w in worlds: set_current(w, staffing=.5)
        self.assertEqual(world_facts(worlds[0]), world_facts(worlds[1]))
        self.assertEqual(cash(worlds[0]), cash(worlds[1]))
        for index, w in enumerate(worlds):
            with self.subTest(has_A=index == 0):
                prior = preserved_contract(w); a = workshop_arc(w.cat); before = cash(w)
                play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
                self.assertEqual(before - cash(w), 1000)
                e = deliver(w, a, 1112)
                self.assertEqual(option_legal(w, e, "reuse_fiscal_witness"), index == 0)
                self.assertFalse(option_legal(w, e, "new_witness"))
                if index:
                    office(w)["occupancy"] = .8; choose(w, a, e, "new_witness")
                else: choose(w, a, e, "reuse_fiscal_witness")
                signature = deliver(w, a, 1113); office(w)["occupancy"] = .5
                self.assertEqual(option_legal(w, signature, "sign_responsibility"), index == 0)
                if index: office(w)["occupancy"] = .8
                choose(w, a, signature, "sign_responsibility"); play(w, a, 1114, DUTIES["rural"])
                month(w, a, 6); finish_review(w, a)
                self.assertEqual(before - cash(w), 2000); self.assert_closed(w, 1)
                self.assert_old_preserved(w, prior)

    def test_actual_province_paid_and_waived_meetings_both_qualify_but_neither_reduces_new_two_fees(self):
        worlds = [province_world(False), province_world(True), province_world(False, national=True)]
        for w in worlds: set_current(w, staffing=.5)
        self.assertTrue(all(world_facts(w) == world_facts(worlds[0]) for w in worlds))
        for index, w in enumerate(worlds):
            with self.subTest(old_meeting=index):
                prior = preserved_contract(w); before = cash(w)
                a = ready_for_review(w, witness="reuse_province_witness")
                self.assertEqual(before - cash(w), 1000)
                month(w, a, 6); finish_review(w, a)
                self.assertEqual(before - cash(w), 2000)
                self.assert_closed(w, 1); self.assert_old_preserved(w, prior)

    def test_each_genuinely_earned_fiscal_core_component_is_required_and_new_witness_remains_available(self):
        for missing in A_POSITIVE:
            with self.subTest(missing=missing):
                w = fiscal_world(); del state(w)[missing]
                a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
                e = deliver(w, a, 1112)
                self.assertFalse(option_legal(w, e, "reuse_fiscal_witness"))
                self.assertTrue(option_legal(w, e, "new_witness"))
        # The alternate merchant contract is actually advanced and repaid, never seeded.
        w = new_world(); a, e = merchant_offer(w); before = w.treasury[w.tag]
        old_choose(w, a, e, "accept_port_advance"); principal = state(w)["ywc_shu_merchant_principal"]
        self.assertEqual(w.treasury[w.tag] - before, principal)
        before = w.treasury[w.tag]; repay(w); self.assertAlmostEqual(w.treasury[w.tag] - before, -principal)
        for n, key in ((1006, "settle_as_provincial"), (1007, "provincial_retention"),
                       (1008, "review_in_peace"), (1009, "confirm_provincial_share")):
            old_play(w, a, n, key)
        set_current(w); a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
        e = deliver(w, a, 1112); self.assertTrue(option_legal(w, e, "reuse_fiscal_witness"))
        for missing in ("ywc_shu_merchant_advance", "ywc_shu_merchant_consultation",
                        "ywc_shu_merchant_principal", "ywc_shu_merchant_advance_repaid"):
            v = copy.deepcopy(w); del state(v)[missing]
            self.assertFalse(option_legal(v, e, "reuse_fiscal_witness"), missing)

    def test_each_province_component_and_real_meeting_branch_is_required_including_waiver_A(self):
        for waived in (False, True):
            names = (*B_POSITIVE, "ywc_shu_prov_meeting_fee_waived") if waived else (
                *B_POSITIVE, "ywc_shu_prov_meeting_fee_paid", "ywc_shu_prov_meeting_fee")
            for missing in names:
                with self.subTest(waived=waived, missing=missing):
                    w = province_world(waived); del state(w)[missing]
                    a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
                    e = deliver(w, a, 1112)
                    self.assertFalse(option_legal(w, e, "reuse_province_witness"))
                    self.assertTrue(option_legal(w, e, "new_witness"))
        w = province_world(True); del state(w)["ywc_shu_second_audit"]
        a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
        e = deliver(w, a, 1112); self.assertFalse(option_legal(w, e, "reuse_province_witness"))
        for missing in ("ywc_shu_prov_relief_paid", "ywc_shu_prov_fee_amount"):
            w = province_world(False, national=True)
            a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
            e = deliver(w, a, 1112); del state(w)[missing]
            self.assertFalse(option_legal(w, e, "reuse_province_witness"), missing)
        # Malformed negative ONLY: a genuine paid history cannot also claim waiver.
        # The contradictory marker never earns or advances any business action.
        w = province_world(False); a = workshop_arc(w.cat)
        play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
        e = deliver(w, a, 1112); state(w)["ywc_shu_prov_meeting_fee_waived"] = 1
        self.assertFalse(option_legal(w, e, "reuse_province_witness"))

    def test_old_region_is_bridged_inside_new_exact_pilot_and_later_same_region_state_cannot_replace_it(self):
        for region, eligible in (("s:STATE_SICHUAN", True), ("s:STATE_CHONGQING", False)):
            with self.subTest(region=region):
                w = fiscal_world(); s = state(w); original = s["states"][0]
                original["owner"] = "CHI"
                replacement = copy.deepcopy(original); replacement.update(owner="SHU", region=region)
                s["states"].append(replacement)
                a = workshop_arc(w.cat); play(w, a, 1110, ROUTES["rural"]); play(w, a, 1111, "pay_admin")
                self.assertIs(pilot(w), replacement); self.assertIsInstance(s[P + "pilot"], StateRef)
                self.assertEqual(s["ywc_shu_v03_pilot_state"], 1)
                e = deliver(w, a, 1112)
                self.assertEqual(option_legal(w, e, "reuse_fiscal_witness"), eligible)
                if eligible:
                    choose(w, a, e, "reuse_fiscal_witness")
                    s["states"].append(copy.deepcopy(replacement)); replacement["owner"] = "CHI"
                    sign = deliver(w, a, 1113)
                    self.assertFalse(option_legal(w, sign, "sign_responsibility"))

    def test_adopted_fiscal_source_is_live_at_signature_acceptance_observation_bill_request_and_close(self):
        for node in (1113, 1114, 1115, 1116, 1117):
            with self.subTest(node=node):
                w = fiscal_world(); a = through_witness(w, witness="reuse_fiscal_witness")
                if node > 1113: play(w, a, 1113, "sign_responsibility")
                if node > 1114: play(w, a, 1114, DUTIES["rural"])
                if node >= 1115: month(w, a, 6)
                if node >= 1116: play(w, a, 1115, "pay_survey")
                if node == 1117: play(w, a, 1116, "request_full")
                e = deliver(w, a, node); before = cash(w); del state(w)["ywc_shu_first_audit"]
                key = {1113: "sign_responsibility", 1114: DUTIES["rural"], 1115: "pay_survey",
                       1116: "request_full", 1117: "close_full"}[node]
                self.assertFalse(option_legal(w, e, key)); self.assertEqual(cash(w), before)
                if node == 1115:
                    month(w, a); self.assertEqual(state(w)[P + "review_streak"], 0)
                    self.assertIn(P + "review_interrupted", state(w))
                if node == 1116:
                    self.assertTrue(option_legal(w, e, "request_setback"))
        # Ordinary current office loss is also real, independent of historical deletion.
        w = fiscal_world(); a = ready_for_review(w, witness="reuse_fiscal_witness")
        month(w, a, 3); pop(w, "bureaucrats")["employed"] = False; month(w, a)
        self.assertEqual(state(w)[P + "review_streak"], 0)

    def test_adopted_province_source_is_rechecked_at_signature_acceptance_and_paid_late_boundary(self):
        for waived in (False, True):
            for node in (1113, 1114, 1116):
                with self.subTest(waived=waived, node=node):
                    w = province_world(waived); a = through_witness(w, witness="reuse_province_witness")
                    if node > 1113: play(w, a, 1113, "sign_responsibility")
                    if node > 1114:
                        play(w, a, 1114, DUTIES["rural"]); month(w, a, 6); play(w, a, 1115, "pay_survey")
                    e = deliver(w, a, node)
                    del state(w)["ywc_shu_prov_meeting_fee_waived" if waived else "ywc_shu_prov_meeting_fee_paid"]
                    key = {1113: "sign_responsibility", 1114: DUTIES["rural"], 1116: "request_full"}[node]
                    self.assertFalse(option_legal(w, e, key))
                    if node == 1116:
                        paid = {k: state(w)[k] for pair in PAID.values() for k in pair}
                        choose(w, a, e, "request_setback"); play(w, a, 1117, "close_setback")
                        self.assert_closed(w, 3); self.assertEqual({k: state(w)[k] for k in paid}, paid)

    def test_real_old_conservative_withdrawn_setback_and_absence_all_allow_independent_new_finite(self):
        worlds = [fiscal_world("capped"), fiscal_world("withdrawn"), new_world()]
        w = fiscal_world("central"); earn_province(w, setback=True); worlds.append(w)
        for w in worlds:
            with self.subTest(old_result=state(w).get(F + "outcome"), province=state(w).get(V + "outcome")):
                prior = preserved_contract(w); set_current(w, bare=True, staffing=.25)
                before = cash(w); a = ready_for_review(w, limited=True)
                month(w, a, 6); finish_review(w, a, 2)
                self.assertEqual(before - cash(w), 1000)
                self.assert_closed(w, 2); self.assert_old_preserved(w, prior)

    def test_paid_finite_resign_replaces_adopted_old_source_honestly_and_retains_actual_money(self):
        for source in ("fiscal", "province"):
            with self.subTest(source=source):
                w = fiscal_world() if source == "fiscal" else province_world(True)
                a = ready_for_review(w, witness="reuse_fiscal_witness" if source == "fiscal" else "reuse_province_witness")
                month(w, a, 6); play(w, a, 1115, "pay_survey")
                paid = {k: state(w)[k] for pair in PAID.values() for k in pair}
                play(w, a, 1116, "recount_1115"); office(w)["occupancy"] = .25
                play(w, a, 1115, "narrow_and_recount")
                del state(w)["ywc_shu_first_audit" if source == "fiscal" else "ywc_shu_prov_share_terms"]
                s = state(w); self.assertEqual((s[P + "mode"], s[P + "target"], s[P + "review_streak"]), (3, 2, 0))
                for triple in IDENTITIES.values(): self.assertEqual(tuple(s[k] for k in triple), (3, 2, s[P + "pilot"]))
                month(w, a, 5); self.assertNotIn(P + "review_mature", s); month(w, a)
                before = cash(w); finish_review(w, a, 2)
                self.assertEqual(cash(w), before); self.assertEqual({k: s[k] for k in paid}, paid)
                self.assert_closed(w, 2)

    def test_real_old_military_installments_and_repaid_merchant_ledger_are_preserved(self):
        w = new_world(); a = w.cat["arcs"][0]
        for n, key in (*PREFIX, (1007, "provincial_retention"), (1008, "review_in_peace"),
                       (1009, "confirm_provincial_share")):
            old_play(w, a, n, "pay_partial_advance" if n == 1003 else key)
        s = state(w); self.assertEqual(s[F + "outcome"], 2)
        self.assertEqual((s["ywc_shu_military_payer"], s["ywc_shu_military_installments_paid"]), (1, 1))
        set_current(w); before = cash(w); installment = s["ywc_shu_military_installment"]
        a = ready_for_review(w, witness="reuse_fiscal_witness"); month(w, a, 6); finish_review(w, a)
        self.assertEqual(s["ywc_shu_military_installments_paid"], 12)
        self.assertEqual(s["ywc_shu_military_contract_fulfilled"], 1)
        self.assertAlmostEqual(before - cash(w), 2000 + 11 * installment)
        self.assert_closed(w, 1)
        w = new_world(); a, e = merchant_offer(w); old_choose(w, a, e, "accept_port_advance"); repay(w)
        for n, key in ((1006, "settle_as_provincial"), (1007, "provincial_retention"),
                       (1008, "review_in_peace"), (1009, "confirm_provincial_share")):
            old_play(w, a, n, key)
        set_current(w); prior = preserved_contract(w)
        a = ready_for_review(w, witness="reuse_fiscal_witness"); month(w, a, 6); finish_review(w, a)
        self.assert_old_preserved(w, prior); self.assert_closed(w, 1)


if __name__ == "__main__":
    unittest.main()
