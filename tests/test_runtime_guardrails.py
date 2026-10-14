import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MOD = ROOT / "yongchang_world"
ACTION_LOCATIONS = (
    MOD / "localization/english/ywc_diplomacy_l_english.yml",
    MOD / "localization/simp_chinese/ywc_diplomacy_l_simp_chinese.yml",
)
LAW_COMPATIBILITY = (
    MOD / "common/history/countries/ywc_regional_countries.txt",
    MOD / "common/history/countries/ywc_ocean_countries.txt",
    MOD / "common/history/countries/zzz_ywc_opening_profiles.txt",
)
OPENING_PROFILES = ROOT / "data/scenario/opening_profiles.json"
REGIONAL_LAW_TAGS = (
    "MHG", "WBK", "KHQ", "HUL", "SOL", "AMR",
    "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT", "DER", "KAM", "GYL",
    "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "AMD", "DLI", "PNP",
    "PLW", "YAP", "MHL", "MRG",
)

def country_blocks(text, tag):
    blocks = []
    for match in re.finditer(rf"(?m)^\s*c:{tag}\s+\?=\s*\{{", text):
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[match.start():index + 1])
                    break
    return blocks


class RuntimeGuardrailsTest(unittest.TestCase):
    def test_regional_starts_use_law_compatible_fallbacks(self):
        text = "\n".join(path.read_text("utf-8-sig") for path in LAW_COMPATIBILITY)
        profiles = json.loads(OPENING_PROFILES.read_text(encoding="utf-8-sig"))["countries"]
        for tag in REGIONAL_LAW_TAGS:
            blocks = country_blocks(text, tag)
            laws = [law for block in blocks for law in re.findall(r"activate_law\s*=\s*law_type:(law_[a-z0-9_]+)", block)]
            laws.extend(profiles.get(tag, {}).get("laws", []))
            self.assertIn("law_isolationism", laws, tag)
            effective_speech_law = next((law for law in reversed(laws) if law in {"law_censorship", "law_right_of_assembly"}), None)
            self.assertIn(effective_speech_law, {"law_censorship", "law_right_of_assembly"}, tag)

    def test_shun_start_uses_the_reviewed_censorship_law(self):
        source = (MOD / "common/history/countries/ywc_shu.txt").read_text("utf-8-sig")
        overlay = (MOD / "common/history/countries/zzz_ywc_opening_profiles.txt").read_text("utf-8-sig")
        profile = json.loads(OPENING_PROFILES.read_text(encoding="utf-8-sig"))["countries"]["SHU"]
        self.assertNotIn("activate_law = law_type:law_censorship", source)
        self.assertIn("law_censorship", profile["laws"])
        self.assertIn("activate_law = law_type:law_censorship", country_blocks(overlay, "SHU")[-1])

    def test_mod_does_not_add_unsupported_interest_group_database_objects(self):
        text = (MOD / "common/interest_groups/ywc_interest_groups.txt").read_text("utf-8-sig")
        self.assertNotRegex(text, r"(?m)^\s*ig_ywc_[A-Za-z0-9_]+\s*=\s*\{")

    def test_custom_ideologies_use_the_law_group_of_each_law(self):
        text = (MOD / "common/ideologies/ywc_ideologies.txt").read_text("utf-8-sig")
        governance_blocks = re.findall(
            r"lawgroup_governance_principles\s*=\s*\{(?P<body>[^}]*)\}", text
        )
        self.assertEqual(len(governance_blocks), 10)
        for body in governance_blocks:
            self.assertNotRegex(body, r"\blaw_(?:autocracy|oligarchy)\b")

    def test_existing_vanilla_lan_flag_is_not_redeclared(self):
        text = (MOD / "common/flag_definitions/ywc_flags.txt").read_text("utf-8-sig")
        self.assertNotRegex(text, r"(?m)^\s*LAN\s*=\s*\{")

    def test_existing_vanilla_country_lists_are_not_redeclared(self):
        dynamic_names = (MOD / "common/dynamic_country_names/ywc_dynamic_names.txt").read_text("utf-8-sig")
        flags = (MOD / "common/flag_definitions/ywc_flags.txt").read_text("utf-8-sig")
        # KOR and LAN keep their vanilla dynamic-name lists because those names
        # already fit the mod; MGL is the one deliberate override (see
        # test_mgl_dynamic_names_override_vanilla_mongolian_state). Cross-file
        # entries for one tag merge into the same candidate list -- vanilla's
        # own 00_dynamic_country_names.txt holds multiple entries per tag
        # (51 of 146 tags), so same-tag additions are list appends, not
        # rejected duplicates.
        for tag in ("KOR", "LAN"):
            self.assertNotRegex(dynamic_names, rf"(?m)^\s*{tag}\s*=\s*\{{")
        for tag in ("MGL", "TIB", "KOR"):
            self.assertNotRegex(flags, rf"(?m)^\s*{tag}\s*=\s*\{{")

    def test_dynamic_maritime_name_evaluates_shared_trigger_in_country_scope(self):
        text = (MOD / "common/dynamic_country_names/ywc_dynamic_names.txt").read_text(
            "utf-8-sig"
        )
        for tag in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "NMG"):
            expected = (
                rf"trigger = \{{ exists = scope:actor "
                rf"scope:actor \?= \{{ c:{tag} \?= this "
                rf"ywc_has_maritime_network = yes \}} \}}"
            )
            self.assertRegex(text, expected)

    def test_mgl_dynamic_names_override_vanilla_mongolian_state(self):
        text = (MOD / "common/dynamic_country_names/ywc_dynamic_names.txt").read_text(
            "utf-8-sig"
        )
        # Vanilla 00_dynamic_country_names.txt gives MGL
        # dyn_c_great_mongolian_state (priority 0, monarchy trigger); the mod
        # entries must outrank it or the map shows the wrong country name.
        khalkha = (
            r"name = ywc_dyn_mgl_khalkha "
            r"adjective = ywc_dyn_mgl_khalkha_adj "
            r"is_main_tag_only = yes priority = 10 "
            r"trigger = \{ exists = scope:actor "
            r"scope:actor \?= \{ c:MGL \?= this "
            r"coa_def_monarchy_flag_trigger = yes \} \}"
        )
        self.assertRegex(text, khalkha)
        self.assertRegex(
            text,
            r"name = ywc_dyn_mgl_maritime .*?priority = 20",
        )

    def test_maritime_trigger_uses_shared_numeric_threshold(self):
        text = (MOD / "common/scripted_triggers/ywc_shared_triggers.txt").read_text(
            "utf-8-sig"
        )
        match = re.search(
            r"ywc_has_maritime_network\s*=\s*\{(?P<body>.*?)\n\}",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("has_variable = ywc_maritime_network_level", body)
        self.assertRegex(body, r"var:ywc_maritime_network_level\s*>=\s*60")
        self.assertNotRegex(body, r"c:(?:JHG|DMG|LAN|NMG)")

    def test_shu_dynamic_names_match_shun_identity(self):
        zh = (MOD / "localization/simp_chinese/ywc_content_l_simp_chinese.yml").read_text(
            "utf-8-sig"
        )
        en = (MOD / "localization/english/ywc_content_l_english.yml").read_text(
            "utf-8-sig"
        )
        self.assertRegex(zh, r'ywc_dyn_shu_heritage:0\s+"大顺礼制国"')
        self.assertRegex(zh, r'ywc_dyn_shu_maritime:0\s+"大顺海疆国"')
        self.assertRegex(en, r'ywc_dyn_shu_heritage:0\s+"Shun Ritual State"')
        self.assertRegex(en, r'ywc_dyn_shu_maritime:0\s+"Shun Maritime State"')
        self.assertNotIn("蜀汉礼制国", zh)
        self.assertNotIn("蜀汉海疆国", zh)
        self.assertNotIn('"Shu Ritual State"', en)
        self.assertNotIn('"Shu Maritime State"', en)

    def test_custom_flag_triggers_keep_country_comparisons_in_country_scope(self):
        text = (MOD / "common/flag_definitions/ywc_flags.txt").read_text("utf-8-sig")
        self.assertNotIn("?= THIS", text)
        for tag in ("SHU", "JHG", "DMG", "NQG", "OIR", "NMG"):
            self.assertRegex(
                text,
                rf"exists = c:{tag} c:{tag} \?= \{{ ywc_has_maritime_network = yes \}}",
            )

    def test_static_modifiers_use_known_11311_modifier_types(self):
        text = (MOD / "common/static_modifiers/ywc_static_modifiers.txt").read_text("utf-8-sig")
        for invalid in (
            "country_tax_capacity_mult",
            "country_convoy_capacity_mult",
            "country_migration_pull_mult",
        ):
            self.assertNotIn(invalid, text)

    def test_custom_ideology_icons_use_known_base_game_ids(self):
        text = (MOD / "common/ideologies/ywc_ideologies.txt").read_text("utf-8-sig")
        self.assertIn("market_liberal.dds", text)
        self.assertNotIn("mercantile.dds", text)

    def test_diplomatic_action_has_all_runtime_notification_keys(self):
        keys = {
            "ywc_nmg_autonomy_negotiation_proposal_notification_name",
            "ywc_nmg_autonomy_negotiation_proposal_notification_desc",
            "ywc_nmg_autonomy_negotiation_proposal_accepted_name",
            "ywc_nmg_autonomy_negotiation_proposal_accepted_desc",
            "ywc_nmg_autonomy_negotiation_proposal_declined_name",
            "ywc_nmg_autonomy_negotiation_proposal_declined_desc",
            "ywc_nmg_autonomy_negotiation_action_notification_break_name",
            "ywc_nmg_autonomy_negotiation_action_notification_break_desc",
        }
        for path in ACTION_LOCATIONS:
            text = path.read_text("utf-8-sig")
            for key in keys:
                self.assertRegex(text, rf"(?m)^\s*{re.escape(key)}:[0-9]+")

    def test_diplomatic_action_icon_is_shipped(self):
        self.assertTrue(
            (
                MOD
                / "gfx/interface/icons/lens_toolbar_icons/ywc_nmg_autonomy_negotiation.dds"
            ).is_file()
        )

    def test_catalog_events_are_triggered_and_no_known_orphans_remain(self):
        catalog = json.loads(
            (ROOT / "data/content/content_catalog.json").read_text("utf-8")
        )
        declared = set()
        for path in (MOD / "events").glob("*.txt"):
            declared.update(
                re.findall(
                    r"(?m)^\s*(ywc_[a-z0-9_]+\.[0-9]+)\s*=\s*\{",
                    path.read_text("utf-8-sig"),
                )
            )
        triggered = set(
            re.findall(
                r"trigger_event\s*=\s*\{\s*id\s*=\s*(ywc_[a-z0-9_]+\.[0-9]+)",
                "\n".join(path.read_text("utf-8-sig") for path in MOD.rglob("*.txt")),
            )
        )
        catalog_events = {
            event
            for row in catalog["countries"].values()
            for event in row["events"]
        }
        self.assertEqual(declared & {"ywc_dlc.1"}, set())
        self.assertTrue(catalog_events.issubset(triggered))


if __name__ == "__main__":
    unittest.main()
