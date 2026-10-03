# Fix stage C: geometric CoAs + flag definitions for every new-tag country
# that still lacks a flag (the engine default is the French tricolor, which is
# what the user saw on Lijiang).
import json
from pathlib import Path

ROOT = Path(".")
COA_PATH = ROOT / "yongchang_world/common/coat_of_arms/coat_of_arms/ywc_core_coas.txt"
FLAG_PATH = ROOT / "yongchang_world/common/flag_definitions/ywc_flags.txt"

PATTERNS = ["pattern_cross", "pattern_per_bend", "pattern_per_saltire", "pattern_circle",
            "pattern_gironny_8", "pattern_gironny_12", "pattern_border_of_3", "pattern_lozengy_bend"]
COLORS = ["red_china", "yellow", "azure", "white", "joseon_blue", "british_red",
          "red_dark", "orange", "green_dark", "finnish_brown"]

reg = json.loads((ROOT / "data/scenario/tag_registry.json").read_text(encoding="utf-8-sig"))
new_tags = [row["tag"] for row in reg["countries"] if row.get("mode") == "new"]

coa_text = COA_PATH.read_text(encoding="utf-8-sig")
flag_text = FLAG_PATH.read_text(encoding="utf-8-sig")

added_coa, added_flag = [], []
for index, tag in enumerate(new_tags):
    coa_name = f"YWC_{tag}"
    if f"{coa_name} = {{" in coa_text:
        continue
    pattern = PATTERNS[index % len(PATTERNS)]
    color1 = COLORS[index % len(COLORS)]
    color2 = COLORS[(index + 3) % len(COLORS)]
    if color2 == color1:
        color2 = COLORS[(index + 5) % len(COLORS)]
    coa_text += f'{coa_name} = {{ pattern = "{pattern}.dds" color1 = "{color1}" color2 = "{color2}" }}\n'
    added_coa.append(coa_name)
    if f"{tag} = {{" not in flag_text:
        flag_text += (
            f"{tag} = {{\n"
            f"\tflag_definition = {{ coa = {coa_name} priority = 5 trigger = {{ exists = c:{tag} }} }}\n"
            f"}}\n"
        )
        added_flag.append(tag)

COA_PATH.write_text(coa_text, encoding="utf-8-sig", newline="\n")
FLAG_PATH.write_text(flag_text, encoding="utf-8-sig", newline="\n")
print(f"added {len(added_coa)} CoAs and {len(added_flag)} flag definitions")
print("tags:", ", ".join(added_flag))
