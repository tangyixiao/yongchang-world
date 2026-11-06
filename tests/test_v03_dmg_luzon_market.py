"""DMG market stories run generated native ASTs against actual market objects."""
import copy
import unittest

from dmg_market_runtime import DmgMarketWorld, market_test_facts
from shu_kor_strict_review_runtime import facts
from test_v03_shu_provincial_contract import choose, force_option, option_legal

SLUG = "v03_dmg_luzon_border_market"
JES = ("ywc_je_v03_dmg_luzon_market_terms", "ywc_je_v03_dmg_luzon_market_review")
P = "ywc_dmg_market_"
ROUTES = {"controlled": "controlled_market", "multilateral": "multilateral_ports",
          "guarded": "guarded_boundary"}


def market_arc(catalog):
    return next(arc for arc in catalog["arcs"] if arc["slug"] == SLUG)


def new_world(bare=False, access="treaty"):
    data = market_test_facts()
    world = DmgMarketWorld()
    state = facts()
    state.update({name: data["countries"]["DMG"][name] for name in
                  ("market_id", "alive", "junior_in_customs_union")})
    state["literacy_rate"] = .35
    province = state["states"][0]
    province.update(owner="DMG", region="s:STATE_LUZON", market_access=.9)
    by_type = {building["type"]: building for building in province["buildings"]}
    trade = {"type": "building_trade_center", "occupancy": .8,
             "shortage": False, "groups": [], "level": 1}
    province["buildings"].append(trade)
    for kind, building in (
        ("laborers", by_type["building_port"]), ("farmers", by_type["building_maize_farm"]),
        ("officers", by_type["building_barrack"]), ("academics", by_type["building_university"]),
    ):
        pop = copy.deepcopy(province["pops"][0])
        pop.update(type=kind, workplace=building)
        province["pops"].append(pop)
    if bare:
        state["laws"] = ["law_monarchy", "law_isolationism", "law_serfdom", "law_no_schools"]
        state["institutions"] = {}
        province["market_access"] = .35
        province["pops"] = [p for p in province["pops"] if p["type"] in ("bureaucrats", "farmers")]
        province["buildings"] = [by_type["building_government_administration"],
                                 by_type["building_maize_farm"]]
        by_type["building_government_administration"]["occupancy"] = .5
        by_type["building_maize_farm"]["occupancy"] = .25
    data["countries"]["DMG"] = state
    data["markets"]["m_dmg"]["imports_reliance"] = {"m_phi": .02, "m_jhg": .02, "m_lan": .02}
    data["relations"] = {("DMG", partner): 25 for partner in ("PHI", "JHG", "LAN")}
    if access == "treaty":
        data["treaties"] = [
            {"participants": ["DMG", owner], "articles": [
                {"type": "trade_privilege", "source_country": owner, "target_country": "DMG"}]}
            for owner in ("SPA", "JHG", "LAN")]
    elif access == "same_market":
        for partner in ("PHI", "JHG", "LAN"):
            data["countries"][partner]["market_id"] = "m_dmg"
        data["treaties"] = []
        data["markets"]["m_dmg"]["imports_reliance"] = {}
    elif access == "none":
        data["treaties"] = []
        data["markets"]["m_dmg"]["imports_reliance"] = {}
    else:
        raise ValueError(access)
    world.countries = data["countries"]
    world.configure_market_facts(**{key: data[key] for key in
        ("markets", "treaties", "draft_treaties", "wars", "pacts", "relations")})
    world.run("ywc_v03_initialize_country", world.tag)
    return world


def play(world, arc, number, key):
    event = world.deliver(arc, f"ywc_dmg.{number}")
    choose(world, arc, event, key)
    return event


def month(world, arc, count=1):
    for _ in range(count):
        world.advance_months(1)
        world.elapsed_months += 1
        world.pulse(arc)


def ready_for_review(world, route="controlled", limited=False, hearing="write_new_hearing"):
    arc = market_arc(world.cat)
    for number, key in (
        (1100, ROUTES[route]), (1101, "pay_setup"),
        (1102, "limit_local_livelihood" if limited else "confirm_existing_access"),
        (1103, hearing), (1104, "sign_six_month_terms"),
    ):
        play(world, arc, number, key)
    assert world.history[world.tag][JES[0]] == "complete"
    assert JES[1] in world.active[world.tag]
    return arc


