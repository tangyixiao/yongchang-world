# Round 4b: playset mod paths via correct tables; rest of the checks.
import re
import sqlite3
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. playset mod paths ===")
db = Path("D:/Documents/Paradox Interactive/Victoria 3/launcher-v2.sqlite")
con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
try:
    for row in con.execute("SELECT id, dirPath, fileName FROM mods").fetchall():
        print("  mod:", row)
    for row in con.execute("SELECT playsetId, modId FROM playsets_mods").fetchall():
        print("  playset_mod:", row)
    for row in con.execute("SELECT id, name, isActive FROM playsets").fetchall():
        print("  playset:", row)
finally:
    con.close()

print("=== 2. timeline: northern Qing ===")
path = ROOT / "docs/superpowers/specs/2026-09-04-01-1644至1836历史年表.md"
for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if re.search(r"大清|入关|北直隶|直隶|北京|清廷|北清|南北", line):
        print(f"{i}: {line.strip()[:110]}")

print("=== 3. regional plan NE/north ===")
path = ROOT / "docs/superpowers/plans/2026-09-04-02-区域场景扩展.md"
for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if re.search(r"东北|满洲|CHI|大清|直隶|北清|辽宁|吉林|黑龙江|盛京", line):
        print(f"{i}: {line.strip()[:110]}")

print("=== 4. vanilla dynamic names for reused tags ===")
vdir = GAME / "common/dynamic_country_names"
for tag in ("TIB", "MGL", "YRK", "ARA", "LAD", "MNP", "KHO", "KOK", "KAM", "DER"):
    found = []
    for path in vdir.glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if re.search(rf"^\s*{tag}\s*=\s*\{{", text, re.M):
            m = re.search(rf"{tag}\s*=\s*\{{(.*?)\n\}}", text, re.S)
            found = re.findall(r"name\s*=\s*([A-Za-z0-9_]+)", m.group(1)) if m else ["(parse?)"]
            break
    print(tag, "->", found[:8])

print("=== 5. southwest pops scale ===")
pops = (ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt").read_text(encoding="utf-8-sig")
print("bytes:", len(pops))
print(pops[:800])
