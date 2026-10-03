from pathlib import Path

# tag_registry.json: BOM-free (repo JSON rule)
reg = Path("data/scenario/tag_registry.json")
reg.write_text(reg.read_text(encoding="utf-8-sig").lstrip("﻿"), encoding="utf-8", newline="\n")
print("registry BOM stripped")

# 00_states.txt: game script file -> UTF-8 with BOM (metadata contract)
led = Path("yongchang_world/common/history/states/00_states.txt")
body = led.read_text(encoding="utf-8-sig")
led.write_text(body, encoding="utf-8-sig", newline="\n")
print("ledger BOM restored:", led.read_bytes()[:3] == b"\xef\xbb\xbf")
