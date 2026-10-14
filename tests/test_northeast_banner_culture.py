"""The northeast banner leagues: Manchu-led cultures and a bespoke
establishment law (law_ywc_banner_rites) written the way vanilla writes
country-specific establishment laws - the Ottoman millet system being the
pattern (one law in lawgroup_church_and_state expressing how THIS polity
arranges religion), NOT a template to copy Islamic-specific content from."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
LAW_FILE = ROOT / "yongchang_world/common/laws/ywc_laws.txt"
DEFINITIONS = ROOT / "yongchang_world/common/country_definitions/ywc_regional_countries.txt"
PROFILE_FILE = ROOT / "data/scenario/opening_profiles.json"
GENERATED = ROOT / "yongchang_world/common/history/countries/zzz_ywc_opening_profiles.txt"
ZH_LOC = ROOT / "yongchang_world/localization/simp_chinese/ywc_content_l_simp_chinese.yml"
EN_LOC = ROOT / "yongchang_world/localization/english/ywc_content_l_english.yml"
VANILLA_CULTURES = GAME / "common/cultures/00_cultures.txt"

BANNER_TAGS = ("SOL", "AMR")
LAW_ID = "law_ywc_banner_rites"


def braced_block(text: str, pattern: str) -> str:
    start = re.search(pattern, text)
    if not start:
        raise AssertionError(f"no block matched {pattern}")
    opening = text.find("{", start.start())
    depth = 1
    pos = opening + 1
    while pos < len(text) and depth:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    if depth:
        raise AssertionError(f"unclosed block matched {pattern}")
    return text[opening + 1 : pos - 1]


def scoped_block(text: str, tag: str) -> str:
    start = re.search(rf"c:{tag}\s*\?=\s*\{{", text)
    if not start:
        raise AssertionError(f"no history block for {tag}")
    depth = 1
    pos = start.end()
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start.end() : i]
    raise AssertionError(f"unclosed history block for {tag}")


class NortheastBannerRitesTest(unittest.TestCase):
    def test_sol_and_amr_are_manchu_led_with_siberian_secondary(self):
        definitions = DEFINITIONS.read_text(encoding="utf-8-sig")
        for tag in BANNER_TAGS:
            match = re.search(
                rf"(?m)^{tag}\s*=\s*\{{.*?cultures\s*=\s*\{{([^}}]*)\}}", definitions, re.S
            )
            self.assertIsNotNone(match, tag)
            self.assertEqual(match.group(1).split(), ["manchu", "siberian"], tag)

    def test_profiles_carry_banner_rites_law_and_cultures(self):
        data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        for tag in BANNER_TAGS:
            profile = data["countries"][tag]
            self.assertEqual(profile["primary_cultures"], ["manchu", "siberian"], tag)
            self.assertIn(LAW_ID, profile["laws"], tag)
            self.assertEqual(profile["state_religion"], "animist", tag)
            self.assertFalse(profile["state_religion_law"], tag)
        for tag in ("HUL", "KHQ"):
            self.assertNotIn(LAW_ID, data["countries"][tag].get("laws", []), tag)

    def test_generated_history_activates_banner_rites_only_for_banner_leagues(self):
        generated = GENERATED.read_text(encoding="utf-8-sig")
        for tag in BANNER_TAGS:
            block = scoped_block(generated, tag)
            self.assertIn(f"activate_law = law_type:{LAW_ID}", block, tag)
            self.assertIn("set_state_religion = rel:animist", block, tag)
        for tag in ("HUL", "KHQ", "SHU"):
            self.assertNotIn(LAW_ID, scoped_block(generated, tag), tag)

    def test_banner_rites_is_bespoke_not_a_millet_copy(self):
        raw = LAW_FILE.read_bytes()
        self.assertEqual(raw[:3], b"\xef\xbb\xbf", "law file must keep its UTF-8 BOM")
        law_text = LAW_FILE.read_text(encoding="utf-8-sig")
        law = braced_block(law_text, rf"(?m)^{LAW_ID}\s*=\s*\{{")

        self.assertIn("group = lawgroup_church_and_state", law)
        self.assertIn("parent = law_state_religion", law)
        self.assertIn('icon = "gfx/interface/icons/law_icons/state_religion.dds"', law)
        self.assertIn("progressiveness = -50", law)
        for requirement in ("law_theocracy", "law_monarchy", "law_chiefdom"):
            self.assertIn(requirement, law)

        # Shared-sacrifice semantics: no conversion mandate, no jizya, no
        # conscription penalty - those belong to the Ottoman millet context.
        self.assertNotIn("tax_modifier_", law)
        self.assertNotIn("tax_heathen_add", law)
        self.assertNotIn("state_conversion_mult", law)
        self.assertNotIn("state_conscription_rate_mult", law)
        self.assertNotIn("state_religion_wages_mult", law)
        for policy in (
            "violent_hostility",
            "cultural_erasure",
            "open_prejudice",
            "second_rate_citizen",
            "full_acceptance",
        ):
            self.assertIn(
                f"country_allow_conversion_{policy}_bool = no", law, policy
            )

        modifiers = braced_block(law, r"(?m)^\s*modifier\s*=\s*\{")
        self.assertIn("interest_group_ig_devout_pol_str_mult = 0.25", modifiers)
        self.assertIn("country_authority_add = 100", modifiers)
        self.assertIn("country_acceptance_state_religion_add = 25", modifiers)
        self.assertIn("country_acceptance_shared_religious_trait_add = 10", modifiers)
        self.assertIn("country_acceptance_shared_religious_trait_group_add = 10", modifiers)
        self.assertIn("country_acceptance_no_shared_religious_trait_add = -15", modifiers)

        visible = braced_block(law, r"(?m)^\s*is_visible\s*=\s*\{")
        self.assertIn("c:SOL ?= this", visible)
        self.assertIn("c:AMR ?= this", visible)
        tags = set(re.findall(r"c:([A-Z]{3})", visible))
        self.assertEqual(tags, set(BANNER_TAGS))

        self.assertRegex(law, r"can_impose\s*=\s*\{\s*always\s*=\s*no\s*\}")
        self.assertNotIn("deactivate_law", law, "no self-revert guard needed")

    def test_banner_cultures_exist_in_vanilla_with_expected_default_religions(self):
        cultures = VANILLA_CULTURES.read_text(encoding="utf-8-sig")
        manchu = braced_block(cultures, r"(?m)^manchu\s*=\s*\{")
        siberian = braced_block(cultures, r"(?m)^siberian\s*=\s*\{")
        self.assertIn("religion = confucian", manchu)
        self.assertIn("religion = animist", siberian)

    def test_banner_rites_localization_exists_in_both_languages(self):
        for path in (ZH_LOC, EN_LOC):
            text = path.read_text(encoding="utf-8-sig")
            self.assertRegex(text, rf'(?m)^\s*{LAW_ID}:0\s+"[^"]+"')
            self.assertRegex(text, rf'(?m)^\s*{LAW_ID}_desc:0\s+"[^"]+"')
            self.assertNotIn("millet", text)
        zh = ZH_LOC.read_text(encoding="utf-8-sig")
        self.assertIn("盟旗共祭制", zh)

    def test_all_touched_paradox_files_keep_utf8_bom(self):
        for path in (LAW_FILE, DEFINITIONS, GENERATED, ZH_LOC, EN_LOC):
            self.assertEqual(path.read_bytes()[:3], b"\xef\xbb\xbf", str(path))


if __name__ == "__main__":
    unittest.main()