# ONE deterministic world-fix pass from the committed HEAD state.
# Restores the two data files from git (read-only git show, not checkout),
# then applies the ownership fixes, regenerates the ledger, post-processes
# the basin cities, and rewrites pops/ARK/dynamic-names/flags.
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
TPL_GAME = GAME / "common/history/states/00_states.txt"

# ---------- restore both files from HEAD ----------
for rel in ("yongchang_world/common/history/states/00_states.txt",
            "data/scenario/ownership_overrides.json"):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True,
                       cwd=ROOT, text=True, encoding="utf-8", errors="ignore")
    assert r.returncode == 0, (rel, r.stderr)
    Path(ROOT / rel).write_text(r.stdout.lstrip("﻿"), encoding="utf-8", newline="\n")
print("restored ledger + overrides from HEAD")

# ---------- ownership fixes ----------
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
ov = json.loads(OV_PATH.read_text(encoding="utf-8-sig"))
by_state = {row["state"]: row for row in ov["states"]}
tpl = TPL_GAME.read_text(encoding="utf-8-sig")
all_states = sorted(baseline["state_regions"].keys())
positions = []
for state in all_states:
    m = re.search(rf"(?m)^\s*s:{re.escape(state)}\s*=", tpl)
    if m:
        positions.append((m.start(), state))
positions.sort()
tpl_blocks = {}
for idx, (start, state) in enumerate(positions):
    end = positions[idx + 1][0] if idx + 1 < len(positions) else len(tpl)
    tpl_blocks[state] = tpl[start:end]

for state, new_owner in DESIGN.items():
    block = tpl_blocks[state]
    groups = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        plist = re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close])
        owner = cm.group(1)
        groups.append({"owner": new_owner if owner == "CHI" else owner, "owned_provinces": plist})
    flat = [p for g in groups for p in g["owned_provinces"]]
    assert len(flat) == len(set(flat)) and set(flat) == set(baseline["state_regions"][state]), state
    if state in by_state:
        by_state[state]["groups"] = groups
    else:
        ov["states"].append({"state": state, "groups": groups})
    print(f"ownership {state} -> {[(g['owner'], len(g['owned_provinces'])) for g in groups][:3]}...")

# MANDALAY: every create_state block -> ARK
mrow = by_state["STATE_MANDALAY"]
for g in mrow["groups"]:
    g["owner"] = "ARK"
print("ownership STATE_MANDALAY -> ARK x", len(mrow["groups"]))
OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------- regenerate the ledger from the HEAD ledger as template ----------
r = subprocess.run([
    "python", "-X", "utf8", "tools/build_state_history.py",
    "--baseline", "data/baseline/vic3-1.13.11.json",
    "--game-root", str(GAME),
    "--overrides", "data/scenario/ownership_overrides.json",
    "--template", "yongchang_world/common/history/states/00_states.txt",
    "--output", "yongchang_world/common/history/states/00_states.txt",
    "--scenario-root", "data/scenario",
], capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
assert r.returncode == 0, (r.stdout, r.stderr)
print("ledger regenerated")

# ---------- basin city provinces -> new SHU create_state blocks ----------
CITIES = {"STATE_SICHUAN": ("x60E0D5", "KAM"), "STATE_YUNNAN": ("x78DC66", "LJG")}
ledger = LEDGER.read_text(encoding="utf-8-sig")
for state, (city, holder) in CITIES.items():
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", ledger)
    nxt = re.search(rf"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", ledger[m.end():])
    end = m.end() + (nxt.start() if nxt else len(ledger) - m.end())
    block = ledger[m.start():end]
    assert "c:SHU" not in block, f"{state} already has a SHU block"
    hm = re.search(rf"country = c:{holder}\s*\n\s*owned_provinces\s*=\s*\{{([^}}]*)\}}", block)
    assert hm, (state, holder)
    assert city in hm.group(1).split(), (state, city)
    new_list = " ".join(p for p in hm.group(1).split() if p != city)
    block = block[:hm.start(1)] + new_list + block[hm.end(1):]
    lines = block.split("\n")
    insert_at = 1 + next(i for i, l in enumerate(lines[1:], 1) if "create_state" in l)
    lines.insert(insert_at, f"\t\tcreate_state = {{\n\t\t\tcountry = c:SHU\n\t\t\towned_provinces = {{ {city} }}\n\t\t}}")
    block = "\n".join(lines)
    ledger = ledger[:m.start()] + block + ledger[end:]
    print(f"basin {state}: {city} -> SHU")
LEDGER.write_text(ledger, encoding="utf-8-sig", newline="\n")
print("STAGE A COMPLETE")
