import re
from pathlib import Path

root = Path("yongchang_world/common/journal_entries")
stems = ["shu_court", "jhg_convoy", "dmg_compact", "nqg_supply", "oir_banner",
         "mng_balance", "tib_estate", "kor_reform", "lan_charter", "nmg_bargain"]
for path in sorted(root.glob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    hits = [m.group(1) for m in re.finditer(r"(?m)^(ywc_je_flavor_\w+) = \{", text)]
    if hits:
        print(path.name, "->", hits, "| flavor at EOF:", text.rstrip().endswith("}"))
print("---- other refs to flavor markers outside journal_entries ----")
for path in Path("yongchang_world").rglob("*.txt"):
    if "journal_entries" in path.parts:
        continue
    t = path.read_text(encoding="utf-8-sig")
    for m in re.finditer(r"ywc_je_flavor_\w+_(resolved|failed)", t):
        line = t.count("\n", 0, m.start()) + 1
        print(f"{path}:{line}: {m.group(0)}")
