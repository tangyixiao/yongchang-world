import json
from pathlib import Path

# 1. southwest_states.json: declare SHU's basin-city share + rename ARA->RKN
p = Path("data/scenario/southwest_states.json")
data = json.loads(p.read_text(encoding="utf-8-sig"))
shares = {"STATE_SICHUAN": ["x60E0D5"], "STATE_YUNNAN": ["x78DC66"]}
for g in data["groups"]:
    if g["target_country"] == "ARA":
        g["target_country"] = "RKN"
        print(f"group renamed ARA->RKN for {g['source_state']}")
for state, plist in shares.items():
    if not any(g["source_state"] == state and g["target_country"] == "SHU" for g in data["groups"]):
        data["groups"].append({
            "source_state": state,
            "target_country": "SHU",
            "reason": "Basin core (prefectural city) held directly by Shun",
        })
        print(f"+SHU group for {state}")
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
