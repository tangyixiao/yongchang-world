# Diagnose the in-game bugs reported from the 1836 lobby screenshots:
# 1. tag collisions between mod tags and vanilla tags
# 2. missing flag/coat-of-arms definitions for regional countries
# 3. diplomacy pacts referencing vanilla countries (France/Japan/Finland)
# 4. dynamic country names (大顺礼制国?)
import json
import re
from pathlib import Path

ROOT = Path(".")
baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
vanilla_tags = set(baseline.get("country_tags", []))
print(f"vanilla tags: {len(vanilla_tags)}")

reg = json.loads((ROOT / "data/scenario/tag_registry.json").read_text(encoding="utf-8"))
print("=== registry modes vs vanilla ===")
for row in reg["countries"]:
    tag = row["tag"]
    mode = row.get("mode")
    collides = tag in vanilla_tags
    flag = "COLLIDES" if (mode == "new" and collides) else ("reuse-ok" if mode == "reuse" and collides else ("new-ok" if mode == "new" and not collides else "REUSE-MISSING" if mode == "reuse" and not collides else "?"))
    print(f"{tag} {mode:6} vanilla={collides} -> {flag}  {row.get('name_zh','')}")

# what does vanilla ARA/LAD/MNP resolve to (english names from baseline if present)?
names = baseline.get("country_names", {})
for tag in ("ARA", "LAD", "MNP", "LJG", "SIP", "SHD", "DER", "KTG"):
    if tag in vanilla_tags:
        print("vanilla has", tag, "->", names.get(tag, "?"))

print("=== country_definitions blocks in mod ===")
defs = (ROOT / "yongchang_world/common/country_definitions").rglob("*.txt")
defined = set()
for path in defs:
    text = path.read_text(encoding="utf-8-sig")
    for m in re.finditer(r"(?m)^([A-Z]{3})\s*=\s*\{", text):
        defined.add(m.group(1))
print(sorted(defined))

print("=== flags / coats of arms present in mod ===")
for folder in ("common/flag_definitions", "common/coat_of_arms"):
    names_found = set()
    for path in (ROOT / "yongchang_world" / folder).rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        names_found |= set(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*=\s*\{", text))
    print(folder, "->", sorted(n for n in names_found if not n.startswith("#"))[:40])

print("=== diplomacy files: every c:TAG referenced ===")
for path in sorted((ROOT / "yongchang_world/common/history/diplomacy").glob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    tags = sorted(set(re.findall(r"c:([A-Z]{3})", text)))
    print(path.name, "->", tags)

print("=== dynamic country names ===")
for path in sorted((ROOT / "yongchang_world/common/dynamic_country_names").rglob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    if "礼制" in text or "顺" in text:
        for line in text.splitlines():
            if "礼制" in line or "大顺" in line:
                print(path.name, ":", line.strip()[:100])
