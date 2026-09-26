import json

cat = json.load(open("data/content/content_catalog.json", encoding="utf-8"))
for tag, row in cat["countries"].items():
    f = row["flavor"]
    print(tag, "|", f["variable"], "|", f.get("journals"), "|", f.get("events"), "|", f.get("high_modifier"), f.get("low_modifier"))
