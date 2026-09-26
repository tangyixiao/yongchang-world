# Fix stage B: pops, ARK rename across content, dynamic names, flags.
import json
import re
from pathlib import Path

ROOT = Path(".")
POPS = ROOT / "yongchang_world/common/history/pops"

# ---------- 1. China pops for SHU's uncovered states ----------
CHINA_POPS = {
    "STATE_ZHILI": [("han", 20000000)],
    "STATE_SHANDONG": [("han", 28000000)],
    "STATE_SHANXI": [("han", 13000000)],
    "STATE_HENAN": [("han", 22000000)],
    "STATE_XIAN": [("han", 10000000)],
    "STATE_GANSU": [("han", 10000000), ("mongol", 600000)],
    "STATE_NINGXIA": [("han", 1200000), ("mongol", 400000)],
    "STATE_CHONGQING": [("han", 12000000)],
    "STATE_SICHUAN": [("han", 8000000)],
    "STATE_GUIZHOU": [("han", 3500000), ("yi", 1500000)],
    "STATE_YUNNAN": [("han", 2400000), ("yi", 800000)],
    "STATE_GUANGXI": [("han", 6500000), ("yi", 1500000)],
    "STATE_GUANGDONG": [("han", 21000000)],
    "STATE_SHAOZHOU": [("han", 2000000)],
    "STATE_FUJIAN": [("han", 16000000)],
    "STATE_ZHEJIANG": [("han", 23000000)],
    "STATE_JIANGXI": [("han", 20000000)],
    "STATE_HUNAN": [("han", 17000000)],
    "STATE_EASTERN_HUBEI": [("han", 13000000)],
    "STATE_WESTERN_HUBEI": [("han", 7000000)],
    "STATE_NORTHERN_ANHUI": [("han", 18000000)],
    "STATE_SOUTHERN_ANHUI": [("han", 14000000)],
    "STATE_JIANGSU": [("han", 20000000)],
    "STATE_NANJING": [("han", 5000000)],
    "STATE_SUZHOU": [("han", 10000000)],
    "STATE_SOUTHERN_MANCHURIA": [("han", 6000000), ("manchu", 800000)],
}

ne_additions = {
    "STATE_AMUR": [("AMR", [("siberian", 150000), ("manchu", 60000)])],
    "STATE_HINGGAN": [("SOL", [("siberian", 200000), ("mongol", 80000)])],
}
inner_additions = {
    "STATE_ALXA": [("KHO", [("mongol", 220000)])],
    "STATE_TUVA": [("MGL", [("mongol", 90000)])],
    "STATE_ALTAI": [("MGL", [("mongol", 130000)])],
    "STATE_JETISY": [("GJU", [("kazak", 380000)])],
}


def render_blocks(states):
    blocks = []
    for state, groups in states:
        rows = []
        for tag, pops in groups:
            pop_lines = "\n".join(
                f"                create_pop = {{ culture = {culture} size = {size} }}"
                for culture, size in pops
            )
            rows.append(f"            region_state:{tag} = {{\n{pop_lines}\n            }}")
        blocks.append(f"        s:{state} = {{\n" + "\n".join(rows) + "\n        }")
    return "\n".join(blocks)


def render_china(table):
    blocks = []
    for state, pops in sorted(table.items()):
        pop_lines = "\n".join(
            f"                create_pop = {{ culture = {culture} size = {size} }}"
            for culture, size in pops
        )
        blocks.append(
            f"        s:{state} = {{\n"
            f"            region_state:SHU = {{\n{pop_lines}\n            }}\n"
            f"        }}"
        )
    return "\n".join(blocks)


china_text = (
    "﻿# China-proper pops for SHU (v0.2 repair). The state ledger reassigns the\n"
    "# former Qing core to SHU; these are the 1836 province populations.\n"
    "POPS = {\n"
    + render_china(CHINA_POPS)
    + "\n}\n"
)
(POPS / "ywc_china_pops.txt").write_text(china_text, encoding="utf-8-sig", newline="\n")
print("wrote ywc_china_pops.txt")

for name, additions in (("ywc_northeast_pops.txt", ne_additions),
                        ("ywc_inner_asia_pops.txt", inner_additions)):
    path = POPS / name
    text = path.read_text(encoding="utf-8-sig")
    assert "POPS = {" in text
    text = text.rstrip()[:-1] + "\n" + render_blocks(sorted(additions.items())) + "\n}\n"
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"extended {name}")

# ---------- 2. southwest pops: scale up x4, rebrand ARA -> ARK ----------
sw_path = POPS / "ywc_southwest_pops.txt"
text = sw_path.read_text(encoding="utf-8-sig")
text = text.replace("region_state:ARA", "region_state:ARK")

def scale(match):
    return f"size = {int(match.group(1)) * 4:}"
text = re.sub(r"size\s*=\s*(\d+)", scale, text)
sw_path.write_text(text, encoding="utf-8-sig", newline="\n")
print("scaled ywc_southwest_pops x4, ARA->ARK")

# ---------- 3. ARK rename across content ----------
reg_path = ROOT / "data/scenario/tag_registry.json"
reg = json.loads(reg_path.read_text(encoding="utf-8-sig"))
for row in reg["countries"]:
    if row["tag"] == "ARA":
        row["tag"] = "ARK"
        row["mode"] = "new"
        row["source_tag"] = None
        row["name_zh"] = "若开"
reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("tag_registry ARA -> ARK")

