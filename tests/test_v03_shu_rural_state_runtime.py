"""Native state identity without substituting a country/runtime or business predicate."""
import copy
from datetime import date, datetime
from pathlib import Path
import unittest

from clausewitz_harness import parse
from shu_public_runtime import ShuPublicWorld
from shu_rural_state_runtime import StateScopeMixin, StateRef, ShuRuralStateWorld


class StateWorld(StateScopeMixin, ShuPublicWorld):
    pass


CAPTURE = """save_scope_as = ROOT
every_scope_state = {
    limit = { owner = ROOT NOT = { ROOT = { has_variable = literal_pilot } } }
    ROOT = { set_variable = { name = literal_pilot value = PREV } }
}"""
QUERY = """var:literal_pilot = { owner = ROOT this = scope:ROOT.var:literal_pilot
    any_scope_pop = { is_pop_type = farmers is_employed = yes
        workplace ?= { is_building_type = building_rice_farm occupancy >= .5
                         building_has_goods_shortage = no } } }"""


def province(owner="SHU"):
    farm = {"type": "building_rice_farm", "occupancy": .8, "shortage": False}
    return {"owner": owner, "region": "s:STATE_SICHUAN", "average_sol": 12,
            "buildings": [farm], "pops": [{"type": "farmers", "employed": True, "workplace": farm}]}


def world(cls=StateWorld, **kwargs):
    w = cls(**kwargs)
    w.countries = {"SHU": {"states": [province("CHI"), province(), province()], "igs": [],
                            "number": 7, "laws": [], "net_fixed_income": 0},
                   "CHI": {"states": [], "igs": [], "number": 99, "laws": [], "net_fixed_income": 5}}
    return w


def capture(w):
    w.execute(parse(CAPTURE), "SHU")
    return w.countries["SHU"]["literal_pilot"]


def check(w, text=QUERY):
    return w.conditions(parse(text), "SHU")


