"""JHG content contracts tied to the whole option and transitive script consumers."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data/content/v03/countries/jhg.json"
EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_jhg_effects.txt"
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_jhg_triggers.txt"


def blocks(source: str) -> dict[str, str]:
    """Read top-level Clausewitz blocks while respecting nested braces."""
    result = {}
    for match in re.finditer(r"(?m)^([A-Za-z0-9_]+)\s*=\s*\{", source):
        name, start = match.group(1), match.end() - 1
        depth = 0
        for i in range(start, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    result[name] = source[start:i + 1]
                    break
    return result


def closure(text: str, definitions: dict[str, str]) -> tuple[set[str], str]:
    """Return all called authored helpers and their transitive source."""
    seen: set[str] = set()
    pending = list(re.findall(r"\b(ywc_jhg_[A-Za-z0-9_]+)\s*=\s*yes\b", text))
    pieces = [text]
    while pending:
        name = pending.pop()
        if name in seen or name not in definitions:
            continue
        seen.add(name)
        body = definitions[name]
        pieces.append(body)
        pending.extend(re.findall(r"\b(ywc_jhg_[A-Za-z0-9_]+)\s*=\s*yes\b", body))
    return seen, "\n".join(pieces)


class JHGContentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.effects = blocks(EFFECTS.read_text(encoding="utf-8"))
        cls.triggers = blocks(TRIGGERS.read_text(encoding="utf-8"))

    def test_all_24_cards_have_complete_bilingual_narrative(self):
        events = [event for arc in self.catalog["arcs"] for event in arc["events"]]
        self.assertEqual(len(events), 24)
        journals = [journal for arc in self.catalog["arcs"] for journal in arc["journals"]]
        self.assertEqual(len(journals), 6)
        for journal in journals:
            for field in ("title", "desc"):
                self.assertEqual(set(journal[field]), {"zh", "en"}, (journal["id"], field))
                self.assertTrue(all(journal[field][lang].strip() for lang in ("zh", "en")))
        for event in events:
            for field in ("title", "desc"):
                self.assertEqual(set(event[field]), {"zh", "en"}, (event["id"], field))
                self.assertTrue(all(event[field][lang].strip() for lang in ("zh", "en")))
            for option in event["options"]:
                for field in ("label", "cost_note", "consequence_note"):
                    self.assertEqual(set(option[field]), {"zh", "en"}, (event["id"], option["key"], field))
                    self.assertTrue(all(option[field][lang].strip() for lang in ("zh", "en")))

    def test_each_option_text_matches_its_whole_effect_helper_closure(self):
        events = [event for arc in self.catalog["arcs"] for event in arc["events"]]
        for event in events:
            arc = next(a for a in self.catalog["arcs"] if event in a["events"])
            family = {"v03_jhg_court_assembly": "court", "v03_jhg_convoy_capacity": "convoy", "v03_jhg_tribute_autonomy": "tribute"}[arc["slug"]]
            for option in event["options"]:
                key = (event["id"], option["key"])
                with self.subTest(option=key):
                    trigger_helpers, trigger_closure = closure(option.get("trigger", ""), self.triggers)
                    effect_helpers, effect_closure = closure(option.get("effect", ""), self.effects)
                    # Partner language is supported only by reads in eligibility triggers.
                    partner_claim = any(word in (option["label"]["en"] + " " + option["cost_note"]["en"] + " " + option["consequence_note"]["en"]).lower() for word in ("partner", "ally", "allied"))
                    if partner_claim:
                        self.assertTrue(trigger_helpers or "has_diplomatic_pact" in option.get("trigger", ""), key)
                        self.assertNotRegex(trigger_closure, r"\b(?:add_diplomatic_pact|change_relations|add_relations|add_treasury)\s*=")
                        self.assertNotRegex(effect_closure, r"\b(?:add_diplomatic_pact|change_relations|add_relations|transfer_treasury)\s*=")
                    # The JHG choice effects select a domestic route and queue domestic follow-up work.
                    # They do not create modifiers, political changes, partner transfers, or deployed units.
                    self.assertNotRegex(effect_closure, r"\b(?:add_modifier|add_timed_modifier|change_government_legitimacy|add_authority|add_diplomatic_pact|change_relations|add_relations|transfer_treasury|spawn_fleet|create_fleet)\s*=")
                    if "filing fee" in option["cost_note"]["en"].lower() or "one-time fee for this arc" in option["cost_note"]["en"].lower():
                        self.assertIn(f"ywc_jhg_{family}_pay_filing_fee_once", option["effect"], key)

    def test_action_labels_match_what_the_whole_option_does(self):
        expected = {'ywc_jhg.1000:audit_contract': {'zh': '登记审账契约提案', 'en': 'Register the audit-contract proposal'}, 'ywc_jhg.1000:prince_guarantee': {'zh': '登记王府担保提案', 'en': 'Register the household guarantee proposal'}, 'ywc_jhg.1001:audit_contract': {'zh': '记下季度公开条款', 'en': 'Record quarterly-disclosure terms'}, 'ywc_jhg.1002:prince_guarantee': {'zh': '登记王府担保提案', 'en': 'Register the household guarantee proposal'}, 'ywc_jhg.1003:merchant_pool': {'zh': '登记优先报关提案', 'en': 'Register the priority-clearance proposal'}, 'ywc_jhg.1004:audit_contract': {'zh': '核验现有账房人员', 'en': 'Verify current clerk staffing'}, 'ywc_jhg.1005:prince_guarantee': {'zh': '按现行制度确认代表资格', 'en': 'Confirm representation under current law'}, 'ywc_jhg.1006:hold_course': {'zh': '继续观察现行安排', 'en': 'Continue observing the current arrangement'}, 'ywc_jhg.1007:settle_full': {'zh': '记录完整结案结果', 'en': 'Record the full domestic settlement'}, 'ywc_jhg.1007:settle_partial': {'zh': '记录妥协结案结果', 'en': 'Record a compromise settlement'}, 'ywc_jhg.1010:main_lane': {'zh': '登记主航线方案', 'en': 'Register a main-lane plan'}, 'ywc_jhg.1010:shared_escort': {'zh': '按现存盟约提出有限护航方案', 'en': 'Propose limited escort under the existing alliance'}, 'ywc_jhg.1011:main_lane': {'zh': '核验主航线港口现有人员', 'en': 'Check current staffing at main-lane ports'}, 'ywc_jhg.1012:shared_escort': {'zh': '提出盟约下分担护航方案', 'en': 'Propose shared escort under the existing alliance'}, 'ywc_jhg.1013:main_lane': {'zh': '登记主航线方案', 'en': 'Register a main-lane plan'}, 'ywc_jhg.1014:insurance': {'zh': '登记商业保险提案', 'en': 'Register a commercial-insurance proposal'}, 'ywc_jhg.1015:explain_limits': {'zh': '承认护航能力有限', 'en': 'Acknowledge the escort limit'}, 'ywc_jhg.1016:main_lane': {'zh': '按现行海军法登记主航线方案', 'en': 'Register a main-lane plan under current naval law'}, 'ywc_jhg.1017:hold_course': {'zh': '继续观察现有方案', 'en': 'Continue review under the current plan'}, 'ywc_jhg.1018:settle_full': {'zh': '记录完整结案结果', 'en': 'Record the full domestic result'}, 'ywc_jhg.1018:settle_partial': {'zh': '记录有限妥协结果', 'en': 'Record the limited compromise result'}, 'ywc_jhg.1020:fixed_share': {'zh': '提出固定份额方案', 'en': 'Propose a standing-share arrangement'}, 'ywc_jhg.1020:ambiguity': {'zh': '保留未定贡单条款', 'en': 'Leave the tribute terms open'}, 'ywc_jhg.1021:fixed_share': {'zh': '回信提出固定份额', 'en': 'Propose a fixed share in reply'}, 'ywc_jhg.1022:project_share': {'zh': '提出共同项目方案', 'en': 'Propose a joint-project arrangement'}, 'ywc_jhg.1023:ambiguity': {'zh': '保留未定贡单条款', 'en': 'Leave the tribute terms open'}, 'ywc_jhg.1025:settle_full': {'zh': '记录完整结案结果', 'en': 'Record the full domestic result'}, 'ywc_jhg.1025:settle_partial': {'zh': '记录妥协结案结果', 'en': 'Record a compromise settlement'}}
        events = {event["id"]: event for arc in self.catalog["arcs"] for event in arc["events"]}
        for key, label in expected.items():
            event_id, option_key = key.split(":", 1)
            option = next(option for option in events[event_id]["options"] if option["key"] == option_key)
            with self.subTest(option=key):
                self.assertEqual(option["label"], label)
                if option_key not in ("hold_course", "settle_full", "settle_partial", "explain_limits"):
                    self.assertIn("pending_event", option["effect"])

    def test_return1_narrative_uses_contract_voice(self):
        journals = {journal["id"]: journal for arc in self.catalog["arcs"] for journal in arc["journals"]}
        event = next(event for arc in self.catalog["arcs"] for event in arc["events"] if event["id"] == "ywc_jhg.1012")
        self.assertIn("The clerks spread six months of ledgers", journals["ywc_je_v03_jhg_court_settlement"]["desc"]["en"])
        self.assertIn("lays the escort proposal beside the alliance papers", journals["ywc_je_v03_jhg_convoy_partner_watch"]["desc"]["en"])
        self.assertIn("brings the household a limited escort proposal", event["desc"]["en"])
        self.assertIn("It remains a domestic proposal for discussion", event["desc"]["en"])

    def test_overclaims_removed_from_all_user_facing_card_fields(self):
        events = [event for arc in self.catalog["arcs"] for event in arc["events"]]
        corpus = []
        journals = [journal for arc in self.catalog["arcs"] for journal in arc["journals"]]
        for journal in journals:
            corpus += [journal["title"]["en"], journal["desc"]["en"]]
        for event in events:
            corpus += [event["title"]["en"], event["desc"]["en"]]
            for option in event["options"]:
                corpus += [option[field]["en"] for field in ("label", "cost_note", "consequence_note")]
        text = "\n".join(corpus).lower()
        stale_claims = (
            "legitimacy improves", "authority rises", "landowner support rise",
            "tax base and legitimacy suffer", "property interests grow",
            "merchants front the money", "partner must genuinely contribute",
            "both fleets cruise", "ally delivered", "partner willing to pay",
            "someone will share the tribute", "merchants carry premiums", "executable autonomy arrangement",
            "exposed to back-payment later", "expand only the main-lane establishment",
            "fill the clerk establishment", "staff the main-lane docks first",
            "the share is fixed and the autonomy boundary with it",
            "adds no political or economic effect", "reads an existing pact",
            "no allied response is requested", "does not request a response or dispatch",
        )
        for phrase in stale_claims:
            self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
