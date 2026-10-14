import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. vanilla history/countries: ?= vs = usage ===")
qmark = eq = 0
qfiles = eqfiles = 0
for path in (GAME / "common/history/countries").glob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    q = len(re.findall(r"c:[A-Z]{3}\s*\?=", text))
    e = len(re.findall(r"c:[A-Z]{3}\s*=[^{]", text))
    qmark += q
    eq += e
    if q:
        qfiles += 1
    if e:
        eqfiles += 1
print(f"  vanilla: ?= count {qmark} ({qfiles} files), plain = count {eq} ({eqfiles} files)")

print("=== 2. content_starts head ===")
text = (ROOT / "yongchang_world/common/history/countries/ywc_content_starts.txt").read_text(encoding="utf-8-sig")
print(text[:400])

print("=== 3. vanilla: who else adds je_warlord_china / its trigger ===")
for path in (GAME / "common/history/countries").glob("*china*"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if "je_warlord_china" in text:
        print("  vanilla file:", path.name)
for path in (GAME / "common/on_actions").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if "je_warlord_china" in text:
        print("  vanilla on_action:", path.name)

print("=== 4. mod pops 11_east_asia head (lines 1-80) ===")
lines = (ROOT / "yongchang_world/common/history/pops/11_east_asia.txt").read_text(encoding="utf-8-sig").splitlines()
print("\n".join(lines[:80]))

print("=== 5. 09_central_asia lines 405-430 ===")
lines9 = (ROOT / "yongchang_world/common/history/pops/09_central_asia.txt").read_text(encoding="utf-8-sig").splitlines()
print("\n".join(lines9[404:430]))

print("=== 6. port modifier ===")
for path in (ROOT / "yongchang_world/common/history/buildings").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if "state_building_port_max_level_add" in text:
        print("  ", path.name)
