# Round 2: installed-copy freshness, states ownership syntax, vanilla tag identities,
# dynamic-name triggers.
import json
import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
USER_MOD = Path("D:/Documents/Paradox Interactive/Victoria 3/mod/yongchang_world")

print("=== 1. installed copy: journal files + loc probes ===")
if USER_MOD.is_dir():
    jr = USER_MOD / "common/journal_entries"
    files = sorted(p.name for p in jr.glob("*.txt")) if jr.is_dir() else []
    print("installed journal_entries:", files)
    loc_text = ""
    for p in (USER_MOD / "localization/simp_chinese").glob("*.yml"):
        loc_text += p.read_text(encoding="utf-8-sig", errors="ignore")
    for needle in ("茶马引盐", "天命", "脆弱的统一", "隐秘的王国", "义和团"):
        print(f"  installed loc has [{needle}]:", needle in loc_text)
else:
    print("  no installed copy")

print("=== 2. states file: actual ownership syntax + owners of china states ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
print(states_text[:600])
# count owner-ish patterns
for pat in (r"set_owner\s*=\s*c:([A-Z]{3})", r"owner\s*=\s*c:([A-Z]{3})", r"add_owner\s*=", r"region_state"):
    hits = re.findall(pat, states_text)
    print(pat, "->", len(hits), sorted(set(hits))[:15] if hits and pat.endswith("([A-Z]{3})\")") else "")
# which states exist in the file
state_names = re.findall(r"(?m)^\s*s:([A-Z_]+)", states_text)
print("states covered:", len(state_names), "unique:", len(set(state_names)))
china_states = [s for s in set(state_names) if any(k in s for k in ("ZHILI", "SHANDONG", "SHANXI", "SHAANXI", "HENAN", "HUBEI", "HUNAN", "JIANGSU", "ANHUI", "ZHEJIANG", "JIANGXI", "FUJIAN", "GUANGDONG", "GUANGXI", "GUIZHOU", "YUNNAN", "SICHUAN", "LHASA", "BEIJING", "CHAHAR", "MANCHURIA", "LIAONING", "JILIN", "HEILONGJIANG", "INNER", "MONGOLIA"))]
print("china-related states in file:", sorted(china_states))

print("=== 3. vanilla identities of contested tags (search vanilla loc broadly) ===")
def find_tag_name(tag):
    for path in (GAME / "localization/simp_chinese").glob("*.yml"):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        m = re.search(rf"^\s*{tag}:0\s+\"([^\"]+)\"", text, re.M)
        if m:
            return m.group(1)
    return None
for tag in ("ARA", "LAD", "MNP", "MGL", "KJU", "MJU", "GJU", "CHI", "QNG"):
    print(tag, "->", find_tag_name(tag))

print("=== 4. dynamic country name triggers ===")
for path in sorted((ROOT / "yongchang_world/common/dynamic_country_names").rglob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    print("---", path.name, len(text), "bytes")
    print(text[:1500])
