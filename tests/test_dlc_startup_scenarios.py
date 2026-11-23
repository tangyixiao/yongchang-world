"""Exercise the shipped startup hook with explicit DLC and controller fixtures."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from clausewitz_harness import PulseWorld, parse


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "yongchang_world/common"
NATIONAL_MODIFIERS = {
    "SHU": "ywc_ai_shu_domestic_priority",
    "JHG": "ywc_ai_jinghai_defensive_maritime",
    "DMG": "ywc_ai_dongming_spanish_pressure",
}


def fields(nodes):
    return {key: value for key, _, value in nodes}


def definitions(path):
    return fields(parse((COMMON / path).read_text("utf-8-sig")))


class StartupWorld(PulseWorld):
    def __init__(self, effects, features, ai_countries):
        super().__init__(effects, {tag: {} for tag in (*NATIONAL_MODIFIERS, "MEX")})
        self.features = features
        self.ai_countries = ai_countries
        self.strategies = {}

    def condition(self, node, tag):
        key, comparison, value = node
        if key == "has_dlc_feature" and comparison == "=":
            return value in self.features
        if key == "is_ai" and comparison == "=" and value in ("yes", "no"):
            return (tag in self.ai_countries) == (value == "yes")
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        # Keep conditional chains together when delegating to PulseWorld.
        start = 0
        for index, (key, _, value) in enumerate(nodes):
            if key not in ("every_country", "set_strategy"):
                continue
            if start < index:
                super().execute(nodes[start:index], tag)
            if key == "every_country":
                for country in self.countries:
                    self.execute(value, country)
            else:
                self.strategies[tag] = value
            start = index + 1
        if start < len(nodes):
            super().execute(nodes[start:], tag)


class DlcStartupScenariosTest(unittest.TestCase):
    def test_country_grants_and_ai_strategies(self):
        matrix = json.loads((ROOT / "data/balance/dlc_matrix.json").read_text("utf-8"))
        guardrails = json.loads((ROOT / "data/balance/guardrails.json").read_text("utf-8"))
        effects = (COMMON / "scripted_effects/ywc_dlc_effects.txt").read_text("utf-8-sig")
        hooks = definitions("on_actions/ywc_startup_hooks.txt")
        callbacks = fields(hooks["on_game_started_after_lobby"])["on_actions"]
        modifiers = definitions("static_modifiers/ywc_static_modifiers.txt")
        journal = fields(definitions("journal_entries/ywc_dlc_compatibility.txt")["ywc_je_dlc_compatibility"])
        scenarios = (("none", False), ("none", True), ("charters", False), ("all", False), ("all", True))

        for config, with_ip5 in scenarios:
            features = set(matrix[config]["features"])
            if with_ip5:
                features.add("ip5_content")
            for ai_countries in ({"SHU", "MEX"}, {"JHG", "DMG"}):
                with self.subTest(config=config, with_ip5=with_ip5, ai=sorted(ai_countries)):
                    world = StartupWorld(effects, features, ai_countries)
                    for callback, _, _ in callbacks:
                        world.execute(fields(hooks[callback])["effect"], tag=None)

                    self.assertEqual(world.strategies, {
                        tag: guardrails[tag]["strategy_id"] for tag in ai_countries if tag in NATIONAL_MODIFIERS
                    })
                    self.assertEqual(world.countries["MEX"], {})
                    self.assertFalse(any(tag == "MEX" for tag, _ in world.modifiers))
                    self.assertCountEqual([(tag, fields(body)["type"]) for tag, body in world.journals],
                                          [(tag, "ywc_je_dlc_compatibility") for tag in NATIONAL_MODIFIERS])
                    for tag, national in NATIONAL_MODIFIERS.items():
                        with self.subTest(country=tag):
                            self.assertEqual(world.countries[tag]["ywc_dlc_base_path"], 1)
                            self.assertTrue(world.conditions(journal["complete"], tag))
                            grants = [entry for recipient, entry in world.modifiers if recipient == tag]
                            expected = [(name, "3650") for name in matrix[config]["modifiers"]]
                            self.assertCountEqual([(g["name"], g["days"]) for g in grants],
                                                  [(national, "10950"), *expected])
                            if config == "all":
                                key, total = {
                                    "SHU": ("country_legitimacy_base_add", "9"),
                                    "JHG": ("country_authority_mult", "0.13"),
                                    "DMG": ("country_legitimacy_base_add", "7"),
                                }[tag]
                                actual = sum(Decimal(fields(modifiers[g["name"]]).get(key, "0")) for g in grants)
                                self.assertEqual(actual, Decimal(total))
