import json
import re
import sys
from pathlib import Path

ROOT = Path(".")
b = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
base = set(b["country_tags"])
for cand in ("RKN", "RAK", "ARN", "ARK"):
    print(cand, "in vanilla:", cand in base)

sys.path.insert(0, ".")
from tests.test_scenario_integrity import ScenarioIntegrityTest
t = ScenarioIntegrityTest("x")
t.setUpClass()
missing = []
for state, tags in t.owners.items():
    for tag in tags:
        if tag in t.registry_tags and (state, tag) not in t.pop_targets:
            missing.append((state, tag))
print("missing pops pairs:", missing)

# the state-history test invocation
test_text = (ROOT / "tests/test_state_history_generation.py").read_text(encoding="utf-8")
i = test_text.find("def test_generated_state_history")
print(test_text[i:i + 1300])

# regional test references to ARA
reg_text = (ROOT / "tests/test_regional_states.py").read_text(encoding="utf-8")
for i, line in enumerate(reg_text.splitlines(), 1):
    if "ARA" in line:
        print(f"regional test {i}: {line.strip()[:100]}")
