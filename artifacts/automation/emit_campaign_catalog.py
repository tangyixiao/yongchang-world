# One-off emitter: build data/content/large_campaign_event_catalog.json from the
# approved 2026-09-25 event card specs plus the English copy table.
# The catalog is the committed source of truth for tools/build_campaign_content.py.
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/superpowers/specs"
OUT = ROOT / "data/content/large_campaign_event_catalog.json"

COUNTRIES = {
    "shu": {
        "tag": "SHU", "name_cn": "大顺", "name_en": "Shun",
        "flavor": "ywc_flavor_shu_court_balance", "journal_stem": "shu_court",
        "preludes": {"1": "ywc_shu.7", "2": "ywc_shu.8", "3": "ywc_shu.9"},
        "cost": 5000,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "exists = c:JHG",
        },
        "crisis_start": {},
    },
    "jhg": {
        "tag": "JHG", "name_cn": "靖海", "name_en": "Jinghai",
        "flavor": "ywc_flavor_jhg_convoy_commitment", "journal_stem": "jhg_convoy",
        "preludes": {"1": "ywc_jhg.6", "2": "ywc_jhg.7", "3": "ywc_jhg.8"},
        "cost": 1200,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "ywc_has_maritime_network = yes",
            "3": "exists = c:SHU",
        },
        "crisis_start": {
            "1": {"crisis": 4},
            "2": {"crisis": 1, "cross_holder": "SHU"},
        },
    },
    "dmg": {
        "tag": "DMG", "name_cn": "东明", "name_en": "Dongming",
        "flavor": "ywc_flavor_dmg_huafei_compact", "journal_stem": "dmg_compact",
        "preludes": {"1": "ywc_dmg.6", "2": "ywc_dmg.7", "3": "ywc_dmg.8"},
        "cost": 700,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "exists = c:SPA",
        },
        "crisis_start": {},
    },
    "nqg": {
        "tag": "NQG", "name_cn": "北清", "name_en": "Northern Qing",
        "flavor": "ywc_flavor_nqg_island_supply", "journal_stem": "nqg_supply",
        "preludes": {"1": "ywc_nqg.6", "2": "ywc_nqg.7", "3": "ywc_nqg.8"},
        "cost": 500,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "ywc_has_maritime_network = yes",
            "3": "OR = { exists = c:RUS exists = c:JAP }",
        },
        "crisis_start": {"1": {"crisis": 2}},
    },
    "oir": {
        "tag": "OIR", "name_cn": "卫拉特", "name_en": "Oirat",
        "flavor": "ywc_flavor_oir_banner_cohesion", "journal_stem": "oir_banner",
        "preludes": {"1": "ywc_oir.7", "2": "ywc_oir.8", "3": "ywc_oir.9"},
        "cost": 1200,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "OR = { exists = c:RUS exists = c:SHU }",
        },
        "crisis_start": {"1": {"crisis": 3}},
    },
    "mng": {
        "tag": "MGL", "name_cn": "喀尔喀", "name_en": "Khalkha",
        "flavor": "ywc_flavor_mng_south_north_balance", "journal_stem": "mng_balance",
        "preludes": {"1": "ywc_mng.7", "2": "ywc_mng.8", "3": "ywc_mng.9"},
        "cost": 350,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "OR = { exists = c:RUS exists = c:SHU }",
        },
        "crisis_start": {},
    },
    "tib": {
        "tag": "TIB", "name_cn": "西藏", "name_en": "Tibet",
        "flavor": "ywc_flavor_tib_estate_reform", "journal_stem": "tib_estate",
        "preludes": {"1": "ywc_tib.7", "2": "ywc_tib.8", "3": "ywc_tib.9"},
        "cost": 350,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "OR = { exists = c:OIR exists = c:MGL }",
            "3": "NOT = { is_at_war = yes }",
        },
        "crisis_start": {},
    },
    "kor": {
        "tag": "KOR", "name_cn": "朝鲜", "name_en": "Korea",
        "flavor": "ywc_flavor_kor_court_reform", "journal_stem": "kor_reform",
        "preludes": {"1": "ywc_kor.7", "2": "ywc_kor.8", "3": "ywc_kor.9"},
        "cost": 1200,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "OR = { exists = c:JAP exists = c:SHU }",
        },
        "crisis_start": {},
    },
    "lan": {
        "tag": "LAN", "name_cn": "兰芳", "name_en": "Lanfang",
        "flavor": "ywc_flavor_lan_company_charter", "journal_stem": "lan_charter",
        "preludes": {"1": "ywc_lan.7", "2": "ywc_lan.8", "3": "ywc_lan.9"},
        "cost": 250,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "NOT = { is_at_war = yes }",
            "3": "exists = c:HOL",
        },
        "crisis_start": {},
    },
    "nmg": {
        "tag": "NMG", "name_cn": "新明", "name_en": "New Ming",
        "flavor": "ywc_flavor_nmg_federal_bargain", "journal_stem": "nmg_bargain",
        "preludes": {"1": "ywc_nmg.6", "2": "ywc_nmg.7", "3": "ywc_nmg.8"},
        "cost": 600,
        "gates": {
            "1": "NOT = { is_at_war = yes }",
            "2": "exists = c:MEX",
            "3": "OR = { exists = c:USA exists = c:MEX }",
        },
        "crisis_start": {"2": {"crisis": 5}},
    },
}

