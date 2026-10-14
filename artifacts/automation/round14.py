from pathlib import Path
import re

ROOT = Path(".")
LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")

print("=== game.log/debug.log: ywc_je / journal_entries/ywc errors ===")
for name in ("game.log", "debug.log", "game.1.log", "debug.1.log"):
    p = LOGS / name
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    hits = [l for l in text.splitlines() if ("ywc_je" in l or ("journal_entries" in l and "ywc" in l.lower()))]
    seen = set()
    print(f"--- {name}: {len(hits)} hits ---")
    for h in hits[:15]:
        if h[:80] not in seen:
            seen.add(h[:80])
            print("  ", h[:170])

print("=== mod 11_east_asia: CHI-targeted state list ===")
text = (ROOT / "yongchang_world/common/history/pops/11_east_asia.txt").read_text(encoding="utf-8-sig")
states = re.findall(r"s:(STATE_[A-Z0-9_]+)", text)
print("states:", states)

print("=== 09/14 CHI-targeted states ===")
for name in ("09_central_asia", "14_siberia"):
    text = (ROOT / "yongchang_world/common/history/pops" / f"{name}.txt").read_text(encoding="utf-8-sig")
    print(name, re.findall(r"s:(STATE_[A-Z0-9_]+)", text))

print("=== port modifier location ===")
for path in (ROOT / "yongchang_world/common/history/buildings").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for i, line in enumerate(text.splitlines(), 1):
        if "state_building_port_max_level_add" in line:
            print(f"  {path.name}:{i}: {line.strip()[:100]}")
            break
