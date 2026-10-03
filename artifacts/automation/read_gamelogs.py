from pathlib import Path
import re

LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")
for name in ("game.log", "debug.log", "game.1.log", "debug.1.log"):
    p = LOGS / name
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if ("ywc_je" in low or "journal" in low and "ywc" in low or "content_starts" in low
                or "ywc_china_pops" in low or "database" in low and "ywc" in low):
            hits.append(line[:180])
    print(f"=== {name}: {len(hits)} hits ===")
    seen = set()
    for h in hits[:25]:
        if h not in seen:
            seen.add(h)
            print("  ", h)