class ShuRuralStateIdentity(unittest.TestCase):
    def test_native_root_prev_capture_produces_a_typed_first_owned_state(self):
        w = world()
        try:
            reference = capture(w)
        except AssertionError as exc:
            self.fail(f"native ROOT/PREV state capture unavailable: {exc}")
        self.assertIsInstance(reference, StateRef)
        self.assertTrue(check(w))
        self.assertNotIn("literal_pilot", w.countries["CHI"])

    def test_capture_is_once_and_equal_region_or_enumeration_changes_cannot_reselect(self):
        w = world(); selected = w.countries["SHU"]["states"][1]
        reference = capture(w)
        w.countries["SHU"]["states"].insert(0, province())
        w.countries["SHU"]["states"].reverse()
        self.assertEqual(capture(w), reference)
        selected["pops"][0]["employed"] = False
        self.assertFalse(check(w), "healthy other owned state cannot replace the original")

    def test_live_ownership_loss_and_foreign_split_cannot_borrow_another_states_jobs(self):
        w = world(); selected = w.countries["SHU"]["states"][1]; reference = capture(w)
        selected["owner"] = "CHI"
        self.assertFalse(check(w))
        self.assertTrue(check(w, "exists = var:literal_pilot"))
        self.assertEqual(w.countries["SHU"]["literal_pilot"], reference)
        selected["owner"] = "SHU"
        self.assertTrue(check(w))

    def test_actual_object_moves_between_country_lists_without_changing_identity(self):
        w = world(); selected = w.countries["SHU"]["states"][1]; reference = capture(w)
        w.countries["SHU"]["states"].remove(selected)
        selected["owner"] = "CHI"; w.countries["CHI"]["states"].append(selected)
        self.assertFalse(check(w))
        self.assertTrue(check(w, "var:literal_pilot = { owner = c:CHI this = scope:ROOT.var:literal_pilot }"))
        self.assertEqual(w.countries["SHU"]["literal_pilot"], reference)

    def test_vanished_state_does_not_bind_to_equal_replacement_and_can_return_as_same_object(self):
        w = world(); selected = w.countries["SHU"]["states"][1]; reference = capture(w)
        w.countries["SHU"]["states"].remove(selected)
        w.countries["SHU"]["states"].insert(1, copy.deepcopy(selected))
        self.assertFalse(check(w, "exists = var:literal_pilot"))
        self.assertFalse(check(w))
        self.assertEqual(w.countries["SHU"]["literal_pilot"], reference)
        w.countries["SHU"]["states"].append(selected)
        self.assertTrue(check(w))

    def test_saved_state_scope_and_root_variable_comparison_use_actual_objects(self):
        w = world(); capture(w)
        w.execute(parse("""var:literal_pilot = { save_scope_as = original_object }
            set_variable = { name = second_ref value = scope:original_object }
        """), "SHU")
        self.assertTrue(check(w, "var:second_ref = var:literal_pilot"))
        self.assertTrue(check(w, "var:literal_pilot = { this = scope:ROOT.var:second_ref }"))
        with self.assertRaises(AssertionError):
            check(w, "var:literal_pilot >= 1")

    def test_missing_wrong_type_unknown_state_and_region_tokens_reject(self):
        for bad in (0, True, "s:STATE_SICHUAN", {}, StateRef(999999), StateRef(True), StateRef(1.0), StateRef("1")):
            with self.subTest(bad=bad):
                w = world(); w.countries["SHU"]["literal_pilot"] = bad
                with self.assertRaises(AssertionError): check(w)
        w = world()
        for expression in ("var:missing = { owner = ROOT }", "scope:missing = { owner = ROOT }",
                           "var:number = { owner = ROOT }", "this >= 0"):
            with self.subTest(expression=expression), self.assertRaises(AssertionError): check(w, expression)

    def test_numeric_variables_remain_strict_and_state_refs_are_not_numbers(self):
        w = world(); capture(w)
        w.execute(parse("set_variable = { name = copy_number value = ROOT.var:number }"), "SHU")
        self.assertEqual(w.countries["SHU"]["copy_number"], 7)
        self.assertTrue(check(w, "var:copy_number = 7"))
        w.execute(parse("save_scope_value_as = { name = numeric_callback value = var:number }"), "SHU")
        self.assertTrue(check(w, "var:number = scope:numeric_callback"))
        self.assertTrue(check(w, "exists = scope:numeric_callback"))
        self.assertTrue(check(w, "var:literal_pilot = { average_sol >= ROOT.var:number }"))
        w.countries["SHU"]["yearly_gross_income"] = 52000
        w.execute(parse("""set_variable = { name = copied_income value = yearly_gross_income }
            change_variable = { name = copied_income divide = 52 }
            change_variable = { name = copied_income add = ROOT.var:number }
            clamp_variable = { name = copied_income min = 100 max = 1000 }
        """), "SHU")
        self.assertEqual(w.countries["SHU"]["copied_income"], 1000)
        self.assertTrue(check(w, "var:missing_number = 0"), "ordinary script guard keeps the inherited absence semantics")
        for expression in ("var:missing_number = var:literal_pilot", "var:number = nan"):
            with self.subTest(expression=expression), self.assertRaises(AssertionError): check(w, expression)
        for effect in ("set_variable = { name = x value = var:missing_number }",
                       "change_variable = { name = literal_pilot add = 1 }",
                       "set_variable = { name = x value = nan }",
                       "change_variable = { name = number add = var:missing_number }",
                       "change_variable = { name = number add = nan }",
                       "set_variable = { name = x value = 1 days = nan }"):
            with self.subTest(effect=effect), self.assertRaises(AssertionError): w.execute(parse(effect), "SHU")

    def test_root_and_prev_are_restored_across_actual_foreign_country_scope(self):
        w = world(); capture(w)
        self.assertTrue(check(w, "c:CHI = { var:number = 99 ROOT = { var:number = 7 } }"))
        self.assertTrue(check(w, "var:literal_pilot = { ROOT = { var:literal_pilot = PREV } }"))
        with self.assertRaises(AssertionError):
            w.execute(parse("ROOT = { set_variable = { name = bad_state value = PREV } }"), "SHU")
        self.assertTrue(check(w))

    def test_queries_and_effect_exceptions_restore_stack_and_all_literal_scopes(self):
        w = world(); capture(w)
        names = ("state_scope", "pop_scope", "building_scope", "scope_ig", "good_scope", "_state_scope_stack")
        before = {name: getattr(w, name, None) for name in names}
        for expression, expected in ((QUERY, True), ("var:literal_pilot = { average_sol > 100 }", False)):
            self.assertEqual(check(w, expression), expected)
            for name,value in before.items(): self.assertIs(getattr(w, name, None), value, name)
        for expression in ("var:literal_pilot = { any_scope_pop = { unknown_rural_fact = yes } }",
                           "var:literal_pilot = { ROOT = { var:missing_object = var:literal_pilot } }"):
            with self.assertRaises(AssertionError): check(w, expression)
            for name,value in before.items(): self.assertIs(getattr(w, name, None), value, name)
        with self.assertRaises(AssertionError):
            w.execute(parse("var:literal_pilot = { ROOT = { unknown_rural_effect = yes } }"), "SHU")
        for name,value in before.items(): self.assertIs(getattr(w, name, None), value, name)
        w.countries["SHU"]["igs"] = [{"type": "ig_landowners", "approval": float("nan")}]
        with self.assertRaises(AssertionError):
            check(w, "var:literal_pilot = { ROOT = { any_interest_group = { is_interest_group_type = ig_landowners ig_approval >= 0 } } }")
        for name,value in before.items(): self.assertIs(getattr(w, name, None), value, name)

    def test_untyped_pop_building_and_ig_scopes_cannot_masquerade_as_prev_state(self):
        w = world(); capture(w)
        for expression in ("var:literal_pilot = { any_scope_pop = { this = scope:ROOT.var:literal_pilot } }",
                           "var:literal_pilot = { any_scope_building = { owner = ROOT } }"):
            with self.subTest(expression=expression), self.assertRaises(AssertionError): check(w, expression)

    def test_actual_rural_world_composition_keeps_sol_pm_and_price_literal(self):
        w = world(ShuRuralStateWorld); capture(w)
        selected = w.countries["SHU"]["states"][1]
        selected["pops"][0]["standard_of_living"] = 8
        selected["buildings"][0]["active_production_methods"] = ["pm_home_workshops_building_subsistence_rice_farm"]
        w.countries["SHU"]["market"] = {"grain": {"pricier": .25}}
        self.assertTrue(check(w, """var:literal_pilot = { owner = ROOT any_scope_pop = {
            is_employed = yes standard_of_living >= 5 workplace ?= {
                has_active_production_method = pm_home_workshops_building_subsistence_rice_farm } } }
            market_capital.market = { mg:grain = { market_goods_pricier <= .25 } }
        """))


