import json
import re
from pathlib import Path

ROOT = Path(".")
ledger = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
pops = (ROOT / "yongchang_world/common/history/pops/ywc_china_pops.txt").read_text(encoding="utf-8-sig")

CHINA_POPS = {
    "STATE_ZHILI", "STATE_SHANDONG", "STATE_SHANXI", "STATE_HENAN", "STATE_XIAN",
    "STATE_GANSU", "STATE_NINGXIA", "STATE_CHONGQING", "STATE_SICHUAN", "STATE_GUIZHOU",
    "STATE_YUNNAN", "STATE_GUANGXI", "STATE_GUANGDONG", "STATE_SHAOZHOU", "STATE_FUJIAN",
    "STATE_ZHEJIANG", "STATE_JIANGXI", "STATE_HUNAN", "STATE_EASTERN_HUBEI",
    "STATE_WESTERN_HUBEI", "STATE_NORTHERN_ANHUI", "STATE_SOUTHERN_ANHUI", "STATE_JIANGSU",
    "STATE_NANJING", "STATE_SUZHOU", "STATE_SOUTHERN_MANCHURIA",
}
baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))

positions = []
for m in re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", ledger):
    positions.append((m.start(), m.group(1)))
positions.sort()
all_blocks = {}
for idx, (start, state) in enumerate(positions):
    end = positions[idx + 1][0] if idx + 1 < len(positions) else len(ledger)
    all_blocks[state] = ledger[start:end]

for state in sorted(CHINA_POPS):
    block = all_blocks.get(state)
    if block is None:
        print(f"{state}: NOT IN LEDGER!!!")
        continue
    owners = re.findall(r"country = c:([A-Z]{3})", block)
    pop_block = f"region_state:SHU" in pops
    in_pops = f"s:{state}" in pops
    print(f"{state}: ledger owners={owners} in-my-pops={in_pops}")
print("pops file states:", sorted(re.findall(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)", pops)))
