# Definitive: ledger state coverage vs vanilla; who owns SHENGJING and the north.
import re
from pathlib import Path

GAME = Path("E:/SteamLibrary/steamapps/common/Victoria 3/game")
ROOT = Path(".")

vanilla_states = set()
for path in GAME.glob("map_data/state_regions/*.txt"):
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    vanilla_states |= set(re.findall(r"(STATE_[A-Z0-9_]+)\s*=\s*\{", text))

ledger = (ROOT / "yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
ledger_names = set(re.findall(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)", ledger))
print("ledger states:", len(ledger_names))
missing = sorted(vanilla_states - ledger_names)
extra = sorted(ledger_names - vanilla_states)
print("vanilla states MISSING from ledger:", len(missing), missing[:40])
print("ledger states NOT in vanilla:", extra)

# who owns SHENGJING / the northern states in the ledger (with a robust scan: find state block start, read to next state start)
def owner_of(state):
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", ledger)
    if not m:
        return "(ABSENT FROM LEDGER -> vanilla owner applies)"
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", ledger[m.end():])
    block = ledger[m.end():m.end() + nxt.start()] if nxt else ledger[m.end():]
    tags = re.findall(r"country = c:([A-Z]{3})", block)
    return tags or "(no create_state)"

for state in ("STATE_SHENGJING", "STATE_SOUTHERN_MANCHURIA", "STATE_HINGGAN", "STATE_AMUR",
              "STATE_NORTHERN_MANCHURIA", "STATE_OUTER_MANCHURIA", "STATE_ALXA",
              "STATE_TUVA", "STATE_ALTAI", "STATE_JETISY", "STATE_BEIJING", "STATE_ZHILI"):
    print(state, "->", owner_of(state))

# what vanilla owner do the missing states have (from vanilla history)?
van_hist = ""
for path in GAME.glob("history/states/*.txt"):
    van_hist += path.read_text(encoding="utf-8-sig", errors="ignore")
print("\n=== vanilla owners of the states missing from the ledger ===")
for state in missing[:60]:
    m = re.search(rf"s:{state}\s*=\s*\{{", van_hist)
    if m:
        nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", van_hist[m.end():])
        block = van_hist[m.end():m.end() + nxt.start()] if nxt else van_hist[m.end():m.end() + 3000]
        tags = re.findall(r"country = c:([A-Z]{3})", block)
        print(f"  {state}: vanilla owner {sorted(set(tags))}")
