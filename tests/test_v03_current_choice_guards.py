"""Current-fact losses between display and the real generated paid choice.

KOR/LAN use their existing country fact runtimes. The seven-case unit matrix
uses DMG's older helper-result seams for guard controls; a separate native DMG
test below executes the real ownership/pop/workplace/occupancy predicate AST.
Business effects, JE admission and generated options use current source.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from clausewitz_harness import parse
import test_v03_lan_foundation as lan_fixtures
import test_v03_kor_foundation_lifecycle as kor_fixtures
from test_v03_dmg_foundation_lifecycle import (
    DmgWorld, EFFECTS as DMG_EFFECTS, SHARED_EFFECTS as DMG_SHARED_EFFECTS,
    _generated_je, _nodes_field,
)


CASES = (
    ("kor_army", "kor", 1000, "court_supply", "ywc_kor_supply_route", "ywc_kor_audit_paid", 1000),
    ("kor_school", "kor", 1010, "court_office", "ywc_kor_school_route", "ywc_kor_school_filing_fee_paid", 1500),
    ("kor_ports", "kor", 1018, "general_customs", "ywc_kor_ports_route", "ywc_kor_ports_filing_fee_paid", 1500),
    ("lan_mine", "lan", 1000, "public_audit", "ywc_lan_mine_route", "ywc_lan_mine_filing_fee_paid", 1000),
    ("lan_river", "lan", 1010, "compensate", "ywc_lan_river_route", "ywc_lan_river_filing_fee_paid", 1000),
    ("lan_fund", "lan", 1020, "mutual_fund", "ywc_lan_fund_route", "ywc_lan_fund_filing_fee_paid", 1000),
    ("dmg_court", "dmg", 1016, "local_compact", "ywc_dmg_court_route", "ywc_dmg_court_charter_paid", 1000),
)


def migrated_opening_projection(country, historical_arcs):
    """Exact reviewed historical migration; never read current effect strings.

    Delivery fixtures still compare every other historical field and source
    proof. The expected caller wrappers below are spelled from the contract.
    """
    arcs = copy.deepcopy(historical_arcs)
    changed = 0
    for arc in arcs:
        for event in arc["events"]:
            for option in event["options"]:
                key, number = option["key"], int(event["id"].rsplit(".", 1)[1])
                if country == "dmg" and event["id"] == "ywc_dmg.1016":
                    helpers = {"royal_administration": "royal", "joint_appointment": "joint", "local_compact": "local"}
                    if key in helpers:
                        option["effect"] = "{ ywc_dmg_foundation_choose_court_" + helpers[key] + " = yes }"
                        changed += 1
                if country != "kor" or arc["era"] != "foundation":
                    continue
                choices = {
                    1000: {"court_supply": "army_size > 0", "provincial_share": "army_size > 0", "limited_legacy": ""},
                    1010: {"co_manage": "ywc_kor_school_coop_ready = yes", "court_office": "ywc_kor_school_office_ready = yes", "limited_lessons": "ywc_kor_school_limited_ready = yes"},
                    1018: {"licensed_port": "ywc_kor_ports_designated_ready = yes", "general_customs": "ywc_kor_ports_general_ready = yes", "shore_ledger": "ywc_kor_ports_shore_ready = yes"},
                }
                if number not in choices or key not in choices[number]:
                    continue
                slug, prefix, terminal = {
                    1000: ("military_accounts", "ywc_kor_", "ywc_kor_arc_abandoned"),
                    1010: ("school_factions", "ywc_kor_school_", "ywc_kor_school_withdrawn"),
                    1018: ("controlled_ports", "ywc_kor_ports_", "ywc_kor_ports_withdrawn"),
                }[number]
                queue = prefix + "pending_event"
                context = (f"NOT = {{ has_variable = ywc_v03_kor_v03_kor_{slug}_settled }} "
                           f"NOT = {{ has_variable = {terminal} }} "
                           f"OR = {{ NOT = {{ has_variable = {queue} }} var:{queue} ?= {number} var:{queue} ?= {number + 1} }}")
                eligibility = choices[number][key]
                if number == 1000:
                    eligibility = ("NOT = { has_variable = ywc_v03_kor_v03_kor_military_accounts_settled } "
                                   "NOT = { has_variable = ywc_kor_any_outcome } "
                                   "NOT = { has_variable = ywc_kor_arc_abandoned } net_fixed_income >= 0 "
                                   "in_default = no NOT = { has_modifier = declared_bankruptcy }"
                                   + (" " + eligibility if eligibility else ""))
                historical_body = option["effect"].strip()[1:-1].strip()
                option["effect"] = (f"{{ if = {{ limit = {{ {context} }} if = {{ limit = {{ {eligibility} }} {historical_body} }} "
                                    f"else = {{ if = {{ limit = {{ OR = {{ NOT = {{ has_variable = {queue} }} var:{queue} ?= {number} }} }} "
                                    f"set_variable = {{ name = {queue} value = {number} }} }} }} }} }}")
                changed += 1
    assert changed == {"dmg": 3, "kor": 9}[country], (country, changed)
    return arcs


def field(nodes, name):
    return next((value for key, _, value in nodes if key == name), [])


def generated_option(country, number, key):
    text = (ROOT / f"yongchang_world/events/ywc_v03_country_{country}_events.txt").read_text(encoding="utf-8-sig")
    event = next(value for name, _, value in parse(text) if name == f"ywc_{country}.{number}")
    return next(value for name, _, value in event if name == "option"
                and any(k == "name" and v == f"ywc_{country}.{number}.{key}" for k, _, v in value))


def executable(nodes):
    for key, op, value in nodes:
        if key in ("name", "trigger", "ai_chance"):
            continue
        if key == "custom_tooltip":
            if isinstance(value, list):
                yield from executable([node for node in value if node[0] != "text"])
        else:
            yield key, op, value


def queued_variable(case):
    name = case[0]
    return {
        "kor_army": "ywc_kor_pending_event", "kor_school": "ywc_kor_school_pending_event",
        "kor_ports": "ywc_kor_ports_pending_event", "lan_mine": "ywc_lan_mine_pending_event",
        "lan_river": "ywc_lan_river_pending_event", "lan_fund": "ywc_lan_fund_pending_event",
        "dmg_court": "ywc_dmg_court_pending_event",
    }[name]


def settled_variable(case):
    return {
        "kor_army": "ywc_v03_kor_v03_kor_military_accounts_settled",
        "kor_school": "ywc_v03_kor_v03_kor_school_factions_settled",
        "kor_ports": "ywc_v03_kor_v03_kor_controlled_ports_settled",
        "lan_mine": "ywc_v03_lan_v03_lan_mine_accounts_settled",
        "lan_river": "ywc_v03_lan_v03_lan_river_compacts_settled",
        "lan_fund": "ywc_v03_lan_v03_lan_work_accident_fund_settled",
        "dmg_court": "ywc_v03_dmg_v03_dmg_court_provinces_settled",
    }[case[0]]


def choice_helper(case):
    return {
        "kor_army": "ywc_kor_choose_court_supply", "kor_school": "ywc_kor_choose_school_office",
        "kor_ports": "ywc_kor_choose_port_general", "lan_mine": "ywc_lan_choose_mine_audit",
        "lan_river": "ywc_lan_choose_river_compensate", "lan_fund": "ywc_lan_choose_fund_mutual",
        "dmg_court": "ywc_dmg_foundation_choose_court_local",
    }[case[0]]


def prepare(case):
    name, country, number, key, _, _, _ = case
    if country == "lan":
        fixture = lan_fixtures.LanLifecycleRegressionTest()
        fixture.setUp()
        world = fixture._world(10000, strict=True)
        world.active_journals = {"LAN": None}
        world.journal_states = {"LAN": {}}
        world.journal_add_cursor = {"LAN": 0}
        state = world.countries["LAN"]
        state["test_laws"] = {"law_poor_laws", "law_commercialized_agriculture"}
        slug = {"lan_mine": "v03_lan_mine_accounts", "lan_river": "v03_lan_river_compacts",
                "lan_fund": "v03_lan_work_accident_fund"}[name]
        arc = lan_fixtures._arc(fixture.catalog, slug)
        fixture._admit_entry(world, arc["journals"][0])
        assert fixture._dispatch_queued_event(world, arc) == number
    elif country == "kor":
        state = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "bureaucracy": 100, "gold_reserves": 10000, "owns_state": 1,
            "army_size": 5, "staffed_office": 1, "staffed_port": 1,
            "staffed_university": 1, "school_investment": 1,
            "laws": {"law_public_schools", "law_protectionism"},
        }
        if name != "kor_army":
            state["ywc_v03_kor_v03_kor_military_accounts_settled"] = 1
        data = json.loads((ROOT / "data/content/v03/countries/kor.json").read_text(encoding="utf-8-sig"))
        slug = {"kor_army": "v03_kor_military_accounts", "kor_school": "v03_kor_school_factions",
                "kor_ports": "v03_kor_controlled_ports"}[name]
        arc = next(arc for arc in data["arcs"] if arc["slug"] == slug)
        fixture = kor_fixtures.KorPortsLifecycleRegression()
        world = kor_fixtures.KorLifecycleWorld(state)
        fixture.activate_entry(world, arc, arc["journals"][0])
        fixture.deliver(world, arc, arc["journals"][0], f"ywc_kor.{number}")
    else:
        state = {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "yearly_gross_income": 52000, "net_fixed_income": 0,
            "gold_reserves": 10000, "fixture_owned_state": 1,
            "fixture_secondary_office_ready": 1,
        }
        world = DmgWorld(DMG_EFFECTS + "\n" + DMG_SHARED_EFFECTS, {"DMG": state})
        journal = _generated_je("ywc_je_v03_dmg_court_appointment")
        assert world.conditions(_nodes_field(journal, "possible"), "DMG")
        world.execute(_nodes_field(journal, "immediate"), "DMG")
        world.journals.append(("DMG", [("type", "=", "ywc_je_v03_dmg_court_appointment")]))
        # Consume the opening queue without pretending to run the engine dispatcher.
        state.pop("ywc_dmg_court_pending_event", None)
    return world, state, generated_option(country, number, key)


def lose_fact(case, state):
    name = case[0]
    if name == "kor_army":
        state["army_size"] = 0
    elif name == "kor_school":
        state["laws"] = {"law_no_schools", "law_protectionism"}
    elif name == "kor_ports":
        state["laws"] = {"law_public_schools", "law_isolationism"}
    elif name == "lan_fund":
        state["test_laws"].remove("law_poor_laws")
    elif name.startswith("lan_"):
        next(building for building in state["test_buildings"]
             if building["type"] == "building_government_administration")["occupancy"] = .79
    else:
        state["fixture_secondary_office_ready"] = 0


class CurrentChoiceGuards(unittest.TestCase):
    def test_missing_engine_facts_do_not_count_as_paid_choice_eligibility(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, _ = prepare(case)
                tag = case[1].upper()
                missing = "army_size" if case[0] == "kor_army" else "laws" if tag == "KOR" else "test_laws" if case[0] == "lan_fund" else "test_buildings" if tag == "LAN" else "fixture_secondary_office_ready"
                state.pop(missing, None)
                before_route = state.get(case[4])
                world.run(choice_helper(case), tag)
                self.assertEqual(world.treasury[tag], 0)
                self.assertEqual(state.get(case[4]), before_route)
                self.assertNotIn(case[5], state)

    def test_deep_choice_helpers_also_refuse_fact_loss(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, _ = prepare(case)
                tag = case[1].upper()
                lose_fact(case, state)
                route_before = state.get(case[4])
                world.run(choice_helper(case), tag)
                self.assertEqual(world.treasury[tag], 0)
                self.assertEqual(state.get(case[4]), route_before)
                self.assertNotIn(case[5], state)

    def test_seven_actual_cached_choices_refuse_current_fact_loss(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                self.assertTrue(world.conditions(field(option, "trigger"), tag))
                lose_fact(case, state)
                self.assertFalse(world.conditions(field(option, "trigger"), tag))
                before = world.treasury[tag]
                route_before = state.get(case[4])
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], before, "lost current eligibility must not charge")
                self.assertEqual(state.get(case[4]), route_before, "refused choice must not select a route")
                self.assertNotIn(case[5], state, "refusal cannot invent a paid receipt")
                self.assertIn(state.get(queued_variable(case)), (None, case[2]), "refusal cannot advance")

    def test_valid_choice_pays_once_and_replay_preserves_later_queue(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                before = world.treasury[tag]
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag] - before, -case[6])
                self.assertEqual(state[case[5]], 1)
                paid = copy.deepcopy(state)
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag] - before, -case[6])
                self.assertEqual(state, paid)

    def test_restore_actual_fact_retries_without_double_charging(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                facts = copy.deepcopy(state)
                lose_fact(case, state)
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], 0)
                # Restore only the engine-owned fact changed by lose_fact.
                for name in ("army_size", "laws", "test_laws", "test_buildings", "fixture_secondary_office_ready"):
                    if name in facts:
                        state[name] = copy.deepcopy(facts[name])
                self.assertTrue(world.conditions(field(option, "trigger"), tag))
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], -case[6])
                self.assertEqual(state[case[5]], 1)

    def test_earned_receipt_survives_lost_fact_without_rewinding_later_queue(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                world.execute(list(executable(option)), tag)
                state["gold_reserves"] = 0
                lose_fact(case, state)
                before = copy.deepcopy(state)
                cash = world.treasury[tag]
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], cash)
                self.assertEqual(state, before, "stale already-paid choice must keep the earned receipt and later queue")

    def test_terminal_context_does_not_resurrect_paid_opening(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                state[settled_variable(case)] = 1
                before = copy.deepcopy(state)
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], 0)
                self.assertEqual(state, before, "a closed arc must not pay or queue an opening")

    def test_actual_withdrawal_cannot_be_reopened_by_the_cached_paid_choice(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                key = "withdraw_court" if tag == "DMG" else "defer_or_withdraw" if case[0] == "kor_army" else "withdraw"
                withdrawal = generated_option(case[1], case[2], key)
                self.assertNotIn(settled_variable(case), state)
                world.execute(list(executable(withdrawal)), tag)
                self.assertEqual(state.get(settled_variable(case)), 1,
                                 "the real withdrawal must first make the arc terminal")
                before = copy.deepcopy(state)
                cash = world.treasury[tag]
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], cash)
                self.assertEqual(state, before)

    def test_native_dmg_court_choice_rechecks_owned_employed_workplace_and_retries(self):
        from dmg_market_runtime import DmgMarketWorld
        from test_v03_dmg_luzon_market import new_world

        for loss in ("ownership", "occupancy", "workplace"):
            with self.subTest(loss=loss):
                world = new_world(access="none")
                self.assertIsInstance(world, DmgMarketWorld)
                state = world.countries["DMG"]
                self.assertFalse(any(key.startswith("fixture_") for key in state))
                arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_dmg_court_provinces")
                event = world.deliver(arc, "ywc_dmg.1016")
                option = next(o for k, _, o in event if k == "option"
                              and field(o, "name").endswith(".local_compact"))
                gate = parse("ywc_dmg_v03_secondary_local_office_ready = yes")
                self.assertTrue(world.conditions(gate, "DMG"))
                self.assertTrue(world.conditions(field(option, "trigger"), "DMG"))
                province = state["states"][0]
                employee = next(p for p in province["pops"] if p["type"] == "bureaucrats")
                office = employee["workplace"]
                self.assertEqual(office["type"], "building_government_administration")
                self.assertTrue(employee["employed"])
                self.assertFalse(employee["primary"])
                self.assertGreaterEqual(office["occupancy"], .8)
                if loss == "ownership":
                    province["owner"] = "PHI"
                elif loss == "occupancy":
                    office["occupancy"] = .79
                else:
                    employee["workplace"] = next(b for b in province["buildings"]
                                                 if b["type"] == "building_port")
                self.assertFalse(world.conditions(gate, "DMG"))
                self.assertFalse(world.conditions(field(option, "trigger"), "DMG"))
                cash = world.treasury["DMG"]
                price = state["ywc_dmg_court_charter_cost"]
                world.execute(list(executable(option)), "DMG")
                self.assertEqual(world.treasury["DMG"], cash)
                self.assertNotIn("ywc_dmg_court_charter_paid", state)
                self.assertNotIn("ywc_dmg_court_route", state)
                self.assertEqual(state.get("ywc_dmg_court_pending_event"), 1016)
                if loss == "ownership":
                    province["owner"] = "DMG"
                elif loss == "occupancy":
                    office["occupancy"] = 1
                else:
                    employee["workplace"] = office
                self.assertTrue(world.conditions(gate, "DMG"))
                retry = world.deliver(arc, "ywc_dmg.1016")
                retried = next(o for k, _, o in retry if k == "option"
                               and field(o, "name").endswith(".local_compact"))
                self.assertTrue(world.conditions(field(retried, "trigger"), "DMG"))
                world.execute(list(executable(retried)), "DMG")
                self.assertEqual(world.treasury["DMG"] - cash, -price)
                self.assertEqual(state["ywc_dmg_court_charter_paid"], 1)
                self.assertEqual(state["ywc_dmg_court_route"], 3)
                self.assertEqual(state["ywc_dmg_court_pending_event"], 1017)
                paid = copy.deepcopy(state)
                world.execute(list(executable(retried)), "DMG")
                self.assertEqual(world.treasury["DMG"] - cash, -price)
                self.assertEqual(state, paid)

    def test_unrelated_later_queue_is_preserved_by_the_cached_choice(self):
        for case in CASES:
            with self.subTest(case=case[0]):
                world, state, option = prepare(case)
                tag = case[1].upper()
                state[queued_variable(case)] = 9999
                before = copy.deepcopy(state)
                world.execute(list(executable(option)), tag)
                self.assertEqual(world.treasury[tag], 0)
                self.assertEqual(state, before)

    def test_sibling_kor_choices_recheck_their_own_current_gate(self):
        siblings = (
            (CASES[0], "provincial_share", lambda s: s.update(army_size=0)),
            (CASES[0], "limited_legacy", lambda s: s.update(net_fixed_income=-1)),
            (CASES[1], "co_manage", lambda s: s.update(staffed_office=0, staffed_university=0)),
            (CASES[1], "limited_lessons", lambda s: s.update(staffed_office=0)),
            (CASES[2], "licensed_port", lambda s: s.update(staffed_port=0)),
            (CASES[2], "shore_ledger", lambda s: s.update(staffed_office=0)),
        )
        for case, key, lose in siblings:
            with self.subTest(case=case[0], key=key):
                world, state, _ = prepare(case)
                option = generated_option("kor", case[2], key)
                self.assertTrue(world.conditions(field(option, "trigger"), "KOR"))
                lose(state)
                self.assertFalse(world.conditions(field(option, "trigger"), "KOR"))
                route = state.get(case[4])
                world.execute(list(executable(option)), "KOR")
                self.assertEqual(world.treasury["KOR"], 0)
                self.assertEqual(state.get(case[4]), route)
                self.assertNotIn(case[5], state)

    def test_joint_court_sibling_rechecks_appointment_before_charter_payment(self):
        case = CASES[-1]
        world, state, _ = prepare(case)
        state["fixture_government_appointment_ready"] = 1
        option = generated_option("dmg", 1016, "joint_appointment")
        self.assertTrue(world.conditions(field(option, "trigger"), "DMG"))
        state["fixture_government_appointment_ready"] = 0
        self.assertFalse(world.conditions(field(option, "trigger"), "DMG"))
        world.execute(list(executable(option)), "DMG")
        self.assertEqual(world.treasury["DMG"], 0)
        self.assertNotIn("ywc_dmg_court_route", state)
        self.assertNotIn("ywc_dmg_court_charter_paid", state)


if __name__ == "__main__":
    unittest.main()
