# Correct audit: pops targets must be within the state's owner set; owners without pops = the gap.
import re
from pathlib import Path

ROOT = Path(".")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", states_text)
starts = [(m.group(1), m.start()) for m in blocks]
owners = {}
for idx, (name, start) in enumerate(starts):
    end = starts[idx + 1][1] if idx + 1 < len(starts) else len(states_text)
    block = states_text[start:end]
    owners[name] = set(re.findall(r"country = c:([A-Z]{3})", block))

orphan = {}
covered = {}
for path in sorted((ROOT / "yongchang_world/common/history/pops").glob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", text)
    starts = [(m.group(1), m.start()) for m in blocks]
    for idx, (name, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(text)
        block = text[start:end]
        state_owners = owners.get(name, set())
        for tag in re.findall(r"region_state:([A-Z]{3})", block):
            if state_owners and tag not in state_owners:
                orphan.setdefault(path.name, []).append((name, tag, sorted(state_owners)))
            covered.setdefault(name, set()).add(tag)

print("=== A. orphan pops targets (tag not an owner of that state) ===")
for fname, rows in sorted(orphan.items()):
    print(f"  {fname}: {len(rows)}")
    for state, tag, real in rows[:12]:
        print(f"     {state}: region_state:{tag} but owners={real}")

print("=== B. owners without any pops (coverage gap) ===")
gap = {}
for state, own in sorted(owners.items()):
    for tag in own:
        if tag not in covered.get(state, set()):
            gap.setdefault(tag, []).append(state)
for tag, states in sorted(gap.items(), key=lambda kv: -len(kv[1])):
    print(f"  {tag}: {len(states)} states without pops -> {states[:12]}")
