# One-off emitter: build data/content/hegemony_event_catalog.json for the
# v0.2 "顺我者昌，逆我者亡" hegemony layer. The catalog is the committed
# source of truth for tools/build_hegemony_content.py.
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/content/hegemony_event_catalog.json"

HEGEMON = {
    "short": "shu", "tag": "SHU", "name_cn": "大顺", "name_en": "Shun",
    "journal": "ywc_je_hegemony_order",
    "authority_var": "ywc_hegemony_authority",
    "cost": 3000,
}

# Fixed summons order; each entry is one quarterly dispatch.
PARTICIPANTS = [
    {"short": "jhg", "tag": "JHG", "name_cn": "靖海", "name_en": "Jinghai", "cost": 1200},
    {"short": "kor", "tag": "KOR", "name_cn": "朝鲜", "name_en": "Korea", "cost": 1200},
    {"short": "lan", "tag": "LAN", "name_cn": "兰芳", "name_en": "Lanfang", "cost": 250},
    {"short": "nqg", "tag": "NQG", "name_cn": "北清", "name_en": "Northern Qing", "cost": 500},
    {"short": "dmg", "tag": "DMG", "name_cn": "东明", "name_en": "Dongming", "cost": 700},
    {"short": "mgl", "tag": "MGL", "name_cn": "喀尔喀", "name_en": "Khalkha", "cost": 350},
    {"short": "tib", "tag": "TIB", "name_cn": "西藏", "name_en": "Tibet", "cost": 350},
    {"short": "oir", "tag": "OIR", "name_cn": "卫拉特", "name_en": "Oirat", "cost": 1200},
    {"short": "nmg", "tag": "NMG", "name_cn": "新明", "name_en": "New Ming", "cost": 600},
]


def ev(id_, kind, short, tag, slot, title_cn, desc_cn, title_en, desc_en, choices, trigger=""):
    return {
        "id": id_, "kind": kind, "short": short, "tag": tag, "slot": slot,
        "title_cn": title_cn, "desc_cn": desc_cn, "title_en": title_en, "desc_en": desc_en,
        "choices": choices, "trigger": trigger,
    }


def ch(label_cn, label_en, ops):
    return {"label_cn": label_cn, "label_en": label_en, "ops": ops}


