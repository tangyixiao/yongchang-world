# Recovery: rebuild SICHUAN/YUNNAN/MANDALAY override rows EXACTLY from the
# shipped ledger (using the generator's own state_blocks parser), fix the
# catalog BOM, and verify the generator round-trips.
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
sys.path.insert(0, ".")
from tools.build_state_history import state_blocks

LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"

baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
ledger = LEDGER.read_text(encoding="utf-8-sig")
blocks = state_blocks(ledger, baseline)
ov = json.loads(OV_PATH.read_text(encoding="utf-8-sig"))

target_owners = {"STATE_SICHUAN": "RKN", "STATE_YUNNAN": None, "STATE_MANDALAY": "RKN"}
by_state = {row["state"]: row for row in ov["states"]}
for state in target_owners:
    block = blocks[state]
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        plist = re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])
        owner = cm.group(1)
        if target_owners[state]:
            owner = target_owners[state]
        groups.append({"owner": owner, "owned_provinces": plist})
    flat = [p for g in groups for p in g["owned_provinces"]]
    assert len(flat) == len(set(flat)) and set(flat) == set(baseline["state_regions"][state]), state
    by_state[state]["groups"] = groups
    print(state, "->", [(g["owner"], len(g["owned_provinces"])) for g in groups])

OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("overrides recovered")

# strip any BOM the catalog picked up
cat = ROOT / "data/content/southwest_event_catalog.json"
raw = cat.read_text(encoding="utf-8-sig")
cat.write_text(raw.lstrip("﻿"), encoding="utf-8", newline="\n")
print("catalog BOM stripped")

r = subprocess.run(["python", "-X", "utf8", "tools/build_southwest_content.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print("sw regen:", r.returncode, (r.stdout or r.stderr)[-120:])

# verify the state generator round-trips the shipped file
r = subprocess.run([
    "python", "-X", "utf8", "tools/build_state_history.py",
    "--baseline", "data/baseline/vic3-1.13.11.json",
    "--game-root", "E:/SteamLibrary/steamapps/common/Victoria 3/game",
    "--overrides", "data/scenario/ownership_overrides.json",
    "--template", "yongchang_world/common/history/states/00_states.txt",
    "--output", "artifacts/automation/roundtrip_states.txt",
    "--scenario-root", "data/scenario",
], capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print("roundtrip rc:", r.returncode, (r.stdout or r.stderr)[-200:])
shipped = LEDGER.read_bytes()
made = Path("artifacts/automation/roundtrip_states.txt").read_bytes()
print("roundtrip identical:", shipped == made)
