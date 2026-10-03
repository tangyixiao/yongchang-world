# Round 4: which copy does the playset mount; timeline design for the north;
# vanilla dynamic names hijacking reused tags; pops scale.
import re
import sqlite3
from pathlib import Path

ROOT = Path(".")
GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")

print("=== 1. playset mod paths (launcher db, read-only) ===")
db = Path("D:/Documents/Paradox Interactive/Victoria 3/launcher-v2.sqlite")
if db.exists():
    uri = f"file:{db.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute("SELECT name, value FROM settings WHERE name LIKE '%mod%'").fetchall()
        print("settings:", rows[:5])
        try:
            mods = con.execute("SELECT id, dirPath FROM mods").fetchall()
            print("mods table:", mods[:10])
        except Exception as e:
            print("mods table err:", e)
        try:
            ps = con.execute("SELECT id, name, isActive FROM playsets").fetchall()
            print("playsets:", ps)
        except Exception as e:
            print("playsets err:", e)
    finally:
        con.close()
else:
    print("no launcher db")

print("=== 2. timeline: what happened to the northern Qing mainland? ===")
for name in ("2026-09-04-01-1644至1836历史年表.md",):
    path = ROOT / "docs/superpowers/specs" / name
    if path.exists():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"大清|入关|北直隶|直隶|北京|清廷|北清", line):
                print(f"{i}: {line.strip()[:110]}")

print("=== 3. regional plan: intended NE / north ownership ===")
path = ROOT / "docs/superpowers/plans/2026-09-04-02-区域场景扩展.md"
if path.exists():
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"东北|满洲|CHI|大清|直隶|北清|辽宁|吉林|黑龙江", line):
            print(f"{i}: {line.strip()[:110]}")

print("=== 4. vanilla dynamic names for reused tags ===")
vdir = GAME / "common/dynamic_country_names"
for tag in ("TIB", "MGL", "YRK", "ARA", "LAD", "MNP", "KHO", "KOK"):
    found = []
    for path in vdir.glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if re.search(rf"^{tag}\s*=\s*\{{", text, re.M):
            m = re.search(rf"{tag}\s*=\s*\{{(.*?)\n\}}", text, re.S)
            names = re.findall(r"name\s*=\s*([A-Za-z0-9_]+)", m.group(1)) if m else []
            found = names
            break
    print(tag, "-> dynamic names:", found[:6])

print("=== 5. southwest pops scale ===")
pops = (ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt").read_text(encoding="utf-8-sig")
print("size:", len(pops), "bytes")
print(pops[:900])
