import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
EVENTS = ROOT / "yongchang_world/events/ywc_dmg_nqg_events.txt"
STEPPE_EVENTS = ROOT / "yongchang_world/events/ywc_steppe_highland_events.txt"
OVERSEAS_EVENTS = ROOT / "yongchang_world/events/ywc_kor_lan_nmg_events.txt"
DMG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_dmg.txt"
NQG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_nqg.txt"
OIR_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_oir.txt"
MNG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_mng.txt"
TIB_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_tib.txt"
KOR_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_kor.txt"
LAN_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_lan.txt"
NMG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_nmg.txt"


def block_for(text: str, key: str) -> str:
    start = text.index(f"{key} = {{")
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {key}")


class RegionalRouteContractTest(unittest.TestCase):
    def setUp(self):
        self.events = EVENTS.read_text("utf-8")
        self.steppe_events = STEPPE_EVENTS.read_text("utf-8")
        self.overseas_events = OVERSEAS_EVENTS.read_text("utf-8")
        self.dmg_journal = DMG_JOURNAL.read_text("utf-8")
        self.nqg_journal = NQG_JOURNAL.read_text("utf-8")
        self.oir_journal = OIR_JOURNAL.read_text("utf-8")
        self.mng_journal = MNG_JOURNAL.read_text("utf-8")
        self.tib_journal = TIB_JOURNAL.read_text("utf-8")
        self.kor_journal = KOR_JOURNAL.read_text("utf-8")
        self.lan_journal = LAN_JOURNAL.read_text("utf-8")
        self.nmg_journal = NMG_JOURNAL.read_text("utf-8")

    def test_dmg_and_nqg_routes_are_progress_gated(self):
        specs = (
            (
                "ywc_route_dmg_huafei_monarchy",
                "ywc_route_dmg_huafei_monarchy_progress",
                "ywc_dmg.4",
                "ywc_route_dmg_local_republic_active",
                self.dmg_journal,
                "ywc_add_heritage_legitimacy",
            ),
            (
                "ywc_route_dmg_local_republic",
                "ywc_route_dmg_local_republic_progress",
                "ywc_dmg.5",
                "ywc_route_dmg_huafei_monarchy_active",
                self.dmg_journal,
                "ywc_open_trade_route",
            ),
            (
                "ywc_route_nqg_sakhalin_restoration",
                "ywc_route_nqg_sakhalin_restoration_progress",
                "ywc_nqg.4",
                "ywc_route_nqg_multicultural_island_active",
                self.nqg_journal,
                "ywc_add_heritage_legitimacy",
            ),
            (
                "ywc_route_nqg_multicultural_island",
                "ywc_route_nqg_multicultural_island_progress",
                "ywc_nqg.5",
                "ywc_route_nqg_sakhalin_restoration_active",
                self.nqg_journal,
                "ywc_add_maritime_network",
            ),
        )
        for route, progress, event_id, rival, journal_text, shared_effect in specs:
            journal = block_for(journal_text, route)
            event = block_for(self.events, event_id)
            self.assertIn(f"var:{progress} >= 100", journal)
            self.assertIn(f"var:{progress} >= 100", event)
            self.assertIn(f"NOT = {{ has_variable = {rival} }}", event)
            self.assertIn(shared_effect, event)
            self.assertIn("change_variable", event)
            self.assertIn("add_modifier", event)
            self.assertGreaterEqual(event.count("remove_variable"), 2)
            self.assertEqual(event.count("ai_chance = {"), 3)

    def test_route_events_do_not_directly_complete_on_first_option(self):
        for event_id, success in (
            ("ywc_dmg.4", "ywc_route_dmg_huafei_monarchy_success"),
            ("ywc_dmg.5", "ywc_route_dmg_local_republic_success"),
            ("ywc_nqg.4", "ywc_route_nqg_sakhalin_restoration_success"),
            ("ywc_nqg.5", "ywc_route_nqg_multicultural_island_success"),
        ):
            event = block_for(self.events, event_id)
            self.assertNotRegex(
                event,
                rf"option = \{{\s*name = [^}}]+\s+default_option = yes\s+set_variable = \{{ name = {success}",
            )

    def test_oir_mng_tib_routes_use_the_same_contract(self):
        specs = (
            ("ywc_route_oir_bureaucratic_khanate", "ywc_route_oir_bureaucratic_khanate_progress", "ywc_oir.5", "ywc_route_oir_pastoral_federation_active", self.oir_journal, "ywc_add_heritage_legitimacy"),
            ("ywc_route_oir_pastoral_federation", "ywc_route_oir_pastoral_federation_progress", "ywc_oir.6", "ywc_route_oir_bureaucratic_khanate_active", self.oir_journal, "ywc_raise_autonomy_pressure"),
            ("ywc_route_mng_southern_trade", "ywc_route_mng_southern_trade_progress", "ywc_mng.5", "ywc_route_mng_russian_protection_active", self.mng_journal, "ywc_open_trade_route"),
            ("ywc_route_mng_russian_protection", "ywc_route_mng_russian_protection_progress", "ywc_mng.6", "ywc_route_mng_southern_trade_active", self.mng_journal, "ywc_raise_autonomy_pressure"),
            ("ywc_route_tib_monastic_reform", "ywc_route_tib_monastic_reform_progress", "ywc_tib.5", "ywc_route_tib_kham_league_active", self.tib_journal, "ywc_add_heritage_legitimacy"),
            ("ywc_route_tib_kham_league", "ywc_route_tib_kham_league_progress", "ywc_tib.6", "ywc_route_tib_monastic_reform_active", self.tib_journal, "ywc_open_trade_route"),
        )
        for route, progress, event_id, rival, journal_text, shared_effect in specs:
            journal = block_for(journal_text, route)
            event = block_for(self.steppe_events, event_id)
            self.assertIn(f"var:{progress} >= 100", journal)
            self.assertIn(f"var:{progress} >= 100", event)
            self.assertIn(f"NOT = {{ has_variable = {rival} }}", event)
            self.assertIn(shared_effect, event)
            self.assertIn("change_variable", event)
            self.assertIn("add_modifier", event)
            self.assertGreaterEqual(event.count("remove_variable"), 2)
            self.assertEqual(event.count("ai_chance = {"), 3)

    def test_kor_lan_nmg_routes_use_distinct_overseas_contracts(self):
        specs = (
            ("ywc_route_kor_small_china", "ywc_route_kor_small_china_progress", "ywc_kor.5", "ywc_route_kor_national_foundation_active", self.kor_journal, "ywc_add_heritage_legitimacy"),
            ("ywc_route_kor_national_foundation", "ywc_route_kor_national_foundation_progress", "ywc_kor.6", "ywc_route_kor_small_china_active", self.kor_journal, "ywc_open_trade_route"),
            ("ywc_route_lan_company_republic", "ywc_route_lan_company_republic_progress", "ywc_lan.5", "ywc_route_lan_mining_state_active", self.lan_journal, "ywc_open_trade_route"),
            ("ywc_route_lan_mining_state", "ywc_route_lan_mining_state_progress", "ywc_lan.6", "ywc_route_lan_company_republic_active", self.lan_journal, "ywc_add_heritage_legitimacy"),
            ("ywc_route_nmg_catholic_autonomy", "ywc_route_nmg_catholic_autonomy_progress", "ywc_nmg.4", "ywc_route_nmg_mexican_federalism_active", self.nmg_journal, "ywc_raise_autonomy_pressure"),
            ("ywc_route_nmg_mexican_federalism", "ywc_route_nmg_mexican_federalism_progress", "ywc_nmg.5", "ywc_route_nmg_catholic_autonomy_active", self.nmg_journal, "ywc_open_trade_route"),
        )
        for route, progress, event_id, rival, journal_text, shared_effect in specs:
            journal = block_for(journal_text, route)
            event = block_for(self.overseas_events, event_id)
            self.assertIn(f"var:{progress} >= 100", journal)
            self.assertIn(f"var:{progress} >= 100", event)
            self.assertIn(f"NOT = {{ has_variable = {rival} }}", event)
            self.assertIn(shared_effect, event)
            self.assertIn("change_variable", event)
            self.assertIn("add_modifier", event)
            self.assertGreaterEqual(event.count("remove_variable"), 2)
            self.assertEqual(event.count("ai_chance = {"), 3)


if __name__ == "__main__":
    unittest.main()
