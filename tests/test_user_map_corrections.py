import json
import pathlib
import re
import unittest

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - installed game validation has these.
    np = None
    Image = None

from tools.ownership_topology import _state_adjacency, component_sizes


ROOT = pathlib.Path(__file__).parents[1]
GAME = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game")
BASELINE = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text("utf-8"))
OVERRIDES = json.loads((ROOT / "data/scenario/ownership_overrides.json").read_text("utf-8"))
AUTHORITY = {row["state"]: row["groups"] for row in OVERRIDES["states"]}


def balanced_block(text, marker):
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {marker}")


def owner_groups(state):
    return {
        group["owner"]: set(group["owned_provinces"])
        for group in AUTHORITY.get(state, [])
    }


class UserMapCorrectionTest(unittest.TestCase):
    def test_original_zhuz_frontier_is_preserved(self):
        for state in ("STATE_SEMIRECHE", "STATE_AKMOLINSK", "STATE_SYRDARYA", "STATE_AKTOBE"):
            for group in BASELINE["states"][state]:
                if group["country"] in {"KZH", "OZH", "UZH"}:
                    parts={"KZH":["KZH","BYL","JTR"],"OZH":["OZH","NMN","KER"],"UZH":["UZH","ZHL","ABN"]}[group["country"]]
                    actual=set().union(*(owner_groups(state).get(tag,set()) for tag in parts))
                    self.assertTrue(set(group["owned_provinces"]) <= actual, state)
        self.assertIn("UZH", owner_groups("STATE_JETISY"))
        self.assertNotIn("UZH", owner_groups("STATE_KIRGHIZIA"))
        self.assertTrue(owner_groups("STATE_TOMSK")["NMN"])
        self.assertTrue(owner_groups("STATE_URALSK")["BKY"])

    def test_indian_princely_state_territory_is_preserved(self):
        history = "\n".join(path.read_text("utf-8-sig") for path in (ROOT / "yongchang_world/common/history/countries").glob("*.txt"))
        for tag in ("ASM", "MNP", "KAS", "CHT"):
            self.assertNotRegex(history, rf"c:{tag}\s*\??=\s*\{{")
        expected_assam = {g["country"]: set(g["owned_provinces"]) for g in BASELINE["states"]["STATE_ASSAM"]}
        self.assertEqual(owner_groups("STATE_ASSAM"), expected_assam)
        for directory in ("pops", "buildings"):
            vanilla = (GAME / f"common/history/{directory}/10_india.txt").read_text("utf-8-sig")
            mod = (ROOT / f"yongchang_world/common/history/{directory}/10_india.txt").read_text("utf-8-sig")
            self.assertEqual(balanced_block(mod, "s:STATE_ASSAM"), balanced_block(vanilla, "s:STATE_ASSAM"))
        protected = {
            "STATE_ASSAM": {"ASM", "MNP"},
            "STATE_KASHMIR": {"KAS", "CHT", "LAD"},
        }
        for state, tags in protected.items():
            expected = {
                group["country"]: set(group["owned_provinces"])
                for group in BASELINE["states"][state]
                if group["country"] in tags
            }
            actual = owner_groups(state)
            self.assertEqual({tag: actual.get(tag, set()) for tag in tags}, expected, state)

    def test_tibet_and_kham_are_connected_and_lhasa_stays_in_tibet(self):
        lhasa = owner_groups("STATE_LHASA")
        self.assertEqual(set(lhasa), {"TIB", "KAM", "CHD", "HOR"})
        self.assertIn("x06698A", lhasa["TIB"])
        self.assertGreater(sum(len(ps) for tag, ps in lhasa.items() if tag != "TIB"), 20)
        for tag in ("SIK", "BHU"):
            expected = next(set(g["owned_provinces"]) for g in BASELINE["states"]["STATE_EASTERN_HIMALAYAS"] if g["country"] == tag)
            self.assertEqual(owner_groups("STATE_EASTERN_HIMALAYAS")[tag], expected)
        if np is None or Image is None:
            self.skipTest("Pillow and NumPy are required")
        provinces = set().union(*(set(BASELINE["state_regions"][s]) for s in ("STATE_LHASA", "STATE_SICHUAN", "STATE_EASTERN_HIMALAYAS")))
        pixels = np.asarray(Image.open(GAME / "map_data/provinces.png").convert("RGB"), dtype=np.uint32)
        encoded = pixels[:, :, 0] * 65536 + pixels[:, :, 1] * 256 + pixels[:, :, 2]
        adjacency = _state_adjacency(provinces, encoded, np)
        for tag in ("KAM", "DER", "CHD", "HOR", "LTG"):
            kham = set().union(*(owner_groups(s).get(tag, set()) for s in ("STATE_LHASA", "STATE_SICHUAN", "STATE_EASTERN_HIMALAYAS")))
            self.assertEqual(component_sizes(kham, adjacency), [len(kham)], tag)
        self.assertEqual(component_sizes(lhasa["TIB"], adjacency), [len(lhasa["TIB"])])

    def test_burmese_core_and_arakan_are_in_their_geographic_states(self):
        for state in ("STATE_MANDALAY",):
            expected = {
                group["country"]: set(group["owned_provinces"])
                for group in BASELINE["states"][state]
            }
            actual = owner_groups(state)
            self.assertEqual(actual, expected)

        arakan_baseline = BASELINE["states"]["STATE_ARAKAN"]
        arakan_actual = owner_groups("STATE_ARAKAN")
        expected_arakan = {
            "RKN": set(next(group["owned_provinces"] for group in arakan_baseline if group["country"] == "BIC")),
            "KKI": set(next(group["owned_provinces"] for group in arakan_baseline if group["country"] == "KKI")),
        }
        self.assertEqual(arakan_actual, expected_arakan)

    def test_lijiang_has_no_enclave_inside_xishuangbanna(self):
        if np is None or Image is None:
            self.skipTest("Pillow and NumPy are required for the province topology check")
        state = "STATE_YUNNAN"
        groups = owner_groups(state)
        pixels = np.asarray(Image.open(GAME / "map_data/provinces.png").convert("RGB"), dtype=np.uint32)
        encoded = pixels[:, :, 0] * 65536 + pixels[:, :, 1] * 256 + pixels[:, :, 2]
        adjacency = _state_adjacency(BASELINE["state_regions"][state], encoded, np)
        self.assertEqual(component_sizes(groups["LJG"], adjacency), [len(groups["LJG"])])

    def test_northeast_is_repartitioned_and_qing_remains_a_separate_russian_buffer(self):
        for state, tag in (("STATE_SHENGJING", "SHU"), ("STATE_OUTER_MANCHURIA", "AMR"), ("STATE_TRANS_BAIKAL", "CHI")):
            self.assertEqual(owner_groups(state), {tag: set(BASELINE["state_regions"][state])}, state)
        self.assertIn("SOL", owner_groups("STATE_NORTHERN_MANCHURIA"))
        self.assertNotIn("HUL", owner_groups("STATE_OUTER_MANCHURIA"))
        self.assertIn("SHU", owner_groups("STATE_SOUTHERN_MANCHURIA"))

        if np is None or Image is None:
            self.skipTest("Pillow and NumPy are required for the province topology check")
        pixels = np.asarray(Image.open(GAME / "map_data/provinces.png").convert("RGB"), dtype=np.uint32)
        encoded = pixels[:, :, 0] * 65536 + pixels[:, :, 1] * 256 + pixels[:, :, 2]
        all_ids = set().union(*(set(provinces) for provinces in BASELINE["state_regions"].values()))
        adjacency = _state_adjacency(all_ids, encoded, np)
        owners = {"CHI": set(), "SHU": set(), "RUS": set()}
        for state, groups in BASELINE["states"].items():
            for group in groups:
                if group["country"] in owners:
                    owners[group["country"]].update(group["owned_provinces"])
        for state, groups in AUTHORITY.items():
            state_provinces = set(BASELINE["state_regions"][state])
            for tag in owners:
                owners[tag].difference_update(state_provinces)
            for group in groups:
                if group["owner"] in owners:
                    owners[group["owner"]].update(group["owned_provinces"])
        self.assertEqual(component_sizes(owners["CHI"], adjacency), [len(owners["CHI"])])
        self.assertTrue(any(neighbor in owners["RUS"] for province in owners["CHI"] for neighbor in adjacency[province]))
        self.assertFalse(any(neighbor in owners["SHU"] for province in owners["CHI"] for neighbor in adjacency[province]))

    def test_china_subjects_are_removed_from_qing_and_transferred_to_shun(self):
        vanilla_path = GAME / "common/history/diplomacy/00_subject_relationships.txt"
        mod_path = ROOT / "yongchang_world/common/history/diplomacy/00_subject_relationships.txt"
        vanilla = vanilla_path.read_text("utf-8-sig")
        mod = mod_path.read_text("utf-8-sig")
        self.assertNotIn("c:CHI ?=", mod)
        expected = vanilla.replace(balanced_block(vanilla, "c:CHI ?="), "", 1)
        russian = balanced_block(expected, "c:RUS ?=")
        for tag in ("KZH", "OZH", "UZH"):
            pact_pattern = re.compile(r"(?ms)^\s*create_diplomatic_pact\s*=\s*\{.*?^\s*\}")
            for match in list(pact_pattern.finditer(russian)):
                pact = match.group(0)
                if re.search(rf"\bcountry\s*=\s*c:{tag}\b", pact):
                    russian = russian.replace(pact, "", 1)
            expected = expected.replace(balanced_block(expected, f"c:{tag} ?="), "", 1)
        expected = expected.replace(balanced_block(expected, "c:RUS ?="), russian, 1)
        self.assertEqual(re.sub(r"\s+", "", mod), re.sub(r"\s+", "", expected))

        for tag in ("KZH", "OZH", "UZH"):
            self.assertNotRegex(balanced_block(mod, "c:RUS ?="), rf"country\s*=\s*c:{tag}\b")
        geographic = (ROOT / "yongchang_world/common/history/diplomacy/ywc_geographic_diplomacy.txt").read_text("utf-8-sig")
        russian_frontier = balanced_block(geographic, "c:RUS ?=")
        self.assertRegex(russian_frontier, r"country\s*=\s*c:BKY\s+type\s*=\s*protectorate")

        shun_diplomacy = (ROOT / "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt").read_text("utf-8")
        shun = balanced_block(shun_diplomacy, "c:SHU ?=")
        self.assertIn("country = c:KOR", shun)
        self.assertIn("country = c:LAN", shun)
        self.assertNotIn("country = c:TIB", shun)
        tibet = balanced_block(shun_diplomacy, "c:TIB ?=")
        self.assertIn("country = c:LAD", tibet)
        self.assertIn("country = c:NEP", tibet)
        self.assertIn("country = c:SIK", tibet)
        self.assertIn("country = c:BHU", tibet)
        self.assertNotRegex(shun_diplomacy, r"(?s)c:KAM\s*\?=\s*\{.*?country\s*=\s*c:(?:SIK|BHU)")

    def test_shun_inherits_chinese_unity_journal_and_is_named_great_shun(self):
        shu_history = (ROOT / "yongchang_world/common/history/countries/ywc_shu.txt").read_text("utf-8")
        chi_history = (ROOT / "yongchang_world/common/history/countries/chi - china.txt").read_text("utf-8-sig")
        self.assertIn("type = je_warlord_china", shu_history)
        self.assertNotIn("type = je_warlord_china", chi_history)
        self.assertRegex(chi_history, r"(?m)set_capital\s*=\s*STATE_TRANS_BAIKAL")
        self.assertRegex(chi_history, r"(?m)set_market_capital\s*=\s*STATE_TRANS_BAIKAL")
        warlord = (ROOT / "yongchang_world/common/journal_entries/00_warlord_china.txt").read_text("utf-8-sig")
        self.assertIn("c:SHU ?= THIS", warlord)
        self.assertNotIn("c:SHU = THIS", warlord)
        names = list((ROOT / "yongchang_world/localization/english").glob("*.yml"))
        shu_names = [re.search(r"(?m)^\s*SHU:\s*\d+\s+\"([^\"]+)\"", path.read_text("utf-8")) for path in names]
        shu_names = [match.group(1) for match in shu_names if match]
        self.assertEqual(shu_names, ["Great Shun"])

    def test_regional_militia_is_defined_for_new_map_countries(self):
        formation_path = ROOT / "yongchang_world/common/history/military_formations/ywc_regional_military_formations.txt"
        text = formation_path.read_text("utf-8")
        for tag in ("SHU", "CHI", "OIR", "KZH", "OZH", "UZH", "TIB", "KAM", "LJG", "AMR", "HUL", "SOL", "RKN"):
            country = balanced_block(text, f"c:{tag} ?=")
            self.assertIn("create_military_formation", country)
            for state in re.findall(r"state_region\s*=\s*s:(STATE_[A-Z_]+)", country):
                groups = owner_groups(state) if state in AUTHORITY else {
                    g["country"]: set(g["owned_provinces"]) for g in BASELINE["states"][state]
                }
                self.assertIn(tag, groups, f"{tag}'s army is based outside its territory in {state}")


if __name__ == "__main__":
    unittest.main()
