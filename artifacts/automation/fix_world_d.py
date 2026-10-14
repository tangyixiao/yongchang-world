# Final alignment: ARK -> RKN (ARK collides with a vanilla tag), MANDALAY
# override groups aligned with the shipped ledger (4/4), EZO pops for
# Sakhalin, MGL dynamic block removed (vanilla list redeclaration guardrail),
# regional CoAs moved to their own file (the core CoA count contract stays).
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")

def sub_in(path: Path, pairs, encoding="utf-8-sig"):
    text = path.read_text(encoding=encoding)
    changed = False
    for old, new in pairs:
        if old in text:
            text = text.replace(old, new)
            changed = True
    if changed:
        path.write_text(text, encoding=encoding, newline="\n")
        print("updated", path)

# 1. ARK -> RKN everywhere
pairs = [("c:ARK", "c:RKN"), ("ywc_ark", "ywc_rkn"), ("YWC_ARK", "YWC_RKN"),
         ('"tag": "ARK"', '"tag": "RKN"'), ('"short": "ark"', '"short": "rkn"'),
         ("region_state:ARK", "region_state:RKN"), ("ARK = {", "RKN = {")]
for rel in ("data/scenario/tag_registry.json",
            "yongchang_world/common/country_definitions/ywc_regional_countries.txt",
            "yongchang_world/common/history/states/00_states.txt",
            "yongchang_world/common/history/pops/ywc_southwest_pops.txt",
            "data/content/southwest_event_catalog.json",
            "yongchang_world/common/journal_entries/ywc_southwest_journal.txt",
            "yongchang_world/common/history/countries/ywc_regional_countries.txt",
            "yongchang_world/localization/simp_chinese/ywc_southwest_keys_l_simp_chinese.yml",
            "yongchang_world/localization/english/ywc_southwest_keys_l_english.yml",
            "artifacts/automation/emit_southwest_catalog.py",
            "artifacts/automation/fix_world_c.py"):
    sub_in(ROOT / rel, pairs)
# regenerate southwest content with the renamed catalog
import subprocess
r = subprocess.run(["python", "-X", "utf8", "tools/build_southwest_content.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print("sw regen:", r.returncode, (r.stdout or r.stderr)[-120:])

# 2. MANDALAY override groups: match the shipped ledger's create_state count
LEDGER = ROOT / "yongchang_world/common/history/states/00_states.txt"
OV_PATH = ROOT / "data/scenario/ownership_overrides.json"
ledger = LEDGER.read_text(encoding="utf-8-sig")
ov = json.loads(OV_PATH.read_text(encoding="utf-8-sig"))

def template_block(text, state):
    m = re.search(rf"(?m)^\s*s:{state}\s*=\s*\{{", text)
    nxt = re.search(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{{", text[m.end():])
    return text[m.start():m.end() + (nxt.start() if nxt else len(text) - m.end())]

by_state = {row["state"]: row for row in ov["states"]}
for state in ("STATE_SICHUAN", "STATE_YUNNAN"):
    block = template_block(ledger, state)
    creates = re.findall(r"country = c:([A-Z]{3})\s*\n\s*owned_provinces\s*=\s*\{([^}]*)\}", block)
    groups = []
    for owner, plist in creates:
        provinces = plist.split()
        existing = next((g for g in by_state[state]["groups"] if g["owner"] == owner), None)
        if existing and set(existing["owned_provinces"]) == set(provinces):
            groups.append(existing)
        else:
            groups.append({"owner": owner, "owned_provinces": provinces})
    by_state[state]["groups"] = groups
    print(state, "->", [(g["owner"], len(g["owned_provinces"])) for g in groups])
OV_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 3. EZO pops on Sakhalin
ne_path = ROOT / "yongchang_world/common/history/pops/ywc_northeast_pops.txt"
ne = ne_path.read_text(encoding="utf-8-sig")
if "region_state:EZO" not in ne or "STATE_SAKHALIN" not in ne:
    block = (
        "    s:STATE_SAKHALIN = {\n"
        "        region_state:EZO = {\n"
        "            create_pop = { culture = ainu size = 42000 }\n"
        "            create_pop = { culture = siberian size = 26000 }\n"
        "        }\n"
        "    }\n"
    )
    ne = ne.rstrip()[:-1] + "\n" + block + "}\n"
    ne_path.write_text(ne, encoding="utf-8-sig", newline="\n")
    print("added EZO Sakhalin pops")

# 4. remove the MGL dynamic block (vanilla list redeclaration guardrail)
dyn_path = ROOT / "yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt"
dyn = dyn_path.read_text(encoding="utf-8-sig")
m = re.search(r"MGL = \{.*?\n\}", dyn, re.S)
if m:
    dyn = dyn[:m.start()] + dyn[m.end():]
    dyn_path.write_text(dyn, encoding="utf-8-sig", newline="\n")
    print("removed MGL dynamic block (guardrail)")

# 5. regional CoAs: move out of the core file
coa_core = ROOT / "yongchang_world/common/coat_of_arms/coat_of_arms/ywc_core_coas.txt"
coa_reg = ROOT / "yongchang_world/common/coat_of_arms/coat_of_arms/ywc_regional_coas.txt"
core_text = coa_core.read_text(encoding="utf-8-sig")
lines = core_text.split("\n")
regional, kept = [], []
for line in lines:
    m = re.match(r"(YWC_[A-Z]{3}) =", line)
    if m and not (m.group(1).endswith("_MARITIME")) and m.group(1) not in {
        "YWC_SHU", "YWC_JHG", "YWC_DMG", "YWC_NQG", "YWC_OIR", "YWC_TIB",
        "YWC_KOR", "YWC_LAN", "YWC_MNG", "YWC_NMG",
    }:
        regional.append(line)
    else:
        kept.append(line)
if regional:
    coa_core.write_text("\n".join(kept), encoding="utf-8-sig", newline="\n")
    existing = coa_reg.read_text(encoding="utf-8-sig") if coa_reg.exists() else ""
    coa_reg.write_text(existing + "\n".join(regional), encoding="utf-8-sig", newline="\n")
print(f"moved {len(regional)} regional CoAs to ywc_regional_coas.txt")
