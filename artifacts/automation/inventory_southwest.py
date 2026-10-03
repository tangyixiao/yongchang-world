import json
import re
from pathlib import Path

reg = json.load(open("data/scenario/tag_registry.json", encoding="utf-8"))
sw_tags = ["DER", "KAM", "GYL", "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "MNP", "SHD", "ARA", "LAD"]
print("=== tag registry entries ===")
for row in reg.get("countries", []):
    if row.get("tag") in sw_tags:
        print(json.dumps(row, ensure_ascii=False))
print("=== scenario spec mentions ===")
for name in ["2026-09-04-02-1836开局剧本.md", "2026-09-04-00-世界观总纲.md"]:
    path = Path("docs/superpowers/specs") / name
    if not path.exists():
        continue
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"\b(DER|KAM|GYL|LXJ|LJG|SIP|KTG|WAA|KCH|AHM|MNP|SHD|ARA|LAD)\b", line):
            print(f"{name}:{i}: {line.strip()[:120]}")
print("=== current content per tag (events/journals/scripts) ===")
root = Path("yongchang_world")
for tag in sw_tags:
    hits = []
    for p in root.rglob("*.txt"):
        t = p.read_text(encoding="utf-8-sig", errors="ignore")
        n = t.count(f"c:{tag}")
        if n:
            hits.append(f"{p.name}:{n}")
    print(tag, "c:TAG refs ->", hits[:6] if hits else "NONE")
