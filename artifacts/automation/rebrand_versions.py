# Rebrand the hegemony batch: v0.2 顺我者昌，逆我者亡 -> v1.0 受命于天，既寿永昌.
from pathlib import Path

ROOT = Path(".")

REPLACEMENTS = {
    "docs/superpowers/specs/2026-09-26-受命于天-天命霸权设计.md": [
        ("# 《永昌世界》v0.2「顺我者昌，逆我者亡」设计",
         "# 《永昌世界》v1.0「受命于天，既寿永昌」先行层：天命霸权设计"),
        ("v0.2「顺我者昌，逆我者亡」", "v1.0「受命于天，既寿永昌」"),
    ],
    "docs/superpowers/plans/2026-09-26-受命于天实施计划.md": [
        ("# 《永昌世界》v0.2「顺我者昌，逆我者亡」实施计划",
         "# 《永昌世界》v1.0「受命于天，既寿永昌」先行层实施计划"),
        ("v0.2「顺我者昌，逆我者亡」", "v1.0「受命于天，既寿永昌」"),
    ],
    "README.md": [
        ("## v0.2「顺我者昌，逆我者亡」：天命霸权层（2026-09-26）",
         "## v1.0「受命于天，既寿永昌」先行层：天命霸权（2026-09-26）"),
    ],
    "CHANGELOG.md": [
        ("## Unreleased — v0.2 顺我者昌，逆我者亡: the hegemony layer",
         "## Unreleased — v1.0 受命于天，既寿永昌 (first layer): the hegemony system"),
    ],
    "docs/release/v0.1-acceptance.md": [
        ("**v0.2 顺我者昌，逆我者亡** — the hegemony layer",
         "**v1.0 受命于天，既寿永昌** — the hegemony layer (first v1.0 batch)"),
        ("**v0.2 顺我者昌，逆我者亡** — the hegemony layer (33 events",
         "**v1.0 受命于天，既寿永昌** — the hegemony layer (33 events"),
    ],
}

for relative, pairs in REPLACEMENTS.items():
    path = ROOT / relative
    text = path.read_text(encoding="utf-8-sig")
    for old, new in pairs:
        if old in text:
            text = text.replace(old, new)
        else:
            print(f"NOTE: pattern not found in {relative}: {old[:50]}")
    path.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"rebranded {relative}")

# Hegemony journal display name follows the version title.
loc_path = Path("artifacts/automation/emit_hegemony_scripts.py")
text = loc_path.read_text(encoding="utf-8")
text = text.replace(
    '"ywc_je_hegemony_order": "天命霸权：顺我者昌"',
    '"ywc_je_hegemony_order": "受命于天，既寿永昌——天命霸权"',
)
text = text.replace(
    '"ywc_je_hegemony_order": "The Mandate: Submit and Prosper"',
    '"ywc_je_hegemony_order": "The Mandate of Heaven: Enduring Prosperity"',
)
loc_path.write_text(text, encoding="utf-8", newline="\n")
print("updated hegemony loc emitter")
