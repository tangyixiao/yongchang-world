# Inspect the vanilla template's create_state structure for the seven states.
import re
from pathlib import Path

tpl = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
for state in ("STATE_SOUTHERN_MANCHURIA", "STATE_AMUR", "STATE_HINGGAN", "STATE_ALXA",
              "STATE_TUVA", "STATE_ALTAI", "STATE_JETISY"):
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", tpl)
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", tpl[m.end():])
    block = tpl[m.end():m.end() + nxt.start()] if nxt else tpl[m.end():m.end() + 4000]
    creates = re.findall(r"country = c:([A-Z]{3})", block)
    sizes = [len(re.findall(r"x[0-9A-Fa-f]+", p)) for p in re.findall(r"owned_provinces\s*=\s*\{([^}]*)\}", block)]
    print(state, "->", list(zip(creates, sizes)))
