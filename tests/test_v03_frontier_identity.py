import json
import pathlib
import re
import unittest

from tools.build_frontier_polity_content import (
    LEGACY_IDS,
    REGISTRY,
    outputs,
)


ROOT = pathlib.Path(__file__).parents[1]
ROOT_OUTPUTS = {path.as_posix().split("yongchang_world/", 1)[-1]: value for path, value in outputs().items()}
ZH_FLAVOR = ROOT_OUTPUTS["localization/simp_chinese/replace/ywc_frontier_country_flavor_l_simp_chinese.yml"]
EN_FLAVOR = ROOT_OUTPUTS["localization/english/replace/ywc_frontier_country_flavor_l_english.yml"]
EVENTS = ROOT_OUTPUTS["events/ywc_frontier_starts.txt"]


def flavor_line(content, tag):
    match = re.search(rf'(?m)^\s*{tag}_FLAVOR_TEXT:0 "([^"]+)"$', content)
    if not match:
        raise AssertionError(f"missing generated flavor for {tag}")
    return match.group(1)


class FrontierIdentityTest(unittest.TestCase):
    def test_generated_identity_matches_registry_and_current_history(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        countries = {row["tag"]: row for row in registry["countries"]}
        expected_names = {
            "HSR": "希萨尔伯克国",
            "DRZ": "达尔瓦兹沙国",
            "BKY": "布克依汗国",
            "LXJ": "木里王国",
            "CHI": "大清",
        }
        for tag, expected_name in expected_names.items():
            self.assertEqual(expected_name, countries[tag]["name_zh"])
            self.assertIn(f"{tag}_FLAVOR_TEXT:0", ZH_FLAVOR)
        states = ("STATE_UZBEKIA", "STATE_TAJIKISTAN", "STATE_URALSK", "STATE_ASTRAKHAN", "STATE_YUNNAN", "STATE_TRANS_BAIKAL")
        state_history = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
        self.assertIn("country = c:HSR", state_history)
        self.assertIn("country = c:DRZ", state_history)
        self.assertIn("country = c:BKY", state_history)
        self.assertIn("country = c:LXJ", state_history)
        self.assertIn("country = c:CHI", state_history)
        state_blocks = re.split(r"(?m)(?=^s:STATE_)", state_history)
        owners = {}
        for block in state_blocks:
            state_match = re.match(r"s:(STATE_[A-Z_]+)\s*=\s*\{", block)
            if state_match:
                owners[state_match.group(1)] = {
                    tag for tag in ("CHI", "NQG") if re.search(rf"country = c:{tag}\b", block)
                }
        self.assertEqual(
            {"STATE_NORTHERN_MANCHURIA", "STATE_YAKUTSK", "STATE_TRANS_BAIKAL", "STATE_IRKUTSK", "STATE_BURYATIA", "STATE_AMUR"},
            {state for state, tags in owners.items() if "CHI" in tags},
        )
        self.assertEqual({"STATE_SAKHALIN"}, {state for state, tags in owners.items() if "NQG" in tags})
        chi_history = (ROOT / "yongchang_world/common/history/countries/chi - china.txt").read_text(encoding="utf-8-sig")
        self.assertIn("set_capital = STATE_TRANS_BAIKAL", chi_history)
        corrections = json.loads((ROOT / "data/scenario/geographic_corrections.json").read_text(encoding="utf-8-sig"))
        owner_states = {tag: set() for tag in expected_names}
        for change in corrections["changes"]:
            for group in change.get("groups", []):
                if group["owner"] in owner_states:
                    owner_states[group["owner"]].add(change["state"])
        self.assertEqual({"STATE_TAJIKISTAN"}, owner_states["HSR"])
        self.assertEqual({"STATE_TAJIKISTAN"}, owner_states["DRZ"])
        self.assertEqual({"STATE_URALSK", "STATE_ASTRAKHAN"}, owner_states["BKY"])
        self.assertEqual({"STATE_YUNNAN"}, owner_states["LXJ"])
        expected_english = {
            "HSR": "Hisar Begdom",
            "DRZ": "Darvaz Shahdom",
            "BKY": "Bukey Horde",
            "LXJ": "Muli Kingdom",
            "CHI": "Great Qing",
        }
        en_starts = ROOT_OUTPUTS["localization/english/ywc_frontier_starts_l_english.yml"]
        zh_starts = ROOT_OUTPUTS["localization/simp_chinese/ywc_frontier_starts_l_simp_chinese.yml"]
        frozen_ids = json.loads(LEGACY_IDS.read_text(encoding="utf-8"))["frontier_event_ids"]
        for tag, country_name in expected_english.items():
            event_id = frozen_ids[tag][0]
            self.assertIn(f'{event_id}.t:0 "{country_name}: The Local Compact"', en_starts)
            self.assertIn(f'{event_id}.t:0 "{expected_names[tag]}：地方約章"', zh_starts)
        for state in states:
            self.assertIn(state, chi_history if state == "STATE_TRANS_BAIKAL" else state_history)

    def test_generated_geographic_hooks_use_each_politys_actual_region(self):
        zh = {tag: flavor_line(ZH_FLAVOR, tag) for tag in ("HSR", "DRZ", "BKY", "LXJ", "CHI")}
        en = {tag: flavor_line(EN_FLAVOR, tag) for tag in zh}
        self.assertIn("中亚", zh["HSR"])
        self.assertIn("河谷", zh["HSR"])
        self.assertIn("灌", zh["HSR"])
        self.assertIn("Central Asian", en["HSR"])
        self.assertIn("irrigation", en["HSR"])
        for text in (zh["HSR"], en["HSR"]):
            for wrong in ("河湟", "回部", "Hehuang", "Hui towns"):
                self.assertNotIn(wrong, text)

        self.assertIn("山地河谷", zh["DRZ"])
        self.assertIn("中亚商队", zh["DRZ"])
        self.assertIn("通往中亚集市的商路", zh["DRZ"])
        self.assertIn("mountain valleys", en["DRZ"])
        self.assertIn("Central Asian caravans", en["DRZ"])
        self.assertIn("Central Asian markets", en["DRZ"])
        for text in (zh["DRZ"], en["DRZ"]):
            for wrong in ("德令哈", "柴达木", "Delingha", "Qaidam"):
                self.assertNotIn(wrong, text)

        self.assertIn("里海", zh["BKY"])
        self.assertIn("布克依汗国", zh["BKY"])
        self.assertNotIn("布凯汗国", zh["BKY"])
        self.assertIn("乌拉尔", zh["BKY"])
        self.assertIn("季节迁牧", zh["BKY"])
        self.assertIn("Caspian", en["BKY"])
        self.assertIn("Ural", en["BKY"])
        self.assertIn("seasonal", en["BKY"])
        for text in (zh["BKY"], en["BKY"]):
            for wrong in ("巴里坤", "清廷", "Barkul", "Qing offices"):
                self.assertNotIn(wrong, text)

        self.assertIn("木里", zh["LXJ"])
        self.assertIn("寺院", zh["LXJ"])
        self.assertIn("道路", zh["LXJ"])
        self.assertIn("Muli", en["LXJ"])
        self.assertIn("monasteries", en["LXJ"])
        for text in (zh["LXJ"], en["LXJ"]):
            for wrong in ("丽江木府", "Lijiang's Mu house"):
                self.assertNotIn(wrong, text)

        self.assertIn("外贝加尔", zh["CHI"])
        self.assertIn("残廷", zh["CHI"])
        self.assertIn("Trans-Baikal", en["CHI"])
        self.assertIn("residual court", en["CHI"])
        self.assertIn("复国并非必然", zh["CHI"])
        self.assertIn("restoration is not inevitable", en["CHI"])

    def test_related_starts_remain_distinct_in_both_languages(self):
        self.assertNotEqual(flavor_line(ZH_FLAVOR, "LXJ"), flavor_line(ZH_FLAVOR, "LJG"))
        self.assertNotEqual(flavor_line(EN_FLAVOR, "LXJ"), flavor_line(EN_FLAVOR, "LJG"))
        self.assertIn("库页", flavor_line(ZH_FLAVOR, "NQG"))
        self.assertIn("外贝加尔", flavor_line(ZH_FLAVOR, "CHI"))
        self.assertNotEqual(flavor_line(ZH_FLAVOR, "CHI"), flavor_line(ZH_FLAVOR, "NQG"))
        self.assertNotEqual(flavor_line(EN_FLAVOR, "CHI"), flavor_line(EN_FLAVOR, "NQG"))

    def test_identity_corrections_preserve_frozen_frontier_event_ids(self):
        frozen = json.loads(LEGACY_IDS.read_text(encoding="utf-8"))["frontier_event_ids"]
        for tag in ("HSR", "DRZ", "BKY", "LXJ", "CHI"):
            self.assertEqual(3, len(frozen[tag]), tag)
            self.assertEqual(3, len(set(frozen[tag])), tag)
            for event_id in frozen[tag]:
                self.assertRegex(EVENTS, rf"(?m)^{re.escape(event_id)} = \{{", tag)
        all_ids = re.findall(r"(?m)^(ywc_frontier\.\d+) = \{", EVENTS)
        self.assertEqual(168, len(all_ids))
        self.assertEqual(168, len(set(all_ids)))


if __name__ == "__main__":
    unittest.main()
