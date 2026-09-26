import json
from pathlib import Path

p = Path("data/scenario/southwest_states.json")
data = json.loads(p.read_text(encoding="utf-8-sig"))
data["starting_tags"] = ["RKN" if t == "ARA" else t for t in data["starting_tags"]]
print("starting_tags:", data["starting_tags"])
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("starting_tags updated")
