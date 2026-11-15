"""Focused source-contract tests for MGL's middle-era mobile offices card."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests.test_v03_mgl_actual_source import _StrictMglWorld, _ordinary_facts

ROOT = Path(__file__).resolve().parents[1]


def _canonical_git_text_newlines(content: bytes) -> bytes:
    """Normalize only Git's CRLF checkout conversion while preserving bytes otherwise."""
    return content.replace(b"\r\n", b"\n")


class _MobileWorld(_StrictMglWorld):
    def condition(self, node, tag):
        key, comparison, value = node
        if key == "has_building":
            state = self.scope_state
            return state is not None and any(building.get("type") == value for building in state.get("buildings", []))
        return super().condition(node, tag)


def _runtime_world(*, route="joint", cash=1000, laws=None, foundations=()):
    facts = _ordinary_facts()
    facts["laws"] = set(laws or {"law_hereditary_bureaucrats", "law_tenant_farmers"})
    facts["gold_reserves"] = cash
    facts["states"][0]["buildings"].append({"type": "building_government_administration", "level": 1,
                                             "groups": {"bg_government"}})
    facts["states"][0]["pops"].append({"employed": True, "workplace": "building_government_administration"})
    facts["buildings"].append({"type": "building_government_administration", "level": 1,
                               "groups": {"bg_government"}})
    effects_paths = ("yongchang_world/common/scripted_effects/ywc_v03_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_shared_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_flavor_effects.txt")
    trigger_paths = ("yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt",
                     "yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt")
    effects = "\n".join((ROOT / path).read_text(encoding="utf-8-sig") for path in effects_paths)
    triggers = "\n".join((ROOT / path).read_text(encoding="utf-8-sig") for path in trigger_paths)
    world = _MobileWorld(effects, triggers, {"MGL": facts, "SHU": {"relations": {}}, "RUS": {"relations": {}}})
    state = world.countries["MGL"]
    state.update({"ywc_v03_mgl_v03_mgl_mobile_offices_started": 1,
                  "ywc_mgl_mobile_fee": 100, "ywc_mgl_mobile_half_fee": 50,
                  "ywc_mgl_mobile_quarter_fee": 25, "ywc_mgl_mobile_route": {"circuit": 1, "joint": 2, "quota": 3}[route]})
    for slug, outcome in foundations:
        state[f"ywc_v03_mgl_v03_mgl_{slug}_settled"] = 1
        state[f"ywc_v03_mgl_v03_mgl_{slug}_outcome"] = outcome
    return world


def _actual_mobile_world(*, root_slugs=None, bureaucracy="law_hereditary_bureaucrats",
                         land_law="law_tenant_farmers", admit_mobile=False, register_mobile=False):
    from tests.test_v03_mgl_inline_actual_source import actual_mgl_inline_world, legal_ordinary_facts
    facts = legal_ordinary_facts()
    facts["laws"].difference_update({"law_hereditary_bureaucrats", "law_appointed_bureaucrats",
                                    "law_elected_bureaucrats", "law_serfdom", "law_tenant_farmers",
                                    "law_commercialized_agriculture"})
    facts["laws"].update({bureaucracy, land_law})
    return actual_mgl_inline_world(admit_mobile=admit_mobile, register_mobile=register_mobile,
                                   root_slugs=root_slugs, ordinary_facts=facts)


def _deliver_actual_event(world, expected):
    from tests.test_v03_mgl_actual_source import pulse_actual_journals
    for _ in range(90):
        actual = pulse_actual_journals(world)
        if actual == expected:
            return
        if actual is not None:
            raise AssertionError(("unexpected_mobile_or_foundation_event", expected, actual))
    raise AssertionError(("actual_event_timeout", expected))


def _choose_actual_event(world, event_id, suffix):
    from tests.test_v03_mgl_actual_source import choose_actual_option, _refresh_actual_journal_lifecycle
    choose_actual_option(world, event_id, suffix)
    _refresh_actual_journal_lifecycle(world)


def _complete_actual_local_foundation(world, *, first_event, outcome_variable):
    """Complete one actual route-3 foundation from delivered source events/options."""
    from tests.test_v03_mgl_actual_source import pulse_actual_journals
    prefix = first_event
    term = "covenant_terms" if prefix == 1010 else "local_terms"
    for event, option in ((prefix, "local"), (prefix + 1, "review"),
                          (prefix + 2, term), (prefix + 3, "clarify"),
                          (prefix + 4, term)):
        event_id = f"ywc_mng.{event}"
        _deliver_actual_event(world, event_id)
        _choose_actual_event(world, event_id, option)
    _deliver_actual_event(world, f"ywc_mng.{prefix + 5}")
    _choose_actual_event(world, f"ywc_mng.{prefix + 5}", "review")
    state = world.countries["MGL"]
    for _ in range(9):
        if state.get(outcome_variable) is not None:
            break
        result = pulse_actual_journals(world)
        if result is not None:
            raise AssertionError(("unexpected_foundation_completion_event", result))
    if state.get(outcome_variable) is None:
        raise AssertionError(("foundation_outcome_not_recorded", outcome_variable))


