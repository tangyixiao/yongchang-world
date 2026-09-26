import re
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")

print("=== 1. script locations paired with create_pop errors ===")
lines = (LOGS / "error.log").read_text(encoding="utf-8", errors="ignore").splitlines()
for i, line in enumerate(lines):
    if "create_pop" in line:
        context = [l.strip()[:150] for l in lines[max(0, i - 2):i + 3]]
        print(" | ".join(context))
        print("--")

print("=== 2. vanilla add_journal_entry usage in common/history/countries ===")
count = 0
for path in (GAME / "common/history/countries").glob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    n = len(re.findall(r"add_journal_entry", text))
    if n:
        count += 1
        if count <= 5:
            print("  ", path.name, n)
print("  vanilla country-history files using add_journal_entry:", count)

print("=== 3. 脆弱的统一 source ===")
for path in (GAME / "localization/simp_chinese").glob("*.yml"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"(?m)^\s*(\w+):0?\s+\"脆弱的统一\"", text):
        print("  ", path.name, "->", m.group(1))
        break

print("=== 4. who adds that journal (vanilla) ===")
hits = []
for path in (GAME / "common/history/countries").glob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for m in re.finditer(r"add_journal_entry = \{\s*type = (\w+)", text):
        hits.append((path.name, m.group(1)))
print("  vanilla country-history journal adds:", hits[:10])

print("=== 5. mod on_actions ===")
for path in (ROOT / "yongchang_world/common/on_actions").rglob("*.txt"):
    print("---", path.name)
    print(path.read_text(encoding="utf-8-sig")[:900])

print("=== 6. settle_mid definition in effects file ===")
effects = (ROOT / "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text(encoding="utf-8-sig")
m = re.search(r"ywc_campaign_settle_mid = \{.*?\n\}", effects, re.S)
print(m.group(0)[:500] if m else "not found")
