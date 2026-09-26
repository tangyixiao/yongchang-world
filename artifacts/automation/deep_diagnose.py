# Deep-dive: whose names are 大顺礼制国/大蒙古国/吐蕃承统国; what vanilla ARA/LAD/MNP are;
# did the user run a stale installed copy; who owns the north-China states.
import json
import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. mod localizations for mystery names ===")
for needle in ("礼制", "大蒙古国", "承统", "脆弱的统一", "义和团", "隐秘的王国"):
    hits = []
    for path in (ROOT / "yongchang_world/localization").rglob("*.yml"):
        for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if needle in line:
                hits.append(f"{path.name}:{i}: {line.strip()[:80]}")
    print(f"[{needle}] -> {hits[:4] if hits else 'NOT IN MOD LOC'}")

print("=== 2. vanilla names for contested tags ===")
# vanilla chinese loc for tags
van_loc = GAME / "localization/simp_chinese"
tag_names = {}
for path in van_loc.glob("*.yml"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"^\s*([A-Z]{3}):0\s+\"([^\"]+)\"", text, re.M):
        tag_names.setdefault(m.group(1), m.group(2))
for tag in ("ARA", "LAD", "MNP", "MGL", "KJU", "MJU", "GJU", "QNG", "QIN", "QNG", "CHI"):
    print(tag, "->", tag_names.get(tag, "(no vanilla loc)"))

print("=== 3. installed mod copy staleness ===")
user_mod = Path("D:/Documents/Paradox Interactive/Victoria 3/mod")
if user_mod.is_dir():
    for entry in sorted(user_mod.iterdir()):
        print("  ", entry.name, "(dir)" if entry.is_dir() else "")
        if entry.is_dir() and "yongchang" in entry.name.lower():
            for probe in ("events/ywc_southwest_events.txt", "events/ywc_hegemony_events.txt",
                          "events/ywc_large_campaign_events.txt", "events/ywc_shu_jhg_events.txt"):
                p = entry / probe
                print("     ", probe, "EXISTS" if p.exists() else "MISSING",
                      p.stat().st_mtime if p.exists() else "")
else:
    print("  no user mod dir")

print("=== 4. state ownership: who owns china in mod states file ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
owners = {}
for m in re.finditer(r"c:([A-Z]{3})", states_text):
    owners[m.group(1)] = owners.get(m.group(1), 0) + 1
print("c:TAG occurrences in 00_states.txt:", sorted(owners.items(), key=lambda kv: -kv[1])[:20])
print("STATE blocks:", len(re.findall(r"(?m)^\s*s:", states_text)), "set_owner lines:", len(re.findall(r"set_owner", states_text)))
print("QNG/QING/CHI referenced as owner?", [t for t in ("QNG", "QIN", "QING", "CHI") if t in owners])