HEGEMONY_EVENTS = [
    ev("ywc_hegemony.1", "hegemon", "shu", "SHU", "proclaim",
       "颁行新制",
       "三章既毕，大顺诏告天下：设朝贡新籍——入籍者互市通商、海路受护，贡额有度；不入籍者，不得沾天朝之利。诏书未出，各方探子已快马出京。",
       "Proclaiming the New Order",
       "With the three chapters settled, Shun proclaims a tribute registry: those who join trade under its protection; those who stay out forgo the court's favour. Before the ink dries, every capital already has its spies on the road.",
       [
           ch("颁宽仁之诏：以利相诱，不迫人以威",
              "Proclaim a lenient edict: lure with profit, not force",
              [{"op": "authority_init", "value": 40},
               {"op": "legitimacy", "delta": 10},
               {"op": "treasury", "amount": -3000},
               {"op": "stage_done", "stage": 1}]),
           ch("颁威严之诏：顺者嘉之，逆者必问",
              "Proclaim a stern edict: reward obedience, interrogate defiance",
              [{"op": "authority_init", "value": 65},
               {"op": "treasury", "amount": -1000},
               {"op": "stage_done", "stage": 1}]),
       ]),
    ev("ywc_hegemony.2", "hegemon", "shu", "SHU", "reactions",
       "四方震动",
       "诏使四出，奏报先后入京——有欣然请籍者，有托辞观望者，亦有婉拒不奉者。天宪初行，回应之姿将定此后十年之局。",
       "The Realm Stirs",
       "Reports stream back to the capital: some ask to join at once, some stall for time, some decline outright. The first answers will set the tone of the decade.",
       [
           ch("广施恩信：不论顺逆，使者皆厚待之",
              "Show grace to all: treat every envoy generously",
              [{"op": "authority", "delta": 3},
               {"op": "treasury", "amount": -2000},
               {"op": "legitimacy", "delta": 5},
               {"op": "stage_done", "stage": 3}]),
           ch("张威慑止：顺者嘉奖，观望者限期",
              "Brandish the edict: reward the compliant, set deadlines for the hedging",
              [{"op": "authority", "delta": 6},
               {"op": "relations_on_stance", "stance": 2, "value": -5},
               {"op": "stage_done", "stage": 3}]),
       ]),
    ev("ywc_hegemony.3", "hegemon", "shu", "SHU", "reward",
       "酬顺之政",
       "入籍各国使团齐集京师。酬庸之策：普施互市，则费帑而众悦；择亲厚赏，则省费而恩私。",
       "Rewarding the Compliant",
       "The missions of the enrolled states gather at court. Spend broadly on open trade and please them all, or reward only the closest and save the treasury.",
       [
           ch("互市普施：凡入籍者皆得商照与水师照应",
              "Open trade for every enrolled state",
              [{"op": "treasury", "amount": -4000},
               {"op": "modifier_on_stance", "stance": 1, "name": "ywc_tributary_trade", "months": 24},
               {"op": "relations_on_stance", "stance": 1, "value": 15},
               {"op": "fire_stance", "stance": 1},
               {"op": "authority", "delta": 4},
               {"op": "stage_done", "stage": 4}]),
           ch("择亲厚赏：贡额重者优先",
              "Reward the foremost contributors only",
              [{"op": "treasury", "amount": -1500},
               {"op": "modifier_on_stance", "stance": 1, "name": "ywc_tributary_trade", "months": 12},
               {"op": "relations_on_stance", "stance": 1, "value": 10},
               {"op": "fire_stance", "stance": 1},
               {"op": "authority", "delta": 2},
               {"op": "stage_done", "stage": 4}]),
       ]),
    ev("ywc_hegemony.4", "hegemon", "shu", "SHU", "punish",
       "问罪逆藩",
       "拒诏之国，使书置而不答。天宪既颁，岂容轻慢——然问罪之方，利钝各异。",
       "Censuring the Defiant",
       "The defiant have returned the edict unanswered. The new order cannot be flouted with impunity, yet each instrument of censure carries its own cost.",
       [
           ch("孤立锁市：禁其商路，绝其互市",
              "Seal their trade: embargo the defiant",
              [{"op": "modifier_on_stance", "stance": 3, "name": "ywc_defiance_isolation", "months": 24},
               {"op": "relations_on_stance", "stance": 3, "value": -20},
               {"op": "authority", "delta": 2},
               {"op": "fire_stance", "stance": 3},
               {"op": "stage_done", "stage": 5}]),
           ch("陈兵耀武：大阅于边，示威于海",
              "Muster on the marches: overawe them",
              [{"op": "modifier_on_stance", "stance": 3, "name": "ywc_defiance_isolation", "months": 24},
               {"op": "relations_on_stance", "stance": 3, "value": -25},
               {"op": "relations_on_stance", "stance": 2, "value": -5},
               {"op": "authority", "delta": 5},
               {"op": "modifier", "name": "ywc_celestial_authority", "months": 24},
               {"op": "fire_stance", "stance": 3},
               {"op": "stage_done", "stage": 5}]),
       ]),
    ev("ywc_hegemony.5", "hegemon", "shu", "SHU", "summit",
       "朝会天宪",
       "观望之国使节皆至。是收权一统，定朝贡为定制；还是共治分权，以宗盟之名行其实——天命在此一举。",
       "The Summit of the Mandate",
       "The hedging states have sent envoys at last. Concentrate authority into standing custom, or share the order as a league of equals.",
       [
           ch("收权一统：贡籍朝籍皆出天朝，不容分享",
              "Concentrate authority: the registry answers to the throne alone",
              [{"op": "authority", "delta": 8},
               {"op": "modifier_on_stance", "stance": 2, "name": "ywc_defiance_isolation", "months": 12},
               {"op": "relations_on_stance", "stance": 2, "value": -10},
               {"op": "legitimacy", "delta": -5},
               {"op": "stage_done", "stage": 6}]),
           ch("共治分权：设同盟之约，共守海陆商路",
              "Share the order: a league to keep the trade routes",
              [{"op": "authority", "delta": -5},
               {"op": "modifier_on_stance", "stance": 2, "name": "ywc_tributary_trade", "months": 12},
               {"op": "relations_on_stance", "stance": 2, "value": 10},
               {"op": "legitimacy", "delta": 10},
               {"op": "stage_done", "stage": 6}]),
       ]),
    ev("ywc_hegemony.6", "hegemon", "shu", "SHU", "settle",
       "天命所归",
       "新制行世数年，顺逆之势已明。是定于一尊，还是留个未竟之局——史笔在此。",
       "Where the Mandate Rests",
       "Years on, the balance of compliance and defiance is clear. Crown the order, accept a setback, or watch it crumble.",
       [
           ch("定于一尊：天命所归，朝贡为定制",
              "Crown the order: the mandate is settled",
              [{"op": "outcome", "value": 1},
               {"op": "modifier", "name": "ywc_hegemony_established", "months": 120},
               {"op": "modifier_on_stance", "stance": 3, "name": "ywc_defiance_isolation", "months": 36},
               {"op": "stage_done", "stage": 7}]),
           ch("接受受挫：新制有名无实，徐图再举",
              "Accept the setback: the order exists on paper",
              [{"op": "outcome", "value": 2},
               {"op": "modifier", "name": "ywc_hegemony_stalled", "months": 60},
               {"op": "stage_done", "stage": 7}]),
           ch("承认崩解：权威扫地，天下各行其是",
              "Admit the collapse: the authority is spent",
              [{"op": "outcome", "value": 3},
               {"op": "modifier", "name": "ywc_hegemony_collapsed", "months": 60},
               {"op": "legitimacy", "delta": -15},
               {"op": "stage_done", "stage": 7}]),
       ],
       trigger="var:ywc_hegemony_authority >= 55 var:ywc_hegemony_compliant >= 3 var:ywc_hegemony_defiant <= 2"),
]

