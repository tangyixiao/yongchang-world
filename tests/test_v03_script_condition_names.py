import json, os, pathlib, re, tempfile, unittest
from tests.clausewitz_harness import PulseWorld, parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
COUNTRY_TAGS = ("dmg", "jhg", "kor", "lan", "mgl", "nmg", "nqg", "oir", "shu", "tib")


def _all_script_definitions():
    definitions = {}
    for folder in ("scripted_effects", "scripted_triggers"):
        for path in sorted((ROOT / "yongchang_world/common" / folder).glob("*.txt")):
            for key, _, body in parse(path.read_text(encoding="utf-8-sig")):
                if key.startswith("ywc_"):
                    definitions.setdefault(key, body)
    return definitions


def _walk_ywc_calls(nodes, path, definitions, depth=0):
    for key, _, value in nodes:
        if depth > 0 and key.startswith("ywc_") and key not in definitions:
            yield f"{path}:{key}"
        if isinstance(value, list):
            yield from _walk_ywc_calls(value, path, definitions, depth + 1)


def _all_scripted_triggers():
    definitions = {}
    for path in sorted((ROOT / "yongchang_world/common/scripted_triggers").glob("*.txt")):
        for key, _, body in parse(path.read_text(encoding="utf-8-sig")):
            if key.startswith("ywc_"):
                definitions.setdefault(key, body)
    return definitions


class StrictConditionWorld(PulseWorld):
    def __init__(self, facts):
        super().__init__("", {"JHG": facts})
        self.scripted_triggers = _all_scripted_triggers()

    def condition(self, node, tag):
        key, comparison, value = node
        if key.startswith("ywc_"):
            if key not in self.scripted_triggers:
                raise AssertionError(f"undefined ywc_ scripted trigger in source condition: {key}")
            if comparison != "=" or value != "yes":
                raise AssertionError(f"unsupported ywc_ trigger invocation: {node}")
            return self.conditions(self.scripted_triggers[key], tag)
        return super().condition(node, tag)


class ScriptConditionNameAuditTest(unittest.TestCase):
    def test_all_v03_country_scripts_call_only_declared_ywc_helpers(self):
        definitions = _all_script_definitions()
        files = []
        for tag in COUNTRY_TAGS:
            files.extend((
                ROOT / f"yongchang_world/events/ywc_v03_country_{tag}_events.txt",
                ROOT / f"yongchang_world/common/journal_entries/ywc_v03_country_{tag}_journal.txt",
                ROOT / f"yongchang_world/common/scripted_effects/ywc_v03_{tag}_effects.txt",
                ROOT / f"yongchang_world/common/scripted_triggers/ywc_v03_{tag}_triggers.txt",
            ))
        missing = []
        for path in files:
            self.assertTrue(path.is_file(), f"missing generated/local script: {path}")
            missing.extend(_walk_ywc_calls(parse(path.read_text(encoding="utf-8-sig")), path.name, definitions))
        self.assertEqual(missing, [])

    def test_jhg_withdrawn_failures_are_real_flags_and_exclusive_to_completion(self):
        catalog = json.loads((ROOT / "data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        generated = parse((ROOT / "yongchang_world/common/journal_entries/ywc_v03_country_jhg_journal.txt").read_text(encoding="utf-8-sig"))
        generated_by_id = {key: body for key, _, body in generated}
        goal_facts = {
            "ywc_je_v03_jhg_court_assembly": {"ywc_jhg_court_route": 1, "ywc_jhg_court_filing_fee_paid": 1},
            "ywc_je_v03_jhg_court_settlement": {"ywc_jhg_court_established": 1},
            "ywc_je_v03_jhg_convoy_capacity": {"ywc_jhg_convoy_route": 1, "ywc_jhg_convoy_filing_fee_paid": 1, "gold_reserves": 10000},
            "ywc_je_v03_jhg_convoy_partner_watch": {"ywc_jhg_convoy_route": 2, "ywc_jhg_convoy_six_months_complete": 1},
            "ywc_je_v03_jhg_convoy_settlement": {"ywc_jhg_convoy_established": 1},
            "ywc_je_v03_jhg_tribute_autonomy": {"ywc_jhg_tribute_established": 1},
        }
        count = 0
        for arc in catalog["arcs"]:
            for journal in arc["journals"]:
                jid = journal["id"]
                fail = journal["exit_conditions"]
                # Catch the exact bad syntax structurally, before evaluation can hide it.
                self.assertNotRegex(fail, r"(?<![\w:])ywc_jhg_(?:court|convoy|tribute)_withdrawn\s*\?=\s*yes")
                emitted = {name: value for name, _, value in generated_by_id[jid]}
                generated_fail = emitted["fail"]
                self.assertEqual(parse("condition = " + fail)[0][2], generated_fail, jid)
                withdrawn = jid.split("_jhg_", 1)[1].split("_", 1)[0]
                flag = f"ywc_jhg_{withdrawn}_withdrawn"
                facts = {"bureaucracy": 100, "net_fixed_income": 1, "government_legitimacy": 30,
                         "gold_reserves": 10000, "in_default": False, "is_at_war": False}
                facts.update(goal_facts[jid])
                world = StrictConditionWorld(facts)
                goal_ast = parse("condition = " + journal["goal"])[0][2]
                fail_ast = parse("condition = " + fail)[0][2]
                self.assertTrue(world.conditions(goal_ast, "JHG"), jid + " should complete on its authored success fixture")
                self.assertFalse(world.conditions(fail_ast, "JHG"), jid + " must not fail while its withdrawal flag is absent")
                facts[flag] = 1
                self.assertTrue(world.conditions(fail_ast, "JHG"), jid + " must fail on the actual withdrawal flag")
                self.assertFalse(world.conditions(goal_ast, "JHG"), jid + " goal/fail must be exclusive after withdrawal")
                count += 1
        self.assertEqual(count, 6)


if __name__ == "__main__":
    unittest.main()
