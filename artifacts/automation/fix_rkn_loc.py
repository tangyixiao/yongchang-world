from pathlib import Path

pairs = {
    "simp_chinese": [(' LJG:0 "丽江国"', ' LJG:0 "丽江国"\n RKN:0 "若开"\n RKN_adj:0 "若开"')],
    "english": [(' LJG:0 "Lijiang"', ' LJG:0 "Lijiang"\n RKN:0 "Arakan"\n RKN_adj:0 "Arakanese"')],
}
for language, (old, new) in pairs.items():
    p = Path(f"yongchang_world/localization/{language}/ywc_regional_l_{language}.yml")
    t = p.read_text(encoding="utf-8-sig")
    assert old in t
    p.write_text(t.replace(old, new), encoding="utf-8-sig", newline="\n")
print("RKN country-name loc added")
