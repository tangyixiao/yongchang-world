import json
from pathlib import Path

# 1. southwest_states.json: declare SHU's basin-city share so the coverage
#    contract holds for SICHUAN/YUNNAN
p = Path("data/scenario/southwest_states.json")
data = json.loads(p.read_text(encoding="utf-8-sig"))
shares = {"STATE_SICHUAN": ("SHU", ["x60E0D5"]), "STATE_YUNNAN": ("SHU", ["x78DC66"])}
for row in data["states"]:
    if row["state"] in shares:
        owner, plist = shares[row["state"]]
        if not any(g["owner"] == owner for g in row["groups"]):
            row["groups"].append({"owner": owner, "owned_provinces": plist})
            print(f"{row['state']}: +{owner} group")
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

# 2. test file: ARA -> RKN (the Arakan tag is now RKN)
p = Path("tests/test_regional_states.py")
t = p.read_text(encoding="utf-8")
t = t.replace('"SHD", "ARA", "LAD"', '"SHD", "RKN", "LAD"')
p.write_text(t, encoding="utf-8", newline="\n")
print("test_regional_states ARA -> RKN")

# 3. flag file: ARK -> RKN
p = Path("yongchang_world/common/flag_definitions/ywc_flags.txt")
t = p.read_text(encoding="utf-8-sig")
t = t.replace("ARK = {", "RKN = {").replace("YWC_ARK", "YWC_RKN")
p.write_text(t, encoding="utf-8-sig", newline="\n")
print("flag file ARK -> RKN")

# 4. regional coas: YWC_ARK -> YWC_RKN
p = Path("yongchang_world/common/coat_of_arms/coat_of_arms/ywc_regional_coas.txt")
t = p.read_text(encoding="utf-8-sig").replace("YWC_ARK", "YWC_RKN")
p.write_text(t, encoding="utf-8-sig", newline="\n")
print("regional coas ARK -> RKN")
