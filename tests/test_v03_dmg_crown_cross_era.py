"""Earn earlier DMG policies natively, then consume them in the crown story.

Earlier outcomes, paid costs, settled results and receipts are produced by the
original event and journal ASTs in the same world. Later fixture updates change
only current laws, employees, offices, groups, public finance and ownership.
"""
import copy
import unittest

from lan_public_runtime import LanPublicWorld
from test_v03_dmg_representative_crown import (
    JES, L, P, choose, crown_arc, current_facts, finish_review, month, new_world,
    office, office_pop, option_legal, play, ready_for_review, world_facts,
)
from test_v03_dmg_school_cross_era import (
    COMMON_ESTABLISHED, COMMON_TERRITORIAL, COURT_ESTABLISHED, COURT_LOCAL,
    LAND_MIXED,
)


COMMON = "v03_dmg_common_subjects"
LAND = "v03_dmg_two_land_titles"
COURT = "v03_dmg_court_provinces"
CURRENT_KEYS = (
    "laws", "institutions", "states", "igs", "literacy_rate", "bureaucracy",
    "net_fixed_income", "authority", "legitimacy", "country_has_voting_franchise",
    "is_at_war", "in_default", "yearly_gross_income", "scaled_debt", "is_subject",
    "army_size",
)
LAND_INDIVIDUAL = tuple((number, "individual_appeal" if number == 1014 else key)
                        for number, key in LAND_MIXED)


def early_arc(world, slug):
    return next(arc for arc in world.cat["arcs"] if arc["slug"] == slug)


def earn(world, slug, plan):
    """Delivery advances the real calendar and runs each native monthly pulse."""
    arc = early_arc(world, slug)
    for number, key in plan:
        play(world, arc, number, key)
    return arc


def set_current_facts(world, route="constitutional", bare=False, cash=10000):
    """Keep the country's earned business dictionary and replace engine facts."""
    state = world.countries[world.tag]
    current = current_facts(route, bare)
    if not bare:
        province = current["states"][0]
        farmer = copy.deepcopy(province["pops"][0])
        farmer.update(type="farmers", workplace=next(building for building in
            province["buildings"] if building["type"] == "building_maize_farm"))
        province["pops"].append(farmer)
    state.update(copy.deepcopy({key: current[key] for key in CURRENT_KEYS}))
    # Native gold_reserves reads this factual reserve plus actual paid treasury.
    state["gold_reserves"] = cash - world.treasury[world.tag]


def current_snapshot(world):
    state = world.countries[world.tag]
    result = copy.deepcopy({key: state[key] for key in CURRENT_KEYS})
    result["available_cash"] = state["gold_reserves"] + world.treasury[world.tag]
    return result


def ready_after_hearing(world, arc, limited=False):
    for number, key in ((1113, "sign_appointment"), (1114, "pay_share"),
                        (1115, "write_limited_statement" if limited else "write_statement"),
                        (1116, "handoff_continuity")):
        play(world, arc, number, key)
    return arc


