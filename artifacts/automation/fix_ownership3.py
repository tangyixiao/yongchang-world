# Robust rebuild: slice the template by sorted state positions from the baseline list.
import json
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
ROOT = Path(".")
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
TPL_PATH = GAME / "common/history/states/00_states.txt"

DESIGN = {
    "STATE_SOUTHERN_MANCHURIA": "SHU",
    "STATE_AMUR": "AMR",
    "STATE_HINGGAN": "SOL",
    "STATE_ALXA": "KHO",
    "STATE_TUVA": "MGL",
    "STATE_ALTAI": "MGL",
    "STATE_JETISY": "GJU",
}

baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
all_states = sorted(baseline["state_regions"].keys())
tpl = TPL_PATH.read_text(encoding="utf-8-sig")

positions = []
for state in all_states:
    m = re.search(rf"(?m)^\s*s:{re.escape(state)}\s*=", tpl)
    if m:
        positions.append((m.start(), m.end(), state))
positions.sort()
print(f"template: found {len(positions)} / {len(all_states)} states at line starts")

ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
by_state = {row["state"]: row for row in ov["states"]}

for idx, (start, eq_end, state) in enumerate(positions):
    if state not in DESIGN:
        continue
    end = positions[idx + 1][0] if idx + 1 < len(positions) else len(tpl)
    block = tpl[start:end]
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        plist = re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])
        owner = cm.group(1)
        groups.append({"owner": DESIGN[state] if owner == "CHI" else owner, "owned_provinces": plist})
    assert groups, state
    flat = [p for g in groups for p in g["owned_provinces"]]
    assert len(flat) == len(set(flat)), f"{state}: overlapping provinces"
    assert set(flat) == set(baseline["state_regions"][state]), f"{state}: coverage mismatch"
    if state in by_state:
        by_state[state]["groups"] = groups
    else:
        ov["states"].append({"state": state, "groups": groups})
    print(f"{state}: {[(g['owner'], len(g['owned_provinces'])) for g in groups]}")

OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("overrides rebuilt cleanly")
