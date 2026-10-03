# Final audit: every (state, pops-target-tag) mismatch vs ledger owner.
import re
from pathlib import Path

ROOT = Path(".")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", states_text)
starts = [(m.group(1), m.start()) for m in blocks]
# proper block ends: next s: or EOF
owner = {}
multi = {}
for idx, (name, start) in enumerate(starts):
    end = starts[idx + 1][1] if idx + 1 < len(starts) else len(states_text)
    block = states_text[start:end]
    tags = re.findall(r"country = c:([A-Z]{3})", block)
    owner[name] = tags[0] if tags else "(none)"
    if len(set(tags)) > 1:
        multi[name] = tags

mismatch = {}
for path in sorted((ROOT / "yongchang_world/common/history/pops").glob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", text)
    starts = [(m.group(1), m.start()) for m in blocks]
    for idx, (name, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(text)
        block = text[start:end]
        for tag in re.findall(r"region_state:([A-Z]{3})", block):
            real = owner.get(name)
            if real and tag != real and real != "(none)":
                mismatch.setdefault((path.name, name), set()).add((tag, real))

print(f"=== {len(mismatch)} mismatched (file, state) pairs ===")
by_file = {}
for (fname, state), pairs in mismatch.items():
    by_file.setdefault(fname, []).append((state, sorted(pairs)))
for fname, rows in sorted(by_file.items()):
    print(f"\n{fname}: {len(rows)} states")
    for state, pairs in rows[:40]:
        print(f"   {state}: pops target {pairs[0][0][0]} -> ledger owner {pairs[0][0][1]}")
