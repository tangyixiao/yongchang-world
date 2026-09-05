import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
DIPLOMACY_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"


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


if __name__ == "__main__":
    unittest.main()
