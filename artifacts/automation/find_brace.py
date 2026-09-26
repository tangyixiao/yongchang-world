from pathlib import Path

text = Path("yongchang_world/common/scripted_effects/ywc_campaign_effects.txt").read_text(encoding="utf-8-sig")
depth = 0
in_string = False
in_comment = False
for idx, ch in enumerate(text):
    if in_comment:
        if ch == "\n":
            in_comment = False
        continue
    if ch == '"':
        in_string = not in_string
        continue
    if ch == "#":
        in_comment = True
        continue
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth < 0:
            line = text.count("\n", 0, idx) + 1
            ctx = text[max(0, idx - 200):idx + 80]
            print("NEGATIVE at line", line)
            print(ctx)
            break
print("final depth:", depth)