class MglMobileOfficeCatalogTests(unittest.TestCase):
    def test_catalog_registers_six_middle_events_and_one_journal(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
        rows = [arc for arc in catalog["arcs"] if arc["slug"] == "v03_mgl_mobile_offices"]
        self.assertEqual(len(rows), 1)
        arc = rows[0]
        self.assertEqual(arc["era"], "middle")
        self.assertEqual([event["id"] for event in arc["events"]], [f"ywc_mng.{n}" for n in range(1100, 1106)])
        self.assertEqual([journal["id"] for journal in arc["journals"]], ["ywc_je_v03_mgl_mobile_offices"])
        self.assertEqual(arc["outcomes"], ["mobile_circuit", "joint_banner_office", "limited_registry", "withdrawn"])

    def test_real_three_way_outcomes_are_paid_and_have_distinct_long_term_modifiers(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_mgl_mobile_offices")
        opening = next(e for e in arc["events"] if e["id"] == "ywc_mng.1100")
        options = {o["key"]: o for o in opening["options"]}
        effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt").read_text(encoding="utf-8-sig")
        self.assertTrue({"circuit", "joint", "quota", "withdraw"}.issubset(options))
        for route, key in (("circuit", "circuit"), ("joint", "joint"), ("quota", "quota")):
            self.assertIn("gold_reserves", options[route]["trigger"])
            self.assertIn(f"ywc_mgl_mobile_pay_{key}", options[route]["effect"])
            helper = effects.split(f"ywc_mgl_mobile_pay_{key} = {{", 1)[1].split("\n", 1)[0]
            self.assertIn("add_treasury", helper)
            self.assertIn("NOT = { has_variable = ywc_mgl_mobile_paid }", helper)
        self.assertEqual(len({options[key]["effect"] for key in ("circuit", "joint", "quota")}), 3)

    def test_actual_joint_route_charges_once_and_completes_six_month_observation(self):
        world = _runtime_world(foundations=(("two_trade_roads", 1),))
        world.run("ywc_mgl_mobile_pay_joint", "MGL")
        self.assertEqual(world.treasury["MGL"], -50)
        world.run("ywc_mgl_mobile_pay_joint", "MGL")
        self.assertEqual(world.treasury["MGL"], -50)
        world.run("ywc_mgl_mobile_commit", "MGL")
        world.run("ywc_mgl_mobile_begin_observation", "MGL")
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertTrue(world.countries["MGL"].get("ywc_mgl_mobile_watch"))
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertEqual(world.countries["MGL"].get("ywc_mgl_mobile_timer"), 1)
        world.advance_months(6)
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertEqual(world.countries["MGL"].get("ywc_mgl_mobile_outcome_ready"), 1)
        world.run("ywc_mgl_mobile_settle", "MGL")
        self.assertEqual(world.countries["MGL"].get("ywc_v03_mgl_v03_mgl_mobile_offices_outcome"), 2)

    def test_actual_quota_route_is_self_funded_when_foundation_records_are_missing(self):
        world = _runtime_world(route="quota", foundations=())
        trigger = world.strict_trigger_defs["ywc_mgl_mobile_quota_ready"]
        self.assertTrue(world.conditions(trigger, "MGL"))
        world.run("ywc_mgl_mobile_pay_quota", "MGL")
        self.assertEqual(world.treasury["MGL"], -25)
        self.assertFalse(any(row[1].get("name") == "ywc_v03_mgl_mobile_quota" for row in world.modifiers))
        world.run("ywc_mgl_mobile_commit", "MGL")
        world.run("ywc_mgl_mobile_begin_observation", "MGL")
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        world.advance_months(6)
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertEqual(world.countries["MGL"].get("ywc_mgl_mobile_outcome_ready"), 1)
        world.run("ywc_mgl_mobile_settle", "MGL")
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_quota" for row in world.modifiers))

    def test_actual_route_guards_require_the_matching_prior_trade_or_debt_record(self):
        roads = _runtime_world(route="circuit", laws={"law_appointed_bureaucrats", "law_tenant_farmers"},
                               foundations=(("two_trade_roads", 1),))
        roads_trigger = roads.strict_trigger_defs["ywc_mgl_mobile_circuit_ready"]
        self.assertTrue(roads.conditions(roads_trigger, "MGL"))
        roads_missing = _runtime_world(route="circuit", laws={"law_appointed_bureaucrats", "law_tenant_farmers"})
        self.assertFalse(roads_missing.conditions(roads_missing.strict_trigger_defs["ywc_mgl_mobile_circuit_ready"], "MGL"))
        debt = _runtime_world(route="joint", foundations=(("pastoral_debt", 1),))
        self.assertTrue(debt.conditions(debt.strict_trigger_defs["ywc_mgl_mobile_joint_ready"], "MGL"))
        debt_missing = _runtime_world(route="joint")
        self.assertFalse(debt_missing.conditions(debt_missing.strict_trigger_defs["ywc_mgl_mobile_joint_ready"], "MGL"))

    def test_actual_low_cash_and_lost_same_workplace_job_do_not_charge_or_advance(self):
        poor = _runtime_world(route="quota", cash=1)
        poor.run("ywc_mgl_mobile_pay_quota", "MGL")
        self.assertEqual(poor.treasury["MGL"], 0)
        self.assertNotIn("ywc_mgl_mobile_paid", poor.countries["MGL"])
        self.assertEqual(poor.countries["MGL"].get("ywc_mgl_mobile_pending_event"), 1100)

        world = _runtime_world(foundations=(("two_trade_roads", 1),))
        world.run("ywc_mgl_mobile_pay_joint", "MGL")
        world.run("ywc_mgl_mobile_commit", "MGL")
        world.run("ywc_mgl_mobile_begin_observation", "MGL")
        world.countries["MGL"]["states"][0]["pops"] = []
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertEqual(world.countries["MGL"].get("ywc_mgl_mobile_pending_event"), 1104)
        self.assertIn("ywc_mgl_mobile_paused", world.countries["MGL"])
        self.assertEqual(world.treasury["MGL"], -50)

    def test_current_state_must_own_the_government_office_that_employs_the_pop(self):
        world = _runtime_world(route="quota")
        state = world.countries["MGL"]["states"][0]
        state["pops"] = [pop for pop in state["pops"] if pop.get("workplace") != "building_government_administration"]
        world.countries["MGL"]["states"].append({"market_access": 0.5,
            "pops": [{"employed": True, "workplace": "building_government_administration"}], "buildings": []})
        ready = world.strict_trigger_defs["ywc_mgl_mobile_quota_ready"]
        self.assertFalse(world.conditions(ready, "MGL"))

    def test_actual_source_projection_keeps_foundations_frozen_and_registers_mobile_separately(self):
        from tests import test_v03_mgl_foundation_lifecycle as foundation
        catalog = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
        journals, events = foundation._native_business_projection(catalog)
        self.assertEqual((len(journals), len(events)), (6, 24))
        all_journals, all_events = foundation._native_business_projection(catalog, include_mobile=True)
        self.assertEqual((len(all_journals), len(all_events)), (7, 30))

    def test_actual_rendered_mobile_final_event_remains_live_until_close_choice(self):
        from copy import deepcopy
        from tests.test_v03_mgl_inline_actual_source import actual_mgl_inline_world, legal_ordinary_facts
        from tests.test_v03_mgl_actual_source import pulse_actual_journals, choose_actual_option, _refresh_actual_journal_lifecycle
        facts = legal_ordinary_facts(); facts["laws"].add("law_hereditary_bureaucrats")
        world, evidence = actual_mgl_inline_world(admit_mobile=True, ordinary_facts=facts)
        state = world.countries["MGL"]
        jid = "ywc_je_v03_mgl_mobile_offices"
        self.assertIn(jid, world.active_journals["MGL"])

        def deliver(expected):
            for _ in range(60):
                actual = pulse_actual_journals(world)
                if actual == expected:
                    return
                self.assertIsNone(actual, (expected, actual))
            self.fail(f"actual inline transport did not deliver {expected}")

        def choose(event_id, suffix):
            choose_actual_option(world, event_id, suffix)
            _refresh_actual_journal_lifecycle(world)

        deliver("ywc_mng.1100"); choose("ywc_mng.1100", "quota")
        self.assertEqual(world.treasury["MGL"], -25)
        deliver("ywc_mng.1101"); choose("ywc_mng.1101", "register")
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1102)
        before_commit = deepcopy(state)
        world.run("ywc_mgl_mobile_commit", "MGL")
        self.assertEqual(state, before_commit)
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1102)
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 1)
        deliver("ywc_mng.1102"); choose("ywc_mng.1102", "new_record")
        deliver("ywc_mng.1103"); choose("ywc_mng.1103", "missing_record")

        for month in range(6):
            self.assertIsNone(pulse_actual_journals(world))
            self.assertNotIn("ywc_mgl_mobile_outcome_ready", state)
            if month == 0:
                remaining = world.months_until_expiry["MGL"]["ywc_mgl_mobile_timer"]
                world.run("ywc_mgl_mobile_monthly_review", "MGL")
                self.assertEqual(world.months_until_expiry["MGL"]["ywc_mgl_mobile_timer"], remaining)
        self.assertIsNone(pulse_actual_journals(world))
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1105)
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1)
        self.assertIn(jid, world.active_journals["MGL"])
        self.assertFalse(world.conditions(next(v for k, _, v in world.journal_defs[jid] if k == "complete"), "MGL"))
        deliver("ywc_mng.1105")
        self.assertIn(jid, world.active_journals["MGL"])
        choose("ywc_mng.1105", "close")
        self.assertEqual(state.get("ywc_v03_mgl_v03_mgl_mobile_offices_outcome"), 3)
        self.assertEqual(state.get("ywc_v03_active_arc_count"), 0)
        self.assertNotIn(jid, world.active_journals["MGL"])

    def test_actual_recovery_event_does_not_fail_or_withdraw_the_journal(self):
        from tests.test_v03_mgl_inline_actual_source import actual_mgl_inline_world, legal_ordinary_facts
        from tests.test_v03_mgl_actual_source import pulse_actual_journals, choose_actual_option, _refresh_actual_journal_lifecycle
        facts = legal_ordinary_facts(); facts["laws"].add("law_hereditary_bureaucrats")
        world, _ = actual_mgl_inline_world(admit_mobile=True, ordinary_facts=facts)
        state = world.countries["MGL"]
        jid = "ywc_je_v03_mgl_mobile_offices"

        def deliver(expected):
            for _ in range(60):
                actual = pulse_actual_journals(world)
                if actual == expected:
                    return
                self.assertIsNone(actual, (expected, actual))
            self.fail(f"actual inline transport did not deliver {expected}")

        def choose(event_id, suffix):
            choose_actual_option(world, event_id, suffix)
            _refresh_actual_journal_lifecycle(world)

        deliver("ywc_mng.1100"); choose("ywc_mng.1100", "quota")
        deliver("ywc_mng.1101"); choose("ywc_mng.1101", "register")
        deliver("ywc_mng.1102"); choose("ywc_mng.1102", "new_record")
        deliver("ywc_mng.1103"); choose("ywc_mng.1103", "missing_record")
        state["states"][0]["pops"] = [pop for pop in state["states"][0]["pops"]
                                       if pop.get("workplace") != "building_government_administration"]
        self.assertIsNone(pulse_actual_journals(world))
        deliver("ywc_mng.1104")
        self.assertIn(jid, world.active_journals["MGL"])
        self.assertFalse(world.conditions(next(v for k, _, v in world.journal_defs[jid] if k == "fail"), "MGL"))
        self.assertNotIn("ywc_v03_mgl_v03_mgl_mobile_offices_withdrawn", state)
        state["states"][0]["pops"].append({"employed": True,
                                             "workplace": "building_government_administration"})
        choose("ywc_mng.1104", "retry")
        self.assertIn(jid, world.active_journals["MGL"])
        self.assertEqual(world.treasury["MGL"], -25)

    def test_actual_stale_cached_choice_rechecks_default_cash_and_employment(self):
        from copy import deepcopy
        from tests.test_v03_mgl_actual_source import _block
        world, _ = _actual_mobile_world(admit_mobile=True)
        state = world.countries["MGL"]
        _deliver_actual_event(world, "ywc_mng.1100")
        event = world.event_defs["ywc_mng.1100"]
        option = next(value for key, _, value in event
                      if key == "option" and _block(value, "name") == "ywc_mng.1100.quota")
        gate = _block(option, "trigger")
        self.assertTrue(world.conditions(gate, "MGL"))
        state["gold_reserves"] = 1
        state["in_default"] = True
        self.assertFalse(world.conditions(gate, "MGL"))
        # Simulate the UI delivering a cached option callback: the deepest
        # authored helper still refuses to charge or establish the route.
        world.execute([node for node in option if node[0] not in
                       ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")], "MGL")
        self.assertEqual(world.treasury["MGL"], 0)
        self.assertNotIn("ywc_mgl_mobile_paid", state)
        self.assertNotIn("ywc_mgl_mobile_route", state)
        state["gold_reserves"] = 10000
        state["in_default"] = False
        _choose_actual_event(world, "ywc_mng.1100", "quota")
        self.assertEqual(world.treasury["MGL"], -25)
        self.assertEqual(state.get("ywc_mgl_mobile_route"), 3)
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1101)
        # A stale duplicate callback after successful payment must not rewind
        # the source queue or make a paid offer appear payable again.
        before = deepcopy(state)
        treasury_before = dict(world.treasury)
        modifiers_before = list(world.modifiers)
        world.execute([node for node in option if node[0] not in
                       ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")], "MGL")
        self.assertEqual(state, before)
        self.assertEqual(world.treasury, treasury_before)
        self.assertEqual(world.modifiers, modifiers_before)
        self.assertEqual(world.treasury["MGL"], -25)
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1101)

    def test_actual_default_loss_pauses_and_retry_waits_for_restoration(self):
        from tests.test_v03_mgl_actual_source import pulse_actual_journals, _block
        world, _ = _actual_mobile_world(admit_mobile=True)
        state = world.countries["MGL"]
        _deliver_actual_event(world, "ywc_mng.1100"); _choose_actual_event(world, "ywc_mng.1100", "quota")
        _deliver_actual_event(world, "ywc_mng.1101"); _choose_actual_event(world, "ywc_mng.1101", "register")
        _deliver_actual_event(world, "ywc_mng.1102"); _choose_actual_event(world, "ywc_mng.1102", "new_record")
        _deliver_actual_event(world, "ywc_mng.1103"); _choose_actual_event(world, "ywc_mng.1103", "missing_record")
        state["in_default"] = True
        self.assertIsNone(pulse_actual_journals(world))
        self.assertIn("ywc_mgl_mobile_paused", state)
        _deliver_actual_event(world, "ywc_mng.1104")
        self.assertIn("ywc_mgl_mobile_paused", state)
        retry = next(value for key, _, value in world.event_defs["ywc_mng.1104"]
                     if key == "option" and _block(value, "name") == "ywc_mng.1104.retry")
        self.assertFalse(world.conditions(_block(retry, "trigger"), "MGL"))
        state["in_default"] = False
        _choose_actual_event(world, "ywc_mng.1104", "retry")
        self.assertNotIn("ywc_mgl_mobile_paused", state)
        self.assertEqual(world.treasury["MGL"], -25)

    def test_actual_loss_after_maturity_rejects_cached_final_choice_and_recovers(self):
        from tests.test_v03_mgl_actual_source import pulse_actual_journals, _block
        world, _ = _actual_mobile_world(admit_mobile=True)
        state = world.countries["MGL"]
        jid = "ywc_je_v03_mgl_mobile_offices"
        _deliver_actual_event(world, "ywc_mng.1100"); _choose_actual_event(world, "ywc_mng.1100", "quota")
        _deliver_actual_event(world, "ywc_mng.1101"); _choose_actual_event(world, "ywc_mng.1101", "register")
        _deliver_actual_event(world, "ywc_mng.1102"); _choose_actual_event(world, "ywc_mng.1102", "new_record")
        _deliver_actual_event(world, "ywc_mng.1103"); _choose_actual_event(world, "ywc_mng.1103", "missing_record")
        for _ in range(6):
            self.assertIsNone(pulse_actual_journals(world))
        self.assertIsNone(pulse_actual_journals(world))
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1105)
        self.assertIn(jid, world.active_journals["MGL"])

        state["states"][0]["pops"] = [pop for pop in state["states"][0]["pops"]
                                       if pop.get("workplace") != "building_government_administration"]
        final_option = next(value for key, _, value in world.event_defs["ywc_mng.1105"]
                            if key == "option" and _block(value, "name") == "ywc_mng.1105.close")
        self.assertFalse(world.conditions(_block(final_option, "trigger"), "MGL"))
        world.run("ywc_mgl_mobile_settle", "MGL")
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1104)
        self.assertIn("ywc_mgl_mobile_paused", state)
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1,
                         "the completed six-month record survives a temporary post-maturity loss")
        self.assertNotIn("ywc_v03_mgl_v03_mgl_mobile_offices_settled", state)
        self.assertEqual(world.treasury["MGL"], -25)
        self.assertIn(jid, world.active_journals["MGL"])

        _deliver_actual_event(world, "ywc_mng.1104")
        state["states"][0]["pops"].append({"employed": True,
                                             "workplace": "building_government_administration"})
        _choose_actual_event(world, "ywc_mng.1104", "retry")
        self.assertIn(jid, world.active_journals["MGL"])
        self.assertNotIn("ywc_mgl_mobile_paused", state)
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1105)
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1)
        self.assertEqual(world.treasury["MGL"], -25)
        _deliver_actual_event(world, "ywc_mng.1105")
        _choose_actual_event(world, "ywc_mng.1105", "close")
        self.assertEqual(state.get("ywc_v03_mgl_v03_mgl_mobile_offices_outcome"), 3)

    def test_actual_entry_cannot_borrow_an_office_or_worker_from_another_state_or_country(self):
        from tests.test_v03_mgl_inline_actual_source import actual_mgl_inline_world, legal_ordinary_facts
        from tests.test_v03_mgl_actual_source import _block
        facts = legal_ordinary_facts()
        facts["laws"].add("law_hereditary_bureaucrats")
        # MGL owns an administration building in one state and its employed
        # clerk in a different state. SHU has both facts together; MGL may not
        # borrow either the foreign state or split same-employer evidence.
        first = facts["states"][0]
        first["pops"] = [pop for pop in first["pops"]
                         if pop.get("workplace") != "building_government_administration"]
        facts["states"].append({"market_access": 0.5, "buildings": [],
                                "pops": [{"employed": True,
                                          "workplace": "building_government_administration"}]})
        world, _ = actual_mgl_inline_world(admit_mobile=True, ordinary_facts=facts)
        world.countries["SHU"]["states"] = [{"buildings": [{"type": "building_government_administration"}],
                                             "pops": [{"employed": True,
                                                       "workplace": "building_government_administration"}]}]
        _deliver_actual_event(world, "ywc_mng.1100")
        event = world.event_defs["ywc_mng.1100"]
        for key in ("circuit", "joint", "quota"):
            option = next(value for name, _, value in event
                          if name == "option" and _block(value, "name") == f"ywc_mng.1100.{key}")
            self.assertFalse(world.conditions(_block(option, "trigger"), "MGL"), key)

    def test_actual_explicit_withdrawal_closes_once_without_route_reward(self):
        from tests.test_v03_mgl_actual_source import _refresh_actual_journal_lifecycle
        world, _ = _actual_mobile_world(admit_mobile=True)
        state = world.countries["MGL"]
        journal_id = "ywc_je_v03_mgl_mobile_offices"
        _deliver_actual_event(world, "ywc_mng.1100")
        _choose_actual_event(world, "ywc_mng.1100", "withdraw")
        _refresh_actual_journal_lifecycle(world)
        self.assertNotIn(journal_id, world.active_journals["MGL"])
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"], 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertFalse(any(row[1].get("name", "").startswith("ywc_v03_mgl_mobile_") for row in world.modifiers))
        world.run("ywc_mgl_mobile_withdraw", "MGL")
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"], 4)

    def test_actual_inline_mobile_dispatch_and_ack_reject_wrong_queue_epoch_and_receipt(self):
        from copy import deepcopy
        from tests.test_v03_mgl_inline_actual_source import actual_mgl_inline_world
        from tests.test_v03_mgl_actual_source import _block

        def reserved_world():
            world, _ = actual_mgl_inline_world(admit_mobile=True)
            world.run("ywc_v03_mgl_inline_prepare", "MGL")
            world.run("ywc_v03_mgl_inline_reserve_67", "MGL")
            self.assertTrue(world.condition(("ywc_v03_mgl_inline_dispatch_67", "=", "yes"), "MGL"))
            return world

        for mutation in ("queue", "epoch"):
            with self.subTest(mutation=mutation):
                world = reserved_world()
                state = world.countries["MGL"]
                if mutation == "queue":
                    state["ywc_mgl_mobile_pending_event"] = 1101
                else:
                    state["ywc_v03_mgl_inline_candidate_epoch_67"] += 1
                before = deepcopy(state)
                self.assertFalse(world.conditions(_block(world.event_defs["ywc_mng.1100"], "trigger"), "MGL"))
                world.execute(_block(world.event_defs["ywc_mng.1100"], "immediate"), "MGL")
                self.assertEqual(state, before)
                self.assertNotIn("ywc_v03_mgl_inline_served_4", state)
                self.assertNotIn("ywc_v03_mgl_inline_ack_67", world.named_effect_calls)

        # The native event body may have marked its legitimate cooldown before
        # the ACK. A deliberately stale post-body receipt must not add any more
        # queue, fairness, callback, or cooldown mutation.
        wrong_receipt = reserved_world()
        state = wrong_receipt.countries["MGL"]
        immediate = _block(wrong_receipt.event_defs["ywc_mng.1100"], "immediate")
        body = [row for row in immediate[0][2] if row[0] != "limit"]
        self.assertEqual(body[-1][0], "ywc_v03_mgl_inline_callback_67")
        wrong_receipt.execute(body[:-1], "MGL")
        state["ywc_v03_mgl_inline_body_completed_epoch_67"] = 999
        before_callback = deepcopy(state)
        wrong_receipt.run("ywc_v03_mgl_inline_callback_67", "MGL")
        self.assertEqual(state, before_callback)
        self.assertNotIn("ywc_v03_mgl_inline_served_4", state)
        self.assertNotIn("ywc_v03_mgl_inline_ack_67", wrong_receipt.named_effect_calls)

        correct, _ = actual_mgl_inline_world(admit_mobile=True)
        correct.run("ywc_v03_mgl_inline_prepare", "MGL")
        correct.run("ywc_v03_mgl_inline_reserve_67", "MGL")
        native = correct.event_defs["ywc_mng.1100"]
        self.assertTrue(correct.conditions(_block(native, "trigger"), "MGL"))
        correct.execute(_block(native, "immediate"), "MGL")
        self.assertIn("ywc_v03_mgl_inline_ack_67", correct.named_effect_calls)
        self.assertEqual(correct.countries["MGL"].get("ywc_v03_mgl_inline_served_4"),
                         correct.countries["MGL"].get("ywc_v03_mgl_inline_round"))
        self.assertNotIn("ywc_mgl_mobile_pending_event", correct.countries["MGL"])

    def test_actual_trade_road_outcome_changes_later_appeals_and_circuit_settlement(self):
        from tests.test_v03_mgl_actual_source import _block, pulse_actual_journals
        world, _ = _actual_mobile_world(root_slugs=["v03_mgl_two_trade_roads"],
                                        bureaucracy="law_appointed_bureaucrats", register_mobile=True)
        state = world.countries["MGL"]
        _complete_actual_local_foundation(world, first_event=1000,
            outcome_variable="ywc_v03_mgl_v03_mgl_two_trade_roads_outcome")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_two_trade_roads_outcome"], 3)
        journal_id = "ywc_je_v03_mgl_mobile_offices"
        world.activate_journal(journal_id)
        _deliver_actual_event(world, "ywc_mng.1100"); _choose_actual_event(world, "ywc_mng.1100", "circuit")
        self.assertEqual(world.treasury["MGL"], -150)
        _deliver_actual_event(world, "ywc_mng.1101"); _choose_actual_event(world, "ywc_mng.1101", "register")
        _deliver_actual_event(world, "ywc_mng.1102"); _choose_actual_event(world, "ywc_mng.1102", "roads_narrow")
        self.assertEqual(state.get("ywc_mgl_mobile_roads_influence"), 2)
        _deliver_actual_event(world, "ywc_mng.1103"); _choose_actual_event(world, "ywc_mng.1103", "roads_appeal")
        self.assertEqual(state.get("ywc_mgl_mobile_roads_reviewed"), 1)
        for _ in range(6):
            self.assertIsNone(pulse_actual_journals(world))
            self.assertNotIn("ywc_mgl_mobile_outcome_ready", state)
        self.assertIsNone(pulse_actual_journals(world))
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1)
        self.assertIn(journal_id, world.active_journals["MGL"])
        _deliver_actual_event(world, "ywc_mng.1105")
        _choose_actual_event(world, "ywc_mng.1105", "close")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"], 1)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_circuit" for row in world.modifiers))
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_road_ledger" for row in world.modifiers))
        self.assertFalse(any(row[1].get("name") == "ywc_v03_mgl_mobile_debt_appeals" for row in world.modifiers))
        settled = state["ywc_v03_mgl_v03_mgl_mobile_offices_settled"]
        world.run("ywc_mgl_mobile_settle", "MGL")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_settled"], settled)
        self.assertEqual(sum(row[1].get("name") == "ywc_v03_mgl_mobile_road_ledger" for row in world.modifiers), 1)

    def test_actual_pastoral_debt_outcome_changes_later_appeals_and_joint_settlement(self):
        from tests.test_v03_mgl_actual_source import pulse_actual_journals
        world, _ = _actual_mobile_world(root_slugs=["v03_mgl_pastoral_debt"], land_law="law_serfdom",
                                        register_mobile=True)
        state = world.countries["MGL"]
        _complete_actual_local_foundation(world, first_event=1010,
            outcome_variable="ywc_v03_mgl_v03_mgl_pastoral_debt_outcome")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_pastoral_debt_outcome"], 3)
        journal_id = "ywc_je_v03_mgl_mobile_offices"
        world.activate_journal(journal_id)
        _deliver_actual_event(world, "ywc_mng.1100"); _choose_actual_event(world, "ywc_mng.1100", "joint")
        self.assertEqual(world.treasury["MGL"], -100)
        _deliver_actual_event(world, "ywc_mng.1101"); _choose_actual_event(world, "ywc_mng.1101", "register")
        _deliver_actual_event(world, "ywc_mng.1102"); _choose_actual_event(world, "ywc_mng.1102", "debt_limited")
        self.assertEqual(state.get("ywc_mgl_mobile_debt_influence"), 2)
        _deliver_actual_event(world, "ywc_mng.1103"); _choose_actual_event(world, "ywc_mng.1103", "debt_appeal")
        self.assertEqual(state.get("ywc_mgl_mobile_debt_reviewed"), 1)
        for _ in range(6):
            self.assertIsNone(pulse_actual_journals(world))
            self.assertNotIn("ywc_mgl_mobile_outcome_ready", state)
        self.assertIsNone(pulse_actual_journals(world))
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1)
        _deliver_actual_event(world, "ywc_mng.1105")
        _choose_actual_event(world, "ywc_mng.1105", "close")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"], 2)
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_joint" for row in world.modifiers))
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_debt_appeals" for row in world.modifiers))
        self.assertFalse(any(row[1].get("name") == "ywc_v03_mgl_mobile_road_ledger" for row in world.modifiers))

    def test_actual_law_loss_revises_paid_circuit_to_quota_only_after_second_payment(self):
        from tests.test_v03_mgl_actual_source import pulse_actual_journals, _block
        world, _ = _actual_mobile_world(root_slugs=["v03_mgl_two_trade_roads"],
                                        bureaucracy="law_appointed_bureaucrats", register_mobile=True)
        state = world.countries["MGL"]
        _complete_actual_local_foundation(world, first_event=1000,
            outcome_variable="ywc_v03_mgl_v03_mgl_two_trade_roads_outcome")
        world.activate_journal("ywc_je_v03_mgl_mobile_offices")
        _deliver_actual_event(world, "ywc_mng.1100"); _choose_actual_event(world, "ywc_mng.1100", "circuit")
        self.assertEqual(world.treasury["MGL"], -150)
        _deliver_actual_event(world, "ywc_mng.1101"); _choose_actual_event(world, "ywc_mng.1101", "register")
        _deliver_actual_event(world, "ywc_mng.1102"); _choose_actual_event(world, "ywc_mng.1102", "roads_narrow")
        _deliver_actual_event(world, "ywc_mng.1103"); _choose_actual_event(world, "ywc_mng.1103", "roads_appeal")
        state["laws"].discard("law_appointed_bureaucrats")
        state["laws"].add("law_hereditary_bureaucrats")
        self.assertIsNone(pulse_actual_journals(world))
        self.assertIn("ywc_mgl_mobile_paused", state)
        _deliver_actual_event(world, "ywc_mng.1104")
        revise = next(value for key, _, value in world.event_defs["ywc_mng.1104"]
                      if key == "option" and _block(value, "name") == "ywc_mng.1104.revise")
        self.assertTrue(world.conditions(_block(revise, "trigger"), "MGL"))
        _choose_actual_event(world, "ywc_mng.1104", "revise")
        self.assertEqual(state.get("ywc_mgl_mobile_route"), 3)
        self.assertEqual(world.treasury["MGL"], -175)
        for _ in range(6):
            self.assertIsNone(pulse_actual_journals(world))
            self.assertNotIn("ywc_mgl_mobile_outcome_ready", state)
        self.assertIsNone(pulse_actual_journals(world))
        self.assertEqual(state.get("ywc_mgl_mobile_outcome_ready"), 1)
        _deliver_actual_event(world, "ywc_mng.1105")
        _choose_actual_event(world, "ywc_mng.1105", "close")
        self.assertEqual(state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"], 3)
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_quota" for row in world.modifiers))
        self.assertFalse(any(row[1].get("name") == "ywc_v03_mgl_mobile_circuit" for row in world.modifiers))
        self.assertTrue(any(row[1].get("name") == "ywc_v03_mgl_mobile_road_ledger" for row in world.modifiers))

    def test_inline_scheduler_appends_six_candidates_after_frozen_foundation_ids(self):
        from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog
        catalog = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
        rendered = render_inline_country_adapters(catalog)
        self.assertIn("ywc_v03_mgl_inline_dispatch_67", rendered["effects"])
        self.assertIn("ywc_v03_mgl_inline_dispatch_72", rendered["effects"])
        self.assertIn("ywc_v03_mgl_inline_served_4", rendered["effects"])
        self.assertEqual(rendered["event_hooks"]["ywc_mng.1100"], ["ywc_v03_mgl_inline_dispatch_67"])
        self.assertEqual(rendered["ack_hooks"]["ywc_mng.1100"], ["ywc_v03_mgl_inline_callback_67"])
        tampered = json.loads(json.dumps(catalog))
        tampered["arcs"][-1]["inline_delivery_adapter"]["branches"][0]["candidates"][0]["value"] = 1101
        with self.assertRaisesRegex(ValueError, "source sender binding drift"):
            validate_inline_catalog(tampered)
        unknown = json.loads(json.dumps(catalog))
        extra = json.loads(json.dumps(unknown["arcs"][-1]))
        extra["slug"] = "v03_mgl_unregistered_middle"
        unknown["arcs"].append(extra)
        with self.assertRaisesRegex(ValueError, "only its registered mobile-offices"):
            validate_inline_catalog(unknown)
        unknown_phase = json.loads(json.dumps(catalog))
        unknown_phase["arcs"][-1]["inline_delivery_adapter"]["live_phases"][0]["unexpected_receipt_alias"] = "unbound"
        with self.assertRaisesRegex(ValueError, "live phase binding is malformed"):
            validate_inline_catalog(unknown_phase)
        with self.assertRaisesRegex(ValueError, "live phase binding is malformed"):
            render_inline_country_adapters(unknown_phase)

    def test_frozen_foundation_trigger_prefix_preserves_content_across_line_endings(self):
        import subprocess
        relative = "yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt"
        frozen = subprocess.check_output(["git", "show", f"c7ca59ca16092df816828f19a229cdc5dd0ac5a2:{relative}"], cwd=ROOT)
        current = (ROOT / relative).read_bytes()
        self.assertTrue(_canonical_git_text_newlines(current).startswith(
            _canonical_git_text_newlines(frozen)))
        simulated_crlf_checkout = _canonical_git_text_newlines(current).replace(b"\n", b"\r\n")
        self.assertTrue(_canonical_git_text_newlines(simulated_crlf_checkout).startswith(
            _canonical_git_text_newlines(frozen)))

    def test_frozen_foundation_effect_prefix_and_catalog_arcs_preserve_base_content(self):
        import subprocess
        effect_path = "yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt"
        frozen_effects = subprocess.check_output(
            ["git", "show", f"c7ca59ca16092df816828f19a229cdc5dd0ac5a2:{effect_path}"], cwd=ROOT)
        current_effects = (ROOT / effect_path).read_bytes()
        self.assertTrue(_canonical_git_text_newlines(current_effects).startswith(
            _canonical_git_text_newlines(frozen_effects)))
        simulated_crlf_effects = _canonical_git_text_newlines(current_effects).replace(b"\n", b"\r\n")
        self.assertTrue(_canonical_git_text_newlines(simulated_crlf_effects).startswith(
            _canonical_git_text_newlines(frozen_effects)))
        frozen_catalog = json.loads(subprocess.check_output(
            ["git", "show", "c7ca59ca16092df816828f19a229cdc5dd0ac5a2:data/content/v03/countries/mgl.json"],
            cwd=ROOT).decode("utf-8"))
        current = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
        old = {arc["slug"]: arc for arc in current["arcs"] if arc["era"] == "foundation"}
        self.assertEqual(old, {arc["slug"]: arc for arc in frozen_catalog["arcs"]})

    def test_actual_cash_loss_and_early_law_change_pause_then_recover_without_refund(self):
        world = _runtime_world(foundations=(("pastoral_debt", 1),))
        world.run("ywc_mgl_mobile_pay_joint", "MGL")
        state = world.countries["MGL"]
        world.run("ywc_mgl_mobile_commit", "MGL")
        world.run("ywc_mgl_mobile_begin_observation", "MGL")
        state["laws"].discard("law_hereditary_bureaucrats")
        state["laws"].add("law_appointed_bureaucrats")
        world.run("ywc_mgl_mobile_monthly_review", "MGL")
        self.assertEqual(state.get("ywc_mgl_mobile_pending_event"), 1104)
        self.assertIn("ywc_mgl_mobile_paused", state)
        self.assertEqual(world.treasury["MGL"], -50)
        state["laws"].discard("law_appointed_bureaucrats")
        state["laws"].add("law_hereditary_bureaucrats")
        world.run("ywc_mgl_mobile_retry", "MGL")
        self.assertNotIn("ywc_mgl_mobile_paused", state)
        self.assertNotIn("ywc_mgl_mobile_pending_event", state)

    def test_actual_withdrawal_closes_once_and_records_failure(self):
        world = _runtime_world(route="quota")
        state = world.countries["MGL"]
        state["ywc_v03_active_arc_count"] = 1
        state["ywc_v03_visible_task_count"] = 1
        world.run("ywc_mgl_mobile_withdraw", "MGL")
        outcome = state["ywc_v03_mgl_v03_mgl_mobile_offices_outcome"]
        world.run("ywc_mgl_mobile_withdraw", "MGL")
        self.assertEqual(outcome, 4)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_mobile_helpers_are_distinct_and_recheck_employment_and_cash(self):
        effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt").read_text(encoding="utf-8-sig")
        triggers = (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt").read_text(encoding="utf-8-sig")
        self.assertIn("ywc_mgl_mobile_pay_circuit", effects)
        self.assertIn("ywc_mgl_mobile_withdraw", effects)
        self.assertIn("ywc_mgl_mobile_monthly_review", effects)
        self.assertIn("is_building_type = building_government_administration", triggers)
        self.assertIn("law_hereditary_bureaucrats", triggers)
        self.assertIn("law_appointed_bureaucrats", triggers)
        self.assertIn("gold_reserves >= var:ywc_mgl_mobile_fee", effects)
        from tools.v03_inline_delivery_adapter import validate_mgl_native_helper_source
        mutated = triggers.replace("has_building = building_government_administration",
                                   "has_building = building_trade_center", 1)
        with self.assertRaisesRegex(ValueError, "MGL mobile trigger AST drift"):
            validate_mgl_native_helper_source(mutated)


if __name__ == "__main__":
    unittest.main()
