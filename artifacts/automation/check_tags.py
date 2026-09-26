import json

reg = json.load(open("data/scenario/tag_registry.json", encoding="utf-8"))
countries = reg.get("countries", [])
print("total countries:", len(countries))
for row in countries:
    tag = row.get("tag", "")
    name = row.get("name", row.get("name_cn", ""))
    if tag in {"SPA", "ESP", "NED", "HOL", "RUS", "JAP", "USA", "MEX", "SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "MNG", "TIB", "KOR", "LAN", "NMG"}:
        print(tag, name)
# search by name
for row in countries:
    text = json.dumps(row, ensure_ascii=False)
    if any(k in text for k in ("西班牙", "Spain", "荷兰", "Netherlands", "尼德兰")):
        print("NAME-HIT:", row)
