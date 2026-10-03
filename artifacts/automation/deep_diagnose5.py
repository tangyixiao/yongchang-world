# Round 5: vanilla dynamic names for reused tags, pops scale, timeline design intent.
import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. vanilla dynamic_country_names for reused/new-adjacent tags ===")
vdir = GAME / "common/dynamic_country_names"
for tag in ("TIB", "MGL", "YRK", "ARA", "LAD", "MNP", "KHO", "KOK", "SIK", "KAL"):
    found = None
    for path in vdir.glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        m = re.search(rf"(?m)^\s*{tag}\s*=\s*\{{", text)
        if m:
            block = text[m.start():m.start() + 2000]
            found = re.findall(r"name\s*=\s*([A-Za-z0-9_]+)", block)[:8]
            break
    print(tag, "->", found)

print("=== 2. vanilla country name loc: find the right file ===")
for path in sorted((GAME / "localization/simp_chinese").glob("*.yml")):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if "大清" in text:
        m = re.search(r"\b([A-Z]{3,4}):0\s+\"大清\"", text)
        idx = text.find("大清")
        print(f"{path.name}: 大清 near -> {text[max(0,idx-60):idx+20]!r}")
        break

print("=== 3. timeline: the north after 1644 ===")
path = ROOT / "docs/superpowers/specs/2026-09-04-01-1644至1836历史年表.md"
lines = path.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines, 1):
    if re.search(r"清|满|北|辽|吉|黑|蒙", line) and i < 200:
        print(f"{i}: {line.strip()[:100]}")

print("=== 4. southwest pops sample ===")
pops = (ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt").read_text(encoding="utf-8-sig")
print("bytes:", len(pops))
print(pops[:1200])
