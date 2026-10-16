"""Fixed v0.3 content owners and immutable numeric slot assignments."""

COUNTRY_TAGS = ("SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG")
COUNTRY_NAMESPACES = {
    "SHU": "ywc_shu", "JHG": "ywc_jhg", "DMG": "ywc_dmg", "NQG": "ywc_nqg",
    "OIR": "ywc_oir", "MGL": "ywc_mng", "TIB": "ywc_tib", "KOR": "ywc_kor",
    "LAN": "ywc_lan", "NMG": "ywc_nmg",
}
REGIONAL_TAGS = ("CHI KHQ HUL SOL AMR KZH OZH UZH ODS CHR BKY BYL JTR NMN KER ZHL ABN KIR HMI TRF KUC KSH YRK KHT AKS TSK SMR KRS KGL MEV SHB HSR DRZ QRT TKK YMD LAD KHO KAM LXJ AMD CHD HOR LTG HXI KTG WAA KCH AHM DLI WBK PNP PLW YAP MHL MRG LJG SIP DER GYL SHD RKN MHG").split()
CRISIS_OWNERS = tuple(f"C{i:02d}" for i in range(1, 9))
THEME_OWNERS = tuple(f"T{i:02d}" for i in range(1, 13))
EXPECTED_OWNERS = {"country": COUNTRY_TAGS, "crisis": CRISIS_OWNERS, "regional": tuple(REGIONAL_TAGS), "theme": THEME_OWNERS}
NAMESPACE_LIMITS = {
    "country": (1000, 1999), "crisis": (1000, 1799),
    "regional": (1000, 7299), "theme": (1000, 1599),
}
OWNER_SLOTS = {
    "regional": {tag: (1000 + i * 100, 1099 + i * 100) for i, tag in enumerate(REGIONAL_TAGS)},
    "crisis": {owner: (1000 + i * 100, 1099 + i * 100) for i, owner in enumerate(CRISIS_OWNERS)},
    "theme": {owner: (1000 + i * 50, 1049 + i * 50) for i, owner in enumerate(THEME_OWNERS)},
}


def arc_owner(layer, arc, runtime_tags):
    owner = arc.get("owner")
    if layer == "country" and owner is None and isinstance(runtime_tags, list) and len(runtime_tags) == 1:
        return runtime_tags[0]
    return owner


def owner_slot(layer, owner):
    return OWNER_SLOTS.get(layer, {}).get(owner)
