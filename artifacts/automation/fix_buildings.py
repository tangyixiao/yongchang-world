from pathlib import Path

p = Path("yongchang_world/common/history/buildings/ywc_southwest_buildings.txt")
t = p.read_text(encoding="utf-8-sig")
t = t.replace("region_state:ARA", "region_state:RKN")
t = t.replace('country = "c:ARA"', 'country = "c:RKN"')
p.write_text(t, encoding="utf-8-sig", newline="\n")
print("buildings ARA -> RKN:", "region_state:RKN" in t)
