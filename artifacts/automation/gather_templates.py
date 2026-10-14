import re
from pathlib import Path

ROOT = Path(".")

coa_path = next((ROOT / "yongchang_world/common/coat_of_arms").rglob("*.txt"))
text = coa_path.read_text(encoding="utf-8-sig")
m = re.search(r"YWC_SHU\s*=\s*\{.*?\n\}", text, re.S)
print("=== YWC_SHU coa ===")
print(m.group(0) if m else "not found")

fd_path = next((ROOT / "yongchang_world/common/flag_definitions").rglob("*.txt"))
print("=== flag_definitions file:", fd_path.name, "===")
print(fd_path.read_text(encoding="utf-8-sig")[:800])

print("=== ywc_northeast_pops.txt full ===")
print((ROOT / "yongchang_world/common/history/pops/ywc_northeast_pops.txt").read_text(encoding="utf-8-sig"))

print("=== southwest pops: MANDALAY/KASHMIR sections ===")
sw = (ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt").read_text(encoding="utf-8-sig")
i = sw.find("STATE_MANDALAY")
print(sw[i - 5:i + 700] if i >= 0 else "no mandalay section")

print("=== a new-tag country definition (DER) ===")
for path in (ROOT / "yongchang_world/common/country_definitions").rglob("*.txt"):
    text = path.read_text(encoding="utf-8-sig")
    m = re.search(r"(?m)^\s*DER\s*=\s*\{.*?\n\}", text, re.S)
    if m:
        print(m.group(0))
        break

print("=== build_state_history.py CLI ===")
import subprocess
r = subprocess.run(["python", "-X", "utf8", "tools/build_state_history.py", "--help"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore")
print(r.stdout or r.stderr)