CRISES = {
    "1": {
        "journal": "ywc_je_crisis_suzerainty",
        "name_cn": "天下名分与宗藩再议", "name_en": "Renegotiating the Tributary Order",
        "holder": "SHU", "holder_fallback": "JHG",
        "participants": ["SHU", "JHG", "KOR", "DMG"],
        "cost": 1200,
        "settle_full": (
            "NOT = { is_at_war = yes } "
            "c:JHG ?= { var:ywc_campaign_crisis1_s2_answer = 1 } "
            "c:SHU ?= { var:ywc_campaign_crisis1_s4_answer = 1 }"
        ),
        "starters": [("jhg", "2")],
    },
    "2": {
        "journal": "ywc_je_crisis_blackwater",
        "name_cn": "黑水边疆", "name_en": "The Blackwater Frontier",
        "holder": "NQG", "holder_fallback": "SHU",
        "participants": ["NQG", "SHU", "MGL", "RUS", "JAP"],
        "cost": 700,
        "settle_full": (
            "NOT = { is_at_war = yes } "
            "c:SHU ?= { var:ywc_campaign_crisis2_s8_answer = 1 } "
            "c:NQG ?= { var:ywc_campaign_crisis2_s10_answer = 1 }"
        ),
        "starters": [("nqg", "1")],
    },
    "3": {
        "journal": "ywc_je_crisis_inner_asian_routes",
        "name_cn": "草原与高原商路", "name_en": "Steppe and Highland Trade Routes",
        "holder": "OIR", "holder_fallback": "MGL",
        "participants": ["OIR", "MGL", "TIB", "SHU"],
        "cost": 600,
        "settle_full": (
            "NOT = { is_at_war = yes } "
            "c:SHU ?= { var:ywc_campaign_crisis3_s14_answer = 1 } "
            "c:OIR ?= { var:ywc_campaign_crisis3_s16_answer = 1 }"
        ),
        "starters": [("oir", "1")],
    },
    "4": {
        "journal": "ywc_je_crisis_south_seas",
        "name_cn": "南洋航路", "name_en": "South Sea Navigation",
        "holder": "JHG", "holder_fallback": "DMG",
        "participants": ["JHG", "DMG", "LAN", "SPA", "HOL"],
        "cost": 1200,
        "settle_full": (
            "NOT = { is_at_war = yes } "
            "c:DMG ?= { var:ywc_campaign_crisis4_s20_answer = 1 } "
            "c:JHG ?= { var:ywc_campaign_crisis4_s22_answer = 1 }"
        ),
        "starters": [("jhg", "1")],
    },
    "5": {
        "journal": "ywc_je_crisis_pacific_autonomy",
        "name_cn": "太平洋自治争议", "name_en": "Pacific Autonomy",
        "holder": "NMG", "holder_fallback": "NMG",
        "participants": ["NMG", "MEX", "USA"],
        "cost": 700,
        "settle_full": (
            "NOT = { is_at_war = yes } "
            "c:MEX ?= { var:ywc_campaign_crisis5_s26_answer = 1 } "
            "c:NMG ?= { var:ywc_campaign_crisis5_s28_answer = 1 }"
        ),
        "starters": [("nmg", "2")],
    },
}

