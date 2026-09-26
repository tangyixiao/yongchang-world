import json

cat = json.load(open("data/content/large_campaign_event_catalog.json", encoding="utf-8"))
for e in cat["events"]:
    for i, c in enumerate(e["choices"]):
        if c["cost"]:
            tag = e.get("short") or f"crisis{e['crisis']}"
            print(f"{e['id']}.{chr(97+i)} cost={c['cost']} | {c['label_cn']}")