# Per-participant summon narratives, keyed by short tag.
SUMMONS = {
    "jhg": (
        "贡使再至",
        "大顺诏使再抵王府，新制要求靖海岁贡定额、船籍听册，换取互市与水师照应。旧约之上的新名分，王府与商议会各有盘算。",
        "The Envoy Returns",
        "Shun's envoy is back at the palace: quotas, ship registries, and in exchange the open trade and the navy's covering hand. On top of the old covenant, the court and the council each count costs of their own.",
        [("确认岁贡，船籍入册，请互市如约",
          "Confirm the quota, register the fleet, claim the trade",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -1200}, {"op": "subject_pressure", "raise": False},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以旧约未满为辞，先观各国动向",
          "Cite the old covenant and watch the others first",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("商议会决：船籍册报有违自治旧约，婉拒新制",
          "The council refuses: registries breach the old autonomy",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "kor": (
        "册使之来",
        "大顺册使渡江而来，请朝鲜入新朝贡籍、用新正朔。朝堂之上，事大与自主之争再起；儒臣引经据典，各执一端。",
        "The Investiture Envoy",
        "Shun's envoy crosses the river asking Korea into the new registry and the new calendar. At court the old quarrel between serving the great and standing apart breaks out anew.",
        [("奉表用朔，岁贡如例",
          "Present the tables, adopt the calendar, pay as customary",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -1200}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以“礼当从长”为辞，先遣问安使",
          "Send courtesies first: etiquette takes time",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("朝议决：自立之名分不可轻授",
          "The court declines: independence is not negotiable",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "lan": (
        "万里奉贡",
        "大顺诏使远航至坤甸，请兰芳入贡籍。总厅议事：万里输贡所费不赀，然荷兰窥伺在侧，大顺之名分或有其实。",
        "Tribute Across an Ocean",
        "Shun's envoy reaches Pontianak asking Lanfang into the registry. The hall debates: tribute across an ocean is costly, but with the Dutch watching, a great-power name may be worth the price.",
        [("岁贡金砂，请大顺商照护海路",
          "Pay in gold sand, ask for the sea lanes",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -250}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("先立商约，贡籍缓议",
          "Sign a trade pact first; the registry can wait",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("总厅议决：公司之政不奉朝贡旧礼",
          "The hall declines: a company pays no tribute",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "nqg": (
        "岛上接诏",
        "诏使渡海而至，请北清去帝号、入贡籍。流亡朝廷为之分裂：体面已不可复得，生计却不可不继。",
        "Receiving the Edict on the Island",
        "The envoy crosses to the island asking Northern Qing to lay down its imperial style and enter the registry. The exile court splits: dignity is already gone, but livelihood cannot wait.",
        [("去尊号，岁贡海产，换取互市与不打之谊",
          "Lay down the style, pay in sea produce, buy peace and trade",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -500}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以“未奉正朔已三世”为辞，迁延不答",
          "Stall: three generations without the calendar",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("朝廷决议：残明年号犹在，不奉新朔",
          "The court refuses: the Ming calendar still reigns here",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "dmg": (
        "隔海之诏",
        "大顺诏使经南洋而至，请东明入贡籍。吕宋朝堂多有迟疑：西班牙的炮舰就在马尼拉湾，奉贡之名能否护住这片海？",
        "The Edict Across the Sea",
        "Shun's envoy comes through the South Seas asking Dongming into the registry. Luzon hesitates: Spanish guns ride at Manila Bay — will a tribute name guard these waters?",
        [("奉贡入籍，兼修武备以防不测",
          "Enroll and arm, just in case",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -700}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以南洋航路未决为辞，暂缓答诏",
          "Stall on the unsettled sea-lane dispute",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("朝议决：西怒不可招，贡籍不奉",
          "The court refuses: do not provoke Spain",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "mgl": (
        "南使北信",
        "大顺诏使与俄方信使先后至库伦。入贡则南路互市大开，拒之则北路或有相保之约——草原两属之难，摆在王公与寺院面前。",
        "Envoy from the South, Letter from the North",
        "Shun's envoy and a Russian letter reach Khuree together. Enroll and the southern trade opens wide; refuse and perhaps the north offers protection. The steppe's old dilemma, laid before princes and monasteries.",
        [("奉贡入籍，南路互市为重",
          "Enroll: the southern trade comes first",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -350}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("两部会议未决，先以骏马答使",
          "The banners disagree: answer with horses, not words",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("盟旗共誓：草原之主不称臣",
          "The banners swear: steppe lords bow to no registry",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "tib": (
        "高原奉诏",
        "诏使入藏，请入贡籍、定茶马新则。僧俗两会详议：名分可奉，然茶税与驻使之权，须另立条款。",
        "The Edict on the Plateau",
        "The envoy ascends to Tibet asking for the registry and a new tea-horse code. The assemblies agree the name can be granted, but the tea tax and residency must be bargained separately.",
        [("奉贡入籍，另订茶马条款",
          "Enroll, with the tea-horse code bargained separately",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -350}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以“政教之事须共议”为辞，缓答",
          "Stall: the religious and secular estates must confer",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("两会决：高原之政不由外籍",
          "The assemblies refuse: the plateau governs itself",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "oir": (
        "汗廷之择",
        "大顺以天命自居，请卫拉特称臣入贡。汗廷之议：先祖未尝称臣于顺，然伊犁财路半系南路，拒诏恐失其半。",
        "The Khaganate Chooses",
        "Shun claims the mandate and asks the Oirat to enroll as tributaries. The court weighs it: the ancestors never bowed to Shun, yet half the Ili trade rides the southern road.",
        [("奉贡称臣，互市照旧", "Enroll: keep the trade flowing",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -1200}, {"op": "legitimacy", "delta": -5},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以“盟约未集”为辞，遣使缓颊", "Stall: the league has not met",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("汗廷决：可通商，不称臣", "The court refuses: trade yes, vassalage no",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
    "nmg": (
        "跨洋之诏",
        "大顺诏使跨太平洋而至，请新明入贡籍。海湾议事会两难：旧国之名分或可借力，然墨西哥必疑——两个宗主之间，无处容身。",
        "The Edict Across the Pacific",
        "Shun's envoy crosses the Pacific asking New Ming into the registry. The bay council is trapped: the old country's name might help, but Mexico will certainly object — between two masters there is no room.",
        [("奉贡入籍，同时照会墨西哥以安其心",
          "Enroll, and reassure Mexico at once",
          [{"op": "stance", "value": 1}, {"op": "counter", "name": "compliant", "delta": 1},
           {"op": "treasury", "amount": -600}, {"op": "subject_pressure", "raise": True},
           {"op": "relations_hegemon", "value": 15}, {"op": "authority", "delta": 2}]),
         ("以“须与墨西哥相商”为辞，暂搁",
          "Stall: Mexico must be consulted first",
          [{"op": "stance", "value": 2}, {"op": "counter", "name": "hedging", "delta": 1},
           {"op": "relations_hegemon", "value": -2}]),
         ("议事会决：属邦之身不奉二朝",
          "The council refuses: one subject, one master",
          [{"op": "stance", "value": 3}, {"op": "counter", "name": "defiant", "delta": 1},
           {"op": "relations_hegemon", "value": -15}, {"op": "authority", "delta": -3}])]),
}

FOLLOWUPS = {
    "compliant": {
        "title_cn": "顺者之昌", "title_en": "The Compliant Prosper",
        "desc_cn": "贡籍既入，互市渐开。使团再至，问的是加贡请封，还是谨守本分——昌名之下，各有价码。",
        "desc_en": "Enrolled, the trade begins to open. Another mission asks: petition for greater favour at greater cost, or keep to your station?",
        "choices": [
            ch("加贡请封：岁贡倍之，请开水陆互市全权",
               "Double the tribute, ask for full trade rights",
               [{"op": "treasury", "amount": -1800}, {"op": "tribute_to_hegemon", "amount": 900},
                {"op": "authority", "delta": 3}, {"op": "relations_hegemon", "value": 10},
                {"op": "modifier", "name": "ywc_tributary_trade", "months": 24}]),
            ch("谨守本分：按例输贡，不别有所请",
               "Keep to your station: pay as customary",
               [{"op": "authority", "delta": 1}, {"op": "relations_hegemon", "value": 5},
                {"op": "modifier", "name": "ywc_tributary_trade", "months": 12}]),
        ],
    },
    "defiant": {
        "title_cn": "逆者之亡", "title_en": "The Defiant Falter",
        "desc_cn": "拒诏之后，商路受阻、使节难行，市面渐见萧条。是硬抗到底，还是转圜入贡——体面与生计，只可择一。",
        "desc_en": "Since the refusal the roads have narrowed and the markets thinned. Hold the line, or swallow pride and enroll after all?",
        "choices": [
            ch("硬抗到底：闭境自守，不惧问罪",
               "Hold the line: close the borders and brave the censure",
               [{"op": "modifier", "name": "ywc_defiance_isolation", "months": 24},
                {"op": "relations_hegemon", "value": -10}, {"op": "legitimacy", "delta": -10},
                {"op": "authority", "delta": 2}]),
            ch("转而入贡：遣使谢罪，补行贡礼",
               "Enroll after all: send apologies and back tribute",
               [{"op": "stance", "value": 1},
                {"op": "counter", "name": "defiant", "delta": -1},
                {"op": "counter", "name": "compliant", "delta": 1},
                {"op": "treasury", "amount": -900}, {"op": "tribute_to_hegemon", "amount": 450},
                {"op": "relations_hegemon", "value": 5}, {"op": "authority", "delta": 3},
                {"op": "legitimacy", "delta": -5},
                {"op": "modifier", "name": "ywc_tributary_trade", "months": 12}]),
        ],
    },
}


def build_events() -> list[dict]:
    events = list(HEGEMONY_EVENTS)
    for participant in PARTICIPANTS:
        short, tag, cost = participant["short"], participant["tag"], participant["cost"]
        title_cn, desc_cn, title_en, desc_en, choices = SUMMONS[short]
        scaled = [list(choice) for choice in choices]
        for choice in scaled:
            for op in choice[2]:
                if op["op"] == "treasury" and op["amount"] < 0:
                    op["amount"] = -(cost if -op["amount"] >= 100 else cost // 2)
        events.append(ev(f"ywc_{short}.200", "participant", short, tag, "summon",
                         title_cn, desc_cn, title_en, desc_en,
                         [ch(*item) for item in scaled]))
        for slot, number in (("compliant", 201), ("defiant", 202)):
            followup = FOLLOWUPS[slot]
            choices = []
            for index, choice in enumerate(followup["choices"]):
                ops = json.loads(json.dumps(choice["ops"]))
                for op in ops:
                    # Scale the extra-tribute burdens to the country's size:
                    # 加贡 = 1.5x the yearly tribute (half reaches the court),
                    # 转而入贡 = 0.75x with a quarter reaching the court.
                    if op["op"] == "treasury" and op["amount"] < 0:
                        op["amount"] = -(cost + cost // 2) if slot == "compliant" else -(3 * cost // 4)
                    if op["op"] == "tribute_to_hegemon":
                        op["amount"] = cost // 2 if slot == "compliant" else cost // 4
                choices.append(ch(choice["label_cn"], choice["label_en"], ops))
            events.append(ev(f"ywc_{short}.{number}", "participant", short, tag, slot,
                             followup["title_cn"], followup["desc_cn"],
                             followup["title_en"], followup["desc_en"], choices))
    return events


def main() -> int:
    events = build_events()
    ids = [event["id"] for event in events]
    assert len(ids) == len(set(ids)) == 33, len(ids)
    catalog = {
        "schema_version": 1,
        "source": ["docs/superpowers/specs/2026-09-26-顺昌逆亡霸权秩序设计.md"],
        "hegemon": HEGEMON,
        "participants": PARTICIPANTS,
        "events": events,
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(events)} hegemony events to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
