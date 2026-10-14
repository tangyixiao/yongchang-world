import sqlite3

con = sqlite3.connect("file:D:/Documents/Paradox Interactive/Victoria 3/launcher-v2.sqlite?mode=ro", uri=True)
out = []
cols = [r[1] for r in con.execute("PRAGMA table_info(mods)")]
out.append(f"mods cols: {cols}")
for row in con.execute("SELECT * FROM mods").fetchall():
    out.append(f"mod row: {row}")
for row in con.execute("SELECT * FROM playsets").fetchall():
    out.append(f"playset: {row}")
pcols = [r[1] for r in con.execute("PRAGMA table_info(playsets_mods)")]
out.append(f"playsets_mods cols: {pcols}")
for row in con.execute("SELECT * FROM playsets_mods").fetchall():
    out.append(f"playset_mod: {row}")
con.close()
text = "\n".join(out) or "(empty)"
open("artifacts/automation/playsets_dump.txt", "w", encoding="utf-8").write(text)
print(text[:3000])
