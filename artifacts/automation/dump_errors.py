# Dump the actual error blocks from the user's error.log.
from pathlib import Path
import re

err = Path("D:/Documents/Paradox Interactive/Victoria 3/logs/error.log")
lines = err.read_text(encoding="utf-8", errors="ignore").splitlines()

# show context blocks around "Failed to read key reference"
blocks = []
for i, line in enumerate(lines):
    if "Failed to read key reference" in line:
        blocks.append(lines[max(0, i - 2):i + 3])
print(f"=== {len(blocks)} key-reference failures, first 8 blocks ===")
seen = set()
shown = 0
for block in blocks:
    key = "|".join(block)
    if key in seen:
        continue
    seen.add(key)
    for line in block:
        print("  ", line[:180])
    print("  ---")
    shown += 1
    if shown >= 8:
        break

# categorize all distinct error messages (strip timestamps/line numbers)
print("=== distinct error messages ===")
msgs = {}
for line in lines:
    cleaned = re.sub(r"^\[\d+:\d+:\d+\]\[[^\]]+\]:\s*", "", line)
    cleaned = re.sub(r"\d+", "N", cleaned)[:120]
    msgs[cleaned] = msgs.get(cleaned, 0) + 1
for msg, count in sorted(msgs.items(), key=lambda kv: -kv[1])[:25]:
    print(f"  {count:5}x  {msg}")
