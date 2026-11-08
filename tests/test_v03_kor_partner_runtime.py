"""Offline contracts for missing interpreter primitives, not KOR feature acceptance.

Literal examples compose documented primitives; they are not vanilla excerpts.
Pinned generated-doc mirror (third party), 1.13.11 effects.log:
https://github.com/Victoria-3-Modding-Co-op/Modding-Digests/blob/
62fc149c3b21b9f97713d324df76c55a1b2c085d/1.13.11/docs/effects.log
Lines 38483-38501 (persistent saved scopes/values), 38933-38941 (variables),
39075-39080 (current-recipient dispatch/delay). Installed-source idioms:
obligation_events.txt 34-63; heavenly_kingdom_events.txt 475-480,516-523;
00_victoria_ip4_scripted_effects.txt 610-624 (object comparison).
No external documents, private evidence or installed game files are read.
"""
import copy
from dataclasses import replace
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts
from clausewitz_harness import parse


# One compact source guard/transfer composition, not a prospective feature state
# machine. No signed service, installments, domestic continuation or game AI.
MATCH = """
    exists = scope:requester exists = scope:partner
    scope:partner ?= this
    scope:requester = {
        has_variable = timer has_variable = partner has_variable = generation
        var:partner ?= root
        var:generation = scope:generation
        NOT = { has_variable = settled }
    }
"""
GATE = """
    is_country_alive = yes
    scope:requester = { is_country_alive = yes is_subject = no ywc_kor_v03_finance_safe = yes }
    relations:scope:requester >= 0
    ywc_kor_v03_has_staffed_supplied_barracks = yes
"""
EVENTS = """
test.partner = {
    trigger = { exists = scope:requester scope:partner ?= this }
    immediate = {
        set_variable = { name = observed_root value = root }
        set_variable = { name = observed_generation value = scope:generation }
        set_variable = { name = observed_requester value = scope:requester }
    }
    option = { name = test.partner.accept trigger = { MATCH GATE }
        if = { limit = { MATCH GATE scope:amount > 0
            scope:requester = { gold_reserves >= scope:amount } }
            set_variable = { name = answer value = scope:generation }
            scope:requester = {
                set_variable = { name = settled value = scope:generation }
                add_treasury = { value = scope:amount multiply = -1 }
                scope:partner = { add_treasury = { value = scope:amount } }
            }
        }
    }
    option = { name = test.partner.refuse trigger = { MATCH }
        if = { limit = { MATCH }
            scope:requester = { set_variable = { name = refused value = scope:generation } }
        }
    }
}
""".replace("MATCH", MATCH).replace("GATE", GATE)


def world():
    countries = {tag: copy.deepcopy(facts()) for tag in ("KOR", "SHU", "JHG")}
    for tag, cash in (("KOR", 100), ("SHU", 11), ("JHG", 29)):
        countries[tag]["gold_reserves"] = cash
        countries[tag]["relations"] = {"KOR": 10, "SHU": -9, "JHG": 20}
    return PartnerWorld(countries, EVENTS)


def offer(w, target="SHU", generation=1, price=12, days=0, timer=30):
    delay = f"days = {days}" if days else ""
    w.run_script(f"""
        set_variable = {{ name = generation value = {generation} }}
        set_variable = {{ name = quote value = {price} }}
        set_variable = {{ name = timer days = {timer} }}
        save_scope_as = requester
        save_scope_value_as = {{ name = generation value = var:generation }}
        save_scope_value_as = {{ name = amount value = var:quote }}
        c:{target} = {{
            save_scope_as = partner
            scope:requester = {{ set_variable = {{ name = partner value = prev }} }}
            trigger_event = {{ id = test.partner {delay} }}
        }}
    """)
    return w.jobs[-1]


