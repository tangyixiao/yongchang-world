# Changelog

## v0.1.0-rc1 (prepared)

- Added the ten-country Yongchang World content slice for Victoria 3 1.13.11 (Matcha).
- Added bounded AI guardrails and DLC compatibility gates for `ep1_content`, `mp1_content`, and `ep2_content`.
- Added hidden-launch mount checks, bilingual content, political identities, dynamic names, colors, and pure-color CoA placeholders.
- Added the `ywc_nmg_autonomy_negotiation` diplomatic pact action: New Ming can open autonomy negotiations with Mexico while a subject and carrying the New Ming–Mexico chain journal; acceptance resolves the chain. Bilingual localization included. The in-game smoke suite gained a read-only `ywc_nmg_autonomy_action_ready` check, and engine strings confirmed `tools/scripted_tests` as the exact path the game queries for it.
- Replaced 57 placeholder journal and route titles (all ten countries) with proper English and Simplified Chinese display names, and added a localization parity test that keeps both languages key-aligned and placeholder-free.
- The smoke log collector now records `mod_mount` (mounted / not_mounted / unknown_no_debug_log) with the verbatim mount line in its summary; a fresh hidden launch re-verified `status=clean` with `mod_mount=mounted`.
- Normalized the in-game smoke suite's date literals to the vanilla bare form and statically grounded its trigger vocabulary against vanilla and mod precedents.
- Wired DMG (Dongming), NQG (Northern Qing), SHU (Yongchang), JHG (Jinghai), OIR (Oirat) and MNG (Khalkha) as fully playable countries: their journals now complete or fail through real bilingual decision events, following the content_catalog success/failure/abandon outcomes contract. The unwired journal allowlist drops from 58 to 26 and now exactly matches the remaining gaps (TIB, KOR, LAN, NMG).
- Fixed `install_dev_mod.ps1` for Windows PowerShell 5.1: the PS6+ `utf8NoBOM` encoding switch failed parameter binding on the machine default, so the documented install path did not run; the descriptor is now written BOM-free via `UTF8Encoding($false)`.
- Fixed the observation runner writing a UTF-8 BOM `content_load.json`, which the game rejects and silently falls back to "all DLC enabled, no mods". The runner now writes BOM-free JSON and records `mod_mount`, version-match evidence, observed DLC mounts, and ownership-backend state per hidden launch. A `-NoLaunch` rerun over an already-verified run now preserves the recorded evidence instead of overwriting it.
- Probes established that directly launched executables ignore `disabledDLC` when the ownership backend reports ownership, and that the backend flips between all-owned and none-owned across launches; single-DLC observation configs remain pending instead of being claimed as loaded.
- The 15-run / three-seed observation matrix is prepared but remains pending manual UI observation; no long-run statistics are claimed.

Known limits: most main journals and routes cannot currently complete (58 of 71 `*_resolved` completion variables are unwired to the event chains; tracked by an allowlist test), the mod does not change base map geometry, some regional starts use Province subsets, and NMG remains a contested Mexican autonomous subject.
