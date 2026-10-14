from pathlib import Path

text = Path("yongchang_world/common/history/states/00_states.txt").read_text(encoding="utf-8-sig")
i = text.find("s:STATE_SICHUAN")
nxt = text.find("\ns:STATE_", i + 10)
block = text[i:nxt + 1]
print(block[:1200])
print("...")
print("holders:", [l.strip() for l in block.splitlines() if "country = c:" in l])
