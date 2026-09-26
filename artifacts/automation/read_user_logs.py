# Read the user's most recent game session logs: errors, mounted mods, journal issues.
from pathlib import Path
import re

LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")
print("log dir exists:", LOGS.is_dir())
if LOGS.is_dir():
    for p in sorted(LOGS.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
        print(f"  {p.name}  mtime={p.stat().st_mtime:.0f}  size={p.stat().st_size}")

err = LOGS / "error.log"
if err.exists():
    text = err.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    print(f"\n=== error.log: {len(lines)} lines ===")
    # categorize
    cats = {}
    for line in lines:
        key = line.split(":")[0][:60] if ":" in line else line[:60]
        cats[key] = cats.get(key, 0) + 1
    for key, count in sorted(cats.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {count:5}x  {key}")
    ywc = [line for line in lines if "ywc" in line.lower()]
    print(f"\n=== ywc-related lines: {len(ywc)} ===")
    for line in ywc[:40]:
        print("  ", line[:200])

dbg = LOGS / "debug.log"
if dbg.exists():
    text = dbg.read_text(encoding="utf-8", errors="ignore")
    mounts = [line for line in text.splitlines() if "Mounted" in line or "yongchang" in line.lower()]
    print(f"\n=== debug.log mounts ===")
    for line in mounts[:10]:
        print("  ", line[:200])
