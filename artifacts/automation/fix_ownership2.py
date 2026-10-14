# Rebuild the seven CHI-leftover state rows from the vanilla template:
# CHI blocks retarget to the design owners, non-CHI blocks kept verbatim,
# block count and province coverage match the template exactly.
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

tpl = TPL_PATH.read_text(encoding="utf-8-sig")
ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
by_state = {row["state"]: row for row in ov["states"]}

for state, new_owner in DESIGN.items():
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", tpl)
    assert m, state
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", tpl[m.end():])
    block = tpl[m.end():m.end() + nxt.start()] if nxt else tpl[m.end():]
    # walk each create_state block: owner + its owned_provinces
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        plist = re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])
        owner = cm.group(1)
        groups.append({"owner": new_owner if owner == "CHI" else owner, "owned_provinces": plist})
    assert groups, state
    total = sum(len(g["owned_provinces"]) for g in groups)
    if state in by_state:
        by_state[state]["groups"] = groups
    else:
        ov["states"].append({"state": state, "groups": groups})
    print(f"{state}: {[(g['owner'], len(g['owned_provinces'])) for g in groups]} (total {total})")

OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("overrides rebuilt")
