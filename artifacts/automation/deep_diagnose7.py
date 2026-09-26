# Round 8: last unknowns before the fix package.
import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. who_inherits_china loc + vanilla je_ refs in mod ===")
for path in (ROOT / "yongchang_world/localization").rglob("*.yml"):
    text = path.read_text(encoding="utf-8-sig")
    for line in text.splitlines():
        if "who_inherits_china" in line and ":0" in line:
            print("  ", line.strip()[:90])
            break
refs = set()
for path in (ROOT / "yongchang_world").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"add_journal_entry\s*=\s*\{\s*type\s*=\s*(je_[A-Za-z0-9_]+)", text):
        refs.add((path.name, m.group(1)))
print("  vanilla journal types referenced by mod:", sorted(refs))

print("=== 2. split states: full owner lists ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", states_text)
starts = [(m.group(1), m.start()) for m in blocks]
for idx, (name, start) in enumerate(starts):
    if name in ("STATE_SICHUAN", "STATE_YUNNAN", "STATE_ASSAM", "STATE_SHAN_STATES",
                "STATE_MANDALAY", "STATE_KASHMIR", "STATE_LHASA", "STATE_SOUTHERN_MANCHURIA",
                "STATE_HINGGAN", "STATE_AMUR", "STATE_ALXA", "STATE_TUVA", "STATE_ALTAI", "STATE_JETISY"):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(states_text)
        block = states_text[start:end]
        tags = re.findall(r"country = c:([A-Z]{3})", block)
        print(f"  {name}: owners={tags}")

print("=== 3. vanilla cultures for arakan/burma region ===")
cult = (GAME / "common/cultures").rglob("*.txt")
found = []
for path in cult:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"(?m)^\s*(rakhine|arakanese|burmese|shan|karen|kachin|manipur|meitei|assamese|ahom|ladakhi|tibetan)\s*=", text):
        found.append(m.group(1))
print("  matching vanilla cultures:", sorted(set(found)))

print("=== 4. core flag/coa pattern (SHU) ===")
fd = (ROOT / "yongchang_world/common/flag_definitions").rglob("*.txt")
for path in fd:
    text = path.read_text(encoding="utf-8-sig")
    m = re.search(r"SHU\s*=\s*\{.*?\n\}", text, re.S)
    if m:
        print("  flag_definitions:", m.group(0)[:400])
coa = (ROOT / "yongchang_world/common/coat_of_arms").rglob("*.txt")
for path in coa:
    text = path.read_text(encoding="utf-8-sig")
    m = re.search(r"YWC_SHU\s*=\s*\{.*?\n\}", text, re.S)
    if m:
        print("  coat_of_arms:", m.group(0)[:600])
        break

print("=== 5. how do country definitions reference flags (SHU block) ===")
for path in (ROOT / "yongchang_world/common/country_definitions").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig")
    m = re.search(r"SHU\s*=\s*\{[^{}]*\{[^{}]*\}[^{}]*\}", text, re.S)
    if m:
        print("  ", m.group(0)[:500])
        break
