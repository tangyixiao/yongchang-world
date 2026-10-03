# THE deterministic world-fix pass. Restores the ledger + overrides from HEAD,
# then applies everything once, in the right order, with correct insertion.
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"

def restore(rel):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True,
                       cwd=ROOT, text=True, encoding="utf-8", errors="ignore")
    assert r.returncode == 0, (rel, r.stderr)
    body = r.stdout.lstrip("﻿")
    Path(ROOT / rel).write_text(body, encoding="utf-8", newline="\n")
    return body

ledger = restore("yongchang_world/common/history/states/00_states.txt")
restore("data/scenario/ownership_overrides.json")
ov = json.loads(OV_PATH.read_text(encoding="utf-8-sig"))
by_state = {row["state"]: row for row in ov["states"]}
baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))

DESIGN = {
    "STATE_SOUTHERN_MANCHURIA": "SHU",
    "STATE_AMUR": "AMR",
    "STATE_HINGGAN": "SOL",
    "STATE_ALXA": "KHO",
    "STATE_TUVA": "MGL",
    "STATE_ALTAI": "MGL",
    "STATE_JETISY": "GJU",
}

# --- A. seven CHI leftovers: retarget the CHI create_state owners in place ---
for state, new_owner in DESIGN.items():
    m = re.search(rf"(?m)^(\s*)s:{state}\s*=\s*\{{", ledger)
    assert m, state
    nxt = re.search(rf"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", ledger[m.end():])
    end = m.end() + (nxt.start() if nxt else len(ledger) - m.end())
    block = ledger[m.start():end]
    block = block.replace("country = c:CHI", f"country = c:{new_owner}")
    ledger = ledger[:m.start()] + block + ledger[end:]
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        groups.append({"owner": cm.group(1), "owned_provinces": re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])})
    if state in by_state:
        by_state[state]["groups"] = groups
    else:
        ov["states"].append({"state": state, "groups": groups})
    print(f"A {state} -> {new_owner} ({len(groups)} blocks)")

# --- B. MANDALAY: ARA -> RKN ---
m = re.search(r"(?m)^(\s*)s:STATE_MANDALAY\s*=\s*\{", ledger)
nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", ledger[m.end():])
end = m.end() + (nxt.start() if nxt else len(ledger) - m.end())
block = ledger[m.start():end].replace("country = c:ARA", "country = c:RKN")
ledger = ledger[:m.start()] + block + ledger[end:]
groups = []
for cm in re.finditer(r"country = c:([A-Z]{3})", block):
    p_open = block.find("owned_provinces = {", cm.start())
    p_close = block.find("}", p_open)
    groups.append({"owner": cm.group(1), "owned_provinces": re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])})
by_state["STATE_MANDALAY"]["groups"] = groups
print("B MANDALAY -> RKN")

# --- C. basin cities: insert a SHU create_state right after the state opening,
#        and drop the city from the holder's province list ---
CITIES = {"STATE_SICHUAN": ("x60E0D5", "KAM"), "STATE_YUNNAN": ("x78DC66", "LJG")}
for state, (city, holder) in CITIES.items():
    m = re.search(rf"(?m)^(\s*)s:{state}\s*=\s*\{{", ledger)
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", ledger[m.end():])
    end = m.end() + (nxt.start() if nxt else len(ledger) - m.end())
    block = ledger[m.start():end]
    indent = m.group(1) + "\t"
    inserted = (f"{indent}\tcreate_state = {{\n"
                f"{indent}\t\tcountry = c:SHU\n"
                f"{indent}\t\towned_provinces = {{ {city} }}\n"
                f"{indent}\t}}\n")
    first_create = re.search(r"(?m)^(.*)create_state = \{", block)
    # insert BEFORE the first create_state line, after the state opening
    line_start = block.rfind("\n", 0, first_create.start()) + 1
    block = block[:line_start] + inserted + block[line_start:]
    hm = re.search(rf"country = c:{holder}\s*\n\s*owned_provinces\s*=\s*\{{([^}}]*)\}}", block)
    assert hm and city in hm.group(1).split(), (state, holder, city)
    new_list = " ".join(p for p in hm.group(1).split() if p != city)
    block = block[:hm.start(1)] + new_list + block[hm.end(1):]
    ledger = ledger[:m.start()] + block + ledger[end:]
    print(f"C {state}: {city} -> SHU")

LEDGER.write_text(ledger, encoding="utf-8", newline="\n")

# --- D. overrides rows for the touched states (sorted-position slicing) ---
by_state = {row["state"]: row for row in ov["states"]}
positions = []
for m2 in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", ledger):
    positions.append((m2.start(), m2.group(1)))
positions.sort()
all_blocks = {}
for idx, (start, state) in enumerate(positions):
    end = positions[idx + 1][0] if idx + 1 < len(positions) else len(ledger)
    all_blocks[state] = ledger[start:end]
touched = list(DESIGN) + ["STATE_MANDALAY"] + list(CITIES)
for state in touched:
    block = all_blocks[state]
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        groups.append({"owner": cm.group(1), "owned_provinces": re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])})
    by_state[state]["groups"] = groups
    print("D", state, "->", [(g["owner"], len(g["owned_provinces"])) for g in groups])
OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("D overrides rows aligned with the shipped ledger")

# --- E. roundtrip verification ---
r = subprocess.run([
    "python", "-X", "utf8", "tools/build_state_history.py",
    "--baseline", "data/baseline/vic3-1.13.11.json",
    "--game-root", str(GAME),
    "--overrides", "data/scenario/ownership_overrides.json",
    "--template", "yongchang_world/common/history/states/00_states.txt",
    "--output", "artifacts/automation/roundtrip_states.txt",
    "--scenario-root", "data/scenario",
], capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print("E roundtrip rc:", r.returncode, (r.stdout or r.stderr)[-150:])
made = (ROOT / "artifacts/automation/roundtrip_states.txt").read_text(encoding="utf-8-sig")
shipped = LEDGER.read_text(encoding="utf-8-sig")
print("E roundtrip identical:", made == shipped)
