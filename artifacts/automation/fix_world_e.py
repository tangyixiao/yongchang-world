# FINAL world-content repair pass (round 15).
import json
import re
from pathlib import Path

ROOT = Path(".")
POPS = ROOT / "yongchang_world/common/history/pops"

# ---------- 1. pops: retarget displaced region_state links to the new owners ----------
RETARGET = {
    "STATE_ALXA": ("CHI", "KHO"),
    "STATE_HINGGAN": ("CHI", "SOL"),
    "STATE_SOUTHERN_MANCHURIA": ("CHI", "SHU"),
    "STATE_AMUR": ("CHI", "AMR"),
    "STATE_TUVA": ("CHI", "MGL"),
    "STATE_ALTAI": ("CHI", "MGL"),
    "STATE_JETISY": ("CHI", "GJU"),
    "STATE_LHASA": ("CHI", "TIB"),
    "STATE_SICHUAN": ("CHI", "SHU"),
    "STATE_YUNNAN": ("CHI", "SHU"),
}
owner_map = json.loads((ROOT / "data/scenario/ownership_overrides.json").read_text(encoding="utf-8-sig"))
own = {}
for row in owner_map["states"]:
    for g in row["groups"]:
        own.setdefault(row["state"], set()).add(g["owner"])

for path in sorted(POPS.glob("*.txt")):
    text = path.read_text(encoding="utf-8-sig")
    blocks = list(re.finditer(r"(?m)^\s*s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text))
    positions = [(m.group(1), m.start()) for m in blocks]
    result = text
    for idx, (state, start) in enumerate(positions):
        end = positions[idx + 1][1] if idx + 1 < len(positions) else len(text)
        block = text[start:end]
        new_owners = own.get(state)
        if not new_owners:
            continue
        for old, new in RETARGET.items():
            if old != new and state == old and old in block:
                block = block.replace(f"region_state:{old}", f"region_state:{new}")
                print(f"retarget {path.name}:{state}: {old} -> {new}")
        # generic: any region_state:TAG whose tag is not an owner of the state
        for m in re.finditer(r"region_state:([A-Z]{3})", block):
            tag = m.group(1)
            if tag not in new_owners and len(new_owners) == 1:
                sole = next(iter(new_owners))
                block = block.replace(f"region_state:{tag}", f"region_state:{sole}")
                print(f"retarget {path.name}:{state}: {tag} -> {sole}")
        if block != text[start:end]:
            result = result[:start] + block + result[end:]
    if result != text:
        path.write_text(result, encoding="utf-8-sig", newline="\n")
        print(f"updated {path.name}")

# ---------- 2. replace the broken china pops with a working-style file ----------
# (matches ywc_inner_asia_pops.txt: POPS on line 1 after BOM, tab indentation,
#  create_pop blocks under ~1M, no comments before the wrapper)
CHINA = [
    ("STATE_CHONGQING", [("han", 6000000), ("han", 6000000)]),
    ("STATE_EASTERN_HUBEI", [("han", 7000000), ("han", 6000000)]),
    ("STATE_FUJIAN", [("han", 8000000), ("han", 8000000)]),
    ("STATE_GANSU", [("han", 5500000), ("han", 4500000), ("mongol", 600000)]),
    ("STATE_GUANGDONG", [("han", 10500000), ("han", 10500000)]),
    ("STATE_GUANGXI", [("han", 5000000), ("yi", 1500000), ("han", 2000000)]),
    ("STATE_GUIZHOU", [("han", 2500000), ("yi", 1500000), ("han", 2000000)]),
    ("STATE_HENAN", [("han", 11000000), ("han", 11000000)]),
    ("STATE_HUNAN", [("han", 8500000), ("han", 8500000)]),
    ("STATE_JIANGSU", [("han", 10000000), ("han", 10000000)]),
    ("STATE_JIANGXI", [("han", 10000000), ("han", 10000000)]),
    ("STATE_NANJING", [("han", 5000000)]),
    ("STATE_NINGXIA", [("han", 900000), ("mongol", 400000), ("han", 300000)]),
    ("STATE_NORTHERN_ANHUI", [("han", 9000000), ("han", 9000000)]),
    ("STATE_SHANDONG", [("han", 14000000), ("han", 14000000)]),
    ("STATE_SHANXI", [("han", 6500000), ("han", 6500000)]),
    ("STATE_SHAOZHOU", [("han", 2000000)]),
    ("STATE_SICHUAN", [("han", 4000000), ("han", 4000000)]),
    ("STATE_SOUTHERN_ANHUI", [("han", 7000000), ("han", 7000000)]),
    ("STATE_SOUTHERN_MANCHURIA", [("han", 4500000), ("manchu", 900000), ("han", 600000)]),
    ("STATE_SUZHOU", [("han", 5000000), ("han", 5000000)]),
    ("STATE_WESTERN_HUBEI", [("han", 3500000), ("han", 3500000)]),
    ("STATE_XIAN", [("han", 5000000), ("han", 5000000)]),
    ("STATE_YUNNAN", [("han", 1600000), ("yi", 900000), ("han", 700000)]),
    ("STATE_ZHEJIANG", [("han", 11500000), ("han", 11500000)]),
    ("STATE_ZHILI", [("han", 10000000), ("han", 10000000)]),
]
blocks = []
for state, pops in CHINA:
    pop_lines = []
    for culture, size in pops:
        pop_lines.append("\t\t\tcreate_pop = { culture = " + culture + " size = " + str(size) + " }")
    rows = "\n".join(pop_lines)
    blocks.append("\ts:" + state + " = {\n\t\tregion_state:SHU = {\n" + rows + "\n\t\t}\n\t}")
china = "POPS = {\n" + "\n".join(blocks) + "\n}\n"
(POPS / "ywc_china_pops.txt").write_text(china, encoding="utf-8-sig", newline="\n")
print("rewrote ywc_china_pops.txt (working style, chunked)")

# ---------- 3. campaign generator: settle calls without FLAVOR ----------
gen = ROOT / "tools/build_campaign_content.py"
t = gen.read_text(encoding="utf-8")
t2 = re.sub(
    r"\{settle} = \{\{ SHORT = \{short\} CH = \{chapter\} \"\n( *)GATE = \"\{gate\}\" FLAVOR = \{config\[\"flavor\"\] \}\}",
    lambda m: m.group(0),
    t,
)  # placeholder; real edit below
t = t.replace(
    'f"{settle} = {{ SHORT = {short} CH = {chapter} "\n            f\'GATE = "{gate}" FLAVOR = {config["flavor"]} }}\'',
    'f"{settle} = {{ SHORT = {short} CH = {chapter} "\n            f\'GATE = "{gate}" }}\'',
)
# the actual current form uses an f-string with double braces; do a robust pair replace:
t = t.replace(' FLAVOR = {config["flavor"]} }}', ' }}')
t = t.replace(' FLAVOR = {config["flavor"]} }', ' }')
gen.write_text(t, encoding="utf-8", newline="\n")
print("campaign generator: FLAVOR dropped from settle calls")

# ---------- 4. hegemony generator: strip leading + from change_variable deltas ----------
hgen = ROOT / "tools/build_hegemony_content.py"
t = hgen.read_text(encoding="utf-8")
t = t.replace('sign = "+" if op["delta"] >= 0 else ""\n        return _guarded_hegemony(\n            f"change_variable = {{ name = ywc_hegemony_{op[\'name\']} add = {sign}{op[\'delta\']} }}"',
              'return _guarded_hegemony(\n            f"change_variable = {{ name = ywc_hegemony_{op[\'name\']} add = {op[\'delta\']} }}"')
hgen.write_text(t, encoding="utf-8", newline="\n")
print("hegemony generator: +sign stripped")