# Per crisis stage: (answerer tag, fallback chain), partner for relations, budget weight.
CRISIS_STAGES = {
    "1": {1: ("SHU", []), 2: ("JHG", []), 3: ("KOR", []), 4: ("SHU", []), 5: ("JHG", []), 6: ("SHU", [])},
    "2": {1: ("NQG", []), 2: ("SHU", []), 3: ("MGL", []), 4: ("NQG", []), 5: ("SHU", []), 6: ("NQG", [])},
    "3": {1: ("OIR", []), 2: ("SHU", []), 3: ("MGL", []), 4: ("TIB", []), 5: ("OIR", []), 6: ("OIR", [])},
    "4": {1: ("JHG", []), 2: ("DMG", []), 3: ("ESP", ["NED", "LAN"]), 4: ("JHG", []), 5: ("LAN", []), 6: ("JHG", [])},
    "5": {1: ("NMG", []), 2: ("MEX", []), 3: ("USA", []), 4: ("NMG", []), 5: ("NMG", []), 6: ("NMG", [])},
}
CRISIS_PARTNER = {
    "1": {2: "SHU", 3: "SHU", 5: "SHU"},
    "2": {2: "NQG", 3: "NQG", 5: "NQG"},
    "3": {2: "OIR", 3: "OIR", 5: "TIB"},
    "4": {2: "JHG", 3: "JHG", 5: "JHG"},
    "5": {2: "NMG", 3: "NMG", 5: "NMG"},
}
CRISIS_STAGE_CN = {1: "请愿", 2: "回应", 3: "第三方", 4: "筹资", 5: "临界点", 6: "结算"}
CRISIS_STAGE_EN = {
    1: "Petition and Proposal", 2: "The Counterpart's Reply", 3: "A Third-Party Response",
    4: "Funding the Terms", 5: "The Crisis Point", 6: "Confirmation and Settlement",
}
CRISIS_STAGE_DESC_EN = {
    ("1", 1): "Shun and Jinghai debate a shared diplomatic style for the tributary order.",
    ("1", 2): "The counterpart answers the proposal on tariffs and navigation rights.",
    ("1", 3): "Korea answers on its own behalf; Dongming may respond to the trade clauses.",
    ("1", 4): "The signatories review the envoy and tariff budgets.",
    ("1", 5): "The proposer handles rejection and domestic opposition.",
    ("1", 6): "The actual signatories confirm the terms in turn.",
    ("2", 1): "Northern Qing petitions for joint surveying and frontier patrols.",
    ("2", 2): "The main neighbour answers the border-market proposal.",
    ("2", 3): "The outside powers answer with guarantees, demands or non-alignment.",
    ("2", 4): "The participants budget the posts and roads.",
    ("2", 5): "The sides handle goods seized at the border market.",
    ("2", 6): "The participants confirm the frontier arrangement.",
    ("3", 1): "The holder publishes the low-tax transit routes.",
    ("3", 2): "The main transit neighbour answers with a passage note.",
    ("3", 3): "Local banners, monasteries and merchants answer the rules.",
    ("3", 4): "The signatories budget the stations and patrols.",
    ("3", 5): "The sides handle a blocked pass or a disputed market.",
    ("3", 6): "The signatories confirm passage rights.",
    ("4", 1): "The holder proposes unified harbour rules and convoy terms.",
    ("4", 2): "The main rival answers the mutual flag recognition.",
    ("4", 3): "Spain or the Netherlands answers with market access, priority demands or exit.",
    ("4", 4): "The fleets and harbour treasuries budget the patrols.",
    ("4", 5): "The sides handle seized ships and premium disputes.",
    ("4", 6): "The actual signatories confirm the navigation convention.",
    ("5", 1): "New Ming petitions Mexico with autonomy clauses.",
    ("5", 2): "Mexico answers the fiscal and defence terms.",
    ("5", 3): "The United States and other third parties answer.",
    ("5", 4): "New Ming and Mexico settle the coastal defence ledger.",
    ("5", 5): "The local council answers land and settlement disputes.",
    ("5", 6): "New Ming and Mexico confirm the outcome in turn.",
}

