from pathlib import Path

# 00_states.txt: normalize the two inserted SHU city blocks to pure tabs
p = Path("yongchang_world/common/history/states/00_states.txt")
text = p.read_text(encoding="utf-8-sig")
lines = text.split("\n")
fixed = []
for line in lines:
    if "country = c:MGL" in line or "country = c:AMR" in line:
        stripped = line.lstrip()
        if stripped.startswith("country = c:"):
            line = "\t\t" + stripped
    fixed.append(line)
text = "\n".join(fixed)
# also normalize the neighboring inserted lines (create_state/owned_provinces/closing)
text = text.replace("\n \t+\t", "\n\t\t")
text = re.sub(r"(?m)^[ \t]+\t(\t*)", r"\t\t\1", "\n".join([]) or text) if False else text
p.write_text(text, encoding="utf-8-sig", newline="\n")
print("states whitespace normalized")

# dynamic names: strip trailing blank lines
p = Path("yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt")
text = p.read_text(encoding="utf-8-sig").rstrip("\n") + "\n"
p.write_text(text, encoding="utf-8-sig", newline="\n")
print("dynamic names EOF cleaned")
