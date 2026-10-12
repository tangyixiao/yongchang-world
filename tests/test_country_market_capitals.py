import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
COUNTRY_HISTORY = ROOT / "yongchang_world/common/history/countries"
STATE_HISTORY = ROOT / "yongchang_world/common/history/states/00_states.txt"
SOUTHWEST_STATES = ROOT / "data/scenario/southwest_states.json"


def balanced_end(text, opening):
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(text)):
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
                return index + 1
    raise AssertionError(f"unclosed block at {opening}")


class CountryMarketCapitalTest(unittest.TestCase):
    def test_every_starting_market_capital_is_in_a_state_owned_by_its_country(self):
        state_text = STATE_HISTORY.read_text(encoding="utf-8-sig")
        owners = {}
        for match in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", state_text):
            opening = state_text.find("{", match.start())
            block = state_text[opening:balanced_end(state_text, opening)]
            owners[match.group(1)] = set(re.findall(r"country\s*=\s*c:([A-Z0-9]+)", block))

        southwest = json.loads(SOUTHWEST_STATES.read_text(encoding="utf-8-sig"))
        releasable = set(southwest["releasable_tags"])
        checked = set()
        for path in COUNTRY_HISTORY.glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r"c:([A-Z0-9]+)\s*\?=\s*\{", text):
                tag = match.group(1)
                opening = text.find("{", match.start())
                block = text[opening:balanced_end(text, opening)]
                for state in re.findall(r"set_market_capital\s*=\s*(STATE_[A-Z0-9_]+)", block):
                    if tag in releasable:
                        continue  # These dormant tags do not exist at game start.
                    checked.add(tag)
                    self.assertIn(state, owners, f"{path.name}: unknown market-capital state {state}")
                    self.assertIn(tag, owners[state], f"{path.name}: {tag} does not own {state}")

        self.assertIn("RKN", checked)


if __name__ == "__main__":
    unittest.main()