class ShuRuralNumericDispatchCompatibility(unittest.TestCase):
    def test_absent_ordinary_numeric_guards_preserve_the_inherited_dispatch(self):
        reference = world(ShuPublicWorld)
        composed = world()
        for expression in ("var:unassigned = 0", "var:unassigned = 1", "var:unassigned != 1",
                           "var:unassigned ?= 0", "var:unassigned >= 0", "var:number = 7",
                           "var:unassigned = var:number"):
            with self.subTest(expression=expression):
                expected = check(reference, expression)
                try:
                    actual = check(composed, expression)
                except AssertionError as exc:
                    self.fail(f"ordinary numeric dispatch was intercepted as a required object: {expression}: {exc}")
                self.assertEqual(actual, expected)
                self.assertNotIn("unassigned", composed.countries["SHU"])
                self.assertEqual(composed._state_scope_stack, ())

    def test_actual_generated_prepare_and_reclaim_accept_absent_reservation(self):
        from test_v03_shu_rural_workshop import new_world
        w = new_world()
        state = w.countries["SHU"]
        self.assertEqual(set(w.countries), {"SHU", "CHI", "DMG", "KOR", "JHG", "LAN", "NMG", "MGL", "NQG", "TIB", "OIR"})
        self.assertNotIn("ywc_v03_shu_inline_reservation", state)
        w.run("ywc_v03_shu_inline_prepare", "SHU")
        # Reclaim is embedded in the generated prepare body, not a named effect.
        after_prepare = copy.deepcopy(state)
        w.run("ywc_v03_shu_inline_prepare", "SHU")
        self.assertEqual(state, after_prepare)
        self.assertNotIn("ywc_v03_shu_inline_reservation", state)
        self.assertNotIn("ywc_shu_workshop_last_event", state)
        self.assertEqual(w._state_scope_stack, ())

    def test_actual_initialization_and_first_native_rural_callback_need_no_seed(self):
        from test_v03_shu_rural_workshop import new_world, workshop_arc, deliver
        w = new_world()
        state = w.countries["SHU"]
        self.assertNotIn("ywc_v03_shu_inline_reservation", state)
        self.assertNotIn("ywc_shu_workshop_last_event", state)
        event = deliver(w, workshop_arc(w.cat), 1110)
        self.assertTrue(event)
        self.assertIsInstance(state["ywc_shu_workshop_pilot"], StateRef)
        self.assertIs(w._state_object(state["ywc_shu_workshop_pilot"]), state["states"][0])
        self.assertEqual(state["ywc_shu_workshop_last_event"], 1110)
        self.assertNotIn("ywc_v03_shu_inline_reservation", state)
        self.assertNotIn("ywc_shu_workshop_pending_event", state)
        self.assertNotIn("ywc_shu_workshop_admin_paid", state)
        self.assertNotIn("ywc_shu_workshop_survey_paid", state)
        self.assertEqual(w._state_scope_stack, ())

    def test_missing_current_world_facts_and_native_objects_remain_strict(self):
        for missing in ("sol", "pm", "grain"):
            with self.subTest(missing=missing):
                w = world(ShuRuralStateWorld); capture(w)
                selected = w.countries["SHU"]["states"][1]
                selected["pops"][0]["standard_of_living"] = 8
                selected["buildings"][0]["active_production_methods"] = ["pm_home_workshops_building_subsistence_rice_farm"]
                w.countries["SHU"]["market"] = {"grain": {"pricier": .25}}
                if missing == "sol":
                    del selected["pops"][0]["standard_of_living"]
                    query = "var:literal_pilot = { any_scope_pop = { standard_of_living >= 0 } }"
                elif missing == "pm":
                    del selected["buildings"][0]["active_production_methods"]
                    query = "var:literal_pilot = { any_scope_building = { has_active_production_method = pm_home_workshops_building_subsistence_rice_farm } }"
                else:
                    del w.countries["SHU"]["market"]["grain"]
                    query = "market_capital.market = { mg:grain = { market_goods_pricier <= 0 } }"
                with self.assertRaises(AssertionError): check(w, query)
                with self.assertRaises(AssertionError): check(w, "var:missing_state = { owner = ROOT }")
                with self.assertRaises(AssertionError): check(w, "var:missing_state = var:literal_pilot")
                self.assertEqual(w._state_scope_stack, ())


