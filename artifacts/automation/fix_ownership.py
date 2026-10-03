# Fix stage 1: ownership_overrides.json
# - reassign the seven leftover CHI states per the timeline design
# - give SHU the Sichuan/Yunnan basin remainder (the highland fragments keep
#   their assigned border provinces)
# - rename the Mandalay owner ARA (vanilla Arabia collision) to the new ARK
import json
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
ROOT = Path(".")
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"

# vanilla province lists for the states we touch (authoritative: baseline dump)
BASELINE = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))

def provinces_of(state):
    plist = list(BASELINE["state_regions"][state])
    assert len(plist) == len(set(plist)), state
    return plist

REASSIGN = {  # CHI leftovers -> design owners (2026-09-04-01 timeline)
    "STATE_SOUTHERN_MANCHURIA": "SHU",   # 辽东、吉林中南部大顺移民区
    "STATE_AMUR": "AMR",                 # 黑水部盟
    "STATE_HINGGAN": "SOL",              # 索伦部盟
    "STATE_ALXA": "KHO",                 # 阿拉善和硕特
    "STATE_TUVA": "MGL",                 # 唐努乌梁海
    "STATE_ALTAI": "MGL",                # 阿尔泰诺尔乌梁海
    "STATE_JETISY": "GJU",               # 七河归大玉兹
}
RESIDUAL_TO_SHU = {"STATE_SICHUAN", "STATE_YUNNAN"}

ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
by_state = {row["state"]: row for row in ov["states"]}
changed = []

for state, new_owner in REASSIGN.items():
    plist = provinces_of(state)
    if state in by_state:
        row = by_state[state]
        before = [g["owner"] for g in row["groups"]]
        row["groups"] = [{"owner": new_owner, "owned_provinces": plist}]
        changed.append(f"{state}: {before} -> [{new_owner}] ({len(plist)} provinces)")
    else:
        ov["states"].append({"state": state, "groups": [{"owner": new_owner, "owned_provinces": plist}]})
        changed.append(f"{state}: ADDED [{new_owner}] ({len(plist)} provinces; previously vanilla CHI)")

for state in RESIDUAL_TO_SHU:
    row = by_state[state]
    allp = provinces_of(state)
    assigned = []
    for g in row["groups"]:
        assigned += g.get("owned_provinces", [])
    remainder = [p for p in allp if p not in assigned]
    if remainder:
        row["groups"].append({"owner": "SHU", "owned_provinces": remainder})
        changed.append(f"{state}: +SHU residual ({len(remainder)} provinces; fragments keep {len(assigned)})")
    else:
        # The fragments already absorb the whole state. Per the scenario the
        # basin core (the state's city province) belongs to SHU directly.
        city = None
        for path in GAME.glob("map_data/state_regions/*.txt"):
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
            m = re.search(rf"{state}\s*=\s*\{{(.*?)\n\}}", text, re.S)
            if m:
                cm = re.search(r"city\s*=\s*\"?(x[0-9A-Fa-f]+)\"?", m.group(1))
                if cm:
                    city = cm.group(1)
                break
        assert city, state
        taken_from = None
        for g in row["groups"]:
            if city in g.get("owned_provinces", []):
                g["owned_provinces"].remove(city)
                taken_from = g["owner"]
                break
        assert taken_from, (state, city)
        row["groups"].append({"owner": "SHU", "owned_provinces": [city]})
        changed.append(f"{state}: city {city} moved {taken_from} -> SHU (basin core)")

for row in ov["states"]:
    if row["state"] == "STATE_MANDALAY":
        for g in row["groups"]:
            if g["owner"] == "ARA":
                g["owner"] = "ARK"
                changed.append("STATE_MANDALAY: ARA -> ARK")

OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("\n".join(changed))
print("ownership_overrides.json updated")
