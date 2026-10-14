from pathlib import Path

LOGS = Path("D:/Documents/Paradox Interactive/Victoria 3/logs")
text = (LOGS / "game.log").read_text(encoding="utf-8", errors="ignore")
i = text.find("ywc_china_pops")
while i != -1:
    start = text.rfind("\n", 0, text.rfind("\n", 0, i))
    print(text[max(0, i - 600):i + 300])
    print("=====")
    i = text.find("ywc_china_pops", i + 1)
    if i > 60000:
        break