COST_WORDS = (
    "支付", "出资", "花费", "开支", "支出", "拨款", "借债", "举债", "分摊",
    "补饷", "赔偿", "让利", "扩军", "共建", "投资", "护路成本", "付维护",
    "付费", "补贴", "俸禄", "经费",
)
# Revenue-positive or purely descriptive phrases must not read as treasury costs.
COST_NEG_WORDS = (
    "增收", "减税", "加税", "得经费", "获得让利", "限制投资", "保投资", "省支出",
    "统一征收", "征收统一", "要求投资", "让投资者", "允许受监管", "限制王府",
    "可支付", "主张方让利", "税惠", "投资权",
)
META_PATTERNS = (r"。记录[^。]*$", r"。?参与各方分别作出选择[^。]*$", r"^或改", r"^或")
TRADE_WORDS = ("贸易", "商路", "商船", "关税", "港", "航路", "商队", "货栈", "互市", "市场", "通商", "海贸", "航段", "船照")
SUBJECT_WORDS = ("藩", "宗主", "自治", "属邦", "宗主关系", "称谓", "正朔")

CHAPTER_FOCUS_CN = {
    1: "本章检验制度能否在不耗尽财政与地方支持的前提下分享权力。",
    2: "本章的关键在于财政与商业能力，所选安排必须通过真实市场与公共资金运转。",
    3: "本章检验国家的对外地位；持久安排取决于资源、外交与内部共识。",
}
CHAPTER_FOCUS_EN = {
    1: "The opening chapter tests whether institutions can share power without exhausting public funds or local support.",
    2: "This chapter turns on fiscal and commercial capacity; the chosen arrangement must work through real markets and public funds.",
    3: "The final chapter tests the country's external standing; a durable settlement depends on resources, diplomacy and consent.",
}


