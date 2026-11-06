"""Offline acceptance checks for DMG's common-subjects content card."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from clausewitz_harness import PulseWorld, parse

CATALOG_PATH = ROOT / "data/content/v03/countries/dmg.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_dmg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_dmg_triggers.txt"
EVENT_IDS = [f"ywc_dmg.{number}" for number in range(1000, 1010)]
JE_IDS = ["ywc_je_v03_dmg_public_qualification", "ywc_je_v03_dmg_compact_review"]

class DmgContentCardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.arc = cls.catalog["arcs"][0]
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")

    def test_locked_identity_and_complete_bilingual_card(self):
        self.assertEqual(self.catalog["key"], "country_dmg")
        self.assertEqual(self.catalog["layer"], "country")
        self.assertEqual(self.catalog["runtime_tags"], ["DMG"])
        self.assertEqual(self.arc["slug"], "v03_dmg_common_subjects")
        self.assertEqual(self.arc["era"], "foundation")
        self.assertEqual([row["id"] for row in self.arc["events"]], EVENT_IDS)
        self.assertEqual([row["id"] for row in self.arc["journals"]], JE_IDS)
        for event in self.arc["events"]:
            for field in ("title", "desc"):
                self.assertTrue(event[field]["zh"] and event[field]["en"])
            self.assertGreaterEqual(len(event["options"]), 3)
            for option in event["options"]:
                for field in ("label", "cost_note", "consequence_note"):
                    self.assertTrue(option[field]["zh"] and option[field]["en"])
        for journal in self.arc["journals"]:
            for field in ("title", "desc"):
                self.assertTrue(journal[field]["zh"] and journal[field]["en"])
            self.assertNotRegex(journal["script"], r"(?m)^\s*(complete|fail)\s*=")
            self.assertNotEqual(journal["goal"].strip(), "{ always = yes }")
            self.assertNotEqual(journal["exit_conditions"].strip(), "{ always = yes }")

    def test_je_goal_preserves_stage_or_and_excludes_actual_abandoned_terminal(self):
        goal = self.arc["journals"][0]["goal"]
        # The harness parser accepts a block body; strip the JSON field's outer braces.
        nodes = parse(goal.strip()[1:-1])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0][0:2], ("AND", "="))
        old_or = next(body for key, _, body in nodes[0][2] if key == "OR")
        self.assertEqual(old_or, [
            ("has_variable", "=", "ywc_dmg_first_stage_resolved"),
            ("has_variable", "=", "ywc_dmg_outcome_withdrawn_breach")])
        exclusion = next(body for key, _, body in nodes[0][2] if key == "NOT")
        self.assertEqual(exclusion, [("has_variable", "=", "ywc_dmg_arc_abandoned")])
        for terminal in ("ywc_dmg_first_stage_resolved", "ywc_dmg_outcome_withdrawn_breach"):
            world = PulseWorld("", {"DMG": {terminal: 1}})
            self.assertTrue(world.conditions(nodes, tag="DMG"), terminal)
            world.countries["DMG"]["ywc_dmg_arc_abandoned"] = 1
            self.assertFalse(world.conditions(nodes, tag="DMG"), terminal)
        world = PulseWorld("", {"DMG": {}})
        self.assertFalse(world.conditions(nodes, tag="DMG"))


    def test_reads_and_writes_are_backed_by_script_or_helper_references(self):
        authored = [self.effects, self.triggers]
        for journal in self.arc["journals"]:
            authored.extend([journal["script"], journal["goal"], journal["exit_conditions"]])
        for event in self.arc["events"]:
            authored.append(" ".join([event.get("trigger", ""), event.get("immediate", ""),
                                      *(option.get("effect", "") for option in event["options"]) ]))
        scripts = "\n".join(authored)
        for event in self.arc["events"]:
            for field in ("reads", "writes"):
                for symbol in event[field]:
                    self.assertIn(symbol, scripts, f"{event['id']} {field}: {symbol}")


    def test_full_acceptance_and_same_secondary_pop_must_occupy_real_workplace(self):
        trigger_nodes = parse(self.triggers)
        trigger = next(body for key, _, body in trigger_nodes if key == "ywc_dmg_v03_has_fully_accepted_secondary_pop")
        rendered = self.triggers
        self.assertIn("acceptance_status_5", rendered)
        self.assertIn("is_employed = yes", rendered)
        self.assertIn("workplace ?=", rendered)
        self.assertIn("building_barrack", rendered)
        military = next(body for key, _, body in self._walk(list(parse(self.triggers))) if key == "ywc_dmg_v03_military_appointment_ready")
        self.assertIn("soldiers", str(military))
        self.assertIn("officers", str(military))
        self.assertNotIn("building_barracks", rendered)
        # Acceptance, employment and building facts are nested under the same pop scope.
        office = next(body for key, _, body in self._walk(list(parse(self.triggers))) if key == "ywc_dmg_v03_government_appointment_ready")
        pop = next(body for key, _, body in self._walk(office) if key == "any_scope_pop")
        pop_text = str(pop)
        self.assertIn("pop_acceptance", pop_text)
        self.assertIn("is_employed", pop_text)
        self.assertIn("workplace", pop_text)
        official = Path(r"E:\\SteamLibrary\\steamapps\\common\\Victoria 3\\game\\common\\acceptance_statuses\\00_acceptance_statuses.txt")
        if official.exists():
            source = official.read_text(encoding="utf-8-sig")
            self.assertRegex(source, r"second_rate_citizen\s*=\s*\{[^}]*threshold\s*=\s*60")
            self.assertRegex(source, r"full_acceptance\s*=\s*\{[^}]*threshold\s*=\s*80")
        building = Path(r"E:\\SteamLibrary\\steamapps\\common\\Victoria 3\\game\\common\\buildings\\05_military.txt")
        if building.exists():
            self.assertRegex(building.read_text(encoding="utf-8-sig"), r"(?m)^building_barrack\s*=")

    @staticmethod
    def _walk(nodes):
        for node in nodes:
            yield node
            if isinstance(node[2], list):
                yield from DmgContentCardTest._walk(node[2])

    def test_withdrawal_commits_breach_and_terminal_choices_always_have_escape(self):
        e8 = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1008")
        withdrawal = next(o for o in e8["options"] if o["key"] == "third")
        self.assertIn("ywc_dmg_close_as_breach = yes", withdrawal["effect"])
        e9 = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1009")
        self.assertTrue(any(o["key"] == "limited_settlement" for o in e9["options"]))
        self.assertTrue(any(o["key"] == "withdraw_breach" for o in e9["options"]))
        for o in e9["options"]:
            self.assertTrue(o["trigger"].strip().startswith("{"))
        for key in ("limited_settlement", "withdraw_breach"):
            fallback = next(o for o in e9["options"] if o["key"] == key)
            self.assertIn("ywc_dmg_review_matured", fallback["trigger"])
            self.assertIn("var:ywc_dmg_review_notice_response_context = 12", fallback["trigger"])
            self.assertIn("var:ywc_v03_dmg_v03_dmg_common_subjects_last_event = 10",
                          fallback["trigger"])

    def test_legacy_bridge_is_idempotent_and_new_arc_does_not_stop_old_pulse(self):
        bridge = next(block for key, _, block in parse(self.effects) if key == "ywc_v03_bridge_dmg_compact_one")
        text = str(bridge)
        self.assertIn("ywc_campaign_dmg_c1_outcome", text)
        self.assertIn("ywc_je_flavor_dmg_compact_2", text)
        self.assertIn("has_journal_entry', '=', 'ywc_je_flavor_dmg_compact_2", text)
        self.assertIn("ywc_je_flavor_dmg_compact_2_resolved", text)
        self.assertIn("ywc_je_flavor_dmg_compact_2_failed", text)
        old_je = Path(ROOT / "yongchang_world/common/journal_entries/ywc_dmg.txt").read_text(encoding="utf-8-sig")
        c1 = old_je.split("ywc_je_flavor_dmg_compact_1 = {", 1)[1].split("ywc_je_flavor_dmg_compact_2 = {", 1)[0]
        self.assertIn("ywc_v03_dmg_v03_dmg_common_subjects_started", c1)
        self.assertIn("NOT = { has_variable = ywc_v03_dmg_v03_dmg_common_subjects_started }", c1)


    def test_bridge_maps_new_outcomes_and_never_overwrites_existing_old_result(self):
        for new_outcome, expected in ((1,1),(2,2),(3,2),(4,3),(5,3)):
            world=PulseWorld(self.effects, {"DMG":{"ywc_v03_dmg_v03_dmg_common_subjects_outcome":new_outcome}})
            world.run("ywc_v03_bridge_dmg_compact_one", tag="DMG")
            world.run("ywc_v03_bridge_dmg_compact_one", tag="DMG")
            self.assertEqual(world.countries["DMG"]["ywc_campaign_dmg_c1_outcome"],expected)
            self.assertEqual(sum(1 for tag, body in world.journals if tag=="DMG" and dict((k,v) for k,_,v in body).get("type")=="ywc_je_flavor_dmg_compact_2"),1)
        world=PulseWorld(self.effects,{"DMG":{"ywc_campaign_dmg_c1_outcome":2,"ywc_v03_dmg_v03_dmg_common_subjects_outcome":1}})
        world.run("ywc_v03_bridge_dmg_compact_one",tag="DMG")
        self.assertEqual(world.countries["DMG"]["ywc_campaign_dmg_c1_outcome"],2)


    def test_local_execution_fee_is_income_based_idempotent_and_game_assets_have_bom(self):
        world=PulseWorld(self.effects,{"DMG":{"yearly_gross_income":52000,"gold_reserves":2000}})
        world.run("ywc_dmg_pay_local_rollout_once",tag="DMG")
        first=world.treasury["DMG"]
        self.assertAlmostEqual(first,-1000,places=5)
        world.run("ywc_dmg_pay_local_rollout_once",tag="DMG")
        self.assertEqual(world.treasury["DMG"],first)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_local_rollout_cost_paid"],1)
        assets=[EFFECTS_PATH,TRIGGERS_PATH,ROOT/"yongchang_world/common/journal_entries/ywc_dmg.txt",ROOT/"yongchang_world/common/static_modifiers/ywc_v03_dmg_modifiers.txt",ROOT/"yongchang_world/localization/english/ywc_v03_dmg_modifiers_l_english.yml",ROOT/"yongchang_world/localization/simp_chinese/ywc_v03_dmg_modifiers_l_simp_chinese.yml",ROOT/"yongchang_world/events/ywc_v03_country_dmg_events.txt",ROOT/"yongchang_world/common/journal_entries/ywc_v03_country_dmg_journal.txt",ROOT/"yongchang_world/localization/english/ywc_v03_country_dmg_l_english.yml",ROOT/"yongchang_world/localization/simp_chinese/ywc_v03_country_dmg_l_simp_chinese.yml"]
        for path in assets:
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"),str(path))
        modifiers=Path(ROOT/"yongchang_world/common/static_modifiers/ywc_v03_dmg_modifiers.txt").read_text(encoding="utf-8-sig")
        declared=set(dict((key,body) for key,_,body in parse(modifiers)))
        for name in ("ywc_dmg_joint_council","ywc_dmg_noble_guarantee","ywc_dmg_royal_directive","ywc_dmg_language_central_forms","ywc_dmg_language_translation","ywc_dmg_language_old_register","ywc_dmg_precedent_central","ywc_dmg_precedent_local_courts","ywc_dmg_precedent_lineage"):
            self.assertIn(name,declared)

    def test_local_contract_has_real_gate_fee_finite_tradeoffs_and_later_reads(self):
        territory = next(t for key, _, t in parse(self.triggers) if key == "ywc_dmg_v03_territorial_compact_ready")
        self.assertIn("ywc_dmg_appeal_mechanism", str(territory))
        self.assertIn("ywc_dmg_inheritance_precedent", self.effects + json.dumps(self.arc))
        self.assertIn("ywc_dmg_public_language_mode", self.effects + json.dumps(self.arc))
        for name in ("ywc_dmg_joint_council", "ywc_dmg_noble_guarantee", "ywc_dmg_royal_directive"):
            self.assertIn(name, Path(ROOT / "yongchang_world/common/static_modifiers/ywc_v03_dmg_modifiers.txt").read_text(encoding="utf-8-sig"))
        self.assertIn("months = 24", self.effects)
        self.assertIn("remove_modifier = ywc_dmg_joint_council", self.effects)
        self.assertIn("country_legitimacy_base_add", Path(ROOT / "yongchang_world/common/static_modifiers/ywc_v03_dmg_modifiers.txt").read_text(encoding="utf-8-sig"))

    def test_scripted_employment_predicate_with_injected_engine_facts_uses_same_pop_and_building(self):
        triggers = dict((key, body) for key, _, body in parse(self.triggers))
        nodes = triggers["ywc_dmg_v03_government_appointment_ready"]
        def eval_nodes(tree, scope, country):
            for key, op, value in tree:
                if key == "AND" and not all(eval_nodes([child], scope, country) for child in value): return False
                if key == "OR" and not any(eval_nodes([child], scope, country) for child in value): return False
                if key == "NOT" and eval_nodes(value, scope, country): return False
                if key == "bureaucracy" and not (country["bureaucracy"] >= float(value)): return False
                # Legacy spelling is fixture compatibility, not engine syntax.
                if key in ("owner", "is_owned_by"):
                    if (op, value) != ("=", "ROOT"):
                        raise AssertionError(("unsupported state owner", key, op, value))
                    if scope.get("owner") != country["tag"]: return False
                if key == "any_scope_state" and not any(eval_nodes(value, state, country) for state in country["states"]): return False
                if key == "any_scope_pop" and not any(eval_nodes(value, pop, country) for pop in scope["pops"]): return False
                if key == "pop_has_primary_culture" and scope.get("primary") != (value == "yes"): return False
                if key == "pop_acceptance" and not (scope.get("acceptance", 0) >= (5 if value == "acceptance_status_5" else 4)): return False
                if key == "is_pop_type" and scope.get("pop_type") != value: return False
                if key == "is_employed" and scope.get("employed") != (value == "yes"): return False
                if key == "workplace" and op == "?=":
                    if scope.get("workplace") is None or not eval_nodes(value, scope["workplace"], country): return False
                if key == "is_building_type" and scope.get("building_type") != value: return False
                if key == "occupancy" and not (scope.get("occupancy", 0) >= float(value)): return False
                if key == "building_has_goods_shortage" and scope.get("shortage") != (value == "yes"): return False
            return True
        def facts(popset):
            state = {"owner":"DMG", "pops":popset}
            return {"tag":"DMG", "bureaucracy":0, "states":[state]}
        def pop(primary=False, acceptance=5, employed=False, workplace=None, pop_type="bureaucrats"):
            return {"primary":primary, "acceptance":acceptance, "employed":employed, "workplace":workplace, "pop_type":pop_type}
        admin={"building_type":"building_government_administration", "occupancy":0.8, "shortage":False}
        self.assertFalse(eval_nodes(nodes, {}, facts([pop(acceptance=5, employed=False), pop(primary=True, employed=True, workplace=admin)])))
        self.assertFalse(eval_nodes(nodes, {}, facts([pop(acceptance=4, employed=True, workplace=admin)])))
        self.assertFalse(eval_nodes(nodes, {}, facts([pop(acceptance=5, employed=True, workplace={**admin,"occupancy":0.79})])))
        self.assertTrue(eval_nodes(nodes, {}, facts([pop(acceptance=5, employed=True, workplace=admin)])))
        for owner in ("KOR", None):
            foreign = facts([pop(acceptance=5, employed=True, workplace=admin)])
            if owner is None:
                foreign["states"][0].pop("owner")
            else:
                foreign["states"][0]["owner"] = owner
            self.assertFalse(eval_nodes(nodes, {}, foreign))

    def test_scripts_use_real_acceptance_and_job_eligibility_checks(self):
        self.assertIn("any_scope_pop", self.triggers)
        self.assertIn("pop_acceptance", self.triggers)
        self.assertIn("acceptance_status_2", self.triggers)
        self.assertIn("workplace ?=", self.triggers)
        self.assertIn("building_government_administration", self.triggers)
        self.assertIn("building_barrack", self.triggers)
        self.assertNotIn("building_barracks", self.triggers)
        self.assertIn("occupancy >= 0.8", self.triggers)
        self.assertIn("building_has_goods_shortage = no", self.triggers)
        # A cohort's acceptance and the presence of occupied jobs remain separate predicates.
        self.assertNotIn("ywc_dmg_v03_common_qualification_ready = {\n\tany_scope_pop", self.triggers)
        official = Path(r"E:\SteamLibrary\steamapps\common\Victoria 3\game\common\laws\00_citizenship.txt")
        if official.exists():
            self.assertIn("law_subjecthood", official.read_text(encoding="utf-8-sig"))


    def test_monthly_pulse_is_wrapped_and_six_month_clock_tracks_continuous_readiness(self):
        for journal in self.arc["journals"]:
            self.assertRegex(journal["script"], r"on_monthly_pulse\s*=\s*\{\s*effect\s*=\s*\{")
        public = self.arc["journals"][0]["script"]
        self.assertIn("ywc_dmg_v03_selected_route_ready = yes", public)
        self.assertIn("set_variable = { name = ywc_dmg_first_stage_due value = 1 months = 6 }", public)
        self.assertIn("remove_variable = ywc_dmg_first_stage_due", public)
        self.assertIn("has_variable = ywc_dmg_first_stage_ready_once", public)
        e6 = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1006")
        self.assertIn("ywc_dmg_first_stage_matured", e6["trigger"])
        self.assertIn("ywc_dmg_first_stage_matured", e6["trigger"])
        self.assertIn("has_variable = ywc_dmg_review_matured", next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1009")["trigger"])


    def test_extracted_pulse_effect_runs_six_continuous_months_and_restarts_after_break(self):
        journal = self.arc["journals"][0]
        script_nodes = parse(journal["script"])
        pulse = next(body for key, _, body in script_nodes if key == "on_monthly_pulse")
        pulse_effect = next(body for key, _, body in pulse if key == "effect")
        self.assertTrue(pulse_effect)

        world = PulseWorld(self.effects, {"DMG": {
            "ywc_dmg_v03_selected_route_ready": 1,
            "ywc_dmg_blocked_12_due": 1,
            "ywc_dmg_blocked_36_due": 1,
        }})
        world.months_until_expiry["DMG"].update({
            "ywc_dmg_blocked_12_due": 12, "ywc_dmg_blocked_36_due": 36
        })
        base_condition = world.condition
        def condition(node, tag):
            key = node[0]
            if key == "ywc_dmg_v03_selected_route_ready":
                return bool(world.countries[tag].get("ywc_dmg_v03_selected_route_ready"))
            if key == "ywc_dmg_v03_has_owned_state":
                return True
            if key == "ywc_v03_can_deliver_major":
                return False  # keep the shared 90-day delivery gate closed in this offline simulation
            return base_condition(node, tag)
        world.condition = condition

        def pulse_month():
            world.execute(pulse_effect, "DMG")
        pulse_month()
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_first_stage_due"], 6)
        for _ in range(3):
            world.advance_months(1)
            pulse_month()
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 0
        pulse_month()
        self.assertNotIn("ywc_dmg_first_stage_due", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_first_stage_matured", world.countries["DMG"])
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 1
        pulse_month()
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_first_stage_due"], 6)
        for _ in range(5):
            world.advance_months(1)
            pulse_month()
        self.assertNotIn("ywc_dmg_first_stage_matured", world.countries["DMG"])
        world.advance_months(1)
        pulse_month()
        self.assertEqual(world.countries["DMG"]["ywc_dmg_first_stage_matured"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_pending_event"], 1006)

    def test_je2_review_is_nine_continuous_months_of_selected_route_fulfillment(self):
        journal = self.arc["journals"][1]
        nodes = parse(journal["script"])
        pulse = next(body for key, _, body in nodes if key == "on_monthly_pulse")
        effect = next(body for key, _, body in pulse if key == "effect")
        pulse_text = journal["script"]
        self.assertIn("ywc_dmg_v03_selected_route_ready", pulse_text)
        self.assertIn("ywc_dmg_review_due", pulse_text)
        self.assertIn("ywc_dmg_review_matured", pulse_text)
        self.assertIn("remove_variable = ywc_dmg_review_due", pulse_text)
        self.assertIn("remove_variable = ywc_dmg_review_matured", pulse_text)
        event = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1009")
        self.assertIn("has_variable = ywc_dmg_review_matured", event["trigger"])
        for option in event["options"][:3]:
            self.assertIn("ywc_dmg_review_matured", option.get("trigger", ""))

    def test_je2_review_clock_restarts_after_lost_fulfillment(self):
        journal = self.arc["journals"][1]
        pulse = next(body for key, _, body in parse(journal["script"]) if key == "on_monthly_pulse")
        pulse_effect = next(body for key, _, body in pulse if key == "effect")
        world = PulseWorld(self.effects, {"DMG": {"ywc_dmg_v03_selected_route_ready": 1}})
        original_condition = world.condition

        def condition(node, tag):
            if node[0] == "ywc_dmg_v03_selected_route_ready":
                return bool(world.countries[tag].get("ywc_dmg_v03_selected_route_ready"))
            if node[0] == "ywc_dmg_v03_has_owned_state":
                return True
            if node[0] == "ywc_v03_can_deliver_major":
                return False
            return original_condition(node, tag)

        world.condition = condition
        world.execute(pulse_effect, "DMG")
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_review_due"], 9)
        for _ in range(4):
            world.advance_months()
            world.execute(pulse_effect, "DMG")
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 0
        world.execute(pulse_effect, "DMG")
        self.assertNotIn("ywc_dmg_review_due", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_review_matured", world.countries["DMG"])
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 1
        world.execute(pulse_effect, "DMG")
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_review_due"], 9)
        for _ in range(8):
            world.advance_months()
            world.execute(pulse_effect, "DMG")
        self.assertNotIn("ywc_dmg_review_matured", world.countries["DMG"])
        world.advance_months()
        world.execute(pulse_effect, "DMG")
        self.assertEqual(world.countries["DMG"]["ywc_dmg_review_matured"], 1)

    def test_common_qualification_excludes_reserved_service_and_checks_current_franchise(self):
        common = next(body for key, _, body in parse(self.triggers) if key == "ywc_dmg_v03_common_route_ready")
        common_text = str(common)
        self.assertIn("ywc_dmg_service_qualification", common_text)
        self.assertRegex(common_text, r"var:ywc_dmg_service_qualification', '<', '3")
        politics = next(body for key, _, body in parse(self.triggers)
                        if key == "ywc_dmg_v03_common_political_qualification_ready")
        politics_text = self.triggers
        self.assertIn("country_has_voting_franchise = yes", politics_text)
        self.assertIn("country_bureaucrats_voting_power_add", politics_text)
        self.assertIn("ROOT.modifier:country_voting_power_wealth_threshold_add", politics_text)
        self.assertIn("ROOT.modifier:country_voting_power_base_add", politics_text)
        self.assertIn("ROOT.modifier:country_bureaucrats_voting_power_add", politics_text)
        self.assertIn("ROOT.modifier:country_officers_voting_power_add", politics_text)
        self.assertIn("ROOT.modifier:country_voting_power_from_literacy_add", politics_text)
        self.assertIn("country_voting_power_from_literacy_add", politics_text)
        self.assertIn("literacy_rate > 0", politics_text)
        self.assertIn("ywc_dmg_v03_electoral_representative_ready", politics_text)
        self.assertIn("country_allow_voting_full_acceptance_bool", politics_text)
        self.assertIn("var:ywc_dmg_appeal_mechanism = 1", politics_text)
        self.assertNotIn("has_modifier = ywc_dmg_joint_council", politics_text)
        self.assertIn("country_has_voting_franchise = no", politics_text)

    def test_installed_11311_sources_support_used_electoral_accessors(self):
        game = Path(r"E:\SteamLibrary\steamapps\common\Victoria 3\game\common")
        triggers = (game / "scripted_triggers/00_scripted_triggers.txt").read_text(encoding="utf-8-sig")
        laws = (game / "laws/00_distribution_of_power.txt").read_text(encoding="utf-8-sig")
        citizenship = (game / "laws/00_citizenship.txt").read_text(encoding="utf-8-sig")
        bureaucracy = (game / "pop_types/bureaucrats.txt").read_text(encoding="utf-8-sig")
        capitalists = (game / "pop_types/capitalists.txt").read_text(encoding="utf-8-sig")
        modifiers = (game / "modifier_type_definitions/00_modifier_types.txt").read_text(encoding="utf-8-sig")
        self.assertIn("country_has_voting_franchise = {", triggers)
        self.assertIn("country_bureaucrats_voting_power_add", triggers)
        self.assertIn("country_aristocrats_voting_power_add", laws)
        self.assertIn("country_officers_voting_power_add", laws)
        self.assertIn("country_allow_voting_full_acceptance_bool = yes", citizenship)
        self.assertIn("literacy_rate > 0.2", bureaucracy)
        self.assertIn("wealth > 10", capitalists)
        self.assertIn("country_voting_power_wealth_threshold_add={", modifiers)
        branch = Path(r"E:\SteamLibrary\steamapps\common\Victoria 3\caligula_branch.txt")
        self.assertIn("release/1.13.11", branch.read_text(encoding="utf-8-sig"))

    def test_cost_is_income_based_once_and_old_status_route_has_separate_cost(self):
        self.assertIn("value = yearly_gross_income", self.effects)
        self.assertIn("divide = 52", self.effects)
        self.assertIn("max = 100", self.effects)
        self.assertRegex(self.effects, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_dmg_[a-z_]+cost")
        self.assertIn("ywc_dmg_compensation_paid", self.effects)
        self.assertIn("ywc_dmg_status_orders_cost_paid", self.effects)
        opening = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1000")
        self.assertIn("年总收入÷52", json.dumps(opening, ensure_ascii=False))
        self.assertIn("最低100", json.dumps(opening, ensure_ascii=False))

    def test_early_laws_do_not_fake_jobs_and_routes_remain_distinct(self):
        for outcome in ("common_qualification", "territorial_compact", "status_orders", "withdrawn_breach"):
            self.assertIn(f"ywc_dmg_outcome_{outcome}", self.effects)
        self.assertIn("ywc_dmg_v03_government_appointment_ready", self.triggers)
        self.assertIn("ywc_dmg_v03_military_appointment_ready", self.triggers)
        self.assertIn("bureaucracy >= 0", self.triggers)
        self.assertIn("ywc_dmg_appointment_actual", self.effects)
        self.assertIn("ywc_dmg_pay_compensation_once", self.effects)
        self.assertIn("NOT = { has_variable = ywc_dmg_compensation_paid }", self.effects)

    def test_country_helpers_are_idempotent_and_counted_once(self):
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 1_000}})
        world.run("ywc_dmg_open_common_subjects_once", tag="DMG")
        world.run("ywc_dmg_open_common_subjects_once", tag="DMG")
        self.assertEqual(world.countries["DMG"]["ywc_dmg_arc_open"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_v03_active_arc_count"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_v03_visible_task_count"], 1)
        self.assertNotIn("ywc_dmg_outcome_common_qualification", world.countries["DMG"])

    def test_repeated_payments_are_idempotent_and_keep_income_proportional(self):
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 1_000}})
        world.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        first = world.treasury["DMG"]
        self.assertAlmostEqual(first, -1_000, places=5)
        self.assertEqual(first, -1_000)
        world.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        self.assertEqual(world.treasury["DMG"], first)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_public_registry_paid"], 1)
        poor = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 104, "gold_reserves": 100}})
        poor.run("ywc_dmg_snapshot_costs_once", tag="DMG")
        self.assertEqual(poor.countries["DMG"]["ywc_dmg_public_registry_cost"], 100)

    def test_payment_effect_needs_exact_cash_and_does_not_mark_unpaid_cost_as_paid(self):
        exact = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 1_000}})
        exact.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        self.assertEqual(exact.countries["DMG"]["ywc_dmg_public_registry_cost"], 1_000)
        self.assertEqual(exact.treasury["DMG"], -1_000)
        self.assertEqual(exact.countries["DMG"]["ywc_dmg_public_registry_paid"], 1)
        short = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 999}})
        short.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        self.assertNotIn("ywc_dmg_public_registry_paid", short.countries["DMG"])
        self.assertEqual(short.treasury["DMG"], 0)
        defaulted = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 2_000, "in_default": True}})
        defaulted.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        self.assertNotIn("ywc_dmg_public_registry_paid", defaulted.countries["DMG"])

    def test_unfunded_opening_choice_cannot_select_a_paid_route(self):
        opening = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1000")
        option = next(o for o in opening["options"] if o["key"] == "common_qualification")
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 0}})
        world.execute(parse(option["effect"][1:-1]), "DMG")
        state = world.countries["DMG"]
        self.assertNotIn("ywc_dmg_public_registry_paid", state)
        self.assertNotIn("ywc_dmg_route", state)
        self.assertNotEqual(state.get("ywc_dmg_pending_event"), 1001)
        self.assertTrue(any(o["key"] in ("defer", "withdraw") for o in opening["options"]))

    def test_common_close_cannot_award_success_without_registry_payment(self):
        effects = self.effects + "\nywc_v03_release_arc_dmg_v03_dmg_common_subjects = { set_variable = { name = released value = 1 } }\n"
        class ReadyWithoutPaidRegistry(PulseWorld):
            def condition(self, node, tag):
                if node[0] == "ywc_dmg_v03_common_route_ready":
                    return True
                return super().condition(node, tag)
        world = ReadyWithoutPaidRegistry(effects, {"DMG": {
            "ywc_dmg_route": 1,
            "ywc_dmg_service_qualification": 2,
            "ywc_dmg_appointment_actual": 1,
        }})
        world.run("ywc_dmg_close_as_common", tag="DMG")
        self.assertNotEqual(world.countries["DMG"].get("ywc_dmg_outcome_common_qualification"), 1)

    def test_je2_blocked_route_prompts_after_twelve_months_without_maturity_and_keeps_exit(self):
        from test_v03_dmg_notice_exits import blocked_world
        from test_v03_shu_provincial_contract import choose, option_legal
        world, arc = blocked_world()
        event = world.deliver(arc, "ywc_dmg.1009")
        state = world.countries[world.tag]
        self.assertNotIn("ywc_dmg_review_matured", state)
        self.assertNotIn("ywc_dmg_review_blocked_12_notice", state)
        self.assertEqual(state["ywc_dmg_review_notice_response_context"], 12)
        for key in ("continue_repair", "limited_settlement", "withdraw_breach"):
            self.assertTrue(option_legal(world, event, key), key)
        choose(world, arc, event, "limited_settlement")
        self.assertEqual(state["ywc_dmg_outcome_limited_qualification"], 1)
        self.assertNotIn("ywc_dmg_outcome_common_qualification", state)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def test_je2_lost_territory_keeps_immediate_breach_exit_and_releases_slot(self):
        from test_v03_dmg_school_languages import new_world, play
        from test_v03_dmg_school_cross_era import COMMON_ESTABLISHED
        from test_v03_shu_provincial_contract import choose, option_legal
        world = new_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_dmg_common_subjects")
        for number, key in COMMON_ESTABLISHED[:-1]:
            play(world, arc, number, key)
        state = world.countries[world.tag]
        state["states"][0]["owner"] = "PHI"
        event = world.deliver(arc, "ywc_dmg.1009")
        self.assertTrue(option_legal(world, event, "withdraw_breach"))
        choose(world, arc, event, "withdraw_breach")
        self.assertEqual(state["ywc_dmg_outcome_withdrawn_breach"], 1)
        self.assertNotIn("ywc_dmg_outcome_common_qualification", state)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        self.assertEqual(world.history[world.tag][arc["journals"][1]["id"]], "failed")

    def test_failed_compensation_and_local_fee_choices_do_not_advance(self):
        training = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1002")
        option = next(o for o in training["options"] if o["key"] == "pay_training")
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 0}})
        world.execute(parse(option["effect"][1:-1]), "DMG")
        self.assertNotIn("ywc_dmg_compensation_paid", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_service_qualification", world.countries["DMG"])
        self.assertNotEqual(world.countries["DMG"].get("ywc_dmg_pending_event"), 1003)

        local = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1003")
        for key in ("joint_hearing", "noble_guarantee", "royal_order"):
            option = next(o for o in local["options"] if o["key"] == key)
            world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000, "gold_reserves": 0}})
            world.execute(parse(option["effect"][1:-1]), "DMG")
            self.assertNotIn("ywc_dmg_appeal_mechanism", world.countries["DMG"], key)
            self.assertNotEqual(world.countries["DMG"].get("ywc_dmg_pending_event"), 1004, key)

    def test_outcomes_close_once_and_release_capacity_even_after_lost_state(self):
        effects = self.effects + "\nywc_v03_release_arc_dmg_v03_dmg_common_subjects = { set_variable = { name = ywc_v03_dmg_v03_dmg_common_subjects_settled value = 1 } }\n"
        world = PulseWorld(effects, {"DMG": {"ywc_dmg_route": 3, "ywc_dmg_compensation_paid": 1}})
        world.run("ywc_dmg_close_as_breach", tag="DMG")
        world.run("ywc_dmg_close_as_breach", tag="DMG")
        self.assertEqual(world.countries["DMG"]["ywc_dmg_outcome_withdrawn_breach"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_compensation_paid"], 1)
        self.assertEqual(sum(v for k,v in world.countries["DMG"].items() if k.startswith("ywc_dmg_outcome_")), 1)

if __name__ == "__main__":
    unittest.main()
