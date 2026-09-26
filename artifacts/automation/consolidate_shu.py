# Consolidate the SICHUAN/YUNNAN SHU groups (idempotent-repair).
import json
from pathlib import Path

OV_PATH = Path("data/scenario/ownership_overrides.json")
ov = json.loads(OV_PATH.read_text(encoding="utf-8"))
CITIES = {"STATE_SICHUAN": "x60E0D5", "STATE_YUNNAN": "x78DC66"}

for row in ov["states"]:
    if row["state"] not in CITIES:
        continue
    city = CITIES[row["state"]]
    shu_provinces = []
    others = []
    for g in row["groups"]:
        if g["owner"] == "SHU":
            shu_provinces += g.get("owned_provinces", [])
        else:
            others.append(g)
    if city not in shu_provinces:
        # find the group currently holding the city and take it back
        for g in others:
            if city in g.get("owned_provinces", []):
                g["owned_provinces"].remove(city)
                shu_provinces.append(city)
                break
    assert shu_provinces == [city], (row["state"], shu_provinces)
    others.append({"owner": "SHU", "owned_provinces": [city]})
    row["groups"] = others
    print(row["state"], "->", [(g["owner"], len(g["owned_provinces"])) for g in row["groups"]])

OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("consolidated")
