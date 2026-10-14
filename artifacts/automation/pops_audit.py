# Round 7: pops coverage per tag vs ledger ownership; where are SHU's 400M people?
import re
from pathlib import Path

ROOT = Path(".")

print("=== pops files in mod ===")
pops_dir = ROOT / "yongchang_world/common/history/pops"
files = sorted(pops_dir.glob("*.txt"))
total = 0
per_tag_states = {}
for path in files:
    text = path.read_text(encoding="utf-8-sig")
    pairs = re.findall(r"s:(STATE_[A-Z_]+)\s*=\s*\{([^{}]*?)region_state:([A-Z]{3})", text) or []
    # simpler: for each state block, which tags get pops
    blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", text)
    starts = [(m.group(1), m.start()) for m in blocks]
    covered = set()
    for idx, (name, start) in enumerate(starts):
        end = starts[idx + 1][1] if idx + 1 < len(starts) else len(text)
        block = text[start:end]
        for tag in re.findall(r"region_state:([A-Z]{3})", block):
            covered.add((name, tag))
    sizes = [int(x) for x in re.findall(r"size\s*=\s*(\d+)", text)]
    print(f"  {path.name}: {len(starts)} states, {len(sizes)} pop blocks, total size={sum(sizes):,}")
    total += sum(sizes)
    for state, tag in covered:
        per_tag_states.setdefault(tag, set()).add(state)
print(f"  TOTAL pop size across mod pops files: {total:,}")

print("=== SHU states in ledger vs pops coverage ===")
states_text = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
blocks = re.finditer(r"(?m)^\s*s:(STATE_[A-Z_]+)\s*=\s*\{", states_text)
starts = [(m.group(1), m.start()) for m in blocks]
owner = {}
for idx, (name, start) in enumerate(starts):
    end = starts[idx + 1][1] if idx + 1 < len(starts) else len(states_text)
    m = re.search(r"country = c:([A-Z]{3})", states_text[start:end])
    owner[name] = m.group(1) if m else "(none)"

for tag in ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG"):
    owned = sorted(s for s, o in owner.items() if o == tag)
    with_pops = sorted(per_tag_states.get(tag, set()) & set(owned))
    missing = sorted(set(owned) - set(with_pops))
    print(f"  {tag}: owns {len(owned)}, with pops {len(with_pops)}, MISSING POPS: {missing}")
