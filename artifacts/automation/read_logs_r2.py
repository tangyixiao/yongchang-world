# Round 11: the user's latest session logs — pops/journal failures.
from pathlib import Path
import re

LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")
files = sorted(LOGS.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
print("newest logs:", [(p.name, int(p.stat().st_mtime)) for p in files[:4]])

err = LOGS / "error.log"
lines = err.read_text(encoding="utf-8", errors="ignore").splitlines()
print(f"error.log: {len(lines)} lines")

print("=== lines mentioning pops/china/journal/ywc ===")
seen = set()
count = 0
for line in lines:
    low = line.lower()
    if ("ywc" in low or "pops" in low or "journal" in low or "create_pop" in low) and line not in seen:
        seen.add(line)
        print("  ", line[:190])
        count += 1
        if count >= 40:
            break

print("=== distinct error heads ===")
msgs = {}
for line in lines:
    cleaned = re.sub(r"^\[\d+:\d+:\d+\]\[[^\]]+\]:\s*", "", line)[:110]
    msgs[cleaned] = msgs.get(cleaned, 0) + 1
for msg, c in sorted(msgs.items(), key=lambda kv: -kv[1])[:20]:
    print(f"  {c:5}x  {msg}")
