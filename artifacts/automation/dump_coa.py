from pathlib import Path

t = Path("yongchang_world/common/coat_of_arms/coat_of_arms/ywc_core_coas.txt").read_text(encoding="utf-8-sig")
i = t.find("YWC_SHU")
out = t[i:i + 900] if i >= 0 else "YWC_SHU not found; head:\n" + t[:900]
Path("artifacts/automation/coa_sample.txt").write_text(out, encoding="utf-8")
print(out)