cat_path = ROOT / "data/content/southwest_event_catalog.json"
cat = cat_path.read_text(encoding="utf-8")
cat = cat.replace('"ywc_ara.', '"ywc_ark.').replace('"short": "ara"', '"short": "ark"') \
         .replace('"tag": "ARA"', '"tag": "ARK"').replace('ywc_je_sw_ara', 'ywc_je_sw_ark') \
         .replace('ywc_sw_ara_', 'ywc_sw_ark_')
cat_path.write_text(cat, encoding="utf-8")
print("southwest catalog ARA -> ARK")

emit_cat = ROOT / "artifacts/automation/emit_southwest_catalog.py"
t = emit_cat.read_text(encoding="utf-8")
t = t.replace('"ara", "ARA", "若开", "Arakan"', '"ark", "ARK", "若开", "Arakan"') \
     .replace('events.append(ev(f"ywc_{short}.200"', 'events.append(ev(f"ywc_{short}.200"')
emit_cat.write_text(t, encoding="utf-8", newline="\n")

starts_path = ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt"
text = starts_path.read_text(encoding="utf-8-sig")
text = text.replace("c:ARA ?= {", "c:ARK ?= {") \
           .replace("type = ywc_je_sw_ara", "type = ywc_je_sw_ark")
starts_path.write_text(text, encoding="utf-8-sig", newline="\n")
print("content_starts ARA -> ARK")

for language in ("simp_chinese", "english"):
    p = ROOT / f"yongchang_world/localization/{language}/ywc_southwest_keys_l_{language}.yml"
    t = p.read_text(encoding="utf-8-sig").replace("ywc_je_sw_ara", "ywc_je_sw_ark")
    p.write_text(t, encoding="utf-8-sig", newline="\n")
print("southwest keys ARA -> ARK")

# ---------- 3b. ARK country definition (若开, Arakan) ----------
defs_path = ROOT / "yongchang_world/common/country_definitions/ywc_regional_countries.txt"
defs_text = defs_path.read_text(encoding="utf-8-sig")
if "ARK = {" not in defs_text:
    ark_def = ("ARK = { color = { 96 142 108 } country_type = unrecognized tier = principality "
               "cultures = { burmese } capital = STATE_MANDALAY }\n")
    anchor = defs_text.find("LJG = {")
    defs_text = defs_text[:anchor] + ark_def + defs_text[anchor:]
    defs_path.write_text(defs_text, encoding="utf-8-sig", newline="\n")
print("country definition ARK added")

# ---------- 3c. MGL dynamic-name loc keys ----------
for language, khalkha, khalkha_adj, maritime, maritime_adj in (
    ("simp_chinese", "喀尔喀汗国", "喀尔喀", "蒙古海贸国", "蒙古海贸"),
    ("english", "Khalkha Khanate", "Khalkha", "Khalkha Maritime State", "Khalkha Maritime"),
):
    p = ROOT / f"yongchang_world/localization/{language}/ywc_content_l_{language}.yml"
    t = p.read_text(encoding="utf-8-sig")
    additions = []
    if "ywc_dyn_mgl_khalkha:" not in t:
        additions.append(f' ywc_dyn_mgl_khalkha:0 "{khalkha}"')
        additions.append(f' ywc_dyn_mgl_khalkha_adj:0 "{khalkha_adj}"')
    if "ywc_dyn_mgl_maritime:" not in t:
        additions.append(f' ywc_dyn_mgl_maritime:0 "{maritime}"')
        additions.append(f' ywc_dyn_mgl_maritime_adj:0 "{maritime_adj}"')
    if additions:
        # insert after the last ywc_dyn_ line to keep related keys together
        lines = t.split("\n")
        idx = max(i for i, l in enumerate(lines) if "ywc_dyn_" in l)
        lines[idx + 1:idx + 1] = additions
        p.write_text("\n".join(lines), encoding="utf-8-sig", newline="\n")
print("MGL dynamic-name loc keys added")

# ---------- 4. dynamic names: drop the always-on heritage renames ----------
dyn_path = ROOT / "yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt"
text = dyn_path.read_text(encoding="utf-8-sig")
lines = text.split("\n")
out, skip = [], False
for line in lines:
    if re.match(r"^\s*dynamic_country_name = \{ name = ywc_dyn_\w+_heritage ", line):
        continue
    out.append(line)
text = "\n".join(out)
# replace the MNG-keyed block (dead: MNG is not a runtime tag) with an MGL block
m = re.search(r"MNG = \{.*?\n\}", text, re.S)
mgl_block = (
    "MGL = {\n"
    "\tdynamic_country_name = { name = ywc_dyn_mgl_khalkha adjective = ywc_dyn_mgl_khalkha_adj "
    "is_main_tag_only = yes priority = 15 trigger = { exists = scope:actor scope:actor ?= { c:MGL ?= this } } }\n"
    "\tdynamic_country_name = { name = ywc_dyn_mgl_maritime adjective = ywc_dyn_mgl_maritime_adj "
    "is_main_tag_only = yes priority = 20 trigger = { exists = scope:actor scope:actor ?= { c:MGL ?= this ywc_has_maritime_network = yes } } }\n"
    "}"
)
if m:
    text = text[:m.start()] + mgl_block + text[m.end():]
else:
    text = text.rstrip() + "\n\n" + mgl_block + "\n"
dyn_path.write_text(text, encoding="utf-8-sig", newline="\n")
print("dynamic names: heritage entries dropped, MGL block installed")