def finish_review(world, arc, route="controlled", limited=False):
    play(world, arc, 1105, "pay_review_bill")
    play(world, arc, 1106, "retain_limited" if limited else "retain_" + route)
    return play(world, arc, 1107, "close_compromise" if limited else "close_established")


class DmgLuzonMarket(unittest.TestCase):
    def test_late_loss_can_close_an_honest_setback_and_cannot_replay_or_release_twice(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        play(world, arc, 1105, "pay_review_bill")
        event = world.deliver(arc, "ywc_dmg.1106")
        world.treaties = []
        self.assertFalse(option_legal(world, event, "retain_controlled"))
        self.assertTrue(option_legal(world, event, "record_setback"))
        choose(world, arc, event, "record_setback")
        final = world.deliver(arc, "ywc_dmg.1107")
        self.assertFalse(option_legal(world, final, "close_established"))
        self.assertTrue(option_legal(world, final, "close_setback"))
        choose(world, arc, final, "close_setback")
        self.assertEqual(state[P + "outcome"], 3)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        before = copy.deepcopy(world.countries)
        for key in ("close_setback", "close_established", "withdraw", "recount_changed"):
            force_option(world, final, key)
        world.run("ywc_dmg_market_release_once", world.tag)
        world.refresh(arc)
        self.assertEqual(world.countries, before)
        # Recording a mature, paid setback resolves the review honestly;
        # withdrawal alone uses the failed lifecycle exit.
        self.assertEqual(world.history[world.tag][JES[1]], "complete")

    def test_late_recovery_rejects_cached_setback_and_requires_a_fresh_requested_outcome(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        play(world, arc, 1105, "pay_review_bill")
        event = world.deliver(arc, "ywc_dmg.1106")
        treaties = copy.deepcopy(world.treaties)
        world.treaties = []
        choose(world, arc, event, "record_setback")
        final = world.deliver(arc, "ywc_dmg.1107")
        world.treaties = treaties
        before = copy.deepcopy(world.countries)
        self.assertFalse(option_legal(world, final, "close_setback"))
        self.assertFalse(option_legal(world, final, "close_established"))
        force_option(world, final, "close_setback")
        self.assertEqual(world.countries, before)
        choose(world, arc, final, "recount_changed")
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "requested_outcome", state)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)

    def test_three_arc_capacity_blocks_market_admission_without_partial_claim(self):
        world = new_world()
        state = world.countries[world.tag]
        for arc in world.cat["arcs"][:3]:
            world.refresh(arc)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
        arc = market_arc(world.cat)
        world.refresh(arc)
        self.assertNotIn(JES[0], world.active[world.tag])
        self.assertNotIn("ywc_v03_dmg_v03_dmg_luzon_border_market_started", state)
        self.assertNotIn(P + "budget", state)
        self.assertEqual(state["ywc_v03_active_arc_count"], 3)

    def test_lost_pilot_between_terms_choice_and_handoff_does_not_lose_the_successor_or_slot(self):
        world = new_world()
        arc = market_arc(world.cat)
        for number, key in ((1100, "controlled_market"), (1101, "pay_setup"),
                            (1102, "confirm_existing_access"), (1103, "write_new_hearing")):
            play(world, arc, number, key)
        event = world.deliver(arc, "ywc_dmg.1104")
        self.assertTrue(option_legal(world, event, "sign_six_month_terms"))
        force_option(world, event, "sign_six_month_terms")
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "PHI"
        world.refresh(arc)
        self.assertEqual(world.history[world.tag][JES[0]], "complete")
        self.assertIn(JES[1], world.active[world.tag])
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (1, 1))
        review = world.deliver(arc, "ywc_dmg.1105")
        self.assertTrue(option_legal(world, review, "wait_review"))
        choose(world, arc, review, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(world.history[world.tag][JES[1]], "failed")

    def test_foreign_and_other_owned_state_ports_cannot_supply_the_selected_luzon_state(self):
        world = new_world()
        arc = market_arc(world.cat)
        play(world, arc, 1100, "controlled_market")
        play(world, arc, 1101, "pay_setup")
        event = world.deliver(arc, "ywc_dmg.1102")
        state = world.countries[world.tag]
        province = state["states"][0]
        elsewhere = copy.deepcopy(province)
        elsewhere["region"] = "s:STATE_TAIWAN"
        province["pops"] = [p for p in province["pops"]
                            if p["workplace"]["type"] != "building_port"]
        province["buildings"] = [b for b in province["buildings"]
                                 if b["type"] not in ("building_port", "building_trade_center")]
        self.assertFalse(option_legal(world, event, "confirm_existing_access"))
        state["states"].append(elsewhere)
        self.assertFalse(option_legal(world, event, "confirm_existing_access"))
        self.assertEqual(world.countries["PHI"]["states"][0]["buildings"][0]["type"], "building_port")
        self.assertTrue(option_legal(world, event, "limit_local_livelihood"))

    def test_interrupted_foreign_link_requires_explicit_six_new_observations(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 4)
        treaties = copy.deepcopy(world.treaties)
        world.treaties = []
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_running", state)
        event = world.deliver(arc, "ywc_dmg.1105")
        self.assertFalse(option_legal(world, event, "pay_review_bill"))
        world.treaties = treaties
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        choose(world, arc, event, "restart_review")
        before = copy.deepcopy((state, world.treasury))
        for key in ("restart_review", "wait_review", "withdraw"):
            force_option(world, event, key)
        self.assertEqual((state, world.treasury), before)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)
        self.assertEqual(world.treasury[world.tag], -2000)

    def test_paid_bill_survives_a_late_explicit_recount_without_charge_or_queue_overwrite(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        bill = play(world, arc, 1105, "pay_review_bill")
        later = world.deliver(arc, "ywc_dmg.1106")
        world.treaties = []
        self.assertFalse(option_legal(world, later, "retain_controlled"))
        month(world, arc)
        self.assertEqual(state[P + "stage"], 1106)
        self.assertNotEqual(state.get(P + "pending_event"), 1105)
        choose(world, arc, later, "recount_changed")
        self.assertEqual(state[P + "stage"], 1105)
        self.assertEqual(state[P + "review_streak"], 0)
        old_amount = state[P + "bill_paid_amount"]
        old_cash = world.treasury[world.tag]
        before = copy.deepcopy(state)
        force_option(world, bill, "pay_review_bill")
        self.assertEqual(state, before)
        month(world, arc)
        review = world.deliver(arc, "ywc_dmg.1105")
        self.assertTrue(option_legal(world, review, "limit_and_recount"))
        choose(world, arc, review, "limit_and_recount")
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        state["gold_reserves"] = -world.treasury[world.tag]
        finish_review(world, arc, limited=True)
        self.assertEqual(state[P + "outcome"], 2)
        self.assertEqual(state[P + "bill_paid_amount"], old_amount)
        self.assertEqual(world.treasury[world.tag], old_cash)

    def test_current_market_owner_replacement_uses_its_real_existing_privilege(self):
        world = new_world()
        arc = market_arc(world.cat)
        play(world, arc, 1100, "controlled_market")
        play(world, arc, 1101, "pay_setup")
        event = world.deliver(arc, "ywc_dmg.1102")
        self.assertTrue(option_legal(world, event, "confirm_existing_access"))
        # PHI's current market passes to JHG, which already grants DMG an
        # actual directed privilege. The old separate JHG market disappears.
        world.markets["m_phi"]["owner"] = "JHG"
        world.countries["JHG"]["market_id"] = "m_phi"
        del world.markets["m_jhg"]
        del world.markets["m_dmg"]["imports_reliance"]["m_jhg"]
        self.assertTrue(option_legal(world, event, "confirm_existing_access"))
        choose(world, arc, event, "confirm_existing_access")
        self.assertEqual(world.countries[world.tag][P + "stage"], 1103)
        world.treaties = [t for t in world.treaties if "JHG" not in t["participants"]]
        self.assertFalse(world.conditions(world.trigger_defs[P + "link_phi"], world.tag))

    def test_three_actual_existing_channel_or_guard_routes_pay_their_own_costs(self):
        for route, charge in (("controlled", 2000), ("multilateral", 4000), ("guarded", 1000)):
            with self.subTest(route=route):
                world = new_world()
                state = world.countries[world.tag]
                before = copy.deepcopy((world.countries, world.markets, world.treaties))
                arc = ready_for_review(world, route)
                self.assertEqual(state[P + "review_streak"], 0)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (1, 1))
                month(world, arc, 6)
                finish_review(world, arc, route)
                self.assertEqual(state[P + "outcome"], 1)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))
                self.assertEqual(world.markets, before[1])
                self.assertEqual(world.treaties, before[2])
                for tag in ("PHI", "SPA", "JHG", "LAN"):
                    self.assertEqual(world.countries[tag], before[0][tag])
                for key in ("laws", "institutions", "states"):
                    self.assertEqual(state[key], before[0][world.tag][key])

    def test_same_market_is_a_current_object_path_without_forged_cross_market_trade(self):
        for route in ("controlled", "multilateral"):
            with self.subTest(route=route):
                world = new_world(access="same_market")
                self.assertEqual(world.treaties, [])
                self.assertEqual(world.markets["m_dmg"]["imports_reliance"], {})
                arc = ready_for_review(world, route)
                month(world, arc, 6)
                finish_review(world, arc, route)
                self.assertEqual(world.countries[world.tag][P + "outcome"], 1)

    def test_conservative_nonindustrial_local_target_requires_no_partner_or_school(self):
        for route, charge in (("controlled", 2000), ("multilateral", 4000), ("guarded", 1000)):
            with self.subTest(route=route):
                world = new_world(bare=True, access="none")
                arc = ready_for_review(world, route, limited=True)
                month(world, arc, 6)
                finish_review(world, arc, route, limited=True)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "outcome"], 2)
                self.assertEqual(world.treasury[world.tag], -charge)
                self.assertEqual(state["institutions"], {})
                self.assertIn("law_isolationism", state["laws"])
                self.assertFalse(any(b["type"] in ("building_port", "building_trade_center",
                                                   "building_barrack", "building_university")
                                     for b in state["states"][0]["buildings"]))

    def test_only_real_directional_treaty_and_positive_imports_support_controlled_access(self):
        for loss in ("none", "reverse", "draft", "wrong_owner", "imports_zero", "imports_one_percent",
                     "embargo_out", "embargo_in", "relations_zero", "dead_partner", "isolation", "war"):
            with self.subTest(loss=loss):
                world = new_world()
                arc = market_arc(world.cat)
                play(world, arc, 1100, "controlled_market")
                play(world, arc, 1101, "pay_setup")
                event = world.deliver(arc, "ywc_dmg.1102")
                self.assertTrue(option_legal(world, event, "confirm_existing_access"))
                if loss == "none": world.treaties = []
                elif loss == "reverse":
                    world.treaties[0]["articles"][0].update(source_country="DMG", target_country="SPA")
                elif loss == "draft":
                    world.draft_treaties = copy.deepcopy(world.treaties)
                    world.treaties = []
                elif loss == "wrong_owner":
                    world.countries["GBR"] = copy.deepcopy(world.countries["SPA"])
                    world.markets["m_phi"]["owner"] = "GBR"
                elif loss == "imports_zero": world.markets["m_dmg"]["imports_reliance"]["m_phi"] = 0
                elif loss == "imports_one_percent": world.markets["m_dmg"]["imports_reliance"]["m_phi"] = .01
                elif loss == "embargo_out": world.pacts.add(("DMG", "PHI", "embargo"))
                elif loss == "embargo_in": world.pacts.add(("PHI", "DMG", "embargo"))
                elif loss == "relations_zero": world.relations[("DMG", "PHI")] = 0
                elif loss == "dead_partner": world.countries["PHI"]["alive"] = False
                elif loss == "isolation": world.countries["SPA"]["laws"] = ["law_isolationism"]
                elif loss == "war": world.wars.add(("DMG", "SPA"))
                self.assertFalse(option_legal(world, event, "confirm_existing_access"))
                before = copy.deepcopy(world.countries)
                force_option(world, event, "confirm_existing_access")
                self.assertEqual(world.countries, before)
                self.assertEqual(option_legal(world, event, "limit_local_livelihood"), loss != "war")
                self.assertTrue(option_legal(world, event, "withdraw"))

    def test_creation_day_and_five_observations_do_not_make_a_six_month_review(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        world.pulse(arc)
        self.assertEqual(state[P + "review_streak"], 0)
        for count in range(1, 6):
            month(world, arc)
            world.pulse(arc)
            self.assertEqual(state[P + "review_streak"], count)
            self.assertNotIn(P + "review_mature", state)
            self.assertFalse(world.events)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)

    def test_pilot_loss_after_admission_delivers_a_real_wait_or_withdraw_choice(self):
        world = new_world()
        arc = market_arc(world.cat)
        world.refresh(arc)
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "PHI"
        event = world.deliver(arc, "ywc_dmg.1100")
        self.assertFalse(option_legal(world, event, "controlled_market"))
        self.assertTrue(option_legal(world, event, "wait_pilot"))
        choose(world, arc, event, "withdraw")
        self.assertEqual(state[P + "outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(world.history[world.tag][JES[0]], "failed")


if __name__ == "__main__":
    unittest.main()
