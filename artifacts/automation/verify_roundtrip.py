import re
from pathlib import Path

out = Path("artifacts/automation/roundtrip_states.txt").read_text(encoding="utf-8-sig")
for state in ("STATE_SICHUAN", "STATE_YUNNAN", "STATE_SOUTHERN_MANCHURIA", "STATE_MANDALAY", "STATE_AMUR"):
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", out)
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", out[m.end():])
    end = m.end() + (nxt.start() if nxt else len(out) - m.end())
    block = out[m.start():end]
    pairs = []
    for cm in re.finditer(r"country = c:([A-Z]{3})", block):
        p_open = block.find("owned_provinces = {", cm.start())
        p_close = block.find("}", p_open)
        pairs.append((cm.group(1), len(re.findall(r"x[0-9A-Fa-f]+", block[p_open:p_close]))))
    print(state, "->", pairs)
# global CHI check
print("CHI blocks:", len(re.findall(r"country = c:CHI", out)))
