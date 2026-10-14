# Round 3: decisive facts.
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. was 脆弱的统一 ever a mod journal? (stale-copy test) ===")
r = subprocess.run(["git", "log", "--oneline", "-S", "脆弱的统一", "--", "yongchang_world"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
print(r.stdout or "(never in git history)")
r2 = subprocess.run(["git", "log", "--oneline", "-3", "--", "yongchang_world/common/journal_entries"],
                    capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("recent journal commits:", r2.stdout)

print("=== 2. full dynamic names file ===")
text = (ROOT / "yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt").read_text(encoding="utf-8-sig")
print(text[1500:3400])

print("=== 3. who owns china states in the ledger ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
# find the create_state country for each china state
for state in ("STATE_BEIJING", "STATE_ZHILI", "STATE_SHANDONG", "STATE_SHANXI", "STATE_HENAN",
              "STATE_JIANGSU", "STATE_HUBEI", "STATE_HUNAN", "STATE_FUJIAN", "STATE_GUANGDONG",
              "STATE_GUANGXI", "STATE_GUIZHOU", "STATE_YUNNAN", "STATE_SICHUAN", "STATE_LHASA",
              "STATE_SOUTHERN_MANCHURIA", "STATE_NORTHERN_MANCHURIA", "STATE_OUTER_MANCHURIA",
              "STATE_LIAONING", "STATE_JILIN", "STATE_HEILONGJIANG"):
    m = re.search(rf"s:{state} = \{{(.*?)\n\s*\}}\n", states_text, re.S)
    if not m:
        print(f"{state}: NOT IN LEDGER (keeps vanilla owner)")
        continue
    block = m.group(1)
    owners = re.findall(r"country = c:([A-Z]{3})", block)
    print(f"{state}: create_state owners -> {owners}")

print("=== 4. vanilla tag identities (correct loc pattern) ===")
hits = {}
for path in (GAME / "localization/simp_chinese").glob("*.yml"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"\b(ARA|LAD|MNP|MGL|KJU|MJU|GJU|CHI):0\s+\"([^\"]{1,30})\"", text):
        hits.setdefault(m.group(1), m.group(2))
for tag in ("ARA", "LAD", "MNP", "MGL", "KJU", "MJU", "GJU", "CHI"):
    print(tag, "->", hits.get(tag))
# also search by chinese name
for name in ("阿拉伯", "若开", "拉达克", "曼尼普尔", "蒙古", "大清"):
    m = re.search(rf"\b([A-Z]{{3}}):0\s+\"{name}\"", " ".join(
        p.read_text(encoding="utf-8-sig", errors="ignore") for p in (GAME / "localization/simp_chinese").glob("*.yml")))
    print(f"name[{name}] -> tag {m.group(1) if m else '?'}")
