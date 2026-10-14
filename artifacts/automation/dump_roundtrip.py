from pathlib import Path

out = Path("artifacts/automation/roundtrip_states.txt").read_text(encoding="utf-8-sig")
i = out.find("STATE_SOUTHERN_MANCHURIA")
print("--- around SOUTHERN_MANCHURIA (first 500) ---")
print(out[i:i + 500])
print("--- the next 3 state openings after it ---")
import re
after = out[i + 10:]
for m in list(re.finditer(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=", after))[:3]:
    print(repr(after[m.start():m.start() + 40]))
print("--- count of state openings in the whole roundtrip file ---")
print(len(re.findall(r"(?m)^\s*s:STATE_[A-Z0-9_]+\s*=\s*\{", out)))
print("--- head of file (first 200) ---")
print(repr(out[:200]))
