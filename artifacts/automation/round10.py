import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".")

print("=== BOM state of touched files ===")
for rel in ("data/content/southwest_event_catalog.json",
            "data/scenario/tag_registry.json",
            "data/scenario/ownership_overrides.json",
            "yongchang_world/common/history/states/00_states.txt",
            "yongchang_world/common/history/pops/ywc_china_pops.txt",
            "yongchang_world/common/coat_of_arms/coat_of_arms/ywc_regional_coas.txt",
            "yongchang_world/common/dynamic_country_names/ywc_dynamic_names.txt"):
    head = (ROOT / rel).read_bytes()[:3]
    print(f"  {rel}: BOM={head == b'\xef\xbb\xbf'}")

print("=== error details from the failing tests ===")
r = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest",
                    "tests.test_tag_registry.TagRegistryTest.test_new_tags_do_not_collide_with_base",
                    "tests.test_regional_states.RegionalTagRegistryTest.test_regional_tags_are_new_and_registered",
                    "tests.test_scenario_tag_audit.ScenarioTagAuditTest.test_current_scenario_and_history_tags_are_clean"],
                   capture_output=True, text=True, encoding="utf-8", errors="ignore", cwd=ROOT)
print(r.stderr[-3000:])