class ShuRuralCalendarScriptValue(unittest.TestCase):
    def test_actual_global_calendar_value_is_native_and_needs_no_nmg_country(self):
        w = world(ShuRuralStateWorld)
        self.assertNotIn("NMG", w.countries)
        try:
            w.execute(parse("set_variable = { name = literal_month_token value = ywc_nmg_current_calendar_month }"), "SHU")
        except AssertionError as exc:
            self.fail(f"actual global calendar script value unavailable: {exc}")
        self.assertEqual(w.countries["SHU"]["literal_month_token"], 1836 * 12)

    def test_days_one_three_and_thirteen_share_one_actual_calendar_token(self):
        w = world(ShuRuralStateWorld)
        for index, advance in enumerate((0, 2, 10)):
            w.advance_days(advance)
            w.execute(parse(f"set_variable = {{ name = literal_month_{index} value = ywc_nmg_current_calendar_month }}"), "SHU")
        self.assertEqual(w.date, date(1836, 1, 13))
        self.assertEqual(w.day, 12)
        self.assertEqual([w.countries["SHU"][f"literal_month_{i}"] for i in range(3)], [1836 * 12] * 3)

    def test_month_and_year_boundaries_increment_token_once(self):
        for start, end, expected in ((date(1836, 1, 31), date(1836, 2, 1), 1836 * 12 + 1),
                                     (date(1836, 12, 31), date(1837, 1, 1), 1837 * 12)):
            with self.subTest(start=start):
                w = world(ShuRuralStateWorld, start_date=start)
                w.execute(parse("set_variable = { name = before_month value = ywc_nmg_current_calendar_month }"), "SHU")
                w.advance_days(1)
                w.execute(parse("set_variable = { name = after_month value = ywc_nmg_current_calendar_month }"), "SHU")
                self.assertEqual(w.date, end)
                self.assertEqual(w.day, 1)
                self.assertEqual(w.countries["SHU"]["after_month"], expected)
                self.assertEqual(w.countries["SHU"]["after_month"] - w.countries["SHU"]["before_month"], 1)

    def test_gregorian_leap_and_month_advancement_keep_real_day_expiry(self):
        for year, day_count in ((1836, 29), (1837, 28)):
            with self.subTest(year=year):
                w = world(ShuRuralStateWorld, start_date=date(year, 1, 31))
                w.execute(parse("set_variable = { name = native_day_timer value = 1 days = 28 }"), "SHU")
                w.advance_months(1)
                self.assertEqual(w.date, date(year, 2, day_count))
                self.assertEqual(w.day, day_count)
                self.assertNotIn("native_day_timer", w.countries["SHU"])
                w.execute(parse("set_variable = { name = february value = ywc_nmg_current_calendar_month }"), "SHU")
                self.assertEqual(w.countries["SHU"]["february"], year * 12 + 1)
                w.advance_days(1)
                self.assertEqual(w.date, date(year, 3, 1))
        w = world(ShuRuralStateWorld, start_date=date(1836, 1, 31))
        w.advance_months(2)
        self.assertEqual(w.date, date(1836, 3, 31))
        self.assertEqual(w.day, 60)
        self.assertEqual(w.elapsed_months, 0, "existing SHU callers still own the elapsed-month diagnostic counter")

    def test_actual_parsed_definition_is_read_only_and_unsupported_shapes_reject(self):
        path = Path(__file__).resolve().parents[1] / "yongchang_world/common/script_values/ywc_v03_nmg_values.txt"
        original = path.read_bytes()
        w = world(ShuRuralStateWorld)
        self.assertEqual(w._calendar_value_body, [("value", "=", "year"), ("multiply", "=", "12"), ("add", "=", "month")])
        bodies = (
            [], [("value", "=", "year")],
            [("value", "=", "year"), ("divide", "=", "12"), ("add", "=", "month")],
            [("value", "=", "year"), ("multiply", ">", "12"), ("add", "=", "month")],
            [("value", "=", "year"), ("multiply", "=", "1e999"), ("add", "=", "month")],
            [("value", "=", "year"), ("multiply", "=", "12"), ("add", "=", "unknown_calendar_fact")],
            [("value", "=", "year"), ("multiply", "=", []), ("add", "=", "month")],
        )
        for body in bodies:
            with self.subTest(body=body):
                w._calendar_value_body = body
                with self.assertRaises(AssertionError):
                    w.execute(parse("set_variable = { name = invalid_month value = ywc_nmg_current_calendar_month }"), "SHU")
                self.assertNotIn("invalid_month", w.countries["SHU"])
                self.assertEqual(w._state_scope_stack, ())
        self.assertEqual(path.read_bytes(), original)

    def test_calendar_value_keeps_native_root_prev_numeric_and_exception_scope_restoration(self):
        w = world(ShuRuralStateWorld); capture(w)
        names = ("state_scope", "pop_scope", "building_scope", "scope_ig", "good_scope", "_state_scope_stack")
        before = {name: getattr(w, name, None) for name in names}
        w.execute(parse("var:literal_pilot = { ROOT = { set_variable = { name = owned_month value = ywc_nmg_current_calendar_month } } }"), "SHU")
        self.assertEqual(w.countries["SHU"]["owned_month"], 1836 * 12)
        self.assertTrue(check(w, "var:owned_month = ywc_nmg_current_calendar_month"))
        for token in ("ywc_missing_current_calendar_month", "unknown_script_value", "year"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                w.execute(parse(f"var:literal_pilot = {{ ROOT = {{ set_variable = {{ name = unsupported_month value = {token} }} }} }}"), "SHU")
            for name, value in before.items(): self.assertIs(getattr(w, name, None), value, name)
        self.assertTrue(check(w))

    def test_malformed_date_or_elapsed_arguments_reject_without_advancing(self):
        for start in (True, "1836-01-01", None, datetime(1836, 1, 1)):
            with self.subTest(start=start), self.assertRaises(AssertionError):
                ShuRuralStateWorld(start_date=start)
        w = world(ShuRuralStateWorld)
        for invalid in (True, -1, 1.5, "1", None):
            for method in (w.advance_days, w.advance_months):
                with self.subTest(method=method.__name__, invalid=invalid), self.assertRaises(AssertionError): method(invalid)
                self.assertEqual(w.date, date(1836, 1, 1))
                self.assertEqual(w.day, 0)
        w.date = None
        with self.assertRaises(AssertionError):
            w.execute(parse("set_variable = { name = invalid_date value = ywc_nmg_current_calendar_month }"), "SHU")
        self.assertNotIn("invalid_date", w.countries["SHU"])
        self.assertEqual(w._state_scope_stack, ())

    def test_actual_full_path_uses_existing_month_caller_once_per_gregorian_month(self):
        from test_v03_shu_rural_workshop import new_world, ready_for_review, month, finish_review
        w = new_world()
        arc = ready_for_review(w)
        state = w.countries["SHU"]
        w.execute(parse("set_variable = { name = literal_calendar_start value = ywc_nmg_current_calendar_month }"), "SHU")
        start = state["literal_calendar_start"]
        for offset in range(1, 7):
            before = w.elapsed_months
            month(w, arc)
            self.assertEqual(w.elapsed_months, before + 1)
            w.execute(parse("set_variable = { name = literal_calendar_now value = ywc_nmg_current_calendar_month }"), "SHU")
            self.assertEqual(state["literal_calendar_now"] - start, offset)
            self.assertEqual(w.day, (w.date - w._epoch).days)
        finish_review(w, arc)
        self.assertEqual(state["ywc_shu_workshop_outcome"], 1)
        self.assertEqual(state["ywc_shu_workshop_admin_paid"], 1)
        self.assertEqual(state["ywc_shu_workshop_survey_paid"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
