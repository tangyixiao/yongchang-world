from pathlib import Path

inserts = {
    "simp_chinese": [" RKN:0 \"若开\"", " RKN_adj:0 \"若开\""],
    "english": [" RKN:0 \"Arakan\"", " RKN_adj:0 \"Arakanese\""],
}
for language, lines in inserts.items():
    p = Path(f"yongchang_world/localization/{language}/ywc_regional_l_{language}.yml")
    body = p.read_text(encoding="utf-8-sig")
    changed = False
    for line in lines:
        if line.strip().split(":")[0] not in body:
            body = body.rstrip("\n") + "\n" + line + "\n"
            changed = True
    p.write_text(body, encoding="utf-8-sig", newline="\n")
    print(language, "updated:", changed)
