import json
import re
import sys

sys.path.insert(0, ".")
from tools.build_state_history import state_blocks, override_map

tpl = open("E:/SteamLibrary/steamapps/common/Victoria 3/game/common/history/states/00_states.txt", encoding="utf-8-sig").read()
baseline = json.load(open("data/baseline/vic3-1.13.11.json", encoding="utf-8"))
blocks = state_blocks(tpl, baseline)
ov = json.load(open("data/scenario/ownership_overrides.json", encoding="utf-8"))
mapping = override_map(ov)
mismatch = []
for state, block in blocks.items():
    n = len(re.findall(r"create_state\s*=\s*\{", block))
    if state in mapping and n != len(mapping[state]):
        owners = re.findall(r"country = c:([A-Z]{3})", block)
        mismatch.append((state, n, len(mapping[state]), owners))
for m in mismatch:
    print("MISMATCH:", m)
print("total mismatches:", len(mismatch))
