from pathlib import Path

p = Path("CHANGELOG.md")
lines = p.read_text(encoding="utf-8-sig").split("\n")
# drop the duplicated '# Changelog' line(s) right after the first one
out = [lines[0]]
seen_header = 0
for line in lines[1:]:
    if line.strip() == "# Changelog":
        seen_header += 1
        continue
    out.append(line)
p.write_text("\n".join(out), encoding="utf-8-sig", newline="\n")
print("removed", seen_header, "duplicate headers")