def source_rows(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*`(ywc_[^`]+)`\s*\|(.+)$", line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(2).split("|")]
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        rows.append((match.group(1), cells[0], cells[1]))
    return rows


def cost_of(text: str, base: int) -> int:
    if any(word in text for word in COST_NEG_WORDS):
        return 0
    return base if any(word in text for word in COST_WORDS) else 0


def clean_label(text: str) -> str:
    """Strip designer meta notes and leading alternatives from card labels."""
    cleaned = text.strip()
    for pattern in META_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    return cleaned.strip("。；， ").strip()


def main() -> int:
    english = json.loads((ROOT / "data/content/large_campaign_english.json").read_text(encoding="utf-8"))
    national_rows = source_rows(SPEC / "2026-09-25-大型内容包十国事件卡.md")
    crisis_rows = source_rows(SPEC / "2026-09-25-大型内容包跨国危机事件卡.md")
    assert len(national_rows) == 150, len(national_rows)
    assert len(crisis_rows) == 30, len(crisis_rows)

    events = []
    for event_id, card, choices in national_rows:
        match = re.match(r"ywc_([a-z]+)\.(\d+)$", event_id)
        short, number = match.group(1), int(match.group(2))
        assert short in COUNTRIES and 100 <= number <= 114, event_id
        title_match = re.match(r"《([^》]+)》[：:]\s*(.*)$", card)
        assert title_match, card
        split = [clean_label(c) for c in choices.split("；")]
        assert len(split) == 2, (event_id, len(split))
        copy = english.get(event_id)
        assert copy and len(copy) == 3, event_id
        config = COUNTRIES[short]
        chapter = (number - 100) // 5 + 1
        position = (number - 100) % 5 + 1
        choices_out = []
        for index, (label_cn, label_en) in enumerate(zip(split, copy[1:])):
            choices_out.append({
                "label_cn": label_cn,
                "label_en": label_en,
                "direction": "bold" if index == 0 else "cautious",
                "cost": cost_of(label_cn, config["cost"]),
                "trade": any(w in label_cn for w in TRADE_WORDS),
                "subject": any(w in label_cn for w in SUBJECT_WORDS),
            })
        events.append({
            "id": event_id, "kind": "national", "short": short, "tag": config["tag"],
            "chapter": chapter, "position": position, "final": position == 5,
            "title_cn": title_match.group(1), "desc_cn": title_match.group(2),
            "title_en": copy[0],
            "desc_en": f"{config['name_en']} must address {copy[0]}. {CHAPTER_FOCUS_EN[chapter]}",
            "desc_cn": f"{title_match.group(2)}。{CHAPTER_FOCUS_CN[chapter]}",
            "choices": choices_out,
        })

    for event_id, stage_desc, choices in crisis_rows:
        number = int(event_id.rsplit(".", 1)[1])
        crisis = (number - 1) // 6 + 1
        stage = (number - 1) % 6 + 1
        split = [clean_label(c) for c in choices.split("；")]
        if stage == 6 and len(split) == 2:
            split.append("无协议收束，并承受有时限的外交与贸易余波")
        assert len(split) == 3 if stage == 6 else len(split) >= 2, (event_id, len(split))
        answerer, fallbacks = CRISIS_STAGES[str(crisis)][stage]
        config = CRISES[str(crisis)]
        title_en = f"{CRISIS_STAGE_EN[stage]}: {config['name_en']}"
        events.append({
            "id": event_id, "kind": "crisis", "crisis": crisis, "stage": stage,
            "answerer": answerer, "answerer_fallbacks": fallbacks,
            "partner": CRISIS_PARTNER[str(crisis)].get(stage, ""),
            "title_cn": f"{config['name_cn']}·{CRISIS_STAGE_CN[stage]}",
            "desc_cn": stage_desc,
            "title_en": title_en,
            "desc_en": (
                f"Stage {stage} of {config['name_en']}. "
                f"{CRISIS_STAGE_DESC_EN[(str(crisis), stage)]} "
                "Each participant decides for itself; the answers shape the settlement."
            ),
            "choices": [
                {"label_cn": clean_label(label), "label_en": "", "direction": "", "cost": 0, "trade": False, "subject": False}
                for label in split
            ],
        })

    # Fill crisis English copy from the shared per-stage vocabulary.
    crisis_choices_en = {
        1: [
            "Propose reciprocal terms and share the cost of envoys and implementation.",
            "Keep the existing hierarchy, gaining conservative support but raising the risk of rejection.",
        ],
        2: [
            "Accept negotiations with conditions and demand concessions from the proposing side.",
            "Reject the change and preserve the status quo, accepting more trade friction.",
        ],
        3: [
            "Join on terms that preserve our sovereignty and existing obligations.",
            "Decline or observe without a binding commitment.",
        ],
        4: [
            "Fund a practical agreement with market access and shared expenses.",
            "Narrow the promise to a low-cost declaration without changing trade.",
        ],
        5: [
            "Drop exclusive claims and preserve the practical terms to seek compromise.",
            "Hold to the original demand and accept a higher risk of escalation.",
        ],
        6: [
            "Ratify the full agreement if consent, funding and relations make it workable.",
            "Accept a limited pact that resolves only the most practical issue.",
            "End negotiations and accept time-limited diplomatic and trade fallout.",
        ],
    }
    for event in events:
        if event["kind"] != "crisis":
            continue
        labels = crisis_choices_en[event["stage"]]
        assert len(event["choices"]) == len(labels), event["id"]
        for choice, label in zip(event["choices"], labels):
            choice["label_en"] = label
            choice["direction"] = "bold" if label is labels[0] else ("limited" if len(labels) == 3 and choice is event["choices"][1] else "cautious")
            choice["trade"] = any(w in choice["label_cn"] for w in TRADE_WORDS)
            choice["subject"] = any(w in choice["label_cn"] for w in SUBJECT_WORDS)
        if event["stage"] == 6:
            base = CRISES[str(event["crisis"])]["cost"]
            event["choices"][0]["cost"] = base
            event["choices"][1]["cost"] = base // 2
            event["choices"][2]["cost"] = 0
        else:
            for choice in event["choices"]:
                choice["cost"] = cost_of(choice["label_cn"], CRISES[str(event["crisis"])]["cost"])

    ids = [event["id"] for event in events]
    assert len(ids) == len(set(ids)) == 180

    catalog = {
        "schema_version": 1,
        "source": [
            "docs/superpowers/specs/2026-09-25-大型内容包十国事件卡.md",
            "docs/superpowers/specs/2026-09-25-大型内容包跨国危机事件卡.md",
            "data/content/large_campaign_english.json",
        ],
        "countries": COUNTRIES,
        "crises": CRISES,
        "crisis_stage_names": {"cn": CRISIS_STAGE_CN, "en": CRISIS_STAGE_EN},
        "events": events,
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(events)} events to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
