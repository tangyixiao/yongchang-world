import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
EVENTS = ROOT / "yongchang_world/events/ywc_dmg_nqg_events.txt"
DMG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_dmg.txt"
NQG_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_nqg.txt"


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
        self.dmg_journal = DMG_JOURNAL.read_text("utf-8")
        self.nqg_journal = NQG_JOURNAL.read_text("utf-8")

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


if __name__ == "__main__":
    unittest.main()
