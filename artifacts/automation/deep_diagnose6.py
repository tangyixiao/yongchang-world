# Round 6: full coverage audit — pops gaps, state owners, dynamic name values, vanilla tag names.
import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. all ywc_dyn_* loc values ===")
loc = (ROOT / "yongchang_world/localization/simp_chinese/ywc_content_l_simp_chinese.yml").read_text(encoding="utf-8-sig")
for line in loc.splitlines():
    if "ywc_dyn_" in line:
        print("  ", line.strip()[:80])

print("=== 2. ledger: every china/ne state and its create_state owner ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
# robust: for each s:STATE block, take the first `country = c:XXX` inside
blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", states_text)
starts = [(m.group(1), m.start()) for m in blocks]
owners = {}
for idx, (name, start) in enumerate(starts):
    end = starts[idx + 1][1] if idx + 1 < len(starts) else len(states_text)
    block = states_text[start:end]
    m = re.search(r"country = c:([A-Z]{3})", block)
    owners[name] = m.group(1) if m else "(none)"
china_states = [s for s in owners if re.search(
    r"BEIJING|ZHILI|SHANDONG|SHANXI|SHAANXI|SHENSI|HENAN|HUBEI|HUNAN|JIANGSU|ANHUI|ZHEJIANG|JIANGXI|FUJIAN|"
    r"GUANGDONG|GUANGXI|GUIZHOU|YUNNAN|SICHUAN|LHASA|TIBET|GANSU|KANSU|NINGXIA|QINGHAI|KOKONOR|"
    r"MANCHURIA|LIAONING|JILIN|HEILONGJIANG|AMUR|INNER_MONGOLIA|OUTER_MONGOLIA|MONGOLIA|HULUN|"
    r"TAIWAN|HAINAN|Formosa", s)]
for state in sorted(china_states):
    print(f"  {state}: {owners[state]}")
chi_states = [s for s, o in owners.items() if o == "CHI"]
print("  CHI-owned states in ledger:", chi_states)
print("  total states in ledger:", len(owners))

print("=== 3. pops coverage vs split states ===")
pops_files = list((ROOT / "yongchang_world/common/history/pops").glob("*.txt"))
pop_region_states = set()
for path in pops_files:
    text = path.read_text(encoding="utf-8-sig")
    pop_region_states |= set(re.findall(r"region_state:([A-Z]{3})", text))
ledger_region_states = set()
for name, start in starts:
    end = starts[idx + 1][1] if False else None
# derive region states from ledger: countries = c:TAG lines
ledger_countries = set(re.findall(r"country = c:([A-Z]{3})", states_text))
print("pops region_state tags:", sorted(pop_region_states))
print("ledger create_state tags:", sorted(ledger_countries))
print("ledger tags WITHOUT pops:", sorted(ledger_countries - pop_region_states))

print("=== 4. vanilla names for ARA/LAD/MNP/MGL via countries loc file ===")
cfile = GAME / "localization/simp_chinese/countries_l_simp_chinese.yml"
if cfile.exists():
    text = cfile.read_text(encoding="utf-8-sig")
    for tag in ("ARA", "LAD", "MNP", "MGL", "CHI", "QNG"):
        m = re.search(rf"^\s*{tag}:0\s+\"([^\"]+)\"", text, re.M)
        print(f"  {tag}: {m.group(1) if m else '?'}")
else:
    print("  countries loc file not found; candidates:")
    for p in sorted((GAME / "localization/simp_chinese").glob("*countr*")):
        print("   ", p.name)
