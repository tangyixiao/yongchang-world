"""Generate opening flavor and three decision journals for uncovered mod starts.

The registry is the tag source of truth. Output is restricted to the frontier
content files so campaign and regional content can be edited independently.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "yongchang_world"
REGISTRY = ROOT / "data/scenario/tag_registry.json"
OWNED = {"SHU", "JHG", "DMG", "NQG", "OIR", "MGL", "TIB", "KOR", "LAN", "NMG", "LJG", "SIP", "DER", "GYL", "SHD", "RKN", "MHG"}
# Small groups are deliberately conservative. Medium frontier polities can
# contest nearby roads and pasture, while maritime/island states prioritize
# access and survival. No group receives colonial interest.
PROFILES = {
    "highland": {
        "zh": "高原与山地政体",
        "en": "highland polities",
        "zh_pressure": "寺院、地方首领与商队都要对山口和供役提出自己的规矩",
        "en_pressure": "monasteries, local chiefs, and caravans each claim a say over passes and service",
        "zh_intro": "高地的权力依靠季节性通道、地方承诺与稀少的税源维系。朝廷若越过地方盟约，命令便很难翻过山口；若只守旧约，新的道路和军费又无从安排。",
        "en_intro": "Authority in the highlands rests on seasonal passes, local promises, and a narrow tax base. Orders that bypass local compacts rarely cross the mountains; old bargains alone cannot pay for new roads or defence.",
        "zh_open": "一次关于牧地、山口和供役的争执被送到议事桌上。寺院或首领愿意协助登记，但要求地方界线得到承认。",
        "en_open": "A dispute over pasture, passes, and service reaches the council. Monasteries or chiefs will help keep registers, provided local boundaries are respected.",
        "aggression": -0.25, "boldness": -25, "neutrality": 20, "tax": "medium", "build": "bg_ranching = 1.35 bg_agriculture = 1.15 bg_construction = 0.90", "goods": "grain wood tools", "art": "asia_sepoy_mutiny",
    },
    "oasis": {
        "zh": "绿洲与商路政体", "en": "oasis and caravan states",
        "zh_pressure": "关卡税、商队通行和邻近强权的哨所彼此牵制",
        "en_pressure": "toll rights, caravan passage, and the posts of nearby powers pull in different directions",
        "zh_intro": "绿洲城镇的生计系于水渠、集市和商路。提高关税可以供养官署，却会把商队赶向别的驿站；轻易让路，则可能让邻国把临时通行变成永久权利。",
        "en_intro": "Oasis towns depend on canals, bazaars, and caravan roads. Higher tolls can fund offices but divert merchants to another stop; an easy passage can turn a temporary concession into a lasting claim.",
        "zh_open": "商队要求统一关卡和通行文书。城中商人愿意垫付整顿费用，但希望税额和执法边界写入公开约章。",
        "en_open": "Caravans ask for common tolls and travel papers. Merchants will help fund repairs if rates and enforcement are written into a public compact.",
        "aggression": -0.12, "boldness": -10, "neutrality": 12, "tax": "medium", "build": "bg_mining = 1.15 bg_agriculture = 1.20 bg_construction = 1.00", "goods": "grain wood tools", "art": "africa_diplomats_negotiating",
    },
    "steppe": {
        "zh": "草原旗盟政体", "en": "steppe confederations",
        "zh_pressure": "各部需要共享牧地与军役，也警惕邻国把互市变成控制",
        "en_pressure": "clans must share pasture and service while guarding against neighbours turning trade into control",
        "zh_intro": "草原诸部以牧地、盟誓和共同防务维系联盟。可汗或盟主若要求过多固定军役，会失去部众；若无法协调冬营和边市，联盟又会被更有组织的邻国逐步挤压。",
        "en_intro": "Pasture, oaths, and common defence hold the steppe clans together. Excessive fixed service can drive them away; without coordination of winter camps and border markets, better-organized neighbours will steadily press in.",
        "zh_open": "诸部代表要求重议季节牧地与共同防务。盟主可以建立常设议约，也可以把裁决权留给各部首领。",
        "en_open": "Clan delegates ask to renew seasonal pasture and common defence rules. The leader can establish a standing compact or leave arbitration with the chiefs.",
        "aggression": -0.03, "boldness": -2, "neutrality": 8, "tax": "medium", "build": "bg_ranching = 1.45 bg_mining = 1.10 bg_agriculture = 1.00", "goods": "grain wood iron", "art": "asia_sepoy_mutiny",
    },
    "frontier": {
        "zh": "边疆城镇政体", "en": "frontier principalities",
        "zh_pressure": "边防、征税和本地治权必须在有限的人口与财政中取舍",
        "en_pressure": "border defence, taxation, and local authority compete for a small population and treasury",
        "zh_intro": "边疆政权的命令常常只到达城镇和近郊，远处仍由旧有首领与地方习惯维持秩序。扩军能暂时吓阻竞争者，却会吞掉官署、道路和粮秣的预算。",
        "en_intro": "A frontier ruler's orders often reach only towns and nearby settlements; older chiefs and local custom govern farther out. More troops can deter rivals for a time, but consume the budget needed for offices, roads, and stores.",
        "zh_open": "边防哨所与地方长老同时要求朝廷作出保证。扩充巡防能够提高戒备，却需要由城镇承担额外的军需和修路费用。",
        "en_open": "Border posts and local elders both ask for guarantees. More patrols can improve readiness, but towns will bear the added cost of supplies and roads.",
        "aggression": -0.18, "boldness": -15, "neutrality": 16, "tax": "medium", "build": "bg_agriculture = 1.25 bg_mining = 1.10 bg_construction = 0.90", "goods": "grain wood tools", "art": "unspecific_politicians_arguing",
    },
    "island": {
        "zh": "岛屿与沿海政体", "en": "island and coastal polities",
        "zh_pressure": "港口补给、外来船只与岛内社群自治需要同一套可靠约定",
        "en_pressure": "port supplies, foreign shipping, and island communities need a reliable common compact",
        "zh_intro": "岛屿政权依靠港口、渔场与海上消息连接彼此。外来商船能带来稀缺物资，也会使地方首领担心港税和司法被外人支配；闭锁海湾同样会让补给变贵。",
        "en_intro": "Island governments depend on ports, fisheries, and news by sea. Foreign ships bring scarce supplies but raise fears that outsiders will control harbour dues and justice; closing the bays makes provisions costlier too.",
        "zh_open": "渔民、港口领主和远航商人要求重订锚地规矩。开放港湾可改善补给，地方议会则要求保留检查和裁判权。",
        "en_open": "Fishers, harbour chiefs, and long-distance traders ask for new anchorage rules. Open bays improve supplies, while local councils insist on keeping inspection and courts in their hands.",
        "aggression": -0.28, "boldness": -20, "neutrality": 22, "tax": "low", "build": "bg_fishing = 1.45 bg_logging = 1.20 bg_private_infrastructure = 1.10", "goods": "fish wood grain", "art": "africa_diplomats_negotiating",
    },
    "maritime": {
        "zh": "海贸与群岛政体", "en": "maritime and island communities",
        "zh_pressure": "海路收益取决于港口协作，同时受到殖民者和更强海军的挤压",
        "en_pressure": "sea-lane income depends on port cooperation under pressure from colonial claims and stronger navies",
        "zh_intro": "沿海和群岛社群靠航路、港埠与彼此的互信谋生。谁能征收港税、调停岛间争端、保护渔场，决定了商人是否愿意继续停靠。",
        "en_intro": "Coastal and island communities live by sea lanes, harbours, and mutual trust. Control of port dues, arbitration between islands, and protection of fisheries determines whether merchants keep calling.",
        "zh_open": "数个港口提出联合巡护与统一停泊费的建议。协议有助于吸引商船，也意味着各港要接受共同核验和分担成本。",
        "en_open": "Several ports propose joint patrols and a common anchorage fee. The compact may attract shipping, but each harbour must accept shared inspection and costs.",
        "aggression": -0.20, "boldness": -15, "neutrality": 18, "tax": "low", "build": "bg_fishing = 1.35 bg_private_infrastructure = 1.20 bg_manufacturing = 1.00", "goods": "fish wood tools", "art": "africa_diplomats_negotiating",
    },
    "forest": {
        "zh": "森林河谷边疆政体", "en": "forest and river frontier states",
        "zh_pressure": "河运、木材与分散村社之间尚未形成稳定的行政纽带",
        "en_pressure": "river traffic, timber, and scattered settlements lack a dependable administrative link",
        "zh_intro": "森林与河谷把定居点隔得很远，河道既是商路，也是外来势力进入的通道。国家要先解决港埠、仓储和地方司法，才有余力把边疆地图上的线变成日常秩序。",
        "en_intro": "Forests and river valleys leave settlements far apart. Rivers are both trade routes and channels for outside influence. Ports, stores, and local justice must work before lines on a frontier map become everyday authority.",
        "zh_open": "沿河聚落要求轮换的巡护和共享仓储。修复码头能改善物资流动，但需要村社同意分担维护和征调。",
        "en_open": "River settlements ask for rotating patrols and shared stores. Repairing landings can move supplies more reliably, but villages must agree to share upkeep and levies.",
        "aggression": -0.25, "boldness": -20, "neutrality": 20, "tax": "low", "build": "bg_logging = 1.35 bg_fishing = 1.15 bg_agriculture = 1.00", "goods": "wood fish grain", "art": "africa_construction_colony",
    },
}

# Human-authored profiles put each start in its actual regional setting.
TAG_PROFILE: dict[str, str] = {}
for group, tags in {
    "highland": "KHO AMD CHD HOR LTG KAM GYL DER LXJ HSR DRZ QRT LAD SIK MNP".split(),
    "oasis": "HMI TRF KUC KSH YRK KHT TSK SMR KRS KGL MEV AKS SHB TKK YMD".split(),
    "steppe": "OIR MGL KHQ HUL SOL ODS CHR BKY BYL JTR NMN KER ZHL ABN KZH OZH UZH".split(),
    "island": "NQG NMG PNP PLW YAP MHL EZO PHL".split(),
    "maritime": "JHG DMG LAN WBK SHD RKN SIP KTG WAA KCH AHM DLI MHG".split(),
    "forest": "AMR MRG".split(),
    "frontier": "SHU NQG HUL SOL HXI".split(),
}.items():
    for tag in tags:
        TAG_PROFILE.setdefault(tag, group)

NAME_EN_OVERRIDES = {
    "MGL": "Khalkha Khanate", "CHI": "Great Qing", "MNG": "Khalkha Khanate",
    "KHQ": "Khorchin Confederation", "HUL": "Hulun Confederation", "SOL": "Solon League",
    "AMR": "Amur Union", "KHO": "Khoshut Khanate", "HMI": "Hami Khanate",
    "TRF": "Turfan Emirate", "KUC": "Kucha Principality", "KSH": "Kashgar Khanate",
    "YRK": "Yarkand Begdom", "KHT": "Khotan Emirate", "DER": "Kingdom of Derge",
    "KAM": "Kham Chiefdoms", "GYL": "Gyalrong League", "LXJ": "Lijiang Council",
    "LJG": "Lijiang", "SIP": "Kengtung", "KTG": "Kengtung", "WAA": "Wa Confederation",
    "KCH": "Kachin Hills", "AHM": "Ahom Kingdom", "AMD": "Amdo Monasteries",
    "DLI": "Dali", "PNP": "Pohnpei League", "PLW": "Palau Kingdom", "YAP": "Yap Confederation",
    "MHL": "Marshall Islands", "MRG": "Marege Alliance", "CHD": "Chamdo Monastic State",
    "HOR": "Hor States", "LTG": "Litang Chiefdom", "TSK": "Tashkent Begdom",
    "KIR": "Kyrgyz Tribal Union", "SMR": "Samarkand", "KRS": "Karshi Begdom",
    "KGL": "Kongrat Khanate", "MEV": "Merv Oasis", "AKS": "Aksu Begdom",
    "ODS": "Ordos Confederation", "CHR": "Chahar League", "BKY": "Bukey Horde",
    "SHB": "Shahrisabz", "HSR": "Hisar Begdom", "DRZ": "Darvaz Shahdom",
    "QRT": "Karategin", "TKK": "Teke Confederation", "YMD": "Yomut Confederation",
    "HXI": "Hexi Garrisons", "BYL": "Bai-Ul Confederation", "JTR": "Seven Juz League",
    "NMN": "Naiman Confederation", "KER": "Kereit Confederation", "ZHL": "Zhalair Confederation",
    "ABN": "Alban Confederation", "WBK": "West Borneo Mining League", "MHG": "Mekong Chinese State",
    "NMG": "New Ming", "OIR": "Oirat Khanate", "NQG": "Northern Qing",
    "JHG": "Jinghai", "DMG": "Eastern Ming", "SHU": "Great Shun",
}

# Distinct selection-screen geopolitical hooks keep the shared regional prose
# anchored to each polity's actual neighbours, institutions, and livelihood.
COUNTRY_CONTEXT = {
    "CHI": ("大清仍以满洲官署和八旗为复国根基，却必须在大顺势力与俄国边境之间重建统治。", "Great Qing relies on Manchu offices and banner forces for restoration while rebuilding authority between Great Shun and the Russian frontier."),
    "HXI": ("河西走廊的军镇控制大顺通往西域的驿道和关隘，屯田补给与将领调兵权是边防核心。", "Hexi garrisons guard Great Shun's relay roads and passes toward the western regions, balancing military farms with commanders' control over mobilization."),
    "DRZ": ("德令哈周边的穆斯林商户依靠水源与青海湖—柴达木驿路，地方首领要抵御邻近汗国对关税的争夺。", "Muslim merchants around Delingha depend on wells and routes between Lake Qinghai and Qaidam, while local chiefs resist neighbouring khanates' claims to tolls."),
    "HSR": ("河湟谷地的回部城镇以绿洲农业和清真寺社群为根基，必须在藏区商路与周边强权之间守住自治。", "Hui towns in the Hehuang valley rely on oasis farming and mosque communities, protecting their autonomy along trade routes toward Tibet."),
    "KZH": ("这支草原联盟要在相邻汗国的竞争中协调牧地、盟誓与共同防务。", "This steppe league must coordinate pasture, oaths, and common defence amid rivalry among neighbouring khanates."),
    "OZH": ("各部首领围绕草场和商道结盟，任何常备军役都可能削弱盟主的号召力。", "Clans unite around pasture and caravan roads, but fixed military service can weaken the confederation's leader."),
    "UZH": ("联盟处在北方草原与南方绿洲商路交汇处，部众要求互市而不愿受邻国支配。", "The league sits between northern pasture and southern oasis routes; its members want trade without subordination to a neighbour."),
    "LAD": ("拉达克以高山商道连接克什米尔与西藏，关隘安全和季节性贸易决定王权收入。", "Ladakh links Kashmir and Tibet through high passes, making route security and seasonal trade central to royal revenue."),
    "WBK": ("西婆罗洲矿业联盟依靠矿场与河口商路，必须在公司章程、华人社群自治和沿海竞争者之间求稳。", "West Borneo's mining league depends on river-mouth trade and must balance company charters, Chinese community autonomy, and coastal rivals."),
    "KHQ": ("科尔沁诸旗既要守住牧场，也要在满洲清廷、大顺与俄国之间保留自主结盟空间。", "Khorchin banners must protect pasture and preserve room to choose partners among Qing Manchuria, Great Shun, and Russia."),
    "HUL": ("呼伦贝尔诸部需要协调牧地与边防，同时防止任何邻国把互市变成常驻控制。", "The Hulun clans must coordinate pasture and border defence while preventing trade from becoming a neighbour's permanent foothold."),
    "SOL": ("索伦各部沿黑龙江流域分布，河运和边防哨所是联盟维持协作的关键。", "Solon communities spread along the Amur basin, where river traffic and frontier posts hold the league together."),
    "AMR": ("黑龙江沿岸的聚落依赖渔猎、木材和河运，边境秩序须同时容纳通古斯社群与外来商人。", "Settlements on the Amur depend on fishing, timber, and river traffic; frontier rule must accommodate Tungusic communities and outside traders."),
    "KHO": ("和硕特汗国要在青海草场、藏传佛教寺院和通往西藏的贸易之间维持盟约。", "The Khoshut Khanate must sustain compacts across Qinghai pasture, Tibetan Buddhist institutions, and trade toward Tibet."),
    "HMI": ("哈密控制天山南北的门槛，水渠农业、驿站与清廷和西域商队的往来共同支撑埃米尔。", "Hami guards a gateway across the Tian Shan; irrigation, relay stations, and traffic with Qing offices and western caravans sustain the emir."),
    "TRF": ("吐鲁番依赖坎儿井和葡萄园，也要守住通往塔里木与天山北麓的商道。", "Turfan relies on karez irrigation and vineyards while defending routes toward the Tarim and the northern Tian Shan."),
    "KUC": ("库车绿洲位于塔里木商路中央，水权和驿站秩序比扩张疆界更能决定其生存。", "Kucha's oasis sits on the Tarim trade road, where water rights and relay security matter more than territorial expansion."),
    "KSH": ("喀什噶尔连接费尔干纳与塔里木盆地，商队通行和边境盟约使汗权时刻面对外部竞争。", "Kashgar links Ferghana to the Tarim Basin, leaving the khanate exposed to rivalry over caravans and border compacts."),
    "YRK": ("叶尔羌的绿洲灌溉和丝路市集维持统治，争夺水渠与商税会牵动城镇和乡村。", "Yarkand rests on oasis irrigation and Silk Road markets; disputes over canals and tolls reach both towns and villages."),
    "KHT": ("和田的绿洲农耕与玉石贸易依靠水渠及南疆山口，商路安全直接关系地方收入。", "Khotan's oasis farms and jade trade depend on canals and southern passes, making route security essential to local revenue."),
    "KAM": ("康区首领控制横穿山地的道路，大顺的边务与拉萨的宗教影响都要求他们表态。", "Kham chiefs control mountain crossings and face demands from Great Shun's frontier offices and Lhasa's religious influence."),
    "LXJ": ("丽江木府依靠纳西聚落、盐道和茶马贸易维持权威，外部整饬边务会触及旧有自治。", "Lijiang's Mu house relies on Naxi communities, salt roads, and tea-horse trade; outside frontier reforms challenge its autonomy."),
    "KTG": ("景栋控制掸邦山口和茶路，必须在缅甸王庭、兰纳邻邦与大顺使者之间周旋。", "Kengtung controls Shan passes and tea routes, balancing Burma's court, Lan Na neighbours, and Great Shun's envoys."),
    "WAA": ("佤邦各山地领地以地方首领和互市维系联盟，共同防务必须尊重分散的村社权力。", "Wa hill territories unite through local chiefs and markets; common defence must respect authority dispersed among villages."),
    "KCH": ("克钦山地把阿萨姆、缅甸和云南商路连接起来，首领要以通行权换取安全和贸易收益。", "Kachin hills connect routes between Assam, Burma, and Yunnan; chiefs trade passage for security and market access."),
    "AHM": ("阿洪王国依靠布拉马普特拉河谷和山地边界维持独立，缅甸与英属印度的压力都不可忽视。", "Ahom authority rests on the Brahmaputra valley and hill frontier, under pressure from both Burma and British India."),
    "AMD": ("安多寺院、牧民与商路城镇共同塑造高原东北部秩序，朝廷政策须得到宗教与地方首领认可。", "Amdo's monasteries, pastoralists, and caravan towns jointly shape the northeastern plateau; policy needs religious and local consent."),
    "DLI": ("大理连接滇西山地和缅甸商路，地方军镇与多族城镇要求自治得到制度承认。", "Dali links western Yunnan's hills with Burmese trade routes; garrisons and diverse towns demand recognized local autonomy."),
    "PNP": ("波纳佩各酋邦围绕港湾、耕地和岛间航路协商，外来船只带来贸易也带来主权争议。", "Pohnpei's chiefdoms negotiate over harbours, farmland, and inter-island routes; foreign ships bring trade and sovereignty disputes."),
    "PLW": ("帕劳的岛屿社群依赖珊瑚礁渔场和安全锚地，外来商船的停泊须服从本地裁判权。", "Palau's island communities depend on reef fisheries and safe anchorages, while visiting ships must respect local jurisdiction."),
    "YAP": ("雅浦的石币网络和岛间航海维系地方声望，港湾开放与传统裁决需要并行。", "Yap's stone-money networks and inter-island navigation sustain local prestige; open harbours must coexist with customary arbitration."),
    "MHL": ("马绍尔群岛各环礁依靠航海、椰干和渔场互通，海上补给和首领间协约决定防务。", "Marshallese atolls depend on navigation, copra, and shared fisheries; maritime supply and chiefly compacts shape defence."),
    "MHG": ("湄公河华人共和国依靠三角洲航运、稻作和跨境商贸维系新政权；地方社群的土地权与河道治理必须写入共同制度。", "The Mekong Chinese Republic rests on delta shipping, rice cultivation, and cross-border commerce; its institutions must protect local land rights and govern shared waterways."),
    "MRG": ("马雷格联盟沿澳大利亚北岸分布，渔猎与跨海贸易必须在英国殖民扩张中守住社群土地。", "The Marege alliance spans Australia's northern coast; communities must protect their land and sea trade amid British colonial expansion."),
    "CHD": ("昌都僧院和康区首领共同掌握连接拉萨、四川与青海的山口，交通税源与地方宗教权威彼此牵制。", "Chamdo's monasteries and Kham chiefs control passes linking Lhasa, Sichuan, and Qinghai, balancing toll revenue with religious authority."),
    "HOR": ("霍尔诸部依靠牧地和通往藏北的商道结盟，任何统一军役安排都必须获得各部首领认可。", "The Hor states unite through pasture and northern Tibetan trade; any common military service needs the chiefs' consent."),
    "LTG": ("理塘位于康区交通要道，寺院地产与牧民供役共同支撑地方治理。", "Litang sits on a Kham transit route, where monastic estates and pastoral service both sustain local government."),
    "TSK": ("塔什干是中亚绿洲与草原交界的商贸枢纽，城镇自治、关税和汗权决定其对外选择。", "Tashkent is a commercial hinge between Central Asian oases and the steppe; urban autonomy, tolls, and the khan's authority shape its diplomacy."),
    "KIR": ("吉尔吉斯部族跨越天山牧场，联盟要在季节迁徙、俄国边境和中亚汗国之间维持共同立场。", "Kyrgyz clans range across Tian Shan pasture and must coordinate seasonal migration between the Russian frontier and Central Asian khanates."),
    "SMR": ("撒马尔罕依靠泽拉夫尚河灌溉和丝路市集维持繁荣，城中商人和周边绿洲共同影响统治。", "Samarkand prospers through Zeravshan irrigation and Silk Road markets, with merchants and surrounding oases shaping its rule."),
    "KRS": ("卡尔希连接布哈拉与阿富汗方向的商路，绿洲水利和边境防务是埃米尔财政的两端。", "Karshi links routes from Bukhara toward Afghanistan; oasis irrigation and frontier defence both draw on the emir's treasury."),
    "KGL": ("康里汗国围绕草场和锡尔河商路组织诸部，必须防止邻近绿洲强权把互市变成臣属关系。", "The Kongrat Khanate organizes clans around pasture and Syr Darya trade, resisting attempts by oasis powers to turn commerce into subordination."),
    "MEV": ("梅尔夫依靠绿洲灌溉和跨沙漠商路连接波斯与中亚，水利维修和商队保护优先于征服。", "Merv links Persia and Central Asia through oasis irrigation and desert caravans, making waterworks and merchant protection more urgent than conquest."),
    "AKS": ("阿克苏把塔里木绿洲与伊犁商路相连，城镇守备和水源管理决定其能否抵御更强汗国。", "Aksu links Tarim oases with Ili trade; town defences and water management determine whether it can withstand stronger khanates."),
    "ODS": ("鄂尔多斯盟旗控制黄河套地和南下牧道，盟主需要协调牧地使用并防止大国把旗盟分化。", "Ordos banners control the Yellow River bend and southern grazing routes; their leader must share pasture and resist outside attempts to divide the league."),
    "CHR": ("察哈尔诸部位于草原与华北边缘，盟誓和骑兵调度是他们在大顺与北方强权间的筹码。", "Chahar clans lie between the steppe and North China, using oaths and cavalry coordination as bargaining power with Great Shun and northern rivals."),
    "BKY": ("布凯汗国依赖伏尔加—乌拉尔草原牧道，俄国的定居边疆与商贸扩展正压缩部族迁徙空间。", "The Bukey Horde depends on Volga-Ural pasture routes as Russian settlement and commerce narrow the clans' room to migrate."),
    "SHB": ("沙赫里萨布兹依托绿洲农田和山口商路维持地方王权，布哈拉与周边汗国都觊觎其税源。", "Shahrisabz sustains local rule through oasis farms and mountain trade, while Bukhara and neighbouring khanates seek its revenue."),
    "QRT": ("卡拉特金山地领地控制通往费尔干纳的隘口，地方首领以通行权换取自治与安全保障。", "Karategin's mountain chiefs control passes toward Ferghana, exchanging access for autonomy and security guarantees."),
    "TKK": ("特克部族守卫希瓦以南的绿洲与商路，草场迁徙和俄国里海扩张共同威胁其独立。", "Teke clans guard oases and routes south of Khiva, facing threats to their independence from pasture pressures and Russian expansion around the Caspian."),
    "YMD": ("约穆特部族联系里海岸与希瓦商路，海上贸易和草原迁徙都需要灵活的部族协商。", "Yomut clans link the Caspian shore with Khiva's routes, relying on flexible bargains for sea trade and steppe migration."),
    "BYL": ("巴宜乌尔联盟以部族盟誓维持草原防务，成员需要在共同骑兵义务和牧地自治间取得平衡。", "The Bai-Ul league sustains steppe defence through clan oaths, balancing shared cavalry duties against pasture autonomy."),
    "JTR": ("七河诸部横跨天山北麓与草原，俄国移民和边防扩张使迁牧权成为联盟核心议题。", "The Seven Juz span the northern Tian Shan and steppe, where Russian settlement and frontier growth make migration rights central."),
    "NMN": ("乃蛮部众依靠草原盟约和骑兵协作维持联盟，周边强权都试图争取其边境通道。", "Naiman clans hold their league through steppe compacts and cavalry cooperation while neighbouring powers court their border routes."),
    "KER": ("克烈联盟须协调分散牧地与季节军役，汗权能否维持取决于各部是否获得公平份额。", "The Kereit league must coordinate scattered pasture and seasonal service; the khan's authority rests on fair shares for each clan."),
    "ZHL": ("札剌亦儿诸部连接北方草原与绿洲边缘，互市和共同防卫须避免演变为外部控制。", "Zhalair clans link the northern steppe with oasis frontiers, seeking trade and common defence without outside control."),
    "ABN": ("阿勒班部众在草原与山地通道间迁徙，部族大会要协调牧场、商队护送和边境承诺。", "Alban clans move between steppe and mountain corridors, coordinating pasture, caravan escorts, and border guarantees through their assembly."),
}

# Selection-screen prose ends with a question tied to each country's own
# political choice. Keep these separate from regional profile boilerplate.
COUNTRY_QUESTIONS = {
    "ABN": ("牧地分配与商队护送该由部族大会共同裁断，还是交还各营地自决？", "Should the assembly settle pasture and caravan escorts together, or leave each camp to decide for itself?"),
    "AHM": ("面对缅甸与英属印度的压力，阿洪王庭要依靠河谷防务，还是借山地通道争取周旋余地？", "Under pressure from Burma and British India, should the Ahom court rely on valley defences or use the hill routes to preserve room to manoeuvre?"),
    "AKS": ("阿克苏有限的税收该先修复绿洲水渠，还是加固通往伊犁的商道？", "Should Aksu spend its limited revenue on oasis canals or on the trade road to Ili?"),
    "AMD": ("高原东北部的军费与道路，要怎样取得寺院、牧户和商镇的共同认可？", "How can Amdo win consent from monasteries, pastoral households, and market towns for roads and defence?"),
    "AMR": ("黑龙江河运应由地方社群共同管理，还是优先满足边防与外来商人的要求？", "Should Amur communities govern river traffic together, or give priority to frontier posts and outside traders?"),
    "BKY": ("俄国商路带来的收益，值得以扩大清廷驻防和盟旗管辖来换取吗？", "Are Russian trade revenues worth accepting a wider Qing and banner presence in Barkul?"),
    "BYL": ("巴宜乌尔各部愿意承担多少共同骑兵义务，才不会失去对牧地的自治？", "How much shared cavalry service will the Bai-Ul clans accept before pasture autonomy is at risk?"),
    "CHD": ("昌都的关卡收入该由寺院与康区首领共同支配，还是集中到一个政权手中？", "Should Chamdo's toll revenue remain shared by monasteries and Kham chiefs, or be gathered under one authority?"),
    "CHI": ("大清要依靠八旗和满洲官署立足，还是借俄国边贸牵制大顺的压力？", "Should Great Qing rely on its banners and Manchu offices, or use Russian trade to counter pressure from Great Shun?"),
    "CHR": ("察哈尔诸部要把骑兵盟约交给大顺统筹，还是继续以部族议盟保留选择权？", "Should Chahar cavalry compacts answer to Great Shun, or remain under a clan council that preserves room to choose?"),
    "DER": ("德格的印经院与道路账册，要由僧俗共同管理到什么程度？", "How much authority over Derge's printing house and road registers should be shared by religious and lay leaders?"),
    "DLI": ("大理的军镇能否在保障缅甸商路时，也给多族城镇正式的自治席位？", "Can Dali secure the Burmese trade routes while giving its diverse towns a formal voice in local rule?"),
    "DMG": ("东明要如何与西班牙抗衡，同时让伊洛卡诺社群把明朝名号视为共同国家的根基？", "How can Eastern Ming resist Spain and persuade Ilocano communities to make the Ming name part of a shared state?"),
    "DRZ": ("德令哈该如何守住水源和跨高原商路，又不让邻近汗国垄断关税？", "How can Delingha protect its wells and trans-highland routes without letting a neighbouring khanate monopolize tolls?"),
    "GYL": ("嘉绒联盟若要常设防务，各部的席位、军役与收益应怎样分配？", "If the Gyalrong league establishes common defence, how should it divide seats, service, and revenue among its tribes?"),
    "HMI": ("哈密应向清廷官署和西来商队开放到什么程度，才能保住驿站与水渠的收益？", "How far should Hami open to Qing offices and western caravans while keeping the returns from its relays and canals?"),
    "HOR": ("藏北商路需要共同守护时，霍尔诸部会接受怎样的军役约定？", "What common service would the Hor states accept to protect northern Tibetan trade?"),
    "HSR": ("河湟回部城镇如何维护清真寺社群的自治，同时让商路关税不被邻国接管？", "How can the Hui towns of Hehuang protect communal autonomy while keeping neighbouring powers from taking their trade dues?"),
    "HUL": ("呼伦贝尔的互市能否在不设常驻外军的条件下换来边防保障？", "Can Hulun trade bring frontier guarantees without allowing a neighbour to station permanent forces?"),
    "HXI": ("河西军镇应把征粮与调兵权交给大顺朝廷，还是保留地方将领的裁量？", "Should Hexi commanders hand levies and mobilization to Great Shun, or keep those decisions local?"),
    "JHG": ("靖海如何在维护舰队与船坞的同时，守住港口自治和对大顺的藩贡承诺？", "How can Jinghai maintain its fleet and dockyards while preserving port autonomy and its tribute obligations to Great Shun?"),
    "JTR": ("七河诸部要怎样保障季节迁牧，才能抵住俄国移民和边防线的推进？", "How can the Seven Juz protect seasonal migration as Russian settlement and frontier posts advance?"),
    "KAM": ("康区首领要以何种盟约同时回应大顺边务与拉萨的宗教影响？", "What compact can Kham chiefs accept while answering both Great Shun's frontier demands and Lhasa's religious influence?"),
    "KCH": ("克钦山道的通行收益该换取阿萨姆、缅甸还是云南方向的安全承诺？", "Should Kachin passage rights buy security guarantees from Assam, Burma, or Yunnan?"),
    "KER": ("克烈各部怎样分担季节军役，才能让弱小营地也得到公平牧地？", "How should the Kereit clans share seasonal service so smaller camps retain fair pasture?"),
    "KGL": ("康里汗国能否开放锡尔河互市，又不让布哈拉把商贸变成臣属？", "Can the Kongrat Khanate open Syr Darya trade without letting Bukhara turn commerce into subordination?"),
    "KHO": ("和硕特汗国该怎样协调青海牧地、寺院利益和通往西藏的商道？", "How should the Khoshut Khanate balance Qinghai pasture, monastic interests, and trade toward Tibet?"),
    "KHQ": ("科尔沁诸旗要在满洲清廷、大顺与俄国之间选择怎样的结盟边界？", "Where should Khorchin banners draw the line between alliance with Qing Manchuria, Great Shun, and Russia?"),
    "KHT": ("和田要优先保障玉石商队、南疆山口，还是绿洲农田的用水？", "Should Khotan first protect jade caravans and southern passes, or secure irrigation for its oasis farms?"),
    "KIR": ("吉尔吉斯部族能否协调跨天山迁牧，同时避免被俄国边防或汗国征役束缚？", "Can Kyrgyz clans coordinate migration across the Tian Shan without becoming bound by Russian posts or khanate service?"),
    "KOR": ("朝鲜朝廷要先推动海防与新知，还是先取得文官和边镇执行改革的信任？", "Should Joseon prioritize coastal defence and new learning, or first earn the officials' and garrisons' trust to carry out reform?"),
    "KRS": ("卡尔希该把财政投向绿洲水利还是阿富汗方向的边防？", "Should Karshi direct its treasury toward oasis irrigation or frontier defence toward Afghanistan?"),
    "KSH": ("喀什噶尔要让费尔干纳商队自由通行，还是以更严的边境盟约换取汗权安全？", "Should Kashgar keep Ferghana caravans moving freely, or seek security for the khanate through tighter border compacts?"),
    "KTG": ("景栋如何在缅甸王庭、兰纳邻邦和大顺使者之间守住茶路与裁决权？", "How can Kengtung protect its tea routes and local arbitration among Burma, Lan Na, and Great Shun?"),
    "KUC": ("库车该先修复塔里木水渠，还是加固保障驿站秩序的城镇守备？", "Should Kucha first repair Tarim canals or strengthen the town guards that keep its relay stations secure?"),
    "KZH": ("这支草原联盟要以何种盟誓协调牧地，而不把防务交给邻近汗国？", "What oath can unite this steppe league over pasture without handing its defence to a neighbouring khanate?"),
    "LAD": ("拉达克该如何保障克什米尔与西藏间的季节商路，又不让关隘成为外部驻军的借口？", "How can Ladakh secure seasonal trade between Kashmir and Tibet without turning its passes into a pretext for foreign garrisons?"),
    "LAN": ("兰芳的矿利该优先分给公司股东，还是承担客家村社的道路、劳工与防务责任？", "Should Lanfang's mining profits favour company shareholders, or fund roads, workers, and defence for Hakka settlements?"),
    "LJG": ("木府要如何保障盐道通行，同时让纳西聚落继续保有旧有边界？", "How can the Mu house keep its salt roads open while respecting the old boundaries of Naxi communities?"),
    "LTG": ("理塘的寺院地产和牧民供役，应由谁来裁定道路与地方治理的负担？", "Who should decide how Litang's monastic estates and pastoral households share the costs of roads and local government?"),
    "LXJ": ("大顺整饬边务时，丽江木氏要交出多少裁量，才能换取商路与旧盟约的承认？", "As Great Shun reorganizes the frontier, how much discretion should the Mu house yield in return for recognition of its trade routes and old compacts?"),
    "MEV": ("梅尔夫的有限财力该先修水利，还是用于保护穿越沙漠的商队？", "Should Merv spend its limited means first on waterworks or on protecting desert caravans?"),
    "MHG": ("湄公河华人政权怎样把沿河社群的土地权和共同河道治理写入制度？", "How will the Mekong Chinese state protect riverside land rights while governing waterways shared across communities?"),
    "MHL": ("马绍尔各环礁要怎样分担海上补给与巡护，才能让首领协约继续有效？", "How should the Marshallese atolls share maritime supply and patrols so their chiefly compact holds?"),
    "MRG": ("马雷格社群要如何守住北岸土地与跨海贸易，面对英国殖民扩张？", "How can Marege communities defend northern lands and sea trade as British colonial expansion advances?"),
    "NMG": ("新明要以自治、联邦席位还是地方防务作为与墨西哥谈判的首要保证？", "Should New Ming make autonomy, federal representation, or local defence its first guarantee in negotiations with Mexico?"),
    "NMN": ("乃蛮各部愿意开放哪些边境通道，才不会把商贸变成邻国的控制？", "Which border routes will Naiman clans open without letting trade become a neighbour's instrument of control?"),
    "NQG": ("北清应接受北方强权的海岸保护，还是冒险独自经营复国所需的港口与粮仓？", "Should Northern Qing accept northern protection of its coast, or risk building the ports and stores needed for restoration on its own?"),
    "ODS": ("鄂尔多斯盟旗要如何协调黄河套地和南下牧道，避免被大国逐一拉拢？", "How can Ordos banners coordinate the Yellow River bend and southern grazing routes before outside powers court them separately?"),
    "OIR": ("统一伊犁牧地规约能否巩固卫拉特汗权，而不把异议旗盟推向外部保护者？", "Can common pasture law strengthen the Oirat khan without driving dissenting banners toward outside patrons?"),
    "OZH": ("盟主要以何种议约协调草场和商路，才能避免常备军役削弱部众忠诚？", "What compact can coordinate pasture and trade without fixed service weakening the clans' loyalty?"),
    "PLW": ("帕劳能否欢迎外来船只补给，同时坚持由本地社群裁决港湾争端？", "Can Palau welcome visiting ships for supplies while keeping harbour disputes under local jurisdiction?"),
    "PNP": ("波纳佩各酋邦开放港湾之后，如何保住耕地、锚地和岛间争端的裁决权？", "After Pohnpei opens its harbours, how will its chiefdoms retain authority over farmland, anchorages, and inter-island disputes?"),
    "QRT": ("卡拉特金该以多少商道通行权换取山地自治与边境安全？", "How much access to its mountain routes should Karategin exchange for local autonomy and frontier security?"),
    "RKN": ("若开要接受英国保护承诺，还是依靠海港和山路抵御缅甸王庭的影响？", "Should Arakan accept British protection, or rely on its ports and mountain routes to resist Burmese influence?"),
    "SHB": ("沙赫里萨布兹如何守住绿洲税源，又避免布哈拉把贸易收益纳入自身版图？", "How can Shahrisabz keep its oasis revenue without letting Bukhara absorb its trade into the emirate?"),
    "SHD": ("掸邦联席会议能否在统一巡护与征税时，仍让各土司保有实际裁决权？", "Can the Shan council organize common patrols and dues while leaving each chief a real voice in arbitration?"),
    "SHU": ("大顺朝廷要如何在军功集团、地方士绅与新式官署之间重分权责？", "How should Great Shun divide authority among military households, local gentry, and its changing administration?"),
    "SIP": ("车里诸土司要怎样回应大顺与缅甸的贡赋要求，才不失去联席议事的余地？", "How can the rulers of Kengtung answer tribute demands from Great Shun and Burma while preserving room for council decisions?"),
    "SMR": ("撒马尔罕应由城中商人还是周边绿洲共同决定灌溉与丝路关税？", "Should Samarkand's merchants or its surrounding oases set the rules for irrigation and Silk Road tolls?"),
    "SOL": ("黑龙江沿岸诸社群要怎样共管河运与哨所，才能维持联盟而不受外部支配？", "How can Solon communities govern river traffic and frontier posts together without falling under outside control?"),
    "TIB": ("拉萨的政令要如何越过地方盟约，既保障寺院供养又获得康区首领执行？", "How can Lhasa's orders cross local compacts while sustaining the monasteries and winning Kham chiefs' cooperation?"),
    "TKK": ("特克部族应优先防守希瓦商路还是争取更大的草场迁徙空间，以抵挡俄国扩张？", "Should Teke clans prioritize the Khiva routes or wider pasture access as Russian expansion advances?"),
    "TRF": ("吐鲁番要怎样分配坎儿井维护与葡萄园收益，才能守住通往塔里木的商道？", "How should Turfan balance karez upkeep and vineyard income while protecting its routes to the Tarim?"),
    "TSK": ("塔什干应以城镇自治换取商路畅通，还是让汗权集中关税与外交？", "Should Tashkent trade urban autonomy for open commerce, or let the khan centralize tolls and diplomacy?"),
    "UZH": ("这支联盟该把互市扩展到什么程度，才能与南方绿洲往来又不受其支配？", "How far should this league expand trade with the southern oases without coming under their control?"),
    "WAA": ("佤邦共同防务要如何尊重分散村社的权力，而不让联盟失去协同行动？", "How can Wa common defence respect village authority without leaving the confederation unable to act together?"),
    "WBK": ("西婆罗洲矿业联盟要如何约束公司章程，才能同时保护客家社群和河口商路？", "How should West Borneo's mining league constrain company charters while protecting Hakka communities and river-mouth trade?"),
    "YAP": ("雅浦开放港湾后，能否继续由传统裁决处理岛间航路和石币网络的争端？", "After Yap opens its harbours, can customary arbitration still settle disputes over navigation and stone-money networks?"),
    "YMD": ("约穆特部族如何兼顾里海贸易与草原迁徙，不让希瓦或俄国垄断通行？", "How can Yomut clans balance Caspian trade with steppe migration without letting Khiva or Russia monopolize passage?"),
    "YRK": ("叶尔羌该优先整顿水渠还是统一商税，才能同时维持城镇与乡村的生计？", "Should Yarkand first repair its canals or standardize tolls to sustain both towns and villages?"),
    "ZHL": ("札剌亦儿诸部要怎样扩大互市与共同防卫，同时阻止邻国取得常驻控制？", "How can Zhalair clans expand trade and common defence while preventing a neighbour from gaining permanent control?"),
    "MGL": ("喀尔喀汗国该优先倚重大顺茶马边市，还是接受俄国北路的保护与约束？", "Should the Khalkha Khanate rely on Great Shun's tea-horse markets or accept the protection and limits of Russia's northern route?"),
    "DAI": ("大南要优先扩充沿海防务与官署，还是把资源留给农业、道路和港口贸易？", "Should Dai Nam expand coastal defences and offices, or keep resources for agriculture, roads, and port trade?"),
}

def read_country_names() -> dict[str, str]:
    names = dict(NAME_EN_OVERRIDES)
    for path in (MOD / "localization").rglob("*.yml"):
        if "english" not in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for tag, name in re.findall(r'^\s*([A-Z]{3}):\d+\s+"([^"]+)"', text, re.M):
            names.setdefault(tag, name)
    return names

def live_start_tags() -> set[str]:
    """Tags with a mod country-history start block are the actual playable set."""
    tags: set[str] = set()
    pattern = re.compile(r"c:([A-Z0-9]{3})\s*\?=\s*\{")
    for path in (MOD / "common/history/countries").glob("*.txt"):
        tags.update(pattern.findall(path.read_text(encoding="utf-8-sig")))
    return tags

def outputs() -> dict[pathlib.Path, str]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    countries = {row["tag"]: row for row in registry["countries"]}
    live = live_start_tags()
    # Existing, purpose-built country campaigns and regional journals remain
    # authoritative. Add the new start to every other registered mod polity.
    included = sorted((set(countries) & live) - OWNED)
    names_en = read_country_names()
    journals: list[str] = ["# Generated by tools/build_frontier_polity_content.py; edit the registry/profile source, not this file.\n"]
    events: list[str] = ["# Generated by tools/build_frontier_polity_content.py; each choice chain is tag-scoped.\n"]
    loc_en = ["l_english:"]
    loc_zh = ["l_simp_chinese:"]
    flavor_en = ["l_english:"]
    flavor_zh = ["l_simp_chinese:"]
    special_flavor = {
        "SHU": ("大顺继承中原王朝的中央官署与辽阔疆域，却必须在军功集团、地方士绅和新式行政之间重新划定权责。统一仍有力量，财政与边疆都在考验朝廷能否兑现承诺。", "Great Shun inherited China's central offices and a vast realm, but must renegotiate authority among military households, local gentry, and a changing administration. Unity remains powerful; treasury and frontier will test whether the court can keep its promises."),
        "JHG": ("靖海凭郑氏海军、商行与大顺宗藩关系立足台湾。护航和港口可以带来财富，船坞、藩贡与自治却争夺同一笔预算。", "Jinghai rests on the Zheng fleet, merchant houses, and its tributary ties to Great Shun. Convoys and ports can bring wealth, while dockyards, tribute, and autonomy compete for the same budget."),
        "DMG": ("东明在吕宋建立明裔政权，面对西班牙的主张，也必须争取伊洛卡诺与其他本地社群的信任。王朝名号只有写进共同契约，才能成为国家根基。", "Eastern Ming has built a Ming-descended court on Luzon. Spain presses its claims, while Ilocano and other local communities must decide whether to trust the new state. A dynastic name becomes a foundation only when written into a shared compact."),
        "NQG": ("北清流亡朝廷退守库页岛，复国记忆无法代替粮仓、港口与岛民的认可。北方强权能提供贸易和保护，也会要求对外交与海岸拥有发言权。", "Northern Qing's exile court has retreated to Sakhalin, where restorationist memory cannot replace stores, ports, or the consent of island communities. Northern powers offer trade and protection while demanding a voice over diplomacy and the coast."),
        "OIR": ("卫拉特汗国继承准噶尔的军政遗产、伊犁商路和彼此竞争的旗盟。统一牧地规约能加强汗权，也可能把不愿受管束的部众推向外部保护者。", "The Oirat Khanate inherits Dzungar institutions, Ili's caravan trade, and competing banners. Common pasture law can strengthen the khan, yet drive resistant clans toward outside patrons."),
        "MGL": ("喀尔喀汗国夹在大顺茶马边市与俄国北路之间。两条商路都能带来军需和收入，任何一方的保护承诺也都可能压缩汗国的自主空间。", "The Khalkha Khanate stands between Great Shun's tea-horse markets and Russia's northern road. Both routes bring supplies and revenue; either patron's guarantees can narrow the khanate's room to act."),
        "TIB": ("甘丹颇章的僧院、贵族与康区首领共同塑造高原秩序。寺院地产支撑行政和军队，地方盟约则决定拉萨的命令能否越过山口。", "The Ganden Phodrang's monasteries, nobles, and Kham chiefs jointly shape the highland order. Monastic estates sustain administration and troops; local compacts decide whether Lhasa's orders cross the passes."),
        "KOR": ("朝鲜拥有成熟的文官体系，却受到边镇安全、礼仪名分与海上新知的多重牵制。改革能否落地，取决于朝廷是否获得官署和军镇共同执行的信用。", "Joseon has a mature civil administration, constrained by frontier security, ritual standing, and new maritime knowledge. Reform depends on the court earning the trust of offices and garrisons to carry it out."),
        "LAN": ("兰芳的矿井、公司章程与客家村社彼此依存，荷兰势力则不断要求更多港口和矿权。公司共和若要生存，利润必须承担道路、劳工与防务责任。", "Lanfang's mines, company charters, and Hakka settlements depend on one another as Dutch power presses for greater access to ports and claims. A company republic endures only if profits carry duties to roads, workers, and defence."),
        "NMG": ("新明在下加利福尼亚经营华墨边疆，必须与墨西哥谈判自治、联邦席位和地方防务。教会与多族社区能凝聚新国家，也要求看得见的制度保障。", "New Ming governs a Chinese-Mexican frontier in Baja California and must negotiate autonomy, federal representation, and local defence with Mexico. Church networks and plural communities can bind the state together, but require visible institutional guarantees."),
        "AHM": ("阿洪王国依靠布拉马普特拉河谷的稻田与水道维持生计，南缘山口又牵动对缅防务。王庭必须在整修水利、守护边界和维持地方首领的效忠之间分配有限资源。", "The Ahom kingdom depends on rice fields and waterways in the Brahmaputra valley, while southern hill passes shape its defence against Burma. The court must divide scarce resources between irrigation, border security, and the allegiance of local chiefs."),
        "DLI": ("大理的城镇、山地与洱海相连，商路通往云南腹地和缅甸边境。政权要在守护关隘、维持地方盟约与保障跨境贸易之间安排有限的军费和税收。", "Dali's towns, mountains, and Erhai Lake link caravan routes into Yunnan and toward the Burmese frontier. The state must divide scarce revenue between defending passes, maintaining local compacts, and keeping cross-border trade open."),
        "KCH": ("克钦诸邦依靠高地村寨与山道维持自治，通路连接滇缅边境和周边低地。邻近王朝要求通行与驻防，山地首领则要守住地方裁决权。", "Kachin polities rely on upland communities and mountain routes for autonomy along the Burma-Yunnan frontier. Neighbouring courts seek passage and garrisons, while hill chiefs work to retain local authority."),
        "KTG": ("景栋位于掸邦东部的山地商路之间，茶市、山口以及大顺与缅甸的影响共同塑造其议事秩序。地方首领必须在互市收益、边防义务与自治之间议定边界。", "Kengtung lies among the eastern Shan hills and their caravan routes. Tea markets, mountain passes, and pressure from Great Shun and Burma shape its councils; local chiefs must balance trade, frontier duties, and autonomy."),
        "WAA": ("佤邦高地由多个村寨和山地首领组成，跨山通道连接掸邦、云南与缅甸低地。共同防务和边市能带来安全与收益，但各村寨仍要保有裁断事务的权力。", "Wa highlands consist of villages and local chiefs linked by routes toward Shan, Yunnan, and Burma's lowlands. Common defence and border markets can bring security and revenue, while each community retains a say in its affairs."),
        "LJG": ("丽江木氏依靠山地商路、盐引和地方盟约维持权力。大顺整饬边务时，木府必须证明自己既能保障通行，也尊重纳西聚落的旧有边界。", "The Mu house of Lijiang relies on mountain trade, salt licences, and local compacts. As Great Shun reorganizes the frontier, it must secure passage while respecting Naxi communities' boundaries."),
        "SIP": ("车里诸土司以茶山、山口和季节性贡赋维持曼荼罗秩序。大顺与缅甸使者都带着要求，联席议事要在两边之间争取实际余地。", "The rulers of Kengtung sustain a mandala order through tea hills, passes, and seasonal tribute. Envoys from Great Shun and Burma both bring demands; council deliberation must secure room between them."),
        "DER": ("德格依靠印经院、寺院地产和横穿康区的商队维持繁荣。账册和道路可以巩固政权，却必须获得僧俗与沿线首领的共同认可。", "Derge depends on its printing house, monastic estates, and caravans across Kham. Registers and roads can strengthen the state, but require consent from religious authorities and chiefs along the route."),
        "GYL": ("嘉绒诸部在屯田、山地关隘和共同防务之间寻找新均势。盟主若想把临时协作变成稳定联盟，必须说明各部的席位、军役和收益如何分配。", "The Gyalrong tribes seek a balance among farms, mountain passes, and common defence. A durable league requires clear rules for each member's voice, service, and share of the gains."),
        "SHD": ("掸邦联席会议连接分散的山地领地，也要回应大顺、缅甸与英国势力的压力。共同征税与巡护能带来安全，前提是各土司仍能参与裁决。", "The Shan council links scattered hill territories while answering pressure from Great Shun, Burma, and Britain. Common dues and patrols can bring security if each chief retains a voice in arbitration."),
        "RKN": ("若开以海岸港口和山地通道维持独立空间，同时面对英国保护要求与缅甸王庭的影响。海贸能提供财政，外交承诺却会重新划定自身边界。", "Arakan preserves its room to act through coastal ports and mountain routes while facing British protection demands and Burmese influence. Trade can fund the state, but each diplomatic promise redraws its boundaries."),
        "HXI": ("河西走廊的军镇依靠驿道、屯田与关隘维持补给。大顺朝廷需要它守住西行商路，地方将领则要求保留调兵与征粮的裁量；修复烽燧和仓站比经营森林河运更迫切。", "The Hexi corridor garrisons depend on relay roads, military farms, and passes for supply. Great Shun needs them to secure the western trade route, while commanders demand room over levies and provisions; restoring signal towers and depots matters more than river timber traffic."),
        "DRZ": ("德令哈周边的商路连接青海湖与柴达木盆地，穆斯林商户和地方首领都要守住水源与驿站。政权的要务是保障跨高原贸易并平衡邻近部族的势力，而非以寺院地产统合全境。", "Routes around Delingha link Lake Qinghai with the Qaidam Basin. Muslim merchants and local chiefs depend on wells and relay stations; the state's task is to protect trans-highland trade and balance neighbouring groups, not to govern through monastic estates."),
        "HSR": ("河湟谷地的回部城镇依靠绿洲农田、清真寺网络与青藏商路维持生计。周边强权都希望控制关口和赋税，地方政治的关键是保障信仰社群的自治并维持通行。", "The Hui towns of the Hehuang valley rely on oasis farming, mosque networks, and trade toward Tibet. Nearby powers seek control of passes and dues; local politics turns on protecting communal autonomy while keeping routes open."),
        "BKY": ("巴里坤位于天山北麓，是清廷通往伊犁与准噶尔草原的军驿节点。清朝官署、驻军和蒙古盟旗共同影响边防；俄国越境商路带来货物，也带来新的势力竞争。", "Barkul lies north of the Tian Shan on the Qing military route toward Ili and the Dzungar steppe. Qing offices, garrisons, and Mongol banners all shape its defence; Russian trade brings goods and a new contest for influence."),
    }
    for tag, row in sorted(countries.items()):
        if tag not in live or tag == "MGL":
            continue
        p = PROFILES[TAG_PROFILE.get(tag, "frontier")]
        zh = row["name_zh"]
        country_en = names_en.get(tag, tag)
        if tag in special_flavor:
            zh_text, en_text = special_flavor[tag]
        elif tag in COUNTRY_CONTEXT:
            geo_zh, geo_en = COUNTRY_CONTEXT[tag]
            zh_text, en_text = f"{geo_zh}{p['zh_intro']}", f"{geo_en} {p['en_intro']}"
        else:
            zh_text, en_text = f"{zh}一带的{p['zh_pressure']}。{p['zh_intro']}", f"In {country_en}, {p['en_pressure']}. {p['en_intro']}"
        zh_question, en_question = COUNTRY_QUESTIONS[tag]
        flavor_zh.append(f' {tag}_FLAVOR_TEXT:0 "{zh_text}{zh_question}"')
        flavor_en.append(f' {tag}_FLAVOR_TEXT:0 "{en_text} {en_question}"')
    mgl_zh_question, mgl_en_question = COUNTRY_QUESTIONS["MGL"]
    dai_zh_question, dai_en_question = COUNTRY_QUESTIONS["DAI"]
    flavor_zh.append(f' MGL_FLAVOR_TEXT:0 "喀尔喀汗国夹在大顺茶马边市与俄国北路之间。两条商路都能带来军需和收入，任何一方的保护承诺也都可能压缩汗国的自主空间。{mgl_zh_question}"')
    flavor_en.append(f' MGL_FLAVOR_TEXT:0 "The Khalkha Khanate stands between Great Shun\'s tea-horse markets and Russia\'s northern road. Both routes bring supplies and revenue; either patron\'s guarantees can narrow the khanate\'s room to act. {mgl_en_question}"')
    flavor_zh.append(f' DAI_FLAVOR_TEXT:0 "大南控制着湄公河以东的越南腹地。扩展边防和官署会带来安全，也会消耗王朝必须用于农业、道路与沿海贸易的资源。{dai_zh_question}"')
    flavor_en.append(f' DAI_FLAVOR_TEXT:0 "Dai Nam governs the Vietnamese heartland east of the Mekong. Extending garrisons and offices can improve security, but draws resources from agriculture, roads, and coastal trade. {dai_en_question}"')
    ai = ["# Generated frontier strategies; low infamy ceilings and no colonial interests preserve their regional scale.\n"]
    startup = ["# Generated frontier starts; installed once after lobby initialization.\n", "ywc_install_frontier_starts = {\n\teffect = {\n\t\tevery_country = {\n"]
    for index, tag in enumerate(included):
        row = countries[tag]
        zh = row["name_zh"]
        en = names_en.get(tag, tag)
        profile_id = TAG_PROFILE.get(tag, "frontier")
        p = PROFILES[profile_id]
        je = f"ywc_je_frontier_{tag.lower()}"
        evbase = "ywc_frontier"
        event_first = index * 3 + 1
        journals.append(f"""\n{je} = {{
\tis_shown_in_lobby = {{ c:{tag} ?= THIS }}
\ticon = "gfx/interface/icons/event_icons/event_portrait.dds"
\tgroup = je_group_internal_affairs
\ton_monthly_pulse = {{
\t\teffect = {{
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tNOT = {{ has_variable = ywc_frontier_{tag.lower()}_stage1 }}
\t\t\t\t\tNOT = {{ has_variable = ywc_frontier_{tag.lower()}_resolved }}
\t\t\t\t}}
\t\t\t\ttrigger_event = {{ id = {evbase}.{event_first} }}
\t\t\t}}
\t\t}}
\t}}
\tcomplete = {{ has_variable = ywc_frontier_{tag.lower()}_resolved }}
}}
""")
        for stage in (1, 2, 3):
            next_stage = stage + 1
            event_id = f"{evbase}.{event_first + stage - 1}"
            next_event_id = f"{evbase}.{event_first + stage}"
            if stage == 1:
                title_en = f"{en}: The Local Compact"
                title_zh = f"{zh}：地方約章"
                desc_en = f"{p['en_open']} The debate in {en} turns on whether authority will be recorded in a common register or left with local brokers."
                desc_zh = f"{p['zh_open']} {zh}眼下要决定：由共同账册统一规制，还是继续把裁量留给地方中介。"
                opt0_en, opt0_zh = "Record the obligations and boundaries.", "把义务与边界写入公册。"
                opt1_en, opt1_zh = "Keep the settlement in local hands.", "让地方继续自行维持约定。"
            elif stage == 2:
                title_en = f"{en}: Roads and Dues"
                title_zh = f"{zh}：道路与税额"
                desc_en = f"{p['en_pressure'].capitalize()}. Delegates now ask whether the state should fund the route or preserve local tolls and retainers."
                desc_zh = f"{p['zh_pressure']}。代表们要求决定由国库出资整顿通道，还是保留地方关税与供役安排。"
                opt0_en, opt0_zh = "Fund a shared route and inspection posts.", "出资修路并设置共同核验点。"
                opt1_en, opt1_zh = "Keep the existing dues and obligations.", "保留现有税额与地方供役。"
            else:
                title_en = f"{en}: A Place Among Neighbours"
                title_zh = f"{zh}：邻国之间"
                desc_en = f"The opening compact has clarified who may speak for {en}, but not how far its commitments should reach. The final council weighs a regional guarantee against a narrower, self-reliant settlement."
                desc_zh = f"开局约章已经说明谁能代表{zh}发言，却还没有决定对外承诺的边界。最后一次议事要在区域互保与有限自立之间作出选择。"
                opt0_en, opt0_zh = "Seek a reciprocal regional guarantee.", "争取彼此承担义务的区域保障。"
                opt1_en, opt1_zh = "Keep the agreement narrow and affordable.", "把约定收窄到本国承担得起的范围。"
            loc_en += [f' {event_id}.t:0 "{title_en}"', f' {event_id}.d:0 "{desc_en}"', f' {event_id}.a:0 "{opt0_en}"', f' {event_id}.b:0 "{opt1_en}"']
            loc_zh += [f' {event_id}.t:0 "{title_zh}"', f' {event_id}.d:0 "{desc_zh}"', f' {event_id}.a:0 "{opt0_zh}"', f' {event_id}.b:0 "{opt1_zh}"']
            # Only stage 1 needs a flag to stop the monthly pulse reopening
            # the chain. Stages 2 and 3 are sequenced by delayed events.
            stage_marker = (
                f"\t\tset_variable = {{ name = ywc_frontier_{tag.lower()}_stage1 value = 1 }}\n"
                if stage == 1 else ""
            )
            done = f"ywc_frontier_{tag.lower()}_resolved"
            outcome = ("ywc_frontier_council", "ywc_frontier_route", "ywc_frontier_guarantee") if stage < 3 else ("ywc_frontier_tradeoff", "ywc_frontier_restraint")
            option_blocks = []
            for option, modifier in zip(("a", "b"), outcome):
                schedule = f"trigger_event = {{ id = {next_event_id} days = 90 }}" if stage < 3 else f"set_variable = {{ name = {done} value = 1 }}"
                option_blocks.append(f"""\toption = {{
\t\tname = {event_id}.{option}
\t\t{('default_option = yes' if option == 'a' else '')}
{stage_marker.rstrip()}
\t\tadd_modifier = {{ name = {modifier} months = 36 }}
\t\t{schedule}
\t}}
""")
            events.append(f"""\n{event_id} = {{
\ttype = country_event
\tplacement = ROOT
\ttitle = {event_id}.t
\tdesc = {event_id}.d
\tevent_image = {{ video = "{p['art']}" }}
{''.join(option_blocks)}
}}
""")
        loc_en += [f' ywc_je_frontier_{tag.lower()}:0 "The {en} Settlement"', f' ywc_je_frontier_{tag.lower()}_reason:0 "{p["en_intro"]} Its future rests on the balance between local consent, reliable routes, and commitments it can afford."']
        loc_zh += [f' ywc_je_frontier_{tag.lower()}:0 "{zh}的地方约章"', f' ywc_je_frontier_{tag.lower()}_reason:0 "{p["zh_intro"]}未来取决于地方认可、交通通畅与财政承诺之间能否维持平衡。"']
        strategy = f"ai_strategy_ywc_{tag.lower()}"
        build = p["build"]
        goods = " ".join(f'{good} = {{ stance = wants_high_supply }}' for good in p["goods"].split())
        ai.append(f"""\n{strategy} = {{
\ticon = "gfx/interface/icons/ai_strategy_icons/protect_region.dds"
\ttype = diplomatic
\tdesired_tax_level = {p['tax']}
\tmin_tax_level = low
\tmax_tax_level = high
\tundesirable_infamy_level = {{ value = 15 }}
\tunacceptable_infamy_level = {{ value = 30 }}
\tdiplomatic_play_neutrality = {{ value = {p['neutrality']} if = {{ limit = {{ is_active_in_diplomatic_play = yes }} add = 25 }} if = {{ limit = {{ is_subject = yes }} add = 15 }} }}
\tdiplomatic_play_boldness = {{ value = {p['boldness']} if = {{ limit = {{ has_modifier = declared_bankruptcy }} add = -15 }} }}
\trecklessness = {{ value = -0.30 if = {{ limit = {{ has_modifier = declared_bankruptcy }} add = -0.20 }} }}
\taggression = {{ value = {p['aggression']} if = {{ limit = {{ is_subject = yes }} add = -0.12 }} }}
\tcolonial_interest_ratio = {{ value = 0 }}
\tbuilding_group_weights = {{ {build} }}
\tgoods_stances = {{ {goods} }}
\tpossible = {{ always = yes }}
\tweight = {{ value = 30 if = {{ limit = {{ has_modifier = declared_bankruptcy }} multiply = 0.5 }} }}
}}
""")
        startup.append(f"""\t\t\tif = {{
\t\t\t\tlimit = {{ c:{tag} ?= this }}
\t\t\t\tif = {{ limit = {{ is_ai = yes }} set_strategy = {strategy} }}
\t\t\t\tadd_journal_entry = {{ type = {je} }}
\t\t\t}}
""")
    startup.append("\t\t}\n\t}\n}\n\non_game_started_after_lobby = {\n\ton_actions = { ywc_install_frontier_starts }\n}\n")
    loc_en.extend([
        ' ywc_frontier_council:0 "Frontier council compact"',
        ' ywc_frontier_route:0 "Maintained regional route"',
        ' ywc_frontier_guarantee:0 "Reciprocal frontier guarantee"',
        ' ywc_frontier_tradeoff:0 "Bounded regional commitment"',
        ' ywc_frontier_restraint:0 "Local powers retained"',
    ])
    loc_zh.extend([
        ' ywc_frontier_council:0 "边疆议事约章"',
        ' ywc_frontier_route:0 "整饬区域通道"',
        ' ywc_frontier_guarantee:0 "互惠边疆保障"',
        ' ywc_frontier_tradeoff:0 "有限区域承诺"',
        ' ywc_frontier_restraint:0 "保留地方裁量"',
    ])
    static = """# Small, temporary choices for frontier polities; all use tested country modifier fields.
