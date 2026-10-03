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

    def test_vanilla_qing_never_survives_on_the_map(self):
        # 1644: the Qing court never entered the pass; by 1715 it is a Sakhalin
        # exile (NQG). The vanilla China tag must not own a single province.
        for state, tags in self.owners.items():
            self.assertNotIn("CHI", tags, f"vanilla Qing still owns {state}")

    def test_every_mod_country_state_has_pops(self):
        # Reassigning a state without authoring pops silently deletes millions
        # of people (SHU showed 17.3M instead of ~350M).
        for state, tags in self.owners.items():
            for tag in tags:
                if tag in self.registry_tags:
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