class PartnerRuntimeTests(unittest.TestCase):
    def test_documented_and_legacy_ownership_in_foreign_recipient_event(self):
        for spelling in ("owner", "is_owned_by"):
            for recipient in ("SHU", "JHG"):
                for owner in ("KOR", recipient, None, "absent"):
                    with self.subTest(spelling=spelling, recipient=recipient, owner=owner):
                        w = world()
                        state = w.countries["KOR"]["states"][0]
                        state["owned"] = True
                        if owner != "absent":
                            state["owner"] = owner
                        w.event_defs["test.typed_owner"] = parse("""
                            trigger = { always = yes }
                            immediate = {
                                scope:requester = {
                                    if = { limit = { any_scope_state = { OWNER = ROOT } }
                                        set_variable = { name = event_root_owned value = yes } }
                                    if = { limit = { any_scope_state = { OWNER = scope:requester } }
                                        set_variable = { name = requester_owned value = yes } }
                                }
                            }
                        """.replace("OWNER", spelling))
                        job = replace(offer(w, recipient), event_id="test.typed_owner")
                        self.assertTrue(w.display_job(job))
                        self.assertEqual(w.countries["KOR"].get("event_root_owned", False), owner == recipient)
                        self.assertEqual(w.countries["KOR"].get("requester_owned", False), owner in ("KOR", "absent"))
                        self.assertIsNone(w.state_scope)
                        self.assertIsNone(w.building_scope)

    def test_wrapped_option_effects_preserve_recipient_and_stale_guards(self):
        for target in ("SHU", "JHG"):
            with self.subTest(target=target):
                w = world()
                option = next(body for key, _, body in w.event_defs["test.partner"]
                              if key == "option" and body[0][2] == "test.partner.accept")
                option[:] = parse("""
                    name = test.partner.accept
                    custom_tooltip = test.localization.only
                    custom_tooltip = {
                        text = test.wrapper.tt
                        if = { limit = { MATCH scope:amount > 0
                            scope:requester = { gold_reserves >= scope:amount } }
                            set_variable = { name = wrapped_root value = root }
                            scope:requester = {
                                set_variable = { name = settled value = scope:generation }
                                add_treasury = { value = scope:amount multiply = -1 }
                                scope:partner = { add_treasury = { value = scope:amount } }
                            }
                        }
                    }
                """.replace("MATCH", MATCH))
                old = offer(w, target, generation=1, price=7)
                self.assertTrue(w.display_job(old))
                current = offer(w, target, generation=2, price=13)
                w.choose_job(old, "accept")
                self.assertEqual(w.treasury["KOR"], 0)
                self.assertNotIn("wrapped_root", w.countries[target])
                self.assertTrue(w.display_job(current))
                w.choose_job(current, "accept")
                self.assertEqual(w.countries[target].get("wrapped_root"), w.country_ref(target))
                self.assertEqual(w.treasury["KOR"], -13)
                self.assertEqual(w.treasury[target], 13)
                third = "JHG" if target == "SHU" else "SHU"
                self.assertEqual(w.treasury[third], 0)
                w.choose_job(current, "accept")
                self.assertEqual(w.treasury[target], 13)
        w = world()
        w.event_defs["test.partner"].extend(parse("""
            option = { name = test.partner.unknown
                custom_tooltip = { text = test.wrapper.tt unknown_wrapped_instruction = yes }
            }
        """))
        job = offer(w)
        self.assertTrue(w.display_job(job))
        with self.assertRaisesRegex(AssertionError, "unsupported.*unknown_wrapped_instruction"):
            w.choose_job(job, "unknown")

    def test_inherited_delivery_and_direct_advancement_count_each_month_once(self):
        w = world()
        w.run_script("set_variable = { name = wait value = yes months = 1 }")
        w.event_defs["test.clock"] = parse("trigger = { always = yes }")
        observations = []

        # A small pulse seam isolates the inherited delivery loop: a genuine
        # timed variable expires before the next pulse authors the source event.
        def pulse(_arc):
            observations.append((w.day, w.elapsed_months))
            if not w.check_script("has_variable = wait"):
                w.run_script("trigger_event = { id = test.clock }")

        w.pulse = pulse
        w.deliver({}, "test.clock")
        self.assertEqual(observations, [(0, 0), (30, 1)])
        self.assertEqual((w.day, w.elapsed_months), (30, 1))
        w.advance_months(2)
        self.assertEqual((w.day, w.elapsed_months), (90, 3))
        # Ensure ownership is restored even if inherited delivery raises.
        w.events.clear()
        w.run_script("set_variable = { name = wait value = yes months = 1 }")
        with self.assertRaisesRegex(AssertionError, "unexpected_event"):
            w.deliver({}, "test.different")
        self.assertEqual((w.day, w.elapsed_months), (120, 4))
        w.advance_months()
        self.assertEqual((w.day, w.elapsed_months), (150, 5))

    def test_event_root_ownership_and_country_prev_boundary(self):
        w = world()
        # A foreign recipient re-enters requester: ROOT remains SHU, not KOR.
        w.event_defs["test.ownership"] = parse("""
            trigger = { always = yes }
            immediate = {
                scope:requester = {
                    if = { limit = { any_scope_state = { is_owned_by = ROOT } }
                        set_variable = { name = wrong_owner value = yes }
                    }
                    if = { limit = { any_scope_state = { is_owned_by = scope:requester } }
                        set_variable = { name = correct_owner value = prev }
                    }
                }
                save_scope_as = responder
                save_scope_value_as = { name = answer_number value = scope:generation }
            }
            option = { name = test.ownership.read
                scope:requester = {
                    set_variable = { name = responder value = scope:responder }
                    set_variable = { name = copied_answer value = scope:answer_number }
                }
            }
        """)
        job = offer(w)
        ownership_job = replace(job, event_id="test.ownership")
        self.assertTrue(w.display_job(ownership_job))
        self.assertNotIn("wrong_owner", w.countries["KOR"])
        self.assertEqual(w.countries["KOR"]["correct_owner"], w.country_ref("SHU"))
        w.choose_job(ownership_job, "read")
        self.assertEqual(w.countries["KOR"]["responder"], w.country_ref("SHU"))
        self.assertEqual(w.countries["KOR"]["copied_answer"], 1)
        for source in (
            "any_scope_state = { prev.var:generation = 1 }",
            "any_scope_state = { any_scope_building = { prev.var:generation = 1 } }",
        ):
            with self.subTest(unsupported_scope=source), self.assertRaisesRegex(AssertionError, "unsupported.*PREV"):
                w.check_script(source)
        self.assertTrue(w.check_script("ywc_kor_v03_has_staffed_supplied_barracks = yes"))

    def test_dispatch_uses_selected_country_and_saved_values(self):
        for target in ("SHU", "JHG"):
            with self.subTest(target=target):
                w = world()
                job = offer(w, target, generation=7, price=13)
                self.assertEqual(job.recipient, w.country_ref(target))
                self.assertFalse(job.explicit_delay)
                self.assertEqual(job.due_day, 0)
                self.assertTrue(w.display_job(job))
                state = w.countries[target]
                self.assertEqual(state["observed_root"], w.country_ref(target))
                self.assertEqual(state["observed_requester"], w.country_ref("KOR"))
                self.assertEqual(state["observed_generation"], 7)
                self.assertNotIn("observed_root", w.countries["KOR"])
                self.assertTrue(w.job_options(job)["accept"])
                w.choose_job(job, "accept")
                w.choose_job(job, "accept")
                self.assertEqual(w.treasury, {"KOR": -13, target: 13,
                                              "JHG" if target == "SHU" else "SHU": 0})

    def test_three_requests_isolate_delayed_and_displayed_context(self):
        w = world()
        a = offer(w, "SHU", 1, 9, days=2)
        w.advance_days(2)
        self.assertTrue(w.display_job(a))
        b = offer(w, "JHG", 2, 17, days=4)
        c = offer(w, "SHU", 3, 23)
        self.assertEqual(dict(a.saved)["generation"], 1)
        self.assertEqual(dict(b.saved)["amount"], 17)
        self.assertEqual(dict(c.saved)["generation"], 3)
        w.run_script("set_variable = { name = quote value = 999 }")
        for key in ("accept", "refuse"):
            with self.subTest(old_effect=key):
                w.choose_job(a, key)
                self.assertNotIn("settled", w.countries["KOR"])
                self.assertNotIn("refused", w.countries["KOR"])
        w.advance_days(4)
        self.assertTrue(w.display_job(b))
        self.assertEqual(w.countries["JHG"]["observed_generation"], 2)
        w.choose_job(b, "accept")
        self.assertEqual(sum(w.treasury.values()), 0)
        self.assertEqual(w.treasury["KOR"], 0)
        self.assertTrue(w.display_job(c))
        w.choose_job(c, "accept")
        self.assertEqual(w.treasury, {"KOR": -23, "SHU": 23, "JHG": 0})
        self.assertEqual(w.countries["SHU"]["answer"], 3)

    def test_delayed_older_display_after_new_request_retains_snapshot(self):
        w = world()
        old = offer(w, "SHU", 1, 4, days=5)
        self.assertTrue(old.explicit_delay)
        self.assertEqual(old.due_day, 5)
        new = offer(w, "SHU", 2, 8)
        self.assertFalse(w.display_job(old))
        self.assertTrue(w.display_job(new))
        w.advance_days(5)
        self.assertTrue(w.display_job(old))
        self.assertEqual(w.countries["SHU"]["observed_generation"], 1)
        w.choose_job(old, "refuse")
        self.assertNotIn("refused", w.countries["KOR"])
        w.choose_job(new, "refuse")
        self.assertEqual(w.countries["KOR"]["refused"], 2)

    def test_expiration_clock_boundary_and_repeated_months(self):
        w = world()
        job = offer(w, days=30, timer=30)
        self.assertFalse(w.display_job(job))
        w.advance_days(29)
        self.assertFalse(w.display_job(job))
        self.assertIn("timer", w.countries["KOR"])
        w.advance_days(1)
        self.assertNotIn("timer", w.countries["KOR"])
        self.assertTrue(w.display_job(job))
        w.choose_job(job, "accept")
        self.assertEqual(w.treasury["KOR"], 0)
        w.run_script("set_variable = { name = monthly value = yes months = 2 }")
        for generation in (2, 3):
            with self.subTest(month=generation):
                offer(w, generation=generation, days=30, timer=30)
                w.advance_months()
                self.assertFalse(w.check_script("has_variable = timer"))
                self.assertTrue(w.display_job(w.jobs[-1]))
                w.choose_job(w.jobs[-1], "accept")
                self.assertEqual(w.treasury["KOR"], 0)
        self.assertFalse(w.check_script("has_variable = monthly"))

    def test_country_identity_lifecycle_and_optional_absence(self):
        w = world()
        job = offer(w)
        old = w.country_ref("SHU")
        w.remove_country("SHU")
        self.assertFalse(w.check_script("exists = c:SHU"))
        self.assertFalse(w.display_job(job))
        w.add_country("SHU", facts())
        self.assertNotEqual(old, w.country_ref("SHU"))
        self.assertFalse(w.check_script("exists = var:partner"))
        self.assertFalse(w.check_script("var:partner ?= c:SHU"))
        self.assertFalse(w.display_job(job))
        w.run_script("var:partner ?= { set_variable = { name = revived value = yes } }")
        w.run_script("scope:absent ?= { add_treasury = 100 }")
        self.assertNotIn("revived", w.countries["SHU"])
        self.assertEqual(w.treasury["KOR"], 0)
        self.assertFalse(w.check_script("exists = scope:absent"))
        w.countries["JHG"]["is_country_alive"] = False
        self.assertFalse(w.check_script("c:JHG = { is_country_alive = yes }"))
        self.assertTrue(w.check_script("c:KOR ?= this"))
        self.assertTrue(w.check_script("is_country_alive = yes"))
        for removed in ("KOR", "SHU"):
            with self.subTest(removed_after_display=removed):
                w = world()
                job = offer(w)
                self.assertTrue(w.display_job(job))
                w.remove_country(removed)
                w.add_country(removed, facts())
                w.choose_job(job, "accept")
                self.assertEqual(sum(w.treasury.values()), 0)
                self.assertNotIn("settled", w.countries["KOR"])

    def test_wrong_recipient_or_missing_context_never_repairs_snapshot(self):
        for missing in ("partner", "requester", "generation", "amount", "wrong_recipient"):
            with self.subTest(context=missing):
                w = world()
                original = offer(w)
                changed = (replace(original, recipient=w.country_ref("JHG"))
                           if missing == "wrong_recipient" else
                           replace(original, saved=tuple((k, v) for k, v in original.saved if k != missing)))
                if missing == "generation":
                    with self.assertRaisesRegex(AssertionError, "undefined"):
                        w.display_job(changed)
                    self.assertEqual(w.treasury["KOR"], 0)
                    continue
                displayed = w.display_job(changed)
                if missing in ("partner", "requester", "wrong_recipient"):
                    self.assertFalse(displayed)
                else:
                    # Undefined saved values raise explicitly, never use current state.
                    # generation is read in immediate, amount only in effect guard.
                    if displayed:
                        with self.assertRaisesRegex(AssertionError, "undefined"):
                            w.choose_job(changed, "accept")
                self.assertEqual(w.treasury["KOR"], 0)

    def test_real_country_facts_gate(self):
        for defect in ("subject", "hostile", "unstaffed", "shortage", "default", "dead", "dead_flag"):
            with self.subTest(defect=defect):
                w = world()
                job = offer(w)
                if defect == "subject":
                    w.countries["KOR"]["is_subject"] = True
                elif defect == "hostile":
                    w.countries["SHU"]["relations"]["KOR"] = -1
                elif defect == "default":
                    w.countries["KOR"]["in_default"] = True
                elif defect == "dead":
                    w.remove_country("SHU")
                elif defect == "dead_flag":
                    w.countries["KOR"]["is_country_alive"] = False
                else:
                    barrack = w.countries["SHU"]["states"][0]["buildings"][1]
                    barrack["occupancy" if defect == "unstaffed" else "shortage"] = 0 if defect == "unstaffed" else True
                if w.display_job(job):
                    self.assertFalse(w.job_options(job)["accept"])
                    w.choose_job(job, "accept")
                self.assertEqual(w.treasury["KOR"], 0)
        w = world()
        self.assertTrue(w.check_script("ywc_kor_v03_finance_safe = yes ywc_kor_v03_has_translation_employer = yes"))
        # relations:root uses the true event ROOT in nested country context.
        w.run_script("c:SHU = { if = { limit = { relations:root >= 0 } set_variable = { name = related value = yes } } }")
        self.assertTrue(w.countries["SHU"]["related"])

    def test_saved_quote_finances_and_nested_reads(self):
        for amount in (0, 101, 12):
            with self.subTest(amount=amount):
                w = world()
                job = offer(w, "JHG", price=amount)
                w.run_script("set_variable = { name = quote value = 999 }")
                self.assertTrue(w.display_job(job))
                w.choose_job(job, "accept")
                paid = 12 if amount == 12 else 0
                self.assertEqual(w.treasury, {"KOR": -paid, "SHU": 0, "JHG": paid})
        w = world()
        w.run_script("""
            set_variable = { name = number value = 6 }
            save_scope_as = requester
            save_scope_value_as = { name = n value = var:number }
            c:SHU = {
                set_variable = { name = x value = root.var:number }
                set_variable = { name = y value = prev.var:number }
                set_variable = { name = z value = scope:requester.var:number }
                set_variable = { name = country value = scope:requester }
                set_variable = { name = via_object value = var:country.var:number }
                set_variable = { name = direct value = c:KOR.var:number }
                change_variable = { name = x add = scope:n }
                change_variable = { name = x multiply = 2 }
                change_variable = { name = x divide = 3 }
                clamp_variable = { name = x min = 0 max = 7 }
                add_treasury = { value = prev.var:number multiply = -1 }
                c:JHG = { add_treasury = { value = prev.var:y } }
            }
        """)
        self.assertTrue(w.check_script("c:SHU = { var:x = 7 var:y = c:KOR.var:number var:z >= 6 var:via_object = 6 var:direct <= 6 }"))
        self.assertEqual(w.treasury, {"KOR": 0, "SHU": -6, "JHG": 6})

    def test_typed_values_and_unsupported_source_fail_explicitly(self):
        w = world()
        w.run_script("set_variable = { name = country value = c:SHU } set_variable = { name = flag value = yes }")
        self.assertTrue(w.check_script("var:country ?= c:SHU var:flag = yes"))
        w.event_defs["test.values"] = parse("""
            trigger = { always = yes }
            immediate = { set_variable = { name = bool_snapshot value = scope:flag } }
        """)
        w.run_script("""
            save_scope_value_as = { name = flag value = var:flag }
            set_variable = { name = flag value = no }
            c:SHU = { trigger_event = { id = test.values days = 0 } }
        """)
        bool_job = w.jobs[-1]
        self.assertTrue(bool_job.explicit_delay)
        self.assertTrue(w.display_job(bool_job))
        self.assertIs(w.countries["SHU"]["bool_snapshot"], True)
        self.assertIs(w.countries["KOR"]["flag"], False)
        # Restore the local bool for the wrong-type comparison below.
        w.run_script("set_variable = { name = flag value = yes }")
        bad_effects = (
            "set_variable = { name = bogus value = unknown_flag }",
            "set_variable = { name = bogus value = var:states }",
            "set_variable = { name = missing value = var:missing }",
            "set_variable = { name = missing value = c:ABS }",
            "save_scope_value_as = { name = object value = c:SHU }",
            "change_variable = { name = country add = 1 }",
            "change_variable = { name = country divide = 0 }",
            "set_variable = { name = bad value = yes typo = 1 }",
            "trigger_event = { id = test.partner hours = 1 }",
            "save_temporary_scope_value_as = { name = no value = 1 }",
            "unknown_instruction = yes",
        )
        for source in bad_effects:
            with self.subTest(effect=source), self.assertRaisesRegex(AssertionError, "unsupported|undefined|numeric|country"):
                w.run_script(source)
        for source in ("var:country = 1", "var:flag = 1", "var:country > c:SHU", "unknown_predicate = yes", "var:missing = 0", "is_subject = typo", "always = typo"):
            with self.subTest(predicate=source), self.assertRaisesRegex(AssertionError, "unsupported|undefined|typed|numeric"):
                w.check_script(source)


if __name__ == "__main__":
    unittest.main()
