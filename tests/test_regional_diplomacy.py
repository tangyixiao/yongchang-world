import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"
OCEAN_DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_ocean_diplomacy.txt"
VANILLA_SUBJECTS_FILE = ROOT / "yongchang_world/common/history/diplomacy/00_subject_relationships.txt"
GEOGRAPHIC_DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_geographic_diplomacy.txt"


class InnerAsiaDiplomacyTest(unittest.TestCase):
    def setUp(self):
        self.text = DIPLOMACY_FILE.read_text("utf-8")

    def test_required_relationships_are_declared(self):
        self.assertNotIn("c:RUS ?=", self.text)
        self.assertRegex(self.text, r"c:SHU\s*\?=\s*\{(?s:.*?)country\s*=\s*c:HMI")
        self.assertRegex(self.text, r"c:SHU\s*\?=\s*\{(?s:.*?)country\s*=\s*c:DAI(?s:.*?)type\s*=\s*tributary")
        self.assertRegex(self.text, r"c:SHU\s*\?=\s*\{(?s:.*?)country\s*=\s*c:KAM(?s:.*?)type\s*=\s*tributary")
        self.assertRegex(self.text, r"c:OIR\s*\?=\s*\{(?s:.*?)country\s*=\s*c:KOK")
        self.assertRegex(self.text, r"c:KOK\s*\?=\s*\{(?s:.*?)country\s*=\s*c:OIR")

    def test_inner_asia_subject_edges_do_not_cycle(self):
        edges = re.findall(
            r"c:([A-Z]{3})\s*\?=\s*\{\s*create_diplomatic_pact\s*=\s*\{\s*country\s*=\s*c:([A-Z]{3})\s+type\s*=\s*(?:tributary|protectorate)",
            self.text,
        )
        graph = {}
        for source, target in edges:
            graph.setdefault(source, set()).add(target)
        for source in graph:
            for target in graph[source]:
                self.assertNotIn(source, graph.get(target, set()), f"subject cycle: {source}->{target}")

    def test_tibet_and_kho_are_not_subjects_of_each_other(self):
        self.assertNotRegex(self.text, r"c:TIB\s*\?=\s*\{(?s:.*?)country\s*=\s*c:KHO")
        self.assertNotRegex(self.text, r"c:KHO\s*\?=\s*\{(?s:.*?)country\s*=\s*c:TIB")

    def test_tibet_protects_himalayan_tributaries_and_batang_is_not_overlord(self):
        self.assertRegex(
            self.text,
            r"c:TIB\s*\?=\s*\{(?s:.*?)country\s*=\s*c:LAD(?s:.*?)type\s*=\s*tributary",
        )
        self.assertRegex(self.text, r"c:TIB\s*\?=\s*\{(?s:.*?)country\s*=\s*c:SIK(?s:.*?)type\s*=\s*tributary")
        self.assertRegex(self.text, r"c:TIB\s*\?=\s*\{(?s:.*?)country\s*=\s*c:BHU(?s:.*?)type\s*=\s*tributary")
        self.assertNotRegex(self.text, r"c:KAM\s*\?=\s*\{(?s:.*?)country\s*=\s*c:(?:SIK|BHU)")


class OceanDiplomacyTest(unittest.TestCase):
    def setUp(self):
        self.text = OCEAN_DIPLOMACY_FILE.read_text("utf-8")

    def test_overseas_relationships_are_declared(self):
        self.assertRegex(self.text, r"c:MEX\s*\?=\s*\{(?s:.*?)country\s*=\s*c:NMG(?s:.*?)type\s*=\s*protectorate")
        for country in ("DAI", "SIA", "CAM", "JHG"):
            self.assertRegex(self.text, rf"c:MHG\s*\?=\s*\{{(?s:.*?)country\s*=\s*c:{country}")
        self.assertRegex(self.text, r"c:LAN\s*\?=\s*\{(?s:.*?)country\s*=\s*c:WBK")
        self.assertRegex(self.text, r"c:WBK\s*\?=\s*\{(?s:.*?)country\s*=\s*c:LAN")
        for country in ("PNP", "PLW", "YAP", "MHL"):
            self.assertRegex(self.text, rf"c:JHG\s*\?=\s*\{{(?s:.*?)country\s*=\s*c:{country}")

    def test_nmg_has_no_american_starting_subject_edge(self):
        self.assertNotRegex(self.text, r"c:USA\s*\?=\s*\{(?s:.*?)create_diplomatic_pact")


class RussianFrontierDiplomacyTest(unittest.TestCase):
    def test_zhuz_are_independent_and_bukey_remains_russian_protectorate(self):
        vanilla_subjects = VANILLA_SUBJECTS_FILE.read_text("utf-8-sig")
        russian_block = re.search(r"c:RUS\s*\?=\s*\{(?s:.*?)\n\s*\}", vanilla_subjects).group(0)
        for tag in ("KZH", "OZH", "UZH"):
            self.assertNotRegex(russian_block, rf"country\s*=\s*c:{tag}\b")
        self.assertNotRegex(vanilla_subjects, r"c:(?:KZH|OZH|UZH)\s*\?=\s*\{(?s:.*?)add_liberty_desire")

        geographic = GEOGRAPHIC_DIPLOMACY_FILE.read_text("utf-8-sig")
        self.assertRegex(geographic, r"c:RUS\s*\?=\s*\{(?s:.*?)country\s*=\s*c:BKY\s+type\s*=\s*protectorate")


if __name__ == "__main__":
    unittest.main()
