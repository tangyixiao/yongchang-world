# Validate pops state names against vanilla; also find template source for the generator.
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
vanilla_states = set()
for path in GAME.glob("map_data/state_regions/*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    vanilla_states |= set(re.findall(r"(STATE_[A-Z0-9_]+)\s*=\s*\{", text))
print("vanilla states:", len(vanilla_states))

bad = {}
allpops = {}
for path in Path("yongchang_world/common/history/pops").glob("*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    names = re.findall(r"s:(STATE_[A-Z0-9_]+)", text)
    allpops[path.name] = names
    for s in names:
        if s not in vanilla_states:
            bad.setdefault(path.name, []).append(s)
for name, states in bad.items():
    print("INVALID STATE NAMES:", name, states)
print("pops file state counts:", {k: len(set(v)) for k, v in allpops.items()})

# does vanilla have SHENGJING-like names under another name?
for probe in ("SHENGJING", "SOUTHERN_MANCHURIA", "HINGGAN", "AMUR", "ALXA", "TUVA", "ALTAI", "JETISY"):
    print(probe, "in vanilla:", any(probe in s for s in vanilla_states))

# template file for the generator?
for cand in ("data/baseline", "tools", "data/scenario"):
    for path in Path(cand).glob("*template*"):
        print("template candidate:", path)
