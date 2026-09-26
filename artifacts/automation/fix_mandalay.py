# Align MANDALAY override groups with the template's create_state count (all -> ARK).
import json
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
ROOT = Path(".")
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
tpl = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")

ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
state = "STATE_MANDALAY"
m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", tpl)
nxt = re.search(rf"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", tpl[m.end():])
block = tpl[m.end():m.end() + nxt.start()] if nxt else tpl[m.end():]
groups = []
for cm in re.finditer(r"country = c:([A-Z]{3})", block):
    p_open = block.find("owned_provinces = {", cm.start())
    p_close = block.find("}", p_open)
    plist = re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])
    groups.append({"owner": "ARK", "owned_provinces": plist})
print(f"{state}: template blocks -> {len(groups)} ARK groups")
for row in ov["states"]:
    if row["state"] == state:
        row["groups"] = groups
        break
OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("aligned")
