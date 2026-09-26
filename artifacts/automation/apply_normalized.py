import re
import shutil
from pathlib import Path

t = Path("artifacts/automation/roundtrip_states.txt").read_text(encoding="utf-8-sig")
print("CHI blocks:", len(re.findall(r"country = c:CHI", t)))
for state, city in (("STATE_SICHUAN", "x60E0D5"), ("STATE_YUNNAN", "x78DC66")):
    i = t.find("s:" + state)
    nxt = re.search(r"(?m)^\s*s:STATE_", t[i + 10:])
    block = t[i:i + 10 + nxt.start()]
    owners = re.findall(r"country = c:([A-Z]{3})", block)
    print(state, owners, "city present:", city in block)
shutil.copyfile("artifacts/automation/roundtrip_states.txt",
                "yongchang_world/common/history/states/00_states.txt")
print("ledger replaced with normalized output")
