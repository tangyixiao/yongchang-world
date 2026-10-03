import re
from pathlib import Path

ROOT = Path(".")

# 1. drop the duplicate SOUTHERN_MANCHURIA block (11_east_asia's historical pops
#    were retargeted to SHU already)
p = ROOT / "yongchang_world/common/history/pops/ywc_china_pops.txt"
text = p.read_text(encoding="utf-8-sig")
m = re.search(r"\n\ts:STATE_SOUTHERN_MANCHURIA = \{.*?\n\t\}", text, re.S)
if m:
    text = text[:m.start()] + text[m.end():]
    p.write_text(text, encoding="utf-8-sig", newline="\n")
    print("removed duplicate SOUTHERN_MANCHURIA pops")

# 2. delete the dead CHI country history (CHI no longer exists at start)
chi = ROOT / "yongchang_world/common/history/countries/chi - china.txt"
if chi.exists():
    chi.unlink()
    print("deleted chi - china.txt (CHI is landless and does not instantiate)")

# 3. port modifier: locate it
for path in (ROOT / "yongchang_world/common/buildings").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for i, line in enumerate(text.splitlines(), 1):
        if "state_building_port_max_level_add" in line:
            print(f"PORT: {path.name}:{i}: {line.strip()[:100]}")

# 4. on_action: append the mod journal adds per country (idempotent with
#    content_starts; on_action-added journals are the reliable display path)
hooks = ROOT / "yongchang_world/common/on_actions/ywc_startup_hooks.txt"
text = hooks.read_text(encoding="utf-8-sig")
starts = (ROOT / "yongchang_world/common/history/countries/ywc_content_starts.txt").read_text(encoding="utf-8-sig")

# extract each country's add_journal_entry lines from content_starts
journal_adds = {}
current = None
for line in starts.splitlines():
    m = re.search(r"c:([A-Z]{3}) \?=", line)
    if m:
        current = m.group(1)
        journal_adds.setdefault(current, [])
    jm = re.search(r"add_journal_entry = \{ type = (ywc_[A-Za-z0-9_]+) \}", line)
    if jm and current:
        journal_adds[current].append(jm.group(1))

inserted = 0
for tag, journals in journal_adds.items():
    block_m = re.search(rf"(limit = \{{ c:{tag} \?= this \}}\n)((?:\t\t\t.*\n)+)", text)
    if not block_m:
        print(f"  no on_action block for {tag}")
        continue
    block = block_m.group(2)
    adds = []
    for journal in journals:
        add_line = f"\t\t\t\tadd_journal_entry = {{ type = {journal} }}\n"
        if add_line not in text:
            adds.append(add_line)
    if adds:
        new_block = block + "".join(adds)
        text = text.replace(block, new_block, 1)
        inserted += 1
hooks.write_text(text, encoding="utf-8-sig", newline="\n")
print(f"on_action journal adds inserted for {inserted} countries")
