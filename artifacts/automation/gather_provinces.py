# Gather: province lists for the states to fix; cultures used in existing pops.
import json
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
ROOT = Path(".")

NEED = ["STATE_SICHUAN", "STATE_YUNNAN", "STATE_SOUTHERN_MANCHURIA", "STATE_AMUR",
        "STATE_HINGGAN", "STATE_ALXA", "STATE_TUVA", "STATE_ALTAI", "STATE_JETISY",
        "STATE_MANDALAY", "STATE_ASSAM", "STATE_SHAN_STATES", "STATE_KASHMIR"]
provinces = {}
for name in NEED:
    path = GAME / f"map_data/state_regions/{name}.txt"
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    m = re.search(r"provinces\s*=\s*\{([^}]*)\}", text)
    plist = re.findall(r"x[0-9A-Fa-f]+", m.group(1)) if m else []
    provinces[name] = plist
    print(f"{name}: {len(plist)} provinces")

# what the ledger already assigns
ov = json.load(open("data/scenario/ownership_overrides.json", encoding="utf-8"))
for row in ov["states"]:
    if row["state"] in provinces:
        assigned = []
        for g in row["groups"]:
            assigned += g.get("owned_provinces", [])
        remainder = [p for p in provinces[row["state"]] if p not in assigned]
        print(f"{row['state']}: groups={[(g['owner'], len(g.get('owned_provinces', []))) for g in row['groups']]} "
              f"total={len(provinces[row['state']])} assigned={len(assigned)} remainder={len(remainder)}")
        if row["state"] in ("STATE_SICHUAN", "STATE_YUNNAN"):
            print("   remainder:", remainder[:200])

# cultures used in existing mod pops
cults = set()
for path in (ROOT / "yongchang_world/common/history/pops").glob("*.txt"):
    cults |= set(re.findall(r"culture\s*=\s*([a-z_]+)", path.read_text(encoding="utf-8-sig", errors="ignore")))
print("cultures in mod pops:", sorted(cults))

# northeast + inner asia pops content (style + tags)
print("--- ywc_northeast_pops.txt ---")
print((ROOT / "yongchang_world/common/history/pops/ywc_northeast_pops.txt").read_text(encoding="utf-8-sig")[:700])
print("--- ywc_inner_asia_pops.txt head ---")
print((ROOT / "yongchang_world/common/history/pops/ywc_inner_asia_pops.txt").read_text(encoding="utf-8-sig")[:500])
