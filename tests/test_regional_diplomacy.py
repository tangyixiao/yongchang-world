import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"
OCEAN_DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_ocean_diplomacy.txt"


class InnerAsiaDiplomacyTest(unittest.TestCase):
    def setUp(self):
        self.text = DIPLOMACY_FILE.read_text("utf-8")

    def test_required_relationships_are_declared(self):
        self.assertRegex(self.text, r"c:RUS\s*\?=\s*\{(?s:.*?)country\s*=\s*c:KJU")
        self.assertRegex(self.text, r"c:RUS\s*\?=\s*\{(?s:.*?)country\s*=\s*c:MJU")
        self.assertRegex(self.text, r"c:RUS\s*\?=\s*\{(?s:.*?)country\s*=\s*c:GJU")
        self.assertRegex(self.text, r"c:SHU\s*\?=\s*\{(?s:.*?)country\s*=\s*c:HMI")
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


if __name__ == "__main__":
    unittest.main()
