import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
tpl = (GAME / "common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
DESIGN = ["STATE_SOUTHERN_MANCHURIA", "STATE_AMUR", "STATE_HINGGAN", "STATE_ALXA",
          "STATE_TUVA", "STATE_ALTAI", "STATE_JETISY"]
for state in DESIGN:
    entries = []
    for m in re.finditer(rf"(?m)^\s*s:{state}\s*=\s*\{{", tpl):
        nxt = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", tpl[m.end():])
        end = m.end() + nxt.start() if nxt else len(tpl)
        block = tpl[m.end():end]
        creates = re.findall(r"country = c:([A-Z]{3})", block)
        entries.append(creates)
    print(state, "entries:", entries)