class DmgCrownCrossEra(unittest.TestCase):
    def world(self):
        world = new_world("consultative")
        self.assertIsInstance(world, LanPublicWorld)
        state = world.countries[world.tag]
        # Actual original histories have full offices plus employed service,
        # agricultural and university populations in the same owned Luzon.
        office(world)["occupancy"] = 1
        province = state["states"][0]
        by_type = {building["type"]: building for building in province["buildings"]}
        for kind, building in (("farmers", "building_maize_farm"),
                               ("officers", "building_barrack"),
                               ("academics", "building_university")):
            pop = copy.deepcopy(office_pop(world))
            pop.update(type=kind, workplace=by_type[building])
            province["pops"].append(pop)
        state["laws"].append("law_total_separation")
        # Earlier common-subjects uses its actual appointed-charter path under
        # the then-current autocracy. Later census voting is a factual change.
        state["country_has_voting_franchise"] = False
        for slug in (COMMON, LAND, COURT):
            self.assertNotIn(f"ywc_v03_dmg_{slug}_started", state)
            self.assertNotIn(f"ywc_v03_dmg_{slug}_settled", state)
        self.assertNotIn(P + "registry_paid", state)
        return world

    def assert_old_closed(self, world, slug, outcome, failed=False):
        state = world.countries[world.tag]
        self.assertEqual(state[f"ywc_v03_dmg_{slug}_settled"], 1)
        outcome_key = {
            COMMON: f"ywc_v03_dmg_{COMMON}_outcome",
            LAND: "ywc_dmg_titles_outcome",
            COURT: "ywc_dmg_court_outcome",
        }[slug]
        self.assertEqual(state[outcome_key], outcome)
        statuses = [world.history[world.tag].get(journal["id"])
                    for journal in early_arc(world, slug)["journals"]]
        if failed:
            self.assertIn("failed", statuses)
        else:
            self.assertTrue(all(status == "complete" for status in statuses), statuses)
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))

    def assert_crown_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))

    def test_two_real_old_policy_bundles_change_registry_and_hearing_under_identical_current_facts(self):
        worlds = [self.world(), self.world()]
        for world, common_plan, land_plan in (
            (worlds[0], COMMON_ESTABLISHED, LAND_MIXED),
            (worlds[1], COMMON_TERRITORIAL, LAND_INDIVIDUAL),
        ):
            earn(world, COMMON, common_plan)
            self.assert_old_closed(world, COMMON, 1 if world is worlds[0] else 2)
            earn(world, LAND, land_plan)
            self.assert_old_closed(world, LAND, 1)
            set_current_facts(world)
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        arcs = []
        for world, expected in zip(worlds, (500, 1000)):
            arc = crown_arc(world.cat)
            arcs.append(arc)
            before = world.treasury[world.tag]
            play(world, arc, 1110, "constitutional_crown")
            play(world, arc, 1111, "pay_registry")
            self.assertEqual(world.treasury[world.tag] - before, -expected)
            self.assertEqual(world.countries[world.tag][P + "registry_paid_amount"], expected)
            office(world)["occupancy"] = .25
        # Equalize factual reserves again after the different real payments.
        for world in worlds:
            world.countries[world.tag]["gold_reserves"] = 10000 - world.treasury[world.tag]
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        hearings = [world.deliver(arc, "ywc_dmg.1112")
                    for world, arc in zip(worlds, arcs)]
        self.assertTrue(option_legal(worlds[0], hearings[0], "reuse_land_hearing"))
        self.assertFalse(option_legal(worlds[0], hearings[0], "new_hearing"))
        self.assertFalse(option_legal(worlds[1], hearings[1], "reuse_land_hearing"))
        self.assertFalse(option_legal(worlds[1], hearings[1], "new_hearing"))
        choose(worlds[0], arcs[0], hearings[0], "reuse_land_hearing")
        office(worlds[1])["occupancy"] = .5
        self.assertTrue(option_legal(worlds[1], hearings[1], "new_hearing"))
        choose(worlds[1], arcs[1], hearings[1], "new_hearing")
        hearing_kinds = [world.countries[world.tag][P + "hearing"] for world in worlds]
        self.assertEqual(hearing_kinds, [1, 2])
        for world, arc, inherited_hearing in zip(worlds, arcs, (True, False)):
            # A full constitutional appointment still needs its real .8 office.
            office(world)["occupancy"] = .8
            ready_after_hearing(world, arc)
            office(world)["occupancy"] = .25
            # Before any new finite agreement, real old land terms retain
            # their quarter-office hearing; the fresh full hearing needs .5.
            self.assertEqual(world.conditions(world.trigger_defs[P + "hearing_ready"],
                                               world.tag), inherited_hearing)
            month(world, arc)
            interrupted = world.deliver(arc, "ywc_dmg.1117")
            self.assertTrue(option_legal(world, interrupted, "narrow_and_recount"))
            choose(world, arc, interrupted, "narrow_and_recount")
            self.assertEqual(world.countries[world.tag][P + "target"], 2)
            # Explicit narrowing signs a new finite hearing, superseding both
            # old kinds instead of silently caching an earlier entitlement.
            self.assertEqual(world.countries[world.tag][P + "hearing"], 3)
            month(world, arc, 6)
            finish_review(world, arc, outcome=2)
            self.assert_crown_closed(world, 2)
        left, right = [world.countries[world.tag] for world in worlds]
        self.assertEqual((left[P + "hearing"], right[P + "hearing"]), (3, 3))
        self.assertEqual((left[P + "share_paid_amount"], right[P + "share_paid_amount"]), (1000, 1000))
        self.assertEqual((left[P + "review_paid_amount"], right[P + "review_paid_amount"]), (500, 500))

    def test_real_common_positive_outcome_without_earned_translation_duty_is_not_a_discount(self):
        world = self.world()
        earn(world, COMMON, COMMON_ESTABLISHED)
        self.assert_old_closed(world, COMMON, 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_translation_duty"], 1)
        del state["ywc_dmg_translation_duty"]
        set_current_facts(world)
        arc = crown_arc(world.cat)
        play(world, arc, 1110, "constitutional_crown")
        before = world.treasury[world.tag]
        play(world, arc, 1111, "pay_registry")
        self.assertEqual(world.treasury[world.tag] - before, -1000)
        self.assertEqual(state[P + "registry_paid_amount"], 1000)
        self.assertNotIn(P + "registry_source_common", state)
        self.assertEqual(state[f"ywc_v03_dmg_{COMMON}_outcome"], 1)
        play(world, arc, 1112, "withdraw")

    def test_real_common_unpaid_discount_reads_current_acceptance_and_paid_price_is_retained(self):
        for pay_before_loss in (False, True):
            with self.subTest(pay_before_loss=pay_before_loss):
                world = self.world()
                earn(world, COMMON, COMMON_ESTABLISHED)
                self.assert_old_closed(world, COMMON, 1)
                set_current_facts(world)
                state = world.countries[world.tag]
                arc = crown_arc(world.cat)
                play(world, arc, 1110, "constitutional_crown")
                event = world.deliver(arc, "ywc_dmg.1111")
                state["gold_reserves"] = 500 - world.treasury[world.tag]
                self.assertTrue(option_legal(world, event, "pay_registry"))
                if pay_before_loss:
                    choose(world, arc, event, "pay_registry")
                    before = world.treasury[world.tag]
                    office_pop(world)["acceptance"] = 4
                    month(world, arc)
                    self.assertEqual(world.treasury[world.tag], before)
                    self.assertEqual(state[P + "registry_paid_amount"], 500)
                    play(world, arc, 1112, "withdraw")
                else:
                    office_pop(world)["acceptance"] = 4
                    self.assertFalse(option_legal(world, event, "pay_registry"))
                    self.assertEqual(state["ywc_dmg_outcome_common_qualification"], 1)
                    state["gold_reserves"] = 1000 - world.treasury[world.tag]
                    self.assertTrue(option_legal(world, event, "pay_registry"))
                    before = world.treasury[world.tag]
                    choose(world, arc, event, "pay_registry")
                    self.assertEqual(world.treasury[world.tag] - before, -1000)
                    self.assertNotIn(P + "registry_source_common", state)
                    play(world, arc, 1112, "withdraw")

    def test_genuine_court_joint_contract_halves_federal_share_without_paying_other_bills(self):
        for previous, expected in (("joint", 750), ("local", 1500), ("absent", 1500)):
            with self.subTest(previous=previous):
                world = self.world()
                if previous != "absent":
                    earn(world, COURT, COURT_ESTABLISHED if previous == "joint" else COURT_LOCAL)
                    self.assert_old_closed(world, COURT, 1 if previous == "joint" else 3)
                set_current_facts(world, "federal")
                office(world)["occupancy"] = 1
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                arc = ready_for_review(world, "federal")
                self.assertEqual(state[P + "registry_paid_amount"], 1000)
                self.assertEqual(state[P + "share_paid_amount"], expected)
                self.assertEqual(P + "share_source_court" in state, previous == "joint")
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(state[P + "review_paid_amount"], 1000)
                self.assertEqual(world.treasury[world.tag] - before, -2000 - expected)
                self.assert_crown_closed(world, 1)

    def test_court_outcome_alone_without_earned_joint_appointment_cannot_discount_the_share(self):
        world = self.world()
        earn(world, COURT, COURT_ESTABLISHED)
        self.assert_old_closed(world, COURT, 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_joint_appointment_clause"], 1)
        del state["ywc_dmg_joint_appointment_clause"]
        set_current_facts(world, "federal")
        office(world)["occupancy"] = 1
        arc = ready_for_review(world, "federal")
        self.assertEqual(state[P + "share_paid_amount"], 1500)
        self.assertNotIn(P + "share_source_court", state)
        self.assertEqual(state["ywc_dmg_court_outcome"], 1)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assert_crown_closed(world, 1)

    def test_court_unpaid_share_reprices_on_current_office_loss_and_does_not_recharge_paid_share(self):
        for pay_before_loss in (False, True):
            with self.subTest(pay_before_loss=pay_before_loss):
                world = self.world()
                earn(world, COURT, COURT_ESTABLISHED)
                self.assert_old_closed(world, COURT, 1)
                set_current_facts(world, "federal")
                office(world)["occupancy"] = 1
                arc = crown_arc(world.cat)
                for number, key in ((1110, "united_republic"), (1111, "pay_registry"),
                                    (1112, "new_hearing"), (1113, "sign_appointment")):
                    play(world, arc, number, key)
                state = world.countries[world.tag]
                event = world.deliver(arc, "ywc_dmg.1114")
                state["gold_reserves"] = 750 - world.treasury[world.tag]
                self.assertTrue(option_legal(world, event, "pay_share"))
                if pay_before_loss:
                    choose(world, arc, event, "pay_share")
                    before = world.treasury[world.tag]
                    office(world)["occupancy"] = .5
                    month(world, arc)
                    self.assertEqual(world.treasury[world.tag], before)
                    self.assertEqual(state[P + "share_paid_amount"], 750)
                    play(world, arc, 1115, "withdraw")
                else:
                    office(world)["occupancy"] = .5
                    self.assertFalse(option_legal(world, event, "pay_share"))
                    state["gold_reserves"] = 1500 - world.treasury[world.tag]
                    self.assertTrue(option_legal(world, event, "pay_share"))
                    before = world.treasury[world.tag]
                    choose(world, arc, event, "pay_share")
                    self.assertEqual(world.treasury[world.tag] - before, -1500)
                    self.assertNotIn(P + "share_source_court", state)
                    play(world, arc, 1115, "withdraw")

    def test_land_positive_outcome_without_paid_compensation_cannot_supply_the_old_hearing(self):
        world = self.world()
        earn(world, LAND, LAND_MIXED)
        self.assert_old_closed(world, LAND, 1)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        del state["ywc_dmg_titles_compensation_paid"]
        set_current_facts(world)
        office(world)["occupancy"] = .25
        arc = crown_arc(world.cat)
        play(world, arc, 1110, "narrow_consultation")
        play(world, arc, 1111, "pay_registry")
        hearing = world.deliver(arc, "ywc_dmg.1112")
        self.assertFalse(option_legal(world, hearing, "reuse_land_hearing"))
        self.assertFalse(option_legal(world, hearing, "new_hearing"))
        self.assertEqual(state["ywc_dmg_titles_outcome"], 1)
        self.assertTrue(option_legal(world, hearing, "limited_hearing"))
        choose(world, arc, hearing, "limited_hearing")
        ready_after_hearing(world, arc, limited=True)
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assert_crown_closed(world, 2)

    def test_real_land_hearing_rechecks_agriculture_at_signature_and_during_observation(self):
        world = self.world()
        earn(world, LAND, LAND_MIXED)
        self.assert_old_closed(world, LAND, 1)
        set_current_facts(world)
        office(world)["occupancy"] = .25
        arc = crown_arc(world.cat)
        for number, key in ((1110, "narrow_consultation"), (1111, "pay_registry"),
                            (1112, "reuse_land_hearing")):
            play(world, arc, number, key)
        state = world.countries[world.tag]
        farmer = next(pop for pop in state["states"][0]["pops"] if pop["type"] == "farmers")
        event = world.deliver(arc, "ywc_dmg.1113")
        farmer["employed"] = False
        self.assertFalse(option_legal(world, event, "sign_appointment"))
        self.assertEqual(state["ywc_dmg_titles_compensation_paid"], 1)
        farmer["employed"] = True
        choose(world, arc, event, "sign_appointment")
        for number, key in ((1114, "pay_share"), (1115, "write_limited_statement"),
                            (1116, "handoff_continuity")):
            play(world, arc, number, key)
        month(world, arc, 2)
        self.assertEqual(state[P + "review_streak"], 2)
        farmer["employed"] = False
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_running", state)
        farmer["employed"] = True
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        event = world.deliver(arc, "ywc_dmg.1117")
        self.assertTrue(option_legal(world, event, "restart_review"))
        choose(world, arc, event, "restart_review")
        month(world, arc, 6)
        finish_review(world, arc, outcome=2)
        self.assert_crown_closed(world, 2)

    def test_actual_old_2_3_4_5_and_absence_have_an_explicit_limited_current_end(self):
        for previous in (2, 3, 4, 5, None):
            with self.subTest(previous=previous):
                world = self.world()
                state = world.countries[world.tag]
                if previous == 2:
                    earn(world, COMMON, COMMON_TERRITORIAL)
                    self.assert_old_closed(world, COMMON, 2)
                elif previous == 3:
                    earn(world, COURT, COURT_LOCAL)
                    self.assert_old_closed(world, COURT, 3)
                elif previous == 4:
                    arc = early_arc(world, COMMON)
                    play(world, arc, 1000, "withdraw")
                    self.assert_old_closed(world, COMMON, 4, failed=True)
                elif previous == 5:
                    arc = earn(world, COMMON, COMMON_ESTABLISHED[:-1])
                    final = world.deliver(arc, "ywc_dmg.1009")
                    for pop in state["states"][0]["pops"]:
                        pop["acceptance"] = 4
                    self.assertFalse(option_legal(world, final, "common_qualification"))
                    choose(world, arc, final, "limited_settlement")
                    self.assert_old_closed(world, COMMON, 5)
                set_current_facts(world, bare=True)
                before_facts = world_facts(world)
                before_cash = world.treasury[world.tag]
                arc = ready_for_review(world, limited=True)
                self.assertEqual(state[P + "target"], 2)
                self.assertNotIn(P + "registry_source_common", state)
                self.assertNotIn(P + "share_source_court", state)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assertEqual(world.treasury[world.tag] - before_cash, -1500)
                self.assertEqual(world_facts(world), before_facts)
                self.assert_crown_closed(world, 2)

    def test_real_common_history_cannot_pay_a_registry_in_a_foreign_owned_pilot(self):
        world = self.world()
        earn(world, COMMON, COMMON_ESTABLISHED)
        self.assert_old_closed(world, COMMON, 1)
        set_current_facts(world)
        arc = crown_arc(world.cat)
        play(world, arc, 1110, "constitutional_crown")
        event = world.deliver(arc, "ywc_dmg.1111")
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "PHI"
        before = world.treasury[world.tag]
        self.assertFalse(option_legal(world, event, "pay_registry"))
        self.assertTrue(option_legal(world, event, "withdraw"))
        choose(world, arc, event, "withdraw")
        self.assertEqual(world.treasury[world.tag], before)
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(world.history[world.tag][JES[0]], "failed")
        self.assertEqual((state["ywc_v03_active_arc_count"],
                          state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
