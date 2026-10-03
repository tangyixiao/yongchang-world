from pathlib import Path

files = [
    "docs/superpowers/specs/2026-09-26-受命于天-天命霸权设计.md",
    "docs/superpowers/plans/2026-09-26-受命于天实施计划.md",
    "README.md",
    "CHANGELOG.md",
    "docs/release/v0.1-acceptance.md",
]
for name in files:
    text = Path(name).read_text(encoding="utf-8-sig")
    stale = [line.strip()[:90] for line in text.splitlines() if ("顺我者昌" in line or "v0.2「顺" in line or "v0.2 顺" in line)]
    has_new = "受命于天" in text
    print(name, "| has-v1.0-title:", has_new, "| stale-lines:", len(stale))
    for line in stale:
        print("   STALE:", line)
# loc check
for lang in ("simp_chinese", "english"):
    t = Path(f"yongchang_world/localization/{lang}/ywc_hegemony_keys_l_{lang}.yml").read_text(encoding="utf-8-sig")
    for line in t.splitlines():
        if "ywc_je_hegemony_order:" in line:
            print(lang, "->", line.strip()[:70])
