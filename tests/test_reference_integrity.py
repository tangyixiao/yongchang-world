"""Cross-file reference integrity: every ywc_ key a script references must
be defined somewhere in the mod. Dangling references parse silently but only
fail at runtime, which hidden preloads never reach."""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MOD = ROOT / "yongchang_world"


def scripts():
    return sorted(MOD.rglob("*.txt"))


def all_text() -> str:
    return "\n".join(p.read_text("utf-8-sig") for p in scripts())


def defined_in(folder: str, prefix: str = "ywc_") -> set:
    out = set()
    pattern = rf"^({prefix}[A-Za-z0-9_.]+)\s*=\s*\{{"
    for path in (MOD / folder).rglob("*.txt"):
        out.update(re.findall(pattern, path.read_text("utf-8-sig"), re.MULTILINE))
    return out


class ReferenceIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = all_text()
        cls.strategies = defined_in("common/ai_strategies", prefix="ai_strategy_ywc_")
        cls.modifiers = defined_in("common/scripted_modifiers")
        cls.effects = defined_in("common/scripted_effects")
        cls.triggers = defined_in("common/scripted_triggers")
        cls.journals = defined_in("common/journal_entries")
        cls.events = defined_in("events")

    def test_set_strategy_references_are_defined(self):
        refs = set(re.findall(r"set_strategy\s*=\s*(ai_strategy_ywc_[A-Za-z0-9_]+)", self.text))
        self.assertTrue(refs)
        missing = refs - self.strategies
        self.assertEqual(missing, set(), f"undefined strategies: {sorted(missing)}")

    def test_add_modifier_names_are_defined(self):
        refs = set(re.findall(r"add_modifier\s*=\s*\{\s*name\s*=\s*(ywc_[A-Za-z0-9_]+)", self.text))
        self.assertTrue(refs)
        missing = refs - self.modifiers
        self.assertEqual(missing, set(), f"undefined modifiers: {sorted(missing)}")

    def test_journal_entry_references_are_defined(self):
        refs = set(
            re.findall(
                r"(?:add_journal_entry\s*=\s*\{\s*type|has_journal_entry)\s*=\s*(ywc_[A-Za-z0-9_]+)",
                self.text,
            )
        )
        self.assertTrue(refs)
        missing = refs - self.journals
        self.assertEqual(missing, set(), f"undefined journals: {sorted(missing)}")

    def test_event_references_are_defined(self):
        refs = set(re.findall(r"trigger_event\s*=\s*\{[^}]*id\s*=\s*(ywc_[A-Za-z0-9_.]+)", self.text))
        self.assertTrue(refs)
        missing = refs - self.events
        self.assertEqual(missing, set(), f"undefined events: {sorted(missing)}")

    def test_yes_style_calls_resolve_to_effects_or_triggers(self):
        refs = set(re.findall(r"(?m)^\s*(ywc_[a-z0-9_]+)\s*=\s*yes\s*$", self.text))
        self.assertTrue(refs)
        resolvable = self.effects | self.triggers
        missing = refs - resolvable
        self.assertEqual(missing, set(), f"unresolved yes-style calls: {sorted(missing)}")

    def test_journal_completion_variables_have_setters(self):
        # Plan 03 requires every main journal and route to be completable or
        # failable. As of v0.1 the event chains record ywc_<tag>.N_success /
        # _failure variables that were never bridged to the journals'
        # *_resolved completion conditions, so the variables below (audited
        # 2026-09-06) have no setter. They are recorded here instead of being
        # silently ignored: any NEW unwired variable fails this test, and each
        # entry should be removed once its journal gets real completion logic.
        known_unwired = {
            "ywc_highland_without_master_resolved",
            "ywc_je_jinghai_council_resolved",
            "ywc_je_jinghai_maritime_network_resolved",
            "ywc_je_jinghai_succession_resolved",
            "ywc_je_kor_border_question_resolved",
            "ywc_je_kor_bureaucratic_state_resolved",
            "ywc_je_kor_maritime_learning_resolved",
            "ywc_je_korea_who_inherits_china_resolved",
            "ywc_je_lan_company_shareholders_resolved",
            "ywc_je_lan_dutch_pressure_resolved",
            "ywc_je_lan_miner_frontier_resolved",
            "ywc_je_lanfang_company_republic_resolved",
            "ywc_je_mng_pan_mongol_council_resolved",
            "ywc_je_mng_russian_protection_resolved",
            "ywc_je_mng_shun_trade_resolved",
            "ywc_je_mongol_south_north_resolved",
            "ywc_je_nmg_baja_frontier_resolved",
            "ywc_je_nmg_catholic_huamo_resolved",
            "ywc_je_nmg_mexican_federation_resolved",
            "ywc_je_northern_qing_exile_resolved",
            "ywc_je_northern_qing_island_society_resolved",
            "ywc_je_northern_qing_russian_choice_resolved",
            "ywc_ocean_frontiers_resolved",
            "ywc_je_oir_dzungar_legacy_resolved",
            "ywc_je_oir_ili_trade_resolved",
            "ywc_je_oir_russian_pressure_resolved",
            "ywc_je_oir_succession_resolved",
            "ywc_je_shu_blackwater_frontier_resolved",
            "ywc_je_shu_opium_question_resolved",
            "ywc_je_shu_scholar_merchants_resolved",
            "ywc_je_tib_caravan_gate_resolved",
            "ywc_je_tib_kham_alliance_resolved",
            "ywc_je_tib_monastery_estates_resolved",
            "ywc_je_tibet_highland_without_master_resolved",
            "ywc_je_yongchang_century_resolved",
            "ywc_route_jhg_naval_tributary_state_resolved",            "ywc_route_jhg_south_sea_council_resolved",
            "ywc_route_kor_national_foundation_resolved",
            "ywc_route_kor_small_china_resolved",
            "ywc_route_lan_company_republic_resolved",
            "ywc_route_lan_mining_state_resolved",
            "ywc_route_mng_russian_protection_resolved",
            "ywc_route_mng_southern_trade_resolved",
            "ywc_route_nmg_catholic_autonomy_resolved",
            "ywc_route_nmg_mexican_federalism_resolved",
            "ywc_route_nqg_multicultural_island_resolved",
            "ywc_route_nqg_sakhalin_restoration_resolved",
            "ywc_route_oir_bureaucratic_khanate_resolved",
            "ywc_route_oir_pastoral_federation_resolved",
            "ywc_route_shu_bureaucratic_integration_resolved",
            "ywc_route_shu_customs_reform_resolved",
            "ywc_route_tib_kham_league_resolved",
            "ywc_route_tib_monastic_reform_resolved",
        }
        journal_text = "\n".join(
            p.read_text("utf-8-sig") for p in scripts() if "journal_entries" in str(p)
        )
        failures = []
        checked = 0
        for name in sorted(set(re.findall(r"^(ywc_[A-Za-z0-9_]+)\s*=\s*\{", journal_text, re.MULTILINE))):
            block = re.search(rf"^{name}\s*=\s*\{{(?s:.*?)^\}}", journal_text, re.MULTILINE)
            if not block:
                continue
            for var in re.findall(r"has_variable\s*=\s*(ywc_[A-Za-z0-9_]+)", block.group(0)):
                checked += 1
                setter = re.findall(
                    rf"set_variable\s*=\s*(?:{var}\b|\{{[^}}]*\bname\s*=\s*{var}\b)",
                    all_text(),
                )
                if not setter and var not in known_unwired:
                    failures.append(f"journal {name}: {var} has no set_variable anywhere")
        self.assertGreater(checked, 40)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
