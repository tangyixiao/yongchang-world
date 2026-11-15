import json
import pathlib
import re
import tempfile
import unittest

from tools.build_frontier_polity_content import COUNTRY_CONTEXT, MOD, OWNED, live_start_tags, outputs, write_generated_output
from clausewitz_harness import parse


ROOT = pathlib.Path(__file__).parents[1]


class FrontierPolityContentTest(unittest.TestCase):
    def setUp(self):
        self.generated = outputs()
        self.files = {path.relative_to(ROOT).as_posix(): content for path, content in self.generated.items()}

    def test_every_uncovered_registry_tag_has_a_journal_and_ai_strategy(self):
        registry = json.loads((ROOT / "data/scenario/tag_registry.json").read_text(encoding="utf-8-sig"))
        tags = (set(row["tag"] for row in registry["countries"]) & live_start_tags()) - OWNED
        journals = self.files["yongchang_world/common/journal_entries/ywc_frontier_starts.txt"]
        startup = self.files["yongchang_world/common/on_actions/ywc_frontier_startup.txt"]
        strategies = self.files["yongchang_world/common/ai_strategies/ywc_frontier_country_ai.txt"]
        for tag in tags:
            self.assertIn(f"ywc_je_frontier_{tag.lower()} = {{", journals, tag)
            self.assertIn(f"is_shown_in_lobby = {{ c:{tag} ?= THIS }}", journals, tag)
            self.assertNotIn(f"is_shown_in_lobby = {{ c:{tag} = THIS }}", journals, tag)
            self.assertIn(f"type = ywc_je_frontier_{tag.lower()}", startup, tag)
            self.assertIn(f"ai_strategy_ywc_{tag.lower()} = {{", strategies, tag)
            self.assertIn(f"set_strategy = ai_strategy_ywc_{tag.lower()}", startup, tag)
        self.assertNotIn("MNG", tags)  # logical registry entry reuses live vanilla MGL, not Brazilian MNG
        self.assertNotIn("SIK", tags)  # registered but not an active mod country start
        self.assertTrue(tags <= set(COUNTRY_CONTEXT), sorted(tags - set(COUNTRY_CONTEXT)))

    def test_frontier_events_are_unique_reachable_and_bilingual(self):
        events = self.files["yongchang_world/events/ywc_frontier_starts.txt"]
        ids = re.findall(r"(?m)^(ywc_frontier\.\d+) = \{", events)
        self.assertEqual(len(ids), 168)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(events.count("default_option = yes"), len(ids))
        en = self.files["yongchang_world/localization/english/ywc_frontier_starts_l_english.yml"]
        zh = self.files["yongchang_world/localization/simp_chinese/ywc_frontier_starts_l_simp_chinese.yml"]
        en_keys = set(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_.]*):0", en))
        zh_keys = set(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_.]*):0", zh))
        self.assertEqual(en_keys, zh_keys)
        for event_id in ids:
            self.assertIn(f"{event_id}.t:0", en)
            self.assertIn(f"{event_id}.t:0", zh)
            self.assertRegex(events, rf"(?s){re.escape(event_id)} = \{{.*?event_image = \{{ video = \"[a-z0-9_]+\" \}}")

    def test_frontier_chain_only_writes_the_pulse_guard_marker(self):
        events = self.files["yongchang_world/events/ywc_frontier_starts.txt"]
        self.assertRegex(events, r"set_variable = \{ name = ywc_frontier_[a-z0-9]+_stage1 value = 1 \}")
        self.assertNotRegex(events, r"set_variable = \{ name = ywc_frontier_[a-z0-9]+_stage[23]\b")
        self.assertNotRegex(events, r"has_variable = ywc_frontier_[a-z0-9]+_stage[23]\b")

    def test_route_start_events_have_safe_cooldown_fallbacks_and_images(self):
        event_ids = [f"ywc_{tag}.{stage}" for tag in "shu jhg dmg nqg oir mng tib kor lan nmg".split() for stage in (4, 5)]
        for event_id in event_ids:
            found = False
            for path in (MOD / "events").glob("ywc_*_events.txt"):
                text = path.read_text(encoding="utf-8-sig")
                match = re.search(rf"(?m)^{re.escape(event_id)} = \{{", text)
                if not match:
                    continue
                found = True
                depth = 0
                end = None
                for index in range(match.end() - 1, len(text)):
                    depth += (text[index] == "{") - (text[index] == "}")
                    if depth == 0:
                        end = index + 1
                        break
                block = text[match.start():end]
                self.assertIn("fallback = yes", block, event_id)
                self.assertIn("default_option = yes", block, event_id)
                self.assertRegex(block, r"set_variable = \{ name = ywc_route_[a-z0-9_]+_abandonment_cooldown days = 90 \}", event_id)
                self.assertRegex(block, r"event_image = \{ video = \"[a-z0-9_]+\" \}", event_id)
            self.assertTrue(found, event_id)

    def test_country_selection_copy_covers_registry_and_runtime_aliases(self):
        registry = json.loads((ROOT / "data/scenario/tag_registry.json").read_text(encoding="utf-8-sig"))
        tags = ({row["tag"] for row in registry["countries"]} & live_start_tags()) | {"MGL", "DAI"}
        for language in ("english", "simp_chinese"):
            path = f"yongchang_world/localization/{language}/replace/ywc_frontier_country_flavor_l_{language}.yml"
            content = self.files[path]
            found = set(re.findall(r"(?m)^\s*([A-Z]{3})_FLAVOR_TEXT:0", content))
            self.assertTrue(tags <= found, sorted(tags - found))
            self.assertNotIn("MNG", found)  # MNG is Brazilian Minas Gerais; the logical Mongol start is MGL.
            self.assertIn("MGL", found)

    def test_every_visible_country_event_has_a_vanilla_event_image(self):
        checked = 0
        for path in (MOD / "events").rglob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r"(?m)^(ywc_[\w.]+) = \{", text):
                depth = 0
                quoted = escaped = False
                end = None
                for index in range(match.end() - 1, len(text)):
                    char = text[index]
                    if quoted:
                        if escaped:
                            escaped = False
                        elif char == "\\":
                            escaped = True
                        elif char == '"':
                            quoted = False
                    elif char == '"':
                        quoted = True
                    elif char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            end = index + 1
                            break
                block = text[match.end() - 1:end]
                properties = {key: value for key, _, value in parse(block[1:-1])}
                # Hidden contract endpoints have no event window. Requiring
                # artwork there would confuse background protocol with UI.
                if properties.get("type") == "country_event" and properties.get("hidden") != "yes":
                    checked += 1
                    self.assertRegex(block, r"event_image = \{ video = \"[a-z0-9_]+\" \}", match.group(1))
        self.assertGreater(checked, 0)

    def test_route_fallback_buttons_have_bilingual_localization(self):
        for language, suffix in (("english", "l_english"), ("simp_chinese", "l_simp_chinese")):
            content = (MOD / "localization" / language / f"ywc_content_{suffix}.yml").read_text(encoding="utf-8-sig")
            for tag in "shu jhg dmg nqg oir mng tib kor lan nmg".split():
                for stage in (4, 5):
                    self.assertRegex(content, rf"(?m)^\s*ywc_{tag}\.{stage}\.e:0 \"[^\"]+\"$")

    def test_generated_writer_emits_engine_required_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "sample.yml"
            write_generated_output(path, "l_english:\n test_key:0 \"value\"\n")
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
