import json
import re
import sys

sys.path.insert(0, ".")
from tools.build_state_history import state_blocks, override_map

tpl = open("yongchang_world/common/history/states/00_states.txt", encoding="utf-8-sig").read()
baseline = json.load(open("data/baseline/vic3-1.13.11.json", encoding="utf-8"))
blocks = state_blocks(tpl, baseline)
ov = json.load(open("data/scenario/ownership_overrides.json", encoding="utf-8"))
mapping = override_map(ov)
out = []
for state, block in blocks.items():
    n = len(re.findall(r"create_state", block))
    if state in mapping and n != len(mapping[state]):
        out.append((state, n, len(mapping[state]), re.findall(r"country = c:([A-Z]{3})", block)))
print(len(out), "mismatches")
for row in out:
    print(row)
