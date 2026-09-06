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


class RuntimeGuardrailsTest(unittest.TestCase):
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
        for tag in ("KOR", "LAN"):
            self.assertNotRegex(dynamic_names, rf"(?m)^\s*{tag}\s*=\s*\{{")
        for tag in ("MNG", "TIB", "KOR"):
            self.assertNotRegex(flags, rf"(?m)^\s*{tag}\s*=\s*\{{")

    def test_dynamic_maritime_name_evaluates_shared_trigger_in_country_scope(self):
        text = (MOD / "common/dynamic_country_names/ywc_dynamic_names.txt").read_text(
            "utf-8-sig"
        )
        for tag in ("SHU", "JHG", "DMG", "NQG", "OIR", "MNG", "TIB", "NMG"):
            expected = (
                rf"trigger = \{{ exists = scope:actor "
                rf"scope:actor \?= \{{ c:{tag} \?= this "
                rf"ywc_has_maritime_network = yes \}} \}}"
            )
            self.assertRegex(text, expected)

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
        self.assertEqual(declared & {"ywc_dlc.1", "ywc_jhg.6", "ywc_dmg.6", "ywc_nqg.6", "ywc_nmg.6"}, set())
        self.assertTrue(catalog_events.issubset(triggered))


if __name__ == "__main__":
    unittest.main()
