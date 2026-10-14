from pathlib import Path

block = Path("artifacts/automation/changelog_world_repair.txt").read_text(encoding="utf-8").rstrip()
p = Path("CHANGELOG.md")
t = p.read_text(encoding="utf-8-sig")
marker = "## Unreleased — v0.2 六六大顺: the six southwest countries"
i = t.find(marker)
assert i > 0, "marker not found"
t = t[:i] + block + "\n\n" + t[i:]
p.write_text(t, encoding="utf-8-sig", newline="\n")
print("CHANGELOG updated:", block[:60])