ywc_frontier_council = { country_legitimacy_base_add = 2 country_authority_mult = 0.02 }
ywc_frontier_route = { country_bureaucracy_mult = 0.03 country_loan_interest_rate_mult = -0.02 }
ywc_frontier_guarantee = { country_legitimacy_base_add = 2 country_authority_mult = 0.03 }
ywc_frontier_tradeoff = { country_legitimacy_base_add = 2 country_loan_interest_rate_mult = -0.02 }
ywc_frontier_restraint = { country_authority_mult = 0.03 country_bureaucracy_mult = 0.02 }
"""
    return {
        MOD / "common/journal_entries/ywc_frontier_starts.txt": "".join(journals),
        MOD / "events/ywc_frontier_starts.txt": "namespace = ywc_frontier\n" + "".join(events),
        MOD / "localization/english/ywc_frontier_starts_l_english.yml": "\n".join(loc_en) + "\n",
        MOD / "localization/simp_chinese/ywc_frontier_starts_l_simp_chinese.yml": "\n".join(loc_zh) + "\n",
        MOD / "localization/english/replace/ywc_frontier_country_flavor_l_english.yml": "\n".join(flavor_en) + "\n",
        MOD / "localization/simp_chinese/replace/ywc_frontier_country_flavor_l_simp_chinese.yml": "\n".join(flavor_zh) + "\n",
        MOD / "common/ai_strategies/ywc_frontier_country_ai.txt": "\n".join(ai) + "\n",
        MOD / "common/on_actions/ywc_frontier_startup.txt": "".join(startup),
        MOD / "common/static_modifiers/ywc_frontier_modifiers.txt": static,
    }


def write_generated_output(path: pathlib.Path, content: str) -> None:
    """Write Clausewitz text and localization with the engine-required UTF-8 BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8-sig")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    generated = outputs()
    stale = []
    for path, content in generated.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8-sig") != content:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            write_generated_output(path, content)
            print(f"wrote {path.relative_to(ROOT).as_posix()}")
    if stale:
        print("stale generated files: " + ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print(f"frontier generated files current ({len(generated)} files)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
