"""Scenario integrity locks for the bugs surfaced by the first real look at
the 1836 lobby (2026-09-26): a leftover vanilla-Qing ledger, missing pops on
reassigned states, invented state names in pops files, countries without
flags, and a tag collision (ARA = vanilla Arabia)."""

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).parents[1]
GAME = pathlib.Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
POPS_DIR = ROOT / "yongchang_world/common/history/pops"
REGISTRY = ROOT / "data/scenario/tag_registry.json"
FLAG_DIR = ROOT / "yongchang_world/common/flag_definitions"


def ledger_owners():
    text = LEDGER.read_text(encoding="utf-8-sig")
    owners = {}
    for match in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text):
        state = match.group(1)
        nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", text[match.end():])
        end = match.end() + (nxt.start() if nxt else len(text) - match.end())
        block = text[match.start():end]
        for tag in re.findall(r"country = c:([A-Z]{3})", block):
            owners.setdefault(state, set()).add(tag)
    return owners


class ScenarioIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owners = ledger_owners()
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        cls.registry_tags = {row["tag"] for row in cls.registry["countries"]}
        cls.new_tags = {row["tag"] for row in cls.registry["countries"] if row.get("mode") == "new"}
        cls.pop_targets = set()
        cls.pop_states = set()
        for path in POPS_DIR.glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            cls.pop_states |= set(re.findall(r"s:(STATE_[A-Z0-9_]+)", text))
            for match in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text):
                state = match.group(1)
                nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", text[match.end():])
                end = match.end() + (nxt.start() if nxt else len(text) - match.end())
                cls.pop_targets |= {
                    (state, tag) for tag in re.findall(r"region_state:([A-Z]{3})", text[match.start():end])
                }

    def test_qing_holds_trans_baikal_and_exact_frontier_buffer(self):
        qing_states = {state for state, tags in self.owners.items() if "CHI" in tags}
        self.assertEqual(
            qing_states,
            {
                "STATE_TRANS_BAIKAL", "STATE_AMUR", "STATE_NORTHERN_MANCHURIA",
                "STATE_YAKUTSK", "STATE_IRKUTSK", "STATE_BURYATIA",
            },
        )

        baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
        ledger = LEDGER.read_text(encoding="utf-8-sig")
        qing_provinces = set()
        state_matches = list(re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", ledger))
        for index, state_match in enumerate(state_matches):
            state_end = state_matches[index + 1].start() if index + 1 < len(state_matches) else len(ledger)
            state_block = ledger[state_match.start():state_end]
            groups = list(re.finditer(r"(?m)^\s*create_state\s*=\s*\{", state_block))
            for group_index, group_match in enumerate(groups):
                group_end = groups[group_index + 1].start() if group_index + 1 < len(groups) else len(state_block)
                group_block = state_block[group_match.start():group_end]
                if re.search(r"\bcountry\s*=\s*c:CHI\b", group_block):
                    owned = re.search(r"owned_provinces\s*=\s*\{([^}]*)\}", group_block, re.S)
                    if owned:
                        qing_provinces.update(re.findall(r"\b(x[0-9A-F]{6})\b", owned.group(1)))
        trans_baikal = set(baseline["state_regions"]["STATE_TRANS_BAIKAL"])
        self.assertEqual(qing_provinces & trans_baikal, trans_baikal)

        expected_frontier_buffer = {
            "STATE_AMUR": {
                "x48F0E7", "x447043", "x87B611", "xD72514", "x532B1B", "x1DEDA0",
            },
            "STATE_NORTHERN_MANCHURIA": {
                "x975775", "x4F6B8F", "xD3B4B5",
            },
        }
        for state, expected in expected_frontier_buffer.items():
            self.assertEqual(
                qing_provinces & set(baseline["state_regions"][state]),
                expected,
                f"unexpected Qing frontier provinces in {state}",
            )

    def test_every_mod_country_state_has_pops(self):
        # Reassigning a state without authoring pops silently deletes millions
        # of people (SHU showed 17.3M instead of ~350M).
        for state, tags in self.owners.items():
            for tag in tags:
                if tag in self.new_tags or (state in {
                    "STATE_AKTOBE", "STATE_AKMOLINSK", "STATE_KIRGHIZIA",
                    "STATE_JETISY", "STATE_SEMIRECHE",
                } and tag in {"KZH", "OZH", "UZH"}):
                    self.assertIn(
                        (state, tag), self.pop_targets,
                        f"{state}: region_state:{tag} has no pops in the mod's pops files",
                    )

    def test_pops_reference_real_states(self):
        baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
        for state in self.pop_states:
            self.assertIn(state, baseline["state_regions"], f"invented state name {state}")

    def test_every_new_tag_has_a_flag_definition(self):
        flag_text = "\n".join(path.read_text(encoding="utf-8-sig") for path in FLAG_DIR.glob("*.txt"))
        for tag in self.new_tags:
            self.assertIn(f"{tag} = {{", flag_text, f"{tag} has no flag definition (renders as the default tricolor)")

    def test_registry_tags_do_not_collide_with_new_tag_claims(self):
        baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
        vanilla_tags = set(baseline["country_tags"])
        for row in self.registry["countries"]:
            if row.get("mode") == "new":
                self.assertNotIn(
                    row["tag"], vanilla_tags,
                    f"{row['tag']} claims to be a new tag but vanilla already defines it",
                )


if __name__ == "__main__":
    unittest.main()
