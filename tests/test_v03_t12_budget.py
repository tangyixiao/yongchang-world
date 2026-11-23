"""Exercise the generated budget options with local state and army facts."""
from pathlib import Path
import unittest

from clausewitz_harness import PulseWorld, parse


MOD = Path(__file__).resolve().parents[1] / "yongchang_world"


def script(path):
    return (MOD / path).read_text(encoding="utf-8-sig")


def fields(nodes):
    return {key: value for key, _, value in nodes}


EVENTS = fields(parse(script("events/ywc_v03_theme_t12_events.txt")))
TRIGGERS = fields(parse(script("common/scripted_triggers/ywc_v03_t12_triggers.txt")))
MODIFIERS = fields(parse(script("common/static_modifiers/ywc_v03_shu_modifiers.txt")))


class BudgetWorld(PulseWorld):
    def __init__(self):
        countries = {
            "SHU": {"gold_reserves": 3200, "ywc_t12_stage": 1552, "ywc_t12_popup_epoch": 3},
            "capital": {"owner": "SHU", "gdp": 90, "buildings": ["barracks"]},
            "small": {"owner": "SHU", "gdp": 10, "buildings": ["port_a"]},
            "large": {"owner": "SHU", "gdp": 60, "buildings": ["port_b"]},
            "foreign": {"owner": "DMG", "gdp": 100, "buildings": ["port_c"]},
            "barracks": {"type": "building_barracks", "occupancy": 1},
            "port_a": {"type": "building_port", "occupancy": .3},
            "port_b": {"type": "building_port", "occupancy": .8},
            "port_c": {"type": "building_port", "occupancy": .9},
            "formation": {"is_army": True, "is_mobilized": False},
        }
        super().__init__(script("common/scripted_effects/ywc_v03_t12_effects.txt"), countries)
        self.capital = "capital"
        self.states = ("capital", "small", "large", "foreign")
        self.country = countries["SHU"]
        self.country["law"] = "law_national_militia"
        self.journals.append(("SHU", [("type", "=", "ywc_je_v03_t12_representation_pact")]))
        self.open_popup()

    def open_popup(self):
        self.scopes["ywc_t12_popup_epoch"] = self.country["ywc_t12_popup_epoch"]

    def option(self, number, key):
        name = f"ywc_society.{number}.{key}"
        return next(body for k, _, body in EVENTS[f"ywc_society.{number}"]
                    if k == "option" and fields(body)["name"] == name)

    def choose(self, number, key):
        option = self.option(number, key)
        self.execute([n for n in option if n[0] not in
                      {"name", "trigger", "custom_tooltip", "ai_chance"}], "SHU")

    def condition(self, node, tag):
        key, op, body = node
        fact = self.countries[tag]
        if key in TRIGGERS:
            return self.conditions(TRIGGERS[key], tag)
        if key == "exists" and body == "capital":
            return self.capital is not None
        if key == "capital":
            return self.capital is not None and self.conditions(body, self.capital)
        if key == "owner" and body == "root":
            return fact["owner"] == "SHU"
        if key == "any_scope_state":
            return any(self.conditions(body, state) for state in self.states)
        if key == "any_scope_building":
            return any(self.conditions(body, building) for building in fact["buildings"])
        if key == "is_building_type":
            return fact["type"] == body
        if key == "occupancy" and op == ">=":
            return fact["occupancy"] >= float(body)
        if key == "state_infrastructure_balance" and op == "<":
            return fact["spare_infrastructure"] < float(body)
        if key == "any_military_formation":
            return self.conditions(body, "formation")
        if key in {"is_army", "is_mobilized"}:
            return fact[key] == (body == "yes")
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        resolved = []
        for key, op, body in nodes:
            if key == "capital":
                resolved.append((f"c:{self.capital}", op, body))
            elif key == "ordered_scope_state":
                selector = fields(body)
                candidates = [s for s in self.states if self.conditions(selector["limit"], s)]
                candidates.sort(key=lambda s: self.countries[s][selector["order_by"]], reverse=True)
                actions = [n for n in body if n[0] not in
                           {"limit", "order_by", "position", "check_range_bounds"}]
                if candidates:
                    resolved.append((f"c:{candidates[int(selector['position'])]}", op, actions))
            else:
                resolved.append((key, op, body))
        super().execute(resolved, tag)


