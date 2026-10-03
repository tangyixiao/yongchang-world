from pathlib import Path

t = Path("yongchang_world/common/history/pops/ywc_china_pops.txt").read_text(encoding="utf-8-sig")
print(repr(t[:600]))
print("...")
print("braces: open", t.count("{"), "close", t.count("}"))
