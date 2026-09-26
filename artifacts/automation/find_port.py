from pathlib import Path

ROOT = Path(".")
for path in ROOT.rglob("*.txt"):
    if "git" in path.parts:
        continue
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if "state_building_port_max_level_add" in line:
            print(f"{path}:{i}: {line.strip()[:120]}")
