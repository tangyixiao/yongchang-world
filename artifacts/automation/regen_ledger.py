# Restore SICHUAN/YUNNAN fragment groups, regenerate the ledger from the
# current mod ledger as template, then move the basin city provinces
# (成都 x60E0D5 / 昆明 x78DC66) into new SHU create_state blocks.
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
CITIES = {"STATE_SICHUAN": ("x60E0D5", "KAM"), "STATE_YUNNAN": ("x78DC66", "LJG")}

ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
for row in ov["states"]:
    if row["state"] in CITIES:
        city, holder = CITIES[row["state"]]
        row["groups"] = [g for g in row["groups"] if g["owner"] != "SHU"]
        restored = False
        for g in row["groups"]:
            if g["owner"] == holder:
                if city not in g["owned_provinces"]:
                    g["owned_provinces"].append(city)
                restored = True
        print(row["state"], "->", [(g["owner"], len(g["owned_provinces"])) for g in row["groups"]], "restored:", restored)
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

text = LEDGER.read_text(encoding="utf-8-sig")
for state, (city, holder) in CITIES.items():
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", text)
    assert m, state
    nxt = re.search(rf"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", text[m.end():])
    block_end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    block = text[m.start():block_end]
    # remove the city from the holder's owned_provinces
    hm = re.search(rf"country = c:{holder}\s*\n\s*owned_provinces\s*=\s*\{{([^}}]*)\}}", block)
    assert hm, (state, holder)
    new_list = " ".join(p for p in hm.group(1).split() if p != city)
    block = block[:hm.start(1)] + new_list + block[hm.end(1):]
    # insert the SHU create_state right after the state opening line
    lines = block.split("\n")
    insert_at = 1 + next(i for i, l in enumerate(lines[1:], 1) if "create_state" in l)
    lines.insert(insert_at, f"\t\tcreate_state = {{\n\t\t\tcountry = c:SHU\n\t\t\towned_provinces = {{ {city} }}\n\t\t}}")
    block = "\n".join(lines)
    text = text[:m.start()] + block + text[block_end:]
    print(f"{state}: basin city {city} -> SHU")
LEDGER.write_text(text, encoding="utf-8-sig", newline="\n")
print("ledger post-processed")
