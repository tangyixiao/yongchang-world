import json

d = json.load(open("data/scenario/ownership_overrides.json", encoding="utf-8"))
out = []
for row in d["states"]:
    state = row["state"]
    if state in ("STATE_SICHUAN", "STATE_YUNNAN", "STATE_ASSAM", "STATE_SHAN_STATES",
                 "STATE_MANDALAY", "STATE_KASHMIR", "STATE_LHASA", "STATE_SOUTHERN_MANCHURIA",
                 "STATE_HINGGAN", "STATE_AMUR", "STATE_ALXA", "STATE_TUVA", "STATE_ALTAI",
                 "STATE_JETISY", "STATE_QINGHAI", "STATE_GANSU", "STATE_NINGXIA"):
        for g in row["groups"]:
            n = len(g.get("owned_provinces", []))
            out.append(f"{state}: {g['owner']} ({n} provinces)")
text = "\n".join(out)
open("artifacts/automation/ownership_china_dump.txt", "w", encoding="utf-8").write(text)
print(text)
