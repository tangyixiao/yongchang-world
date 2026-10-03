import subprocess
from pathlib import Path

ROOT = Path(".")
for cmd in (
    ["grep", "-rn", "state_building_port_max_level_add", "yongchang_world/"],
    ["python", "-X", "utf8", "tools/build_campaign_content.py"],
    ["python", "-X", "utf8", "tools/build_hegemony_content.py"],
    ["python", "-X", "utf8", "tools/build_southwest_content.py"],
    ["grep", "-c", "add = +1", "yongchang_world/events/ywc_hegemony_events.txt"],
    ["grep", "-c", "FLAVOR", "yongchang_world/events/ywc_large_campaign_events.txt"],
):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
    print("$", " ".join(cmd[1:])[:80], "->", r.returncode)
    if r.stdout.strip():
        print(r.stdout.strip()[:400])
