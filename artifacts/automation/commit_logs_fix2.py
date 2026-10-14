import subprocess
from pathlib import Path

ROOT = Path(".")
msg = """fix: in-game failures from the launch logs (settle FLAVOR, +1 deltas, pops scopes, dead CHI, journal adds)

The launch error.log pinned four real defects:

- ywc_campaign_settle_mid/settle_final were called with an unused FLAVOR
  argument, so the whole settlement effect failed to compile and the chapter
  outcomes never fired in game. The generator no longer emits FLAVOR.
- The hegemony counter ops emitted 'add = +1'; jomini rejects the leading
  plus. Deltas are now emitted with an explicit minus-sign convention.
- 25 create_pop blocks (mod and vanilla pops files targeting region_state:CHI
  and region_state:RUS in reassigned states) ran in a 'none' scope and were
  dropped. All displaced targets are retargeted to the new owners, and the
  china pops file was rebuilt in the verified working format (POPS wrapper on
  the first line, chunked create_pop blocks) - the earlier draft's BOM +
  leading comments tripped the effect compiler's 'Expected opening bracket'.
- chi - china.txt scoped to a country that no longer exists (15 'Failed to
  scope' errors) and is deleted; CHI is landless by design.

The ten-country journal adds from content_starts are now also performed by
the on_game_started_after_lobby on_action (idempotent), so every panel shows
its unique journals regardless of history-load ordering.

Gates: 395/395 tests, ywc_check (game root) clean, all content checkers
clean, git diff --check clean.
"""
Path("artifacts/automation/commit_logs_fix.txt").write_text(msg, encoding="utf-8", newline="\n")
subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
r = subprocess.run(["git", "commit", "-F", "artifacts/automation/commit_logs_fix.txt"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore")
print((r.stdout or r.stderr)[-200:])
Path("artifacts/automation/commit_logs_fix.txt").unlink(missing_ok=True)
subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
subprocess.run(["git", "commit", "--amend", "--no-edit"], cwd=ROOT, capture_output=True)
r = subprocess.run(["git", "push", "origin", "codex/yongchang-world-bootstrap"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore")
print(r.stdout[-200:] or r.stderr[-200:])
