import json

d = json.load(open("data/scenario/ownership_overrides.json", encoding="utf-8"))
out = []
if isinstance(d, dict):
    out.append(f"keys: {list(d.keys())}")
    for k, v in list(d.items())[:3]:
        out.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:400]}")
else:
    out.append(f"list len {len(d)}")
    for row in d[:5]:
        out.append(json.dumps(row, ensure_ascii=False)[:300])
text = "\n".join(out)
open("artifacts/automation/ownership_dump.txt", "w", encoding="utf-8").write(text)
print(text)
