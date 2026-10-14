import json
import subprocess
from pathlib import Path

ROOT = Path(".")

# southwest_states.json: Mandalay owner ARA -> RKN
p = ROOT / "data/scenario/southwest_states.json"
t = p.read_text(encoding="utf-8-sig")
t = t.replace('"target_country": "ARA"', '"target_country": "RKN"')
p.write_text(t, encoding="utf-8", newline="\n")
print("southwest_states ARA -> RKN")

# catalog: journal + marker keys
p = ROOT / "data/content/southwest_event_catalog.json"
t = p.read_text(encoding="utf-8-sig")
t = t.replace("ywc_je_sw_ark", "ywc_je_sw_rkn").replace("ywc_sw_ark_", "ywc_sw_rkn_")
p.write_text(t, encoding="utf-8", newline="\n")
print("catalog journal/marker keys -> rkn")

# content_starts journal type
p = ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt"
t = p.read_text(encoding="utf-8-sig")
t = t.replace("type = ywc_je_sw_ark", "type = ywc_je_sw_rkn")
p.write_text(t, encoding="utf-8-sig", newline="\n")
print("starts journal type -> rkn")

# SW keys loc
for language in ("simp_chinese", "english"):
    p = ROOT / f"yongchang_world/localization/{language}/ywc_southwest_keys_l_{language}.yml"
    t = p.read_text(encoding="utf-8-sig").replace("ywc_je_sw_ark", "ywc_je_sw_rkn")
    p.write_text(t, encoding="utf-8-sig", newline="\n")
print("SW keys loc -> rkn")

# emitter consistency (provenance)
p = ROOT / "artifacts/automation/emit_southwest_catalog.py"
t = p.read_text(encoding="utf-8")
t = t.replace('"ark", "ARK", "若开", "Arakan"', '"rkn", "RKN", "若开", "Arakan"')
p.write_text(t, encoding="utf-8", newline="\n")

# regenerate southwest content
r = subprocess.run(["python", "-X", "utf8", "tools/build_southwest_content.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print("sw regen:", r.returncode, (r.stdout or r.stderr)[-150:])
