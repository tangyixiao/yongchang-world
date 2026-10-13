"""Regression checks for the narrow Han royal outfit fallback and vanilla overrides."""

import pathlib
import os
import re
import unittest

from tools.build_state_history import balanced_end
try:
    from tests.clausewitz_harness import parse as parse_clausewitz
except ModuleNotFoundError:
    from clausewitz_harness import parse as parse_clausewitz


ROOT = pathlib.Path(__file__).parents[1]
MOD = ROOT / "yongchang_world"
VANILLA_ROOT = pathlib.Path(os.environ.get(
    "VIC3_GAME_ROOT", r"E:\SteamLibrary\steamapps\common\Victoria 3\game"
))
VANILLA_FILE = VANILLA_ROOT / "common/scripted_triggers/00_clothes_triggers.txt"


def block_for(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*(?:REPLACE:)?{re.escape(key)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {key}")
    opening = text.find("{", match.start(), match.end())
    return text[opening + 1 : balanced_end(text, opening)]


def canonical(text: str) -> str:
    text = re.sub(r"(?m)#.*$", "", text)
    return re.sub(r"\s+", "", text)


def declared_trigger(text: str, name: str):
    for key, comparison, body in parse_clausewitz(text):
        if key in (name, f"REPLACE:{name}") and comparison == "=":
            if not isinstance(body, list):
                raise AssertionError(f"{name} must be a parsed block")
            return body
    raise AssertionError(f"missing trigger: {name}")


def eval_gate(nodes, character, eacr_active=False, trigger_definitions=None):
    """Strictly evaluate the shipped appearance gate's small scope subset."""
    scope = {"scope:character": character}
    trigger_definitions = trigger_definitions or {}

    def evaluate(items, entity):
        return all(condition(node, entity) for node in items)

    def condition(node, entity):
        key, comparison, value = node
        if key in ("AND", "OR", "NOT", "NOR"):
            matches = [condition(child, entity) for child in value]
            return {"AND": all, "OR": any, "NOT": lambda xs: not all(xs),
                    "NOR": lambda xs: not any(xs)}[key](matches)
        if key.startswith("scope:"):
            target = scope.get(key)
            return target is not None and evaluate(value, target)
        if key == "exists":
            if value == "scope:character":
                return character is not None
            if value == "home_country":
                return entity.get("home_country") is not None
            if value == "c:CHI":
                return True
            raise AssertionError(f"unsupported exists check in appearance gate: {node}")
        if key == "EACR_is_active_trigger":
            if value != "no":
                raise AssertionError(f"unsupported EACR trigger polarity: {node}")
            return not eacr_active
        if key in trigger_definitions and value == "yes":
            return evaluate(trigger_definitions[key], {"scope": scope})
        if key == "is_ruler_of_own_country":
            return entity.get("is_ruler") is (value == "yes")
        if key == "is_heir_of_own_country":
            return entity.get("is_heir") is (value == "yes")
        if key == "culture":
            return evaluate(value, entity.get("culture") or {})
        if key == "has_discrimination_trait":
            return value in entity.get("traits", set())
        if key == "has_discrimination_trait_group":
            return value in entity.get("trait_groups", set())
        if key == "home_country":
            country = entity.get("home_country")
            if isinstance(value, list):
                return country is not None and evaluate(value, country)
            if value.startswith("c:"):
                return country is not None and country.get("tag") == value[2:]
            raise AssertionError(f"unsupported home_country predicate: {node}")
        if key == "has_law":
            if comparison != "=":
                raise AssertionError(f"unsupported law comparison: {node}")
            return value in entity.get("laws", set())
        if key == "has_law_or_variant":
            return value in entity.get("laws", set())
        if key == "this" and value.startswith("cu:"):
            return entity.get("id") == value[3:]
        if key.startswith("c:") and comparison == "?=":
            return entity.get("tag") == key[2:] and value == "this"
        raise AssertionError(f"unsupported appearance gate predicate: {node}")

    return evaluate(nodes, {"scope": scope})


class HanRoyalAppearanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod_triggers = (MOD / "common/scripted_triggers/ywc_appearance_triggers.txt").read_text("utf-8-sig")
        cls.eacr_compat = (MOD / "common/scripted_triggers/00_ywc_EACR_compat_trigger.txt").read_text("utf-8-sig")
        cls.mod_trigger_ast = parse_clausewitz(cls.mod_triggers)
        cls.mod_portraits = (MOD / "gfx/portraits/portrait_modifiers/ywc_han_royal_appearance.txt").read_text("utf-8-sig")

    def vanilla_trigger_body(self, name):
        if not VANILLA_FILE.is_file():
            self.skipTest(f"Vanilla trigger comparison requires VIC3_GAME_ROOT or {VANILLA_FILE}")
        vanilla = VANILLA_FILE.read_text("utf-8-sig")
        return declared_trigger(vanilla, name)

    def test_identity_gate_is_han_rulers_and_heirs_in_four_states(self):
        gate = block_for(self.mod_triggers, "ywc_han_royal_appearance_trigger")
        self.assertIn("is_ruler_of_own_country=yes", canonical(gate))
        self.assertIn("is_heir_of_own_country=yes", canonical(gate))
        self.assertIn("has_discrimination_trait=heritage_han", canonical(gate))
        self.assertIn("has_law=law_type:law_monarchy", canonical(gate))
        self.assertIn("has_law=law_type:law_social_monarchy", canonical(gate))
        tags = set(re.findall(r"c:([A-Z]{3})\s*\?=\s*this", gate))
        self.assertEqual(tags, {"SHU", "DMG", "NMG", "MHG"})

    def test_shipped_gate_and_imperial_exclusion_behavior_matrix(self):
        gate = declared_trigger(self.mod_triggers, "ywc_han_royal_appearance_trigger")
        fallback = declared_trigger(self.mod_triggers, "ywc_han_royal_fallback_trigger")
        imperial = declared_trigger(self.mod_triggers, "chinese_imperial_clothes_trigger")
        court = declared_trigger(self.mod_triggers, "chinese_court_clothes_trigger")
        trigger_definitions = {
            "ywc_han_royal_appearance_trigger": gate,
            "ywc_han_royal_fallback_trigger": fallback,
        }
        cases = {
            "SHU Han monarchy ruler": ("SHU", True, True, False, False, True, False, False),
            "SHU Han monarchy heir": ("SHU", True, False, True, False, True, False, False),
            "DMG Han social monarchy ruler": ("DMG", True, True, False, True, True, False, False),
            "NMG Han monarchy ruler": ("NMG", True, True, False, False, True, False, False),
            "MHG Han monarchy ruler": ("MHG", True, True, False, False, True, False, False),
            "CHI Han monarchy ruler": ("CHI", True, True, False, False, False, True, True),
            "JHG Han monarchy ruler": ("JHG", True, True, False, False, False, True, True),
            "SHU non-Han monarch": ("SHU", False, True, False, False, False, False, False),
            "SHU Han non-royal character": ("SHU", True, False, False, False, False, False, True),
            "SHU Han republic": ("SHU", True, True, False, False, False, False, True),
            "SHU Han without country": (None, True, True, False, False, False, False, True),
        }
        for label, (tag, han, ruler, heir, social, expected_identity, expected_imperial, expected_court) in cases.items():
            with self.subTest(case=label):
                country = None if tag is None else {
                    "tag": tag,
                    "laws": ({"law_type:law_social_monarchy"} if social else
                             ({"law_type:law_monarchy"} if label != "SHU Han republic" else set())),
                }
                character = {
                    "is_ruler": ruler,
                    "is_heir": heir,
                    "culture": {"traits": ({"heritage_han"} if han else set()), "id": "han"},
                    "home_country": country,
                }
                expected = (tag in {"SHU", "DMG", "NMG", "MHG"} and han and
                            (ruler or heir) and country is not None and bool(country["laws"]))
                self.assertEqual(eval_gate(gate, character), expected_identity and expected, label)
                self.assertEqual(eval_gate(fallback, character, trigger_definitions=trigger_definitions), expected, label)
                self.assertEqual(eval_gate(imperial, character, trigger_definitions=trigger_definitions), expected_imperial, label)
                self.assertEqual(eval_gate(court, character, trigger_definitions=trigger_definitions), expected_court, label)

        shu_han = {"is_ruler": True, "is_heir": False,
                   "culture": {"traits": {"heritage_han"}, "id": "han"},
                   "home_country": {"tag": "SHU", "laws": {"law_type:law_monarchy"}}}
        self.assertTrue(eval_gate(gate, shu_han, eacr_active=True, trigger_definitions=trigger_definitions), "identity remains active with EACR")
        self.assertFalse(eval_gate(fallback, shu_han, eacr_active=True, trigger_definitions=trigger_definitions), "EACR active disables only Yongchang fallback")
        self.assertFalse(eval_gate(imperial, shu_han, eacr_active=True, trigger_definitions=trigger_definitions), "royal exclusion stays active with EACR")
        self.assertFalse(eval_gate(court, shu_han, eacr_active=True, trigger_definitions=trigger_definitions), "court-cap exclusion stays active with EACR")

        shu_heir = {**shu_han, "is_ruler": False, "is_heir": True}
        self.assertTrue(eval_gate(gate, shu_heir, eacr_active=True, trigger_definitions=trigger_definitions))
        self.assertFalse(eval_gate(fallback, shu_heir, eacr_active=True, trigger_definitions=trigger_definitions))
        self.assertFalse(eval_gate(court, shu_heir, eacr_active=True, trigger_definitions=trigger_definitions))

    def test_eacr_compat_default_matches_authors_replace_or_create_contract(self):
        self.assertEqual(
            canonical(block_for(self.eacr_compat, "EACR_is_active_trigger")),
            "always=no",
        )

    def test_imperial_override_preserves_vanilla_predicate_and_adds_gate_exclusion(self):
        vanilla = self.vanilla_trigger_body("chinese_imperial_clothes_trigger")
        override = block_for(self.mod_triggers, "chinese_imperial_clothes_trigger")
        # Remove exactly the added royal exclusion, then require all original
        # scope conditions and grouping to remain structurally identical.
        override_without_exclusion = re.sub(
            r"NOT\s*=\s*\{\s*ywc_han_royal_appearance_trigger\s*=\s*yes\s*\}",
            "",
            override,
        )
        override_ast = declared_trigger(
            f"test_override = {{{override_without_exclusion}}}", "test_override"
        )
        self.assertEqual(override_ast, vanilla)
        self.assertIn("NOT={ywc_han_royal_appearance_trigger=yes}", canonical(override))
        self.assertTrue(re.search(r"(?m)^\s*REPLACE:chinese_imperial_clothes_trigger\s*=", self.mod_triggers))

    def test_court_exclusion_keeps_vanilla_scope_rules_and_other_countries(self):
        vanilla = self.vanilla_trigger_body("chinese_court_clothes_trigger")
        override = block_for(self.mod_triggers, "chinese_court_clothes_trigger")
        override_without_exclusion = re.sub(
            r"NOT\s*=\s*\{\s*ywc_han_royal_appearance_trigger\s*=\s*yes\s*\}",
            "",
            override,
            count=1,
        )
        override_ast = declared_trigger(
            f"test_override = {{{override_without_exclusion}}}", "test_override"
        )
        self.assertEqual(override_ast, vanilla)
        self.assertRegex(self.mod_triggers, r"(?m)^\s*REPLACE:chinese_court_clothes_trigger\s*=")
        # Exclusion is tied to the state/ruler/law gate, so vanilla's generic
        # culture-based court-clothes rule remains available everywhere else.
        self.assertIn("ywc_han_royal_appearance_trigger=yes", canonical(override))

    def test_fallback_is_weighted_only_and_does_not_override_hair(self):
        self.assertIn("template=chinese_court_outfits", canonical(self.mod_portraits))
        self.assertIn("template=no_headgear", canonical(self.mod_portraits))
        self.assertIn("ywc_han_royal_fallback_trigger=yes", canonical(self.mod_portraits))
        self.assertNotIn("INJECT:hairstyles", self.mod_portraits)
        self.assertNotRegex(self.mod_portraits, r"deterministically\s+wins")


if __name__ == "__main__":
    unittest.main()
