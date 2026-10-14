# 1) dedupe the doubled SHU city blocks in the ledger
# 2) align the SICHUAN/YUNNAN override group counts (add the SHU city group)
# 3) regenerate
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
CITIES = {"STATE_SICHUAN": ("x60E0D5", "KAM"), "STATE_YUNNAN": ("x78DC66", "LJG")}

text = LEDGER.read_text(encoding="utf-8-sig")
for state, (city, holder) in CITIES.items():
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", text)
    nxt = re.search(rf"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", text[m.end():])
    end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    block = text[m.start():end]
    shu_blocks = re.findall(r"create_state = \{\s*country = c:SHU\s*owned_provinces = \{ "
                            + city + r" \}\s*\}", block)
    while len(shu_blocks) > 1:
        block = block.replace(shu_blocks.pop(), "", 1)
    # normalize: exactly one SHU city block
    if f"country = c:SHU" not in block:
        lines = block.split("\n")
        insert_at = 1 + next(i for i, l in enumerate(lines[1:], 1) if "create_state" in l)
        lines.insert(insert_at, f"\t\tcreate_state = {{\n\t\t\tcountry = c:SHU\n\t\t\towned_provinces = {{ {city} }}\n\t\t}}")
        block = "\n".join(lines)
    # remove the city from the holder's list
    hm = re.search(rf"country = c:{holder}\s*\n\s*owned_provinces\s*=\s*\{{([^}}]*)\}}", block)
    if hm and city in hm.group(1).split():
        new_list = " ".join(p for p in hm.group(1).split() if p != city)
        block = block[:hm.start(1)] + new_list + block[hm.end(1):]
    text = text[:m.start()] + block + text[end:]
    cnt = len(re.findall(r"create_state", text[m.start():m.start()] + block))
    print(state, "create_states now:", cnt)
LEDGER.write_text(text, encoding="utf-8-sig", newline="\n")

ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
for row in ov["states"]:
    if row["state"] in CITIES:
        city, holder = CITIES[row["state"]]
        owners = [g["owner"] for g in row["groups"]]
        if "SHU" not in owners:
            row["groups"].append({"owner": "SHU", "owned_provinces": [city]})
        else:
            for g in row["groups"]:
                if g["owner"] == "SHU" and not g["owned_provinces"]:
                    g["owned_provinces"] = [city]
        print(row["state"], "override groups:", [(g["owner"], len(g["owned_provinces"])) for g in row["groups"]])
OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

r = subprocess.run([
    "python", "-X", "utf8", "tools/build_state_history.py",
    "--baseline", "data/baseline/vic3-1.13.11.json",
    "--game-root", "E:/SteamLibrary/steamapps/common/Victoria 3/game",
    "--overrides", "data/scenario/ownership_overrides.json",
    "--template", "yongchang_world/common/history/states/00_states.txt",
    "--output", "yongchang_world/common/history/states/00_states.txt",
    "--scenario-root", "data/scenario",
], capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("regen rc:", r.returncode, (r.stdout or r.stderr)[-200:])
