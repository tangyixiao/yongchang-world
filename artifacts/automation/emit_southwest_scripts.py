# One-off emitter: v0.2 六六大顺 supporting content —
# 1. add ywc_reset_shared_variables + the six journal adds to each country's
#    block in ywc_regional_countries.txt (reset must precede the journal adds,
#    per the shared-variable initialization gate);
# 2. append the eight southwest static modifiers;
# 3. write the journal/modifier bilingual key files.
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LINES = [
    ("ljg", "LJG", "丽江国", "Lijiang"),
    ("sip", "SIP", "西双版纳", "Sipsongpanna"),
    ("der", "DER", "德格王国", "Derge"),
    ("gyl", "GYL", "嘉绒联盟", "Gyalrong League"),
    ("shd", "SHD", "掸邦联盟", "Shan Confederation"),
    ("ara", "ARA", "若开", "Arakan"),
]

STARTS_PATH = ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt"
MODIFIERS_PATH = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"

STATIC_MODIFIERS = '''
ywc_sw_tea_charter = {
    country_authority_mult = 0.02
    country_bureaucracy_mult = 0.01
}

ywc_sw_market_open = {
    country_authority_mult = 0.01
    country_legitimacy_base_add = 2
}

ywc_sw_caravan_guard = {
    country_authority_mult = 0.02
    country_loan_interest_rate_mult = -0.01
}

ywc_sw_drill_effect = {
    country_authority_mult = 0.03
    country_legitimacy_base_add = 2
}

ywc_sw_levy_burden = {
    country_authority_mult = -0.01
    country_legitimacy_base_add = -3
}

ywc_sw_poppy_shadow = {
    country_authority_mult = -0.02
    country_legitimacy_base_add = -6
}

ywc_sw_rice_contract = {
    country_legitimacy_base_add = 1
    country_loan_interest_rate_mult = -0.02
}

ywc_sw_exile_strain = {
    country_authority_mult = -0.01
    country_legitimacy_base_add = -2
}
'''

LOC_CN = {
    "ywc_je_sw_ljg": "茶马引盐",
    "ywc_je_sw_ljg_reason": "大顺整饬西南商路，丽江木氏在引权、藏商与继嗣之间步步取舍。",
    "ywc_je_sw_sip": "十二版纳",
    "ywc_je_sw_sip_reason": "茶山、缅使与摊派——车里宣慰司在两个朝廷之间求全。",
    "ywc_je_sw_der": "印经银钱",
    "ywc_je_sw_der_reason": "德格以印经立国，僧俗与商路之争皆系于银钱。",
    "ywc_je_sw_gyl": "戎马屯田",
    "ywc_je_sw_gyl_reason": "嘉绒七部在屯田、练军与盟主之位上寻找新的均势。",
    "ywc_je_sw_shd": "三十七土司",
    "ywc_je_sw_shd_reason": "掸邦联席会议议贡额、设官与山地生计。",
    "ywc_je_sw_ara": "两属之邦",
    "ywc_je_sw_ara_reason": "若开在英国保护与缅甸影响之间维持门面。",
    "ywc_sw_tea_charter": "茶马新章",
    "ywc_sw_market_open": "互市开城",
    "ywc_sw_caravan_guard": "护商之约",
    "ywc_sw_drill_effect": "练军之效",
    "ywc_sw_levy_burden": "摊派之累",
    "ywc_sw_poppy_shadow": "烟祸蔓延",
    "ywc_sw_rice_contract": "稻米专约",
    "ywc_sw_exile_strain": "流亡之累",
}
LOC_EN = {
    "ywc_je_sw_ljg": "Tea, Horses and Salt",
    "ywc_je_sw_ljg_reason": "As Shun reorganizes the southwest roads, Lijiang's Mu clan bargains over licences, caravans and succession.",
    "ywc_je_sw_sip": "The Twelve Banners",
    "ywc_je_sw_sip_reason": "Tea hills, a Burmese envoy and shared levies: the mandala between two courts.",
    "ywc_je_sw_der": "Silver for the Canon",
    "ywc_je_sw_der_reason": "Derge lives by its printing house; monks, ministers and caravans all turn on the silver.",
    "ywc_je_sw_gyl": "Farms and Banners",
    "ywc_je_sw_gyl_reason": "The Gyalrong tribes balance farm colonies, drilled muskets and the league chair.",
    "ywc_je_sw_shd": "The Thirty-Seven Chiefs",
    "ywc_je_sw_shd_reason": "The Shan council sets tribute, magistrates and the hill economy.",
    "ywc_je_sw_ara": "Between Two Courts",
    "ywc_je_sw_ara_reason": "Arakan keeps its face between the British Residency and the Burmese court.",
    "ywc_sw_tea_charter": "Tea-Horse Charter",
    "ywc_sw_market_open": "Open Market",
    "ywc_sw_caravan_guard": "Caravan Escort Pact",
    "ywc_sw_drill_effect": "Drilled in the New Way",
    "ywc_sw_levy_burden": "Shared Levy Burden",
    "ywc_sw_poppy_shadow": "Poppy Blight",
    "ywc_sw_rice_contract": "Rice Contract",
    "ywc_sw_exile_strain": "Strain of the Exiles",
}


def patch_starts() -> None:
    text = STARTS_PATH.read_text(encoding="utf-8-sig")
    total = 0
    for short, tag, _cn, _en in LINES:
        pattern = re.compile(rf"(?m)^(    c:{tag} \?=\s*\{{\n)")
        match = pattern.search(text)
        assert match, tag
        if f"ywc_je_sw_{short}" in text:
            continue
        insertion = (
            "        ywc_reset_shared_variables = yes\n"
            f"        add_journal_entry = {{ type = ywc_je_sw_{short} }}\n"
        )
        text = text[:match.end()] + insertion + text[match.end():]
        total += 1
    STARTS_PATH.write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"patched {total} regional country blocks")


def append_modifiers() -> None:
    text = MODIFIERS_PATH.read_text(encoding="utf-8-sig")
    assert "ywc_sw_tea_charter" not in text
    text = text.rstrip("\n") + "\n" + STATIC_MODIFIERS
    MODIFIERS_PATH.write_text(text, encoding="utf-8-sig", newline="\n")
    print("appended southwest static modifiers")


def write_loc() -> None:
    for language, table in (("simp_chinese", LOC_CN), ("english", LOC_EN)):
        root_key = "l_simp_chinese:" if language == "simp_chinese" else "l_english:"
        rows = [root_key]
        for key, value in table.items():
            rows.append(f' {key}:0 "{value}"')
        path = ROOT / f"yongchang_world/localization/{language}/ywc_southwest_keys_l_{language}.yml"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig", newline="\n")
        print(f"wrote {path.name}")


STEPS = {"starts": patch_starts, "modifiers": append_modifiers, "loc": write_loc}


def main() -> int:
    import sys

    for step in sys.argv[1:] or list(STEPS):
        STEPS[step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
