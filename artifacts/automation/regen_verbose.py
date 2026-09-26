import subprocess
import re
from pathlib import Path

r = subprocess.run([
    "python", "-X", "utf8", "tools/build_state_history.py",
    "--baseline", "data/baseline/vic3-1.13.11.json",
    "--game-root", "E:/SteamLibrary/steamapps/common/Victoria 3/game",
    "--overrides", "data/scenario/ownership_overrides.json",
    "--template", "yongchang_world/common/history/states/00_states.txt",
    "--output", "yongchang_world/common/history/states/00_states.txt",
    "--scenario-root", "data/scenario",
], capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("regen rc:", r.returncode)
print("stdout:", (r.stdout or "")[-500:])
print("stderr:", (r.stderr or "")[-500:])

text = Path("yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
blocks = re.findall(r"country = c:CHI\s*\n\s*owned_provinces\s*=\s*\{([^}]*)\}", text)
print("CHI create_state blocks:", len(blocks), "sizes:", [len(b.split()) for b in blocks])
