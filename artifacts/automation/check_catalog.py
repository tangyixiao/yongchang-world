import json

cat = json.load(open("data/content/large_campaign_event_catalog.json", encoding="utf-8"))
events = {e["id"]: e for e in cat["events"]}
print("total:", len(events))
for eid in ["ywc_shu.100", "ywc_shu.104", "ywc_mng.110", "ywc_crisis.1", "ywc_crisis.6", "ywc_crisis.21"]:
    e = events[eid]
    print("----", eid, e["kind"], "final" if e.get("final") else "")
    print("  cn:", e["title_cn"], "|", e["desc_cn"][:60])
    print("  en:", e["title_en"], "|", e["desc_en"][:60])
    for c in e["choices"]:
        print("   *", c["direction"], "cost", c["cost"], "trade", c["trade"], "|", c["label_cn"][:40], "||", c["label_en"][:50])
# integrity: chapter/position grid
from collections import Counter
cnt = Counter((e["short"], e["chapter"]) for e in events.values() if e["kind"] == "national")
assert all(v == 5 for v in cnt.values()), cnt
print("national grid ok; crisis per stage:", Counter(e["stage"] for e in events.values() if e["kind"] == "crisis"))
