import json
import re
import sys
from pathlib import Path

ROOT = Path(".")
b = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
base = set(b["country_tags"])
print("RKN free:", "RKN" not in base)

LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
POPS_DIR = ROOT / "yongchang_world/common/history/pops"
REGISTRY = ROOT / "data/scenario/tag_registry.json"
registry_tags = {row["tag"] for row in json.loads(REGISTRY.read_text(encoding="utf-8-sig"))["countries"]}

owners = {}
text = LEDGER.read_text(encoding="utf-8-sig")
for match in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text):
    state = match.group(1)
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", text[match.end():])
    end = match.end() + (nxt.start() if nxt else len(text) - match.end())
    block = text[match.start():end]
    for tag in re.findall(r"country = c:([A-Z]{3})", block):
        owners.setdefault(state, set()).add(tag)

pop_targets = set()
for path in POPS_DIR.glob("*.txt"):
    ptext = path.read_text(encoding="utf-8-sig")
    for match in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", ptext):
        state = match.group(1)
        nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", ptext[match.end():])
        end = match.end() + (nxt.start() if nxt else len(ptext) - match.end())
        for tag in re.findall(r"region_state:([A-Z]{3})", ptext[match.start():end]):
            pop_targets.add((state, tag))

missing = [(s, t) for s, tags in owners.items() for t in tags
           if t in registry_tags and (s, t) not in pop_targets]
print("missing pops pairs:", missing)

# state history test invocation
test_text = (ROOT / "tests/test_state_history_generation.py").read_text(encoding="utf-8")
i = test_text.find("def test_generated_state_history")
print(test_text[i:i + 1400])