class BudgetTests(unittest.TestCase):
    def test_earmarks_reach_one_state_and_cannot_be_bought_twice(self):
        for choice, target, name, stat, magnitude in [
            ("services_first", "capital", "ywc_t12_capital_post_roads", "state_infrastructure_add", "1"),
            ("defense_share", "large", "ywc_t12_escort_provisions", "building_port_throughput_add", "0.05"),
        ]:
            with self.subTest(choice=choice):
                w = BudgetWorld()
                w.country["gold_reserves"] = 800
                w.choose(1552, choice)
                w.choose(1552, "services_first")
                w.choose(1552, "defense_share")
                self.assertEqual(w.treasury["SHU"], -800)
                self.assertEqual([(s, m["name"], m["days"]) for s, m in w.modifiers],
                                 [(target, name, "180")])
                self.assertEqual(fields(MODIFIERS[name])[stat], magnitude)
                self.assertEqual(w.country["ywc_t12_stage"], 1555)

    def test_ineligible_cached_choice_spends_nothing_and_can_be_reviewed(self):
        for loss, choice in [("no_port", "defense_share"), ("owner", "services_first"),
                             ("no_capital", "services_first"), ("cash", "defense_share")]:
            with self.subTest(loss=loss):
                w = BudgetWorld()
                gate = fields(w.option(1552, choice))["trigger"]
                self.assertTrue(w.conditions(gate, "SHU"))
                if loss == "no_port":
                    w.countries["port_a"]["occupancy"] = .29
                    w.countries["large"]["owner"] = "DMG"
                elif loss == "no_capital":
                    w.capital = None
                elif loss == "owner":
                    w.countries["capital"]["owner"] = "DMG"
                else:
                    w.country["gold_reserves"] = 799
                self.assertFalse(w.conditions(gate, "SHU"))
                w.choose(1552, choice)
                self.assertEqual(w.country["ywc_t12_pending"], 1552)
                self.assertNotIn("ywc_t12_budget_paid", w.country)
                w.open_popup()
                w.choose(1552, "even_split")
                self.assertEqual(w.country["ywc_t12_budget_mode"], 3)
                self.assertEqual((w.treasury["SHU"], w.modifiers), (0, []))

    def test_ai_spending_is_sensitive_to_cash_and_prefers_deciding(self):
        w = BudgetWorld()
        options = ("services_first", "defense_share", "even_split", "wait")
        for reserves, spare, war, expected in [
            (1000, 0, True, [10, 10, 100, 5]),
            (2000, -2, False, [50, 10, 100, 5]),
            (3200, 4, False, [20, 20, 100, 5]),
            (3200, 0, False, [60, 20, 100, 5]),
            (3200, 4, True, [20, 60, 100, 5]),
        ]:
            w.country["gold_reserves"] = reserves
            w.country["is_at_war"] = war
            w.countries["capital"]["spare_infrastructure"] = spare
            self.assertEqual([w.ai_weight(fields(w.option(1552, o))["ai_chance"], "SHU")
                              for o in options], expected)

    def test_claims_follow_war_or_a_mobilized_army_and_remain_resolvable(self):
        for war, army, mobilized, stage in [(False, True, False, 1555), (False, False, True, 1555),
                                            (False, True, True, 1553), (True, True, False, 1553)]:
            with self.subTest(war=war, army=army, mobilized=mobilized):
                w = BudgetWorld()
                w.country["is_at_war"] = war
                w.countries["formation"].update(is_army=army, is_mobilized=mobilized)
                w.choose(1552, "even_split")
                self.assertEqual(w.country["ywc_t12_stage"], stage)
                if stage == 1553:
                    w.country["is_at_war"] = False
                    w.countries["formation"]["is_mobilized"] = False
                    w.open_popup()
                    w.choose(1553, "record_pledge")
                    self.assertEqual(w.country["ywc_t12_stage"], 1555)
                w.open_popup()
                w.choose(1555, "extend_once")
                self.assertEqual(w.country["ywc_t12_pending"], 1555)
                w.open_popup()
                w.choose(1555, "sunset_now")
                self.assertEqual(w.country["ywc_t12_stage"], 1556)
