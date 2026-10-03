from pathlib import Path

ROOT = Path(".")
p = ROOT / "yongchang_world/common/on_actions/ywc_startup_hooks.txt"
print("=== ywc_startup_hooks.txt ===")
print(p.read_text(encoding="utf-8-sig"))

hits = []
for path in (ROOT / "yongchang_world/common/history/buildings").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    if "state_building_port_max_level_add" in text:
        for i, line in enumerate(text.splitlines(), 1):
            if "state_building_port_max_level_add" in line:
                hits.append(f"{path.name}:{i}: {line.strip()[:80]}")
print("=== port modifier hits ===")
print("\n".join(hits) or "(none)")

for name in ("11_east_asia", "09_central_asia", "14_siberia", "05_north_america", "10_india", "12_indonesia", "13_australasia"):
    text = (ROOT / "yongchang_world/common/history/pops" / f"{name}.txt").read_text(encoding="utf-8-sig")
    chi = len(re.findall(r"region_state:CHI", text))
    rus = len(re.findall(r"region_state:RUS", text))
    print(f"{name}: region_state:CHI x{chi}, region_state:RUS x{rus}")
